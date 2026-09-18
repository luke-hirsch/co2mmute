/**
 * The context object and its hook, kept apart from the provider component so
 * that the provider file exports only a component — React Fast Refresh gives up
 * on a module that mixes the two, and a game screen losing its socket on every
 * save is a bad way to develop.
 */

import { createContext, useContext } from "react";

import type { Identity } from "@/lib/queries/identity";
import type { GameState } from "@/lib/game/game-state";
import type { WSStatus } from "@/types/wsTypes";

export type GameContextValue = {
  state: GameState;
  /** Socket status, for the connection indicator. */
  connection: WSStatus;
  /** Who this browser is in this game. */
  identity: Identity | undefined;
  /** This browser's seat, or null for the host and for a device with none. */
  seatId: string | null;
  isHost: boolean;
  /** The REST snapshot is still in flight and the socket has said nothing yet. */
  isLoading: boolean;
  /** The snapshot failed — usually a missing or expired game cookie. */
  error: unknown;
  /**
   * Send a message to the game socket. Returns false when the socket is not
   * open, so a control can say so instead of pretending the click worked.
   */
  send: (message: object) => boolean;
  /**
   * The last `{"type": "error"}` the server sent, and a way to clear it. It is
   * a refusal of something this client asked for — voting out of turn, mostly —
   * so it belongs next to the control that caused it, not in the game state.
   */
  lastError: string | null;
  clearError: () => void;
};

export const GameContext = createContext<GameContextValue | null>(null);

export function useGame(): GameContextValue {
  const value = useContext(GameContext);
  if (!value) {
    throw new Error("useGame() outside <GameProvider>");
  }
  return value;
}
