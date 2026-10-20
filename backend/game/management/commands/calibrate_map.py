"""Measure a map's commuters, and what the budget buys on it.

./manage.py calibrate_map map.json --speed 19        # find the commuters, then the table
./manage.py calibrate_map map.json --commuters 6800  # keep the commuters, measure the table

The rule is in `game/calibration.py`: the commuters are as many as make a
morning where everybody drives as slow as the city's rush hour (`--speed`, in
km/h — the figure and its source come from whoever runs this; for Berlin, the
TomTom Traffic Index's 19.0). The budget is kg per person per round, the same
on every map, so what is measured about it is what it buys here: a round at
each car share, per person, and the share the normal kg stays inside. And the
share of the timetable the class pays (`GameMap.timetable_factor`): what its
riders would emit in buses as full as Germany's, over the base timetable, on
the round where half drive (`calibration.timetable_factor`). The table is that
bill — the rounds run the whole timetable, and the share is taken after.

The file is imported into a throwaway database, never the one the app runs
on: a test database of its own (`<name>_calibrate`) on the same Postgres, where
the rounds of a step play side by side. The simulation reads its rows in pk
order, never by name, so a round comes out the same whatever the rows are
called. Its graph goes through the
game's own router (`frontend/scripts/routes.mjs`, so Node and `npm ci` in
frontend/ are needed) and its rounds through the simulation, every one rolled
back. Only the pairs the seeds deal are routed, in the car and by public
transport. On Postgres the rounds of a step play side by side, one process
each (`--workers`, as many as the seeds unless the machine has fewer cores):
all of Berlin took four and a half hours one by one. Prints the answer and the
table it came from; `--out` writes a copy of the file carrying the count,
`calibrated: true` and the share.
"""

import json
import logging
import os
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


def calibrated_file(graph, result):
    """The file with what the calibration measured on it, for `--out`.

    The count and `calibrated: true`, and the share of the timetable the class
    pays where there was one to measure; where not, the file keeps its own. And
    the table of kg a head per car share, which the create form reads.
    """
    meta = graph.setdefault("map", {})
    meta["district_commuters"] = result.commuters
    # A file from before the budget was per person (2026-10-07).
    meta.pop("co2_budget_kg_per_round", None)
    meta["calibrated"] = True
    if result.timetable_factor is not None:
        meta["timetable_factor"] = result.timetable_factor
    meta["co2_table"] = result.co2_table
    return graph


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
            "--per-home",
            type=int,
            default=calibration.PER_HOME,
            help=(
                "Arbeitsorte, die jeder Wohnort pro Runde spielt, neu gezogen je "
                f"Seed (Vorgabe: {calibration.PER_HOME}; so viele, wie die Karte "
                "Arbeitsorte hat: jedes Paar)."
            ),
        )
        parser.add_argument(
            "--map-version",
            dest="version_name",
            help="Name der Version (Vorgabe: die Basisversion, auf der ein Spiel beginnt).",
        )
        parser.add_argument(
            "--workers",
            type=int,
            help=(
                "Prozesse, die die Runden eines Schritts nebeneinander spielen "
                "(Vorgabe: so viele wie Seeds, höchstens so viele wie Kerne)."
            ),
        )
        parser.add_argument(
            "--out",
            help=(
                "Kopie der Datei mit der Pendlerzahl, calibrated: true und dem "
                "Anteil am Fahrplan."
            ),
        )

    def handle(
        self,
        *args,
        file,
        speed,
        commuters,
        seeds,
        per_home,
        version_name,
        workers,
        out,
        **options,
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
        if per_home is not None and per_home < 1:
            raise CommandError("--per-home ist mindestens 1.")
        if workers is not None and workers < 1:
            raise CommandError("--workers ist mindestens 1.")

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
            # `autoclobber` drops whatever has the name.
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
                    per_home=per_home,
                    version_name=version_name,
                    workers=workers,
                )
            finally:
                connection.creation.destroy_test_db(old_name, verbosity=0)
                logging.disable(logging.NOTSET)

        self._report(graph, rounds, result)
        if out:
            Path(out).write_text(
                json.dumps(calibrated_file(graph, result), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            self.stdout.write(f"Geschrieben: {out}")

    def _calibrate(
        self, graph, path, *, speed, commuters, seeds, per_home, version_name, workers
    ):
        """Import, route and play — inside the throwaway database."""
        from game.measure import (
            PLAYED_MODES,
            MapRounds,
            RoutesRefused,
            RoutesUnavailable,
            client_routes,
            every_pair,
            version_graph,
        )
        from game.measure_workers import Workers
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
            served = version_graph(game_map, version)
            rounds = MapRounds(game_map, version, every_pair(served), host, per_home)
            played = rounds.played(seeds)
            rounds.route(client_routes(served, played, PLAYED_MODES))
        except RoutesUnavailable as exc:
            raise CommandError(f"Keine Routen: {exc}")

        if workers is None:
            workers = min(len(seeds), os.cpu_count() or 1)
        if self.verbose:
            dealt = f"je Wohnort {rounds.per_seat} gezogen, " if rounds.dealt else ""
            side = "einem Prozess" if workers == 1 else f"{workers} Prozessen"
            self.stdout.write(
                f"{game_map.name} — {version.name}: {len(rounds.commutes)} Wege, "
                f"{len(played)} davon gespielt, {dealt}{rounds.gruppen} Gruppen, "
                f"{len(seeds)} Seeds in {side}, gemessen auf {connection.vendor}"
            )
        try:
            if workers > 1:
                with Workers(rounds, workers) as pool:
                    result = calibration.calibrate(
                        self._shown(rounds.play),
                        play_many=self._shown_many(pool.play),
                        start=commuters or game_map.district_commuters,
                        smallest=rounds.gruppen,
                        target_kmh=speed,
                        commuters=commuters,
                        seeds=seeds,
                    )
            else:
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

    def _say(self, commuters, share, way_home):
        """Which measurement it is on, once — a calibration takes minutes."""
        key = (commuters, share, way_home)
        if self.verbose and key not in self._started:
            self._started.add(key)
            trip = "hin und zurück" if way_home else "Hinweg"
            self.stdout.write(
                f"  … {de(commuters)} Pendler, {round(share * 100)} % Auto, {trip}"
            )

    def _shown(self, play):
        """`play`, saying which measurement it is on."""
        self._started = set()

        def shown(*, commuters, share, seed, way_home=True):
            self._say(commuters, share, way_home)
            return play(commuters=commuters, share=share, seed=seed, way_home=way_home)

        return shown

    def _shown_many(self, play_many):
        """`play_many`, saying which measurements its rounds are on."""

        def shown(jobs):
            for job in jobs:
                self._say(job["commuters"], job["share"], job.get("way_home", True))
            return play_many(jobs)

        return shown

    def _report(self, graph, rounds, result):
        write = self.stdout.write
        write("")
        if result.target_kmh is not None:
            # The search measures mornings, the table plays there and back: a
            # way home that ran into the tick guard leaves no speed to show.
            if result.speed_kmh is None:
                reached = "alle im Auto: nicht alle angekommen (unten),"
            else:
                reached = f"alle im Auto fahren morgens {de(result.speed_kmh, 1)} km/h,"
            write(
                f"Pendler: {de(result.commuters)} — {reached} "
                f"Ziel {de(result.target_kmh, 1)} km/h"
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
                "für eine Runde ohne Auto. Nicht spielbar: nicht zu gewinnen. Mehr kg "
                "auf den Regler, oder den Fahrplan ausdünnen (weniger Linien, längerer "
                "Takt; Bus und Bahn fahren, ob jemand mitfährt oder nicht)."
            )
        elif share >= 1.0:
            write(
                f"Normal, {normal} kg pro Person und Runde, reicht hier auch, "
                "wenn alle Gruppen Auto fahren. Nicht spielbar: nicht zu verlieren. "
                "Weniger kg auf den Regler."
            )
        else:
            write(
                f"Normal, {normal} kg pro Person und Runde, reicht hier, wenn "
                f"{de(share * 100)} % der Gruppen Auto fahren."
            )
        factor = result.timetable_factor
        half = result.rows.get(calibration.TIMETABLE_SHARE, [])
        if factor is None:
            kept = graph.get("map", {}).get("timetable_factor", 1.0)
            write(
                "Anteil am Fahrplan: nicht messbar — bei "
                f"{round(calibration.TIMETABLE_SHARE * 100)} % Auto fährt niemand "
                "Bus oder Bahn, oder die Karte hat keine Linien. Die Tabelle rechnet "
                f"mit dem ganzen Fahrplan, die Datei behält ihren Anteil ({de(kept, 2)})."
            )
        else:
            average = statistics.mean(r.average_kg for r in half)
            base = statistics.mean(r.base_kg for r in half)
            whole = " — mehr als der Fahrplan, also ganz" if average >= base else ""
            write(
                f"Anteil am Fahrplan: {de(factor, 2)}. Bei "
                f"{round(calibration.TIMETABLE_SHARE * 100)} % Auto stoßen die "
                "Mitfahrenden, Bus und Bahn so voll wie in Deutschland (Umweltbundesamt: "
                "Bus 90, Tram 42, Bahn 44 g pro Personen-km), "
                f"{de(average)} kg aus, der Grundfahrplan {de(base)} kg{whole}."
            )
        people = rounds.gruppen * rounds.people_per_gruppe(result.commuters)
        write(
            f"  {de(rounds.people_per_gruppe(result.commuters))} Menschen pro Gruppe, "
            f"{de(people)} auf der Karte, Mittel über "
            f"{len(next(iter(result.rows.values())))} Seeds, hin und zurück; "
            f"pro Person heißt: die Runde durch {de(result.commuters)} Pendler, "
            "wie das Budget; Runde und Fahrplan mit dem Anteil"
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
            timetable = mean("timetable_kg") * (1.0 if factor is None else factor)
            write(
                f"{round(share * 100):>8} % {de(per_person[share], 2):>9} kg "
                f"{de(per_person[share] * result.commuters):>8} kg "
                f"{de(mean('car_kg')):>8} kg {de(timetable):>8} kg "
                f"{trip:>19} {minutes(mean('pt_trip_min')):>12} "
                f"{minutes(mean('pt_wait_min')):>8} {max(r.not_home for r in played):>10}"
            )

        notes = []
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
        if per_person[0.0] > per_person[1.0]:
            notes.append(
                "Eine Runde ohne Auto kostet hier mehr als eine, in der alle fahren: "
                "der Fahrplan fährt, ob jemand mitfährt oder nicht."
            )
        if notes:
            write("")
            for note in notes:
                write(note)
