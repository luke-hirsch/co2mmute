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

**One way into a game: `/app/join/<ID>`.** The QR code, the landing page and the header all point
there.

**Two kinds of auth.** The host is a Django user with a session. A player holds two cookies signed
with `SECRET_KEY`, `game_access_<id>` and `player_<id>`, set only through `set_game_access_cookie` /
`set_player_cookie` in `co2mmute/utils.py` and resolved by `game/auth.py`. Rotating `SECRET_KEY` or
changing what goes into a cookie logs every player out of every running game.

**The host has a `Player` row.** Find it by account — `Player.objects.host_rows()` /
`without_host_rows()` — never by `controlled_by_host`, which means "played at the Leitstelle".

**One counting rule:** `Player.objects.filter(game=…).playing()` — still in the game, not the host's
own row. Rounds, phases, the lobby limit and the summary all use it. Don't spell it out again.

**A seat moves between devices** (`game/seats.py`). Takeover and handover keep the row and give it a
new `player_id`, which makes every old cookie worthless. The handover code is a six-character bearer
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
- **Each direction of a street is its own link.** `lanes` counts the whole street; a bus lane and a
  bike lane each take a car lane, and zero car lanes is a legal gate, closed to cars only.
- **Nobody is stranded.** A pass runs until everyone has arrived, and every line keeps running while
  anybody is out. A non-arrival is a defect, never a third metric.
- **Society pays for the timetable**: a line emits and costs per vehicle-km whether anyone rides or
  not, and that counts against the budget.
- **The round is seeded** from the round's pk. A test asserting an exact number passes `seed=`.
- **Units:** `people_per_agent` is derived (`district_commuters / (seats × Gruppen per seat)`), never
  picked. `AgentSimulationResult.total_co2_g` is per person × `people_per_agent`; `mean_cost_eur` is
  per person; `GameSession.max_CO2_level` is in kg.
- **Calibration is a property of the map**: `GameMap.district_commuters`,
  `co2_budget_kg_per_round`, and `calibrated` (true only for a pair measured on that map).
  `docs/kalibrierung.md` says how the shipped map's pair was found.
- **Two golden masters** (`game/tests/test_sim_golden.py`). Regenerate with `GOLDEN_REGENERATE=1`
  only for a deliberate change, and say so in the commit.

## maps

A map is a graph — nodes, edges, bus and train lines — with **versions**: each row carries the
versions it belongs to, so a version is a filter over one graph. `compatible_versions` between
versions *is* the ballot. A row naming no version is in no version.

- `maps/versions.py` answers "what is in this version": `put_rows_in` / `drop_rows_from` to write it,
  `delete_version` to delete one. Nothing else writes membership.
- A changed street is a clone: the original stays in the versions without the change, the clone is
  in the versions with it. Compare versions by node pair, never by id.
- **The JSON file is the backup and the only way a map moves.** `GET api/maps/<pk>/export/` writes
  every version and the ballot; `POST api/maps/import/` always makes a **new** map (an import that
  overwrote one would take its games with it). `maps/portability.py` owns the format. Export before
  touching a map anyone plays — maps are hours of work.
- **`manage.py check_map <file>`** checks a map file against what every finished map has to keep:
  one link per direction per node pair in a version, lines whole and on their own side of the street,
  line ends where someone can board, a way from every home to every workplace and back. The rules are
  `maps/checks.py`. The upload does not run them — a map in the editor is half drawn.
- `map_examples/` is production data, not a fixture: the map that is played, tested by
  `maps/tests/test_example_map.py`.

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
- **What is stored → the legal pages.**
- **A map field** → the export and the importer (`maps/portability.py`, `maps/importer.py`) and
  `maps/tests/test_portability.py`.
- **A simulation constant** → both golden masters, `docs/kalibrierung.md`, the figures in the
  background doc.
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
