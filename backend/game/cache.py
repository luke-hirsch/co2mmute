from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import GameSession


CACHE_TIMEOUT_SECONDS = getattr(settings, "GAME_SESSION_CACHE_TIMEOUT", 15 * 60)
CACHE_KEY_TEMPLATE = "game:session:{game_id}"


def _cache_key(game_id: str) -> str:
    return CACHE_KEY_TEMPLATE.format(game_id=game_id.upper())


def _should_cache(session: GameSession) -> bool:
    if not session:
        return False

    if session.ended_at:
        return False

    return session.started_at is not None or session.lobby_open <= timezone.now()


def cache_game_session(session: Optional[GameSession]):
    """
    Store the session in cache if it is live or the lobby is open.
    Otherwise clear any stale entry.
    """
    if not session:
        return

    key = _cache_key(session.game_id)
    if _should_cache(session):
        cache.set(key, session, CACHE_TIMEOUT_SECONDS)
    else:
        cache.delete(key)


def invalidate_game_session(game_id: str):
    if not game_id:
        return
    cache.delete(_cache_key(game_id))


def get_cached_game_session(game_id: str) -> Optional[GameSession]:
    """
    Fetch a GameSession from cache, falling back to DB and caching the result.
    """
    if not game_id:
        return None

    normalized = game_id.upper()
    key = _cache_key(normalized)

    session = cache.get(key)
    if session:
        return session

    session = (
        GameSession.objects.select_related("game_map", "game_host")
        .filter(game_id=normalized)
        .first()
    )
    cache_game_session(session)
    return session
