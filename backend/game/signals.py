from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver, Signal
import logging
import asyncio
import threading
from django.utils import timezone

from .cache import cache_game_session, invalidate_game_session
from .models import GameSession, GameRound

logger = logging.getLogger(__name__)

# Custom signal fired when a round is completed (all players have moved)
round_completed = Signal()


@receiver(post_save, sender=GameSession)
def cache_session_when_live(sender, instance: GameSession, **kwargs):
    cache_game_session(instance)


@receiver(post_delete, sender=GameSession)
def clear_session_cache(sender, instance: GameSession, **kwargs):
    invalidate_game_session(instance.game_id)


@receiver(round_completed)
def on_round_completed(sender, game_id, **kwargs):
    """
    Handler for when all players have completed their moves in a round.
    Progresses to the next round or ends the game.
    """
    try:
        game = GameSession.objects.get(game_id=game_id)
        current_round = GameRound.objects.get(game=game, status="active")

        logger.info(f"Round {current_round.round_number} completed for game {game_id}")

        # Mark current round as completed
        current_round.status = "completed"
        current_round.save()

        # Check if game should end
        if current_round.round_number >= game.max_rounds:  # Max rounds reached
            logger.info(f"Game {game_id} reached max rounds")
            game.is_active = False
            game.ended_at = timezone.now()
            game.save()

            # Broadcast final state
            thread = threading.Thread(
                target=_broadcast_state, args=(game_id,), daemon=True
            )
            thread.start()
            return

        # Check CO2 limit (this will be enhanced in game engine)
        # For now, just proceed to next round

        # Create next round
        next_round_number = current_round.round_number + 1
        GameRound.objects.create(
            game=game, round_number=next_round_number, status="active"
        )

        logger.info(f"Created round {next_round_number} for game {game_id}")

        # Broadcast new game state
        thread = threading.Thread(target=_broadcast_state, args=(game_id,), daemon=True)
        thread.start()

    except GameRound.DoesNotExist:
        logger.warning(f"No active round found for game {game_id}")
    except GameSession.DoesNotExist:
        logger.warning(f"Game {game_id} not found")
    except Exception as e:
        logger.error(f"Error processing round completion: {e}")


def _broadcast_state(game_id: str):
    """Helper to broadcast game state in a background thread."""
    from .consumers import GameStateConsumer

    try:
        asyncio.run(GameStateConsumer.broadcast_game_state(game_id))
    except Exception as e:
        logger.error(f"Error broadcasting game state: {e}")
