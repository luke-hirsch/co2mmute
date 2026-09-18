import { createFileRoute, useParams } from "@tanstack/react-router";

import GameLayout from "@/components/game/GameLayout";
import { LobbyScreen } from "@/components/lobby/lobby-screen";
import { ProtectedLayout } from "@/components/ProtectedLayout";
import { RoundScreen } from "@/components/round/round-screen";
import { useGame } from "@/components/game/game-context";
import { currentScreen } from "@/lib/game/game-state";

/**
 * One route per game. Which screen runs is the game's decision, not the URL's.
 *
 * `currentScreen()` reads revocation, the end, the between-round phase and the
 * round number out of the same reducer as everything else. Before this there
 * were two URLs and a button ("Zum Spiel") that somebody had to press — and
 * whoever did not press it sat in a lobby for a game already in progress.
 *
 * `between-rounds` and `ended` still go to the pre-rewrite `GameLayout` until
 * F5 and F6 replace them. That screen brings its own sockets; pause, a revoked
 * seat and a dropped connection are still handled once above, in `GameFrame`,
 * for it as well.
 */
function GameScreenRouter() {
  const { state } = useGame();

  switch (currentScreen(state)) {
    case "lobby":
      return <LobbyScreen />;
    case "playing":
      return <RoundScreen />;
    case "between-rounds":
    case "ended":
      return <LegacyGameScreen />;
    case "revoked":
      // GameFrame renders the notice and never gets here.
      return null;
  }
}

/**
 * The pre-rewrite screen, for the phases that do not have a replacement yet.
 *
 * Kept in this one file so that deleting it in F5 is a single edit rather than
 * a hunt: it, `GamePlay.tsx`, `Game.tsx`, `GameDetail.tsx`, `StatusBar.tsx` and
 * `GameLayout.tsx` go together, and with them the last four `useGameSocket`
 * calls.
 */
function LegacyGameScreen() {
  const { gameId } = useParams({ from: "/game/$gameId" });

  return (
    <ProtectedLayout gameId={`${gameId}`} requiredKind={["host", "player"]}>
      <GameLayout />
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/game/$gameId/")({
  component: GameScreenRouter,
});
