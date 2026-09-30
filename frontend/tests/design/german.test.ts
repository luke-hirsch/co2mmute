import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Every screen in the SPA speaks German, and this is what finds the ones that
 * do not.
 *
 * The backend has had a detector since the funnel was translated
 * (`english_in` in `game/tests/_helpers.py`), and it covered two pages. The
 * SPA had none, which is how `← All maps`, a `confirm("Delete map …")` and a
 * panel headed `Modify Edge` stayed live on the site through two German
 * passes: the map area was never read out loud, and a grep for text nodes does
 * not see a template literal or a label built in an array.
 *
 * Shape is `tokens.test.ts`'s — read the source, name the drifting thing. It
 * is a source scan rather than a render, because rendering these components
 * needs a map, a router and a query client, and the bug is in the file either
 * way.
 *
 * What it reads is only what a reader sees: JSX text, the handful of
 * attributes that are read out (`title`, `placeholder`, `aria-label`, `alt`),
 * and the strings handed to the browser's own dialogs. Class names, imports,
 * CSS and code identifiers are not copy and are stripped before the words are
 * matched.
 */
const SRC = fileURLToPath(new URL("../../src", import.meta.url));

/**
 * Words that cannot appear in German copy, matched whole-word. Deliberately
 * not "Bus", "Route", "Start" or "Modus": they are German too, and flagging
 * them would make the detector an opinion about vocabulary rather than about
 * language — the same line the backend's list draws.
 */
const ENGLISH_GIVEAWAYS = [
  "all",
  "already",
  "cannot",
  "cascade",
  "changes",
  "click",
  "close",
  "combinations",
  "create",
  "creating",
  "bidirectional",
  "delete",
  "edge",
  "edges",
  "edit",
  "failed",
  "invalid",
  "keep",
  "lane",
  "lanes",
  "loading",
  "map",
  "maps",
  "missing",
  "modify",
  "must",
  "new",
  "one-way",
  "node",
  "nodes",
  "pending",
  "please",
  "remove",
  "saving",
  "generating",
  "selected",
  "street",
  "this",
  "train",
  "undo",
  "undone",
  "valid",
  "yes",
  "your",
];

const ENGLISH = new RegExp(`\\b(?:${ENGLISH_GIVEAWAYS.join("|")})\\b`, "i");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return sources(path);
    return path.endsWith(".tsx") ? [path] : [];
  });
}

/**
 * The copy in one file: what a reader sees, and nothing else.
 *
 * Comments go first (they are English by house rule), then `className`,
 * `style` and `key`, then imports — a path is never copy, which is the same
 * call `visible_text` makes on the backend. `{...}` inside JSX text is an
 * expression, so it is replaced rather than read: `Edit {type} Line` has to
 * come back as `Edit Line`, or the two English words around the hole are
 * invisible.
 */
function copyIn(source: string): string[] {
  const code = source
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ")
    .replace(/\bimport\b[^\n]*\n/g, " ")
    .replace(/(?:className|class|style|key|data-testid)=\{[\s\S]*?\}\}?/g, " ")
    .replace(/(?:className|class|style|key|data-testid)="[^"]*"/g, " ")
    .replace(/(?:className|class)=\{`[\s\S]*?`\}/g, " ");

  const found: string[] = [];

  // The attributes that are read out loud, plus the browser's own dialogs.
  const spoken =
    /(?:title|placeholder|aria-label|alt)=(?:"([^"]*)"|\{\s*"([^"]*)"\s*\}|\{`([^`]*)`\})|(?:confirm|alert|prompt)\(\s*(?:"([^"]*)"|`([^`]*)`)|(?:title|placeholder|aria-label|alt)=\{[^}]*?[`"]([^`"]{4,})[`"]/g;
  for (const match of code.matchAll(spoken)) {
    const text = match.slice(1).find((group) => group !== undefined);
    if (text) found.push(text);
  }

  // A sentence in a `{...}` expression is copy too — `{isModifyMode ? "Modify
  // Edge" : "Edge"}` is a heading, and a grep for text nodes never sees it.
  //
  // Every literal is matched, in order, and only then filtered: pairing the
  // quotes is the whole job. A pattern that looks for a literal *containing a
  // space* skips `"var(--car)"` and then pairs its closing quote with the next
  // literal's opening one, reading `", label: de.map.legend.train, dash: "` as
  // a sentence.
  //
  // Two words minimum, which is what separates copy from a compared value:
  // `type === "street"` is not a sentence and must not be read as one. A
  // `throw new Error(...)` and a `console.*` are not copy either — both are
  // addressed to whoever wired the component up, never to a player, and this
  // codebase writes those in English by house rule.
  const withoutInvariants = code
    .replace(/throw new Error\([\s\S]*?\);/g, " ")
    .replace(/console\.\w+\([\s\S]*?\);/g, " ");
  const literals = withoutInvariants.matchAll(
    /"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`/g,
  );
  for (const match of literals) {
    const raw = match[1] ?? match[2];
    if (raw.includes("\n") || !raw.includes(" ")) continue;
    const text = raw.replace(/\$\{[^}]*\}/g, " ").trim();
    if (text && /[A-Za-zÄÖÜäöüß]/.test(text)) found.push(text);
  }

  // JSX text: whatever sits between a tag's `>` and the next `<`. A regex
  // cannot tell that `>` from the one in `a >= b` or `Map<string, X>`, so the
  // ones it cannot be are excluded (`=>`, `>=`, `->`) and anything carrying a
  // statement's punctuation is dropped afterwards — JSX text has no semicolons
  // once its entities are resolved.
  const CODE =
    /[;]|=>|===|!==|&&|\|\||\breturn\b|\bconst\b|\blet\b|\bfunction\b|\btypeof\b|\bnull\b|\bundefined\b/;
  for (const match of code.matchAll(/(?<![=!<>-])>([^<>]*)</g)) {
    const resolved = match[1].replace(/&[a-z]+;/gi, " ");
    if (CODE.test(resolved)) continue;
    // Expressions from the inside out, so a nested one does not leave its
    // outer half behind, then whatever tail an unclosed brace left.
    let text = resolved;
    for (let before = ""; before !== text; ) {
      before = text;
      text = text.replace(/\{[^{}]*\}/g, " ");
    }
    text = text.replace(/\{[\s\S]*$/, " ").replace(/\s+/g, " ").trim();
    if (text && /[A-Za-zÄÖÜäöüß]/.test(text)) found.push(text);
  }

  return found;
}

describe("the SPA speaks German", () => {
  const files = sources(SRC).filter((path) => !path.includes("/ui/"));

  it("reads copy out of the files at all", () => {
    // A scan that finds nothing passes every assertion below it. This is the
    // guard: a known German string has to come back, or the extractor has
    // stopped extracting and the suite has stopped testing anything.
    const round = files.find((path) => path.endsWith("round-screen.tsx"));
    expect(round, "round-screen.tsx").toBeTruthy();
    expect(copyIn(readFileSync(round!, "utf8")).length).toBeGreaterThan(0);
  });

  it.each(files.map((path) => [path.slice(SRC.length + 1), path]))(
    "%s",
    (_name, path) => {
      const offenders = copyIn(readFileSync(path, "utf8")).filter((text) =>
        ENGLISH.test(text),
      );

      expect(offenders).toEqual([]);
    },
  );
});
