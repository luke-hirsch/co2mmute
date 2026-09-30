/**
 * Everything `ws/chat/<game_id>/` can send, as one discriminated union.
 *
 * The chat is the second socket a game opens, and the only other consumer in
 * `game/consumers.py`. It is separate from `ws/game/` on purpose: it is the one
 * channel whose messages are written by players rather than derived from the
 * simulation, it has its own rate limits, and the host can switch it off
 * without touching the game socket.
 *
 * Where the shapes come from, so the next person can check them — all of it is
 * `ChatConsumer` in `game/consumers.py`:
 * - `connect()`          — chat.history, once, on every connect
 * - `chat_broadcast`     — chat.message
 * - `chat_system`        — chat.system (join notices, from game/signals.py)
 * - `_handle_chat_message` — chat.error, to the one client that was refused
 *
 * The envelope is not uniform and is described rather than smoothed over:
 * `chat.message` carries a message *object*, `chat.system` carries a bare
 * string, and `chat.error` carries neither a `game_id` nor a message at all.
 *
 * What is deliberately **not** here: `ping` and `pong`. `BaseWSClient` answers
 * those itself before `handleMessage` ever sees them, on both sockets.
 */

import { de } from "@/lib/de";
import { BaseWSClient } from "@/utils/ws";

/**
 * One stored message. `ChatConsumer._build_message_object`.
 *
 * `playerName` and nothing else — the consumer does not send a `player_id`, so
 * this is all the screen has to go on. Two players can legitimately carry the
 * same name (`Player.name` has no uniqueness constraint; only `player_id` does),
 * which is why the name prints on every line rather than being hidden on the
 * ones the reader wrote.
 */
export type ChatMessage = {
  /** Epoch milliseconds, from the server's clock. */
  ts: number;
  playerName: string;
  message: string;
};

export type ChatEvent =
  | { type: "chat.history"; game_id: string; messages: ChatMessage[] }
  | { type: "chat.message"; game_id: string; message: ChatMessage }
  | { type: "chat.system"; game_id: string; message: string }
  | { type: "chat.error"; error: string };

export type ChatEventType = ChatEvent["type"];

/**
 * How many lines the screen keeps.
 *
 * The same window as `ChatConsumer.CHAT_MESSAGE_HISTORY_LIMIT`, so what a
 * reconnect restores is about what was already on screen. Without a bound a
 * double lesson would grow the array all afternoon on a phone.
 */
export const CHAT_TRANSCRIPT_LIMIT = 100;

/**
 * Narrow an unknown socket payload to a `ChatEvent`.
 *
 * Shallow, like `asGameEvent` — but unlike it this one checks the prefix, and
 * that is not pedantry: both sockets are open at once on every screen in a
 * game, so "has a string type" alone would let a `roster.update` through into
 * the transcript.
 */
export function asChatEvent(payload: unknown): ChatEvent | null {
  if (!payload || typeof payload !== "object") return null;
  const type = (payload as { type?: unknown }).type;
  if (typeof type !== "string" || !type.startsWith("chat.")) return null;
  return payload as ChatEvent;
}

/**
 * The German for a refusal.
 *
 * `ChatConsumer` answers a refused message with an English sentence — the five
 * literals below are the whole set (`_validate_message_content`,
 * `_check_rate_limits`, since S9 the mute check that runs before both, and
 * since S21 the chat-off check before that).
 * They are written for a log and reach the player unchanged, so the
 * translation has to happen at this end.
 *
 * The fallback exists because a fourth refusal would otherwise put an English
 * sentence on a German screen; `"Invalid JSON"` is already one this client
 * should never provoke.
 */
export function chatErrorText(raw: string): string {
  switch (raw) {
    case "Message too long":
      return de.chat.errors.tooLong;
    case "Slow down":
      return de.chat.errors.tooFast;
    case "Chat is moving too fast":
      return de.chat.errors.roomTooFast;
    case "You are muted":
      return de.chat.errors.muted;
    // The host switched the chat off while this socket was open. The same
    // sentence the dock shows when a fresh load finds it off.
    case "Chat is off":
      return de.chat.disabled;
    default:
      return de.chat.errors.unknown;
  }
}

/**
 * What this device is called *in the chat*.
 *
 * Not simply `identity.player.name`: the host does not chat under their seat's
 * name. `resolve_player` hands `ChatConsumer` a `HostPlayer` duck-type whose
 * `name` is `f"{user.username} (Host)"` (`game/ws_auth.py`), and that is the
 * string that ends up on every line the host writes. A screen comparing against
 * the seat name would never recognise the host's own messages.
 *
 * The suffix is duplicated from the backend and there is no way around it — the
 * consumer sends no `player_id` — so it lives here, once, named, and pinned by
 * a test rather than spelled out at a call site.
 */
export function chatDisplayName(identity: {
  kind?: string;
  username?: string;
  player?: { name: string };
}): string | null {
  if (identity.kind === "host") {
    return identity.username ? `${identity.username} (Host)` : null;
  }
  return identity.player?.name ?? null;
}

/**
 * `wss://<host>/ws/chat/<gameId>/`, same origin as the page.
 *
 * Same origin for the same two reasons as the game socket: nginx proxies `/ws`
 * to Daphne in production, and the signed player cookies the consumer
 * authenticates with only ride along on a same-origin socket.
 *
 * The protocol and host are arguments rather than reads of `window` so this
 * stays testable in the node environment the suite runs in.
 */
export function chatSocketUrl(
  gameId: string,
  pageProtocol: string = window.location.protocol,
  host: string = window.location.host,
): string {
  const protocol = pageProtocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/chat/${gameId}/`;
}

export type ChatEventListener = (event: ChatEvent) => void;

export class ChatSocket extends BaseWSClient {
  private listeners: ChatEventListener[] = [];

  constructor(gameId: string) {
    super(chatSocketUrl(gameId));
  }

  protected handleMessage(data: unknown): void {
    const event = asChatEvent(data);
    if (!event) {
      console.warn("Chat socket: frame that is not a chat event, ignored", data);
      return;
    }
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch (err) {
        console.error("Chat event listener failed", err);
      }
    }
  }

  /** Subscribe. Returns the unsubscribe function. */
  onEvent(listener: ChatEventListener): () => void {
    this.listeners.push(listener);
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index >= 0) this.listeners.splice(index, 1);
    };
  }

  /**
   * Send one line. `false` means the socket was not open — the composer keeps
   * the text so nobody loses a sentence to a reconnect.
   */
  sendMessage(text: string): boolean {
    return this.send({ type: "chat.message", message: text });
  }
}
