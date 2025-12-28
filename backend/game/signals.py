from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
import logging

from .cache import cache_game_session, invalidate_game_session
from .models import GameSession

logger = logging.getLogger(__name__)


@receiver(post_save, sender=GameSession)
def cache_session_when_live(sender, instance: GameSession, **kwargs):
    cache_game_session(instance)


@receiver(post_delete, sender=GameSession)
def clear_session_cache(sender, instance: GameSession, **kwargs):
    invalidate_game_session(instance.game_id)
