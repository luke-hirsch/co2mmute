import json
import logging
import time
from typing import Awaitable, cast

import redis.asyncio as redis
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from co2mmute.utils import sanitize_group_name
from django.conf import settings

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

        player, close_code, reason, is_host = await resolve_player(
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
    # Redis key patterns for player tracking
    ROSTER_KEY_PATTERN = "game:{game_id}:roster"
    PLAYER_STATUS_KEY_PATTERN = "game:{game_id}:player:{player_id}:status"
    ROSTER_TTL_SECONDS = 24 * 60 * 60  # 24 hours

    # Player status values
    STATUS_READY = "ready"
    STATUS_MAKING_MOVE = "making_move"
    STATUS_WAITING = "waiting"
    STATUS_NOT_CONNECTED = "not_connected"

    async def connect(self) -> None:
        route = self.scope.get("url_route")
        if not route or "kwargs" not in route:
            logger.warning("Missing URL route for game state")
            await self.close(code=4400)
            return

        self.game_id = route["kwargs"]["game_id"]
        self.group_name = f"gamestate_{sanitize_group_name(self.game_id)}"

        player, close_code, reason, is_host = await resolve_player(
            self.scope, self.game_id
        )
        if close_code or player is None:
            logger.warning(
                f"GameState auth failed for {self.game_id}: code={close_code}"
            )
            await self.close(code=close_code)
            return

        self.player_id = player.player_id
        self.player_name = player.name or "Player"
        self.is_host = is_host
        self.controlled_by_host = player.controlled_by_host
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Register player as online and broadcast roster
        await self._register_player_online()
        await self._broadcast_roster()

        # Send current roster to the newly connected client
        roster = await self._get_roster()
        await self.send_json({
            "type": "roster.update",
            "game_id": self.game_id,
            "players": roster,
        })

        # Send current game state to the newly connected client
        game_state = await self._get_current_game_state()
        if game_state:
            await self.send_json({
                "type": "game.state",
                "game_id": self.game_id,
                "data": game_state,
            })

    async def disconnect(self, code: int) -> None:
        try:
            # Mark player as not connected and broadcast
            await self._mark_player_disconnected()
            await self._broadcast_roster()
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        finally:
            if hasattr(self, "redis_client"):
                await self.redis_client.close()

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
            return

    # ─────────────────────────────────────────────────────────────────────────
    # Player roster management
    # ─────────────────────────────────────────────────────────────────────────

    def _roster_key(self) -> str:
        return self.ROSTER_KEY_PATTERN.format(game_id=self.game_id)

    def _player_status_key(self, player_id: str) -> str:
        return self.PLAYER_STATUS_KEY_PATTERN.format(
            game_id=self.game_id, player_id=player_id
        )

    async def _register_player_online(self) -> None:
        """Register player in the roster and set initial status."""
        roster_key = self._roster_key()
        status_key = self._player_status_key(self.player_id)

        # Store player info in roster hash
        player_data = json.dumps({
            "player_id": self.player_id,
            "name": self.player_name,
            "is_host": self.is_host,
            "controlled_by_host": self.controlled_by_host,
            "online": True,
        })
        await self.redis_client.hset(roster_key, self.player_id, player_data)
        await self.redis_client.expire(roster_key, self.ROSTER_TTL_SECONDS)

        # Set player status to ready (will be updated by game events)
        await self.redis_client.set(status_key, self.STATUS_READY, ex=self.ROSTER_TTL_SECONDS)

    async def _mark_player_disconnected(self) -> None:
        """Mark player as disconnected in the roster."""
        roster_key = self._roster_key()
        status_key = self._player_status_key(self.player_id)

        # Update player online status
        player_data_raw = await self.redis_client.hget(roster_key, self.player_id)
        if player_data_raw:
            player_data = json.loads(player_data_raw)
            player_data["online"] = False
            await self.redis_client.hset(roster_key, self.player_id, json.dumps(player_data))

        # Update status
        await self.redis_client.set(status_key, self.STATUS_NOT_CONNECTED, ex=self.ROSTER_TTL_SECONDS)

    async def _get_roster(self) -> list[dict]:
        """Get current roster with player statuses."""
        roster_key = self._roster_key()
        roster_data = await self.redis_client.hgetall(roster_key)

        players = []
        for player_id, player_json in roster_data.items():
            try:
                player = json.loads(player_json)
                # Get player status
                status_key = self._player_status_key(player_id)
                status = await self.redis_client.get(status_key) or self.STATUS_NOT_CONNECTED
                player["status"] = status
                players.append(player)
            except Exception as e:
                logger.warning(f"Failed to parse player data: {e}")
                continue

        return players

    async def _broadcast_roster(self) -> None:
        """Broadcast roster update to all connected clients."""
        roster = await self._get_roster()
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "roster_update",
                "players": roster,
            }
        )

    async def roster_update(self, event: dict) -> None:
        """Handle roster update broadcast."""
        await self.send_json({
            "type": "roster.update",
            "game_id": self.game_id,
            "players": event.get("players", []),
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Game state events
    # ─────────────────────────────────────────────────────────────────────────

    async def game_state(self, event: dict) -> None:
        """
        Handle game state events broadcast from signals.

        Supported events:
        - game.started: Game has started, players move from lobby to game
        - game.ended: Game has ended (max rounds or CO2 limit reached)
        - round.started: A new round has begun
        - round.completed: Round finished, stats available
        - player.joined: A player joined the game
        - player.left: A player left the game
        """
        event_type = event.get("event", "")
        data = event.get("data", {})

        # Update player statuses based on game events
        if event_type == "round.started":
            await self._set_all_players_status(self.STATUS_MAKING_MOVE)
            await self._broadcast_roster()
        elif event_type == "round.completed":
            await self._set_all_players_status(self.STATUS_READY)
            await self._broadcast_roster()

        await self.send_json({
            "type": event_type,
            "game_id": self.game_id,
            "data": data,
        })

    async def player_status_update(self, event: dict) -> None:
        """Handle player status update (e.g., after submitting a move)."""
        player_id = event.get("player_id")
        status = event.get("status")

        if player_id and status:
            status_key = self._player_status_key(player_id)
            await self.redis_client.set(status_key, status, ex=self.ROSTER_TTL_SECONDS)
            await self._broadcast_roster()

    async def _set_all_players_status(self, status: str) -> None:
        """Set status for all online players."""
        roster = await self._get_roster()
        for player in roster:
            if player.get("online") and not player.get("is_host"):
                status_key = self._player_status_key(player["player_id"])
                await self.redis_client.set(status_key, status, ex=self.ROSTER_TTL_SECONDS)

    async def _get_current_game_state(self) -> dict | None:
        """Fetch current game state from database for reconnecting clients."""
        from channels.db import database_sync_to_async
        from game.models import GameSession, GameRound

        @database_sync_to_async
        def fetch_state():
            try:
                game = GameSession.objects.get(game_id=self.game_id)
            except GameSession.DoesNotExist:
                return None

            # Get current/latest round
            current_round = (
                GameRound.objects.filter(game=game)
                .order_by("-round_number")
                .first()
            )

            # Calculate total emissions across completed rounds
            total_emissions = sum(
                r.total_emissions_g
                for r in GameRound.objects.filter(
                    game=game, status=GameRound.Status.COMPLETED
                )
            )

            return {
                "isActive": game.is_active,
                "currentRound": current_round.round_number if current_round else 0,
                "totalEmissionsG": total_emissions,
                "maxCo2LevelG": game.max_CO2_level * 1000,
                "maxRounds": game.max_rounds,
                "startedAt": game.started_at.isoformat() if game.started_at else None,
                "endedAt": game.ended_at.isoformat() if game.ended_at else None,
            }

        return await fetch_state()
