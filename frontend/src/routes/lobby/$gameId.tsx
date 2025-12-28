import { createFileRoute } from "@tanstack/react-router";
import { useParams } from "@tanstack/react-router";
import { ProtectedLayout } from "../../components/ProtectedLayout";
import LobbyRoute from "../../components/lobby/LobbyRoute";

function LobbyWrapper() {
  const { gameId } = useParams({ from: "/lobby/$gameId" });
  return (
    <ProtectedLayout gameId={gameId}>
      <LobbyRoute />
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/lobby/$gameId")({
  component: LobbyWrapper,
});
