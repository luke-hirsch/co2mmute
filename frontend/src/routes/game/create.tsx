import { createFileRoute } from "@tanstack/react-router";

import { CreateGameScreen } from "@/components/host/create-game-screen";
import { RequireLogin } from "@/components/host/require-login";

/**
 * `/app/game/create` — Spiel anlegen. S13.
 *
 * A static segment beside `game/$gameId`, so the router prefers it over the
 * dynamic one; a game whose id is literally "create" is not reachable and never
 * was (`generate_unique_game_id` makes six upper-case hex characters).
 *
 * `/game/create/` on the Django side redirects here, which is what keeps the
 * landing page, the footer, the profile page and the end-of-game screen
 * pointing at one screen rather than two.
 */
function CreateGameRoute() {
  return (
    <RequireLogin>
      <CreateGameScreen />
    </RequireLogin>
  );
}

export const Route = createFileRoute("/game/create")({
  component: CreateGameRoute,
});
