from rest_framework import serializers

import game.models as gm


class GameSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.GameSession
        fields = (
            "id",
            "game_host",
            "game_name",
            "game_id",
            "game_password",
            "game_qr_code",
            "game_map",
            "map_updates",
            "active_map_version",
            "max_players",
            "agent_per_player",
            "max_rounds",
            "max_CO2_level",
            "chat_enabled",
            "is_active",
            "created_at",
            "updated_at",
            "started_at",
            "ended_at",
        )
        read_only_fields = (
            "id",
            "game_id",
            "game_qr_code",
            "created_at",
            "updated_at",
            "ended_at",
        )

    def validate(self, attrs):
        max_players = attrs.get(
            "max_players", getattr(self.instance, "max_players", None)
        )
        agent_per_player = attrs.get(
            "agent_per_player", getattr(self.instance, "agent_per_player", None)
        )
        max_rounds = attrs.get("max_rounds", getattr(self.instance, "max_rounds", None))
        max_co2_level = attrs.get(
            "max_CO2_level", getattr(self.instance, "max_CO2_level", None)
        )

        errors = {}

        if max_players is not None:
            if max_players < 1:
                errors["max_players"] = "max_players must be at least 1."
            if agent_per_player is not None and agent_per_player > max_players:
                errors["agent_per_player"] = (
                    "agent_per_player cannot exceed max_players."
                )

        if agent_per_player is not None and agent_per_player < 1:
            errors["agent_per_player"] = "agent_per_player must be at least 1."

        if max_rounds is not None and max_rounds < 1:
            errors["max_rounds"] = "max_rounds must be at least 1."

        if max_co2_level is not None and max_co2_level < 1:
            errors["max_CO2_level"] = "max_CO2_level must be at least 1."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.Player
        fields = (
            "id",
            "name",
            "player_id",
            "user",
            "game",
            "joined_at",
            "is_muted",
            "controlled_by_host",
            "agent_assignments",
        )
        read_only_fields = (
            "id",
            "player_id",
            "joined_at",
            "is_muted",
            "controlled_by_host",
            "agent_assignments",
        )


class GameRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.GameRound
        fields = (
            "id",
            "game",
            "round_number",
            "status",
            "started_at",
            "updated_at",
        )
        read_only_fields = ("id", "round_number", "started_at", "updated_at")

    def validate(self, attrs):
        game = attrs.get("game") or getattr(self.instance, "game", None)
        round_number = attrs.get("round_number")

        if round_number is not None and round_number < 1:
            raise serializers.ValidationError(
                {"round_number": "round_number must be at least 1."}
            )

        if (
            game
            and round_number is not None
            and gm.GameRound.objects.exclude(pk=getattr(self.instance, "pk", None))
            .filter(game=game, round_number=round_number)
            .exists()
        ):
            raise serializers.ValidationError(
                {"round_number": "This game already has a round with that number."}
            )

        return attrs


class PlayerMoveSerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.PlayerMove
        fields = (
            "id",
            "session_round",
            "player",
            "action",
            "payload",
            "started_at",
            "updated_at",
        )
        read_only_fields = ("id", "started_at", "updated_at")

    def validate(self, attrs):
        session_round = attrs.get("session_round") or getattr(
            self.instance, "session_round", None
        )
        player = attrs.get("player") or getattr(self.instance, "player", None)

        if session_round is None:
            raise serializers.ValidationError(
                {"session_round": "session_round is required."}
            )
        if player is None:
            raise serializers.ValidationError({"player": "player is required."})

        if player.game.game_id != session_round.game.game_id:
            raise serializers.ValidationError(
                {"player": "Player must belong to the same game as the round."}
            )

        return attrs


class CarMobilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.CarMobility
        fields = (
            "id",
            "session_round",
            "base_emissions_g_per_km",
            "base_cost_per_km",
        )
        read_only_fields = ("id",)


class TrainMobilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.TrainMobility
        fields = (
            "id",
            "session_round",
            "base_emissions_g_per_km",
            "base_cost_per_km",
        )
        read_only_fields = ("id",)


class BusMobilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.BusMobility
        fields = (
            "id",
            "session_round",
            "base_emissions_g_per_km",
            "base_cost_per_km",
        )
        read_only_fields = ("id",)


class BikeMobilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.BikeMobility
        fields = (
            "id",
            "session_round",
            "emissions_g_per_km",
            "cost_per_km",
        )
        read_only_fields = ("id",)


class WalkingMobilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = gm.WalkingMobility
        fields = (
            "id",
            "session_round",
        )
        read_only_fields = ("id",)


# =============================================================================
# Route Serializers (for traffic simulation)
# =============================================================================


class RouteSegmentSerializer(serializers.ModelSerializer):
    """Serializer for individual route segments."""

    class Meta:
        model = gm.RouteSegment
        fields = (
            "id",
            "order",
            "edge",
            "mode",
            "pt_line_id",
        )
        read_only_fields = ("id",)


class AgentRouteSerializer(serializers.ModelSerializer):
    """Serializer for agent routes with nested segments."""

    segments = RouteSegmentSerializer(many=True, read_only=True)

    class Meta:
        model = gm.AgentRoute
        fields = (
            "id",
            "agent_id",
            "transport_mode",
            "optimization",
            "total_distance_m",
            "estimated_time_min",
            "segments",
        )
        read_only_fields = ("id",)


# Input serializers for route submission


class RouteSegmentInputSerializer(serializers.Serializer):
    """Input serializer for route segment data from frontend."""

    edge_id = serializers.IntegerField()
    start_node = serializers.IntegerField()
    end_node = serializers.IntegerField()
    mode = serializers.ChoiceField(choices=gm.RouteSegment.SegmentMode.choices)
    pt_line_id = serializers.IntegerField(required=False, allow_null=True)


class RouteInputSerializer(serializers.Serializer):
    """Input serializer for route data from frontend."""

    total_distance_m = serializers.FloatField()
    estimated_time_min = serializers.FloatField()
    segments = RouteSegmentInputSerializer(many=True)


class AgentRouteInputSerializer(serializers.Serializer):
    """Input serializer for per-agent route submission."""

    id = serializers.IntegerField()  # agent_id
    transport_mode = serializers.ChoiceField(choices=gm.AgentRoute.TransportMode.choices)
    optimization = serializers.ChoiceField(
        choices=gm.AgentRoute.Optimization.choices, required=False, allow_null=True
    )
    route = RouteInputSerializer()


class PlayerMoveWithRoutesInputSerializer(serializers.Serializer):
    """Input serializer for player move with route data."""

    agents = AgentRouteInputSerializer(many=True)

    def validate_agents(self, agents):
        """Validate that agent IDs are unique."""
        agent_ids = [agent["id"] for agent in agents]
        if len(agent_ids) != len(set(agent_ids)):
            raise serializers.ValidationError("Agent IDs must be unique.")
        return agents


# Result serializers


class AgentSimulationResultSerializer(serializers.ModelSerializer):
    """Serializer for per-agent simulation results."""

    agent_id = serializers.IntegerField(source="agent_route.agent_id", read_only=True)
    transport_mode = serializers.CharField(
        source="agent_route.transport_mode", read_only=True
    )

    class Meta:
        model = gm.AgentSimulationResult
        fields = (
            "agent_id",
            "transport_mode",
            "mean_trip_time_min",
            "mean_return_time_min",
            "mean_cost_eur",
            "total_co2_g",
            "congestion_delay_min",
            "wait_time_min",
        )


class SimulationResultSerializer(serializers.ModelSerializer):
    """Serializer for simulation results."""

    agent_results = AgentSimulationResultSerializer(many=True, read_only=True)

    class Meta:
        model = gm.SimulationResult
        fields = (
            "id",
            "status",
            "started_at",
            "completed_at",
            "total_co2_g",
            "total_cost_eur",
            "agent_results",
        )
        read_only_fields = ("id", "started_at", "completed_at")
