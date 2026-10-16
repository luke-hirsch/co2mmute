"""Write the research data of finished games to a sqlite file.

./manage.py export_research_data /abs/path/research.sqlite

Only games that are over and anonymised (`game/research_export.py`).
"""

from django.core.management.base import BaseCommand

from game.research_export import export_research_data


class Command(BaseCommand):
    help = "Write ended, anonymised games to a sqlite file for analysis."

    def add_arguments(self, parser):
        parser.add_argument("out", help="the sqlite file to write (replaced if there)")

    def handle(self, *args, **options):
        counts = export_research_data(options["out"])
        for table, n in counts.items():
            self.stdout.write(f"{table}: {n}")
        self.stdout.write(self.style.SUCCESS(f"{options['out']} geschrieben"))
