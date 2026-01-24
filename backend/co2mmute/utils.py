import logging
from http import cookies

import redis
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CustomPasswordValidator:
    def validate(self, password, user=None):
        errors = []

        if not any(char.isdigit() for char in password):
            errors.append("The password must contain at least one digit.")
        if not any(char.isalpha() and char.islower() for char in password) or not any(
            char.isalpha() and char.isupper() for char in password
        ):
            errors.append(
                "The password must contain both lowercase and uppercase letters."
            )
        if not any(not char.isalnum() for char in password):
            errors.append("The password must contain at least one special character.")

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            "Your password must include at least one digit, one lowercase and uppercase "
            "letter, and one special character."
        )


def game_map_clean(version_game_maps, base_game_map):
    for version_game_map in version_game_maps:
        if version_game_map != base_game_map:
            raise ValidationError(
                f"MapVersion's GameMap {version_game_map} does not match Node's GameMap {base_game_map}"
            )


def per_passenger(value_per_vehicle_km: float, passengers_onboard: float) -> float:
    return float(value_per_vehicle_km) / max(1.0, float(passengers_onboard))


def get_graph_cache_key(map_pk: int, version_pk: int) -> str:
    """Generate cache key for a map version graph."""
    return f"map_graph:{map_pk}:{version_pk}"


def invalidate_map_version_graphs(map_pk: int) -> None:
    """
    Invalidate all cached graphs for a specific map.

    This should be called when nodes, edges, or other map data is modified.

    Args:
        map_pk: The GameMap primary key
    """
    # Get all cached keys pattern and delete those matching our map
    # Since we can't easily pattern-match in all cache backends,
    # we'll use a tracking approach with a set of version keys
    versions_key = f"map_versions:{map_pk}"
    cached_versions = cache.get(versions_key, set())

    # Clear all graph caches for this map's versions
    for version_pk in cached_versions:
        cache_key = get_graph_cache_key(map_pk, version_pk)
        cache.delete(cache_key)

    # Clear the versions tracker
    cache.delete(versions_key)


def track_cached_version(map_pk: int, version_pk: int) -> None:
    """
    Track a cached graph so we can invalidate it later.

    Args:
        map_pk: The GameMap primary key
        version_pk: The MapVersion primary key
    """
    versions_key = f"map_versions:{map_pk}"
    cached_versions = cache.get(versions_key, set())
    cached_versions.add(version_pk)
    cache.set(versions_key, cached_versions, timeout=None)  # Keep indefinitely


def sign_value(value, salt: str) -> str:
    signer = signing.TimestampSigner(salt=salt)
    return signer.sign(str(value))


def unsign_value(signed_value: str, salt: str):
    signer = signing.TimestampSigner(salt=salt)
    result = signer.unsign(signed_value, max_age=None)
    logger.debug(f"Unsigned value with salt {salt}: {signed_value} -> {result}")
    return result


def get_cookie_from_scope(scope, name: str) -> str | None:
    header_bytes = dict(scope.get("headers", {})).get(b"cookie", b"")
    if not header_bytes:
        return None
    jar = cookies.SimpleCookie()
    jar.load(header_bytes.decode("utf-8"))
    morsel = jar.get(name)
    return morsel.value if morsel else None


def set_signed_cookie(
    response,
    key: str,
    value,
    salt: str,
    httponly: bool = True,
    secure: bool = False,
    samesite: str = "Lax",
    max_age: int | None = None,
):
    signed_value = sign_value(value, salt)
    response.set_cookie(
        key,
        signed_value,
        httponly=httponly,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
    )
    return response


def set_game_access_cookie(request, response, game_id: str):
    token_store = request.session.setdefault("game_access_tokens", {})
    import uuid

    token = token_store.get(game_id)
    if not token:
        token = uuid.uuid4().hex
        token_store[game_id] = token
        request.session.modified = True

    secure_flag = (
        getattr(settings, "SESSION_COOKIE_SECURE", False) or request.is_secure()
    )

    # Embed game_id into cookie value for validation in ws_auth
    cookie_value = f"{game_id}:{token}"

    return set_signed_cookie(
        response,
        f"{settings.COOKIE_GAME_PREFIX}{game_id}",
        cookie_value,
        salt=settings.COOKIE_GAME_SALT,
        httponly=True,
        secure=secure_flag,
        samesite="Lax",
        max_age=settings.COOKIE_AGE,
    )


def set_player_cookie(request, response, game_id: str, player_id: str):
    store = request.session.setdefault("player_by_game", {})
    store[game_id] = player_id
    request.session.modified = True

    secure_flag = (
        getattr(settings, "SESSION_COOKIE_SECURE", False) or request.is_secure()
    )

    return set_signed_cookie(
        response,
        f"{settings.COOKIE_PLAYER_PREFIX}{game_id}",
        player_id,
        salt=settings.COOKIE_PLAYER_SALT,
        httponly=True,
        secure=secure_flag,
        samesite="Lax",
        max_age=settings.COOKIE_AGE,
    )


def sanitize_group_name(game_id: str) -> str:
    return game_id.replace(":", "_").replace("-", "_")


def round_complete(movecount, playercount) -> bool:
    return playercount > 0 and movecount >= playercount


def send_chat_system_message(game_id: str, message: str):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("No channel layer configured, cannot send chat system message")
        return
    group_name = f"chat_{sanitize_group_name(game_id)}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {"type": "chat.system", "message": message},
    )


CHAT_MESSAGES_REDIS_KEY_PATTERN = "chat:{game_id}:messages"


def clear_chat_messages(game_id: str):
    """Clear all chat messages for a game from Redis."""
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        key = CHAT_MESSAGES_REDIS_KEY_PATTERN.format(game_id=game_id)
        redis_client.delete(key)
        redis_client.close()
        logger.info(f"Cleared chat messages for game {game_id}")
    except Exception as e:
        logger.error(f"Failed to clear chat messages for game {game_id}: {e}")
