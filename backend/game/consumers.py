from channels.generic.websocket import AsyncWebsocketConsumer

# game/consumers.py

import json
import time

from django.conf import settings

import redis.asyncio as redis

from .ws_auth import resolve_player


class LobbyConsumer(AsyncWebsocketConsumer):
    # Redis key patterns
    PRESENCE_ZSET = "lobby:{game_id}:players:z"
    PRESENCE_META = "lobby:{game_id}:players:meta"
    PRESENCE_TTL_SECONDS = 120

    # ---------- lifecycle ----------

    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group_name = f"lobby:{self.game_id}"
        # --- authenticate via centralized resolver ---
        player, close_code, reason = await resolve_player(self.scope, self.game_id)
        if close_code:
            await self.close(code=close_code)
            return

        self.player_id = player.player_id
        self.player_payload = {"id": str(player.player_id), "name": player.name or "Player"}

        # --- setup redis ---
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

        # --- join ---
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self._presence_add()
        await self._broadcast_roster()

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "redis"):
                await self._presence_remove()
                await self._broadcast_roster()
        finally:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            if hasattr(self, "redis"):
                await self.redis.close()

    async def receive(self, text_data=None, bytes_data=None):
        """
        Lobby doesn't need inbound messages yet.
        This exists so clients can send keepalive/ping if desired.
        """
        if not text_data:
            return

        data = json.loads(text_data)
        if data.get("type") == "ping":
            await self.send(json.dumps({"type": "pong"}))

    # ---------- redis presence ----------

    def _zset_key(self):
        return self.PRESENCE_ZSET.format(game_id=self.game_id)

    def _meta_key(self):
        return self.PRESENCE_META.format(game_id=self.game_id)

    async def _presence_add(self):
        now = time.time()
        zkey = self._zset_key()
        mkey = self._meta_key()

        # remove stale entries first
        cutoff = now - self.PRESENCE_TTL_SECONDS
        stale = await self.redis.zrangebyscore(zkey, "-inf", cutoff)
        if stale:
            await self.redis.hdel(mkey, *stale)
            await self.redis.zremrangebyscore(zkey, "-inf", cutoff)

        # write/update this player's meta and timestamp
        pipe = self.redis.pipeline()
        pipe.hset(mkey, str(self.player_id), json.dumps(self.player_payload))
        pipe.zadd(zkey, {str(self.player_id): now})
        pipe.expire(zkey, self.PRESENCE_TTL_SECONDS * 2)
        pipe.expire(mkey, self.PRESENCE_TTL_SECONDS * 2)
        await pipe.execute()

    async def _presence_remove(self):
        zkey = self._zset_key()
        mkey = self._meta_key()
        await self.redis.hdel(mkey, str(self.player_id))
        await self.redis.zrem(zkey, str(self.player_id))

    async def _get_roster(self):
        zkey = self._zset_key()
        mkey = self._meta_key()

        members = await self.redis.zrange(zkey, 0, -1)
        roster = []
        if not members:
            return roster

        meta = await self.redis.hmget(mkey, *members)
        for raw in meta:
            if not raw:
                continue
            try:
                roster.append(json.loads(raw))
            except Exception:
                pass
        roster.sort(key=lambda x: (x.get("name", ""), x.get("id", "")))
        return roster

    async def _broadcast_roster(self):
        roster = await self._get_roster()
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "lobby.roster",
                "players": roster,
            },
        )

    # ---------- group handlers ----------

    async def lobby_roster(self, event):
        await self.send(
            json.dumps(
                {
                    "type": "lobby.roster",
                    "game_id": self.game_id,
                    "players": event["players"],
                }
            )
        )

    # ---------- helpers ----------
    # Authentication and cookie helpers moved to `game.ws_auth.resolve_player`


class ChatConsumer(AsyncWebsocketConsumer):
    # cookie handling delegated to ws_auth.resolve_player

    # Redis config
    REDIS_KEY_TEMPLATE = "chat:{game_id}:messages"
    HISTORY_LIMIT = 100  # how many messages we keep + send on connect
    TTL_SECONDS = 2 * 60 * 60  # 2 hours. tweak as you like.

    # Guardrails
    MAX_MESSAGE_LEN = 500  # keep it short. it's kids, not a novel.
    MIN_SECONDS_BETWEEN_MSGS = 0.35  # basic anti-spam
    CLOSE_CODE_UNAUTH = 4401
    CLOSE_CODE_FORBIDDEN = 4403

    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group_name = f"chat:{self.game_id}"

        # --- authenticate via centralized resolver ---
        player, close_code, reason = await resolve_player(self.scope, self.game_id)
        if close_code:
            await self.close(code=close_code)
            return

        self.player_id = player.player_id
        self.player_name = player.name or "Player"
        self.last_msg_ts = 0.0

        # Redis client
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.redis_key = self.REDIS_KEY_TEMPLATE.format(game_id=self.game_id)

        # Join + accept
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send history (last N, in chronological order)
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
            # ignore unknown messages (or you can error)
            return

        raw_msg = (data.get("message") or "").strip()
        if not raw_msg:
            return

        if len(raw_msg) > self.MAX_MESSAGE_LEN:
            await self.send(
                json.dumps({"type": "chat.error", "error": "Message too long"})
            )
            return

        # basic rate limiting
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

        # Store in Redis (ephemeral history) and extend TTL
        await self._store_message(message_obj)

        # Broadcast to everyone in this game chat
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

    # ---------- Redis helpers ----------

    async def _store_message(self, message_obj: dict):
        raw = json.dumps(message_obj, separators=(",", ":"))

        # Use a pipeline: push, trim, ensure TTL
        pipe = self.redis.pipeline()
        pipe.rpush(self.redis_key, raw)
        pipe.ltrim(self.redis_key, -self.HISTORY_LIMIT, -1)
        pipe.expire(self.redis_key, self.TTL_SECONDS)
        await pipe.execute()

    async def _load_history(self):
        # last N messages (already stored chronologically)
        raw_items = await self.redis.lrange(self.redis_key, -self.HISTORY_LIMIT, -1)
        messages = []
        for raw in raw_items:
            try:
                messages.append(json.loads(raw))
            except Exception:
                pass
        return messages

    # ---------- Cookie helpers ----------

    # cookie/db helpers moved to `game.ws_auth.resolve_player` (centralized)

    # (DB helpers moved to ws_auth.resolve_player)
