import { Outlet, createRootRoute, useRouterState } from "@tanstack/react-router";

import { AppFooter } from "@/components/layout/app-footer";
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
 * Header and footer are not on every screen: `showsAppChrome` keeps them off
 * the game screens and the map editor, which own their whole viewport, and off
 * the three routes that only redirect.
 *
 * The wrapper is there either way so the `Outlet` never changes position in the
 * tree — moving it would remount the screen. Without chrome it is `contents`
 * and draws no box; with chrome it is the column that pushes the footer to the
 * bottom of a short page, and `data-chrome` is what tells `Screen` to fill that
 * column rather than a whole viewport of its own.
 */
export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const chrome = showsAppChrome(pathname);

  return (
    <div
      data-chrome={chrome ? "" : undefined}
      className={chrome ? "flex min-h-dvh flex-col bg-background" : "contents"}
    >
      {chrome ? <AppHeader /> : null}
      <Outlet />
      {chrome ? <AppFooter /> : null}
    </div>
  );
}
