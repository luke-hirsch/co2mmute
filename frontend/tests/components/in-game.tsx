/**
 * A component rendered to markup inside a game, the way the screens mount it:
 * a game context with the state the test hands it, and a query client for the
 * hooks that read the seat or the game row. Nothing fetches — markup is
 * rendered once, without effects.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  GameContext,
  type GameContextValue,
} from "@/components/game/game-context";
import { initialGameState, type GameState } from "@/lib/game/game-state";

export function renderInGame(
  node: ReactNode,
  state: Partial<GameState> = {},
): string {
  const value: GameContextValue = {
    state: { ...initialGameState("ABC123"), ...state },
    connection: "open",
    identity: undefined,
    seatId: null,
    isHost: false,
    isLoading: false,
    error: null,
    send: () => true,
    lastError: null,
    clearError: () => {},
  };
  return renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <GameContext.Provider value={value}>{node}</GameContext.Provider>
    </QueryClientProvider>,
  );
}
