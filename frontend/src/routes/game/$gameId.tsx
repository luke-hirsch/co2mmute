import GameLayout from "../../components/game/GameLayout";
import { ProtectedLayout } from "../../components/ProtectedLayout";
import { createFileRoute, useParams } from "@tanstack/react-router";

function GameWrapper() {
  const { gameId } = useParams({ from: "/game/$gameId" });

  return (
    <ProtectedLayout gameId={`${gameId}`} requiredKind={["host", "player"]}>
      <GameLayout />
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/game/$gameId")({
  component: GameWrapper,
});
