import { createFileRoute, useParams } from "@tanstack/react-router";
import { ProtectedLayout } from "../../components/ProtectedLayout";
import GameRoute from "../../components/game/GameRoute";

function GameWrapper() {
  const { gameId } = useParams({ from: "/game/$gameId" });
  return (
    <ProtectedLayout gameId={gameId}>
      <GameRoute />
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/game/$gameId")({
  component: GameWrapper,
});
