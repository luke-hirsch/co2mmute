/**
 * One socket per game.
 *
 * The old screens opened four `useGameSocket`s on one page (GamePlay,
 * StatusBar, GameLayout, GameDetail) plus the chat socket, so every event was
 * handled four times by four pieces of state that could disagree. This is the
 * single connection they get replaced by: F1 mounts it once in the lobby hook,
 * F2 lifts the same class into a provider without changing it.
 *
 * Everything hard about the connection — the exponential reconnect, the 30 s
 * heartbeat, and the deliberate one-task delay before `new WebSocket` that
 * keeps WebKit from stalling a fetch issued in the same task — already lives in
 * `BaseWSClient`. This adds only what is specific to the game channel: the URL,
 * and turning a frame into a typed `GameEvent`.
 */

import { asGameEvent, type GameEvent } from "@/lib/game/events";
import { BaseWSClient } from "@/utils/ws";

export type GameEventListener = (event: GameEvent) => void;

/**
 * `wss://<host>/ws/game/<gameId>/`, same origin as the page.
 *
 * Same origin matters twice over: nginx proxies `/ws` to Daphne in production,
 * and the player cookies the consumer authenticates with only ride along on a
 * same-origin socket. In dev, vite's `server.proxy` makes `/ws` reach nginx
 * (`ws: true`), so this URL is correct there too.
 */
export function gameSocketUrl(gameId: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/game/${gameId}/`;
}

export class GameSocket extends BaseWSClient {
  private listeners: GameEventListener[] = [];

  constructor(gameId: string) {
    super(gameSocketUrl(gameId));
  }

  protected handleMessage(data: unknown): void {
    // `ping`/`pong` never reach here — BaseWSClient answers them itself, which
    // is also what renews this seat's presence key on the server.
    const event = asGameEvent(data);
    if (!event) {
      console.warn("Game socket: frame without a type, ignored", data);
      return;
    }
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch (err) {
        // One screen throwing must not stop the others from seeing the event,
        // and must not take the socket down with it.
        console.error("Game event listener failed", err);
      }
    }
  }

  /** Subscribe. Returns the unsubscribe function. */
  onEvent(listener: GameEventListener): () => void {
    this.listeners.push(listener);
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index >= 0) this.listeners.splice(index, 1);
    };
  }
}
