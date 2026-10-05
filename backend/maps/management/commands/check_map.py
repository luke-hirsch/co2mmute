"""Check map files against what every map has to keep.

./manage.py check_map map.json [more.json ...]

`maps/checks.py`, file by file. Reads the file only — nothing is imported and
no database is touched. Fails if any file has a problem, so a script can stop
on it; every file is checked first.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from maps.checks import check_map


class Command(BaseCommand):
    help = "Prüft Kartendateien auf das, was jede Karte einhalten muss."

    def add_arguments(self, parser):
        parser.add_argument("files", nargs="+", metavar="datei.json")

    def handle(self, *args, files, **options):
        failed = 0
        for name in files:
            path = Path(name)
            try:
                graph = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f"{path}: nicht lesbar — {exc}"))
                continue

            problems = check_map(graph)
            if not problems:
                self.stdout.write(self.style.SUCCESS(f"{path}: in Ordnung"))
                continue
            failed += 1
            self.stdout.write(self.style.ERROR(f"{path}: {len(problems)} Probleme"))
            for problem in problems:
                self.stdout.write(f"  [{problem.check}] {problem.message}")

        if failed:
            raise CommandError(f"{failed} von {len(files)} Dateien haben Probleme.")
