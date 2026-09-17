"""Who is in a game and who is connected.

The list comes from the Player rows, so a removed player disappears and a seat
played at the host machine shows up without a socket of its own. The cache
(Redis in production) only answers "is this seat connected right now", keyed by
Player.pk so a new player_id (1.7) keeps it. That answer runs out by itself: a
presence key lives PRESENCE_TTL seconds and every client ping renews it, so a
backend restart that never ran disconnect() leaves nobody "online" for long.

A seat's status is read from the game, not stored: making_move or waiting while
a round is open (has the seat moved?), ready otherwise, not_connected when
offline.

Every function here is sync. The consumer calls them through
database_sync_to_async, the signals and views call them directly.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from co2mmute.utils import sanitize_group_name
from django.core.cache import cache
from django.db import transaction

from game.models import GameRound, GameSession, Player, PlayerMove

logger = logging.getLogger(__name__)

# The client pings every 30 s (frontend/src/utils/ws.ts). Three missed pings
# and the seat shows as offline.
PRESENCE_TTL = 90

READY = "ready"
MAKING_MOVE = "making_move"
WAITING = "waiting"
NOT_CONNECTED = "not_connected"


def player_group(player_pk: int) -> str:
    """The channel group of one seat's sockets."""
    return f"player_{player_pk}"


def _presence_key(player_pk: int) -> str:
    return f"game:presence:{player_pk}"


def build(game: GameSession) -> list[dict]:
    """The roster as roster.update carries it, in join order.

    Every seat still in the game, the host's own row included (flagged
    is_host; the player list in the frontend filters it out).
    """
    rows = list(
        Player.objects.filter(game=game, left_at__isnull=True).order_by(
            "joined_at", "pk"
        )
    )
    host_pks = set(
        Player.objects.filter(game=game).host_rows().values_list("pk", flat=True)  # type: ignore
    )
    present = cache.get_many([_presence_key(row.pk) for row in rows])
    host_online = any(_presence_key(pk) in present for pk in host_pks)

    game_round = GameRound.objects.filter(game=game).order_by("-round_number").first()
    round_open = game_round is not None and game_round.status == GameRound.Status.ACTIVE
    moved = set()
    if round_open:
        moved = set(
            PlayerMove.objects.filter(session_round=game_round).values_list(
                "player", flat=True
            )
        )

    roster = []
    for row in rows:
        is_host = row.pk in host_pks
        # A seat played at the host machine has no socket of its own. It is
        # there whenever the host is.
        online = _presence_key(row.pk) in present or (
            row.controlled_by_host and not is_host and host_online
        )
        if not online:
            status = NOT_CONNECTED
        elif round_open and not is_host:
            status = WAITING if row.pk in moved else MAKING_MOVE
        else:
            status = READY

        roster.append(
            {
                "player_id": row.player_id,
                "name": row.name or "Player",
                "is_host": is_host,
                "controlled_by_host": row.controlled_by_host,
                "online": online,
                "status": status,
            }
        )
    return roster


def broadcast(game_id: str) -> None:
    """Send the current roster to every socket in the game."""
    game = GameSession.objects.filter(game_id=game_id).first()
    if game is None:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("No channel layer configured, cannot send the roster")
        return
    async_to_sync(channel_layer.group_send)(
        f"gamestate_{sanitize_group_name(game_id)}",
        {"type": "roster_update", "players": build(game)},
    )


def schedule_broadcast(game_id: str) -> None:
    """broadcast() once the surrounding transaction has committed, so the
    roster sees the rows the transaction wrote."""
    transaction.on_commit(lambda: broadcast(game_id))


# ─────────────────────────────────────────────────────────────────────────────
# Presence, driven by the consumer
# ─────────────────────────────────────────────────────────────────────────────


def connected(game_id: str, player_pk: int | None) -> None:
    """A socket for this seat opened. None for a host without a host row."""
    if player_pk is not None:
        cache.set(_presence_key(player_pk), 1, PRESENCE_TTL)
    broadcast(game_id)


def heartbeat(game_id: str, player_pk: int) -> None:
    """The client pinged. Renew the seat's presence.

    add() only writes a missing key. If it was missing (expired, or another tab
    of the same player just disconnected), the others still show this seat as
    offline, so they get a fresh roster.
    """
    key = _presence_key(player_pk)
    if cache.add(key, 1, PRESENCE_TTL):
        broadcast(game_id)
    else:
        cache.touch(key, PRESENCE_TTL)


def disconnected(game_id: str, player_pk: int | None) -> None:
    """A socket for this seat closed."""
    if player_pk is not None:
        cache.delete(_presence_key(player_pk))
    broadcast(game_id)


# ─────────────────────────────────────────────────────────────────────────────
# Revoking a seat
# ─────────────────────────────────────────────────────────────────────────────


def revoke(player_pk: int, reason: str) -> None:
    """Tell every socket of this seat it is no longer theirs, and close them.

    reason: "removed" (the host removed the player) or "left" (the player
    left). 1.6 and 1.7 add "taken_over" and "handed_over".
    GameConsumer.player_revoked sends player.revoked and closes with 4403.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("No channel layer configured, cannot revoke a seat")
        return
    async_to_sync(channel_layer.group_send)(
        player_group(player_pk), {"type": "player_revoked", "reason": reason}
    )


def schedule_revoke(player_pk: int, reason: str) -> None:
    """revoke() once the surrounding transaction has committed. A rolled-back
    removal must not close anyone's socket."""
    transaction.on_commit(lambda: revoke(player_pk, reason))
