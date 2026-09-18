import { createFileRoute } from "@tanstack/react-router";

import { LobbyScreen } from "@/components/lobby/lobby-screen";

/** The game id comes from the provider in the layout, not from the params. */
export const Route = createFileRoute("/game/$gameId/lobby")({
  component: LobbyScreen,
});
