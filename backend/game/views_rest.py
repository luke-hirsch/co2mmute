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
from game.models import AgentRoute, GameRound, GameSession, Player, PlayerMove, RouteSegment
from game.permissions import CanDeleteOwnPlayer, HasGameAccess, IsPlayerInGame
from game.serializers import (
    GameSessionSerializer,
    PlayerSerializer,
    PlayerMoveWithRoutesInputSerializer,
)
from co2mmute.utils import send_player_status_update
from game.signals import round_completed
from maps.models import Edge

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
        # Include player's agent assignments in response
        response_data = serializer.data
        response_data["agent_assignments"] = player.agent_assignments
        return Response(response_data, status=status.HTTP_200_OK)


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

            # Check if this is a route submission (new format) or legacy format
            has_routes = payload and "agents" in payload and any(
                "route" in agent for agent in payload.get("agents", [])
            )

            if has_routes:
                # New format: validate with route serializer
                route_serializer = PlayerMoveWithRoutesInputSerializer(data=payload)
                if not route_serializer.is_valid():
                    return Response(
                        {"error": "Invalid route data", "details": route_serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Validate routes: check edge connectivity and permissions
                validation_errors = self._validate_routes(
                    route_serializer.validated_data["agents"],
                    player,
                    game,
                )
                if validation_errors:
                    return Response(
                        {"error": validation_errors},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Use "route_submission" as action for new format
                action = "route_submission"
            else:
                # Legacy format: simple action validation
                if action not in valid_actions:
                    return Response(
                        {"error": f"Invalid action. Must be one of {valid_actions}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Validate legacy payload if it contains agent choices
                if payload and "agents" in payload:
                    for agent_choice in payload["agents"]:
                        if agent_choice.get("action") not in valid_actions:
                            return Response(
                                {"error": f"Invalid agent action. Must be one of {valid_actions}"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

            with transaction.atomic():
                move, created = PlayerMove.objects.update_or_create(
                    session_round=current_round,
                    player=player,
                    defaults={"action": action, "payload": payload or {}},
                )

                # If routes were submitted, store them in the database
                if has_routes:
                    # Delete any existing routes for this move (in case of update)
                    AgentRoute.objects.filter(player_move=move).delete()

                    self._store_routes(move, route_serializer.validated_data["agents"])

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

    def _validate_routes(self, agents_data, player, game):
        """
        Validate submitted routes for connectivity and transport permissions.
        Returns list of error message strings if invalid, None if valid.
        """
        errors = []

        # Get player's agent assignments to validate agent IDs and nodes
        agent_assignments = player.agent_assignments or {}
        home_node = agent_assignments.get("home_node")
        assigned_agents = {a["id"]: a for a in agent_assignments.get("agents", [])}

        if not home_node or not assigned_agents:
            return ["Player has no agent assignments"]

        for agent_data in agents_data:
            agent_id = agent_data["id"]
            if agent_id not in assigned_agents:
                errors.append(f"Invalid agent ID: {agent_id}")
                continue

            route = agent_data["route"]
            segments = route["segments"]

            if not segments:
                errors.append(f"Agent {agent_id} route has no segments")
                continue

            # Validate first segment starts from home
            first_segment = segments[0]
            if first_segment["start_node"] != home_node:
                errors.append(f"Agent {agent_id} route must start from home node {home_node}")

            # Validate last segment ends at destination
            destination = assigned_agents[agent_id]["destination_node"]
            last_segment = segments[-1]
            if last_segment["end_node"] != destination:
                errors.append(f"Agent {agent_id} route must end at destination {destination}")

            # Validate segment connectivity and edge existence
            for i, segment in enumerate(segments):
                try:
                    edge = Edge.objects.get(id=segment["edge_id"])
                except Edge.DoesNotExist:
                    errors.append(f"Agent {agent_id}: edge {segment['edge_id']} does not exist")
                    continue

                # Validate edge matches start/end nodes
                if edge.start_node_id != segment["start_node"] or edge.end_node_id != segment["end_node"]:
                    errors.append(f"Agent {agent_id}: edge {segment['edge_id']} does not connect nodes {segment['start_node']} → {segment['end_node']}")

                # Validate transport mode is allowed on this edge
                mode = segment["mode"]
                if mode == "walk" and not edge.walking:
                    errors.append(f"Agent {agent_id}: walking not allowed on edge {segment['edge_id']}")
                if mode == "bike" and not edge.biking:
                    errors.append(f"Agent {agent_id}: biking not allowed on edge {segment['edge_id']}")
                if mode == "car" and not hasattr(edge, "streetedge_set"):
                    if not edge.streetedge_set.exists():
                        errors.append(f"Agent {agent_id}: cars not allowed on edge {segment['edge_id']}")
                if mode in ("bus", "train"):
                    pass

                # Validate connectivity with previous segment
                if i > 0:
                    prev_segment = segments[i - 1]
                    if prev_segment["end_node"] != segment["start_node"]:
                        errors.append(f"Agent {agent_id}: route discontinuity at segment {i}: {prev_segment['end_node']} != {segment['start_node']}")

        return errors if errors else None

    def _store_routes(self, move, agents_data):
        """Store agent routes and segments in the database."""
        for agent_data in agents_data:
            route_data = agent_data["route"]

            agent_route = AgentRoute.objects.create(
                player_move=move,
                agent_id=agent_data["id"],
                transport_mode=agent_data["transport_mode"],
                optimization=agent_data.get("optimization"),
                total_distance_m=route_data["total_distance_m"],
                estimated_time_min=route_data["estimated_time_min"],
            )

            for i, segment_data in enumerate(route_data["segments"]):
                RouteSegment.objects.create(
                    agent_route=agent_route,
                    order=i,
                    edge_id=segment_data["edge_id"],
                    mode=segment_data["mode"],
                    pt_line_id=segment_data.get("pt_line_id"),
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
