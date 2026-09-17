"""Seats: the Player rows that take part in a game, and who changes them.

The host adds seats that are played at the host machine
(controlled_by_host), in the lobby and while the game runs, and removes any
seat. A player can leave their own.

Before the game starts, removing a seat deletes the row, as it always did.
After the start the row stays, with left_at set: its moves and votes are
research data, and anonymisation renames it like any other.

Sync, like game/phases.py and game/roster.py.
"""

import logging

from co2mmute.utils import send_chat_system_message, send_game_state_message
from django.db import transaction
from django.utils import timezone

from game.models import GameSession, Player
from game.phases import schedule_recheck
from game.roster import schedule_broadcast, schedule_revoke
from game.rounds import active_player_count, schedule_round_completion_check

logger = logging.getLogger(__name__)


class SeatRefused(Exception):
    """A seat change the game doesn't allow. reason goes to the client as is."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def add_seat(game: GameSession, name: str) -> Player:
    """A new seat, played at the host machine. It counts against max_players.

    Allowed until the game ends. Added during a round, the seat is waited for
    in that round, so the host plays it from there.
    """
    with transaction.atomic():
        # The join locks the same row: two requests must not both take the
        # last free seat.
        game = GameSession.objects.select_for_update().get(pk=game.pk)
        if game.ended_at is not None:
            raise SeatRefused("ended")
        if active_player_count(game) >= game.max_players:
            raise SeatRefused("full")

        seat = Player.objects.create(game=game, name=name, controlled_by_host=True)
        # set_up_player writes agent_assignments with update(); read them back.
        seat.refresh_from_db()

    # game_id and player_id, never the name.
    logger.info(f"Host added seat {seat.player_id} to game {game.game_id}")
    return seat


def remove_seat(seat: Player, kicked: bool) -> None:
    """The host removes a seat (kicked), or a player leaves (not kicked)."""
    if seat.game.started_at is None:
        # Nothing to keep yet. signals.cleanup_leaving_player announces it.
        seat._was_kicked = kicked  # type: ignore
        seat.delete()
        return

    seat.left_at = timezone.now()
    seat.save(update_fields=["left_at"])
    announce_departure(seat, kicked)


def announce_departure(seat: Player, kicked: bool) -> None:
    """Everything that follows a seat leaving, whether the row is deleted or not.

    Chat and player.left at once. On commit: the seat's sockets are closed, the
    roster goes out, and the round and the between-round phase are checked
    again, because the seat may have been the last one they waited for.
    """
    game = seat.game
    name = seat.name or "A player"

    if kicked:
        send_chat_system_message(game.game_id, f"{name} was removed from the game")
    else:
        send_chat_system_message(game.game_id, f"{name} left the game")

    send_game_state_message(
        game.game_id,
        "player.left",
        {"player_id": seat.player_id, "player_name": name, "was_kicked": kicked},
    )

    schedule_revoke(seat.pk, "removed" if kicked else "left")
    schedule_broadcast(game.game_id)

    if game.is_active:
        schedule_round_completion_check(game.game_id)
        schedule_recheck(game.game_id)
