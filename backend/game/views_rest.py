import logging
import threading

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Max
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
from game.models import AgentRoute, AgentSimulationResult, EdgeTrafficSnapshot, GameRound, GameSession, Player, PlayerMove, RouteSegment, SimulationResult
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

    def update(self, request, *args, **kwargs):
        game_id = self.kwargs.get("game_id")
        session = get_cached_game_session(game_id)
        if not session or not request.user.is_authenticated or session.game_host != request.user:
            return Response(
                {"error": "Only the host can edit player details"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

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

                # Set initial active map version to base version
                if game.game_map:
                    from maps.models import MapVersion

                    base = MapVersion.objects.filter(
                        game_map=game.game_map, base_version=True
                    ).first()
                    if base:
                        game.active_map_version = base
                        game.save(update_fields=["active_map_version"])

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
                mode = segment["mode"]
                edge_id = segment["edge_id"]

                # edge_id = -1 signals a valid walk segment with no dedicated edge
                # (e.g. start/end node sits directly on a PT stop with no separate
                # walk edge, or a zero-distance transfer at the same node).
                if edge_id == -1:
                    if mode != "walk":
                        errors.append(
                            f"Agent {agent_id}: edge -1 is only valid for walk segments, got mode '{mode}'"
                        )
                    continue

                try:
                    edge = Edge.objects.get(id=edge_id)
                except Edge.DoesNotExist:
                    errors.append(f"Agent {agent_id}: edge {edge_id} does not exist")
                    continue

                # Validate edge matches start/end nodes.
                # Skip connectivity check for bus/train: edge IDs on PT lines are
                # used for simulation properties (bus lane, speed) rather than
                # strict routing, and may be stored in either direction or differ
                # slightly from the traversed stop pair.
                if mode not in ("bus", "train"):
                    forward_ok = (edge.start_node_id == segment["start_node"] and edge.end_node_id == segment["end_node"])
                    reverse_ok = (edge.start_node_id == segment["end_node"] and edge.end_node_id == segment["start_node"])
                    if not forward_ok and not reverse_ok:
                        errors.append(f"Agent {agent_id}: edge {edge_id} does not connect nodes {segment['start_node']} → {segment['end_node']}")

                # Validate transport mode is allowed on this edge
                if mode == "walk" and not edge.walking:
                    errors.append(f"Agent {agent_id}: walking not allowed on edge {edge_id}")
                if mode == "bike" and not edge.biking:
                    errors.append(f"Agent {agent_id}: biking not allowed on edge {edge_id}")
                if mode == "car" and not hasattr(edge, "streetedge_set"):
                    if not edge.streetedge_set.exists():
                        errors.append(f"Agent {agent_id}: cars not allowed on edge {edge_id}")
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


class RoundTrafficHeatmapView(GenericAPIView):
    """Return aggregated traffic congestion data per edge for a completed round."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess,)

    def get(self, request, game_id, round_number):
        try:
            game = GameSession.objects.get(game_id=game_id)
        except GameSession.DoesNotExist:
            return Response({"error": "Game not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            game_round = GameRound.objects.get(game=game, round_number=round_number)
        except GameRound.DoesNotExist:
            return Response({"error": "Round not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            sim_result = game_round.simulation
        except SimulationResult.DoesNotExist:
            return Response(
                {"error": "No simulation for this round"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Aggregate traffic snapshots per edge
        edge_traffic = (
            EdgeTrafficSnapshot.objects.filter(simulation=sim_result)
            .values("edge_id")
            .annotate(
                avg_vehicle_count=Avg("vehicle_count"),
                max_vehicle_count=Max("vehicle_count"),
                avg_speed_kmh=Avg("speed_kmh"),
            )
        )

        # Build lookup for free-flow speeds from StreetEdge
        from maps.models import StreetEdge

        edge_ids = [et["edge_id"] for et in edge_traffic]
        default_speed = game.game_map.default_car_speed_kmh if game.game_map else 50

        street_speeds = {}
        for se in StreetEdge.objects.filter(edge_id__in=edge_ids).select_related("edge"):
            street_speeds[se.edge_id] = se.speed_limit

        heatmap_data = []
        for et in edge_traffic:
            eid = et["edge_id"]
            free_flow = street_speeds.get(eid, default_speed)
            avg_speed = et["avg_speed_kmh"]
            congestion_ratio = (
                max(0.0, min(1.0, 1.0 - (avg_speed / free_flow)))
                if free_flow > 0
                else 0.0
            )

            heatmap_data.append({
                "edge_id": eid,
                "avg_vehicle_count": round(et["avg_vehicle_count"], 1),
                "max_vehicle_count": et["max_vehicle_count"],
                "avg_speed_kmh": round(avg_speed, 1),
                "free_flow_speed_kmh": free_flow,
                "congestion_ratio": round(congestion_ratio, 3),
            })

        return Response({
            "round_number": round_number,
            "edge_count": len(heatmap_data),
            "edges": heatmap_data,
        })


class GameSummaryView(GenericAPIView):
    """Return end-of-game summary with per-player stats across all rounds."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (HasGameAccess,)

    def get(self, request, game_id):
        try:
            game = GameSession.objects.get(game_id=game_id)
        except GameSession.DoesNotExist:
            return Response({"error": "Game not found"}, status=status.HTTP_404_NOT_FOUND)

        players = Player.objects.filter(
            game=game, left_at__isnull=True, controlled_by_host=False
        )
        completed_rounds = GameRound.objects.filter(
            game=game, status=GameRound.Status.COMPLETED
        ).order_by("round_number")

        total_co2_g = sum(r.total_emissions_g for r in completed_rounds)

        # Build per-player, per-round stats from AgentSimulationResult
        players_data = []
        for player in players:
            moves = PlayerMove.objects.filter(
                player=player, session_round__in=completed_rounds
            ).select_related("session_round")

            player_total_co2 = 0.0
            player_total_cost = 0.0
            player_total_time = 0.0
            modes_used = set()
            rounds_data = []

            for game_round in completed_rounds:
                round_move = moves.filter(session_round=game_round).first()
                round_co2 = 0.0
                round_cost = 0.0
                round_time = 0.0

                if round_move:
                    agent_results = AgentSimulationResult.objects.filter(
                        agent_route__player_move=round_move
                    ).select_related("agent_route")

                    if agent_results.exists():
                        for result in agent_results:
                            round_co2 += result.total_co2_g
                            round_cost += result.mean_cost_eur
                            round_time += result.mean_trip_time_min
                            modes_used.add(result.agent_route.transport_mode)
                    else:
                        # Fallback
                        agent_routes = AgentRoute.objects.filter(player_move=round_move)
                        fallback_emissions = {
                            "car": 166.8, "public": 60.0, "bike": 18.0, "walk": 0.0,
                        }
                        for route in agent_routes:
                            dist_km = route.total_distance_m / 1000
                            round_co2 += fallback_emissions.get(route.transport_mode, 0) * dist_km * game.people_per_agent
                            round_time += route.estimated_time_min
                            modes_used.add(route.transport_mode)

                rounds_data.append({
                    "round_number": game_round.round_number,
                    "co2_kg": round(round_co2 / 1000, 2),
                    "cost_eur": round(round_cost, 2),
                    "time_min": round(round_time, 1),
                })

                player_total_co2 += round_co2
                player_total_cost += round_cost
                player_total_time += round_time

            players_data.append({
                "player_id": player.player_id,
                "name": player.name,
                "total_co2_kg": round(player_total_co2 / 1000, 2),
                "total_cost_eur": round(player_total_cost, 2),
                "total_time_min": round(player_total_time, 1),
                "modes_used": sorted(modes_used),
                "rounds": rounds_data,
            })

        # Determine end reason
        end_reason = None
        if game.ended_at:
            co2_limit_reached = total_co2_g >= (game.max_CO2_level * 1000)
            end_reason = "co2_limit" if co2_limit_reached else "max_rounds"

        return Response({
            "game_id": game.game_id,
            "game_name": game.game_name,
            "end_reason": end_reason,
            "rounds_played": completed_rounds.count(),
            "max_rounds": game.max_rounds,
            "total_co2_kg": round(total_co2_g / 1000, 2),
            "max_co2_kg": game.max_CO2_level,
            "players": players_data,
        })
