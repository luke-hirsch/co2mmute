import { Outlet, createRootRoute, useRouterState } from "@tanstack/react-router";

import { AppHeader } from "@/components/layout/app-header";
import { showsAppChrome } from "@/lib/app-chrome";

/**
 * The SPA had no chrome at all — this was a bare `<Outlet/>`.
 *
 * It matters because of where the router's redirects go: `/app/`, `/app/game/`
 * and `/app/maps/` all land on `/app/join`, and `GameFrame` sends a failed
 * snapshot to the same place. A host who followed any of them sat on a screen
 * built for a student with a QR code, with no link back to the landing page or
 * their profile — both Django pages, so the router could not offer them.
 *
 * The header is not on every screen: `showsAppChrome` keeps it off the game
 * screens and the map editor, which own their whole viewport, and off the three
 * routes that only redirect.
 */
export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  return (
    <>
      {showsAppChrome(pathname) ? <AppHeader /> : null}
      <Outlet />
    </>
  );
}
