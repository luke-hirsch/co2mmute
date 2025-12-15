import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/game/$gameId")({
  component: LobbyRoute,
});

function LobbyRoute() {
  // const { gameId } = Route.useParams();

  return (
    <>
      <div className="flex min-h-full flex-col"></div>
    </>
  );
}
