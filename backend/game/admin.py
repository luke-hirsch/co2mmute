from django.contrib import admin

from .models import (
    BikeMobility,
    BusMobility,
    CarMobility,
    GameRound,
    GameSession,
    GameStats,
    Player,
    PlayerMove,
    TrainMobility,
    WalkingMobility,
)


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
    list_display = ("session_round", "player", "action", "moved_at")
    list_filter = ("action", "moved_at")
    search_fields = (
        "player__name",
        "player__player_id",
        "session_round__game__game_name",
        "session_round__game__game_id",
        "action",
    )
    ordering = ("session_round", "moved_at")


@admin.register(GameStats)
class GameStatsAdmin(admin.ModelAdmin):
    list_display = ("session_round", "total_emissions_g", "total_cost_eur")
    search_fields = ("session_round__game__game_name", "session_round__game__game_id")
    ordering = ("session_round",)


@admin.register(CarMobility)
class CarMobilityAdmin(admin.ModelAdmin):
    list_display = ("session_round", "base_emissions_g_per_km", "base_cost_per_km")
    ordering = ("session_round",)


@admin.register(TrainMobility)
class TrainMobilityAdmin(admin.ModelAdmin):
    list_display = ("session_round", "base_emissions_g_per_km", "base_cost_per_km")
    ordering = ("session_round",)


@admin.register(BusMobility)
class BusMobilityAdmin(admin.ModelAdmin):
    list_display = ("session_round", "base_emissions_g_per_km", "base_cost_per_km")
    ordering = ("session_round",)


@admin.register(BikeMobility)
class BikeMobilityAdmin(admin.ModelAdmin):
    list_display = ("session_round", "emissions_g_per_km", "cost_per_km")
    ordering = ("session_round",)


@admin.register(WalkingMobility)
class WalkingMobilityAdmin(admin.ModelAdmin):
    list_display = ("session_round",)
    ordering = ("session_round",)
