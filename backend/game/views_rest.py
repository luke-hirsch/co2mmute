import logging
import threading

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from game.cache import get_cached_game_session
from game.mixins import GameScopedQuerysetMixin
from game.models import GameRound, GameSession, Player, PlayerMove
from game.permissions import CanDeleteOwnPlayer, HasGameAccess, IsPlayerInGame
from game.serializers import GameSessionSerializer, PlayerSerializer
from co2mmute.utils import send_player_status_update
from game.signals import round_completed

logger = logging.getLogger(__name__)


class PlayerDetailView(GameScopedQuerysetMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = PlayerSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess, CanDeleteOwnPlayer)
    lookup_field = "player_id"

    def destroy(self, request, *args, **kwargs):
        game_id = self.kwargs.get("game_id")
        is_kicked = request.query_params.get("kicked", "").lower() == "true"

        instance = self.get_object()
        # Set a temporary attribute so the signal knows if player was kicked
        instance._was_kicked = is_kicked
        instance.delete()

        response = Response({"redirect_url": "/"}, status=status.HTTP_204_NO_CONTENT)

        if game_id:
            player_cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"
            game_cookie_name = f"{settings.COOKIE_GAME_PREFIX}{game_id}"

            response.delete_cookie(player_cookie_name, path="/")
            response.delete_cookie(game_cookie_name, path="/")

        return response


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
        game = self.get_object()

        if game.game_host != request.user:
            return Response(
                {"error": "Only the host can modify game settings"},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_stopped = game.ended_at is not None
        is_currently_active = game.is_active

        is_start_game = (
            "is_active" in request.data and request.data["is_active"] is True
        )

        is_stop_game = (
            "is_active" in request.data
            and request.data["is_active"] is False
            and is_currently_active
        )

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

            if is_stop_game:
                with transaction.atomic():
                    game.is_active = False
                    game.ended_at = timezone.now()
                    game.save()

                serializer = self.get_serializer(game)
                return Response(serializer.data, status=status.HTTP_200_OK)

            return super().update(request, *args, **kwargs)

        if is_start_game:
            with transaction.atomic():
                game.is_active = True
                game.started_at = timezone.now()
                game.save()

                game.refresh_from_db()

                GameRound.objects.get_or_create(
                    game=game,
                    round_number=1,
                    defaults={"status": "active", "started_at": timezone.now()},
                )

            # The post_save signal on GameSession will broadcast game.started
            serializer = self.get_serializer(game)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return super().update(request, *args, **kwargs)


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
    serializer_class = PlayerSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess, IsPlayerInGame)

    def post(self, request, game_id, player_id):
        try:
            from .models import GameRound, GameSession, Player, PlayerMove

            game = GameSession.objects.get(game_id=game_id)
            if not game.is_active:
                return Response(
                    {"error": "Game is not active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            player = Player.objects.get(player_id=player_id, game=game)

            current_round = (
                GameRound.objects.filter(game=game).order_by("-round_number").first()
            )
            if not current_round or current_round.status != "active":
                return Response(
                    {"error": "No active round"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            action = request.data.get("action")
            payload = request.data.get("payload", {})
            valid_actions = ["car", "public", "bike", "walk"]
            if action not in valid_actions:
                return Response(
                    {"error": f"Invalid action. Must be one of {valid_actions}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate payload if it contains agent choices
            if payload and "agents" in payload:
                for agent_choice in payload["agents"]:
                    if agent_choice.get("action") not in valid_actions:
                        return Response(
                            {"error": f"Invalid agent action. Must be one of {valid_actions}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            move, created = PlayerMove.objects.update_or_create(
                session_round=current_round,
                player=player,
                defaults={"action": action, "payload": payload or {}},
            )

            # Notify clients that this player has made their move
            send_player_status_update(game_id, player_id, "waiting")

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
        try:
            game = GameSession.objects.get(game_id=game_id)
            current_round = (
                GameRound.objects.filter(game=game).order_by("-round_number").first()
            )

            if not current_round or current_round.status != "active":
                return

            active_players = Player.objects.filter(
                game=game,
                left_at__isnull=True,
                controlled_by_host=False,
            ).count()

            moves_count = PlayerMove.objects.filter(
                session_round=current_round,
                player__controlled_by_host=False,
            ).count()

            if active_players > 0 and moves_count >= active_players:
                logger.info(f"All players moved in round {current_round.round_number}")
                round_completed.send(sender=GameRound, game_id=game_id)

        except GameSession.DoesNotExist:
            logger.error(f"Game {game_id} not found")
        except Exception as e:
            logger.error(f"Error checking round completion: {e}")
