# Design rules

How co2mmute looks, and why. The evidence for everything here is `/app/styleguide`, which renders
every token, primitive and pattern on one page. If a rule below and that page disagree, the page
is right and this file is stale: fix it. The tokens are in `tokens.md`, the words in `copy.md`.

## 1. Where the look comes from

**Derive it from the game.** The game is a map graph with transport lines on it, so the interface
is a transit diagram: lines, stations, signage, a departure board. Anything that is a sequence —
the rounds of a game, the steps of a turn, the phases between rounds — is drawn as a line with
stops on it.

The failure mode is the stock SaaS look: a hero with blurred gradient blobs, an uppercase eyebrow
label, a card grid, a gradient call-to-action box. It says nothing about the game.

**Never:** blurred blobs · gradient buttons or gradient text · uppercase eyebrow labels (the
departure board's mono label is the one exception, and it is signage, not an eyebrow) · a card grid
as the default layout for anything · drop shadows doing the work a line should do · an icon where a
word is clearer.

**Reach for first:** a line in a mode's colour · a station marker on a heading · a rule above a
section · the departure board for anything that is a code · plain space.

## 2. Weight

The brief for the whole system: more whitespace, bigger margins and paddings, narrower lines of
text, lighter font weights.

| where | weight | Tailwind |
| --- | --- | --- |
| display headings, `text-4xl` and up | 500 | `font-medium` |
| section headings, `text-2xl`–`text-3xl` | 600 | `font-semibold` |
| sub-heads, labels, buttons, badges | 500 | `font-medium` |
| body, leads | 400 | — |

**`font-bold` is not used anywhere.** Nothing goes above 600. Large type carries less weight
better, which is why display sizes step *down* to 500 rather than up.

Size and space separate the levels. Weight does not.

## 3. Measure

Text columns are capped, always. Use the tokens, not a `max-w-*` guess:

- `max-w-(--measure-lead)` — 46ch, for leads and intros
- `max-w-(--measure-body)` — 62ch, for running body text
- `max-w-(--measure-prose)` — 70ch, for a whole document page (legal pages)

A paragraph with no cap is a bug, not a default.

## 4. Air

- **Sections:** `py-20 lg:py-28`. Never `py-12`.
- **Items in a list of sections:** `space-y-16 lg:space-y-20`.
- **Heading → lead:** `mt-3`/`mt-4`. **Lead → body:** `mt-8`.
- **Controls** sit one step roomier than shadcn's defaults — button height 40px as the normal case
  (thumb-sized on a phone), card padding `p-7`, dialog `p-7`, alert `px-5 py-4`.

## 5. Colour

**The four lines are the identity.** Every screen that shows a transport mode uses these and
nothing else:

| mode | colour | stroke | utility |
| --- | --- | --- | --- |
| Auto | primary `#1e88e5` | solid | `bg-mode-car` `text-mode-car` `border-mode-car` |
| Bus & Bahn | accent `#ffb300` | solid | `…-mode-pt` |
| Fahrrad | muted primary, `#35566e` → `#8fb2cc` | **dashed** | `…-mode-bike` |
| zu Fuß | ink, `#111827` → `#f9fafb` | **dotted** | `…-mode-walk` |

**Two colours carry all four lines.** The car line *is* the primary and the PT line *is* the
accent — the same value, not two that happen to match, and `tests/design/tokens.test.ts` enforces
it. The bike is a muted primary; walking is ink.

**Pattern, not hue, is what separates them.** Two blues at stroke width read as one line, and it is
worse than it looks: measured, a pale muted blue and the accent land within **1.01** contrast of
each other on the dark ground. So the car is solid, the bike dashed, walking dotted. That is how a
transit map does it, and unlike hue it survives colour blindness.

Bike and walk each carry a second value for dark, because a line that reads on `#e9ebef` is
invisible on `#0b1120`. Use the `mode-*` utilities, never the raw `--color-line-*` tokens: the
utilities resolve the flip. The mapping lives in `frontend/src/components/metro/mode.ts` — if you
are picking a colour for a mode at a call site, stop and use that.

**There is no success, warning or danger ramp, and no green or red at all.** A signal colour would
collide with a line: a green confirmation reads as a line, an amber warning as the PT line. The
palette is the primary, the accent and ink, and nothing else. What does their work:

- **Attention** — a filling CO₂ budget, a failed request, an irreversible button — is the
  **accent**. It is the primary's complement, so the switch from one to the other reads as tension
  rather than as decoration.
- **Presence and progress** are **filled vs hollow**, not green vs grey: a connected player, a
  round already played. Costs no colour, and it is the language the track already speaks.
- **The CO₂ budget is binary** — primary until `BUDGET_ATTENTION_AT` (0.75, `frontend/src/lib/co2.ts`),
  then accent. No third band: "warning" versus "danger" is a distinction the screen cannot act on.

Everything else: neutrals for surfaces, `primary` for the one main action on a screen.

The cost, accepted: amber carries the PT line, the budget's attention end, destructive buttons and
error alerts at once. Icon and text have to do the separating.

## 5a. Lines that cross, and figures

**A line never runs through another.** Where one has to cross the others — the landing page's PT
detour crosses bike and walk on the way out and back — it is drawn over a **casing**: the same bend,
`--bridge` wider on each side, in the ground colour, underneath (`.metro-casing`). That is how a
transit map shows one line passing over another. A rectangle on the straight leg is not enough when
the crossing is on the curve; the casing has to follow the line's own shape.

**The landing page's ground stays `bg-body`.** Its fan-out hides the lines by painting that colour
over them; another background shows them through.

**A long page is one line, not four.** The docs pages (`backend/template/docs/page.html`) run on
the PT line alone — the landing's detour leads there — with chapters as stations (`metro-dot`
size), sections as stops (a size down), and the contents as a short line of their own that fills
the stations already passed.

**Figures are two colours and ink, and quantity is geometry.** Car = primary, timetable/PT =
accent, people = the soft neutral, axes and rules in ink and subtle. A bar's length is the number;
nothing is a colour ramp. Labels never sit on a line — a halo fails between glyphs, so move the
labels into a column of their own instead. Text at 13 units in a 344-wide viewBox reads ~11 px on a
390 phone; keep that ratio.

**A figure is an SVG file that works alone.** `backend/template/hintergrund/*.svg` are included
inline on the page *and* shown as images by the docs on GitHub, so every colour is
`var(--fig-…, #token)`: the page sets the vars per theme, standalone the fallbacks paint light on
a white card. `test_sanity` refuses a fallback that is no token. The flowcharts on the site follow
the same rule (`npm run flowcharts` moves their colours onto the tokens).

## 6. Type

**System stack, no webfont, ever.** A font from someone else's server sends every visitor's IP
there, and the players are school students under a data-minimisation design whose privacy page has
to describe exactly what leaves the browser. If a real typeface is ever wanted, it gets
self-hosted and the privacy page changes with it.

**The name is set, not drawn.** The lockup is the mark — which *is* the C — followed by "O₂mmute"
as text in the system sans, weight 600, 22 px in the header. The C runs from the top of the O to the
foot of the subscript 2 and is ink like the letters; only its node and edge are the primary
(`frontend/src/components/layout/lockup.tsx`, `backend/template/partials/lockup.html`). No outlined
lettering anywhere, logo included: letters drawn as paths read as a different font beside the
system font.

**Mono is reserved** for ids, codes and numerals: game ids, seat codes, step numbers, kg figures in
a table. Mono anywhere else is noise.

## 7. Both themes, every time

Nothing ships light-only. **Both halves resolve dark the same way**: the `.dark` class on
`<html>`, bound by `@custom-variant dark (&:is(.dark *))` in each stylesheet, written by a bootstrap
script that runs in `<head>` before anything paints.

They are one origin, so they share the `colorMode` entry in `localStorage` — a switch on either
follows on both. The toggle on `/app/styleguide` changes the landing and legal pages too.

Two things this costs, both accepted:

- With JavaScript off the Django pages are light-only. They stay fully readable.
- The bootstrap is written twice: inline in `frontend/index.html`, and
  `backend/static/js/head_script.js` for Django. It has to be inline to avoid a flash, and the two
  cannot share a file across the build boundary. Two copies drift — a storage key missing from one
  makes the theme toggle throw on every click — so `tests/lib/color-mode-bootstrap.test.ts` runs
  the inline script and uses it.

## 8. Copy

German, `du`, never `Sie` — legal pages included. Every player-facing string goes through
`frontend/src/lib/de.ts`; nothing hardcoded in JSX. See `copy.md`.

## 9. How this gets checked

Open `/app/styleguide` on a running dev stack (README) in WebKit — Safari and every iOS browser are
WebKit — at 390 px and 1440 px, light and dark. Nothing scrolls sideways, the console stays empty,
the theme applies, and no heading is heavier than 600. After a token change, compare the page
section by section: if one token moves three unrelated sections, that is the bug the page exists to
catch.

The mechanical guards:

- `frontend/tests/design/tokens.test.ts` — the shared token block in `frontend/src/main.css` and
  `backend/static/css/custom.css` must stay identical, value for value.
- `frontend/tests/design/palette.test.ts` — the SPA paints from the palette only.
- `frontend/tests/lib/de.test.ts` — no `Sie`, and the dictionaries that mirror the backend cover
  exactly what it can send.
- `TemplatesStayOnThePaletteTests` in `backend/co2mmute/tests/test_sanity.py` — the same for the
  Django templates.

## 9a. The Django half

The credential pages are the Django twins of SPA screens, not a second design:
`template/narrow.html` = `<Screen narrow>`, `partials/screen_heading.html` = `ScreenHeading`,
`partials/field.html` = `Field`, and `custom.css`'s component layer carries `field-input`,
`field-checkbox`, `field-help`, `field-error`, `form-alert`, `btn` + `btn-primary` / `btn-outline`
/ `btn-attention` and `text-link`, value for value against the shadcn primitives. A new Django form
uses those, never a utility list in Python — Tailwind does not scan `.py`. A refusal on either half
is an amber rule beside ink text, never amber text.

## 10. What is not settled yet

- The only theme switch is the one on `/app/styleguide`, which is a development surface. No
  player-facing switch exists yet; when one ships it belongs in the nav on both halves.
- A destructive alert and the pause banner are both filled accent panels and look alike — only the
  icon and the words separate them. Live with it, or give one of them an outline instead of a fill.
- `prose` / `prose-invert` on the legal pages are inert — no typography plugin is installed. The
  spacing there is hand-set.
