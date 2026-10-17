# AGENTS.md

Instructions for a coding agent working on co2mmute. Setup, running and deploying are in
`README.md`; how the game is played in `docs/de-quick-start.md`; how it runs, box by box, in
`docs/en-flowcharts.md`. This file is what those don't say: the rules that bind, and the places that
have to change together.

## what it is

A browser game for a classroom. A host opens a game, players join by QR code, each gets a home and a
few Gruppen of commuters, and every round they pick a mode and a route per Gruppe. The server
simulates the round — a link queue model, there and back — and reports CO₂, cost and travel time.
Between rounds the class votes on a change to the map (a bus lane, a new line) and plays the next
round on it. The game ends on a CO₂ budget or a round limit.

It is a hybrid. Django serves the landing page, the docs under `/docs/`, the legal pages, login and
everything else about credentials, and the admin. The React SPA under `/app/` is the join, the game
screens, the host's own pages and the map editor. The line between them: anything about **games** or
the **host's own account** is React; anything that **re-authenticates** (login, sign-up, password,
account deletion) stays Django, because the host machine stands in a classroom, projected and often
still logged in.

## players are minors

The game is designed for school students. A player has **no account, no login, no e-mail** — a
screen name is the only thing collected. That is a requirement, not a gap: never solve a problem with
player accounts or a third-party identity. A host may be logged in while playing a seat in someone
else's game; that login must never link an account to a player.

- Player names never reach a log or an error report (`game/tests/test_privacy.py` catches it).
- A game is anonymised once it has been over for `ANONYMISE_GRACE_HOURS`: names become "Spieler N",
  the QR image goes, every move and result stays (`game/anon.py`, an hourly beat job,
  `manage.py anonymise_games` by hand).
- A host deleting their account keeps the row and loses everything on it, and their running games
  end — `GameSession.game_host` is CASCADE, and the games are research data.
- In a study game a participant code is collected too (`studies`, below). The site cannot tie it
  to a person: it stores which seat used a code, never whose code it is, and no one tries to.
- Anything new that stores player-written text needs an answer for how long it is kept before it
  ships. When what the site stores changes, `backend/template/legal/dsgvo.html` and `cookies.html`
  change with it.

## words

User-facing text is German and says **du**, legal pages included. A game agent is a **Gruppe**, the
host machine is the **Leitstelle**, the sum over all Gruppen is **alle Pendler**. No school words
("Klasse", "Lehrer", "Schule") in the interface; the tests allowlist the few places a host names
their own game. In code and in the API the old names stay: `agent`, `people_per_agent`,
`AgentSimulationResult`.

## how it fits together

**One way in for every code: `/app/join/<CODE>`.** The QR code, the landing page and the header all
point there, and so does a seat's QR. The length says what a code opens (`game/codes.py`): a game id
is six characters, a seat code seven. One endpoint, `api/game/code/<CODE>/`, looks on GET and takes
on POST; the screen renders by the kind it answers. Another app can register a longer kind from its
`AppConfig.ready()`; `game` never imports it. Misses are counted per address for bearer tokens
only (a seat code), never for a game id: a class mistypes the projector.

**Two kinds of auth.** The host is a Django user with a session. A player holds two cookies signed
with `SECRET_KEY`, `game_access_<id>` and `player_<id>`, set only through `set_game_access_cookie` /
`set_player_cookie` in `co2mmute/utils.py` and resolved by `game/auth.py`. Rotating `SECRET_KEY` or
changing what goes into a cookie logs every player out of every running game.

**The host has a `Player` row.** Find it by account — `Player.objects.host_rows()` /
`without_host_rows()` — never by `controlled_by_host`, which means "played at the Leitstelle".

**One counting rule:** `Player.objects.filter(game=…).playing()` — still in the game, not the host's
own row. Rounds, phases, the lobby limit and the summary all use it. Don't spell it out again.

**A seat moves between devices** (`game/seats.py`). Takeover and handover keep the row and give it a
new `player_id`, which makes every old cookie worthless. The handover code is a seven-character bearer
token in the cache, not a signed value — it has to be readable off a projector.

**The round loop runs on Celery.** `game/rounds.py:complete_round_if_ready` is the one decision
point; reach it through `schedule_round_completion_check`. Don't add another sender.

**Between-round phases** live in `game/phases.py`, and every transition is a claim:
`filter(pk=…, between_round_phase=FROM).update(…) == 1`. Broadcast after the atomic block, from sync
code — never call `async_to_sync` from a consumer.

**A refused socket accepts first, then closes with its 44xx code** (`consumers.refuse`). Closed before
`accept()`, the browser sees 1006 and the client retries a permanent refusal.

**An outcome is recorded when it happens**, never derived later: `GameSession.end_reason`,
`GameRound.vote_result`.

**Pendlertypen belong to their game** (`game/personas.py`). A `Persona` with no game is a standard
one, seeded by a migration and edited in the admin. A game copies the ones its host picked when it
is created and deals them at join, one per Gruppe, as `persona` in `agent_assignments`. Never point
a Gruppe at a standard row: editing it would change the debrief of every game it was played in.

**A Gruppe's home is its own** (`game/deal.py`). Each entry of `agent_assignments` carries its
`home_node` and `destination_node`, dealt at join. Off, the default, a seat's Gruppen share one
home. "ausbalanciert" (`GameSession.balanced_deal`, set at creation and never after) gives every
home and workplace the same number of Gruppen, give or take one, over the seats still playing, and
spreads a seat's Gruppen over the map in the game's halves order. The route check, the round screen
and the debrief read the Gruppe's home, never the seat's. The calibration plays every home with
every workplace either way.

**The `studies` app is optional.** Commented out of `INSTALLED_APPS` it is off: no urls, no
"Studien" menu, the `studies` flag in the auth payload false, no section in the privacy page, no
tables in the research export. `game` never imports it (a foreign key from a game to a study would
break `game` and its migrations with the app off; `co2mmute/tests/test_sanity.py` refuses any
import). It plugs in at seams registered from its AppConfig: the code kinds of the one way into a
game, and the export tables (`game.research_export.register_tables`). A study groups games; its
participant codes, all of one length that tells them from a game id and a seat code, are
optional, and a study without them is a collection of normal games. Staff only, reading too: a
code is a bearer token.

**`game/urls.py` order is load-bearing.** `<game_id>/` and `<game_id>/<player_id>/` swallow any one-
and two-segment path, so literal prefixes go first. A route in the wrong place answers a plausible
403, not a 404 — pin routes with `resolve()` in tests.

**Rate limits count failures, per address** (`co2mmute/throttle.py`) — wrong passwords, wrong seat
codes; sign-up counts accounts made. A class is one school NAT, so counting attempts would throttle a
room for playing. Read `X-Real-IP`, never `X-Forwarded-For`, and never count per username: that locks
a host out of their own game.

**One `validate` per serializer.** A second definition silently replaces the first;
`co2mmute/tests/test_sanity.py:NoShadowedMethodsTests` refuses it. Add to the existing method.

## the simulation

`backend/sim/` is the engine — plain Python, no Django. `game/simulation.py` is the adapter: it reads
rows into a `Scenario`, runs it, and writes result rows. `TrafficSimulator` subclasses the engine, so
an adapter method must never take an engine method's name.

- **A link queue model.** Free-flow time, flow capacity, storage capacity; a full link blocks the one
  behind it. Speed is an output, measured over cars. There is no speed floor — don't add one.
- **Each direction of a street is its own link.** `lanes` counts the whole street; a bus lane, a
  bike lane and a tram's own track each take a car lane, and zero car lanes is a legal gate, closed
  to cars only.
- **Where the rails lie is the street's** (`StreetEdge.tram_track`, `"type": "tram"` in the file).
  Rails beside or under a street run free (the U2 under Bismarckstraße); rails in the car lane queue
  with the cars and hold them up (the M1 on Friedrichstraße north); a tram's own track takes a lane.
  The engine asks the link, not the line, whether something on rails queues.
- **On a ring the ring has right of way** (`StreetEdge.junction`: OSM's `roundabout` or
  `circular`, the ring square of Ernst-Reuter-Platz). A car about to drive onto a ring link from
  outside the ring waits while a ring link leading into it has a car through and bound there
  (`_ring_goes_first`). That is giving way, not being stuck: the deadlock escape never counts it.
  On a square with signals the right of way stands in for them, as the jam stands in for traffic
  lights. The builder writes `junction`; a ring drawn by hand has none until the admin sets it.
- **Whoever sets off lets the street's traffic go first** (`_street_goes_first`, StVO §10): a car
  pulling out at its door waits while a link into that node has a car through and bound for the
  same link. Without it the cars pulling out took every place a jam freed and kept a loop of
  streets locked. A line's run leaves its terminus on time.
- **The way home spreads wider than the way there**: the evening's σ is the morning's times
  `EVENING_DEPARTURE_SPREAD` (1.6, SrV 2018 Berlin, in `sim/constants.py`). Only the ratio is
  sourced; the morning's σ is the game's.
- **Nobody is stranded.** A pass runs until everyone has arrived, and every line keeps running while
  anybody is out. A non-arrival is a defect, never a third metric.
- **Society pays for the timetable**: a line emits and costs per vehicle-km whether anyone rides or
  not, and that counts against the budget. The class pays its share of it: every vehicle-km's CO₂ and
  cost times `GameMap.timetable_factor`, the riders' shares, the empty lines and the runs past the
  timetable alike — the lines run a city's timetable for a few thousand of its people. The share is
  what the class's riders would emit in buses and trains as full as Germany's (the Umweltbundesamt's g
  per person-km, `sim/constants.py`) over what the base timetable emits, on the map's round where half
  drive, never more than 1; 1 until measured. It changes the bill, not the round, and never the
  ticket. A game copies it when it starts (`GameSession.timetable_factor`), so a recalibrated map
  never moves a running game.
- **The round is seeded** from the round's pk. A test asserting an exact number passes `seed=`.
- **Units:** `people_per_agent` is derived (`district_commuters / (seats × Gruppen per seat)`), never
  picked. `AgentSimulationResult.total_co2_g` is per person × `people_per_agent`; `mean_cost_eur` is
  per person; `GameSession.max_CO2_level` is in kg.
- **The commuters are the map's, the budget is the game's.** `GameMap.district_commuters` and
  `calibrated` (true only for a count measured on that map) belong to the graph. The budget is kg of
  CO₂ per person per round, the same on every map: the create form's dial (0.6–6.0 kg in 0.2 steps,
  normal 2.4, a commute inside Germany's 2030 climate target — `CO2_KG_PER_PERSON_*` in
  `game/calibration.py`, mirrored in
  `frontend/src/lib/calibration.ts`), recorded as `GameSession.co2_kg_per_person`. The game ends on
  `max_CO2_level` = kg × the map's commuters × rounds — the map's commuters, not the people the scale
  puts on it, because the timetable runs whether anybody rides. `docs/kalibrierung.md` says how the
  shipped map's count, its share of the timetable and normal were found. `GameMap.co2_table`
  (car share in whole percent → kg per person per round, written by `calibrate_map --out`) is what
  that budget means on the map; the create form reads it.
- **A new map is measured by one rule** (`game/calibration.py`): commuters are as many as make a
  morning where everybody drives as slow as the real city's rush hour, from a cited source (for
  Berlin the TomTom Traffic Index: 19.0 km/h in the morning rush, 2025 data). The count is car demand
  that reproduces the rush hour on that graph, not a headcount, and the model has no traffic lights,
  so the jam stands in for them — a design anchor, said so wherever it is quoted. `manage.py
  calibrate_map <file> --speed <km/h>` finds the count (`--commuters N` keeps one), then plays a
  round at each car share and reports the share of the timetable the class pays, kg per person with
  it and the car share normal buys on that map (`--out` writes count and share into the file),
  playing real rounds in a throwaway database (`game/measure.py`) on the routes the game's own router
  finds. It needs Node and `npm ci` in `frontend/`. Run it on Postgres (`DJANGO_DB=postgres`) like
  the server; the rounds of a step play side by side only there. The simulation reads its links,
  lines and routes in pk order, never by name, so a round plays the same on sqlite and Postgres.
  The count is searched in whole people per Gruppe, so it moves in steps of the Gruppen a round plays: a map with many homes and workplaces is played dealt
  (`--per-home`, 4 unless told — `calibration.PER_HOME`), each home a fresh draw of that many
  workplaces per seed, every workplace as often as the others — the seeds average it back to every
  home with every workplace. A map with too few workplaces to deal from plays every pair. Only the
  pairs the seeds deal are routed, and on Postgres the rounds of a step play side by side, one
  process each (`--workers`, `game/measure_workers.py`): they all open the one throwaway database,
  and a seeded round plays the same in any process.
- **A PT line is its type and its id.** Bus and train lines are rows of two tables, so bus 2 and
  train 2 are different lines. Whatever looks a line up by `pt_line_id` takes the segment's mode
  along. A tram is a train line run by trams (`TrainLine.kind`): it rides rails and the same router
  finds it, and its kind sets its seats, speed, figures per km and length in a queue. Only a tram
  runs on rails in the car lane — `check_map` says so.
- **A ride is on one pass of its line.** A line can pass one stop twice — in to a terminus and out
  again, round a loop — so the router (`ptRouting.ts`, `at` in its state) and the engine
  (`PTLeg.board_stop`) know where on the line a rider is, not only at which node. A rider boards
  only the vehicle that still reaches its stop, and off and on the same line at one stop is two
  rides. A line that ends where it starts is a ring and goes on round: whoever rides past its start
  stays aboard for the next departure, and the time until then is a wait. Change one, change both.
- **Two golden masters** (`game/tests/test_sim_golden.py`). Regenerate with `GOLDEN_REGENERATE=1`
  only for a deliberate change, and say so in the commit.

## maps

A map is a graph — nodes, edges, bus and train lines — with **versions**: each row carries the
versions it belongs to, so a version is a filter over one graph. `compatible_versions` between
versions *is* the ballot. A row naming no version is in no version.

- `maps/versions.py` answers "what is in this version": `put_rows_in` / `drop_rows_from` to write it,
  `delete_version` to delete one, `delete_map` a whole map — refused, like a version, once a game
  was on it. Nothing else writes membership.
- A changed street is a clone: the original stays in the versions without the change, the clone is
  in the versions with it. Compare versions by node pair, never by id.
- **The JSON file is the backup and the only way a map moves.** `GET api/maps/<pk>/export/` writes
  every version and the ballot; `POST api/maps/import/` always makes a **new** map (an import that
  overwrote one would take its games with it). `maps/portability.py` owns the format. Export before
  touching a map anyone plays — maps are hours of work.
- **An edge is as long as its road**: the straight line × the map's `scale` × `Edge.circuity`, the
  road's length over that line (1 as drawn). `Edge.length_m` is the one answer — the graph's
  `distance_m`, which both routers read, and the simulation's link. A ratio, so a dragged node takes
  the bends along. The walk and bike limits read the straight line on purpose.
- **`manage.py check_map <file>`** checks a map file against what every finished map has to keep:
  one link per direction per node pair in a version, lines whole and on their own side of the street,
  line ends where someone can board, a way from every home to every workplace and back. The rules are
  `maps/checks.py`. The upload does not run them — a map in the editor is half drawn.
- `map_examples/` is production data, not a fixture: the map that is played, tested by
  `maps/tests/test_example_map.py`.

## the map builder

`backend/mapbuild/` builds a map file from OpenStreetMap — plain Python, standard library only, no
Django, like `sim/`. `manage.py build_map <place>` (or `--bbox s,w,n,e --name …`) is the door; the
file then goes through `check_map`, `calibrate_map --out` and the import. The package docstring
lists the stages in the order they run, each module's docstring its rules.

- **One path for every area.** A place name is its administrative boundary (Nominatim, the most
  local whole municipality), roads kept 1 km past it; a box is built as it is. Secondary and up, a
  place still more than 500 m off gets one class down. A place near a stop as the crow flies but
  more than 1 km from it along the kept streets gets a path to it, as long as OSM's side streets
  walk it, where they bring it within 1 km. No city or rural fork, no caps, no number
  per city — a rule that only fits some areas is not a rule; what a rule can't fix is a line in the
  build report, never a question and never a special case in the code.
- **Downloads happen on first use and stay** in `mapbuild/cache/` (`CO2MMUTE_MAP_CACHE` moves it):
  OSM over Overpass (`OVERPASS_API_URL`; the public instance often 504s — the download waits, then
  splits the box), Nominatim, the Zensus grid, GHSL tiles, DELFI's timetables. A second build of an
  area is offline. Zensus is Germany only: abroad the build stops at the homes and says so.
- **The same inputs, the same file**, under any hash seed (`tests/test_build.py` checks it). Sort
  before iterating a set that reaches the file.
- Tests: one per rule on hand-made inputs, and one whole build of `tests/data/bremen-mitte/` (a
  real cut, ~1 MB), offline — a test that tries to download fails.

## frontend

- Every user-facing string goes through `src/lib/de.ts`. `tests/design/german.test.ts` reads every
  `.tsx` for English.
- **One source of truth per game**: REST seeds the snapshot, the WebSocket owns every update after,
  a reducer applies them. No `refetchInterval`, no `refetch()` from a socket callback.
  `src/lib/game/events.ts` is the whole socket contract, and the reducer in `game-state.ts` ends in
  `assertNever`, so a new backend event fails the build until it is handled.
- **Two colours and ink**: primary blue, accent amber. No green, no red. Lines are told apart by
  pattern (car solid, bike dashed, walk dotted), and mode colours come only from
  `src/components/metro/mode.ts`. No `font-bold`.
- Graph rendering is hand-written SVG. There is no graph library.
- **There is one router.** `searchTrip` in `src/lib/map/trip-search.ts` is how the round screen finds
  a trip, and `scripts/routes.mjs` runs the same code under Node for `calibrate_map`. Don't write a
  second one in Python: two routers disagree about which way a class goes.
- WebKit stalls a fetch sent in the same task as a new `WebSocket`; `BaseWSClient.connect()` opens
  the socket one task later. Keep that. Safari and phones are the browsers that matter — the e2e
  suite runs WebKit.
- Tests live in `frontend/tests/`, mirroring `src/`, not next to the code.

## things that change together

- **Design tokens**: `frontend/src/main.css` and `backend/static/css/custom.css` carry the same block
  between `>>> shared tokens` and `<<< end shared tokens >>>`. `tests/design/tokens.test.ts` names a
  token that drifted.
- **Colour mode bootstrap**: inline in `frontend/index.html` and `backend/static/js/head_script.js`.
- **README**: German first, then the same sections in English. Change one half, change the other.
- **Docs**: `docs/` is flat `de-`/`en-` pairs. The pages under `/docs/` are hand copies of the German
  files (`backend/template/docs/`); a change to one is a change to the other. The flowcharts on the
  site are drawn from `docs/de-flowcharts.md` by `npm run flowcharts` in `frontend/`.
- **What is stored → the legal pages.** With the study app on, the privacy page's section on
  participation codes quotes the three code lengths from the code (`co2mmute/legal.py`).
- **A map field** → the export and the importer (`maps/portability.py`, `maps/importer.py`),
  `maps/tests/test_portability.py`, and the builder if a built map should carry it
  (`mapbuild/mapfile.py`, `mapbuild/transit.py`).
- **A simulation constant** → both golden masters, `docs/kalibrierung.md`, the figures in the
  background doc.
- **A new line's seats and speed**: `BusLine`'s defaults and `TrainLine.DEFAULTS` in
  `maps/models.py`, `frontend/src/lib/map/pt-defaults.ts` and `BUS` / `TRAIN` in
  `mapbuild/transit.py`, per bus, train and tram.
- **The budget dial**: `game/calibration.py` and `frontend/src/lib/calibration.ts` carry the same
  normal, step and range; `game/tests/test_join.py` and `tests/lib/calibration.test.ts` assert the
  same cases.
- **CI**: `test.yml` and `workflow-prod.yml` carry copies of the same jobs, because one workflow cannot
  wait on another. Keep the copies identical.

## tests

- `devops/dev.sh test` is the backend suite, against Postgres, in exactly CI's environment. Read the
  **count**, not OK/FAILED: a file that breaks on import removes its own tests and the summary still
  looks fine.
- New tests go in the topic file that owns the code (`game/tests/test_rounds.py`, `test_phases.py`,
  …). Shared fixtures are in `game/tests/_helpers.py`.
- A test touching game signals needs `@override_settings(**TEST_BACKENDS)`. `transaction.on_commit`
  callbacks never run in a `TestCase` — wrap the call in `captureOnCommitCallbacks(execute=True)`.
  Anything awaiting `database_sync_to_async` needs a `TransactionTestCase`. Assert broadcasts by
  listening (`GroupListener`), not by patching.
- A run is a clean wall of dots: silence expected log noise with `muted()`, never globally.
- Write the test first and see it fail **on the assertion** — a red from an `ImportError` proves
  nothing.
- Frontend: `npx vitest run`, `npx tsc -b` (the `tests/` and `e2e/` folders have their own tsconfig),
  `npm run e2e` against a running stack.

## skills

`.agents/skills/<name>/SKILL.md`, one folder per task. Read the skill before the task it names:

- `map-create`: a real area, from its name to a map on an instance — build, check, calibrate,
  upload, and what to tell the human.
- `extract-data`: the research data of finished games as one sqlite file — export, what is in it,
  and what may be said from it.
- `co2mmute-docs`: what changes together — a map field, a constant, a string, a socket event,
  something stored, the dial, a CI job, a doc page — and how to check each.
- `map-versions`: changes said in words as versions of a map, with their questions, the ballot
  and its combinations, checked and measured.
- `map-modify`: what is off on a built map, fixed in its base version after talking it through —
  commuter towns, the count, a footpath, a moved stop, a street.

## repo conventions

- Branch `<area>/<slug>` off `main`, merge back with `--no-ff`. `prod` is a deploy pointer, not a
  branch to work on: `git push origin main:prod` deploys, CI gates it.
- Commit messages: German, lowercase, terse.
- Backend formatted with Black — an older Black, so don't reformat whole files. Comments and
  identifiers in English.
- Before naming a migration, check the last number in that app; never rename an applied one.

## decided

- The summary crowns no winner. CO₂, cost and time sit side by side because they disagree.
- The car carries no external or infrastructure cost: CO₂ is already the meter, in kg.
- No explanation in the ballot. It goes on the waiting screens.
- The host can add seats to a running game. A dropped socket never hands a seat to the host; the
  host takes it over by hand.
- `GameSession.map_updates` defaults to `False` on the model while the create form starts it `True`.
  Pinned by a test; changing it is a decision, not a fix.
