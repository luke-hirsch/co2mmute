---
name: sim-experiment
description: Change a number of the traffic model because newer research says so, and find out what it does to the maps before anything is kept. Use when someone says a figure is out of date ("the new UBA numbers are out", "a bus costs more now", "the standard says 3.9 kWh"). A change to how the model works, not to a number, is a conversation, never this skill.
---

# sim-experiment

The group keeps the model current with research. A number changes, the maps are measured before
and after, the human hears what the change does, and only then is it kept with everything that has
to follow. `docs/de-zahlen.md` / `docs/en-numbers.md` list every number and where it lives; read
the entry of the one at hand first.

**Only a number.** A change to how something works (a new rule, a street that behaves otherwise,
a figure the model does not have yet) is a conversation with the human about what the model
should say. Stop and say so. Never build it as an experiment.

## before you start

- A clone set up with `devops/dev.sh` as in `README.md`, with `npm ci` done in `frontend/`
  (`calibrate_map` routes with the game's own router).
- The human's **source** for the new value, and the old value as it stands in the constant. Without
  a source there is no change: every real-world figure needs one beside it.
- The maps to measure: always the shipped one, `map_examples/Berlin_Mitte-West.json` (`--commuters
  6800`), and every built map the human names (`check-up`'s `report` lists what an instance has).
  Each needs a count: use the map's own, never search a new one here.
- **A before/after run is long**: 3 minutes on the shipped map, about 40 on built Berlin, a minute
  on a village. **Ask before each run**, name the map and the time, and run it on a machine where
  nothing else heavy is going.

## 1. before

On the unchanged code, per map, saving what it prints:

```bash
devops/dev.sh manage calibrate_map /abs/map.json --commuters N > /abs/before-<map>.txt
```

`N` is the map's own count. Read the table: `nicht da` must be 0 in every row. If it is not, stop:
the map is broken before the change and nothing measured on it means anything.

## 2. change the number

In `backend/sim/constants.py` only (and the browser's copy in `frontend/src/lib/constants.ts` if the
doc says it has one). Put the source beside the constant, and name the old value as replaced
("was 3,94 € before the 2026 update, Deiters 2009"): the comment says what the figure is and where
it comes from, and the old one stays findable.

## 3. after

The same command, the same map file, the same count:

```bash
devops/dev.sh manage calibrate_map /abs/map.json --commuters N --out /abs/after-<map>.json > /abs/after-<map>.txt
python3 .agents/skills/sim-experiment/compare.py /abs/before-<map>.txt /abs/after-<map>.txt
```

`compare.py` prints what moved (the count, the share of the timetable, the car share normal buys,
everybody home) and then per car share: kg per person, euro per person, the car trip there and
back, the public transport trip and wait, and `nicht da`, as before → after.

## 4. tell the human

In German, with du, the verdict first, then the numbers:

- one sentence: "Ja, die Änderung macht X" or "Nein, sie bewegt nichts"; if she moves what the
  budget means ("Normal reicht jetzt bei 61 % statt 67 % Auto"), say that first;
- before → after in kg per person and minutes, for the shipped map and each map you measured;
- everybody home (`nicht da`), and anything that got worse on one map and better on another;
- what the change cost in a sentence a class could read, not a table.

The human decides whether it is kept. **If not, put the number back** and say so. Nothing below
happens before a yes.

## 5. keep it: what changes together

In this order, each checked:

1. **The drift test**: `cd frontend && npx vitest run tests/lib/constants.test.ts` (it names a copy
   that disagrees).
2. **The golden masters** go red on purpose (`backend/game/tests/test_sim_golden.py`): the model says
   it changed. Run the test, see it red on the changed number, then regenerate with
   `GOLDEN_REGENERATE=1 devops/dev.sh test game.tests.test_sim_golden` and **say so in the commit message** (German,
   lowercase, terse).
3. **Every map's row**: for each map measured, the file step 3 wrote with `--out` goes to
   `check-up`'s `write`, which puts the
   count, the share, the table and the date on the instance's row. `write` refuses a file whose map
   name differs from the row's: for a shipped file measured against a row of another name (the e2e
   seed calls it "E2E Berlin"), check the names first. A map the human did not name is
   `veraltet` in the sense that its table was measured with the old number; say so, and let
   `check-up` list it.
4. **The docs**, search the old value in each: `docs/kalibrierung.md` (the measured tables),
   `docs/de-zahlen.md` and `docs/en-numbers.md` (the entry), `docs/de-hintergrund.md`,
   `docs/en-background.md` and the site copy `backend/template/docs/hintergrund.html` (the
   figures). The pairs and the site copy change together. Then grep the old value across
   `backend/` and `docs/` once more: comments and docstrings quote figures too.
5. **The whole suites**, one heavy run at a time (`README.md`, "Tests"): backend, vitest, the three
   `tsc`, e2e. Read the counts.

## don't

- Don't change a number without its source, or keep a change the human has not said yes to.
- Don't tune a number to make a table look right. A figure comes from research or it does not move.
- Don't move another number to match (a cost does not follow a CO₂ fix). One change, one measurement.
- Don't regenerate the golden masters before the human has said yes.
- Don't start a long run without asking.
