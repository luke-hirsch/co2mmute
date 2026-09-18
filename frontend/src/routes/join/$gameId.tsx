import { createFileRoute, useParams } from "@tanstack/react-router";

import { JoinForm } from "@/components/join/join-form";

function JoinRoute() {
  const { gameId } = useParams({ from: "/join/$gameId" });
  return <JoinForm gameId={gameId.toUpperCase()} />;
}

export const Route = createFileRoute("/join/$gameId")({
  component: JoinRoute,
});
