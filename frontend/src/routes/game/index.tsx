import { createFileRoute, redirect } from "@tanstack/react-router";

/** `/app/game/` without an id is not a screen. Ask for the id instead. */
export const Route = createFileRoute("/game/")({
  beforeLoad: () => {
    throw redirect({ to: "/join" });
  },
});
