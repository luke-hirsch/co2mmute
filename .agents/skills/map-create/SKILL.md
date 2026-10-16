---
name: map-create
description: Build a playable co2mmute map of a real place from OpenStreetMap, check it, measure its commuters and what the budget buys on it, and upload it. Use when someone wants a new map of a town, a city or a part of one ("a map of Weimar", "our district for a class").
---

# map-create

A real area, from its name to a map the game can play. `build_map` builds it, `check_map` checks
it, `calibrate_map` measures it, the upload puts it on an instance. The commands do the work; this
skill is their order, the two things to ask, how to read what they print, and what to tell the
human at the end.

The bar is **playable, not perfect**. The builder has one set of rules for every area, and what
they cannot fix is a line in its report. You pass that line on with a suggested fix. You don't fix
it in the builder, and you don't edit the file.

## before you start

- A clone set up natively as in `README.md`, with `npm ci` done in `frontend/`: the calibration
  routes with the game's own router, under Node. Run everything on the native stack — the backend
  container has no `frontend/`.
- Postgres (the README's, for the suite, is enough). The calibration runs on it.
- The internet, the first time an area is built: OpenStreetMap over Overpass, Nominatim, the
  Zensus 2022 grid, GHSL tiles, DELFI's timetables. It all stays in `backend/mapbuild/cache/`
  (`CO2MMUTE_MAP_CACHE` moves it), so the second build of an area is offline. The Zensus and the
  timetables are a few hundred MB, once; all of Berlin with them is about 750 MB.
- A staff account on the instance the map goes to.

`devops/dev.sh manage <command>` runs `manage.py` in `backend/` with the app's environment, so
**every file path you pass is absolute**.

## ask the human, once, up front

1. **The area.** A municipality's name ("Bremen", "Callenberg") is built as its boundary, with the
   roads 1 km past it. Anything else — a district, a Kiez, an area across a border — is a box: south,
   west, north, east in degrees, built as it is.
2. **How fast the city drives in the morning rush, with its source.** The TomTom Traffic Index has
   a page per city (`tomtom.com/traffic-index/<city>-traffic/`): take the city's morning-rush speed
   in km/h, the latest year, and write down year and page. Berlin: 19.0 km/h, 2025 data. A box takes
   its city's figure. A place TomTom doesn't list needs a commuter count with a source instead (a
   Land's statistics office counts each municipality's out-commuters). If there is neither, ask; never
   guess one and never take another city's.

Nothing else is a choice. There are no road classes, no detail level, no number of homes or nodes
to pick: the rules decide, the same everywhere.

## 1. build

```bash
devops/dev.sh manage build_map "Bremen"
devops/dev.sh manage build_map --bbox 52.49,13.29,52.56,13.42 --name "Berlin Mitte-West"
```

`--out /abs/path.json` puts the file somewhere else; otherwise it lands in the area's cache
directory, `backend/mapbuild/cache/<area>/`, which git ignores. If the public Overpass instance
keeps answering 504, run the command with another one, e.g.
`OVERPASS_API_URL=https://overpass.kumi.systems/api/interpreter`. The download already waits,
retries and splits a box that is too big; a source that stays down stops the build with one
sentence.

Then open `backend/mapbuild/cache/<area>/area.json` and check `display_name` is the place meant.
Nominatim takes the most local whole municipality of that name ("Bremen" is the city, not the
state), and a name like "Neustadt" has many. Wrong place: delete that directory and build again with
the full name ("Neustadt an der Weinstraße") or a box.

The build stops, with nothing written, when:

| it says | it means | do |
| --- | --- | --- |
| `Nominatim kennt keine Verwaltungsgrenze namens …` | no municipality by that name | the official name, or a box |
| `Keine Zensus-Zellen in diesem Gebiet …` | the area is outside Germany | stop and tell the human: the homes come from the Zensus, which covers Germany only |
| `Keine GHSL-Zellen …` | no buildings in the area | check the area |
| `nicht erreichbar: <url> …` | a source is down | another Overpass instance, or later |

## 2. read the build report

The report comes in sections. Most lines say what a rule did and need nothing. These need the human:

- **Gebiet** — `Teil der Grenze weggelassen: … km² bei …`: a piece of the municipality away from
  the rest is left out (Bremen's port in Bremerhaven). Say which.
- **Straßen** — `keine beschilderten 50er und 100er Straßen …`: every road without a sign takes its
  class's default speed. Say so.
- **Anbindung** — `auch über <class> kein Weg hin und zurück, an den Hauptstraßen: …` and
  `danach noch weiter als 500 m vom Netz: …`: places whose way onto the streets is long. Pass on
  the longest few with their metres.
- **Karte** — `Wohnorte k von n` or `Arbeitsorte k von n` with k below n: places that found no
  node. `N Knoten nicht stark verbunden, weggelassen (…)`: a piece of street a car can't leave or
  can't reach is dropped; say so if a place's street is named.
- **Bus und Bahn** — `Takte: … — aus einem Ersatz: …`: lines whose interval is not from the
  timetable but from OSM or, failing that, the defaults (U-Bahn 5, S-Bahn 10, regional 60, tram 15,
  bus 20 min). List them. `Pendler N (ein Platzhalter bis zur Kalibrierung), Haltestellen …,
  Bahnhöfe …`: the counts for the summary; the commuters are replaced by step 4.
- **Achtung** — every line here goes to the human, each ends in its own `Vorschlag: …`:
  - `auf dieser Karte fährt kein Bus und keine Bahn`: the map plays car, bike and foot only.
  - `kein Fahrplan für dieses Gebiet …`: all intervals from OSM or the defaults.
  - `N Orte ohne Halt im Umkreis von 1000 m (…): …`: no stop of a kept line within 1 km of these
    places — OSM has no line there and the timetable had none to stand in (or there is no
    timetable). Fix: a version with a line there (`map-versions`), or a workplace or home added
    on a node that has a stop (`map-modify` `place`; taking the old one away is the map editor's).
  - `N Orte, die der Halt erst bediente, bevor er auf seinen Knoten rückte, jetzt weiter als 1000 m`:
    the stop was within 1 km in OSM and took a node up to 100 m away. Fix: move the stop's node
    closer to the place (`map-modify` `move`).
  - `N Orte, deren Halt zu Fuß weiter als 1000 m entfernt ist, obwohl er in der Luftlinie näher
    liegt, auch über die Nebenstraßen`: the cover counts the crow, the walk follows the map's links.
    The build has already laid a path wherever OSM's side streets walk the place to a stop within
    1 km (`Fußwege zum Halt über die Nebenstraßen: N gelegt` under "Bus und Bahn"); these are the
    places where even they don't. Fix: a footpath, in the map itself (`map-modify`) or as a version
    (`map-versions`), where the human knows a way the side streets don't show — else a stop.
  - `N Linien ohne Fahrt zwischen 8 und 10 Uhr im Fahrplan (…): …`: the timetable knows the line
    but has no trip in the morning window; the game then runs it once a pass. See below. Fix: a
    version with an interval for the line (`map-versions`).
  - `Arbeitsorte, zu denen nur ein Bus fährt: <Linie> für k von n …`: for k workplaces that bus is
    the only line. See below. Fix: a version with a second line or a shorter interval, or a workplace
    added where more lines run (`map-modify` `place`; taking the old one away is the map editor's).

**A line with no morning trip, or workplaces with only one bus.** Say it plainly: the people who
work there ride a bus that hardly runs in the morning, so they wait, and every line keeps running
until the last of them is home — the timetable runs long because of it. Bremen's 80 at the
steelworks is the case: a shift bus with no trip between 8 and 10, the only line for 26 of 164
workplaces, and most of Bremen's waiting. Suggest a version that gives the line a morning interval
(`map-versions`, `interval`), or add a workplace where more lines run (`map-modify` `place`; taking
the old one away is the map editor's). Don't touch the builder for
it, and don't edit the file.

**The credits** (the file's `credits` field, labelled "Quellen" on screen) are written into the file by the build, for the sources it used:
OpenStreetMap, the Zensus, GHSL, DELFI. Nobody adds or edits them by hand. A calibrated copy and
the upload carry them on.

For each, suggest a fix in a sentence, after the upload: a footpath, a street, a moved stop node or a
place added is `map-modify`; an interval or a new line is `map-versions`; anything else (a stop on a
different node, a place taken away) is the map editor.

## 3. check

```bash
devops/dev.sh manage check_map /abs/path/to/map.json
```

A built map passes (`in Ordnung`). If it doesn't, that is a defect of the builder: stop, give the
human the check's lines, and don't touch the file.

## 4. calibrate

```bash
DJANGO_DB=postgres devops/dev.sh manage calibrate_map /abs/map.json --speed 25.9 --out /abs/map.calibrated.json
DJANGO_DB=postgres devops/dev.sh manage calibrate_map /abs/map.json --commuters 1800 --out /abs/map.calibrated.json
```

It finds the commuters (as many as make a morning where everybody drives as slow as the city's rush
hour), then plays real rounds at 100, 75, 50, 25 and 0 % car, six seeds each, in a throwaway
database. A village takes a minute, a city of half a million about a quarter of an hour, all of
Berlin about forty minutes, the six seeds side by side. Run it in the background with its output
in a log, and read the log when it ends. **One at a time**: each run's database is the app's name
plus `_calibrate`, and a second run drops the first one's. Never SQLite for a file: its numbers
are about 1.5 % off (the report says `Gemessen auf SQLite`).

Read its report:

- `Pendler: N — alle im Auto fahren morgens X km/h, Ziel Y km/h`, then the `gemessen:` lines of the
  search. X close to Y: done. X far from Y: the map tips — a count that still flows next to one
  barely bigger that stands. The command answers the last count that flows. Give the human both lines; don't pick a count by hand.
- `nie fertig`, and `ERROR … The 1000-tick guard stopped …` in the log during the search: a count
  so big its rounds never end. Expected while searching.
- `Normal, 2,4 kg pro Person und Runde, reicht hier, wenn N % der Gruppen Auto fahren` (or `auch,
  wenn alle …`, or `nicht einmal für eine Runde ohne Auto`): how hard the map is at the normal
  budget. Report it as it is; the map keeps its difficulty, and a host moves the budget when
  creating a game. Followed by `Nicht spielbar` (nicht zu gewinnen / nicht zu verlieren): the
  normal budget leaves no game on this map. Tell the human which, with the tip the report gives —
  can't be won: more kg on the dial, or thin out the timetable (fewer lines, a longer interval;
  buses and trains run whether anybody rides or not); can't be lost: fewer kg.
- `Anteil am Fahrplan: F`: the share of the timetable's CO₂ and cost the class pays, written into
  the file. `nicht messbar`: no lines, or nobody rides at 50 % car.
- the table: **`nicht da` is 0 in every row.** Anything else is a defect of the map or the model,
  never a result: stop, don't upload, give the human the row and the log's lines.
- `N Gruppen hatten in ihrem Verkehrsmittel keinen Weg …`: pairs of home and workplace with no way
  by bus and train (or by car). Pass it on with the build report's places.
- `Eine Runde ohne Auto kostet hier mehr als eine, in der alle fahren …`: the timetable runs whether
  anybody rides. On a sparse map that is what the map teaches; say it.

`--out` writes a copy with the commuters, `calibrated: true`, the share and the table (`co2_table`:
kg per person per round at each car share, which the create form reads to say "bei 2,4 kg bis N %
Auto" and "nicht spielbar" at both ends). That copy is the map.

## 5. upload

On any instance: `/app/maps/upload` ("Karte hochladen"), logged in as staff — the calibrated file, a
name, no background image. On the local stack the same upload as a script:

```bash
cd frontend && E2E_MAP=/abs/map.calibrated.json E2E_MAP_NAME="Bremen" node e2e/seed.mjs
```

(`E2E_BASE_URL`, `E2E_USER` and `E2E_PASSWORD` say where and as whom; see the script's head.) An
upload always makes a new map. **A built map never goes into `map_examples/` or into git** — that
folder is the hand-drawn map that is played. A built map lives in the database, and its export
(`api/maps/<id>/export/`) is its backup.

## 6. tell the human

In German, with du, short:

- the area (`display_name`), and nodes, edges, homes, workplaces, bus and train lines from the report;
- the commuters, the speed reached against the target, and the target's source;
- the car share normal allows, and the share of the timetable;
- what the rules could not fix, one line each, with its suggested fix;
- where the map is: the instance, its name and id.

## don't

- Don't add an option, a cap or a special case to `backend/mapbuild/` for one area. A rule that
  fits only some areas is not a rule. A problem that turns up on several areas goes to the human:
  it may earn a rule, with a test of its own on hand-made inputs (`backend/mapbuild/tests/`,
  offline — no test downloads anything).
- Don't edit the built file. What the rules didn't do is a change on the uploaded map.
- Don't tune a number to reach a target — not the count, not the speed. Say the gap.
