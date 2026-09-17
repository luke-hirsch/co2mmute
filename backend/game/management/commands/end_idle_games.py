"""End games nobody has played for their idle_end_days. Roadmap.md 1.6.

./manage.py end_idle_games            # what the daily beat job does
./manage.py end_idle_games --dry-run  # show what would happen
"""

from django.core.management.base import BaseCommand

from game.idle import end_idle_game, games_due_for_idle_end, last_activity


class Command(BaseCommand):
    help = "End games that have been idle longer than their idle_end_days."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        games = games_due_for_idle_end()

        if options["dry_run"]:
            for game in games:
                self.stdout.write(
                    f"would end {game.game_id} ({game.game_name}), "
                    f"idle since {last_activity(game):%Y-%m-%d}"
                )
            self.stdout.write(self.style.WARNING(f"{len(games)} games, dry run"))
            return

        for game in games:
            end_idle_game(game)
        self.stdout.write(self.style.SUCCESS(f"{len(games)} games ended"))
