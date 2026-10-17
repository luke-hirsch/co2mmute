from django.contrib import admin

from .models import (
    GameRound,
    GameSession,
    Persona,
    Player,
    PlayerMove,
)


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("game_name", "game_id", "game_host", "is_active", "created_at")
    list_filter = (
        "is_active",
        "map_updates",
        "balanced_deal",
        "hide_co2",
        "created_at",
    )
    search_fields = (
        "game_name",
        "game_id",
        "game_host__username",
        "game_host__email",
    )
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


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    """The standard Pendlertypen are the rows with no game: filter on "Spiel"
    being empty to edit what every create form offers. A game's own are its
    copies, and editing one changes that game's debrief."""

    list_display = ("name", "description", "game", "order")
    list_filter = (("game", admin.EmptyFieldListFilter),)
    search_fields = ("name", "description", "game__game_name", "game__game_id")
    ordering = ("game", "order", "pk")
