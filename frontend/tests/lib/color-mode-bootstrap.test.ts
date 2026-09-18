import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { describe, expect, it } from "vitest";

/**
 * The colour-mode bootstrap is an inline <script> in index.html, because it has
 * to run before React mounts or the page paints in the wrong theme for a frame.
 * Being inline means nothing type-checks it and nothing imports it, so it is
 * the one piece of the SPA that can rot silently — and it did: the storage key
 * was declared inside the init IIFE while four functions referenced it as a
 * default parameter. Every existing call site happened to pass the key
 * explicitly, so the bootstrap worked and only `setUserColorMode(mode)` — the
 * call React makes — threw `Can't find variable: COLOR_MODE_STORAGE_KEY`.
 *
 * So this test does not read the file and look for patterns. It runs the script
 * and uses it.
 */
const INDEX_HTML = fileURLToPath(new URL("../../index.html", import.meta.url));

function bootstrap({ prefersDark = false, stored = null as string | null } = {}) {
  const html = readFileSync(INDEX_HTML, "utf8");
  const match = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!match) throw new Error("no inline <script> in index.html");

  const classes = new Set<string>();
  const store = new Map<string, string>();
  if (stored !== null) store.set("colorMode", stored);

  const listeners: Array<(e: { matches: boolean }) => void> = [];
  const context: Record<string, unknown> = {
    console: { warn() {}, log() {} },
    document: {
      documentElement: {
        classList: {
          add: (c: string) => classes.add(c),
          remove: (c: string) => classes.delete(c),
          contains: (c: string) => classes.has(c),
        },
      },
    },
  };
  context.window = {
    localStorage: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    },
    matchMedia: () => ({
      matches: prefersDark,
      addEventListener: (_: string, fn: (e: { matches: boolean }) => void) =>
        listeners.push(fn),
    }),
  };

  vm.runInNewContext(match[1], context);
  return {
    context,
    isDark: () => classes.has("dark"),
    stored: () => store.get("colorMode") ?? null,
    fireSystemChange: (matches: boolean) =>
      listeners.forEach((fn) => fn({ matches })),
  };
}

describe("the colour-mode bootstrap in index.html", () => {
  it("follows the OS when nothing is stored, and records the intent", () => {
    expect(bootstrap({ prefersDark: true }).isDark()).toBe(true);
    const light = bootstrap({ prefersDark: false });
    expect(light.isDark()).toBe(false);
    expect(light.stored()).toBe("system");
  });

  it("lets a stored choice beat the OS", () => {
    expect(bootstrap({ prefersDark: true, stored: "light" }).isDark()).toBe(false);
    expect(bootstrap({ prefersDark: false, stored: "dark" }).isDark()).toBe(true);
  });

  it("switches when called with one argument — this is what React does", () => {
    // The regression. With the storage key out of scope this threw instead of
    // switching, so the styleguide's toggle did nothing at all.
    const app = bootstrap({ prefersDark: true });
    const setUserColorMode = app.context.setUserColorMode as (m: string) => void;

    expect(() => setUserColorMode("light")).not.toThrow();
    expect(app.isDark()).toBe(false);
    expect(app.stored()).toBe("light");

    setUserColorMode("dark");
    expect(app.isDark()).toBe(true);

    setUserColorMode("system");
    expect(app.isDark()).toBe(true); // back to following the OS, which is dark
    expect(app.stored()).toBe("system");
  });

  it("ignores a junk mode rather than storing it", () => {
    const app = bootstrap({ prefersDark: false });
    (app.context.setUserColorMode as (m: string) => void)("chartreuse");
    expect(app.stored()).toBe("system");
    expect(app.isDark()).toBe(false);
  });

  it("follows later OS changes only while the mode is system", () => {
    const onSystem = bootstrap({ prefersDark: false });
    onSystem.fireSystemChange(true);
    expect(onSystem.isDark()).toBe(true);

    const pinned = bootstrap({ prefersDark: false, stored: "light" });
    pinned.fireSystemChange(true);
    expect(pinned.isDark()).toBe(false);
  });

  it("uses the same storage key as the Django half", () => {
    // Both halves are one origin, so a switch on either has to follow on both.
    const djangoJs = readFileSync(
      fileURLToPath(new URL("../../../backend/static/js/head_script.js", import.meta.url)),
      "utf8",
    );
    expect(djangoJs).toMatch(/COLOR_MODE_STORAGE_KEY\s*=\s*"colorMode"/);
    expect(readFileSync(INDEX_HTML, "utf8")).toMatch(
      /COLOR_MODE_STORAGE_KEY\s*=\s*"colorMode"/,
    );
  });
});
