import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * The palette is two colours and ink. This is what finds the screen that forgot.
 *
 * ### Why it exists
 *
 * S10 counted the off-palette classes per component directory and got `map/`
 * 118, `map/editor/` 102 and **zero** everywhere else — eleven months of design
 * work on the game screens, and a staff area nobody had looked at painting
 * indigo, emerald, red, green, blue, violet, orange and eight PT-line hues. S18
 * brought it onto the design system. Nothing stops it going back.
 *
 * The shape is `tokens.test.ts`'s and `german.test.ts`'s: read the source, name
 * the drifting file. A rendered check would need a map, a router and a query
 * client, and the class is in the file either way.
 *
 * **Scoped to all of `src/`, not to the map area.** That is the lesson S17 wrote
 * down: `english_in` covered two of nine German pages for months and `/map/upload/`
 * was English behind a green suite. A detector scoped to the screens that
 * prompted it is the failure mode these exist to prevent — so this one reads
 * every `.tsx` and `.ts` under `src/`, and a screen added tomorrow is covered
 * without anybody remembering to add it.
 */
const SRC = fileURLToPath(new URL("../../src", import.meta.url));

/**
 * Tailwind's stock palettes. None of them is in this design: the tokens are
 * `primary`, `brandaccent`, the neutrals and the four `line-*` values, and
 * shadcn's semantic names are `var()`s into those.
 *
 * `white` and `black` are in here too. They are not theme-aware — `bg-white` is
 * a hole in dark mode — so the two places that genuinely want paper-white are
 * listed below instead.
 */
const STOCK_PALETTES = [
  "slate",
  "gray",
  "zinc",
  "neutral",
  "stone",
  "red",
  "orange",
  "amber",
  "yellow",
  "lime",
  "green",
  "emerald",
  "teal",
  "cyan",
  "sky",
  "blue",
  "indigo",
  "violet",
  "purple",
  "fuchsia",
  "pink",
  "rose",
];

/**
 * A colour utility: an optional variant chain, a property prefix, the palette
 * and its step, with an optional opacity. `border-amber-300`,
 * `dark:bg-red-900/40`, `hover:text-indigo-800`, `accent-indigo-600`.
 *
 * `text-white`, `bg-black` and friends carry no step, so they are a second arm.
 */
const COLOUR_PROPS =
  "bg|text|border|ring|outline|divide|from|via|to|fill|stroke|shadow|accent|caret|decoration|placeholder";

const OFF_PALETTE = new RegExp(
  `\\b(?:[a-z-]+:)*(?:${COLOUR_PROPS})-(?:(?:${STOCK_PALETTES.join("|")})-\\d{2,3}|white|black)(?:/\\d{1,3})?\\b`,
  "g",
);

/** A hex colour. Every paint in a component has to be a token that can flip. */
const RAW_HEX = /#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b/g;

/**
 * The three files where `white` and `black` are the right answer, class by class.
 *
 * Two reasons, both about something that is **not theme-aware on purpose**:
 *
 * - **A QR code has to stay black on white to scan.** A phone camera reading a
 *   projector from the back of a room is not the moment to be clever about
 *   theming, so the code sits on a paper-white plate in both themes.
 * - **The departure board is a dark panel in both themes.** It is the amber-on-
 *   black signage from the landing page, so its hairlines and its caption are
 *   white-on-dark by construction, not by forgetting.
 *
 * Listed class by class rather than file by file, so a genuine slip in one of
 * these three files is still caught.
 */
const ALLOWED: Record<string, string[]> = {
  "components/host/seat-code-panel.tsx": ["bg-white", "text-white/50"],
  "components/host/host-lobby-screen.tsx": ["bg-white"],
  "components/metro/departure-board.tsx": [
    "dark:bg-black",
    "border-white/10",
    "border-white/15",
    "bg-white/5",
    "text-white/50",
  ],
};

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return sources(path);
    return path.endsWith(".tsx") || path.endsWith(".ts") ? [path] : [];
  });
}

/**
 * Comments are not paint.
 *
 * They matter here more than usual: half of S18's files carry a note saying
 * which hex they used to be, because "it was `bg-indigo-600`" is the only way a
 * reader a year from now can tell a deliberate choice from a leftover. Stripping
 * them is what lets those notes exist.
 */
function code(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
}

describe("the SPA paints from the design system", () => {
  // `src/components/ui/` is shadcn's, and every colour in it is already a
  // semantic token pointed at ours — it is the layer this rule is enforced
  // *through*, not a screen that could drift.
  const files = sources(SRC).filter((path) => !path.includes("/ui/"));

  it("reads classes out of the files at all", () => {
    // A scan that finds nothing passes every assertion below it. Prove the
    // extractor still extracts, against a file that is *meant* to have one.
    const board = files.find((path) => path.endsWith("departure-board.tsx"));
    expect(board, "departure-board.tsx").toBeTruthy();
    expect(code(readFileSync(board!, "utf8")).match(OFF_PALETTE)).not.toBeNull();
  });

  it.each(files.map((path) => [path.slice(SRC.length + 1), path]))(
    "%s uses no stock Tailwind colour",
    (name, path) => {
      const allowed = ALLOWED[name.split("\\").join("/")] ?? [];
      const found = (code(readFileSync(path, "utf8")).match(OFF_PALETTE) ?? [])
        .filter((hit) => !allowed.includes(hit));

      expect([...new Set(found)]).toEqual([]);
    },
  );

  /**
   * A hex is the one thing a `dark:` variant cannot rescue: it paints the same
   * pixel on `#e9ebef` and on `#0b1120`. The map renderers were full of them —
   * `#10b981` for a home node, `#ef4444` for a railway — and they were the
   * reason the graph looked identical in both themes while everything around it
   * changed. `lib/map/palette.ts` and `metro/mode.ts` answer with `var()` now.
   */
  it.each(files.map((path) => [path.slice(SRC.length + 1), path]))(
    "%s writes no literal colour",
    (_name, path) => {
      const found = code(readFileSync(path, "utf8")).match(RAW_HEX) ?? [];
      expect([...new Set(found)]).toEqual([]);
    },
  );
});
