---
name: check-up
description: Report on the state of the maps on a co2mmute instance (does the map check out, was it measured, was it edited since) and measure again the ones that are out of date. Use when someone asks whether the maps are in order, after maps were edited in the map editor, or before a class plays. Not for changing a map (map-modify, map-versions) and not for building one (map-create).
---

# check-up

A diagnosis, not a test of the whole game. It logs in to an instance like `map-versions` and
`map-modify`, works over the API, and runs the checks locally on each map's export. It never plays
a game on the instance, so nothing it does reaches the research data.

## before you start

- A staff account on the instance, and `python3` (standard library only).
- `CO2MMUTE_URL` (the instance; default `http://127.0.0.1:8000`, Django itself), `CO2MMUTE_USER`
  and `CO2MMUTE_PASSWORD`.
- A clone with `npm ci` done in `frontend/`, because the measuring needs the game's router
  (see `map-create`). `CO2MMUTE_MANAGE` is the command that runs `manage.py` there; the default is
  `devops/dev.sh manage`.

## the report

```bash
python3 .agents/skills/check-up/checkup.py report [<dir>]
```

It exports every map into `<dir>` (default `./checkup-<date>`) and prints, per map:

- **check_map**: `in Ordnung`, or the first lines of what is wrong (`maps/checks.py`: one link per
  direction, lines whole and on their own side, a way from every home to every workplace and back).
- **Messung**: `nie gemessen` (the map has no `calibrated_at`), `aktuell, gemessen am …`, or
  `veraltet: bearbeitet am …, gemessen am …`. The map notes an edit whenever a node, an edge, a line
  or the scale or a speed of the map changes (`graph_edited_at`); a measurement written back, a
  rename and an import are no edit.
  `veraltet` means "something changed since": any graph write marks it, also an edit in a version
  other than the base or a poll text, so the report asks and does not decide.
- the commuters, the share of the timetable and whether the table is there;
- the size, and where the export is.

Read it out to the human, in German with du, one map at a time: what is fine, what is not.

## measuring again

A map that is `veraltet`, `nie gemessen`, or has a `check_map` problem is the human's to decide on.
**A map that fails `check_map` is not measured**: give the human the lines.

A measurement takes minutes on a small map and about 40 on Berlin, with the machine busy the whole
time. **Ask before every run**, and name the map and how long it is likely to take. Never start one
on a map you have not told the human about.

For each map the human says yes to, on the export `report` just wrote:

```bash
devops/dev.sh manage calibrate_map /abs/<dir>/<id>-<name>.json --commuters N --out /abs/<dir>/<id>-<name>.calibrated.json
```

`N` is the commuters the report printed for the map: the count stays what it was unless the human
asked for another (that is `map-modify`, `commuters`). `--speed <km/h>` instead of `--commuters` is
`map-create`'s way of finding a count on a new map; do not use it here. Read the table as in
`map-create`: `nicht da` is 0 in every row. Then write it to the map:

```bash
python3 .agents/skills/check-up/checkup.py write <map> /abs/<dir>/<id>-<name>.calibrated.json
```

It puts the count, the share of the timetable, the table and the time the run **started** on the
map's row, and refuses a file of another map. The start is on purpose: an edit made while the run
was going still counts as made after it, and the map stays `veraltet` until measured again.

Run `report` again and say what it now shows.

## does a round play

`calibrate_map --commuters N` is that check: it plays real rounds on the real router in a database
of its own, and its table has `nicht da` 0 in every row when everybody gets home. A map that is up
to date was played this way when it was measured. For a map the human wants checked without
measuring it again, run `calibrate_map` without `--out`, with the same ask-first.

## tell the human

- per map, one line: in order or not, measured when, edited since or not;
- which maps you measured again, with the table's `nicht da`, and the new date;
- what you did not do, and why (not asked, takes too long, `check_map` failed).

## don't

- Don't start a game on the instance to see whether a round plays.
- Don't start a long measurement without asking.
- Don't edit a map here: what is off is `map-modify` or `map-versions`.
- Don't write a count or a share you did not measure. `write` takes only the file `calibrate_map
  --out` made.
