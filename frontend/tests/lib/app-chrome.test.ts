import { describe, expect, it } from "vitest";

import { showsAppChrome } from "@/lib/app-chrome";

/**
 * `/app` had no chrome at all: `__root.tsx` was a bare `<Outlet/>`, and `/app/`
 * and `/app/game/` redirect to `/app/join` — as `/app/maps/` did, until S18 gave
 * it a list of its own. A logged-in host
 * who followed any of those — or whose game screen errored, which lands in the
 * same place — was left on the join screen with no way back to the landing page
 * or their profile.
 *
 * The header belongs on those screens and nowhere else. The game screens run
 * the whole viewport and say what they are; the editor is a canvas with its own
 * toolbar. Putting a second header above either would push the thing the screen
 * exists for below the fold on a phone.
 *
 * **S18 moved the map area across.** `/maps` was listed as both full-bleed and
 * redirect-only, which was right while it was a stub throwing a redirect. It is
 * a staff list now and the detail page is a page; only the editor stays bare.
 */
describe("which screens carry the app header", () => {
  it("shows it on the join screens, which is where every redirect lands", () => {
    expect(showsAppChrome("/join")).toBe(true);
    expect(showsAppChrome("/join/")).toBe(true);
    expect(showsAppChrome("/join/ABC123")).toBe(true);
  });

  it("shows it on the seat handover and the styleguide", () => {
    expect(showsAppChrome("/seat")).toBe(true);
    expect(showsAppChrome("/seat/H7K2M9")).toBe(true);
    expect(showsAppChrome("/styleguide")).toBe(true);
  });

  /**
   * `/game/create` sits under a full-bleed prefix and is not a game: it runs
   * before any game exists, and both header links — the landing page and the
   * profile — are what a host who opened it by accident needs.
   */
  it("shows it on the create screen, which is the funnel", () => {
    expect(showsAppChrome("/game/create")).toBe(true);
    expect(showsAppChrome("/game/create/")).toBe(true);
  });

  it("keeps it off a game screen, which is the whole viewport", () => {
    expect(showsAppChrome("/game/ABC123")).toBe(false);
    expect(showsAppChrome("/game/ABC123/")).toBe(false);
  });

  /**
   * The split S18 needs: the editor sits *under* a screen that does carry the
   * header, so a `startsWith("/maps/")` cannot express it. That is why there is
   * a pattern anchored on `/editor` rather than another prefix.
   */
  it("keeps it off the map editor, which has its own toolbar", () => {
    expect(showsAppChrome("/maps/7/editor")).toBe(false);
    expect(showsAppChrome("/maps/7/editor/")).toBe(false);
  });

  it("shows it on the map index and on one map, which are ordinary screens", () => {
    expect(showsAppChrome("/maps")).toBe(true);
    expect(showsAppChrome("/maps/")).toBe(true);
    expect(showsAppChrome("/maps/7")).toBe(true);
    expect(showsAppChrome("/maps/7/")).toBe(true);
  });

  /** A path that only *starts* like the editor is not the editor. */
  it("does not read a deeper path under a map as the editor", () => {
    expect(showsAppChrome("/maps/7/editorial")).toBe(true);
  });

  /**
   * These three only ever redirect, so the header is never seen on them — but
   * it renders for the tick before the redirect resolves, and a header that
   * flashes and vanishes is worse than none.
   */
  it("keeps it off the routes that only redirect", () => {
    expect(showsAppChrome("/")).toBe(false);
    expect(showsAppChrome("/game")).toBe(false);
    expect(showsAppChrome("/game/")).toBe(false);
  });
});
