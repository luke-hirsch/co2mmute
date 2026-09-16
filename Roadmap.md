# Ideen, Must Haves, ToDos und mögliche Erweiterungen

ziel: uebergabefaehig bis **ende september 26**. reihenfolge unten ist nach abhaengigkeit
sortiert, nicht nach wichtigkeit. phase 0 zuerst, der rest laeuft teilweise parallel.

grundsatz spielerdaten: spieler sind schueler, teils minderjaehrig. datensparsam bleiben.
kein account, kein login, name reicht. das ist absicht und bleibt so.

## Was Muss?

### phase 0 – sofort, klein, blockiert nichts ✅ erledigt 13.08.26

audit 13.08.26. alles hier ist ein paar zeilen, sollte vor der naechsten testrunde drin sein.
alles unten ist drin, suite von `failures=3, errors=17` auf `failures=1, errors=2`.
offen bleibt nur was nicht im repo liegt: cert auf der kiste tauschen, prod `.env`
pruefen, `PROD_*` secrets setzen.

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

#### 1.4 REST fuer join und lobby ✅ erledigt 14.08.26

gemergt 16.09.26. war der blocker fuer 2.3.
drei endpoints in `game/views_join.py`, rein additiv - die form-views laufen
unveraendert weiter, 2.3 loescht sie.

- `GET api/game/lookup/<game_id>/` - ohne cookie lesbar, das ist der erste call nach
  dem qr-scan. sagt nur ob es das spiel gibt, ob ein passwort noetig ist und ob noch
  platz ist. keine namen, kein host, kein passwort im body.
- `POST api/game/join/<game_id>/` - name + optional passwort rein, spieler und beide
  signierten cookies raus. ersetzt die zwei form-schritte inkl. `joined_game_ids`.
- `GET api/game/<game_id>/lobby/` - roster + settings, braucht das game-cookie.
- `GameSessionListView` geloescht statt repariert. hing an `sessions/` ohne `game_id`,
  war hinter `<str:game_id>/` sowieso unerreichbar und lieferte auch erreichbar 403.

dabei zwei defekte aus dem gleichen pfad mitgenommen:

- **das lobby-passwort wurde nie geprueft.** der block lag komplett in
  `if game_session.started_at:`, also genau in dem fall in dem man ohnehin nicht
  reinkommt. jedes spiel das man wirklich betritt hat ihn uebersprungen.
- **`max_players` wurde nirgends durchgesetzt.** die lobby nahm beliebig viele spieler.
  jetzt im REST-pfad, mit `select_for_update` gegen zwei gleichzeitige joins.

offen: der template-pfad prueft `max_players` weiter nicht. dafuer muesste auch
`PlayerCreateView` angefasst werden, die in 2.3 ohnehin rausfliegt.

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

#### 2.1 fundament ✅ erledigt 14.08.26

gemergt 16.09.26. rein additiv, die alten screens laufen unveraendert weiter.
alte theme-variablen und die von shadcn liegen bis ende phase 2 nebeneinander,
die alten heissen deshalb `brandaccent` und `mutedtext`. der dev-proxy ist noch
nie gegen ein echtes backend gelaufen, erster echter test ist 2.3.

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
  auf, geben das ergebnis aber nicht zurueck. tote hooks. `useGameSessionList` zeigt
  ausserdem auf `api/game/sessions/`, den es seit 1.4 nicht mehr gibt - ersatzlos raus.
- runden counter im frontend nicht richtig
- daten im frontend nicht persistent
- maximum player trumpft agents, somehow connected. backend-haelfte ist mit 1.4
  erledigt (join gibt 409 `full`), bleibt die anzeige im frontend.
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
- was rein muss: setup lokal (inkl. self-signed cert fuer nginx, liegt nicht im repo),
  deploy, die env-variablen, das datenmodell,
  wie die simulation rechnet, wie map-versionen und voting zusammenhaengen,
  und wie man den map editor bedient.
- einfaches md reicht. wenn zeit bleibt: generierte api-doku.
- README aufraeumen, die alte bug-liste raus.

#### deploy (14.08.26)

kein staging mehr. die staging-kiste war mein privater vps und wird anderweitig
gebraucht, die TU stellt keine nach. `stage` branch + `workflow-stage.yml` sind
raus, es bleibt `main` -> `prod`.

- die `STAGING_*` secrets zeigen auf eine kiste die nicht mehr zum projekt gehoert.
  loeschen, sonst deployt ein versehentlicher push dort drueber.
- `PROD_HOST` / `PROD_KEY` / `PROD_USER` / `PROD_KNOWN_HOSTS` gibt es nicht,
  deshalb ist `workflow-prod.yml` noch nie gelaufen. die live-kiste wird von hand
  deployed. vor der uebergabe entscheiden: secrets setzen und pruefen ob der
  TU-host ssh von github actions ueberhaupt annimmt - oder den workflow rauswerfen
  und den manuellen weg sauber dokumentieren. halbfertig darf es nicht bleiben.
- ohne staging gibt es keine stufe mehr zwischen merge und live. das gate ist dann
  die testsuite, siehe 1.5. deploy nicht waehrend einer laufenden testrunde.

offen aus phase 0, liegt alles nicht im repo:

- cert auf der live-kiste tauschen. der alte private key ist public und liegt da
  noch. das repo-fix allein rotiert ihn nicht.
- pruefen wer bei `co2mmute.stsds.tu-berlin.de` TLS terminiert. wenn das self-signed
  cert nach aussen geht, laeuft public traffic auf einem veroeffentlichten key
  -> an die TU-admins.
- pruefen ob die prod `.env` einen key >= 32 zeichen setzt, sonst startet der
  container nach dem phase-0 fix nicht mehr:
  `grep -c '^DJANGO_SECRET_KEY=.\{32,\}' devops/.env`

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
