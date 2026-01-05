import asyncio
import logging
import threading

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import transaction

from rest_framework.mixins import ListModelMixin
from rest_framework.generics import GenericAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from game.models import Player, GameSession, GameRound
from game.serializers import PlayerSerializer, GameSessionSerializer
from game.cache import get_cached_game_session, invalidate_game_session
from game.permissions import HasGameAccess, IsPlayerInGame, CanDeleteOwnPlayer
from game.mixins import GameScopedQuerysetMixin


logger = logging.getLogger(__name__)


class PlayerDetailView(GameScopedQuerysetMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = PlayerSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess, CanDeleteOwnPlayer)
    lookup_field = "player_id"

    def destroy(self, request, *args, **kwargs):
        """Override destroy to clear cookies and broadcast update when player is deleted."""
        game_id = self.kwargs.get("game_id")

        # Get the player before deleting it
        instance = self.get_object()
        player_id = instance.player_id
        instance.delete()

        # Invalidate the cached game session since player list has changed
        if game_id:
            invalidate_game_session(game_id)

        # Remove from lobby cache and broadcast update in a background thread
        if game_id and player_id:
            thread = threading.Thread(
                target=self._cleanup_lobby_cache, args=(game_id, player_id), daemon=True
            )
            thread.start()

        # Create a success response with redirect URL
        response = Response({"redirect_url": "/"}, status=status.HTTP_204_NO_CONTENT)

        # Clear the player and game access cookies
        if game_id:
            player_cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"
            game_cookie_name = f"{settings.COOKIE_GAME_PREFIX}{game_id}"

            response.delete_cookie(player_cookie_name, path="/")
            response.delete_cookie(game_cookie_name, path="/")

        return response

    @staticmethod
    def _cleanup_lobby_cache(game_id, player_id):
        """Remove player from lobby cache and broadcast update (runs in background thread)."""
        logger.info(f"Cleanup thread started for {player_id} in {game_id}")
        try:
            from .consumers import LobbyConsumer

            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                logger.info(
                    f"Cleanup: Removing {player_id} from Redis cache for {game_id}"
                )
                loop.run_until_complete(
                    LobbyConsumer.remove_player_from_lobby_cache(game_id, player_id)
                )

                logger.info(f"Cleanup: Broadcasting updated roster for {game_id}")
                loop.run_until_complete(LobbyConsumer.broadcast_updated_roster(game_id))
                logger.info(f"Cleanup: Broadcast complete for {game_id}")
            finally:
                loop.close()
        except Exception as e:
            logger.warning(f"Failed to cleanup lobby cache: {e}", exc_info=True)


class PlayerListView(GameScopedQuerysetMixin, ListModelMixin, GenericAPIView):
    serializer_class = PlayerSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess,)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class MuteUnmutePlayerView(GameScopedQuerysetMixin, GenericAPIView):
    serializer_class = PlayerSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess, IsAuthenticated)

    def post(self, request, *args, **kwargs):
        player_id = self.kwargs.get("player_id")
        try:
            player = self.get_queryset().get(player_id=player_id)
        except Player.DoesNotExist:
            return Response(
                {"detail": "Player not found."}, status=status.HTTP_404_NOT_FOUND
            )

        player.is_muted = not player.is_muted
        player.save()

        serializer = self.get_serializer(player)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GameSessionDetailView(GameScopedQuerysetMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = GameSessionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess, IsAuthenticated)
    lookup_field = "game_id"

    def get_queryset(self):
        game_id = self.kwargs.get("game_id")
        if not game_id:
            raise ValidationError("game_id is required")
        return GameSession.objects.filter(game_id=game_id)

    def update(self, request, *args, **kwargs):
        """Override update to enforce game state rules for editing."""

        game = self.get_object()

        # Only host can update game settings
        if game.game_host != request.user:
            return Response(
                {"error": "Only the host can modify game settings"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check game state
        is_stopped = game.ended_at is not None
        is_currently_active = game.is_active

        # Check if this is a start game request (is_active: true when not started)
        is_start_game = (
            "is_active" in request.data and request.data["is_active"] is True
        )

        # Check if this is a stop game request (is_active: false when active)
        is_stop_game = (
            "is_active" in request.data
            and request.data["is_active"] is False
            and is_currently_active
        )

        # If game has ended, only allow chat_enabled and game_password changes
        if is_stopped:
            allowed_fields = {"chat_enabled", "game_password"}
            provided_fields = set(request.data.keys())
            forbidden_fields = provided_fields - allowed_fields

            if forbidden_fields:
                return Response(
                    {"error": "Game has ended. No further changes allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return super().update(request, *args, **kwargs)

        # If game is currently active (but not stopped), only chat_enabled, game_password, and is_active can be changed
        if is_currently_active:
            allowed_fields = {"chat_enabled", "game_password", "is_active"}
            provided_fields = set(request.data.keys())
            forbidden_fields = provided_fields - allowed_fields

            if forbidden_fields:
                return Response(
                    {
                        "error": f"Cannot modify {', '.join(forbidden_fields)} while game is active"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Handle stop game request
            if is_stop_game:
                with transaction.atomic():
                    game.is_active = False
                    game.ended_at = timezone.now()
                    game.save()

                serializer = self.get_serializer(game)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # For other allowed changes on active game, proceed normally
            return super().update(request, *args, **kwargs)

        # Game not started yet - check if starting game
        if is_start_game:
            # Starting the game - create first round and broadcast
            with transaction.atomic():
                game.is_active = True
                game.started_at = timezone.now()
                game.save()

                print(
                    f"DEBUG: After save - is_active={game.is_active}, started_at={game.started_at}"
                )

                # Refresh from database to verify it was saved
                game.refresh_from_db()
                print(f"DEBUG: After refresh from DB - is_active={game.is_active}")

                # Create first round (or get if it already exists)
                GameRound.objects.get_or_create(
                    game=game, round_number=1, defaults={"status": "active"}
                )

            # Broadcast game state to all players in background
            thread = threading.Thread(
                target=self._broadcast_game_state, args=(game.game_id,), daemon=True
            )
            thread.start()

            serializer = self.get_serializer(game)
            print(f"DEBUG: Serializer data: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # Not starting game, game not started - allow setting changes before game starts
            return super().update(request, *args, **kwargs)

    @staticmethod
    def _broadcast_game_state(game_id: str):
        """Broadcast game state to all connected players."""
        from .consumers import GameStateConsumer

        asyncio.run(GameStateConsumer.broadcast_game_state(game_id))


class GetYourOwnGame(GameScopedQuerysetMixin, GenericAPIView):
    serializer_class = GameSessionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess, IsPlayerInGame)

    def get(self, request, *args, **kwargs):
        player_id = self.kwargs.get("player_id")
        player = get_object_or_404(Player, player_id=player_id)
        game = get_cached_game_session(player.game.game_id)
        if not game:
            return Response(
                {"detail": "Game session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(game)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GameSessionListView(GameScopedQuerysetMixin, ListModelMixin, GenericAPIView):
    serializer_class = GameSessionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess,)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class PlayerMoveView(GameScopedQuerysetMixin, GenericAPIView):
    """Submit a player move (transportation choice) for the current round - players only."""

    serializer_class = PlayerSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess, IsPlayerInGame)

    def post(self, request, game_id, player_id):
        try:
            from .models import GameSession, Player, GameRound, PlayerMove

            # Get and validate game
            game = GameSession.objects.get(game_id=game_id)
            if not game.is_active:
                return Response(
                    {"error": "Game is not active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get and validate player
            player = Player.objects.get(player_id=player_id, game=game)

            # Get current active round
            current_round = (
                GameRound.objects.filter(game=game).order_by("-round_number").first()
            )
            if not current_round or current_round.status != "active":
                return Response(
                    {"error": "No active round"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate and get transportation action
            action = request.data.get("action")
            valid_actions = ["car", "public", "bike", "walk"]
            if action not in valid_actions:
                return Response(
                    {"error": f"Invalid action. Must be one of {valid_actions}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create or update player move for this round
            move, created = PlayerMove.objects.update_or_create(
                game_round=current_round,
                player=player,
                defaults={"action": action, "payload": {}},
            )

            # Check if all players have made a move (trigger round completion)
            thread = threading.Thread(
                target=self._check_round_completion,
                args=(game_id,),
                daemon=True,
            )
            thread.start()

            serializer = self.get_serializer(player)
            return Response(
                {
                    "success": True,
                    "message": "Move recorded",
                    "player": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except GameSession.DoesNotExist:
            return Response(
                {"error": "Game not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Player.DoesNotExist:
            return Response(
                {"error": "Player not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @staticmethod
    def _check_round_completion(game_id: str):
        """Check if all players have made moves and progress the game if so."""
        from .models import GameSession, GameRound, PlayerMove
        from .signals import round_completed

        try:
            game = GameSession.objects.get(game_id=game_id)
            current_round = (
                GameRound.objects.filter(game=game).order_by("-round_number").first()
            )

            if not current_round or current_round.status != "active":
                return

            # Get all non-host players
            active_players = Player.objects.filter(
                game=game,
                left_at__isnull=True,
                controlled_by_host=False,
            ).count()

            # Get players who have made moves this round
            moves_count = PlayerMove.objects.filter(
                game_round=current_round,
                player__controlled_by_host=False,
            ).count()

            # If all players have moved, emit signal to progress round
            if active_players > 0 and moves_count >= active_players:
                logger.info(f"All players moved in round {current_round.round_number}")
                round_completed.send(sender=GameRound, game_id=game_id)

        except GameSession.DoesNotExist:
            logger.error(f"Game {game_id} not found")
        except Exception as e:
            logger.error(f"Error checking round completion: {e}")
