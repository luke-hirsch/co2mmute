from django.conf import settings
from django.core import signing
from rest_framework.permissions import BasePermission

from .cache import get_cached_game_session
from .models import Player
from .cookie_utils import unsign_value
import logging

logger = logging.getLogger(__name__)


class HasGameAccess(BasePermission):
    message = "You do not have access to this game session."

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False

        if request.user.is_authenticated:
            session = get_cached_game_session(game_id)
            if session and session.game_host == request.user:
                logger.info(f"Host {request.user} has access to game {game_id}")
                return True

        cookie_name = f"{settings.COOKIE_GAME_PREFIX}{game_id}"
        try:
            raw_cookie = request.COOKIES.get(cookie_name)
            if not raw_cookie:
                logger.warning(f"Game access cookie not found: {cookie_name}")
                return False

            cookie_value = unsign_value(raw_cookie, settings.COOKIE_GAME_SALT)

            if ":" not in cookie_value:
                logger.warning(f"Malformed game cookie for {game_id}")
                return False
            cookie_game_id, _ = cookie_value.split(":", 1)
            has_access = cookie_game_id == game_id
            logger.info(f"Game cookie access for {game_id}: {has_access}")
            return has_access
        except signing.BadSignature as e:
            logger.warning(f"Game cookie signature failed for {cookie_name}: {e}")
            return False
        except (KeyError, ValueError) as e:
            logger.warning(f"Game cookie check failed for {cookie_name}: {e}")
            return False


class IsPlayerInGame(BasePermission):
    message = "You are not a player in this game session."

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False

        cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"

        try:
            raw_cookie = request.COOKIES.get(cookie_name)
            if not raw_cookie:
                logger.warning(f"Player cookie not found: {cookie_name}")
                return False

            player_id = unsign_value(raw_cookie, settings.COOKIE_PLAYER_SALT)
        except signing.BadSignature as e:
            logger.warning(f"Player cookie signature failed for {cookie_name}: {e}")
            return False
        except (KeyError, ValueError) as e:
            logger.warning(f"Player cookie check failed for {cookie_name}: {e}")
            return False

        return Player.objects.filter(
            game__game_id=game_id, player_id=player_id
        ).exists()


class CanDeleteOwnPlayer(BasePermission):
    message = "You can only delete your own player record."

    def has_permission(self, request, view):
        if request.method != "DELETE":
            return True

        game_id = view.kwargs.get("game_id")
        player_id = view.kwargs.get("player_id")
        if not game_id or not player_id:
            logger.warning(
                f"Missing game_id or player_id: game_id={game_id}, player_id={player_id}"
            )
            return False

        if request.user.is_authenticated:
            session = get_cached_game_session(game_id)
            if session and session.game_host == request.user:
                return True

        cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"
        try:
            raw_cookie = request.COOKIES.get(cookie_name)
            if not raw_cookie:
                logger.warning(f"Player cookie not found: {cookie_name}")
                return False

            cookie_player_id = unsign_value(raw_cookie, settings.COOKIE_PLAYER_SALT)
            match = cookie_player_id == player_id
            logger.info(
                f"Cookie player_id={cookie_player_id}, URL player_id={player_id}, match={match}"
            )
            return match
        except signing.BadSignature as e:
            logger.warning(f"Player cookie signature failed for {cookie_name}: {e}")
            return False
        except (KeyError, ValueError) as e:
            logger.warning(f"Player cookie check failed for {cookie_name}: {e}")
            return False


class IsGameHost(BasePermission):
    message = "Only the game host can perform this action."

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id or not request.user.is_authenticated:
            return False

        session = get_cached_game_session(game_id)
        if session and session.game_host == request.user:
            logger.info(f"Host {request.user} authorized for game {game_id}")
            return True

        logger.warning(f"User {request.user} is not host of game {game_id}")
        return False
