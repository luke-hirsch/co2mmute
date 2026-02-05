"""
Celery tasks for game-related async operations.
"""

import logging

from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from game.models import GameRound, SimulationResult

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_simulation_task(self, game_round_id: int):
    """
    Run traffic simulation for a game round asynchronously.

    Args:
        game_round_id: ID of the GameRound to simulate

    Returns:
        Simulation result ID on success
    """
    try:
        game_round = GameRound.objects.select_related("game", "game__game_map").get(
            id=game_round_id
        )
    except GameRound.DoesNotExist:
        logger.error(f"GameRound {game_round_id} not found")
        return None

    game = game_round.game
    channel_layer = get_channel_layer()

    def broadcast_progress(tick: int, total_ticks: int):
        """Broadcast simulation progress to game group."""
        async_to_sync(channel_layer.group_send)(
            f"game_{game.pk}",
            {
                "type": "simulation.progress",
                "data": {
                    "round_number": game_round.round_number,
                    "status": "running",
                    "tick": tick,
                    "total_ticks": total_ticks,
                    "progress_percent": int((tick / total_ticks) * 100),
                },
            },
        )

    try:
        # Import here to avoid circular imports
        from game.simulation import TrafficSimulator

        # Get scale from game map
        scale = game.game_map.scale if game.game_map else 100.0

        # Broadcast simulation starting
        async_to_sync(channel_layer.group_send)(
            f"game_{game.pk}",
            {
                "type": "simulation.progress",
                "data": {
                    "round_number": game_round.round_number,
                    "status": "starting",
                    "tick": 0,
                    "total_ticks": 200,
                    "progress_percent": 0,
                },
            },
        )

        # Run simulation
        simulator = TrafficSimulator(game_round, scale=scale)
        result = simulator.run_simulation(
            max_ticks=200,
            on_progress=broadcast_progress,
        )

        # Broadcast completion
        async_to_sync(channel_layer.group_send)(
            f"game_{game.pk}",
            {
                "type": "round.completed",
                "data": {
                    "round_number": game_round.round_number,
                    "simulation_id": result.id,
                    "status": "completed",
                    "total_co2_g": result.total_co2_g,
                    "total_cost_eur": result.total_cost_eur,
                },
            },
        )

        logger.info(
            f"Simulation completed for round {game_round.round_number} "
            f"of game {game.pk}: CO2={result.total_co2_g}g"
        )

        return result.id

    except Exception as e:
        logger.exception(f"Simulation failed for round {game_round.round_number}")

        # Broadcast failure
        async_to_sync(channel_layer.group_send)(
            f"game_{game.pk}",
            {
                "type": "simulation.failed",
                "data": {
                    "round_number": game_round.round_number,
                    "error": str(e),
                },
            },
        )

        # Retry if not max retries
        raise self.retry(exc=e, countdown=5)


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
