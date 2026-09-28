import { Link } from "@tanstack/react-router";

import { de } from "@/lib/de";
import { useIdentity } from "@/lib/queries/identity";

/**
 * A way out of the SPA, on the screens that are not a game.
 *
 * `/app/`, `/app/game/` and `/app/maps/` all redirect to `/app/join`, and so
 * does `GameFrame` when the snapshot fails — so the join screen is where a host
 * ends up by accident, and it is built for a student with a QR code. Before
 * this there was nothing on it to press: `__root.tsx` was a bare `<Outlet/>`,
 * and the landing page and the profile are Django pages the router cannot reach.
 *
 * The landing page is still a plain `<a href>` — it is a Django template and
 * the router cannot reach it. The host's page **is** reachable since S13
 * (`/accounts/profile/` redirects to `/app/host`), so that one is a router
 * link: going out to Django and back in for a screen that is already loaded is
 * a full reload for nothing. `showsAppChrome` decides where this renders.
 *
 * The profile link only appears for someone who has an account, which in this
 * project means a host: `whoami` answers `authenticated` for a Django session
 * and players never have one. It is deliberately not gated on `kind === "host"`
 * — a researcher logged in as a host while holding a seat in someone else's
 * game is a normal thing here, and they still want their profile.
 */
export function AppHeader() {
  const identity = useIdentity();
  const authenticated = identity.data?.authenticated ?? false;

  return (
    <header className="border-b border-border">
      <nav
        aria-label={de.app.name}
        className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-4 sm:px-6"
      >
        <a
          href="/"
          className="font-mono text-sm tracking-[0.2em] text-brandaccent uppercase transition hover:text-foreground"
        >
          {de.app.name}
        </a>

        {/* Nothing is rendered while identity is in flight: a profile link that
            appears a beat late is fine, one that appears and vanishes is not. */}
        {authenticated ? (
          <Link
            to="/host"
            className="text-sm text-muted-foreground transition hover:text-foreground"
          >
            {identity.data?.username ?? de.app.header.profile}
          </Link>
        ) : (
          <a
            href="/"
            className="text-sm text-muted-foreground transition hover:text-foreground"
          >
            {de.app.header.home}
          </a>
        )}
      </nav>
    </header>
  );
}
