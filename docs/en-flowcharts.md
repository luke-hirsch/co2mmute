# How it runs

Flowcharts of the parts that are not standard Django: what talks to what, in which order, and where
in the code to start reading. Login, sign-up, password reset and the admin are left out — they are
what Django does anyway.

Every box names the file or function it stands for. The charts are [Mermaid](https://mermaid.js.org/);
GitHub draws them, and so does any editor with a Mermaid preview.

1. [The pieces](#the-pieces)
2. [A game, start to end](#a-game-start-to-end)
3. [Player authentication](#player-authentication)
4. [One round, end to end](#one-round-end-to-end)
5. [Finding a route in the browser](#finding-a-route-in-the-browser)
6. [The simulation](#the-simulation)
7. [Between rounds](#between-rounds)
8. [From the server to the screen](#from-the-server-to-the-screen)
9. [Map versions and the vote](#map-versions-and-the-vote)

## The pieces

One Django app on Daphne serves everything that is not the SPA: the REST API, the websockets and the
server-rendered pages. The simulation never runs in a request — it runs on a Celery worker, and its
results reach the browsers over the websocket.

```mermaid
flowchart TB
    subgraph browser["Browser"]
        spa["SPA under /app/<br>frontend/ — game, host pages, editor"]
        pages["Django pages<br>landing, /docs, legal, login"]
    end
    nginx["nginx<br>serves the SPA bundle,<br>proxies everything else"]
    subgraph daphne["Daphne — backend/"]
        ws["websockets<br>game/consumers.py"]
        rest["REST API<br>game/, maps/"]
        tpl["templates<br>backend/template/"]
    end
    redis[("Redis<br>channel layer, cache,<br>Celery broker")]
    subgraph celery["Celery"]
        beat["beat<br>anonymise hourly, idle games 02:30,<br>old sessions 03:00"]
        worker["worker<br>simulates a round<br>game/tasks.py"]
    end
    pg[("Postgres<br>games, maps, results")]

    spa -->|"/api/…"| nginx
    spa -->|"/ws/…"| nginx
    pages --> nginx
    nginx --> daphne
    %% ~~~ is invisible: it keeps the websockets above Redis and beat below it,
    %% so the chart stays upright and fits beside the list of stops
    ws ~~~ redis
    rest -->|"a round is complete"| redis
    redis ~~~ beat
    redis -->|"tasks"| worker
    worker -->|"events"| redis
    beat -->|"schedules"| redis
    redis -->|"group_send"| ws
    rest --> pg
    worker --> pg
```

## A game, start to end

A game is a `GameSession`, a round a `GameRound`. The phases between rounds have a chart of their
own [further down](#between-rounds). Every ending writes `end_reason` at the moment it happens:
`co2_limit`, `max_rounds`, `host` or `idle`.

```mermaid
stateDiagram-v2
    [*] --> Lobby: host creates the game
    Lobby --> Lobby: players join
    Lobby --> Playing: host starts, round 1 on the base version
    Playing --> Simulating: the last move is in
    Simulating --> BetweenRounds: round.completed
    Simulating --> Ended: CO2 budget spent or last round played
    BetweenRounds --> Playing: next round, on the map the vote chose
    Playing --> Ended: host ends it, or idle for days
    BetweenRounds --> Ended: host ends it, or idle for days
    Ended --> Anonymised: 24 h later (beat)
    Anonymised --> [*]

    note right of Playing
        The host can pause at any point.
        paused_at holds moves, phase changes
        and round completion until resume.
    end note
```

| step                                  | where to read                                                  |
| ------------------------------------- | -------------------------------------------------------------- |
| create                                | `GameSessionListCreateView` in `game/views_rest.py`            |
| join, home and destinations           | `JoinSessionAPIView` in `game/views_join.py`, `set_up_player` and `assign_agent_nodes` in `game/signals.py` |
| start                                 | `GameSessionDetailView.update` in `game/views_rest.py`         |
| round complete, simulate, end         | `game/rounds.py`, then `handle_round_completed` in `game/signals.py` |
| pause, idle end, anonymise            | `game/pause.py`, `game/idle.py`, `game/anon.py`                |

## Player authentication

Players have no account. Joining hands the browser two signed cookies, and every request and every
socket is checked against them. The host is an ordinary Django user with a session, and is checked
first.

### Getting a seat

```mermaid
flowchart TD
    join["join — POST api/game/join/ID/<br>name + game password<br>refused once started, ended or full"]
    create["host creates the game<br>(the host's own row)"]
    whoami["whoami — GET api/whoami/<br>renews both, e.g. after a break"]
    code["seat code — POST api/game/seat/CODE/<br>6 characters, 5 minutes, used once"]
    takeover["host takes a seat over<br>…/player/P/takeover/"]

    code --> rotate
    takeover --> rotate
    rotate["_rotate — game/seats.py<br>same row, same moves and votes,<br>new player_id"]
    rotate -->|"the old player_id<br>names nobody now"| revoked["player.revoked<br>old sockets close with 4403"]

    join --> mint
    create --> mint
    whoami --> mint
    rotate -->|"code redeemed"| mint

    mint["set_game_access_cookie + set_player_cookie<br>co2mmute/utils.py"]
    mint --> cookies["two cookies, TimestampSigner, salt from SECRET_KEY<br>game_access_ID = 'ID:random token'<br>player_ID = 'ID:player_id'"]
```

A seat is a `Player` row, and it can move between devices: the host takes a player's seat over to
play it at the Leitstelle, or hands a seat on with a code. Neither copies the row. `_rotate` gives it
a new `player_id`, so every cookie naming the old one stops working. A seat taken over needs no
cookie — the host acts for it with their session.

### Every request

```mermaid
flowchart TD
    rest["REST call<br>HasGameAccess + IsPlayerInGame<br>game/permissions.py"]
    sock["socket connect<br>resolve_player<br>game/ws_auth.py"]
    rest --> host
    sock --> host

    host{"this game's<br>host?"}
    host -->|"yes"| hostok["host<br>socket: a HostPlayer<br>REST: may act for a seat played at the Leitstelle"]
    host -->|"no"| access{"game cookie<br>valid?"}
    access -->|"no"| refused1["refused<br>REST 403, socket 4401"]
    access -->|"yes"| pid{"player cookie<br>valid?"}
    pid -->|"no"| refused1
    pid -->|"yes"| row{"seat still<br>there?"}
    row -->|"no"| refused2["refused<br>REST 403, socket 4403"]
    row -->|"yes"| player["player"]
```

- **this game's host?** A logged-in Django user who is `game_host` of this game.
- **game cookie valid?** `has_game_access`: `game_access_ID` carries a good signature, has not
  expired, and the game id inside it is this game's.
- **player cookie valid?** `resolve_player_id`: the same checks on `player_ID`. On REST its
  `player_id` must also equal the one in the URL — every `player_id` is in the lobby roster, so
  without that any player could move for any other.
- **seat still there?** A `Player` row with that `player_id` that has not left. The socket also
  refuses a game that has ended.

Both doors go through `game/auth.py`, which knows nothing about the host. A refused socket is
accepted first and then closed with its code (`refuse()` in `game/consumers.py`) — closed before the
accept, the browser only sees 1006 and keeps reconnecting.

Two consequences: rotating `SECRET_KEY`, or changing what goes inside a cookie, logs every player
out of every running game. And a player's name is the only thing the game knows about them; it never
goes into a log.

## One round, end to end

From the first tap on a phone to the stats on every screen. The route is found in the browser, the
server only checks it. The round is complete the moment the last seat that is still playing has
moved; the simulation then runs on Celery and reports back over the websocket.

```mermaid
sequenceDiagram
    autonumber
    participant P as Phone<br>RoundScreen
    participant R as Router<br>in the browser
    participant API as PlayerMoveView<br>game/views_rest.py
    participant RD as game/rounds.py
    participant W as Celery worker
    participant S as TrafficSimulator
    participant WS as GameConsumer<br>every open socket

    P->>R: pick a mode per Gruppe
    R-->>P: way there + way home
    P->>API: POST api/game/ID/player/P/move/
    API->>API: check both legs, store AgentRoutes
    API-->>P: 200
    API->>WS: roster: this seat is waiting
    API->>RD: on commit: complete_round_if_ready
    Note over RD: has every playing seat moved?<br>then claim the round, ACTIVE to COMPLETED
    RD->>W: run_simulation_task.delay
    W->>W: round_completed, handle_round_completed
    W->>S: run_simulation
    S-->>WS: simulation.progress
    S-->>W: SimulationResult and its rows
    W->>WS: round.completed with every seat's numbers
    alt CO2 budget spent or last round
        W->>WS: game.ended
    else
        W->>W: phase STATS
    end
    WS-->>P: gameReducer, then the stats screen
```

Two rules hold this together. There is **one** decision point, `complete_round_if_ready`, and
everything that can complete a round (a move, a player leaving) reaches it through
`schedule_round_completion_check`. And the round is **claimed** with a conditional `update()`, so two
moves arriving at the same instant start one simulation, not two.

## Finding a route in the browser

Everything here runs on the phone (`hooks/use-round-draft.ts`). The graph comes from the server once
per round and version, with last round's measured street speeds attached; the search itself is
Dijkstra.

```mermaid
flowchart TD
    seat["the seat: home + one destination per Gruppe<br>useSeatGame"] --> draft
    mapgraph["graph of the active map version<br>+ last round's speeds, previous_round_traffic<br>useMapGraph — lib/queries/map-graph.ts"] --> draft
    draft["useRoundDraft<br>hooks/use-round-draft.ts"] --> air{"straight line past<br>the mode's limit?"}
    air -->|"yes"| greyed["that mode is greyed out"]
    air -->|"no"| pick["player picks a mode and an option"]
    pick --> isPt{"public transport?"}

    isPt -->|"no"| dijkstra["findPath, dijkstra<br>utils/pathfinding.ts"]
    dijkstra --> weight["calculateEdgeWeight per link<br>canUseEdge: may this mode use it at all?<br>walk, bike: minutes<br>car schnellste: minutes at last round's speed<br>car kürzeste: metres<br>car sparsamste: metres × CO2 factor at that speed"]
    weight --> limit{"route past<br>the mode's limit?"}
    limit -->|"yes"| tooFar["too-far"]
    limit -->|"no"| there

    isPt -->|"yes"| ptr["findBestPTRoute, findPTRoute<br>utils/ptRouting.ts"]
    ptr --> product["Dijkstra over node + state<br>state: walking, or on line X<br>walk at most 2 km to and from a stop<br>boarding costs half the line's interval"]
    product --> there

    there["way there found"] --> back["the same search, destination to home<br>never the way there turned round"]
    back -->|"none"| noHome["no-way-home"]
    back -->|"found"| ready["Gruppe ready"]
    ready --> everyone{"every Gruppe ready?"}
    everyone -->|"yes"| submit["draftPayload, POST move<br>lib/queries/move.ts"]
```

- **The limits** are walk 5 km and bike 15 km (`lib/map/trip-limits.ts`). The straight line is
  checked before a mode is picked — it can only be shorter than the route — and the found route
  after.
- **The way home is a search of its own.** A one-way street has no reverse edge, so on such a map
  the way home is a different route. The server refuses a move without one.
- **The server checks, it does not route.** `_validate_routes` in `game/views_rest.py` checks that
  both legs connect home and destination and that every link allows the mode.
- **Public transport has three options:** fastest, fewest changes (every change after the first
  boarding costs 30 extra minutes in the search) and no bus.
- **A slow search cannot overwrite a newer one.** Every search carries a token per Gruppe; a result
  whose token is no longer the current one is dropped.
- **Unfinished taps survive a reload** (mode and options only, never a route) in localStorage,
  `lib/game/draft-storage.ts`.

## The simulation

A link queue model, the mesoscopic model MATSim uses. What it calculates and why is in
[`docs/en-background.md`](en-background.md); these three charts show how the code is laid out.

### Rows in, engine, rows out

`game/simulation.py` is the adapter: it reads the round's rows into a `Scenario`, lets the engine
run, and writes the results. Everything under `sim/` is plain Python with no Django in it, so a test
or a calibration script can run a round without a database.

```mermaid
flowchart TD
    handler["handle_round_completed<br>game/signals.py"] --> ts["TrafficSimulator(round)<br>game/simulation.py"]
    subgraph rowsIn["rows in: _scenario"]
        direction LR
        r1["_read_routes<br>AgentRoutes of one direction"]
        r2["_read_lines<br>bus and train lines of the active version,<br>each on its own side of the street"]
        r3["_read_links<br>every edge a route or a line drives"]
        r1 --> r2 --> r3
    end
    ts --> rowsIn
    rowsIn --> scen["Scenario<br>sim/scenario.py, no Django from here on"]
    scen --> eng["LinkQueueEngine<br>sim/linkqueue.py<br>links with a capacity draw each,<br>line timetables, where riders board"]
    eng --> morning["way to work<br>_run_pass, _compute_outcomes"]
    morning --> hasHome{"routes home?"}
    hasHome -->|"yes"| evening["way home<br>a fresh network, same random stream"]
    hasHome -->|"no"| save
    evening --> save
    subgraph rowsOut["rows out"]
        save["_save_results<br>one AgentSimulationResult per round trip,<br>EdgeTrafficSnapshots, totals"]
        speeds["_update_street_speeds<br>StreetPerRound, which the next round routes on"]
        replay["build_replay<br>SimulationResult.replay"]
    end
    save --> speeds --> replay
    replay --> stats["back in handle_round_completed:<br>numbers per seat, round.completed"]
```

The round is seeded from the round's pk (`TrafficSimulator(round, seed=…)` to sweep), so a round
replays identically.

### One pass, tick by tick

A pass is one direction. It runs until everybody has arrived; the 1000-tick limit
(`PASS_TICK_GUARD`) only catches a bug, and hitting it is logged as an error.

```mermaid
flowchart TD
    dep["_generate_departures<br>people: a normal spread around the hour<br>lines: one run every interval"] --> waitlist["one waiting list for the whole network,<br>sorted by when people want to leave<br>desired speed drawn once per person"]
    waitlist --> tick["a tick, 5 minutes by default<br>_advance_traffic"]
    tick --> budget["every link gets this tick's flow budget"]
    budget --> spawn["_spawn_vehicles<br>leave if the first link has room,<br>otherwise wait at the door"]
    spawn --> free["_advance_free_running<br>walkers, bikes off the road, trains,<br>buses on a bus lane; stops served on the way"]
    free --> discharge["_discharge every link,<br>in a new random order each tick (the zipper)"]
    discharge --> moved{"anything moved?"}
    moved -->|"yes, a door may be free"| spawn2["_spawn_vehicles again"]
    spawn2 --> discharge
    moved -->|"no"| sample["_record_edge_traffic<br>street samples for the replay"]
    sample --> done{"everybody arrived?"}
    done -->|"no"| tick
    done -->|"yes"| outcomes["_record_arrivals,<br>_compute_outcomes: time, delay, CO2, cost, fare"]
```

Public transport is not a separate model. A bus or train run is an ordinary vehicle on the same
links, under a negative route key (`route_pk < 0` means "a line, not a person"). Riders wait in
`stop_queues` per line and stop, board up to the free seats, and alight where their route leaves the
line (`_serve_stop`). Past its timetable a line keeps running as long as anybody at all is still out.

### One link

What happens to one car on one link. A two-way street is two links, one per direction.

```mermaid
flowchart LR
    want["car wants onto the link"] --> room{"room left?<br>storage: 133 cars<br>per lane and km"}
    room -->|"no"| upstream["waits where it is,<br>which blocks the link behind it"]
    upstream --> room
    room -->|"yes"| drive["drives the free-flow time<br>length ÷ speed limit,<br>at its own desired speed"]
    drive --> queue["joins the queue"]
    queue --> head{"its turn, and flow left this tick?<br>1800 cars per lane and hour"}
    head -->|"no"| queue
    head -->|"yes"| next["onto the next link,<br>or arrived"]
```

- **Who queues:** cars and buses in mixed traffic. A bike on a street with no bike lane has a line of
  its own on the link (`bike_queue`): it takes space, but never waits for a car. Walkers, trains,
  paths and bus lanes run free.
- **Two or more car lanes** get one queue per next street (`_pick_head`), so a car turning left does
  not hold up the ones going straight.
- **A full link that never empties** releases one car after `DEADLOCK_TICKS = 4` anyway, over its
  storage. That is counted (`forced_releases` in the log).
- **Speed is an output.** A link's speed is its length over the time cars actually took
  (`EdgeState.mean_speed_kmh`). That speed sets the car's CO2 and cost on it, and the next round
  routes on it.

## Between rounds

The phases live in `game/phases.py`. The phones and the host send their part over the game socket
(`player.stats_ack`, `vote.open`, `vote.submit`, `stalemate.vote`, `stalemate.force_leave`);
`GameConsumer` only passes them on. The names in capitals are the phases of
`GameRound.BetweenRoundPhase`.

```mermaid
stateDiagram-v2
    [*] --> STATS: round.completed
    STATS --> DISCUSSION: everyone has read the stats, and there is a ballot
    STATS --> NextRound: everyone has read the stats, no ballot
    DISCUSSION --> VOTING: host opens the vote
    VOTING --> NextRound: one winner, the new active_map_version
    VOTING --> STALEMATE: first tie
    VOTING --> NextRound: second tie, the map stays
    STALEMATE --> VOTING: majority for a revote
    STALEMATE --> NextRound: no majority, or host cuts it short
    NextRound --> [*]: new GameRound, round.started
```

- **Every arrow is a claim.** `_claim` moves `GameRound.between_round_phase` with a conditional
  `update()`, so two phones finishing a phase at the same instant move it once.
- **"Everyone" means the seats still playing** — `Player.objects.filter(game=…).playing()`, the same
  rule the round uses. When someone leaves, `phases.recheck` runs, since that can complete a phase.
- **The ballot is drawn once** (`vote_options`, at most two versions) and stored on the round, so
  every phone votes on the same two.
- **A game that ends has no stats phase.** Its last numbers reach the players with `round.completed`
  and on the summary.

## From the server to the screen

One socket per game, one reducer. The REST snapshot is read once to draw something at once; after
that the socket owns every update.

```mermaid
flowchart LR
    subgraph server["backend, sync code"]
        sig["game/signals.py<br>join, start, end, round.completed"]
        ph["game/phases.py<br>stats, vote, stalemate"]
        ro["game/roster.py<br>who is here, who has moved"]
    end
    sig --> layer
    ph --> layer
    ro --> layer
    layer[("channel layer<br>group gamestate_ID")] --> cons["GameConsumer<br>game/consumers.py"]
    cons -->|"game.state on every connect,<br>then every event"| sock["GameSocket, one per game<br>lib/game/socket.ts"]
    snapshot["REST snapshot, read once<br>useLobbySnapshot"] --> reducer
    sock --> reducer["gameReducer<br>lib/game/game-state.ts"]
    reducer --> screen{"currentScreen"}
    screen --> lobby["lobby"]
    screen --> playing["playing<br>RoundScreen, HostDeskScreen"]
    screen --> between["between rounds<br>BetweenScreen, HostBetweenScreen"]
    screen --> ended["ended<br>EndScreen"]
    sock -.->|"stats ack, votes"| cons
    cons -.->|"database_sync_to_async"| ph
```

- **`game.state` arrives on every connect**, so a reconnect is the resync. Nothing polls and nothing
  refetches.
- **The socket wins over the snapshot.** The roster can arrive before the snapshot does, and only the
  socket knows who is connected — so once a roster has arrived, the snapshot no longer touches the
  seats.
- **`lib/game/events.ts` is the whole socket contract** as one typed union. A new event the reducer
  does not handle breaks the build.
- **Broadcast from sync code only.** `send_game_state_message` uses `async_to_sync`, which refuses to
  run on the consumer's event loop.

## Map versions and the vote

A map is one graph; a version is a filter over it. Every node, edge, line and line segment says
which versions it is in, and a row naming no version is in none.

```mermaid
flowchart TD
    map["GameMap"] --> versions["MapVersions<br>base, single changes, combinations<br>every row names the versions it is in"]
    versions -->|"compatible_versions"| ballot["vote_options<br>game/phases.py, at most two"]
    ballot --> vote["the players vote"]
    vote --> active["GameSession.active_map_version"]
    active --> filter["what is in this version<br>nodes and edges: their map_versions<br>line chains: maps/versions.py"]
    filter --> graphApi["MapVersionGraphView<br>api/maps/ID/graph/version/V/?game=…"]
    filter --> simRead["TrafficSimulator<br>_read_lines, _read_links"]
    lastRound["StreetPerRound<br>last round's speeds"] --> graphApi
    graphApi --> router["the router in the browser"]
```

The whole map, every version and the ballot included, goes in and out as one JSON file
(`api/maps/import/`, `api/maps/ID/export/`). An import always creates a new map.
