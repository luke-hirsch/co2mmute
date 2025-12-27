"""
Centralized cookie handling using Django's signing module.

This module provides a unified way to sign and unsign cookies across the application.
All cookie operations should go through these functions to ensure consistency.
"""

from django.core import signing
from django.conf import settings
from http import cookies
import logging

logger = logging.getLogger(__name__)


def sign_value(value, salt: str) -> str:
    """
    Sign a value using Django's TimestampSigner to match set_signed_cookie format.

    This uses TimestampSigner which is what Django's set_signed_cookie() uses internally.
    The signed value includes a timestamp and is URL-safe.

    Args:
        value: The value to sign (will be converted to string if needed)
        salt: The salt to use for signing

    Returns:
        A signed string value with timestamp
    """
    signer = signing.TimestampSigner(salt=salt)
    return signer.sign(str(value))


def unsign_value(signed_value: str, salt: str):
    """
    Unsign a value using Django's TimestampSigner to match set_signed_cookie format.

    This verifies the timestamp signature and returns the original value.

    Args:
        signed_value: The signed value to unsign
        salt: The salt used when signing

    Returns:
        The original value as a string

    Raises:
        signing.BadSignature: If the signature is invalid or expired
        signing.SignatureExpired: If the signature is too old
    """
    signer = signing.TimestampSigner(salt=salt)
    # Note: We don't set max_age here, as cookies should be validated by max_age parameter
    # The timestamp is just for integrity checking
    result = signer.unsign(signed_value, max_age=None)
    logger.debug(f"Unsigned value with salt {salt}: {signed_value} -> {result}")
    return result


def get_cookie_from_scope(scope, name: str) -> str | None:
    """
    Extract a cookie value from a WebSocket scope.

    Args:
        scope: The WebSocket connection scope
        name: The cookie name to retrieve

    Returns:
        The cookie value if found, None otherwise
    """
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
    """
    Set a signed cookie on a response using Django's signing module.

    This method uses signing.dumps() and sets the signed value directly,
    ensuring consistency with unsigning via signing.loads().

    Args:
        response: The HttpResponse object
        key: The cookie name
        value: The value to sign and set
        salt: The salt to use for signing
        httponly: Whether the cookie should be HTTP-only
        secure: Whether the cookie should be secure (HTTPS only)
        samesite: SameSite attribute value
        max_age: Max age in seconds

    Returns:
        The response object with the signed cookie set
    """
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
    """
    Set the game access cookie for a specific game session.

    Args:
        request: The HttpRequest object
        response: The HttpResponse object
        game_id: The game session ID

    Returns:
        The response object with the cookie set
    """
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
    """
    Set the player identification cookie for a specific game session.

    Args:
        request: The HttpRequest object
        response: The HttpResponse object
        game_id: The game session ID
        player_id: The player ID to set

    Returns:
        The response object with the cookie set
    """
    # Mirror to session for convenience/debugging (optional)
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
