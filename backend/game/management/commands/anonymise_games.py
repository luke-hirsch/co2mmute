"""Anonymise finished games from the command line.

./manage.py anonymise_games            # respects the grace period
./manage.py anonymise_games --all      # every ended game, ignore the grace period
./manage.py anonymise_games --dry-run  # show what would happen
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from game.anon import anonymise_game, games_due_for_anonymisation
from game.models import GameSession


class Command(BaseCommand):
    help = "Replace player names with 'Spieler N' in finished games."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", dest="all_ended")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if options["all_ended"]:
            games = GameSession.objects.filter(
                ended_at__isnull=False, anonymised_at__isnull=True
            )
        else:
            games = games_due_for_anonymisation(settings.ANONYMISE_GRACE_HOURS)

        if options["dry_run"]:
            for game in games:
                self.stdout.write(f"would anonymise {game.game_id} ({game.game_name})")
            self.stdout.write(self.style.WARNING(f"{games.count()} games, dry run"))
            return

        total = sum(anonymise_game(game) for game in games)
        self.stdout.write(self.style.SUCCESS(f"{total} players anonymised"))
