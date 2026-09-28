/**
 * The transcript, as a pure reducer.
 *
 * Pure: no React, no socket, no `window`. `use-chat.ts` hangs the connection
 * off it, exactly as `game-provider.tsx` does for `game-state.ts`.
 *
 * One source of truth per field, the same rule as the game state: the socket
 * owns the transcript and nothing else writes to it. There is no REST endpoint
 * for chat history to race with — `ChatConsumer` sends the whole stored history
 * on connect — so the resync question that `lobby-state.ts` has to answer with
 * a `hasLiveRoster` flag does not arise here.
 *
 * Whether a line is the reader's own is **not** state. It is a display
 * question, answered at render from `whoami`, and it is only ever a nicety:
 * `Player.name` is not unique within a game, so two students called Max would
 * each see both lines as theirs. Harmless, because nothing is authorised by it
 * and the name prints on every line either way.
 */

import {
  CHAT_TRANSCRIPT_LIMIT,
  type ChatEvent,
  type ChatMessage,
} from "@/lib/game/chat";

export type ChatLine =
  | { kind: "message"; ts: number; playerName: string; text: string }
  /**
   * A join notice (`game/signals.py` → `send_chat_system_message`). No name and
   * no timestamp, because the consumer sends neither — inventing a client clock
   * for it would put two different clocks in one column.
   */
  | { kind: "system"; text: string };

export type ChatState = {
  lines: ChatLine[];
  /**
   * The last refusal, for the composer. Transient and this client's own — it
   * never joins the transcript, or one student's rate limit would be read by
   * the whole class.
   */
  error: string | null;
};

export type ChatAction =
  | { kind: "event"; event: ChatEvent }
  | { kind: "dismiss-error" }
  /** The host switched the chat off; `clear_chat_on_toggle` wiped the server side. */
  | { kind: "reset" };

export function initialChatState(): ChatState {
  return { lines: [], error: null };
}

function messageLine(message: ChatMessage): ChatLine {
  return {
    kind: "message",
    ts: message.ts,
    playerName: message.playerName,
    text: message.message,
  };
}

/** Keep the newest `CHAT_TRANSCRIPT_LIMIT` lines. */
function bounded(lines: ChatLine[]): ChatLine[] {
  return lines.length <= CHAT_TRANSCRIPT_LIMIT
    ? lines
    : lines.slice(lines.length - CHAT_TRANSCRIPT_LIMIT);
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.kind) {
    case "reset":
      return initialChatState();

    case "dismiss-error":
      return state.error === null ? state : { ...state, error: null };

    case "event":
      return applyEvent(state, action.event);
  }
}

function applyEvent(state: ChatState, event: ChatEvent): ChatState {
  switch (event.type) {
    /**
     * Replaces, never appends.
     *
     * `ChatConsumer.connect()` sends the whole stored history on *every*
     * connect, and a phone on school wifi reconnects several times a lesson —
     * appending would print the conversation twice, then three times. The cost
     * is that the local system lines go with it, which is the honest outcome:
     * they are not stored in Redis, so after this the screen shows exactly what
     * the server can vouch for.
     */
    case "chat.history":
      return { lines: bounded(event.messages.map(messageLine)), error: null };

    case "chat.message":
      return {
        lines: bounded([...state.lines, messageLine(event.message)]),
        // A message that landed means the socket is answering again, so an
        // older refusal has stopped being true.
        error: null,
      };

    case "chat.system":
      return {
        lines: bounded([...state.lines, { kind: "system", text: event.message }]),
        error: state.error,
      };

    case "chat.error":
      return { ...state, error: event.error };
  }
}
