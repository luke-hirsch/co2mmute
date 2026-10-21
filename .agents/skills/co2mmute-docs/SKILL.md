---
name: co2mmute-docs
description: Which files change together in co2mmute. Use before adding or changing a map field, a simulation constant, a line's seats and speed, a user-facing string, a socket event, something the site stores, the budget dial, a CI job or a doc page ("add a field to the map", "new socket event", "change the normal budget").
---

# co2mmute-docs

"Add X" in this repo is never one file. This skill lists every place each kind of change touches,
in the order to touch them, and how to check it. It repeats `AGENTS.md`, whose rules bind; here they
are recipes. Do the steps, then run the check at the end of each recipe, not only the suite.

## read first: which chart for which part

`docs/en-flowcharts.md` (German: `docs/de-flowcharts.md`) draws how information moves. Read the
section that holds what you change before you change it:

| you touch | read |
| --- | --- |
| the apps, Django, Celery, Redis, the SPA | "The pieces" |
| creating, starting or ending a game | "A game, start to end" |
| cookies, seats, joining, handing a seat over | "Player authentication" |
| what a player submits, the round's completion | "One round, end to end" |
| the trip a class picks in the browser | "Finding a route in the browser" |
| the engine, a link, a tick, CO₂ and cost | "The simulation" |
| the stats, discussion, vote and stalemate phases | "Between rounds" |
| a socket event and the screen it moves | "From the server to the screen" |
| versions, the ballot, what a vote changes | "Map versions and the vote" |

`docs/de-hintergrund.md` (English: `docs/en-background.md`) says why the model is the model;
`docs/kalibrierung.md` how the numbers were found.

## a field on the map

1. `backend/maps/models.py` and a migration (check the last number in `backend/maps/migrations/`
   first; never rename an applied one).
2. The file: `backend/maps/portability.py` (export) and `backend/maps/importer.py` (import).
   An import always makes a new map, so a field missing from the file takes its default.
3. `backend/maps/tests/test_portability.py`: a round trip with the field set.
4. A built map that should carry it: `backend/mapbuild/mapfile.py`, and `backend/mapbuild/transit.py`
   for a line's field. `check_map` rules are in `backend/maps/checks.py`.
5. The admin (`backend/maps/admin.py`), the API serializer (`backend/maps/serializer.py`) and the
   frontend type (`frontend/src/types/mapTypes.ts`), if anyone sets or reads it.
6. A game that must not move when the map changes copies the field when it starts (as
   `timetable_factor` is copied to `GameSession`).

Check: `devops/dev.sh test maps`, and `manage.py check_map` on the shipped map in `map_examples/`
(`backend/maps/tests/test_example_map.py` does).

## a simulation constant

1. `backend/sim/constants.py` is the only source of the model's numbers: emission and cost
   figures, speeds, the departure defaults, the dial. Put the number there with its source beside
   it; every real-world figure needs one. The browser's copies are in `frontend/src/lib/constants.ts`
   under the same names, and `frontend/tests/lib/constants.test.ts` fails when one disagrees.
2. Both golden masters: `backend/game/tests/test_sim_golden.py`, fixtures
   `backend/game/tests/golden/sim_golden.json` and `sim_golden_pt.json`. Regenerate with
   `GOLDEN_REGENERATE=1 devops/dev.sh test game.tests.test_sim_golden` only for a deliberate change, and say so in the commit.
3. `docs/de-zahlen.md` / `docs/en-numbers.md` (the entry: value, what it does, its source),
   `docs/kalibrierung.md` and the figures in `docs/de-hintergrund.md` / `docs/en-background.md`,
   then their site copy (see "a doc page"). A number changed on newer research is
   `.agents/skills/sim-experiment/SKILL.md`: the maps measured before and after, then this list.
4. A shipped map's measured count and share (`docs/kalibrierung.md`) are stale after a change that
   moves a round; re-measure with `calibrate_map`.

Check: the whole backend suite, reading the count.

## a line's seats and speed

Three files carry the same defaults, per bus, train and tram:

- `BusLine` and `TrainLine.DEFAULTS` in `backend/maps/models.py`
- `frontend/src/lib/map/pt-defaults.ts`
- `BUS` and `TRAIN` in `backend/mapbuild/transit.py`

Per-kilometre emission and cost for the kind are `backend/sim/constants.py` (see above).

## the router and the engine (change one, change both)

A ride is on one pass of its line. The router (`frontend/src/utils/ptRouting.ts`, `at` in its state)
and the engine (`PTLeg.board_stop` in `backend/sim/linkqueue.py`) both know where on the line a rider
is. The one router is `searchTrip` in `frontend/src/lib/map/trip-search.ts`;
`frontend/scripts/routes.mjs` runs the same code under Node for `calibrate_map`. Never write a second
router in Python.

`docs/de-routensuche.md` / `docs/en-route-search.md` describe both, mode by mode, with the numbers
they use: a change to the router or to how the engine plays a ride changes them.

Check: the router's tests under `frontend/tests/`, the sim tests, and a ring line (one that ends
where it starts) on a map with one.

## a user-facing string

1. `frontend/src/lib/de.ts` — every string; German, **du**, and a game agent is a Gruppe, the host
   machine the Leitstelle, the sum "alle Pendler". No "Klasse", "Lehrer", "Schule" (the few allowed
   places are in `frontend/tests/design/german.test.ts`).
2. A Django page: the template under `backend/template/`, in the same words.
3. A spec that finds a button by its name breaks on a copy edit: grep `frontend/e2e/`.

Check: `cd frontend && npx vitest run` (the German detector reads every `.tsx`), `npx tsc -b`.

## a socket event

1. The backend sends it from `game/signals.py`, `phases.py`, `roster.py`, `seats.py`, `pause.py` or
   `consumers.py`; broadcast after the atomic block, from sync code, never `async_to_sync` from a
   consumer.
2. `frontend/src/lib/game/events.ts`: the whole contract; add the event to the union and note the
   backend file that sends it.
3. The reducer in `frontend/src/lib/game/game-state.ts` ends in `assertNever`, so the build fails
   until the event is handled. Handle it there, not in a component, and never poll beside a socket.
4. A test that listens (`GroupListener` in `backend/game/tests/_helpers.py`), not one that patches.

Check: `npx tsc -b` fails before step 3 and passes after; then the socket tests.

## something the site stores

AGENTS.md: anything new that stores player-written text needs an answer for how long it is kept
before it ships.

1. `backend/game/anon.py` if it holds a name or text from a player.
2. `backend/template/legal/dsgvo.html` and `cookies.html`, in du, in the same commit.
3. A new log line carries ids, never names (`backend/game/tests/test_privacy.py`).
4. The research export: a new column leaves only if it identifies nobody
   (`.agents/skills/extract-data/SKILL.md`).

## the budget dial

`CO2_KG_PER_PERSON_*` in `backend/sim/constants.py` (read by `backend/game/calibration.py`) and
`frontend/src/lib/constants.ts` (read by `frontend/src/lib/calibration.ts`) carry the same normal,
step and range. `backend/game/tests/test_join.py` and
`frontend/tests/lib/calibration.test.ts` assert the same cases. The create form
(`frontend/src/components/host/create-game-screen.tsx`) and `docs/kalibrierung.md` (the normal and
where it comes from) follow.

## a CI job

`.github/workflows/test.yml` and `.github/workflows/workflow-prod.yml` carry copies of the same jobs
(`backend`/`test`, `frontend`, `e2e`), because one workflow cannot wait on another. Change both, keep
the copies identical; deploy needs all three. Diff the two job blocks before you commit.

## a doc page

- `docs/` is flat `de-`/`en-` pairs (`quick-start`, `flowcharts`, `de-zahlen` is `en-numbers`; `de-hintergrund`
  is `en-background`; `de-routensuche` is `en-route-search`).
  `kalibrierung.md` and `testfaelle.md` have no twin and stay off the site; `de-zahlen` and
  `de-routensuche` have no page either.
- The pages under `/docs/` are hand copies of the German files: `backend/template/docs/schnellstart.html`,
  `hintergrund.html`, `ablaufdiagramme.html`. A change to one is a change to the other. No test
  holds a page to its doc, so you are the check: read both.
- Flowcharts: edit the Mermaid in `docs/de-flowcharts.md` (and the English twin), then
  `cd frontend && npm run flowcharts` redraws the SVGs in `backend/template/docs/flowcharts/`.
  Charts stay upright, at most about 800 px wide.
- The README is German first, then the same sections in English: change one half, change the other.
- `docs/testfaelle.md` says `geht` only for a case that was run.

## a design token

`frontend/src/main.css` and `backend/static/css/custom.css` carry the same block between
`>>> shared tokens` and `<<< end shared tokens >>>`; `frontend/tests/design/tokens.test.ts` names the
one that drifted. The colour-mode bootstrap is inline in `frontend/index.html` and in
`backend/static/js/head_script.js`.

## decided: a line runs while anybody is out

A line runs for as long as anybody at all is still out, not only while somebody can still use it.
The other way exists — a line runs only while a rider can still use it — and was not chosen: on the
improving class it measured 95 541 kg against 107 716 kg. The first is fair and truthful, so it
stays. Don't switch it for the lower number.

## don't

- Don't move a number to match a change elsewhere (a cost to match a CO₂ fix). Say the gap.
- Don't add a second path where a rule already has two ends (router and engine, token copies, CI
  jobs, doc pairs): finish both or neither.
- Don't call a recipe done on a green summary. Read the test **count**.
