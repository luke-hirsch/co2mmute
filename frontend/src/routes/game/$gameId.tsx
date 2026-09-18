import { Outlet, createFileRoute } from "@tanstack/react-router";

/**
 * Layout for everything under `/app/game/<ID>`.
 *
 * A pass-through for now. It exists so the new lobby can live at
 * `/game/$gameId/lobby` beside the legacy screen at `/game/$gameId/`, which is
 * the shape F2 needs anyway: the `GameProvider` — one socket, one reducer, one
 * source of truth for the whole game — goes here, and every screen below it
 * becomes a phase rather than a route with its own connection.
 */
export const Route = createFileRoute("/game/$gameId")({
  component: () => <Outlet />,
});
