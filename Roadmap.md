# Ideen, Must Haves, ToDos und mögliche Erweiterungen

ziel: uebergabefaehig bis **ende september 26**. reihenfolge unten ist nach abhaengigkeit
sortiert, nicht nach wichtigkeit. phase 0 zuerst, der rest laeuft teilweise parallel.

grundsatz spielerdaten: spieler sind schueler, teils minderjaehrig. datensparsam bleiben.
kein account, kein login, name reicht. das ist absicht und bleibt so.

## Was Muss?

### phase 0 – sofort, klein, blockiert nichts

audit 13.08.26. alles hier ist ein paar zeilen, sollte vor der naechsten testrunde drin sein.

- `game/signals.py:402` benutzt `voteable_versions`, die variable gibt es nicht.
  NameError am ende jeder runde, ausser wenn das spiel in dem zug endet.
  knallt erst nachdem simulation, stats und phase schon gespeichert sind, also
  sieht man es je nach pfad nur im log oder als fehler beim letzten spieler
  der abschickt. gemeint ist `has_map_versions`.
- `devops/nginx/certs/selfsigned.key` liegt im repo. private key ist public.
  key + cert neu ausstellen, aus dem image raus, per volume oder env rein.
  ausserdem: `server_name luke-hirsch.de` in der nginx.conf ist von einem anderen projekt.
- `DJANGO_SECRET_KEY` faellt auf einen platzhalter zurueck, in settings.py und
  im compose default. die cookie salts fuer spieler-login werden daraus abgeleitet.
  laeuft prod ohne gesetzten key, sind alle spieler-cookies faelschbar.
  -> hart failen wenn `DEBUG=False` und kein key gesetzt. **und pruefen ob die prod .env
  ihn ueberhaupt setzt.** wenn nicht: key setzen, alle laufenden spiele fliegen dabei raus.
- `workflow-prod.yml` triggert auf push nach `prod`, macht auf der kiste dann aber
  `git checkout stage && git pull origin stage`. deployed also stage nach prod.
- `game/engine.py` hat einen syntaxfehler (`game_session = ` ohne wert) und wird
  nirgends importiert. toter dijkstra-stub, loeschen.

### phase 1 – backend: korrektheit, sicherheit, datenschutz

#### 1.1 rundenlogik

- rundenende wird an zwei stellen geprueft. **die doppelung war kein versehen, die
  zweite pruefung hat einen echten fehler abgefangen.** beide sind aber falsch,
  auf unterschiedliche art:

  - `signals.py:50 check_round_completion` (post_save auf PlayerMove) feuert
    **innerhalb** von `transaction.atomic()` in `PlayerMoveView.post`, und zwar
    **bevor `_store_routes` gelaufen ist**. wenn sie die runde ausloest, findet
    `handle_round_completed` fuer den letzten spieler noch keine `AgentRoute`,
    `has_routes` ist False, und es laeuft der legacy-zweig
    `_calculate_hardcoded_stats` statt der simulation. dazu laeuft die ganze
    simulation in der noch offenen transaktion. zaehlt ausserdem alle Player,
    auch `left_at` und host-gesteuerte.
  - `views_rest.py:468 PlayerMoveView._check_round_completion` zaehlt richtig
    (aktive, nicht host-gesteuerte) und laeuft in einem
    `threading.Thread(daemon=True)`, der **nach** dem atomic block startet - sieht
    also die routen. das ist der pfad der die simulation ueberhaupt richtig
    ausloest. aber: eigener daemon-thread mit eigener DB-verbindung, exceptions
    verschwinden im `except Exception` daneben, und beim neustart des containers
    stirbt er mitten in der simulation.

  konsolidierung (eine funktion, zwei aufrufer):

  1. den post_save receiver in signals.py loeschen. falscher zeitpunkt, falsche zaehlung.
  2. den thread durch `transaction.on_commit(...)` ersetzen. laeuft garantiert nach
     dem commit, also mit routen, ohne extra thread und ohne verschluckte fehler.
  3. die runde **atomar beanspruchen**, bevor irgendwas passiert:
     `GameRound.objects.filter(pk=..., status=ACTIVE).update(status=COMPLETED)` und
     nur weitermachen wenn das 1 zurueckgibt. sonst loesen zwei gleichzeitig
     abschickende spieler die runde zweimal aus. das ist heute nur durch die
     reihenfolge der beiden pfade zufaellig abgefangen.
  4. im callback `run_simulation_task.delay(...)` statt der simulation inline -
     damit ist das hier und der celery-punkt unten **eine** aenderung, nicht zwei.
  5. `cleanup_leaving_player` (post_delete auf Player) behaelt seinen trigger,
     ruft aber dieselbe funktion. das ist ein echter dritter fall: wer geht,
     kann damit die runde vollmachen.

  zaehlregel ueberall: aktive spieler (`left_at__isnull=True`), ohne
  host-gesteuerte, auf beiden seiten des vergleichs.
  (haengt zusammen mit "spiel wartet nicht auf eingaben aller user" und
  "spieler muss aus der liste verschwinden".)
- simulation laeuft synchron im signal handler, auf dem daphne worker der den
  letzten move-request bedient hat. celery ist komplett konfiguriert
  (`co2mmute/celery.py`, `game/tasks.py:run_simulation_task`), aber nichts ruft
  `.delay()`, und worker + beat sind im compose auskommentiert.
  bei mehreren parallelen sessions blockiert das die websockets.
  -> `.delay()` benutzen, worker + beat anschalten, fortschritt weiter ueber ws.
- `consumers.py` hat 1312 zeilen und ist die halbe spiellogik (rundenphasen, voting,
  stalemate, roster). aufteilen: consumer nur noch transport, phasenlogik in ein
  eigenes modul das auch ohne websocket testbar ist. **entschieden 13.08.26: bleibt
  drin.** reihenfolge: erst die konsolidierung oben (die legt fest wo rundenende
  entschieden wird), dann der split - andersrum verschiebt man den gleichen fehler
  nur in eine neue datei.

#### 1.2 spieler-auth (kein account, nur haerten)

- das player-cookie ist nicht ans spiel gebunden, die signatur deckt nur die player_id.
  nur der cookie-_name_ enthaelt die game_id. game_id mit in den signierten wert,
  so wie es beim game-cookie schon ist.
- `unsign_value` ruft `TimestampSigner.unsign(..., max_age=None)`, der zeitstempel
  wird also nie geprueft. signierte cookies laufen serverseitig nie ab, nur im browser.
  -> `max_age` auf `COOKIE_AGE` setzen.
- `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS sind nicht gesetzt, obwohl
  die seite unter https laeuft.
- die gleiche pruefung steht zweimal da: `game/permissions.py` fuer REST und
  `game/ws_auth.py` fuer websocket. auf einen resolver zusammenziehen, beide rufen den auf.
- `corsheaders` ist in INSTALLED_APPS, die middleware fehlt. entweder richtig
  einhaengen oder rauswerfen.
- host-accounts bleiben erstmal auf `django.contrib.auth`. MFA/allauth waere nur
  fuer hosts relevant und loest keins der obigen probleme. steht unter "Was geht?".

#### 1.3 datenschutz

- die dsgvo-seite sagt spieldaten werden geloescht "wenn das spiel geloescht wird".
  es loescht aber nie jemand ein spiel. `cleanup_old_simulations(days_old=30)` gibt es,
  wird nirgends aufgerufen und betrifft nur simulationen.
  d.h. namen von schuelern liegen unbegrenzt in der postgres.
  -> **anonymisieren bei spielende**: `Player.name` auf "Spieler N" setzen, qr code
  loeschen. moves, routen und ergebnisse bleiben unveraendert und weiter zuordenbar,
  nur der identifizierende string faellt weg. als celery-beat job (haengt an 1.1).
- `ws_auth.py:100` loggt spielernamen (`logger.debug(f"Players in game ...")`).
  greift nur bei DEBUG log level, aber raus damit.
- chat kommt in der dsgvo-seite gar nicht vor. technisch ist er schon sparsam
  (redis, 100 nachrichten, 2h TTL) - das gehoert nur aufgeschrieben.
- dsgvo.html ergaenzen: chat + aufbewahrung, die anonymisierungsregel oben,
  und der spieler-cookie. cookies.html: spieler-cookie ist technisch notwendig.
  **entwurf, die gruppe muss das freigeben bevor es live geht.**
- offen: braucht die gruppe ein info-blatt fuer schulen/lehrkraefte, was gespeichert
  wird und wie lange? falls ja, faellt es hier mit ab.

#### 1.4 REST fuer join und lobby

**blockiert phase 2.** join, lobby und spieler-anlegen sind heute Django-form-views
(`game/views.py`, `co2mmute/urls.py`), kein REST. die SPA kann sie so nicht uebernehmen.

- endpoints fuer: session per game_id aufloesen, beitreten (name + optional passwort),
  lobby-state lesen. antwortformate + cookie-setzen wie bei den bestehenden views.
- `GameSessionListView` haengt an `sessions/` ohne `game_id`, ist aber mit
  `HasGameAccess` geschuetzt, das ohne `game_id` immer `False` liefert.
  der endpoint gibt also immer 403. richtige permission oder weg damit.

#### 1.5 tests

- aktuell: `game/tests.py`, `tests_simulation.py`, `tests_ws_auth.py`,
  leere stubs in maps und content. CI laeuft davon nichts, die workflows deployen nur.
- auf per-app `tests/` packages umstellen, nach thema geschnitten
  (`test_models.py`, `test_rounds.py`, `test_auth.py`, `test_simulation.py`, ...),
  gemeinsame fixtures in `_helpers.py`.
- eigenes test-settings-modul mit schnellem password hasher.
- abdeckung dahin wo phase 1 was anfasst: rundenabschluss, cookie-signatur,
  anonymisierung, simulation.
- CI: workflow der bei push auf jeden branch die suite laufen laesst.
  deploy erst wenn gruen.

### phase 2 – frontend neu

nicht aufhuebschen, neu bauen. struktur, tests und design nach dem gleichen muster
wie im anderen projekt (jac).

#### 2.1 fundament

- struktur: `src/lib/` (pure logik), `src/lib/queries/` (react-query, ohne toasts),
  `src/components/ui/` (shadcn), `src/components/<feature>/`, `src/routes/`.
- `@/` alias in vite + tsconfig. dev-proxy fuer `/api`, `/ws`, `/media`, `/static`
  auf `localhost:8000` - fehlt heute komplett, deshalb geht `npm run dev`
  nicht gegen ein lokales backend.
- vitest, tests in einem eigenen `frontend/tests/` baum der `src/` spiegelt,
  nicht neben den quelldateien. eigene tsconfig dort, damit `tsc -b` sie nicht anfasst.
- shadcn/ui + radix + lucide + sonner. tailwind v4 bleibt.
- `src/lib/de.ts` als einziges woerterbuch. keine strings direkt im JSX.

#### 2.2 das eigentliche problem

die state-bugs sind kein zufall. jede spielkomponente haengt an **zwei** quellen
fuer dieselben daten: eine react-query mit `refetchInterval: 2000` **und** dem
websocket, dazu manuelle `refetch()` aufrufe aus ws-callbacks und ein `refetchRef`
gegen stale closures. drei mechanismen die sich gegenseitig ueberschreiben.

-> eine quelle. websocket ist die wahrheit, REST liefert nur den startzustand.
ein reducer pro spiel (snapshot rein, ws-events drauf), kein polling mehr.
das loest die runden-counter- und persistenz-bugs an der wurzel statt einzeln.

#### 2.3 routen

SPA uebernimmt: join, lobby, spiel, auswertung, map editor, host-login.
Django behaelt: landing (`/`), legal, admin. `backend/template/` schrumpft entsprechend.
der QR-code zeigt dann direkt auf die SPA-route.

#### 2.4 bugs (aus den testrunden)

- `usePlayerList` und `useGameSessionList` in `hooks/gameHooks.ts` rufen `useQuery`
  auf, geben das ergebnis aber nicht zurueck. tote hooks.
- runden counter im frontend nicht richtig
- daten im frontend nicht persistent
- maximum player trumpft agents, somehow connected
- karte ueber bildrand, buttons fuer auswahlmoeglichkeiten nicht sichtbar, legende fehlt,
  chat horizontal scroll, edges nicht anklickbar, logout im dark mode nicht lesbar
  (die alte liste aus der README - beim neubau abarbeiten und die README-liste leeren)

#### 2.5 deutsch

komplette UI auf deutsch, ueber `de.ts`. `LANGUAGE_CODE` auf `de-de`.

#### 2.6 ui / ux

- design einmal durchziehen, dark/light sauber.
- map editor: **nur portieren**, kein redesign. cytoscape-logik bleibt wie sie ist,
  kommt in die neue struktur und an den `@/` alias, shadcn-huellen nur wo es
  billig ist. der editor ist deliverable, aber die bedienung wird in phase 4
  dokumentiert, nicht umgebaut. map-erstellung wirklich einfacher machen:
  siehe "Was geht?".
- steckbriefe fuer agenten (backend liefert die daten)

### phase 3 – integration tests

- ein kompletter spieldurchlauf: session anlegen, zwei spieler beitreten, runde spielen,
  simulation, voting, naechste runde, spielende, auswertung.
- websocket-pfade mit dazu, das ist wo es bisher bricht.
- laeuft in CI.

### phase 4 – doku und uebergabe

- `docs/backend` und `docs/frontend` sind leer.
- was rein muss: setup lokal, deploy, die env-variablen, das datenmodell,
  wie die simulation rechnet, wie map-versionen und voting zusammenhaengen,
  und wie man den map editor bedient.
- einfaches md reicht. wenn zeit bleibt: generierte api-doku.
- README aufraeumen, die alte bug-liste raus.

### automations (wenn zeit bleibt)

- deployment automation mit tests
- release automation mit tests
- monitoring automations
- scheduled security updates, package updates, ssl certs
- back up

## Was geht?

- dev ops

  - k8 cluster implementierung
    - streng genommen guenstiger, da nur bezahlen, wenn benutzen
    - load balancing + autoscaling + elasticities --> bessere up time

- Backend

  - allauth + MFA fuer host-accounts
  - resourcen schonen mit compilierter sprache (rust)

- Map creation wirklich einfacher machen (13.08.26 bewusst zurueckgestellt)

  karten sind heute handarbeit. stand: 8-55 knoten, 11-140 kanten pro karte,
  abstrahiert aus echten orten, nicht aus OSM gezogen. JSON rein/raus gibt es schon
  (`map/upload/` + `<pk>/export/`), aber nur fuer eine **ganze karte mit genau einer
  base version**. vier richtungen, je nachdem wo die zeit wirklich draufgeht:

  - **grapheingabe**: 140 kanten mal (typ, tempolimit, spuren, busspur, fuss/rad)
    ist stumpfe arbeit. mehrfachauswahl, eigenschaften kopieren, defaults pro karte,
    kantenzuege in einem zug zeichnen, tastaturbedienung, einrasten am hintergrundbild.
  - **change-versionen**: das ist das, worueber im spiel abgestimmt wird, und der
    einzige weg dahin ist heute die m2m-zugehoerigkeit von Node, Edge, StreetEdge,
    TrainEdge und BusLine von hand zu pflegen. "version duplizieren und aendern",
    wobei der editor den diff mitschreibt und die m2m selber setzt. versionen mit
    in den JSON round-trip. `GenerateCombinationsView` erledigt die kombinatorik
    danach schon.
  - **ist die karte gut?**: laesst sich erst im echten spiel beurteilen.
    kuerzeste wege je verkehrsmittel anzeigen, probelauf mit synthetischen agenten,
    stau-vorschau im editor.
  - **vom echten ort zur abstraktion**: massstab aus zwei bekannten punkten
    kalibrieren, einrasten, distanzanzeige. OSM-import nur stark vereinfacht -
    roh liefert ein echtes viertel tausende knoten, das hilft nicht.
    (der auskommentierte `OVERPASS_API_URL` block in settings.py ist der alte anlauf.)
    "map creation mit ml" gehoert auch hierhin.

- Daten

  - daten krake basteln
  - daten dashboard

- Spiel

  - Simulation refactoring (wissenschaftliche Grundlagen einbauen).
    kern fuehlt sich richtig an, deshalb nicht im pflichtteil.
  - frontend simulation
  - mathe fokus staerken ueber path algo choices
  - realtime map updates waehrend laufender session, statt festgelegter Wahl von Versionen
  - alles realtime (zielsetzung aendern a la mini motorways/metro ... wie viele leute bekomme ich commuted.)

- Platform
  - als native apps
