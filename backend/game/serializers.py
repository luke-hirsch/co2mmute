from rest_framework import serializers

import game.models as gm
from game import calibration

# Django's and DRF's own refusals for a number are English — "Ensure this value
# is less than or equal to 365." — and the create screen renders whatever comes
# back beside the field. `validate()` below words the lower bounds that mean
# something in the game; these are the column's range, `idle_end_days`'s 365
# and anything that is not a number at all. S21 met the first one by typing
# 99 999 into "Ende nach Tagen ohne Spiel".
NUMBER_ERRORS = {
    "invalid": "Hier gehört eine ganze Zahl hin.",
    "max_value": "Höchstens {max_value}.",
    "min_value": "Mindestens {min_value}.",
    "max_string_length": "Diese Zahl ist zu lang.",
}
NUMBER_FIELDS = (
    "max_players",
    "agent_per_player",
    "max_rounds",
    "max_CO2_level",
    "people_per_agent",
    "idle_end_days",
)


def _kg(value):
    """1.0 → "1,0": the German way, as the dial writes it."""
    return f"{value:.1f}".replace(".", ",")


# The dial offers a list, so every refusal says the same thing: what the list
# is. DRF's own for a decimal ("Ensure that there are no more than 1 decimal
# places.") is English and names a rule the host never sees.
KG_PER_PERSON_ERROR = (
    f"Wähle zwischen {_kg(calibration.CO2_KG_PER_PERSON_MIN)} und "
    f"{_kg(calibration.CO2_KG_PER_PERSON_MAX)} kg, in Schritten von "
    f"{_kg(calibration.CO2_KG_PER_PERSON_STEP)} kg."
)
KG_PER_PERSON_ERRORS = {
    key: KG_PER_PERSON_ERROR
    for key in (
        "invalid",
        "max_value",
        "min_value",
        "max_digits",
        "max_decimal_places",
        "max_whole_digits",
        "max_string_length",
    )
}


class GameSessionSerializer(serializers.ModelSerializer):
    """The game row, read and written by the SPA and by nothing else.

    **The messages are German because the host reads them.** They used to be
    English, which was harmless only for as long as nothing rendered them: the
    create form was a Django `ModelForm` with its own German copy, and this
    serializer answered the lobby's PATCH, whose errors the screen never
    showed. S13 put the create form in React, so these strings are now the
    sentence a host meets when they ask for a round with no seats in it.

    There is no second copy of them in `de.ts`. A rule the client can check
    before submitting — a missing name, a number below one — is checked there
    with its own wording; a rule that needs the database is checked here and
    the screen renders what comes back. Nothing is worded twice.
    """

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
            "co2_kg_per_person",
            "people_per_agent",
            "chat_enabled",
            "is_active",
            "idle_end_days",
            "created_at",
            "updated_at",
            "started_at",
            "paused_at",
            "ended_at",
        )
        # `game_host` is read-only because it is not the client's to state:
        # the create endpoint takes it off the session. Writable, a POST could
        # hand somebody else's account a game it never asked for.
        read_only_fields = (
            "id",
            "game_host",
            "game_id",
            "game_qr_code",
            "created_at",
            "updated_at",
            "paused_at",
            "ended_at",
        )
        extra_kwargs = {
            **{name: {"error_messages": NUMBER_ERRORS} for name in NUMBER_FIELDS},
            "co2_kg_per_person": {"error_messages": KG_PER_PERSON_ERRORS},
        }

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
                errors["max_players"] = "Es muss mindestens einen Platz geben."
            if agent_per_player is not None and agent_per_player > max_players:
                errors["agent_per_player"] = (
                    "Mehr Gruppen pro Person als Plätze im Spiel geht nicht."
                )

        if agent_per_player is not None and agent_per_player < 1:
            errors["agent_per_player"] = (
                "Jede Person braucht mindestens eine Gruppe."
            )

        if max_rounds is not None and max_rounds < 1:
            errors["max_rounds"] = "Es muss mindestens eine Runde gefahren werden."

        if max_co2_level is not None and max_co2_level < 1:
            errors["max_CO2_level"] = (
                "Das CO₂-Budget muss mindestens ein Kilogramm sein."
            )

        people_per_agent = attrs.get(
            "people_per_agent", getattr(self.instance, "people_per_agent", None)
        )
        if people_per_agent is not None and people_per_agent < 1:
            errors["people_per_agent"] = (
                "Eine Gruppe muss für mindestens einen Menschen stehen."
            )

        # Only what the dial offers. `max_CO2_level` is not checked against
        # it: the screen derives one from the other, and the endpoint takes
        # what it is sent, as it does for the scale.
        kg_per_person = attrs.get("co2_kg_per_person")
        if kg_per_person is not None and (
            kg_per_person not in calibration.co2_kg_per_person_choices()
        ):
            errors["co2_kg_per_person"] = KG_PER_PERSON_ERROR

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class GameSessionCreateSerializer(GameSessionSerializer):
    """`POST api/game/` — the body the create screen sends.

    One thing separates it from its parent: **a map is required.** On the model
    `game_map` is `null=True, blank=True`, which is right for a row whose map
    was deleted afterwards and wrong for a game being made now —
    `GameSession.save()` forces `is_active` back to False whenever there is no
    map, so a mapless game can never be started, never be ended, and used to
    have no way out of the host's list either. The Django form required it for
    that reason; so does this.

    It is a subclass rather than a flag on the parent because the lobby's PATCH
    goes through the parent and must be free to leave `game_map` out of a body
    that only changes `is_active`.
    """

    class Meta(GameSessionSerializer.Meta):
        extra_kwargs = {
            **GameSessionSerializer.Meta.extra_kwargs,
            "game_map": {
                "required": True,
                "allow_null": False,
                "error_messages": {
                    "required": "Wähle eine Karte aus.",
                    "null": "Wähle eine Karte aus.",
                    "does_not_exist": "Diese Karte gibt es nicht.",
                },
            },
            "game_name": {
                "error_messages": {
                    "required": "Gib dem Spiel einen Namen.",
                    "blank": "Gib dem Spiel einen Namen.",
                },
            },
        }


class HostGameListSerializer(serializers.ModelSerializer):
    """`GET api/game/` — the host's own games, for `/app/host`. S13.

    Not `GameSessionSerializer`: that one is the whole row, including the
    password, and this list renders for a host looking at a page, not for a
    screen about to play. What it adds instead is the two counts the delete
    confirmation needs — "was dabei weggeht" cannot say "alle Daten", because
    nobody can weigh that.

    Both counts are annotated on the queryset rather than read per row, and
    `player_count` excludes the host's own seat the way `without_host_rows()`
    does — including the NULL case, which is every student: `user` is null for
    anyone who joined without an account, and a plain `!=` against
    `game_host` would drop them all.
    """

    round_count = serializers.IntegerField(read_only=True)
    player_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = gm.GameSession
        fields = (
            "game_id",
            "game_name",
            "game_map",
            "created_at",
            "started_at",
            "ended_at",
            "end_reason",
            "paused_at",
            "is_active",
            "round_count",
            "player_count",
        )
        read_only_fields = fields


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


class SeatRequestSerializer(serializers.Serializer):
    """Body of POST /api/game/<game_id>/player/: the host adds a seat (1.6).

    `name` is the only identifying thing this project collects from a player —
    see the data-minimisation note in the DSGVO page. There is no account.
    """

    name = serializers.CharField(max_length=100, trim_whitespace=True)

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Please enter a display name.")
        return name


class JoinRequestSerializer(SeatRequestSerializer):
    """Body of POST /api/game/join/<game_id>/: a name, and the password if
    the game has one."""

    password = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
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
    transport_mode = serializers.ChoiceField(
        choices=gm.AgentRoute.TransportMode.choices
    )
    optimization = serializers.ChoiceField(
        choices=gm.AgentRoute.Optimization.choices, required=False, allow_null=True
    )
    route = RouteInputSerializer()
    # The way home. Required: a commute is a round trip, and a turn without one
    # would be simulated as half a commute. It is a route of its own because
    # the graph is directed — a one-way street has no reverse edge, so the way
    # back is not the way there turned round.
    return_route = RouteInputSerializer()


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
