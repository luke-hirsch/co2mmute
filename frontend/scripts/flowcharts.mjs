#!/usr/bin/env node
/**
 * Draw the flowcharts on /docs/ablaufdiagramme/ again, from the Mermaid in
 * docs/de-flowcharts.md. Its English twin, docs/en-flowcharts.md, has no page
 * on the site — the site is German — and GitHub draws its Mermaid itself.
 *
 *   npm run flowcharts          (from frontend/)
 *
 * The site loads nothing from another origin, so it does not run Mermaid: the
 * charts are SVG files under backend/template/docs/flowcharts/, included into
 * the pages. This script is how they get there. It renders every ```mermaid
 * block in WebKit (Playwright, the e2e dependency), with Mermaid fetched
 * into that browser from a CDN for the run only, pinned so a re-run draws the
 * same files. Then it moves every colour onto the design tokens, so the charts
 * follow the page's light and dark mode, and refuses any colour that is not a
 * token — the same rule `co2mmute/tests/test_sanity.py` holds the figures to.
 *
 * A chart is drawn top to bottom and narrow: the column beside the list of
 * stops is about 810 px, a chart is never drawn larger than its own size, and
 * on a phone it shrinks to the screen's width. The script says when one comes
 * out wider than the column — draw it upright (`flowchart TD`, a subgraph with
 * `direction TB`, `~~~` to stack boxes) rather than letting it shrink further.
 *
 * Charts are numbered in the order they stand in the doc (de-01.svg …). Add one
 * in the middle and the ones after it move up a number: the script says when a
 * page includes a different number of charts than its doc has, and the page's
 * `{% include %}` lines are then fixed by hand.
 */

import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { webkit } from "@playwright/test";

const MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.min.js";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const out = path.join(repo, "backend", "template", "docs", "flowcharts");
const pages = {
  de: path.join(repo, "backend", "template", "docs", "ablaufdiagramme.html"),
};

const SANS =
  'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif';

// The light value of each token the charts paint with, and the variable the
// page sets it from (custom.css, `.doc figure`).
const TOKENS = {
  "#111827": "--fig-ink",
  "#ffffff": "--fig-bg",
  "#f4f5f7": "--fig-elevated",
  "#bcc3cc": "--fig-strong",
  "#d7dbe1": "--fig-rule",
  "#6b7280": "--fig-muted",
};
const INK = "#111827";
const SURFACE = "#ffffff";
const ELEVATED = "#f4f5f7";
const STRONG = "#bcc3cc";

// Every colour Mermaid's theme paints with, set to a token.
const themeVariables = {
  fontFamily: SANS,
  fontSize: "16px",
  background: SURFACE,
  primaryColor: SURFACE,
  primaryBorderColor: INK,
  primaryTextColor: INK,
  secondaryColor: ELEVATED,
  secondaryBorderColor: STRONG,
  secondaryTextColor: INK,
  tertiaryColor: ELEVATED,
  tertiaryBorderColor: STRONG,
  tertiaryTextColor: INK,
  lineColor: INK,
  textColor: INK,
  mainBkg: SURFACE,
  nodeBorder: INK,
  nodeTextColor: INK,
  clusterBkg: ELEVATED,
  clusterBorder: STRONG,
  titleColor: INK,
  edgeLabelBackground: SURFACE,
  actorBkg: SURFACE,
  actorBorder: INK,
  actorTextColor: INK,
  actorLineColor: STRONG,
  signalColor: INK,
  signalTextColor: INK,
  labelBoxBkgColor: ELEVATED,
  labelBoxBorderColor: STRONG,
  labelTextColor: INK,
  loopTextColor: INK,
  noteBkgColor: ELEVATED,
  noteBorderColor: STRONG,
  noteTextColor: INK,
  activationBkgColor: ELEVATED,
  activationBorderColor: INK,
  sequenceNumberColor: SURFACE,
  stateBkg: SURFACE,
  stateBorder: INK,
  labelColor: INK,
  altBackground: ELEVATED,
  compositeBackground: ELEVATED,
  compositeTitleBackground: ELEVATED,
  compositeBorder: STRONG,
  innerEndBackground: INK,
  specialStateColor: INK,
  transitionColor: INK,
  transitionLabelColor: INK,
  stateLabelColor: INK,
  errorBkgColor: ELEVATED,
  errorTextColor: INK,
};

// What Mermaid paints on its own, whatever the theme says, onto a token.
const STRAYS = [
  ["#000000", INK],
  ["#000", INK],
  ["black", INK],
  ["#666", INK], // the bottom actors' and the notes' border, as the top's
  ["#eaeaea", SURFACE], // the bottom actors, as the top ones
  ["#999", STRONG], // an actor's lifeline
  ["#e0e0e0", ELEVATED],
  ["#edf2ae", ELEVATED], // a note
  ["rgba(255, 255, 255, 0.5)", SURFACE],
];

// The text column beside the list of stops, from 1280 px up (custom.css).
const COLUMN = 810;

const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function recolour(svg, name) {
  // Mermaid's own hooks (data-points is base64 of every bend) and two
  // attributes that only restate the default
  svg = svg.replace(/\sdata-[\w-]+="[^"]*"/g, "");
  svg = svg.replace(/\sfont-(?:weight|style)="normal"/g, "");
  // shadows: Mermaid's "neo" look and the actor menu, neither of them used
  svg = svg.replace(/filter:\s*drop-shadow\([^;}]*\)\)?;?/g, "");
  svg = svg.replace(/box-shadow:[^;}]*;?/g, "");
  svg = svg.replace(/<filter\b[\s\S]*?<\/filter>/g, "");
  // an arrow's label sits on a half-transparent patch, so the line runs on
  // through the words; on a phone, where the chart is drawn small, that is
  // what makes a label unreadable
  svg = svg.replace(/(\.edgeLabel rect\{)opacity:0\.5;/g, "$1");

  for (const [stray, token] of STRAYS) {
    svg =
      stray === "black"
        ? svg.replace(/(?<=[=:"])black\b/g, token)
        : svg.replace(new RegExp(escape(stray) + "(?![0-9a-fA-F])", "gi"), token);
  }

  const tokens = new RegExp(
    Object.keys(TOKENS).map(escape).join("|") + "(?![0-9a-fA-F])",
    "gi",
  );
  svg = svg.replace(tokens, (hex) => `var(${TOKENS[hex.toLowerCase()]}, ${hex.toLowerCase()})`);

  // coordinates to two places — inside tags only, never in a label
  svg = svg.replace(/<[^>]+>/g, (tag) => tag.replace(/(\d+\.\d\d)\d+/g, "$1"));

  let sized = 0;
  // drawn at most its own size, and smaller with the column: on a phone the
  // whole chart is in view, and two fingers zoom into it
  svg = svg.replace(/style="max-width: ([\d.]+)px;"/, (_, width) => {
    sized += 1;
    return `style="max-width: ${Number(width).toFixed(0)}px;"`;
  });
  if (sized !== 1) throw new Error(`${name}: no max-width on the root`);

  const left = svg.match(/#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)/g) ?? [];
  const bad = [...new Set(left.filter((c) => !(c.toLowerCase() in TOKENS)))];
  if (bad.length) throw new Error(`${name}: colours that are no token: ${bad.join(", ")}`);
  for (const django of ["{{", "{%", "{#"]) {
    if (svg.includes(django)) throw new Error(`${name}: ${django} would be read as a template tag`);
  }
  return svg;
}

const charts = (lang) =>
  [
    ...readFileSync(path.join(repo, "docs", `${lang}-flowcharts.md`), "utf8").matchAll(
      /```mermaid\n([\s\S]*?)```/g,
    ),
  ].map((match) => match[1]);

const browser = await webkit.launch();
try {
  const page = await browser.newPage();
  await page.setContent(`<!doctype html><html><body style="font-family:${SANS}"></body></html>`);
  await page.addScriptTag({ url: MERMAID });
  await page.evaluate((themeVariables) => {
    window.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      // a note's outline is drawn with a little jitter; seeded, a re-run of
      // this script changes no file nobody touched
      handDrawnSeed: 1,
      theme: "base",
      themeVariables,
      fontFamily: themeVariables.fontFamily,
      htmlLabels: false,
      flowchart: { htmlLabels: false, useMaxWidth: true, padding: 18 },
      sequence: { useMaxWidth: true },
      state: { useMaxWidth: true },
    });
  }, themeVariables);

  mkdirSync(out, { recursive: true });
  for (const lang of Object.keys(pages)) {
    const blocks = charts(lang);
    const written = new Set();
    for (const [index, code] of blocks.entries()) {
      const name = `${lang}-${String(index + 1).padStart(2, "0")}`;
      const raw = await page.evaluate(
        async ({ id, code }) => (await window.mermaid.render(id, code)).svg,
        { id: `chart-${name}`, code },
      );
      const svg = recolour(raw, name);
      const width = Number(svg.match(/max-width: (\d+)px/)[1]);
      if (width > COLUMN) {
        console.log(`${name}: ${width} px wide, wider than the column (${COLUMN}): draw it upright`);
      }
      writeFileSync(path.join(out, `${name}.svg`), svg + "\n");
      written.add(`${name}.svg`);
    }
    // a chart taken out of the doc leaves no file behind
    for (const file of readdirSync(out)) {
      if (file.startsWith(`${lang}-`) && !written.has(file)) rmSync(path.join(out, file));
    }

    const included = (
      readFileSync(pages[lang], "utf8").match(/\{% include "docs\/flowcharts\//g) ?? []
    ).length;
    const note =
      included === blocks.length
        ? ""
        : ` — but ${path.relative(repo, pages[lang])} includes ${included}: fix its {% include %} lines`;
    console.log(`${lang}: ${blocks.length} charts${note}`);
  }
} finally {
  await browser.close();
}
