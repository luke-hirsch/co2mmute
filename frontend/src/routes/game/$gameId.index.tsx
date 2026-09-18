import { createFileRoute, useParams } from "@tanstack/react-router";

import GameLayout from "@/components/game/GameLayout";
import { ProtectedLayout } from "@/components/ProtectedLayout";

/**
 * The pre-rewrite game screen, unchanged, moved here so that
 * `/app/game/<ID>` can gain child routes (the new lobby) without touching it.
 *
 * F2/F3 replace this file; until then it is the screen that actually plays a
 * round, so it keeps running exactly as it did.
 */
function GameWrapper() {
  const { gameId } = useParams({ from: "/game/$gameId" });

  return (
    <ProtectedLayout gameId={`${gameId}`} requiredKind={["host", "player"]}>
      <GameLayout />
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/game/$gameId/")({
  component: GameWrapper,
});
