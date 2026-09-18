import { createFileRoute } from "@tanstack/react-router";

import { BetweenScreen } from "@/components/between/between-screen";
import { EndScreen } from "@/components/summary/end-screen";
import { HostBetweenScreen } from "@/components/host/host-between-screen";
import { HostDeskScreen } from "@/components/host/host-desk-screen";
import { HostLobbyScreen } from "@/components/host/host-lobby-screen";
import { LobbyScreen } from "@/components/lobby/lobby-screen";
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
 * **The host takes a different branch** (F4). Not a different route: the game is
 * in the same state for everyone, and the host is simply not playing it — they
 * run it. So each screen has two versions and `isHost` from `whoami` picks. That
 * flag is only trustworthy once identity has resolved, which is why
 * `GameProvider` counts it as loading; otherwise a host would see the player's
 * lobby flash first.
 *
 * With F5 every branch is a rewritten screen and the pre-rewrite tree is gone —
 * `GameLayout`, `GamePlay`, `GameDetail`, `StatusBar`, `Game`, `PlayerDetail`
 * and `GameSummary`, and with them the last four `useGameSocket` calls, the
 * three 2 s polls and the `refetchRef`. This file is where it was kept alive on
 * purpose since F3, so deleting it was the single edit it was meant to be.
 */
function GameScreenRouter() {
  const { state, seatId, isHost } = useGame();

  switch (currentScreen(state)) {
    case "lobby":
      return isHost ? <HostLobbyScreen /> : <LobbyScreen />;
    case "playing":
      return isHost ? <HostDeskScreen /> : <RoundScreen seatId={seatId} />;
    case "between-rounds":
      return isHost ? <HostBetweenScreen /> : <BetweenScreen />;
    case "ended":
      // The same for both: the game is over and nobody is running it any more.
      // F6 turns this into the full summary.
      return <EndScreen />;
    case "revoked":
      // GameFrame renders the notice and never gets here.
      return null;
  }
}

export const Route = createFileRoute("/game/$gameId/")({
  component: GameScreenRouter,
});
