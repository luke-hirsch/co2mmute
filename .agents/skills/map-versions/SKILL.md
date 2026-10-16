---
name: map-versions
description: Turn changes said in words ("a bus lane on the Turmstraße", "the 101 every 10 minutes") into versions of a co2mmute map, with their ballot questions and combinations, checked and measured. Use when someone wants a ballot for a map, or a change for the class to vote on.
---

# map-versions

A version is the map with one change. The class votes between versions after each round, so a
ballot is a few changes, every combination of them, and two questions each: the one to bring the
change in, the one to take it back. `versions.py`, next to this file, does every write over the
instance's own API; this skill is which change is which recipe, what to ask, and what to tell the
human.

## before you start

- An instance with the map on it (the local stack, `devops/dev.sh up`, or any other), and a staff
  account. Set `CO2MMUTE_URL` (Django itself: `http://127.0.0.1:8000` on the local stack),
  `CO2MMUTE_USER` and `CO2MMUTE_PASSWORD`.
- `python3 .agents/skills/map-versions/versions.py maps` lists the maps with their ids.
- **Export the map first** (`versions.py export <map> /abs/before.json`). Maps are hours of work and
  the export is the only backup.
- No game may be running on the map, and none should have been played on it: a version a game has
  seen can't be deleted again.

## ask the human, once

The changes, in words, **at most four**: four make 15 versions (every combination), more is a
ballot nobody reads. Each change touches its own streets and lines: two changes on the same street
or the same line can't be combined, and `ballot` refuses them.

## the changes

There are five kinds. Anything else (a new street, a moved stop, a new place) is not a version:
it is a change to the map itself (`map-modify`), or a drawing in the map editor.

| kind | in words | what it does |
| --- | --- | --- |
| `bus_lane` | "eine Busspur auf der …" | one car lane of each edge becomes a bus lane |
| `interval` | "der 101 alle 10 Minuten" | a line's interval in minutes |
| `close` | "die … für Autos sperren" | the street goes; a path for feet and bikes takes its place |
| `bus_line` | "ein Bus von … nach …" | a new bus line along the shortest streets, there and back |
| `footpath` | "ein Weg von … nach …" | a path for feet and bikes between two existing nodes |

### 1. find what the words name

```bash
python3 versions.py find <map> "Turmstraße"
python3 versions.py find <map> "101"
```

It prints every street, node and line whose name contains the text. A street comes as stretches
(`STRASSE Turmstraße #1`), each with its two ends, its edge ids (`kanten [...]`) and one line per
edge: from → to, lanes, speed, bus lane, the lines on it. Unnamed nodes are named by their
corner (`Ecke Beusselstraße / Turmstraße`).

**More than one hit: ask.** Show the human the hits by their ends ("die Turmstraße zwischen
Beusselstraße und Lübecker Straße, oder …?") and let them pick. A stretch is often longer than
meant; the human may want only some edges of it — then take only those ids. Never pick for them.
A line usually comes twice, one per direction (`Bus 101` and `Bus 101 reverse`): an interval
changes both.

### 2. write the change file

One JSON file per change. `name` is short and says the change ("Busspur Turmstraße"); it is how
the change is shown on the ballot and in the combinations' questions.

```json
{
  "name": "Busspur Turmstraße",
  "poll_text": "Soll auf der Turmstraße eine Autospur zur Busspur werden?",
  "revert_poll_text": "Soll die Busspur auf der Turmstraße wieder eine Autospur werden?",
  "changes": [{"kind": "bus_lane", "edges": [453, 454, 455, 456]}]
}
```

`changes` holds one or more steps, all of one change: both directions of an interval, both
directions of a street.

- `bus_lane`: `"edges"` from `find`. On an edge with one lane the bus lane takes the only lane and
  **closes the street to cars**. `add` refuses it until you have told the human and they still want
  it; then add `"closes_to_cars": true` to the step. A bus lane where no line runs only takes a lane
  away; `add` says so.
- `interval`: `"line"` as `find` prints it (`"Bus 101"`, `"Bahn S41"`, `"Tram M10"`), `"minutes"`.
- `close`: `"edges"`. A street a line runs on can't be closed — the line would break. Ask whether
  a bus lane is meant.
- `bus_line`: `"line_name"`, `"minutes"`, `"there"` and `"back"`, each a list of edge ids from
  `versions.py route <map> <from node> <to node>` (and the same the other way). The stops are
  every node on the way. The route is the shortest along streets; if the human wants it along
  another street, route it in pieces through a node on that street and join the lists.
- `footpath`: `"from"` and `"to"`, two node ids. `"biking": false` for feet only.

**The questions.** In German, with du, as a yes/no question, no explanation and no reason: the
explanation is on the waiting screens, not on the ballot. `poll_text` asks for the change
("Soll der Bus 101 alle 10 statt alle 17 Minuten fahren?"), `revert_poll_text` asks to take it
back ("Soll der Bus 101 wieder alle 17 Minuten fahren?"). Name the street or line as the map does.

### 3. add it

```bash
python3 versions.py add <map> /abs/busspur.json
```

It prints the new version's id and what it noticed. One `add` per change; `list <map>` shows them
all with their questions, `delete <map> <version>` takes one back.

## the ballot

Once every change is added, **in one call**:

```bash
python3 versions.py ballot <map> <version> [<version> ...]
```

One change: the base and the change are on the ballot together. Two to four: every combination is
made, with its own questions ("Sollen die Änderungen »A« und »B« zusammen umgesetzt werden?"), and
each version is paired with the ones one change more or less. Run it once with every change: a
second run with one more change would make the first run's combinations again. If you have to,
`delete` the combinations it names first.

Then export and check:

```bash
python3 versions.py export <map> /abs/ballot.json
devops/dev.sh manage check_map /abs/ballot.json
```

`check_map` must say `in Ordnung`. Anything else is a defect in the versions: give the human its
lines, don't hand-edit anything.

## measure

For the author, never for the ballot: what each version does at 100, 50 and 0 % car. On the
exported file, one version at a time, keeping the map's commuters, `<N>` (`export` prints them):

```bash
DJANGO_DB=postgres devops/dev.sh manage calibrate_map /abs/ballot.json --commuters <N> --map-version "Busspur Turmstraße"
```

It plays the version at 100, 75, 50, 25 and 0 % car, six seeds each; read the rows for 100, 50
and 0. A village takes a minute, a city part a few, a whole city much longer: run it in the
background with a log. One run at a time (each run's database is the app's name plus
`_calibrate`). Measure the base the same way, without `--map-version`, to have something to
compare against. **`nicht da` is 0 in every row**; anything else is a defect, not a result.

## tell the human

In German, with du, short:

- each change: its name, what it does in one sentence, and both questions;
- how many versions the ballot holds, and that `check_map` passed;
- per version against the base: kg CO₂ per person and travel time at 100, 50 and 0 % car;
- anything `add` noticed: a street closed to cars, a bus lane with no line, a line in one direction
  only;
- where the backup export is.

## don't

- Don't change the map in the editor's base version to make a change fit. A version is one change
  on the base as it is.
- Don't pick a stretch, a line or a node for the human when `find` shows more than one.
- Don't write questions that explain or argue. Ask, in du.
- Don't put a measured number on the ballot.
