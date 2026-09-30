import { describe, expect, it } from "vitest";

import { placeBelow, routerPath } from "@/lib/nav-href";

describe("routerPath", () => {
  it("turns an href under /app/ into the path inside the router", () => {
    expect(routerPath("/app/maps")).toBe("/maps");
    expect(routerPath("/app/maps/upload")).toBe("/maps/upload");
    expect(routerPath("/app/game/create")).toBe("/game/create");
    expect(routerPath("/app/host")).toBe("/host");
    // The header's "Beitreten" since S22, when Django's /join/ was deleted.
    expect(routerPath("/app/join")).toBe("/join");
  });

  it("maps the app's own root to the router's", () => {
    expect(routerPath("/app")).toBe("/");
    expect(routerPath("/app/")).toBe("/");
  });

  it("leaves Django pages and other sites to the browser", () => {
    expect(routerPath("/legal/impressum/")).toBeNull();
    expect(routerPath("/hintergrund/")).toBeNull();
    expect(routerPath("/accounts/logout/")).toBeNull();
    expect(routerPath("https://github.com/luke-hirsch/co2mmute")).toBeNull();
  });

  it("is not fooled by a Django path that merely starts with the letters", () => {
    // nginx serves the touch icon from Django's static files at the root.
    expect(routerPath("/apple-touch-icon.png")).toBeNull();
    expect(routerPath("/application/")).toBeNull();
  });
});

describe("placeBelow", () => {
  const anchor = { left: 500, width: 100, bottom: 60 };

  it("hangs the panel under the middle of its button", () => {
    expect(placeBelow(anchor, 224, 1440)).toEqual({ top: 72, left: 438 });
  });

  it("keeps it inside the right edge of a narrow window", () => {
    expect(placeBelow({ left: 1000, width: 80, bottom: 60 }, 224, 1100)).toEqual({
      top: 72,
      left: 1100 - 224 - 16,
    });
  });

  it("keeps it inside the left edge too", () => {
    expect(placeBelow({ left: 0, width: 40, bottom: 60 }, 224, 1440).left).toBe(16);
  });
});
