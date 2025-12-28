from rest_framework.mixins import ListModelMixin
from rest_framework.generics import GenericAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework import status
import asyncio
import logging
import threading

from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from game.models import Player, GameSession
from game.serializers import PlayerSerializer, GameSessionSerializer
from .cache import get_cached_game_session, invalidate_game_session
from .permissions import HasGameAccess, IsPlayerInGame, CanDeleteOwnPlayer
from .mixins import GameScopedQuerysetMixin
from django.shortcuts import get_object_or_404
from django.conf import settings

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
