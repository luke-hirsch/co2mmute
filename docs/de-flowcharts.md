# Wie es läuft

Ablaufdiagramme der Teile, die kein Standard-Django sind: was mit wem redet, in welcher Reihenfolge,
und wo man im Code anfängt zu lesen. Anmelden, Registrieren, Passwort zurücksetzen und der Admin
fehlen — das macht Django sowieso.

Jede Box nennt die Datei oder Funktion, für die sie steht. Die Diagramme sind
[Mermaid](https://mermaid.js.org/); GitHub zeichnet sie, und jeder Editor mit Mermaid-Vorschau auch.

1. [Die Teile](#die-teile)
2. [Ein Spiel von Anfang bis Ende](#ein-spiel-von-anfang-bis-ende)
3. [Zugang für Mitspielende](#zugang-für-mitspielende)
4. [Eine Runde vom Zug bis zur Statistik](#eine-runde-vom-zug-bis-zur-statistik)
5. [Routensuche im Browser](#routensuche-im-browser)
6. [Die Simulation](#die-simulation)
7. [Zwischen den Runden](#zwischen-den-runden)
8. [Vom Server auf den Bildschirm](#vom-server-auf-den-bildschirm)
9. [Kartenversionen und Abstimmung](#kartenversionen-und-abstimmung)

## Die Teile

Eine Django-App auf Daphne liefert alles aus, was nicht die SPA ist: die REST-API, die Websockets und
die serverseitig gerenderten Seiten. Die Simulation läuft nie in einer Anfrage — sie läuft auf einem
Celery-Worker, und ihre Ergebnisse kommen über den Websocket bei den Browsern an.

```mermaid
flowchart LR
    subgraph browser["Browser"]
        spa["SPA unter /app/<br>frontend/ — Spiel, Seiten der Spielleitung, Editor"]
        pages["Django-Seiten<br>Startseite, /hintergrund, Rechtliches, Anmeldung"]
    end
    nginx["nginx<br>liefert das SPA-Bundle aus,<br>reicht alles andere weiter"]
    subgraph daphne["Daphne — backend/"]
        rest["REST-API<br>game/, maps/"]
        tpl["Templates<br>backend/template/"]
        ws["Websockets<br>game/consumers.py"]
    end
    subgraph celery["Celery"]
        worker["Worker<br>simuliert eine Runde<br>game/tasks.py"]
        beat["Beat<br>anonymisieren stündlich, ruhende Spiele 02:30,<br>alte Sitzungen 03:00"]
    end
    pg[("Postgres<br>Spiele, Karten, Ergebnisse")]
    redis[("Redis<br>Channel Layer, Cache,<br>Celery-Broker")]

    spa -->|"/api/…"| nginx
    spa -->|"/ws/…"| nginx
    pages --> nginx
    nginx --> rest
    nginx --> tpl
    nginx --> ws
    rest --> pg
    rest -->|"eine Runde ist komplett"| redis
    beat -->|"plant ein"| redis
    redis -->|"Tasks"| worker
    worker --> pg
    worker -->|"Events"| redis
    redis -->|"group_send"| ws
```

## Ein Spiel von Anfang bis Ende

Ein Spiel ist eine `GameSession`, eine Runde eine `GameRound`. Die Phasen zwischen den Runden haben
[weiter unten](#zwischen-den-runden) ein eigenes Diagramm. Jedes Ende schreibt `end_reason` in dem
Moment, in dem es passiert: `co2_limit`, `max_rounds`, `host` oder `idle`.

```mermaid
stateDiagram-v2
    state "Lobby" as Lobby
    state "Spiel läuft" as Playing
    state "Simulation" as Simulating
    state "zwischen den Runden" as BetweenRounds
    state "beendet" as Ended
    state "anonymisiert" as Anonymised

    [*] --> Lobby: Spielleitung legt das Spiel an
    Lobby --> Lobby: Beitritte
    Lobby --> Playing: Spielleitung startet, Runde 1 auf der Basisversion
    Playing --> Simulating: der letzte Zug ist da
    Simulating --> BetweenRounds: round.completed
    Simulating --> Ended: CO2-Budget verbraucht oder letzte Runde gespielt
    BetweenRounds --> Playing: nächste Runde, auf der Karte, die abgestimmt wurde
    Playing --> Ended: Spielleitung beendet es, oder tagelang Ruhe
    BetweenRounds --> Ended: Spielleitung beendet es, oder tagelang Ruhe
    Ended --> Anonymised: 24 h später (Beat)
    Anonymised --> [*]

    note right of Playing
        Die Spielleitung kann jederzeit pausieren.
        paused_at hält Züge, Phasenwechsel
        und das Rundenende an, bis es weitergeht.
    end note
```

| Schritt                                 | wo man liest                                                   |
| --------------------------------------- | -------------------------------------------------------------- |
| anlegen                                 | `GameSessionListCreateView` in `game/views_rest.py`            |
| beitreten, Zuhause und Ziele            | `JoinSessionAPIView` in `game/views_join.py`, `set_up_player` und `assign_agent_nodes` in `game/signals.py` |
| starten                                 | `GameSessionDetailView.update` in `game/views_rest.py`         |
| Runde komplett, simulieren, beenden     | `game/rounds.py`, dann `handle_round_completed` in `game/signals.py` |
| pausieren, Ende nach Ruhe, anonymisieren | `game/pause.py`, `game/idle.py`, `game/anon.py`               |

## Zugang für Mitspielende

Mitspielende haben kein Konto. Beim Beitreten bekommt der Browser zwei signierte Cookies, und jede
Anfrage und jeder Socket wird gegen sie geprüft. Die Spielleitung ist ein normaler Django-User mit
Sitzung und wird zuerst geprüft.

### Einen Platz bekommen

```mermaid
flowchart TD
    join["beitreten — POST api/game/join/ID/<br>Name + Spielpasswort<br>abgelehnt, wenn gestartet, beendet oder voll"]
    create["Spielleitung legt das Spiel an<br>(ihre eigene Zeile)"]
    whoami["whoami — GET api/whoami/<br>erneuert beide, z. B. nach einer Pause"]
    code["Platz-Code — POST api/game/seat/CODE/<br>6 Zeichen, 5 Minuten, einmal gültig"]
    takeover["Spielleitung übernimmt einen Platz<br>…/player/P/takeover/"]

    code --> rotate
    takeover --> rotate
    rotate["_rotate — game/seats.py<br>dieselbe Zeile, dieselben Züge und Stimmen,<br>neue player_id"]
    rotate -->|"die alte player_id<br>nennt jetzt niemanden"| revoked["player.revoked<br>alte Sockets schließen mit 4403"]

    join --> mint
    create --> mint
    whoami --> mint
    rotate -->|"Code eingelöst"| mint

    mint["set_game_access_cookie + set_player_cookie<br>co2mmute/utils.py"]
    mint --> cookies["zwei Cookies, TimestampSigner, Salt aus SECRET_KEY<br>game_access_ID = 'ID:Zufallstoken'<br>player_ID = 'ID:player_id'"]
```

Ein Platz ist eine `Player`-Zeile und kann zwischen Geräten wandern: Die Spielleitung holt einen
Platz an die Leitstelle („Übernehmen“) oder gibt ihn mit einem Code weiter. Keins von beidem kopiert
die Zeile. `_rotate` gibt ihr eine neue `player_id`, und jedes Cookie, das die alte nennt, ist damit
wertlos. Ein übernommener Platz braucht kein Cookie — die Spielleitung handelt mit ihrer Sitzung für
ihn.

### Jede Anfrage

```mermaid
flowchart TD
    rest["REST-Aufruf<br>HasGameAccess + IsPlayerInGame<br>game/permissions.py"]
    sock["Socket-Verbindung<br>resolve_player<br>game/ws_auth.py"]
    rest --> host
    sock --> host

    host{"Spielleitung<br>dieses Spiels?"}
    host -->|"ja"| hostok["Spielleitung<br>Socket: ein HostPlayer<br>REST: darf für einen Platz an der Leitstelle handeln"]
    host -->|"nein"| access{"Spiel-Cookie<br>gültig?"}
    access -->|"nein"| refused1["abgelehnt<br>REST 403, Socket 4401"]
    access -->|"ja"| pid{"Platz-Cookie<br>gültig?"}
    pid -->|"nein"| refused1
    pid -->|"ja"| row{"Platz noch<br>da?"}
    row -->|"nein"| refused2["abgelehnt<br>REST 403, Socket 4403"]
    row -->|"ja"| player["spielt diesen Platz"]
```

- **Spielleitung dieses Spiels?** Ein angemeldeter Django-User, der `game_host` dieses Spiels ist.
- **Spiel-Cookie gültig?** `has_game_access`: `game_access_ID` hat eine gültige Signatur, ist nicht
  abgelaufen, und die Spiel-ID darin ist die dieses Spiels.
- **Platz-Cookie gültig?** `resolve_player_id`: dieselben Prüfungen für `player_ID`. Bei REST muss
  seine `player_id` außerdem die aus der URL sein — jede `player_id` steht im Roster der Lobby, ohne
  diese Prüfung könnte also jeder für jeden anderen ziehen.
- **Platz noch da?** Eine `Player`-Zeile mit dieser `player_id`, die das Spiel nicht verlassen hat.
  Der Socket lehnt außerdem ein beendetes Spiel ab.

Beide Türen gehen durch `game/auth.py`, das nichts von der Spielleitung weiß. Ein abgelehnter Socket
wird erst angenommen und dann mit seinem Code geschlossen (`refuse()` in `game/consumers.py`) — vor
dem Annehmen geschlossen, sieht der Browser nur 1006 und verbindet sich immer wieder neu.

Zwei Folgen: Wer `SECRET_KEY` wechselt oder ändert, was in einem Cookie steht, wirft alle
Mitspielenden aus allen laufenden Spielen. Und der Name ist das Einzige, was das Spiel über eine
Person weiß; er landet nie in einem Log.

## Eine Runde vom Zug bis zur Statistik

Vom ersten Tippen auf dem Handy bis zur Statistik auf jedem Bildschirm. Die Route wird im Browser
gefunden, der Server prüft sie nur. Die Runde ist komplett, sobald der letzte Platz, der noch
mitspielt, gezogen hat; dann läuft die Simulation auf Celery und meldet sich über den Websocket
zurück.

```mermaid
sequenceDiagram
    autonumber
    participant P as Handy<br>RoundScreen
    participant R as Router<br>im Browser
    participant API as PlayerMoveView<br>game/views_rest.py
    participant RD as game/rounds.py
    participant W as Celery-Worker
    participant S as TrafficSimulator
    participant WS as GameConsumer<br>jeder offene Socket

    P->>R: Verkehrsmittel je Gruppe wählen
    R-->>P: Hinweg + Rückweg
    P->>API: POST api/game/ID/player/P/move/
    API->>API: beide Wege prüfen, AgentRoutes speichern
    API-->>P: 200
    API->>WS: Roster: dieser Platz wartet
    API->>RD: nach dem Commit: complete_round_if_ready
    Note over RD: haben alle spielenden Plätze gezogen?<br>dann die Runde beanspruchen, ACTIVE zu COMPLETED
    RD->>W: run_simulation_task.delay
    W->>W: round_completed, handle_round_completed
    W->>S: run_simulation
    S-->>WS: simulation.progress
    S-->>W: SimulationResult und seine Zeilen
    W->>WS: round.completed mit den Zahlen jedes Platzes
    alt CO2-Budget verbraucht oder letzte Runde
        W->>WS: game.ended
    else
        W->>W: Phase STATS
    end
    WS-->>P: gameReducer, dann die Statistik
```

Zwei Regeln halten das zusammen. Es gibt **einen** Entscheidungspunkt, `complete_round_if_ready`, und
alles, was eine Runde abschließen kann (ein Zug, jemand geht), kommt über
`schedule_round_completion_check` dorthin. Und die Runde wird mit einem bedingten `update()`
**beansprucht**, sodass zwei Züge, die im selben Augenblick ankommen, eine Simulation starten und
nicht zwei.

## Routensuche im Browser

Alles hier läuft auf dem Handy (`hooks/use-round-draft.ts`). Der Graph kommt einmal je Runde und
Version vom Server, mit den gemessenen Geschwindigkeiten der letzten Runde dran; die Suche selbst ist
Dijkstra.

```mermaid
flowchart TD
    seat["der Platz: Zuhause + ein Ziel je Gruppe<br>useSeatGame"] --> draft
    mapgraph["Graph der aktiven Kartenversion<br>+ Geschwindigkeiten der letzten Runde, previous_round_traffic<br>useMapGraph — lib/queries/map-graph.ts"] --> draft
    draft["useRoundDraft<br>hooks/use-round-draft.ts"] --> air{"Luftlinie über dem<br>Limit des Verkehrsmittels?"}
    air -->|"ja"| greyed["das Verkehrsmittel ist ausgegraut"]
    air -->|"nein"| pick["Verkehrsmittel und Option wählen"]
    pick --> isPt{"ÖPNV?"}

    isPt -->|"nein"| dijkstra["findPath, dijkstra<br>utils/pathfinding.ts"]
    dijkstra --> weight["calculateEdgeWeight je Kante<br>canUseEdge: darf das Verkehrsmittel überhaupt drauf?<br>zu Fuß, Rad: Minuten<br>Auto schnellste: Minuten bei der Geschwindigkeit der letzten Runde<br>Auto kürzeste: Meter<br>Auto sparsamste: Meter × CO2-Faktor bei dieser Geschwindigkeit"]
    weight --> limit{"Route über<br>dem Limit?"}
    limit -->|"ja"| tooFar["too-far"]
    limit -->|"nein"| there

    isPt -->|"ja"| ptr["findBestPTRoute, findPTRoute<br>utils/ptRouting.ts"]
    ptr --> product["Dijkstra über Knoten + Zustand<br>Zustand: zu Fuß oder in Linie X<br>höchstens 2 km zu Fuß zur Haltestelle und von ihr weg<br>Einsteigen kostet den halben Takt der Linie"]
    product --> there

    there["Hinweg gefunden"] --> back["dieselbe Suche, vom Ziel nach Hause<br>nie der umgedrehte Hinweg"]
    back -->|"keiner"| noHome["no-way-home"]
    back -->|"gefunden"| ready["Gruppe fertig"]
    ready --> everyone{"alle Gruppen fertig?"}
    everyone -->|"ja"| submit["draftPayload, POST move<br>lib/queries/move.ts"]
```

- **Die Limits** sind 5 km zu Fuß und 15 km mit dem Rad (`lib/map/trip-limits.ts`). Die Luftlinie
  wird geprüft, bevor ein Verkehrsmittel gewählt ist — sie kann nur kürzer sein als die Route —, die
  gefundene Route danach.
- **Der Rückweg ist eine eigene Suche.** Eine Einbahnstraße hat keine Gegenkante, auf so einer Karte
  ist der Rückweg also eine andere Route. Der Server lehnt einen Zug ohne Rückweg ab.
- **Der Server prüft, er sucht keine Route.** `_validate_routes` in `game/views_rest.py` prüft, dass
  beide Wege Zuhause und Ziel verbinden und dass jede Kante das Verkehrsmittel erlaubt.
- **Der ÖPNV hat drei Optionen:** „schnellste“, „wenig umsteigen“ (jeder Umstieg nach dem ersten
  Einsteigen kostet in der Suche 30 Minuten extra) und „ohne Bus“.
- **Eine langsame Suche kann keine neuere überschreiben.** Jede Suche trägt ein Token je Gruppe; ein
  Ergebnis, dessen Token nicht mehr das aktuelle ist, wird verworfen.
- **Angefangene Eingaben überleben ein Neuladen** (nur Verkehrsmittel und Optionen, nie eine Route),
  im localStorage, `lib/game/draft-storage.ts`.

## Die Simulation

Ein Warteschlangenmodell je Kante (Link Queue), das mesoskopische Modell, das MATSim benutzt. Was es
rechnet und warum, steht im [`docs/de-hintergrund.md`](de-hintergrund.md); diese drei Diagramme
zeigen, wie der Code aufgebaut ist.

### Zeilen rein, Engine, Zeilen raus

`game/simulation.py` ist der Adapter: Er liest die Zeilen der Runde in ein `Scenario`, lässt die
Engine laufen und schreibt die Ergebnisse. Alles unter `sim/` ist reines Python ohne Django, ein Test
oder ein Kalibrierskript kann also eine Runde ohne Datenbank rechnen.

```mermaid
flowchart TD
    handler["handle_round_completed<br>game/signals.py"] --> ts["TrafficSimulator(round)<br>game/simulation.py"]
    subgraph rowsIn["Zeilen rein: _scenario"]
        direction LR
        r1["_read_routes<br>AgentRoutes einer Richtung"]
        r2["_read_lines<br>Bus- und Bahnlinien der aktiven Version,<br>jede auf ihrer eigenen Straßenseite"]
        r3["_read_links<br>jede Kante, die eine Route oder Linie befährt"]
        r1 --> r2 --> r3
    end
    ts --> rowsIn
    rowsIn --> scen["Scenario<br>sim/scenario.py, ab hier kein Django"]
    scen --> eng["LinkQueueEngine<br>sim/linkqueue.py<br>Kanten mit je einer gezogenen Kapazität,<br>Fahrpläne der Linien, wo Fahrgäste einsteigen"]
    eng --> morning["Hinweg<br>_run_pass, _compute_outcomes"]
    morning --> hasHome{"Rückwege da?"}
    hasHome -->|"ja"| evening["Rückweg<br>ein frisches Netz, derselbe Zufallsstrom"]
    hasHome -->|"nein"| save
    evening --> save
    subgraph rowsOut["Zeilen raus"]
        save["_save_results<br>ein AgentSimulationResult je Hin- und Rückweg,<br>EdgeTrafficSnapshots, Summen"]
        speeds["_update_street_speeds<br>StreetPerRound, darauf routet die nächste Runde"]
        replay["build_replay<br>SimulationResult.replay"]
    end
    save --> speeds --> replay
    replay --> stats["zurück in handle_round_completed:<br>Zahlen je Platz, round.completed"]
```

Der Zufall einer Runde ist aus ihrem pk geseedet (`TrafficSimulator(round, seed=…)`, um über mehrere
Seeds zu messen), eine Runde läuft also bei jeder Wiederholung gleich.

### Ein Durchlauf, Tick für Tick

Ein Durchlauf ist eine Richtung. Er läuft, bis alle angekommen sind; die Grenze von 1000 Ticks
(`PASS_TICK_GUARD`) fängt nur einen Bug ab, und wird sie erreicht, steht ein Fehler im Log.

```mermaid
flowchart TD
    dep["_generate_departures<br>Menschen: normalverteilt um die Stunde<br>Linien: eine Fahrt je Takt"] --> waitlist["eine Warteliste fürs ganze Netz,<br>sortiert nach gewünschter Abfahrt<br>Wunschgeschwindigkeit einmal je Person gezogen"]
    waitlist --> tick["ein Tick, standardmäßig 5 Minuten<br>_advance_traffic"]
    tick --> budget["jede Kante bekommt das Abflussbudget dieses Ticks"]
    budget --> spawn["_spawn_vehicles<br>losfahren, wenn auf der ersten Kante Platz ist,<br>sonst an der Haustür warten"]
    spawn --> free["_advance_free_running<br>zu Fuß, Räder abseits der Straße, Züge,<br>Busse auf der Busspur; Haltestellen werden unterwegs bedient"]
    free --> discharge["_discharge auf jeder Kante,<br>jeden Tick in neuer zufälliger Reihenfolge (Reißverschluss)"]
    discharge --> moved{"hat sich etwas<br>bewegt?"}
    moved -->|"ja, vielleicht ist eine Tür frei"| spawn2["_spawn_vehicles noch mal"]
    spawn2 --> discharge
    moved -->|"nein"| sample["_record_edge_traffic<br>Messwerte der Straßen für die Wiedergabe"]
    sample --> done{"alle angekommen?"}
    done -->|"nein"| tick
    done -->|"ja"| outcomes["_record_arrivals,<br>_compute_outcomes: Zeit, Verspätung, CO2, Kosten, Fahrpreis"]
```

Der ÖPNV ist kein eigenes Modell. Eine Bus- oder Bahnfahrt ist ein ganz normales Fahrzeug auf
denselben Kanten, unter einem negativen Routenschlüssel (`route_pk < 0` heißt „eine Linie, kein
Mensch“). Fahrgäste warten in `stop_queues` je Linie und Haltestelle, steigen ein, solange Plätze
frei sind, und steigen aus, wo ihre Route die Linie verlässt (`_serve_stop`). Nach ihrem Fahrplan
fährt eine Linie weiter, solange überhaupt noch jemand unterwegs ist.

### Eine Kante

Was einem Auto auf einer Kante passiert. Eine Straße mit zwei Richtungen sind zwei Kanten, eine je
Richtung.

```mermaid
flowchart LR
    want["Auto will auf die Kante"] --> room{"noch Platz?<br>Speicher: 133 Autos<br>je Spur und km"}
    room -->|"nein"| upstream["wartet, wo es ist,<br>und blockiert damit die Kante dahinter"]
    upstream --> room
    room -->|"ja"| drive["fährt die Freiflusszeit<br>Länge ÷ Tempolimit,<br>mit seiner eigenen Wunschgeschwindigkeit"]
    drive --> queue["stellt sich in die Schlange"]
    queue --> head{"dran, und noch Abfluss in diesem Tick?<br>1800 Autos je Spur und Stunde"}
    head -->|"nein"| queue
    head -->|"ja"| next["auf die nächste Kante,<br>oder angekommen"]
```

- **Wer Schlange steht:** Autos und Busse im Mischverkehr. Ein Rad auf einer Straße ohne Radspur hat
  auf der Kante eine eigene Schlange (`bike_queue`): Es nimmt Platz weg, wartet aber nie auf ein
  Auto. Wer zu Fuß geht, Züge, Wege ohne Straße und Busspuren laufen frei.
- **Zwei oder mehr Autospuren** bekommen eine Schlange je nächster Straße (`_pick_head`), ein Auto,
  das links abbiegt, hält also die nicht auf, die geradeaus fahren.
- **Eine volle Kante, die nie leer wird,** lässt nach `DEADLOCK_TICKS = 4` trotzdem ein Auto weiter,
  über ihren Speicher hinaus. Das wird gezählt (`forced_releases` im Log).
- **Geschwindigkeit ist ein Ergebnis.** Die Geschwindigkeit einer Kante ist ihre Länge durch die
  Zeit, die Autos wirklich gebraucht haben (`EdgeState.mean_speed_kmh`). Sie bestimmt CO2 und Kosten
  eines Autos auf dieser Kante, und die nächste Runde routet darauf.

## Zwischen den Runden

Die Phasen stehen in `game/phases.py`. Die Handys und die Spielleitung schicken ihren Teil über den
Spiel-Socket (`player.stats_ack`, `vote.open`, `vote.submit`, `stalemate.vote`,
`stalemate.force_leave`); `GameConsumer` reicht sie nur weiter. Die Namen in Großbuchstaben sind die
Phasen aus `GameRound.BetweenRoundPhase`.

```mermaid
stateDiagram-v2
    state "nächste Runde" as NextRound

    [*] --> STATS: round.completed
    STATS --> DISCUSSION: alle haben die Statistik gelesen, und es gibt einen Stimmzettel
    STATS --> NextRound: alle haben die Statistik gelesen, kein Stimmzettel
    DISCUSSION --> VOTING: Spielleitung eröffnet die Abstimmung
    VOTING --> NextRound: ein Gewinner, die neue active_map_version
    VOTING --> STALEMATE: erster Gleichstand
    VOTING --> NextRound: zweiter Gleichstand, die Karte bleibt
    STALEMATE --> VOTING: Mehrheit für Neuwahl
    STALEMATE --> NextRound: keine Mehrheit, oder die Spielleitung bricht ab
    NextRound --> [*]: neue GameRound, round.started
```

- **Jeder Pfeil wird beansprucht.** `_claim` setzt `GameRound.between_round_phase` mit einem
  bedingten `update()`, zwei Handys, die eine Phase im selben Augenblick abschließen, schalten sie
  also nur einmal weiter.
- **„Alle“ heißt die Plätze, die noch mitspielen** — `Player.objects.filter(game=…).playing()`,
  dieselbe Regel wie in der Runde. Geht jemand, läuft `phases.recheck`, weil das eine Phase
  abschließen kann.
- **Der Stimmzettel wird einmal gezogen** (`vote_options`, höchstens zwei Versionen) und an der Runde
  gespeichert, jedes Handy stimmt also über dieselben zwei ab.
- **Ein Spiel, das endet, hat keine Statistikphase.** Seine letzten Zahlen kommen mit
  `round.completed` und in der Zusammenfassung bei den Mitspielenden an.

## Vom Server auf den Bildschirm

Ein Socket je Spiel, ein Reducer. Der REST-Snapshot wird einmal gelesen, damit sofort etwas zu sehen
ist; danach gehört jedes Update dem Socket.

```mermaid
flowchart LR
    subgraph server["Backend, synchroner Code"]
        sig["game/signals.py<br>beitreten, starten, beenden, round.completed"]
        ph["game/phases.py<br>Statistik, Abstimmung, Gleichstand"]
        ro["game/roster.py<br>wer da ist, wer gezogen hat"]
    end
    sig --> layer
    ph --> layer
    ro --> layer
    layer[("Channel Layer<br>group gamestate_ID")] --> cons["GameConsumer<br>game/consumers.py"]
    cons -->|"game.state bei jeder Verbindung,<br>dann jedes Event"| sock["GameSocket, einer je Spiel<br>lib/game/socket.ts"]
    snapshot["REST-Snapshot, einmal gelesen<br>useLobbySnapshot"] --> reducer
    sock --> reducer["gameReducer<br>lib/game/game-state.ts"]
    reducer --> screen{"currentScreen"}
    screen --> lobby["Lobby"]
    screen --> playing["Spiel läuft<br>RoundScreen, HostDeskScreen"]
    screen --> between["zwischen den Runden<br>BetweenScreen, HostBetweenScreen"]
    screen --> ended["beendet<br>EndScreen"]
    sock -.->|"Statistik gelesen, Stimmen"| cons
    cons -.->|"database_sync_to_async"| ph
```

- **`game.state` kommt bei jeder Verbindung**, ein Reconnect ist also schon der Abgleich. Nichts
  fragt regelmäßig nach, nichts lädt neu.
- **Der Socket schlägt den Snapshot.** Der Roster kann vor dem Snapshot ankommen, und nur der Socket
  weiß, wer verbunden ist — sobald ein Roster da ist, rührt der Snapshot die Plätze also nicht mehr
  an.
- **`lib/game/events.ts` ist der ganze Socket-Vertrag** als eine typisierte Union. Ein neues Event,
  das der Reducer nicht behandelt, bricht den Build.
- **Gesendet wird nur aus synchronem Code.** `send_game_state_message` benutzt `async_to_sync`, und
  das verweigert auf der Event-Loop des Consumers den Dienst.

## Kartenversionen und Abstimmung

Eine Karte ist ein Graph; eine Version ist ein Filter darüber. Bei jedem Knoten, jeder Kante, jeder
Linie und jedem Linienabschnitt steht, in welchen Versionen sie vorkommen, und eine Zeile, die keine
Version nennt, kommt in keiner vor.

```mermaid
flowchart TD
    map["GameMap"] --> versions["MapVersions<br>Basis, einzelne Änderungen, Kombinationen<br>jede Zeile nennt die Versionen, in denen sie ist"]
    versions -->|"compatible_versions"| ballot["vote_options<br>game/phases.py, höchstens zwei"]
    ballot --> vote["die Mitspielenden stimmen ab"]
    vote --> active["GameSession.active_map_version"]
    active --> filter["was in dieser Version ist<br>Knoten und Kanten: ihre map_versions<br>Linienketten: maps/versions.py"]
    filter --> graphApi["MapVersionGraphView<br>api/maps/ID/graph/version/V/?game=…"]
    filter --> simRead["TrafficSimulator<br>_read_lines, _read_links"]
    lastRound["StreetPerRound<br>Geschwindigkeiten der letzten Runde"] --> graphApi
    graphApi --> router["der Router im Browser"]
```

Die ganze Karte, mit jeder Version und dem Stimmzettel, geht als eine JSON-Datei rein und raus
(`api/maps/import/`, `api/maps/ID/export/`). Ein Import legt immer eine neue Karte an.
