from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver, Signal
import logging
import asyncio
import threading
from django.utils import timezone

from game.cache import cache_game_session, invalidate_game_session
from game.models import GameSession, GameRound
from game.consumers import GameStateConsumer

logger = logging.getLogger(__name__)

round_completed = Signal()


@receiver(post_save, sender=GameSession)
def cache_session_when_live(sender, instance: GameSession, **kwargs):
    cache_game_session(instance)


@receiver(post_delete, sender=GameSession)
def clear_session_cache(sender, instance: GameSession, **kwargs):
    invalidate_game_session(instance.game_id)


@receiver(round_completed)
def on_round_completed(sender, game_id, **kwargs):
    try:
        game = GameSession.objects.get(game_id=game_id)
        current_round = GameRound.objects.get(game=game, status="active")

        current_round.status = "completed"
        current_round.save()

        if current_round.round_number >= game.max_rounds:
            logger.info(f"Game {game_id} reached max rounds")
            game.is_active = False
            game.ended_at = timezone.now()
            game.save()

            thread = threading.Thread(
                target=_broadcast_state, args=(game_id,), daemon=True
            )
            thread.start()
            return
        next_round_number = current_round.round_number + 1
        GameRound.objects.create(
            game=game, round_number=next_round_number, status="active"
        )
        thread = threading.Thread(target=_broadcast_state, args=(game_id,), daemon=True)
        thread.start()

    except GameRound.DoesNotExist:
        logger.warning(f"No active round found for game {game_id}")
    except GameSession.DoesNotExist:
        logger.warning(f"Game {game_id} not found")
    except Exception as e:
        logger.error(f"Error processing round completion: {e}")


def _broadcast_state(game_id: str):
    try:
        asyncio.run(GameStateConsumer.broadcast_game_state(game_id))
    except Exception as e:
        logger.error(f"Error broadcasting game state: {e}")
