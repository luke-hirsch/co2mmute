import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * The SPA and the Django templates are built by two separate Tailwind installs,
 * and each Docker image copies only its own directory — so the design tokens
 * cannot live in one shared file without breaking both builds. They are
 * duplicated instead, and this test is what keeps the copies honest.
 *
 * Only the block between the two markers is shared. Everything outside it is
 * allowed to differ: shadcn owns `accent` and `muted` on the SPA side, so the
 * car colour and the muted text colour are called brandaccent / mutedtext
 * there, and the Django half keeps some long-form aliases the templates use.
 */
const SPA_CSS = fileURLToPath(new URL("../../src/main.css", import.meta.url));
const DJANGO_CSS = fileURLToPath(
  new URL("../../../backend/static/css/custom.css", import.meta.url),
);

const START = />>> shared tokens[^\n]*<<<[^\n]*\*\//;
const END = /\/\*\s*<<< end shared tokens >>>\s*\*\//;

function sharedBlock(file: string): string {
  const css = readFileSync(file, "utf8");
  const start = css.search(START);
  const end = css.search(END);
  if (start === -1) throw new Error(`no shared-token start marker in ${file}`);
  if (end === -1) throw new Error(`no shared-token end marker in ${file}`);
  return css.slice(css.match(START)![0].length + start, end);
}

/** `--name: value;` pairs, comments stripped, whitespace collapsed. */
function tokens(block: string): Map<string, string> {
  const withoutComments = block.replace(/\/\*[\s\S]*?\*\//g, "");
  const found = new Map<string, string>();
  for (const decl of withoutComments.split(";")) {
    const match = decl.match(/(--[A-Za-z0-9-]+)\s*:\s*([\s\S]+)/);
    if (!match) continue;
    found.set(match[1], match[2].replace(/\s+/g, " ").trim());
  }
  return found;
}

describe("design tokens are shared between the SPA and the Django templates", () => {
  const spa = tokens(sharedBlock(SPA_CSS));
  const django = tokens(sharedBlock(DJANGO_CSS));

  it("finds a non-trivial block on both sides", () => {
    expect(spa.size).toBeGreaterThan(30);
    expect(django.size).toBe(spa.size);
  });

  it("defines the same token names", () => {
    expect([...django.keys()].sort()).toEqual([...spa.keys()].sort());
  });

  it("gives every token the same value", () => {
    for (const [name, value] of spa) {
      expect(django.get(name), `${name} differs between the two files`).toBe(
        value,
      );
    }
  });

  it("carries the four transport lines, which are the app's identity", () => {
    expect(spa.get("--color-line-car")).toBe("#1e88e5");
    expect(spa.get("--color-line-pt")).toBe("#ffb300");
    expect(spa.get("--color-line-bike")).toBe("#35566e");
    expect(spa.get("--color-line-bike-dark")).toBe("#8fb2cc");
    expect(spa.get("--color-line-walk")).toBe("#111827");
    expect(spa.get("--color-line-walk-dark")).toBe("#f9fafb");
  });

  it("has no success, warning or danger ramp", () => {
    // Green was the bike line and the success colour at once, so a confirmation
    // read as "bike". The ramps are gone; the accent carries attention alone.
    const signals = [...spa.keys()].filter((name) =>
      /--color-(success|warning|danger)-/.test(name),
    );
    expect(signals).toEqual([]);
  });

  it("keeps the two line colours that double as brand colours in step", () => {
    // The car line IS the primary and the PT line IS the accent. If one drifts
    // the interface quietly grows a fifth and sixth colour.
    expect(spa.get("--color-line-car")).toBe(spa.get("--color-primary-500"));
    expect(django.get("--color-line-pt")).toBe("#ffb300");
  });

  it("names no third-party font host", () => {
    // A webfont from someone else's server sends every visitor's IP there, and
    // the players are school students under a data-minimisation design.
    for (const stack of [spa.get("--font-sans"), spa.get("--font-mono")]) {
      expect(stack).toBeDefined();
      expect(stack).not.toMatch(/https?:|fonts\.(googleapis|gstatic)\.com/);
    }
  });
});
