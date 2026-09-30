import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { LOCKUP_HREF, LOCKUP_VIEWBOX } from "@/components/layout/lockup";

/**
 * The lockup is one drawing, `backend/static/img/lockup.svg`, and both halves
 * draw it by reference: `<svg viewBox=…><use href="…#lockup"/></svg>`. The
 * reference cannot carry the drawing's proportions with it, so the viewBox is
 * written out at each place that uses it — the file itself, Django's partial
 * and the React component. If one of them moves alone, the word is cropped or
 * floats in empty space on one half of the site only, which is exactly the
 * kind of drift nobody sees until a screenshot.
 */
const FILE = fileURLToPath(
  new URL("../../../backend/static/img/lockup.svg", import.meta.url),
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
  it("has one viewBox, in the file, the Django partial and the component", () => {
    expect(viewBoxOf(svg)).toBe(LOCKUP_VIEWBOX);
    expect(viewBoxOf(partial)).toBe(LOCKUP_VIEWBOX);
  });

  it("is referenced by the same fragment on both halves", () => {
    expect(LOCKUP_HREF).toBe("/static/img/lockup.svg#lockup");
    expect(partial).toContain(`{% static 'img/lockup.svg' %}#lockup`);
    expect(svg).toContain('id="lockup"');
  });

  it("keeps the mark in the primary and lets the letters follow the theme", () => {
    const wordmark = svg.slice(svg.indexOf('id="wordmark"'));
    expect(wordmark).toContain('stroke="currentColor"');
    expect(wordmark).not.toMatch(/#[0-9a-f]{3,6}/i);

    const mark = svg.slice(svg.indexOf('id="mark"'), svg.indexOf('id="wordmark"'));
    // The car line and the primary are the same value (tokens.test.ts).
    expect(mark.match(/#[0-9a-f]{6}/gi)?.every((hex) => hex.toLowerCase() === "#1e88e5")).toBe(
      true,
    );
  });
});
