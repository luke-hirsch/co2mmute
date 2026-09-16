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
