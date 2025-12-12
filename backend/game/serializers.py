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
            "max_players",
            "agent_per_player",
            "max_rounds",
            "max_CO2_level",
            "lobby_open",
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
            "is_active",
            "created_at",
            "updated_at",
            "started_at",
            "ended_at",
        )

    def validate(self, attrs):
        max_players = attrs.get(
            "max_players", getattr(self.instance, "max_players", None)
        )
        agent_per_player = attrs.get(
            "agent_per_player", getattr(self.instance, "agent_per_player", None)
        )
        max_rounds = attrs.get(
            "max_rounds", getattr(self.instance, "max_rounds", None)
        )
        max_co2_level = attrs.get(
            "max_CO2_level", getattr(self.instance, "max_CO2_level", None)
        )

        errors = {}

        if max_players is not None:
            if max_players < 1:
                errors["max_players"] = "max_players must be at least 1."
            if agent_per_player is not None and agent_per_player > max_players:
                errors[
                    "agent_per_player"
                ] = "agent_per_player cannot exceed max_players."

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
        )
        read_only_fields = ("id", "player_id", "joined_at")
