import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { GameContext, type GameContextValue } from "@/components/game/game-context";
import {
  gameReducer,
  initialGameState,
} from "@/lib/game/game-state";
import { GameSocket } from "@/lib/game/socket";
import { useIdentity } from "@/lib/queries/identity";
import { useLobbySnapshot } from "@/lib/queries/join";
import type { WSStatus } from "@/types/wsTypes";

/**
 * One socket and one reducer for a whole game.
 *
 * Mounted in the `/app/game/<ID>` layout, so every screen underneath — lobby,
 * the round, the between-round phases, the summary — reads the same state and
 * none of them opens a connection of its own. That is the fix for the four
 * `useGameSocket` calls the old screen had on one page, each with its own copy
 * of the same state and its own 2 s poll on top.
 *
 * Three things this deliberately does not do:
 *
 * - **No `refetchInterval`.** The snapshot is read once (`staleTime: Infinity`).
 * - **No `refetch()` from an event.** `game.state` arrives on every connect, so
 *   a reconnect already resyncs everything; refetching would be a second, worse
 *   answer to a question already answered.
 * - **No socket in the same task as the first REST call.** `BaseWSClient`
 *   defers `new WebSocket` by one task because WebKit otherwise stalls a fetch
 *   issued alongside it — that was the Safari lobby hang. Do not "optimise" it.
 */
export function GameProvider({
  gameId,
  children,
}: {
  gameId: string;
  children: ReactNode;
}) {
  const snapshot = useLobbySnapshot(gameId);
  const identity = useIdentity(gameId);
  const [state, dispatch] = useReducer(gameReducer, gameId, initialGameState);
  const [connection, setConnection] = useState<WSStatus>("idle");
  const [lastError, setLastError] = useState<string | null>(null);
  const socketRef = useRef<GameSocket | null>(null);

  useEffect(() => {
    if (snapshot.data) {
      dispatch({ kind: "snapshot", snapshot: snapshot.data });
    }
  }, [snapshot.data]);

  useEffect(() => {
    if (!gameId) return;

    const socket = new GameSocket(gameId);
    socketRef.current = socket;

    const offEvent = socket.onEvent((event) => {
      // Server-side refusals are surfaced next to the control that caused them
      // rather than stored in the game state, which describes the game rather
      // than this client's last mistake.
      if (event.type === "error") {
        setLastError(event.message);
        return;
      }
      dispatch({ kind: "event", event });
    });
    const offStatus = socket.onStatusChange(setConnection);

    // A refused socket (no cookie, or a seat that is no longer ours) rejects
    // here. The screens read that from `connection` and from `state.revoked`;
    // an unhandled rejection would only add noise.
    void socket.connect().catch(() => undefined);

    return () => {
      offEvent();
      offStatus();
      socket.disconnect();
      socketRef.current = null;
    };
  }, [gameId]);

  const send = useCallback((message: object) => {
    return socketRef.current?.send(message) ?? false;
  }, []);

  const clearError = useCallback(() => setLastError(null), []);

  const value = useMemo<GameContextValue>(
    () => ({
      state,
      connection,
      identity: identity.data,
      seatId: identity.data?.player?.playerId ?? null,
      isHost: identity.data?.kind === "host",
      isLoading: snapshot.isLoading && !state.socketSpoke,
      error: snapshot.error,
      send,
      lastError,
      clearError,
    }),
    [
      state,
      connection,
      identity.data,
      snapshot.isLoading,
      snapshot.error,
      send,
      lastError,
      clearError,
    ],
  );

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
}
