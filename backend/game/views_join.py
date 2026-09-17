"""Anonymous join and lobby endpoints.

Kept out of views_rest.py on purpose: everything here runs *before* a player has
a cookie, so it is the one part of the REST surface that cannot use
HasGameAccess. Roadmap.md 1.4.
"""

import logging

from co2mmute.utils import set_game_access_cookie, set_player_cookie
from django.db import transaction
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from game.cache import get_cached_game_session
from game.models import GameSession, Player
from game.permissions import HasGameAccess
from game.serializers import JoinRequestSerializer

logger = logging.getLogger(__name__)


def _active_player_count(game: GameSession) -> int:
    """Seats taken: PlayerQuerySet.playing(), the rule the rounds use too.
    The host's own row is not a seat."""
    return Player.objects.filter(game=game).playing().count()  # type:ignore


def _joinable(game: GameSession) -> tuple[bool, str | None]:
    """Whether a new player may still take a seat, and why not if not."""
    if game.ended_at is not None:
        return False, "ended"
    if game.started_at is not None or game.is_active:
        return False, "started"
    if _active_player_count(game) >= game.max_players:
        return False, "full"
    return True, None


class SessionLookupView(APIView):
    """GET /api/game/lookup/<game_id>/ — the pre-join question.

    Deliberately readable without any cookie: this is what the join screen calls
    after a QR scan, before the player has one. It must therefore leak nothing.
    No host identity, no player names, no password — only whether one is needed.
    """

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request, game_id):
        game = get_cached_game_session(game_id)
        if not game:
            return Response(
                {"detail": "No session found with that ID."},
                status=status.HTTP_404_NOT_FOUND,
            )

        joinable, reason = _joinable(game)
        return Response(
            {
                "game_id": game.game_id,
                "game_name": game.game_name,
                "requires_password": bool(game.game_password),
                "joinable": joinable,
                "reason": reason,
                "player_count": _active_player_count(game),
                "max_players": game.max_players,
            },
            status=status.HTTP_200_OK,
        )


class JoinSessionAPIView(APIView):
    """POST /api/game/join/<game_id>/ — one call replaces two form views.

    The template flow is two steps (JoinSessionView, then PlayerCreateView, with
    request.session["joined_game_ids"] carrying permission between them). The SPA
    does not need that hop: name and password arrive together, so the player row
    and both cookies are created in one request and the session-key handshake
    disappears.

    authentication_classes is empty on purpose. DRF's SessionAuthentication
    enforces CSRF only for an authenticated user, and APIView is csrf_exempt, so
    leaving it on would mean an anonymous join needs no token but a logged-in
    host's join does — one endpoint with two rules. Nobody joins their own game
    as host (GameSessionCreateView already makes the host's Player row), so drop
    authentication entirely and keep one rule.
    """

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request, game_id):
        serializer = JoinRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]  # type: ignore
        password = serializer.validated_data.get("password", "")  # type: ignore

        # Bypass the cache here. get_cached_game_session can hand back a stale
        # copy, and this is the one read where a stale started_at or an outdated
        # row version would let someone into a running game.
        try:
            game = GameSession.objects.get(game_id=game_id.upper())
        except GameSession.DoesNotExist:
            return Response(
                {"detail": "No session found with that ID."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Password before state: a wrong password must not be able to tell you
        # whether the game is full or already running.
        if game.game_password and password != game.game_password:
            return Response(
                {"detail": "Incorrect password."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            # Lock the session row for the capacity check. Without it two players
            # POSTing at once both read max_players - 1 and both get a seat.
            game = GameSession.objects.select_for_update().get(pk=game.pk)

            joinable, reason = _joinable(game)
            if not joinable:
                return Response(
                    {"detail": "Cannot join this session.", "reason": reason},
                    status=status.HTTP_409_CONFLICT,
                )

            player = Player.objects.create(game=game, name=name)

            player.refresh_from_db()

        logger.info(f"Player {player.player_id} joined game {game.game_id} via REST")

        response = Response(
            {
                "game_id": game.game_id,
                "game_name": game.game_name,
                "player_id": player.player_id,
                "name": player.name,
                "agent_assignments": player.agent_assignments,
            },
            status=status.HTTP_201_CREATED,
        )
        response = set_game_access_cookie(request, response, game.game_id)
        response = set_player_cookie(
            request, response, game.game_id, str(player.player_id)
        )
        return response


class LobbyStateView(APIView):
    """GET /api/game/<game_id>/lobby/ — everything the lobby screen renders.

    Requires the game cookie (HasGameAccess), which the join call above just set.
    Player names are in the response because the lobby roster is the whole point
    of the screen and the template already shows exactly this; nothing else
    identifying is added.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess,)

    def get(self, request, game_id):
        game = get_cached_game_session(game_id)
        if not game:
            return Response(
                {"detail": "No session found with that ID."},
                status=status.HTTP_404_NOT_FOUND,
            )

        players = Player.objects.filter(game=game, left_at__isnull=True).order_by(
            "joined_at"
        )
        host_pks = set(
            Player.objects.filter(game=game).host_rows().values_list("pk", flat=True)  # type: ignore
        )
        joinable, reason = _joinable(game)

        return Response(
            {
                "game_id": game.game_id,
                "game_name": game.game_name,
                "max_players": game.max_players,
                "agent_per_player": game.agent_per_player,
                "max_rounds": game.max_rounds,
                "max_co2_level_kg": game.max_CO2_level,
                "chat_enabled": game.chat_enabled,
                "is_active": game.is_active,
                "started_at": game.started_at.isoformat() if game.started_at else None,
                "ended_at": game.ended_at.isoformat() if game.ended_at else None,
                "paused_at": game.paused_at.isoformat() if game.paused_at else None,
                "joinable": joinable,
                "reason": reason,
                "players": [
                    {
                        "player_id": p.player_id,
                        "name": p.name,
                        "is_host": p.pk in host_pks,
                        "controlled_by_host": p.controlled_by_host,
                        "is_muted": p.is_muted,
                    }
                    for p in players
                ],
            },
            status=status.HTTP_200_OK,
        )
