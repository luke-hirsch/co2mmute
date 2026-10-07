"""Measure a map's commuters, and what the budget buys on it.

./manage.py calibrate_map map.json --speed 19        # find the commuters, then the table
./manage.py calibrate_map map.json --commuters 6800  # keep the commuters, measure the table

The rule is in `game/calibration.py`: the commuters are as many as make a
morning where everybody drives as slow as the city's rush hour (`--speed`, in
km/h — the figure and its source come from whoever runs this; for Berlin, the
TomTom Traffic Index's 19.0). The budget is kg per person per round, the same
on every map, so what is measured about it is what it buys here: a round at
each car share, per person, and the share the normal kg stays inside.

The file is imported into a throwaway database, never the one the app runs
on: a test database of its own, in memory under sqlite. Measure on Postgres
(`DJANGO_DB=postgres`) for numbers that go into a file: the simulation reads
its links in name order, which every database sorts its own way, so a round
with riders comes out about 1.5 % apart on sqlite and on the box. Its graph goes through the
game's own router (`frontend/scripts/routes.mjs`, so Node and `npm ci` in
frontend/ are needed) and its rounds through the simulation, every one rolled
back. Prints the answer and the table it came from; `--out` writes a copy of
the file carrying the count and `calibrated: true`.
"""

import json
import logging
import statistics
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import override_settings

from game import calibration
from maps.checks import check_map

# The game's own backends would reach Redis: the round's broadcasts, the graph
# cache. A calibration has no audience and no box.
QUIET_BACKENDS = dict(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    CELERY_TASK_ALWAYS_EAGER=True,
)


def de(value, digits=0):
    """A number the way the German pages write it: 16.174 · 22,5."""
    text = f"{value:,.{digits}f}"
    return text.replace(",", " ").replace(".", ",").replace(" ", ".")


def minutes(value):
    return "—" if value is None else f"{de(value, 1)} min"


class Command(BaseCommand):
    help = (
        "Misst die Pendlerzahl einer Karte nach der Kalibrierungsregel und was "
        "das CO₂-Budget pro Person auf ihr reicht."
    )

    def add_arguments(self, parser):
        parser.add_argument("file", metavar="datei.json")
        which = parser.add_mutually_exclusive_group(required=True)
        which.add_argument(
            "--speed",
            type=float,
            help="Tempo der Stadt im Berufsverkehr, km/h: daraus die Pendlerzahl.",
        )
        which.add_argument(
            "--commuters",
            type=int,
            help="Pendlerzahl behalten und nur die Tabelle messen.",
        )
        parser.add_argument(
            "--seeds",
            type=int,
            default=len(calibration.SEEDS),
            help="Wie viele Seeds pro Messung (6).",
        )
        parser.add_argument(
            "--map-version",
            dest="version_name",
            help="Name der Version (Vorgabe: die Basisversion, auf der ein Spiel beginnt).",
        )
        parser.add_argument(
            "--out", help="Kopie der Datei mit der Pendlerzahl und calibrated: true."
        )

    def handle(
        self, *args, file, speed, commuters, seeds, version_name, out, **options
    ):
        path = Path(file)
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CommandError(f"{path}: nicht lesbar — {exc}")

        problems = check_map(graph)
        if problems:
            for problem in problems:
                self.stdout.write(f"  [{problem.check}] {problem.message}")
            raise CommandError(
                f"{path}: {len(problems)} Probleme — erst `check_map`, dann kalibrieren."
            )
        if not 1 <= seeds <= len(calibration.SEEDS):
            raise CommandError(
                f"--seeds liegt zwischen 1 und {len(calibration.SEEDS)}."
            )
        if speed is not None and speed <= 0:
            raise CommandError("--speed ist ein Tempo in km/h, größer als null.")

        self.verbose = options["verbosity"] >= 1
        old_name = connection.settings_dict["NAME"]
        # `testserver` is the host of the request `version_graph` makes, as
        # under the test runner, which adds it the same way.
        with tempfile.TemporaryDirectory() as media, override_settings(
            MEDIA_ROOT=media,
            ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, "testserver"],
            **QUIET_BACKENDS,
        ):
            logging.disable(logging.INFO)
            # A database of its own, so a test run beside it keeps its own:
            # `autoclobber` drops whatever has the name. Under sqlite the test
            # database is in memory and has none.
            if connection.vendor != "sqlite":
                connection.settings_dict["TEST"] = {
                    **connection.settings_dict.get("TEST", {}),
                    "NAME": f"{old_name}_calibrate",
                }
            connection.creation.create_test_db(
                verbosity=0, autoclobber=True, serialize=False
            )
            try:
                result, rounds = self._calibrate(
                    graph,
                    path,
                    speed=speed,
                    commuters=commuters,
                    seeds=calibration.SEEDS[:seeds],
                    version_name=version_name,
                )
            finally:
                connection.creation.destroy_test_db(old_name, verbosity=0)
                logging.disable(logging.NOTSET)

        self._report(graph, rounds, result)
        if out:
            meta = graph.setdefault("map", {})
            meta["district_commuters"] = result.commuters
            # A file from before the budget was per person (F8 step 2b).
            meta.pop("co2_budget_kg_per_round", None)
            meta["calibrated"] = True
            Path(out).write_text(
                json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            self.stdout.write(f"Geschrieben: {out}")

    def _calibrate(self, graph, path, *, speed, commuters, seeds, version_name):
        """Import, route and play — inside the throwaway database."""
        from game.measure import (
            MapRounds,
            RoutesRefused,
            RoutesUnavailable,
            client_routes,
            version_graph,
        )
        from maps.importer import ImportRefused, MapImporter
        from maps.models import MapVersion

        host = get_user_model().objects.create_user("kalibrierung", is_staff=True)
        meta = graph.get("map", {})
        try:
            game_map = MapImporter(host).run(
                {
                    "map_name": meta.get("name") or path.stem,
                    "json_file": ContentFile(path.read_bytes(), name=path.name),
                    "image_file": None,
                    "description": "",
                    "max_players": meta.get("max_player")
                    or calibration.DEFAULT_MAX_PLAYERS,
                }
            )
        except ImportRefused as exc:
            raise CommandError(f"{path}: der Upload lehnt die Datei ab — {exc}")

        versions = MapVersion.objects.filter(game_map=game_map)
        version = (
            versions.filter(name=version_name).first()
            if version_name
            else versions.filter(base_version=True).first()
        )
        if version is None:
            names = ", ".join(versions.values_list("name", flat=True))
            raise CommandError(f"Keine Version „{version_name}“. Es gibt: {names}")

        try:
            routes = client_routes(version_graph(game_map, version))
            rounds = MapRounds(game_map, version, routes, host)
        except RoutesUnavailable as exc:
            raise CommandError(f"Keine Routen: {exc}")

        if self.verbose:
            self.stdout.write(
                f"{game_map.name} — {version.name}: {len(rounds.commutes)} Wege, "
                f"{rounds.gruppen} Gruppen, {len(seeds)} Seeds, "
                f"gemessen auf {connection.vendor}"
            )
        try:
            result = calibration.calibrate(
                self._shown(rounds.play),
                start=commuters or game_map.district_commuters,
                smallest=rounds.gruppen,
                target_kmh=speed,
                commuters=commuters,
                seeds=seeds,
            )
        except calibration.CalibrationRefused as exc:
            raise CommandError(str(exc))
        except RoutesRefused as exc:
            raise CommandError(
                "Der Router findet Wege, die das Spiel ablehnen würde:\n  "
                + "\n  ".join(exc.errors)
            )
        return result, rounds

    def _shown(self, play):
        """`play`, saying which measurement it is on — a calibration takes minutes."""
        started = set()

        def shown(*, commuters, share, seed, way_home=True):
            key = (commuters, share, way_home)
            if self.verbose and key not in started:
                started.add(key)
                trip = "hin und zurück" if way_home else "Hinweg"
                self.stdout.write(
                    f"  … {de(commuters)} Pendler, {round(share * 100)} % Auto, {trip}"
                )
            return play(commuters=commuters, share=share, seed=seed, way_home=way_home)

        return shown

    def _report(self, graph, rounds, result):
        write = self.stdout.write
        write("")
        if result.target_kmh is not None:
            write(
                f"Pendler: {de(result.commuters)} — alle im Auto fahren morgens "
                f"{de(result.speed_kmh, 1)} km/h, Ziel {de(result.target_kmh, 1)} km/h"
            )
            for population, speed in sorted(result.searched.items()):
                shown = "nie fertig" if speed is None else f"{de(speed, 1)} km/h"
                write(f"  gemessen: {de(population)} Pendler → {shown}")
        else:
            speed = (
                "—" if result.speed_kmh is None else f"{de(result.speed_kmh, 1)} km/h"
            )
            write(
                f"Pendler: {de(result.commuters)} (vorgegeben) — alle im Auto: {speed}"
            )
        normal = de(calibration.CO2_KG_PER_PERSON_NORMAL, 1)
        share = result.normal_share
        if share is None:
            write(
                f"Normal, {normal} kg pro Person und Runde, reicht hier nicht einmal "
                "für eine Runde ohne Auto."
            )
        elif share >= 1.0:
            write(
                f"Normal, {normal} kg pro Person und Runde, reicht hier auch, "
                "wenn alle Gruppen Auto fahren."
            )
        else:
            write(
                f"Normal, {normal} kg pro Person und Runde, reicht hier, wenn "
                f"{de(share * 100)} % der Gruppen Auto fahren."
            )
        people = rounds.gruppen * rounds.people_per_gruppe(result.commuters)
        write(
            f"  {de(rounds.people_per_gruppe(result.commuters))} Menschen pro Gruppe, "
            f"{de(people)} auf der Karte, Mittel über "
            f"{len(next(iter(result.rows.values())))} Seeds, hin und zurück; "
            f"pro Person heißt: die Runde durch {de(result.commuters)} Pendler, "
            "wie das Budget"
        )
        write("")
        write(
            "Autoanteil   pro Person       Runde        Auto    Fahrplan"
            "   Auto hin / zurück   Bus & Bahn   Warten   nicht da"
        )
        per_person = result.per_person
        for share, played in result.rows.items():

            def mean(attribute):
                values = [getattr(r, attribute) for r in played]
                values = [v for v in values if v is not None]
                return statistics.mean(values) if values else None

            car = mean("car_trip_min")
            back = mean("car_return_min")
            trip = "—" if car is None else f"{de(car, 1)} / {de(back or 0, 1)} min"
            write(
                f"{round(share * 100):>8} % {de(per_person[share], 2):>9} kg "
                f"{de(mean('total_kg')):>8} kg "
                f"{de(mean('car_kg')):>8} kg {de(mean('timetable_kg')):>8} kg "
                f"{trip:>19} {minutes(mean('pt_trip_min')):>12} "
                f"{minutes(mean('pt_wait_min')):>8} {max(r.not_home for r in played):>10}"
            )

        notes = []
        if connection.vendor == "sqlite":
            notes.append(
                "Gemessen auf SQLite. Die Simulation liest ihre Strecken in der "
                "Reihenfolge ihrer Namen, und die sortiert jede Datenbank anders: "
                "Runden mit Bus und Bahn liegen hier um gut 1 % neben Postgres, "
                "auf dem gespielt wird. Für die Zahlen, die in die Datei gehen: "
                "DJANGO_DB=postgres."
            )
        switched = max(r.switched for rows in result.rows.values() for r in rows)
        if switched:
            notes.append(
                f"{switched} Gruppen hatten in ihrem Verkehrsmittel keinen Weg und "
                "haben das andere genommen."
            )
        if any(r.not_home for rows in result.rows.values() for r in rows):
            notes.append(
                "Nicht alle sind angekommen: ein Durchlauf hat seine Grenze erreicht. "
                "Das ist ein Fehler der Karte oder des Modells, kein Ergebnis."
            )
        none = statistics.mean(r.total_kg for r in result.rows[0.0])
        everyone = statistics.mean(r.total_kg for r in result.rows[1.0])
        if none > everyone:
            notes.append(
                "Eine Runde ohne Auto kostet hier mehr als eine, in der alle fahren: "
                "der Fahrplan fährt, ob jemand mitfährt oder nicht."
            )
        if notes:
            write("")
            for note in notes:
                write(note)
