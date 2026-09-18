/**
 * Snapshot + socket + reducer, wired together once.
 *
 * This is the whole of Roadmap.md 2.2 at lobby size. Three rules, and every
 * screen from F2 on inherits them:
 *
 * 1. The REST snapshot is read once and never refetched.
 * 2. The socket is the only thing that updates state afterwards.
 * 3. No event handler calls back into the query layer.
 *
 * The old screens broke all three at the same time and the result was blamed on
 * React. jac's `use-run-lifecycle` is the shape being copied.
 */

import { useEffect, useReducer, useState } from "react";

import { useLobbySnapshot } from "@/lib/queries/join";
import {
  initialLobbyState,
  lobbyReducer,
  type LobbyState,
} from "@/lib/game/lobby-state";
import { GameSocket } from "@/lib/game/socket";
import type { WSStatus } from "@/types/wsTypes";

export type LobbyChannel = {
  state: LobbyState;
  /** Socket status, for the connection indicator. */
  connection: WSStatus;
  /** The snapshot is still in flight and no socket state has arrived yet. */
  isLoading: boolean;
  /** The snapshot failed — usually a missing or expired game cookie. */
  error: unknown;
};

export function useLobbyChannel(gameId: string): LobbyChannel {
  const snapshot = useLobbySnapshot(gameId);
  const [state, dispatch] = useReducer(
    lobbyReducer,
    gameId,
    initialLobbyState,
  );
  const [connection, setConnection] = useState<WSStatus>("idle");

  useEffect(() => {
    if (snapshot.data) {
      dispatch({ kind: "snapshot", snapshot: snapshot.data });
    }
  }, [snapshot.data]);

  useEffect(() => {
    if (!gameId) return;

    const socket = new GameSocket(gameId);
    const offEvent = socket.onEvent((event) =>
      dispatch({ kind: "event", event }),
    );
    const offStatus = socket.onStatusChange(setConnection);

    // connect() rejects when the server refuses the socket — no cookie, or a
    // seat that is not ours. The screen reads that from `connection` and from
    // `state.revoked`; an unhandled rejection here would only be noise.
    void socket.connect().catch(() => undefined);

    return () => {
      offEvent();
      offStatus();
      socket.disconnect();
    };
  }, [gameId]);

  return {
    state,
    connection,
    isLoading: snapshot.isLoading && state.seats.length === 0,
    error: snapshot.error,
  };
}
