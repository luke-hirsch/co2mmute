import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  LOCKUP_CLASS,
  MARK_CLASS,
  MARK_HREF,
  MARK_VIEWBOX,
} from "@/components/layout/lockup";
import { de } from "@/lib/de";

/**
 * The lockup is written twice — `components/layout/lockup.tsx` and Django's
 * `template/partials/lockup.html` — because the two halves render separately
 * and neither can include the other. The mark is one drawing,
 * `backend/static/img/mark.svg`, used by reference from both; the reference
 * cannot carry the drawing's proportions, so its viewBox is written out at
 * each place too. If any of these moves alone the name is sized, cropped or
 * spelled differently on one half of the site only — the drift nobody sees
 * until a screenshot.
 */
const FILE = fileURLToPath(
  new URL("../../../backend/static/img/mark.svg", import.meta.url),
);
const PARTIAL = fileURLToPath(
  new URL("../../../backend/template/partials/lockup.html", import.meta.url),
);

const svg = readFileSync(FILE, "utf8");
const partial = readFileSync(PARTIAL, "utf8");

function viewBoxOf(markup: string): string | undefined {
  return markup.match(/<svg[^>]*\sviewBox="([^"]+)"/)?.[1];
}

describe("the lockup", () => {
  it("has one viewBox for the mark, in the file, the Django partial and the component", () => {
    expect(viewBoxOf(svg)).toBe(MARK_VIEWBOX);
    expect(viewBoxOf(partial)).toBe(MARK_VIEWBOX);
  });

  it("draws the mark from the same file on both halves", () => {
    expect(MARK_HREF).toBe("/static/img/mark.svg#mark");
    expect(partial).toContain(`{% static 'img/mark.svg' %}#mark`);
    expect(svg).toContain('id="mark"');
  });

  it("sets the name the same way on both halves", () => {
    const classes = [...partial.matchAll(/class="([^"]+)"/g)].map((m) => m[1]);
    expect(classes).toEqual([LOCKUP_CLASS, MARK_CLASS, "sr-only"]);

    const { before, sub, after } = de.app.wordmark;
    expect(partial).toContain(`</svg>${before}<sub>${sub}</sub>${after}</span>`);
    expect(partial).toContain(`<span class="sr-only">${de.app.name}</span>`);
  });

  it("spells the whole name with the mark as its C", () => {
    const { before, sub, after } = de.app.wordmark;
    expect(de.app.name).toBe(`C${before}${String.fromCharCode(0x2080 + Number(sub))}${after}`);
  });

  it("keeps the mark in the primary, which is the car line", () => {
    const hexes = svg.match(/#[0-9a-f]{6}/gi) ?? [];
    expect(hexes.length).toBeGreaterThan(0);
    expect(hexes.every((hex) => hex.toLowerCase() === "#1e88e5")).toBe(true);
  });
});
