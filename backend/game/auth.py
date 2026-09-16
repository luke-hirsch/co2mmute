"""One definition of "may this browser act in this game".

The check used to be written twice — game/permissions.py for
REST, game/ws_auth.py for the websocket — and the two had already drifted:
HasGameAccess validated the game id embedded in the game cookie, IsPlayerInGame
did not look at the game cookie at all.

Everything here takes a plain cookie mapping so both transports can call it.
"""

import logging

from co2mmute.utils import unsign_value
from django.conf import settings
from django.core import signing

logger = logging.getLogger(__name__)


def _unsign_scoped(raw: str, salt: str, game_id: str) -> str | None:
    """Unwrap a "<game_id>:<value>" cookie, verifying the game id.

    Returns the value, or None on a bad signature, an expired timestamp, a
    malformed payload, or a game id that does not match the one being asked
    about. Never raises — callers are permission checks.
    """
    try:
        payload = unsign_value(raw, salt)
    except signing.SignatureExpired:
        logger.info(f"Expired cookie for game {game_id}")
        return None
    except signing.BadSignature:
        logger.warning(f"Bad cookie signature for game {game_id}")
        return None

    if ":" not in payload:
        logger.warning(f"Malformed cookie payload for game {game_id}")
        return None

    cookie_game_id, value = payload.split(":", 1)
    if cookie_game_id != game_id:
        logger.warning(
            f"Cookie game id mismatch for {game_id}: cookie carries {cookie_game_id}"
        )
        return None

    return value


def has_game_access(cookies, game_id: str) -> bool:
    """True if the browser holds a valid game-access cookie for this game."""
    raw = cookies.get(f"{settings.COOKIE_GAME_PREFIX}{game_id}")
    if not raw:
        return False
    return _unsign_scoped(raw, settings.COOKIE_GAME_SALT, game_id) is not None


def resolve_player_id(cookies, game_id: str) -> str | None:
    """The player id this browser claims for this game, or None.

    Identity only — it does not check that the Player row still exists. Callers
    that need the row look it up themselves, because REST wants a queryset and
    the websocket wants it in a database_sync_to_async block.
    """
    raw = cookies.get(f"{settings.COOKIE_PLAYER_PREFIX}{game_id}")
    if not raw:
        return None
    return _unsign_scoped(raw, settings.COOKIE_PLAYER_SALT, game_id)
