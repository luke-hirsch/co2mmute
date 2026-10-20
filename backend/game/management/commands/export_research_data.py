"""Write the research data of finished games to a zip of CSV files.

./manage.py export_research_data /abs/path/research.zip
./manage.py export_research_data /abs/dir/          (research-<date>.zip inside)

Only games that are over and anonymised (`game/research_export.py`).
"""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from game.research_export import export_research_data


class Command(BaseCommand):
    help = "Write ended, anonymised games as CSV files in one zip for analysis."

    def add_arguments(self, parser):
        parser.add_argument(
            "out",
            nargs="?",
            default=".",
            help=(
                "the zip to write (replaced if there), or a directory for "
                "research-<date>.zip; the current directory if left out"
            ),
        )

    def handle(self, *args, **options):
        out = Path(options["out"])
        if out.is_dir():
            out = out / f"research-{timezone.localdate().isoformat()}.zip"
        counts = export_research_data(out)
        for table, n in counts.items():
            self.stdout.write(f"{table}: {n}")
        self.stdout.write(self.style.SUCCESS(f"{out} geschrieben"))
