# Tokens

Defined **twice**, identically, and guarded by `frontend/tests/design/tokens.test.ts`:

- `frontend/src/main.css` — the SPA
- `backend/static/css/custom.css` — the Django templates

Both blocks sit between `>>> shared tokens` and `<<< end shared tokens >>>`. Change a value in one,
change it in the other, or the test goes red and names the token. Change the tables below with them.

**Why duplicated and not shared:** the two halves run separate Tailwind installs
(`@tailwindcss/vite` vs `@tailwindcss/cli`), and their Docker images copy only their own directory —
`backend/Dockerfile` copies `backend/`, `devops/nginx/Dockerfile` copies `frontend/`. A file
imported across that boundary breaks both builds.

Both blocks are `@theme static`, not `@theme`. Tailwind drops theme variables nothing references
yet, which would make `max-w-(--measure-body)` resolve to nothing the first time it is used.
`static` forces them all out.

---

## The four lines

| token | value | notes |
| --- | --- | --- |
| `--color-line-car` | `#1e88e5` | = `--color-primary-500`; solid |
| `--color-line-pt` | `#ffb300` | = the accent; solid |
| `--color-line-bike` | `#35566e` | muted primary; **dashed** |
| `--color-line-bike-dark` | `#8fb2cc` | what the bike becomes on dark |
| `--color-line-walk` | `#111827` | ink; **dotted** |
| `--color-line-walk-dark` | `#f9fafb` | what walking becomes on dark |

Two colours, four lines. The stroke pattern separates the two blues — at 5px, hue cannot.

Consume through `bg-mode-car`, `text-mode-pt`, `border-mode-walk`, … — those resolve the theme
flip. `frontend/src/components/metro/mode.ts` maps mode → utility.

## Neutrals

| light | | dark | |
| --- | --- | --- | --- |
| `--color-body` | `#e9ebef` | `--color-darkbody` | `#0b1120` |
| `--color-surface` | `#ffffff` | `--color-darksurface` | `#111827` |
| `--color-elevated` | `#f4f5f7` | `--color-darkelevated` | `#1f2933` |
| `--color-subtle` | `#d7dbe1` | `--color-darksubtle` | `#1f2937` |
| `--color-strong` | `#bcc3cc` | `--color-darkstrong` | `#374151` |
| `--color-main` | `#111827` | `--color-darktext` | `#f9fafb` |
| `--color-soft` | `#8b93a1` | `--color-darksofttext` | `#6b7280` |

The light steps are wider than a stock gray-50/100 ramp, on which a white card has no edge against
the page. The dark ramp has real steps of its own.

Muted text is `#6b7280` (dark `--color-darkmutedtext`, `#9ca3af`). It is called `--color-muted` on
the Django side and `--color-mutedtext` in the SPA, because shadcn owns the name `muted` there. The
same for the brand amber: `--color-accent` (Django) vs `--color-brandaccent` (SPA). Those four are
the only names that differ, and they sit outside the shared block on purpose. `text-mutedtext` and
`bg-body` are live tokens, not leftovers.

## Semantic — there are none

No success, warning or danger ramp, and no red or green anywhere. Attention is the accent; presence
and progress are filled vs hollow. See `rulebook.md`, §5.

## Type and measure

```
--font-sans   ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, …
--font-mono   ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, …
--measure-lead   46ch
--measure-body   62ch
--measure-prose  70ch
```

## shadcn's names point here

In `main.css`, `--background`, `--foreground`, `--card`, `--primary`, `--border`, `--ring`,
`--chart-*` and the rest are **not a second palette** — each is a `var()` into a token above. That
is why the shadcn primitives speak this palette without being rewritten.

Two that are chosen by eye rather than mapped mechanically:

- `--secondary` → `--color-subtle`, not `--color-elevated`. Elevated is one step off the body
  colour, which makes a secondary button all but invisible. On dark it is `--color-darkelevated`.
- dark `--primary` → `--color-primary-400`, not `-600`. The 600 blue is too dark to sit on
  `#0b1120`; the label flips to `--color-primary-900` to stay readable on it.
