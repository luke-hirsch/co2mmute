/**
 * Which screens under `/app/` get a header and a footer.
 *
 * `__root.tsx` was a bare `<Outlet/>`, so the SPA had no chrome anywhere. That
 * only mattered once you noticed where its redirects go: `/app/`, `/app/game/`
 * and `/app/maps/` all bounced to `/app/join`, and so does `GameFrame` when the
 * snapshot fails. A host who followed any of them was parked on the join screen
 * — a screen built for a student with a QR code — with no link back to the
 * landing page or their own profile, and nothing on it to press.
 *
 * So: a header on those screens, and on nothing else. Since S20 the footer
 * follows the same rule — it carries the legal links, which a game screen
 * still lacks (`docs/testfaelle.md` S-06).
 *
 * **S18 moved the map area onto the chrome side.** `/maps` was listed as both
 * full-bleed and redirect-only, which was true while it was a stub that threw a
 * redirect and a detail page that ran its own layout. It is an ordinary staff
 * screen now — a list, and a page with a graph on it — and the way back to the
 * landing page is exactly what it wants. The **editor** stays bare, because it
 * is a canvas with its own toolbar, and it is named by a pattern rather than a
 * prefix so that `/maps/7` keeps its header while `/maps/7/editor` loses it.
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
const FULL_BLEED = ["/game"];

/**
 * The same, for a screen a prefix cannot name: the editor sits *under* a screen
 * that does carry the header, so `/maps/7` and `/maps/7/editor` have to split.
 * Anchored at both ends rather than a `startsWith`, which is the kind of guess
 * that quietly starts matching `/maps/7/editorial` one day.
 */
const FULL_BLEED_PATTERNS = [/^\/maps\/[^/]+\/editor\/?$/];

/** Routes whose only job is to redirect somewhere else. */
const REDIRECT_ONLY = ["/", "/game", "/game/"];

/**
 * Screens that sit under a full-bleed prefix but are not that screen.
 *
 * `/game/create` is the funnel, not a game: it is where `/game/create/` sends a
 * logged-in host, it runs before any game exists, and the header's way back to
 * the landing page and the profile is exactly what somebody who opened it by
 * accident needs. Listed rather than reasoned about, because "is this path a
 * game id" is the kind of guess that starts matching the wrong thing.
 */
const CHROME_ANYWAY = ["/game/create"];

export function showsAppChrome(pathname: string): boolean {
  if (CHROME_ANYWAY.includes(pathname.replace(/\/$/, ""))) return true;
  if (REDIRECT_ONLY.includes(pathname)) return false;

  if (FULL_BLEED_PATTERNS.some((pattern) => pattern.test(pathname))) return false;

  // A trailing slash is the same screen, and so is a deeper path under it.
  return !FULL_BLEED.some((prefix) => pathname.startsWith(`${prefix}/`));
}
