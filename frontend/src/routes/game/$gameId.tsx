import { Outlet, createFileRoute, useParams } from "@tanstack/react-router";

import { GameFrame } from "@/components/game/game-frame";
import { GameProvider } from "@/components/game/game-provider";

/**
 * Layout for everything under `/app/game/<ID>`.
 *
 * This is where Roadmap.md 2.2 actually lands: one `GameProvider` — one socket,
 * one reducer, one source of truth — above every screen in the game, instead of
 * four components each opening their own connection to the same channel.
 *
 * `GameFrame` sits inside it so that pause, a revoked seat and a dropped socket
 * are handled once for everything below. That includes the legacy screen at
 * `$gameId.index.tsx`, which keeps running until F3 replaces it — it still
 * opens its own sockets, so for one chunk there are more connections rather
 * than fewer. The trade is deliberate: the game stays playable in every single
 * branch, and no chunk is a "works with the next one".
 */
function GameRoute() {
  const { gameId } = useParams({ from: "/game/$gameId" });
  const id = gameId.toUpperCase();

  return (
    <GameProvider gameId={id}>
      <GameFrame>
        <Outlet />
      </GameFrame>
    </GameProvider>
  );
}

export const Route = createFileRoute("/game/$gameId")({
  component: GameRoute,
});
