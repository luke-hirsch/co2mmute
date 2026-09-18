import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * `/app/maps/` has no list of its own — the map list is a Django page
 * (`/map/list/`). This route only ever bounced elsewhere; it keeps doing that,
 * now without leaving the router. F7 gives the editor a real index.
 */
export const Route = createFileRoute("/maps/")({
  beforeLoad: () => {
    throw redirect({ to: "/join" });
  },
});
