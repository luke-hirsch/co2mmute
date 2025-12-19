import json
import time
from typing import Awaitable, cast
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
import redis.asyncio as redis

from .ws_auth import resolve_player
from .models import Player

import logging

logger = logging.getLogger(__name__)


def sanitize_group_name(game_id: str) -> str:
    """
    Sanitize game_id for use as a Channels group name.
    Group names must contain only ASCII alphanumerics, hyphens, underscores, or periods.
    We replace colons and hyphens with underscores to be safe.
    """
    return game_id.replace(":", "_").replace("-", "_")


class LobbyConsumer(AsyncWebsocketConsumer):
    # Redis key patterns - descriptive names for clarity
    PLAYER_DATA_KEY_PATTERN = (
        "lobby:{game_id}:player_data:{player_id}"  # Hash: player profile
    )
    PLAYER_PRESENCE_ZSET_KEY_PATTERN = (
        "lobby:{game_id}:presence_zset"  # Sorted set: player_id -> timestamp
    )
    PLAYER_METADATA_HASH_KEY_PATTERN = (
        "lobby:{game_id}:presence_meta"  # Hash: player_id -> player_data JSON
    )

    # TTL configuration
    PLAYER_ACTIVE_TTL_SECONDS = 10 * 60  # 10 minutes - keep offline players visible
    PRESENCE_STALE_THRESHOLD_SECONDS = (
        PLAYER_ACTIVE_TTL_SECONDS  # Remove if older than TTL
    )

    async def connect(self):
        # game_id from URL route
        route = self.scope.get("url_route")
        if not route or "kwargs" not in route:
            logger.warning("Missing URL route or kwargs")
            await self.close(code=4400)
            return
        self.game_id = route["kwargs"]["game_id"]
        self.group_name = f"lobby_{sanitize_group_name(self.game_id)}"

        # authentication via cookie
        player, close_code, reason, is_host = await resolve_player(
            self.scope, self.game_id
        )
        if close_code or player is None:
            logger.warning(
                f"WebSocket auth failed for lobby {self.game_id}: code={close_code}, reason={reason}"
            )
            await self.close(code=close_code)
            return

        self.player_id = player.player_id
        self.is_host = is_host
        self.player_payload = {
            "playerId": str(player.player_id),
            "name": player.name or "unknown Player",
            "isMuted": player.is_muted,
            "controlledByHost": player.controlled_by_host,
            "online": True,
            "joinedAt": player.joined_at.isoformat(),
        }

        # redis connection
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Only register regular players in the roster, not the host
        # The host is the game master, not a player in the player list
        if not self.is_host:
            # Store player in Redis and broadcast updated roster
            await self._register_player_presence()
            await self._broadcast_roster_to_group()
        else:
            logger.info(
                f"Host connected to lobby {self.game_id}, not registering in player roster"
            )
            # Still broadcast the updated roster to all players (in case any connected)
            await self._broadcast_roster_to_group()

    async def disconnect(self, close_code):
        try:
            if (
                hasattr(self, "player_id")
                and hasattr(self, "game_id")
                and not self.is_host
            ):
                # Mark player as offline instead of removing immediately
                # Don't do this for hosts since they're not in the player roster
                await self._mark_player_offline()
                await self._broadcast_roster_to_group()
        finally:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            if hasattr(self, "redis_client"):
                await self.redis_client.close()

    async def receive(self, text_data=None, bytes_data=None):
        # Accept ping from clients and use it as a cache refresh signal
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except Exception:
            return

        msg_type = data.get("type")

        # Ping acts as a heartbeat to refresh player presence in Redis
        if msg_type == "ping":
            await self._refresh_player_presence()
            await self.send(json.dumps({"type": "pong"}))
            return

    def _get_player_data_key(self):
        """Get Redis key for storing player data."""
        return self.PLAYER_DATA_KEY_PATTERN.format(
            game_id=self.game_id, player_id=self.player_id
        )

    def _get_presence_zset_key(self):
        """Get Redis sorted set key for tracking presence by timestamp."""
        return self.PLAYER_PRESENCE_ZSET_KEY_PATTERN.format(game_id=self.game_id)

    def _get_presence_metadata_key(self):
        """Get Redis hash key for storing player metadata by ID."""
        return self.PLAYER_METADATA_HASH_KEY_PATTERN.format(game_id=self.game_id)

    async def _register_player_presence(self):
        """Register player in Redis and mark as online."""
        current_timestamp = time.time()
        presence_zset_key = self._get_presence_zset_key()
        presence_meta_key = self._get_presence_metadata_key()

        # Clean up stale entries first
        await self._cleanup_stale_players()

        # Use Redis pipeline for atomic operations
        redis_pipe = self.redis_client.pipeline()

        # Add player to sorted set (for timestamp-based queries)
        redis_pipe.zadd(presence_zset_key, {str(self.player_id): current_timestamp})

        # Store player metadata in hash
        redis_pipe.hset(
            presence_meta_key, str(self.player_id), json.dumps(self.player_payload)
        )

        # Set expiration
        redis_pipe.expire(presence_zset_key, self.PLAYER_ACTIVE_TTL_SECONDS * 2)
        redis_pipe.expire(presence_meta_key, self.PLAYER_ACTIVE_TTL_SECONDS * 2)

        await redis_pipe.execute()

    async def _refresh_player_presence(self):
        """Refresh player presence on ping (extends TTL and updates timestamp)."""
        current_timestamp = time.time()
        presence_zset_key = self._get_presence_zset_key()
        presence_meta_key = self._get_presence_metadata_key()

        redis_pipe = self.redis_client.pipeline()

        # Update timestamp in sorted set
        redis_pipe.zadd(presence_zset_key, {str(self.player_id): current_timestamp})

        # Refresh player metadata (still online)
        redis_pipe.hset(
            presence_meta_key, str(self.player_id), json.dumps(self.player_payload)
        )

        # Refresh expiration
        redis_pipe.expire(presence_zset_key, self.PLAYER_ACTIVE_TTL_SECONDS * 2)
        redis_pipe.expire(presence_meta_key, self.PLAYER_ACTIVE_TTL_SECONDS * 2)

        await redis_pipe.execute()

    async def _mark_player_offline(self):
        """Mark player as offline (still visible in roster for TTL duration)."""
        current_timestamp = time.time()
        presence_zset_key = self._get_presence_zset_key()
        presence_meta_key = self._get_presence_metadata_key()

        offline_player_payload = self.player_payload.copy()
        offline_player_payload["online"] = False

        redis_pipe = self.redis_client.pipeline()

        # Keep timestamp updated so offline players appear in sorted set
        redis_pipe.zadd(presence_zset_key, {str(self.player_id): current_timestamp})

        # Update metadata to show offline status
        redis_pipe.hset(
            presence_meta_key, str(self.player_id), json.dumps(offline_player_payload)
        )

        # Keep expiration so offline players are visible for full TTL
        redis_pipe.expire(presence_zset_key, self.PLAYER_ACTIVE_TTL_SECONDS * 2)
        redis_pipe.expire(presence_meta_key, self.PLAYER_ACTIVE_TTL_SECONDS * 2)

        await redis_pipe.execute()

    async def _cleanup_stale_players(self):
        """Remove players that haven't been seen in PLAYER_ACTIVE_TTL_SECONDS."""
        current_timestamp = time.time()
        stale_cutoff_timestamp = (
            current_timestamp - self.PRESENCE_STALE_THRESHOLD_SECONDS
        )

        presence_zset_key = self._get_presence_zset_key()
        presence_meta_key = self._get_presence_metadata_key()

        # Get all stale player IDs from sorted set
        stale_player_ids = await self.redis_client.zrangebyscore(
            presence_zset_key, "-inf", stale_cutoff_timestamp
        )

        if stale_player_ids:
            # Remove stale entries atomically
            redis_pipe = self.redis_client.pipeline()
            redis_pipe.hdel(presence_meta_key, *stale_player_ids)
            redis_pipe.zremrangebyscore(
                presence_zset_key, "-inf", stale_cutoff_timestamp
            )
            await redis_pipe.execute()

    async def _build_roster_from_redis(self):
        """Build complete roster by fetching all player metadata from Redis and host-controlled players from DB."""
        presence_zset_key = self._get_presence_zset_key()
        presence_meta_key = self._get_presence_metadata_key()

        # Get all player IDs from sorted set (ordered by timestamp)
        all_player_ids = await self.redis_client.zrange(presence_zset_key, 0, -1)

        roster = []

        # First, add all connected players from Redis
        if all_player_ids:
            # Fetch metadata for all players
            raw_player_payloads = await cast(
                Awaitable[list[str | None]],
                self.redis_client.hmget(presence_meta_key, *all_player_ids),
            )

            for raw_payload in raw_player_payloads:
                if not raw_payload:
                    continue
                try:
                    player_data = json.loads(raw_payload)
                    roster.append(player_data)
                except Exception as e:
                    logger.warning(f"Failed to parse player payload: {e}")
                    continue

        # Second, add host-controlled players from DB that aren't already in Redis
        @database_sync_to_async
        def get_host_controlled_players():
            return list(
                Player.objects.filter(
                    game__game_id=self.game_id,
                    controlled_by_host=True,
                    left_at__isnull=True,  # Only active players
                ).values(
                    "player_id", "name", "is_muted", "controlled_by_host", "joined_at"
                )
            )

        host_controlled_players = await get_host_controlled_players()
        existing_player_ids = {p.get("playerId") for p in roster}

        for db_player in host_controlled_players:
            if db_player["player_id"] not in existing_player_ids:
                roster.append(
                    {
                        "playerId": db_player["player_id"],
                        "name": db_player["name"] or "unknown Player",
                        "isMuted": db_player["is_muted"],
                        "controlledByHost": db_player["controlled_by_host"],
                        "online": True,
                        "joinedAt": db_player["joined_at"].isoformat(),
                    }
                )

        # Sort by name for consistent ordering
        roster.sort(
            key=lambda player: (player.get("name", ""), player.get("playerId", ""))
        )
        return roster

    async def _broadcast_roster_to_group(self):
        """Build roster and broadcast to all players in game group."""
        roster = await self._build_roster_from_redis()
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "lobby.roster",
                "players": roster,
            },
        )

    async def lobby_roster(self, event):
        """Handler for roster broadcasts from group_send."""
        await self.send(
            json.dumps(
                {
                    "type": "lobby.roster",
                    "game_id": self.game_id,
                    "players": event["players"],
                }
            )
        )


class ChatConsumer(AsyncWebsocketConsumer):
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
        await self.send(
            json.dumps(
                {
                    "type": "chat.history",
                    "game_id": self.game_id,
                    "messages": message_history,
                }
            )
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
            await self.send(json.dumps({"type": "chat.error", "error": "Invalid JSON"}))
            return

        message_type = data.get("type")

        if message_type == "ping":
            await self.send(json.dumps({"type": "pong"}))
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
            await self.send(
                json.dumps({"type": "chat.error", "error": validation_error})
            )
            return

        rate_limit_error = await self._check_rate_limits()
        if rate_limit_error:
            await self.send(
                json.dumps({"type": "chat.error", "error": rate_limit_error})
            )
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
        await self.send(
            json.dumps(
                {
                    "type": "chat.message",
                    "game_id": self.game_id,
                    "message": message_data,
                }
            )
        )
