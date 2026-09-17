"""
Celery tasks for game-related async operations.
"""

import logging

from celery import shared_task
from co2mmute.utils import send_game_state_message

from game.models import GameRound

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_simulation_task(self, game_round_id: int):
    """Run the round-end work off the request thread.

    Deliberately thin. handle_round_completed is the single definition of what
    finishing a round means — simulate, write totals, check the end conditions,
    broadcast, enter the STATS phase — and it already broadcasts progress to the
    group GameConsumer actually joins (gamestate_<game_id>, via
    send_game_state_message). This task only decides *where* that runs.
    """
    from game.signals import round_completed

    try:
        game_round = GameRound.objects.select_related("game", "game__game_map").get(
            id=game_round_id
        )
    except GameRound.DoesNotExist:
        logger.error(f"GameRound {game_round_id} not found")
        return None

    try:
        round_completed.send(
            sender=GameRound,
            game_session=game_round.game,
            game_round=game_round,
        )
    except Exception as exc:
        logger.exception(
            f"Round completion failed for round {game_round.round_number} "
            f"of game {game_round.game.game_id}"
        )
        send_game_state_message(
            game_round.game.game_id,
            "simulation.failed",
            {
                "round_number": game_round.round_number,
                "error": str(exc),
            },
        )
        raise self.retry(exc=exc, countdown=5)

    return game_round_id


@shared_task
def cleanup_old_simulations(days_old: int = 30):
    """
    Clean up simulation data older than specified days.

    Args:
        days_old: Number of days after which to clean up data
    """
    from datetime import timedelta

    from django.utils import timezone

    from game.models import EdgeTrafficSnapshot

    cutoff_date = timezone.now() - timedelta(days=days_old)

    # Delete old traffic snapshots (they're large)
    deleted_count, _ = EdgeTrafficSnapshot.objects.filter(
        simulation__game_round__start_time__lt=cutoff_date
    ).delete()

    logger.info(f"Cleaned up {deleted_count} old traffic snapshots")

    return deleted_count


@shared_task
def anonymise_finished_games():
    """Sweep games whose grace period has run out. Roadmap.md 1.3.

    Runs on a schedule rather than on game end so the post-game summary still
    shows real names while the class is looking at it.
    """
    from django.conf import settings

    from game.anon import anonymise_game, games_due_for_anonymisation

    grace_hours = settings.ANONYMISE_GRACE_HOURS
    due = games_due_for_anonymisation(grace_hours)

    total = 0
    for game in due:
        try:
            total += anonymise_game(game)
        except Exception:
            # One bad game must not stop the sweep.
            logger.exception(f"Anonymisation failed for game {game.game_id}")

    if total:
        logger.info(f"Anonymised {total} players across {due.count()} games")
    return total


@shared_task
def end_idle_games():
    """End games idle for longer than their idle_end_days. Roadmap.md 1.6.

    anonymise_finished_games picks them up after the grace period, like any
    other ended game.
    """
    from game.idle import end_idle_game, games_due_for_idle_end

    ended = 0
    for game in games_due_for_idle_end():
        try:
            end_idle_game(game)
            ended += 1
        except Exception:
            # One bad game must not stop the sweep.
            logger.exception(f"Idle end failed for game {game.game_id}")

    if ended:
        logger.info(f"Ended {ended} idle games")
    return ended


@shared_task
def clear_expired_sessions():
    """Delete expired django_session rows. Roadmap.md 1.3.

    The DB session backend never does this on its own. Before 1.2 every join
    wrote the player id into the session, and for a logged-in user that row
    links the account to the player.
    """
    from django.core.management import call_command

    call_command("clearsessions")
