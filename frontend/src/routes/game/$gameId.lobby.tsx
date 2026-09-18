import { createFileRoute, useParams } from "@tanstack/react-router";

import { LobbyScreen } from "@/components/lobby/lobby-screen";

function LobbyRoute() {
  const { gameId } = useParams({ from: "/game/$gameId/lobby" });
  return <LobbyScreen gameId={gameId.toUpperCase()} />;
}

export const Route = createFileRoute("/game/$gameId/lobby")({
  component: LobbyRoute,
});
