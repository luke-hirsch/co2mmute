import json
import logging
import time
from collections.abc import Awaitable
from typing import cast

import redis.asyncio as redis
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from co2mmute.utils import sanitize_group_name
from django.conf import settings

from game.phases import (
    ack_host_seats,
    ack_stats,
    force_leave_as_is,
    open_vote,
    submit_stalemate_vote,
    submit_vote,
    vote_options,
)
from game.roster import connected, disconnected, heartbeat, player_group
from game.ws_auth import resolve_player

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    CHAT_MESSAGES_REDIS_KEY_PATTERN = "chat:{game_id}:messages"
    CHAT_MESSAGE_HISTORY_LIMIT = 100
    CHAT_HISTORY_TTL_SECONDS = 2 * 60 * 60

    CHAT_MESSAGE_MAX_LENGTH = 500
    INDIVIDUAL_RATE_LIMIT_SECONDS = 0.35
    GLOBAL_RATE_LIMIT_KEY_PATTERN = "chat:rate_limit:{game_id}"
    GLOBAL_RATE_LIMIT_THRESHOLD_PER_SECOND = 10
    GLOBAL_RATE_LIMIT_WINDOW_SECONDS = 1

    CLOSE_CODE_UNAUTH = 4401
    CLOSE_CODE_FORBIDDEN = 4403

    async def connect(self):
        route = self.scope.get("url_route")
        if not route or "kwargs" not in route:
            logger.warning("Missing URL route or kwargs for chat")
            await self.close(code=4400)
            return

        self.game_id = route["kwargs"]["game_id"]
        self.group_name = f"chat_{sanitize_group_name(self.game_id)}"

        player, close_code, reason, _is_host = await resolve_player(
            self.scope, self.game_id
        )
        if close_code or player is None:
            logger.warning(
                f"WebSocket auth failed for chat {self.game_id}: code={close_code}, reason={reason}"
            )
            await self.close(code=close_code)
            return

        self.player_id = player.player_id
        self.player_name = player.name or "Player"
        self.last_message_sent_timestamp = 0.0

        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.chat_messages_redis_key = self.CHAT_MESSAGES_REDIS_KEY_PATTERN.format(
            game_id=self.game_id
        )
        self.global_rate_limit_key = self.GLOBAL_RATE_LIMIT_KEY_PATTERN.format(
            game_id=self.game_id
        )

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        message_history = await self._load_message_history()
        await self.send_json(
            {
                "type": "chat.history",
                "game_id": self.game_id,
                "messages": message_history,
            }
        )

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        finally:
            if hasattr(self, "redis_client"):
                await self.redis_client.close()

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except Exception:
            await self.send_json({"type": "chat.error", "error": "Invalid JSON"})
            return

        message_type = data.get("type")

        if message_type == "ping":
            await self.send_json({"type": "pong"})
            return

        if message_type != "chat.message":
            return

        await self._handle_chat_message(data)

    async def _handle_chat_message(self, data: dict):
        raw_message_text = (data.get("message") or "").strip()

        if not raw_message_text:
            return

        validation_error = self._validate_message_content(raw_message_text)
        if validation_error:
            await self.send_json({"type": "chat.error", "error": validation_error})
            return

        rate_limit_error = await self._check_rate_limits()
        if rate_limit_error:
            await self.send_json({"type": "chat.error", "error": rate_limit_error})
            return

        message_object = await self._build_message_object(raw_message_text)
        await self._store_message(message_object)

        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.broadcast", "message_data": message_object},
        )

    def _validate_message_content(self, message_text: str) -> str | None:
        if len(message_text) > self.CHAT_MESSAGE_MAX_LENGTH:
            return "Message too long"
        return None

    async def _check_rate_limits(self) -> str | None:
        current_timestamp = time.time()

        if (
            current_timestamp - self.last_message_sent_timestamp
            < self.INDIVIDUAL_RATE_LIMIT_SECONDS
        ):
            return "Slow down"

        messages_in_window = await self.redis_client.incr(self.global_rate_limit_key)
        if messages_in_window == 1:
            await self.redis_client.expire(
                self.global_rate_limit_key, self.GLOBAL_RATE_LIMIT_WINDOW_SECONDS
            )

        if messages_in_window > self.GLOBAL_RATE_LIMIT_THRESHOLD_PER_SECOND:
            return "Chat is moving too fast"

        self.last_message_sent_timestamp = current_timestamp
        return None

    async def _build_message_object(self, message_text: str) -> dict:
        current_timestamp_ms = int(time.time() * 1000)
        return {
            "ts": current_timestamp_ms,
            "playerName": self.player_name,
            "message": message_text,
        }

    async def _store_message(self, message_object: dict):
        raw_message_json = json.dumps(message_object, separators=(",", ":"))

        redis_pipe = self.redis_client.pipeline()
        redis_pipe.rpush(self.chat_messages_redis_key, raw_message_json)
        redis_pipe.ltrim(
            self.chat_messages_redis_key,
            -self.CHAT_MESSAGE_HISTORY_LIMIT,
            -1,
        )
        redis_pipe.expire(self.chat_messages_redis_key, self.CHAT_HISTORY_TTL_SECONDS)
        await redis_pipe.execute()

    async def _load_message_history(self) -> list[dict]:
        raw_message_items = await cast(
            Awaitable[list[str]],
            self.redis_client.lrange(
                self.chat_messages_redis_key, -self.CHAT_MESSAGE_HISTORY_LIMIT, -1
            ),
        )

        parsed_messages = []
        for raw_message in raw_message_items:
            try:
                parsed_message = json.loads(raw_message)
                parsed_messages.append(parsed_message)
            except Exception as parse_error:
                logger.warning(
                    f"Failed to parse stored chat message for game {self.game_id}: {parse_error}"
                )
                continue

        return parsed_messages

    async def chat_broadcast(self, event):
        message_data = event.get("message_data", {})
        await self.send_json(
            {
                "type": "chat.message",
                "game_id": self.game_id,
                "message": message_data,
            }
        )

    async def chat_system(self, event):
        """Handle system messages like player join/leave notifications."""
        await self.send_json(
            {
                "type": "chat.system",
                "game_id": self.game_id,
                "message": event.get("message", ""),
            }
        )


class GameConsumer(AsyncJsonWebsocketConsumer):
    CLOSE_CODE_REVOKED = 4403

    async def connect(self) -> None:
        route = self.scope.get("url_route")
        if not route or "kwargs" not in route:
            logger.warning("Missing URL route for game state")
            await self.close(code=4400)
            return

        self.game_id = route["kwargs"]["game_id"]
        self.group_name = f"gamestate_{sanitize_group_name(self.game_id)}"

        player, close_code, _reason, is_host = await resolve_player(
            self.scope, self.game_id
        )
        if close_code or player is None:
            logger.warning(
                f"GameState auth failed for {self.game_id}: code={close_code}"
            )
            await self.close(code=close_code)
            return

        self.player_id = player.player_id
        # The seat's Player row; for the host, their own row. Presence and the
        # per-seat group hang on it. None only for a game older than host rows.
        self.player_pk = player.pk  # type: ignore
        self.is_host = is_host

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        if self.player_pk is not None:
            await self.channel_layer.group_add(
                player_group(self.player_pk), self.channel_name
            )
        await self.accept()

        # Everyone, this socket included, gets the roster with this seat online.
        await database_sync_to_async(connected)(self.game_id, self.player_pk)

        # Send current game state to the newly connected client
        game_state = await self._get_current_game_state()
        if game_state:
            await self.send_json(
                {
                    "type": "game.state",
                    "game_id": self.game_id,
                    "data": game_state,
                }
            )

    async def disconnect(self, code: int) -> None:
        if not hasattr(self, "player_pk"):
            return
        if self.player_pk is not None:
            await self.channel_layer.group_discard(
                player_group(self.player_pk), self.channel_name
            )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await database_sync_to_async(disconnected)(self.game_id, self.player_pk)

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
        **kwargs,
    ) -> None:
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except Exception:
            return

        msg_type = data.get("type")

        if msg_type == "ping":
            await self.send(json.dumps({"type": "pong"}))
            if self.player_pk is not None:
                await database_sync_to_async(heartbeat)(self.game_id, self.player_pk)
            return

        if msg_type == "player.stats_ack":
            await self._handle_stats_ack()
            return

        if msg_type == "vote.open":
            await self._handle_vote_open()
            return

        if msg_type == "vote.submit":
            await self._handle_vote_submit(data)
            return

        if msg_type == "stalemate.vote":
            await self._handle_stalemate_vote(data)
            return

        if msg_type == "stalemate.force_leave":
            await self._handle_stalemate_force_leave()
            return

    # ─────────────────────────────────────────────────────────────────────────
    # Roster. Built from the Player rows in game/roster.py.
    # ─────────────────────────────────────────────────────────────────────────

    async def roster_update(self, event: dict) -> None:
        """Forward a roster sent by game.roster.broadcast."""
        await self.send_json(
            {
                "type": "roster.update",
                "game_id": self.game_id,
                "players": event.get("players", []),
            }
        )

    async def player_revoked(self, event: dict) -> None:
        """This seat is no longer ours (game.roster.revoke). Say why, hang up."""
        await self.send_json(
            {
                "type": "player.revoked",
                "game_id": self.game_id,
                "data": {"reason": event.get("reason", "")},
            }
        )
        await self.close(code=self.CLOSE_CODE_REVOKED)

    # ─────────────────────────────────────────────────────────────────────────
    # Game state events
    # ─────────────────────────────────────────────────────────────────────────

    async def game_state(self, event: dict) -> None:
        """
        Forward game state events broadcast by send_game_state_message.

        Supported events:
        - game.started: Game has started, players move from lobby to game
        - game.ended: Game has ended (max rounds or CO2 limit reached)
        - round.started: A new round has begun
        - round.completed: Round finished, stats available
        - player.joined: A player joined the game
        - player.left: A player left the game

        The statuses in the roster follow from the game itself; whoever sends
        one of these events also sends a fresh roster.
        """
        await self.send_json(
            {
                "type": event.get("event", ""),
                "game_id": self.game_id,
                "data": event.get("data", {}),
            }
        )

    async def _get_current_game_state(self) -> dict | None:
        """Fetch current game state from database for reconnecting clients."""
        from game.models import GameRound, GameSession

        @database_sync_to_async
        def fetch_state():
            try:
                game = GameSession.objects.get(game_id=self.game_id)
            except GameSession.DoesNotExist:
                return None

            # Get current/latest round
            current_round = (
                GameRound.objects.filter(game=game).order_by("-round_number").first()
            )

            # Calculate total emissions across completed rounds
            total_emissions = sum(
                r.total_emissions_g
                for r in GameRound.objects.filter(
                    game=game, status=GameRound.Status.COMPLETED
                )
            )

            between_round_phase = (
                current_round.between_round_phase if current_round else "none"
            )

            # The ballot stored on the round: the options the players were shown
            # in round.completed.
            map_versions = []
            if (
                between_round_phase != GameRound.BetweenRoundPhase.NONE
                and current_round
            ):
                map_versions = vote_options(current_round)

            return {
                "isActive": game.is_active,
                "currentRound": current_round.round_number if current_round else 0,
                "totalEmissionsG": total_emissions,
                "maxCo2LevelG": game.max_CO2_level * 1000,
                "maxRounds": game.max_rounds,
                "startedAt": game.started_at.isoformat() if game.started_at else None,
                "endedAt": game.ended_at.isoformat() if game.ended_at else None,
                "betweenRoundPhase": between_round_phase,
                "activeMapVersionId": game.active_map_version_id,  # type: ignore
                "hasMapVersions": bool(map_versions),
                "mapVersions": map_versions,
            }

        return await fetch_state()

    # ─────────────────────────────────────────────────────────────────────────
    # Between-round phases (stats → discussion → voting → next round).
    # The rules live in game/phases.py. This part only translates messages.
    # ─────────────────────────────────────────────────────────────────────────

    async def between_round_event(self, event: dict) -> None:
        """Forward a between-round event sent by game.phases."""
        await self.send_json(
            {
                "type": event.get("event", ""),
                "game_id": self.game_id,
                "data": event.get("data", {}),
            }
        )

    def _voter(self, data: dict) -> tuple[str, bool]:
        """Whose vote a message carries, and whether the host sent it.

        A player always votes for themselves. The host names the seat in
        player_id; game.phases accepts only one played at the host machine.
        """
        if self.is_host:
            return str(data.get("player_id") or ""), True
        return str(self.player_id), False

    async def _handle_stats_ack(self) -> None:
        """A player has read the stats. The host's ack counts for every seat
        played at the host machine."""
        if self.is_host:
            await database_sync_to_async(ack_host_seats)(self.game_id)
            return
        await database_sync_to_async(ack_stats)(self.game_id, str(self.player_id))

    async def _handle_vote_open(self) -> None:
        """Host opens voting."""
        if not self.is_host:
            await self.send_json(
                {"type": "error", "message": "Only host can open voting"}
            )
            return
        opened = await database_sync_to_async(open_vote)(self.game_id)
        if not opened:
            await self.send_json(
                {"type": "error", "message": "Voting can't be opened now"}
            )

    async def _handle_vote_submit(self, data: dict) -> None:
        """A vote for a map version, from a player or the host for a seat."""
        voter, by_host = self._voter(data)
        version_id = data.get("version_id")  # null/None = "Leave as it is"
        recorded = await database_sync_to_async(submit_vote)(
            self.game_id, voter, version_id, by_host=by_host
        )
        if not recorded:
            await self.send_json(
                {"type": "error", "message": "Vote failed or already voted"}
            )

    async def _handle_stalemate_vote(self, data: dict) -> None:
        """Vote again after a tie? From a player, or the host for a seat."""
        voter, by_host = self._voter(data)
        want_revote = bool(data.get("want_revote", False))
        await database_sync_to_async(submit_stalemate_vote)(
            self.game_id, voter, want_revote, by_host=by_host
        )

    async def _handle_stalemate_force_leave(self) -> None:
        """Host forces 'leave as is' outcome in a stalemate."""
        if not self.is_host:
            await self.send_json(
                {"type": "error", "message": "Only host can force resolve"}
            )
            return
        await database_sync_to_async(force_leave_as_is)(self.game_id)
