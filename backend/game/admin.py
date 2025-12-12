from django.contrib import admin

from .models import GameSession, GameRound, Player, PlayerMove


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("game_name", "game_id", "game_host", "is_active", "created_at")
    list_filter = ("is_active", "map_updates", "created_at")
    search_fields = ("game_name", "game_id", "game_host__username", "game_host__email")
    ordering = ("-created_at",)


@admin.register(GameRound)
class GameRoundAdmin(admin.ModelAdmin):
    list_display = ("game", "round_number", "status", "started_at")
    list_filter = ("status", "started_at")
    search_fields = ("game__game_name", "game__game_id")
    ordering = ("game", "round_number")


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "player_id", "game", "joined_at")
    list_filter = ("game", "joined_at")
    search_fields = (
        "name",
        "player_id",
        "game__game_name",
        "game__game_id",
        "user__username",
        "user__email",
    )
    ordering = ("game", "name")


@admin.register(PlayerMove)
class PlayerMoveAdmin(admin.ModelAdmin):
    list_display = ("game_round", "player", "action", "started_at")
    list_filter = ("action", "started_at")
    search_fields = (
        "player__name",
        "player__player_id",
        "game_round__game__game_name",
        "game_round__game__game_id",
        "action",
    )
    ordering = ("game_round", "started_at")
