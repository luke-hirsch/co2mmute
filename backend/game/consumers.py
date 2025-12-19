import json
import time
from typing import Awaitable, cast
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
import redis.asyncio as redis

from .ws_auth import resolve_player

import logging

logger = logging.getLogger(__name__)


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
            await self.close(code=4400)
            return
        self.game_id = route["kwargs"]["game_id"]
        self.group_name = f"lobby:{self.game_id}"

        # authentication via cookie
        player, close_code, reason = await resolve_player(self.scope, self.game_id)
        if close_code or player is None:
            await self.close(code=close_code)
            return

        self.player_id = player.player_id
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

        # Store player in Redis and broadcast updated roster
        await self._register_player_presence()
        await self._broadcast_roster_to_group()

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "player_id") and hasattr(self, "game_id"):
                # Mark player as offline instead of removing immediately
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
        """Build complete roster by fetching all player metadata from Redis."""
        presence_zset_key = self._get_presence_zset_key()
        presence_meta_key = self._get_presence_metadata_key()

        # Get all player IDs from sorted set (ordered by timestamp)
        all_player_ids = await self.redis_client.zrange(presence_zset_key, 0, -1)

        if not all_player_ids:
            return []

        # Fetch metadata for all players
        raw_player_payloads = await cast(
            Awaitable[list[str | None]],
            self.redis_client.hmget(presence_meta_key, *all_player_ids),
        )

        roster = []
        for raw_payload in raw_player_payloads:
            if not raw_payload:
                continue
            try:
                player_data = json.loads(raw_payload)
                roster.append(player_data)
            except Exception as e:
                logger.warning(f"Failed to parse player payload: {e}")
                continue

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
    REDIS_KEY_TEMPLATE = "chat:{game_id}:messages"
    HISTORY_LIMIT = 100
    TTL_SECONDS = 2 * 60 * 60

    MAX_MESSAGE_LEN = 500
    MIN_SECONDS_BETWEEN_MSGS = 0.35
    CLOSE_CODE_UNAUTH = 4401
    CLOSE_CODE_FORBIDDEN = 4403

    async def connect(self):
        route = self.scope.get("url_route")
        if not route or "kwargs" not in route:
            await self.close(code=4400)
            return
        self.game_id = route["kwargs"]["game_id"]
        self.group_name = f"chat:{self.game_id}"

        player, close_code, reason = await resolve_player(self.scope, self.game_id)
        if close_code or player is None:
            await self.close(code=close_code)
            return

        self.player_id = player.player_id
        self.player_name = player.name or "Player"
        self.last_msg_ts = 0.0

        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.redis_key = self.REDIS_KEY_TEMPLATE.format(game_id=self.game_id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        history = await self._load_history()
        await self.send(
            json.dumps(
                {
                    "type": "chat.history",
                    "game_id": self.game_id,
                    "messages": history,
                }
            )
        )

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        finally:
            if hasattr(self, "redis"):
                await self.redis.close()

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except Exception:
            await self.send(json.dumps({"type": "chat.error", "error": "Invalid JSON"}))
            return

        msg_type = data.get("type")

        if msg_type == "ping":
            await self.send(json.dumps({"type": "pong"}))
            return

        if msg_type != "chat.message":
            return

        raw_msg = (data.get("message") or "").strip()
        if not raw_msg:
            return

        if len(raw_msg) > self.MAX_MESSAGE_LEN:
            await self.send(
                json.dumps({"type": "chat.error", "error": "Message too long"})
            )
            return

        now = time.time()
        if now - self.last_msg_ts < self.MIN_SECONDS_BETWEEN_MSGS:
            await self.send(json.dumps({"type": "chat.error", "error": "Slow down"}))
            return
        self.last_msg_ts = now

        message_obj = {
            "ts": int(now * 1000),
            "player_id": str(self.player_id),
            "player_name": self.player_name,
            "message": raw_msg,
        }

        await self._store_message(message_obj)

        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.broadcast", "message": message_obj},
        )

    async def chat_broadcast(self, event):
        await self.send(
            json.dumps(
                {
                    "type": "chat.message",
                    "game_id": self.game_id,
                    "message": event["message"],
                }
            )
        )

    async def _store_message(self, message_obj: dict):
        raw = json.dumps(message_obj, separators=(",", ":"))

        pipe = self.redis.pipeline()
        pipe.rpush(self.redis_key, raw)
        pipe.ltrim(self.redis_key, -self.HISTORY_LIMIT, -1)
        pipe.expire(self.redis_key, self.TTL_SECONDS)
        await pipe.execute()

    async def _load_history(self):
        raw_items = await cast(
            Awaitable[list[str]],
            self.redis.lrange(self.redis_key, -self.HISTORY_LIMIT, -1),
        )

        messages = []
        for raw in raw_items:
            try:
                messages.append(json.loads(raw))
            except Exception:
                pass
        return messages
