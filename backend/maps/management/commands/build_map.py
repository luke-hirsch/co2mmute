"""Build a map file from OpenStreetMap: a place name, or a box.

./manage.py build_map Bremen
./manage.py build_map --bbox 52.49,13.29,52.56,13.42 --name "Berlin Mitte-West"

`mapbuild/` does the work; what it downloads it keeps in `mapbuild/cache/` (or
`CO2MMUTE_MAP_CACHE`), so the second build of an area is offline. Writes the file
and the build report — what each rule gave, and what it could not fix. The file
then goes through `check_map`, `calibrate_map --out` and the import.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from mapbuild import area as areas
from mapbuild.build import build
from mapbuild.download import Missing, overpass_url
from mapbuild.mapfile import write


class Command(BaseCommand):
    help = "Baut eine Kartendatei aus OpenStreetMap: ein Ortsname oder eine Box."

    def add_arguments(self, parser):
        parser.add_argument(
            "place", nargs="?", metavar="ort", help="eine Gemeinde, z. B. Bremen"
        )
        parser.add_argument(
            "--bbox",
            metavar="süd,west,nord,ost",
            help="statt eines Orts eine Box, in Grad",
        )
        parser.add_argument("--name", help="der Name der Karte (sonst der des Orts)")
        parser.add_argument(
            "--out", metavar="datei.json", help="wohin (sonst in den Cache des Gebiets)"
        )

    def handle(self, *args, place, bbox, name, out, **options):
        if bool(place) == bool(bbox):
            raise CommandError("Entweder einen Ort oder --bbox.")
        try:
            if bbox:
                try:
                    s, w, n, e = (float(v) for v in bbox.split(","))
                    area = areas.box((s, w, n, e), name=name)
                except ValueError as exc:
                    raise CommandError(f"--bbox: {exc}") from exc
            else:
                area = areas.named(place)
            self.stdout.write(
                f"{area.name}: Daten von {overpass_url()} und den Quellen in mapbuild/download.py"
            )
            data, report = build(area, name=name)
        except Missing as exc:
            raise CommandError(str(exc)) from exc

        path = (
            Path(out) if out else area.cache / f"{areas.slug(name or area.name)}.json"
        )
        write(path, data)
        for heading, lines in report:
            if not lines:
                continue
            self.stdout.write(f"\n{heading}")
            for line in lines:
                self.stdout.write(f"  {line}")
        self.stdout.write(self.style.SUCCESS(f"\nGeschrieben: {path.resolve()}"))
        self.stdout.write(
            "Weiter: manage.py check_map <datei>, dann "
            "manage.py calibrate_map <datei> --speed <km/h> --out <datei> (auf Postgres), dann importieren."
        )
