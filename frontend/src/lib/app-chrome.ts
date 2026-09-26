/**
 * Which screens under `/app/` get a header.
 *
 * `__root.tsx` was a bare `<Outlet/>`, so the SPA had no chrome anywhere. That
 * only mattered once you noticed where its redirects go: `/app/`, `/app/game/`
 * and `/app/maps/` all bounce to `/app/join`, and so does `GameFrame` when the
 * snapshot fails. A host who followed any of them was parked on the join screen
 * — a screen built for a student with a QR code — with no link back to the
 * landing page or their own profile, and nothing on it to press.
 *
 * So: a header on those screens, and on nothing else.
 *
 * - **Not on a game screen.** It runs the whole viewport, it already says which
 *   game it is, and a second bar above it would push the round below the fold
 *   on a phone.
 * - **Not on the map editor.** A canvas with its own toolbar.
 * - **Not on the three redirect-only routes.** Nothing is ever *seen* there, but
 *   the component renders for the tick before the redirect resolves, and a
 *   header that flashes and disappears reads as a bug.
 *
 * Pure and separate from the component so it can be tested: the alternative is
 * a `pathname.startsWith` inline in `__root.tsx`, which is exactly the kind of
 * thing that silently starts matching `/gameover` one day.
 *
 * The argument is the path *inside* the SPA — the router is mounted with
 * `basepath: "/app"` and strips it. Nothing here compensates for that; if an
 * `/app/`-prefixed path ever arrives, the header disappearing is the signal.
 */

/** Screens that own their whole viewport. */
const FULL_BLEED = ["/game", "/maps"];

/** Routes whose only job is to redirect somewhere else. */
const REDIRECT_ONLY = ["/", "/game", "/game/", "/maps", "/maps/"];

export function showsAppChrome(pathname: string): boolean {
  if (REDIRECT_ONLY.includes(pathname)) return false;

  // A trailing slash is the same screen, and so is a deeper path under it.
  return !FULL_BLEED.some((prefix) => pathname.startsWith(`${prefix}/`));
}
