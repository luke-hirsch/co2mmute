---
name: map-modify
description: Fix what is off on a built co2mmute map itself, in its base version, after talking it through: which towns a village commutes to, how many commute, a footpath, a moved stop, a street the rules left out. Use when someone says what is wrong with a map ("Callenberg's people work in Glauchau", "the stop is on the wrong side", "this footpath is missing"). Changes for the ballot are map-versions.
---

# map-modify

The conversation `map-create` leaves out. The builder has one set of rules for every area, and what
they cannot fix comes out as a line in its report. This skill is for those lines, and for whatever a
person who knows the place sees on the map. It changes the **base version**; a change the class
should vote on is `map-versions`.

There are no heuristics here. A village's commuter towns, a statistic, a shortcut: only the human
knows or chooses them. For each case the skill **lays out what the map has, asks, and writes what
was answered**. Never pick a town, a count or a place from the map alone.

## before you start

- A staff account on the instance the map is on, and `python3` (standard library only).
- `CO2MMUTE_URL` (the instance; default `http://127.0.0.1:8000`, Django itself), `CO2MMUTE_USER`
  and `CO2MMUTE_PASSWORD`.
- **Whether any game ever ran on the map.** `modify.py` edits the map in place, so ask the human, and
  see "after every change" if one did.
- A clone with `npm ci` done in `frontend/`, for the re-measuring at the end (see `map-create`).
- To look a name up on the map, `python3 .agents/skills/map-versions/versions.py find <map> <text>`
  prints streets, nodes and lines with their ids.

`modify.py` makes the calls the map editor makes (`frontend/src/lib/queries/map-editor.ts`), one
command per case, each printing what it did. Every command that writes first saves the map's export
into the current directory and says where. Names follow the editor's rule: never empty, never
"Knoten 12" or "Kante 3"; the script refuses both.

```bash
python3 .agents/skills/map-modify/modify.py maps
python3 .agents/skills/map-modify/modify.py places <map>
```

`places` prints the commuters, whether they are measured, the map's size and scale, and every home and
workplace with its node id and place. Read it out to the human first.

## the cases

### which towns the village commutes to

**Lay out:** the homes and workplaces `places` prints; the map's edge on the side the town lies
(`modify.py edge <map> east 8` prints the outermost nodes on that side, with the distance to the
map's border); the builder's heads-up about places it could not connect.

**Ask:** which towns people commute to, and with what source (a Land's statistics office counts each
municipality's out-commuters). For each town, which of the outermost nodes on its side is where the
road leaves toward it. Bordering towns with their road distances are the human's to name; don't
list them from memory.

**Write:** a node on that road becomes the town's workplace (or a home, for people coming in):

```bash
python3 .agents/skills/map-modify/modify.py place <map> <node> workplace "Arbeit Meerane Zentrum"
```

The name follows the builder's: `Arbeit <Ort> Zentrum`, `Wohnort <Ort>`. A node that is already a
place is refused. The place now counts: people are dealt to every workplace. `place` only **adds**.
Moving a place means adding the new one here; taking the old one away is the map editor's.

### how many commute

**Lay out:** the map's count and whether it was measured (`places`).

**Ask:** the number and its source, with year (for Callenberg 1 800, from the Land's statistic of
out-commuters). A statistic gives a headcount. The game's count is car demand, calibrated so that
everybody driving matches the city's rush-hour speed (`map-create`, step 4); a headcount stands in
for it only where no speed source exists, as for a village TomTom doesn't list. Say so.

**Write:**

```bash
python3 .agents/skills/map-modify/modify.py commuters <map> 1800
```

It sets the count and `calibrated` to false: the number was not measured on this map. Measure it
(below), or leave the map unmeasured and say so. The source is not stored on the map; tell the
human to keep it, and name it in your answer.

### a footpath

**Lay out:** the two nodes (look them up with `python3 .agents/skills/map-versions/versions.py find <map> <text>`), and the streets at each.

**Ask:** which two places, a name for it, and whether bikes may use it.

**Write:**

```bash
python3 .agents/skills/map-modify/modify.py footpath <map> <from> <to> "Fußweg Hochufer – Weidensdorf" [--no-bike]
```

Both directions, walking, and biking unless refused. A path of that name between those nodes in that
direction already: the server says so and nothing is written.

### a moved station or stop

**Lay out:** the node and where it is (x, y in map units; one unit is the scale in metres), and the
lines on the edges at that node (`python3 .agents/skills/map-versions/versions.py find <map> <text>`
prints the lines per edge).

**Ask:** where the stop belongs. `move` takes x and y, so it can only be done mechanically when the
target is a home or workplace, whose x and y `places` prints (or an outermost node, `edge`): ask the
human for that place and move the node onto it. For any other target (a street, a corner, "a bit
further north") there is no x and y to read: ask the human to drag the node in the map editor. The
stop on a *different* node is the map editor's as well.

**Write:**

```bash
python3 .agents/skills/map-modify/modify.py move <map> <node> <x> <y>
```

The edges at the node follow with their bend; lines stay on it. It prints the metres moved, and it
moves the node, junction or not. A stop on a different node is the map editor's, never a version.

### a street the rules left out

**Lay out:** the two nodes it joins and what the map has between them (`python3 .agents/skills/map-versions/versions.py route <map>
<from> <to>` prints the way a bus would take today).

**Ask:** the street's name, its lanes and its speed, and one way or two.

**Write:**

```bash
python3 .agents/skills/map-modify/modify.py street <map> <from> <to> "Verbindungsstraße Auestraße" 1 50 [--oneway]
```

One link per direction, each with its street. A line over it, a bus lane or a tram track is the
editor's.

## after every change

A changed map is checked again:

```bash
python3 .agents/skills/map-modify/modify.py export <map> /abs/map.json
devops/dev.sh manage check_map /abs/map.json
devops/dev.sh manage calibrate_map /abs/map.json --commuters N --out /abs/map.calibrated.json
```

`check_map` says `in Ordnung`, or lists what broke: then stop and give the human the lines. A change
of **places or the count** (the first two cases) wants `calibrate_map --commuters N` now, with the
count the human gave; read its report as in `map-create`: `nicht da` is 0 in every row, the speed
reached, the car share normal allows. A footpath, a street or a moved stop wants `check_map` now,
and `calibrate_map --commuters <the map's count>` before the map is played; say which of the two
was done.

`modify.py` edits the map **in place**. Before the first write, check that no game ever ran on it
(the same check as `map-versions`: none running, none played). If one did, export the map, import the
export as a new map (`/app/maps/upload`) and edit that one; the original stays as it is with its
games. A map no game has seen can be edited where it is, and the calibrated file is uploaded as a
new map beside it.

## tell the human

In German, with du, short:

- what changed, one line each, with the node ids and names;
- the commuters and their source, and whether the count is measured now;
- what `check_map` and the calibration said;
- where the export before the change is, and where the new map is (instance, name, id).

## don't

- Don't choose towns, a count or a place from the map. Ask, with the data laid out.
- Don't edit the export file by hand, and don't write to a map without the export `modify.py` takes.
- Don't tune a number to reach a target. Say the gap.
- Don't draw what the class should vote on here; that is `map-versions`.
- Don't give a node or an edge the name the editor would refuse.
