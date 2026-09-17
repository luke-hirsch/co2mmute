"""Seats: the Player rows that take part in a game, and who changes them.

The host adds seats that are played at the host machine
(controlled_by_host), in the lobby and while the game runs, and removes any
seat. A player can leave their own.

Before the game starts, removing a seat deletes the row, as it always did.
After the start the row stays, with left_at set: its moves and votes are
research data, and anonymisation renames it like any other.

 A seat moves between devices. The host takes a student's seat
over, and a short code hands a seat to whichever device redeems it. Both give
the seat a new player_id: every cookie naming the old one is worthless, and
the old device's sockets are closed. Moves, votes and acks hang on the row and
stay.


"""

import logging
import secrets

from co2mmute.utils import send_chat_system_message, send_game_state_message
from django.core.cache import cache
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


# ─────────────────────────────────────────────────────────────────────────────
# Moving a seat to another device (1.7)
# ─────────────────────────────────────────────────────────────────────────────

# A code is a bearer token: whoever reads it off the projector can take the
# seat. So it is short-lived, single use, and only made on request.
CODE_TTL = 5 * 60
# No 0/O and no 1/I/L: the code is read off a screen and typed on a phone.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def _code_key(code: str) -> str:
    return f"seatcode:{code}"


def _seat_code_key(player_pk: int) -> str:
    return f"seatcode:player:{player_pk}"


def _check_movable(seat: Player) -> None:
    """Raise SeatRefused if this seat can't change device at all."""
    if seat.game.ended_at is not None:
        raise SeatRefused("ended")
    if Player.objects.filter(pk=seat.pk).host_rows().exists():  # type: ignore
        raise SeatRefused("host")


def drop_code(player_pk: int) -> None:
    """Forget the seat's live code, if it has one."""
    code = cache.get(_seat_code_key(player_pk))
    if code:
        cache.delete(_code_key(code))
    cache.delete(_seat_code_key(player_pk))


def issue_code(seat: Player) -> str:
    """A new code for this seat. The seat's previous code stops working.

    Raises SeatRefused: "ended", "host" (the host's own row).
    """
    _check_movable(seat)
    drop_code(seat.pk)
    entry = {"game_id": seat.game.game_id, "player_pk": seat.pk}
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        # add() writes only a free key, so two live seats never share a code.
        if cache.add(_code_key(code), entry, CODE_TTL):
            break
    cache.set(_seat_code_key(seat.pk), code, CODE_TTL)
    return code


def seat_for_code(code: str) -> Player | None:
    """The seat a live code points at, or None. Doesn't use the code up.

    A code only counts while it is still the seat's current one, so a code
    overtaken by a newer one is dead even if its own key hasn't run out.
    """
    code = code.strip().upper()
    entry = cache.get(_code_key(code))
    if not entry or cache.get(_seat_code_key(entry["player_pk"])) != code:
        return None
    return (
        Player.objects.select_related("game")
        .filter(pk=entry["player_pk"], left_at__isnull=True)
        .first()
    )


def redeem_code(code: str) -> tuple[Player, str]:
    """Hand the seat behind the code to the device that sent it.

    Returns the seat with its new player_id, and the old player_id. Single
    use: cache.delete() returns True to exactly one caller. Raises
    SeatRefused: "unknown" (no such live code, or already used), "ended".
    """
    code = code.strip().upper()
    seat = seat_for_code(code)
    if seat is None:
        raise SeatRefused("unknown")
    _check_movable(seat)
    if not cache.delete(_code_key(code)):
        raise SeatRefused("unknown")
    cache.delete(_seat_code_key(seat.pk))

    with transaction.atomic():
        seat = Player.objects.select_for_update().get(pk=seat.pk)
        if seat.left_at is not None:
            raise SeatRefused("unknown")
        seat.controlled_by_host = False
        old_player_id = _rotate(seat, "handed_over")
    return seat, old_player_id


def take_over(seat: Player) -> tuple[Player, str]:
    """The host plays this seat from now on; the student's device is out.

    Returns the seat with its new player_id, and the old player_id. A live
    code for the seat dies. Raises SeatRefused: "ended", "host",
    "controlled" (the host plays it already).
    """
    with transaction.atomic():
        seat = Player.objects.select_for_update().get(pk=seat.pk)
        _check_movable(seat)
        if seat.controlled_by_host:
            raise SeatRefused("controlled")
        seat.controlled_by_host = True
        old_player_id = _rotate(seat, "taken_over")
    drop_code(seat.pk)
    return seat, old_player_id


def _rotate(seat: Player, reason: str) -> str:
    """Save the seat with a new player_id and announce it. Returns the old id.

    reason is "taken_over" or "handed_over". On commit: player.<reason> to the
    game, player.revoked to the seat's group, and the roster. Only the old
    device's sockets are in that group; the new device connects afterwards,
    with the new cookie.
    """
    old_player_id = str(seat.player_id)
    seat.player_id = seat.generate_unique_player_id()
    seat.save(update_fields=["controlled_by_host", "player_id"])

    game_id = seat.game.game_id
    change = {"old_player_id": old_player_id, "new_player_id": seat.player_id}
    transaction.on_commit(
        lambda: send_game_state_message(game_id, f"player.{reason}", change)
    )
    schedule_revoke(seat.pk, reason)
    schedule_broadcast(game_id)
    # game_id and player_ids, never the name.
    logger.info(f"Seat {old_player_id} of game {game_id} is now {seat.player_id}")
    return old_player_id
