import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ChatSocket, chatErrorText } from "@/lib/game/chat";
import { chatReducer, initialChatState } from "@/lib/game/chat-state";
import type { WSStatus } from "@/types/wsTypes";

/**
 * The chat socket, opened once for a game.
 *
 * Deliberately a second socket rather than another channel on `ws/game/`: that
 * is how the backend is built (`ChatConsumer` and `GameConsumer` are separate
 * consumers at separate URLs), and the two have genuinely different lifetimes —
 * the chat can be switched off without the game losing its connection.
 *
 * "One socket per game, not one per component" still holds: this hook is called
 * from `ChatDock`, which `GameFrame` mounts exactly once for the whole game.
 * Calling it from a second component would open a second connection and show
 * the history twice.
 *
 * No `refetchInterval` and nothing to refetch — there is no REST endpoint for
 * chat history at all. `ChatConsumer` sends the stored history on every
 * connect, so a reconnect is the resync, exactly as `game.state` is for the
 * game socket.
 */
export function useChat({
  gameId,
  enabled,
}: {
  gameId: string;
  /** `chat_enabled` from the lobby snapshot. False means no socket at all. */
  enabled: boolean;
}) {
  const [state, dispatch] = useReducer(chatReducer, undefined, initialChatState);
  const [socketStatus, setSocketStatus] = useState<WSStatus>("idle");
  const socketRef = useRef<ChatSocket | null>(null);

  // Derived, not stored. With the chat off there is no socket, so its last
  // status is not a fact about anything — writing "idle" into state from inside
  // the effect below would be state chasing state.
  const connection: WSStatus = enabled ? socketStatus : "idle";

  useEffect(() => {
    if (!gameId || !enabled) {
      // Switched off means the server has already wiped the Redis list
      // (`clear_chat_on_toggle`), so leaving the transcript on screen would
      // show a conversation that no longer exists anywhere.
      dispatch({ kind: "reset" });
      return;
    }

    const socket = new ChatSocket(gameId);
    socketRef.current = socket;

    const offEvent = socket.onEvent((event) => dispatch({ kind: "event", event }));
    const offStatus = socket.onStatusChange(setSocketStatus);

    // A refused chat socket (no cookie, a revoked seat, an ended game) rejects
    // here. The dock reads that from `connection`; an unhandled rejection would
    // only add noise, and the game socket is already telling the screen why.
    void socket.connect().catch(() => undefined);

    return () => {
      offEvent();
      offStatus();
      socket.disconnect();
      socketRef.current = null;
    };
  }, [gameId, enabled]);

  /**
   * Send one line. `false` means it did not go — the composer keeps the text.
   *
   * The message is not echoed locally. It comes back through `chat.broadcast`
   * like everybody else's, which keeps one source of truth for the transcript
   * and means what is on screen is what the server actually stored. The round
   * trip is a few milliseconds on a LAN and the alternative is a line that
   * appears, then has to be reconciled or removed when the server refuses it.
   */
  const send = useCallback((text: string): boolean => {
    const trimmed = text.trim();
    if (!trimmed) return false;
    return socketRef.current?.sendMessage(trimmed) ?? false;
  }, []);

  const dismissError = useCallback(() => dispatch({ kind: "dismiss-error" }), []);

  return {
    lines: state.lines,
    /** Already German — `chatErrorText` translates the consumer's English. */
    error: state.error === null ? null : chatErrorText(state.error),
    connection,
    isConnected: connection === "open",
    send,
    dismissError,
  };
}
