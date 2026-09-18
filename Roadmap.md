# Ideen, Must Haves, ToDos und mögliche Erweiterungen

ziel: uebergabefaehig bis **ende september 26**. reihenfolge unten ist nach abhaengigkeit
sortiert, nicht nach wichtigkeit. phase 0 zuerst, der rest laeuft teilweise parallel.

grundsatz spielerdaten: spieler sind schueler, teils minderjaehrig. datensparsam bleiben.
kein account, kein login, name reicht. das ist absicht und bleibt so.
gespielt wird bisher vor allem von der forschungsgruppe und studis, die haetten mit
einem account kein problem. entworfen wird trotzdem fuer die klasse.

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
  eigenes modul das auch ohne websocket testbar ist. ~~entschieden 13.08.26: bleibt
  drin.~~ **17.09.26: kommt doch, vor 1.6** - 1.6 und 1.7 aendern genau diese regeln.
  reihenfolge: erst die konsolidierung oben (die legt fest wo rundenende
  entschieden wird), dann der split - andersrum verschiebt man den gleichen fehler
  nur in eine neue datei.
  - ✅ teil 1 (17.09.26): phasen in `game/phases.py`, sync und ohne socket testbar.
    jeder phasenwechsel wird atomar beansprucht wie das rundenende. stats-acks sind
    eine tabelle statt redis-set, die abstimmungsoptionen liegen auf der runde statt
    2h im cache. zaehlregel steht einmal da (`Player.objects.playing()`).
    abstimmung oeffnen und "leave as is" erzwingen gehen nur noch aus ihrer phase.
    nebenbei gefunden: `round.started` kam nie an. der consumer hat `async_to_sync`
    im event loop aufgerufen, asgiref wirft da, der socket ist jedes mal abgestuerzt.
    `consumers.py` 1312 -> 613 zeilen.
  - teil 2: roster aus den `Player`-zeilen, siehe 1.6.

#### 1.2 spieler-auth (kein account, nur haerten) ✅ erledigt 16.09.26

auf main 16.09.26. alles unten ist drin, REST, websocket und whoami laufen ueber
`game/auth.py`. volle suite: nur noch der qr-code test offen (1.3).
**das player-cookie hat ein neues format, alle alten cookies sind ungueltig.** der
naechste prod-deploy wirft jeden laufenden spieler raus -> nur zwischen testrunden.

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
- `PlayerMoveView` und `GetYourOwnGame` nehmen die `player_id` aus der url,
  `IsPlayerInGame` vergleicht sie nicht mit dem cookie. jeder spieler kann fuer
  jeden anderen im gleichen spiel abschicken, die ids stehen im lobby-roster.
  `GetYourOwnGame` sucht ausserdem ohne spiel-filter, `player_id` ist nur pro spiel
  eindeutig -> 500 sobald zwei spiele die gleiche id haben.
- `WhoAmIView` liest das player-cookie selbst, dritte kopie der pruefung. mit dem
  neuen cookie-format findet es den spieler nicht mehr und das frontend verliert
  seine identitaet. -> auch auf den resolver.
- beide cookie-helper schreiben in die django-session (`player_by_game`,
  `game_access_tokens`), gelesen wird das nie. bei eingeloggten usern verknuepft
  `django_session` damit account und spieler. -> raus.
- host-accounts bleiben erstmal auf `django.contrib.auth`. MFA/allauth waere nur
  fuer hosts relevant und loest keins der obigen probleme. steht unter "Was geht?".

#### 1.3 datenschutz ✅ erledigt 16.09.26

auf main 16.09.26. anonymisierung in `game/anon.py`, beat job stuendlich, greift 24h
nach spielende (`DJANGO_ANONYMISE_GRACE_HOURS`). `./manage.py anonymise_games` fuer
hand und backfill. `clearsessions` naechtlich 03:00 als crontab - beat merkt sich
seine laufzeiten in einer datei im container, jeder rebuild setzt ein 24h-intervall
zurueck. volle suite gruen, zum ersten mal.
**dsgvo.html und cookies.html sind auf main, aber noch nicht freigegeben.** vor dem
naechsten prod-deploy freigeben lassen oder die zwei dateien fuer den deploy
zuruecknehmen. nach dem deploy einmal `clearsessions` von hand, prod hat alles seit
dem start liegen.
durchgespielt: die endkarte zeigt die namen noch, wie gewollt.
offen: beat-log nach einer stunde, rechtstexte im browser (hell/dunkel).
17.09.26: dsgvo + cookies bleiben, die tu-seiten kennen unsere cookies nicht. die
rechtstexte duzen jetzt, wie der rest der seite.
**impressum:** ist noch die firmen-vorlage mit platzhaltern (adresse, handelsregister,
ust-id, TMG) und seit 17.09. im footer jeder seite verlinkt. das team sagt, als
subdomain brauchen wir keins. das tu-impressum gilt laut eigenem text aber nur fuer
`www.tu.berlin` und `redaktion.tu.berlin`, und die dsgvo-seite verweist fuer
verantwortlichen und kontakt aufs impressum. vor dem deploy klaeren: verantwortliche
stelle + kontakt von der gruppe.

- die dsgvo-seite sagt spieldaten werden geloescht "wenn das spiel geloescht wird".
  es loescht aber nie jemand ein spiel. `cleanup_old_simulations(days_old=30)` gibt es,
  wird nirgends aufgerufen und betrifft nur simulationen.
  d.h. namen von schuelern liegen unbegrenzt in der postgres.
  -> **anonymisieren bei spielende**: `Player.name` auf "Spieler N" setzen, qr code
  loeschen. moves, routen und ergebnisse bleiben unveraendert und weiter zuordenbar,
  nur der identifizierende string faellt weg. als celery-beat job (haengt an 1.1).
- ~~`ws_auth.py:100` loggt spielernamen (`logger.debug(f"Players in game ...")`).
  greift nur bei DEBUG log level, aber raus damit.~~ mit 1.2 rausgeflogen.
- die host-zeile (`GameSessionCreateView` legt fuer den host einen Player an) heisst
  "Vorname Nachname (Host)". beim anonymisieren wird sie "Host" und bekommt keine
  nummer. erkannt wird sie am account (`user = game.game_host`), nicht an
  `controlled_by_host` - das braucht 1.6.
- `clearsessions` laeuft nie, abgelaufene zeilen in `django_session` bleiben fuer
  immer liegen. -> als beat job.
- chat kommt in der dsgvo-seite gar nicht vor. technisch ist er schon sparsam
  (redis, 100 nachrichten, 2h TTL) - das gehoert nur aufgeschrieben.
- dsgvo.html ergaenzen: chat + aufbewahrung, die anonymisierungsregel oben,
  und der spieler-cookie. cookies.html: spieler-cookie ist technisch notwendig.
  cookies.html 2.1 sagt ausserdem, session-cookies sind beim schliessen des browsers
  weg. django default sind 14 tage.
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

17.09.26: verifikation zurueckgestellt, 1.6/1.7 gehen vor.

stand 17.09.26: `settings_test.py`, `test.yml` und der test-job in `workflow-prod.yml` sind auf
main gemergt (lokal, noch nicht gepusht), branch geloescht, lokal gruen. CI ist noch nie
gelaufen - der erste push von main ist der erste lauf. danach einen test absichtlich kaputt
machen und schauen ob es rot wird.

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

#### 1.6 host-gesteuerte spieler

**17.09.26: 1.6 und 1.7 als ein szenario geplant.** die klingel pausiert das spiel.
naechste stunde fehlen zwei, der host uebernimmt ihre plaetze und spielt sie am
host-rechner. kommen sie wieder, klickt der host den namen an, das handy scannt
code/qr und hat den platz zurueck. reihenfolge: split teil 1 + 2, 1.6, pause, 1.7.
entschieden:

- pause: knopf beim host. keine eingaben mehr, banner ueberall, plaetze umbauen geht
  weiter.
- wieder reinkommen: cookie wird bei jedem besuch verlaengert, sonst code vom host.
- uebernehmen: neue `player_id`, altes geraet fliegt raus. nie automatisch beim
  disconnect, ein gesperrtes handy trennt auch.
- entfernen nach spielstart nur ueber `left_at`, die daten bleiben. vorher wird wie
  bisher geloescht.
- der host legt plaetze in der lobby und im laufenden spiel an.
- spiele ohne aktivitaet enden nach n tagen, pausiert oder nicht. n stellt der host
  beim anlegen ein, standard 30. danach wird normal anonymisiert.

wunsch der forschungsgruppe. nicht jede klasse hat fuer jede person ein handy.
der host legt in der lobby zusaetzliche spieler an, die am host-rechner reihum
spielen. im extremfall laeuft das ganze spiel auf einem geraet.
kommt nach 1.5, laeuft also schon hinter dem CI-gate.

- `controlled_by_host` heisst heute "das ist die zeile des hosts". die zaehlregel
  aus 1.1 schliesst genau diese zeilen aus - host-gesteuerte spieler wuerden also
  nie abgewartet und zaehlen nicht gegen `max_players`.
  -> host-zeile am account erkennen (`Player.objects.host_rows()`, kommt mit 1.3),
  `controlled_by_host` heisst danach nur noch "spielt am host-rechner".
  datenmigration setzt es bei bestehenden host-zeilen auf False,
  `GameSessionCreateView` setzt es nicht mehr.
- die zaehlregel steht neunmal da, in zwei varianten: `rounds.py`, `views_join.py`,
  `views_rest.py` ueber `controlled_by_host`, `consumers.py` 5x ueber `user`.
  -> eine stelle (`without_host_rows()` + aktiv), alle rufen die auf.
- anlegen und entfernen: host-only endpoint in der lobby, zaehlt gegen
  `max_players`. den namen tippt der host, anonymisiert wird wie bei allen (1.3).
- handeln: der host schickt moves ueber die `player_id` des host-gesteuerten
  spielers in der url. `IsPlayerInGame` bekommt dafuer einen zweiten zweig, die
  stelle legt 1.2 an: host + spieler gehoert zum spiel + `controlled_by_host`.
- websocket: ein host-socket spricht fuer mehrere spieler. votes und
  stalemate-votes brauchen eine `player_id` in der nachricht, heute nimmt der
  consumer `self.player_id` (`consumers.py:910, 1103`).
- der host-bildschirm haengt meistens am beamer. ohne verdeckten zwischenschritt
  beim spielerwechsel sieht die ganze klasse jede wahl und jede stimme.
- der roster im spiel kommt nur aus redis (`GameConsumer`): eintrag beim connect,
  `online: False` beim disconnect, geloescht wird nie. gefunden beim testen 16.09.26:
  - host-gesteuerte spieler haben keinen eigenen socket, tauchen da also nie auf.
  - entfernte spieler bleiben als "offline" stehen. `player.left` wertet niemand aus,
    weder consumer noch frontend.
  - deploy/neustart: daphne ruft `disconnect()` dabei nicht auf. wer gerade verbunden
    war, bleibt `online: True`. wer danach nicht mehr reinkommt, bleibt so haengen.

  -> liste aus den `Player`-zeilen, redis nur noch fuer online + status. fuer das
  haengende `online`: ttl mit heartbeat oder reset beim start, im guide entscheiden.
- `PlayerDetailView.destroy` loescht immer die cookies des aufrufers. entfernt der
  host jemanden, sind seine eigenen weg. faellt heute nicht auf, der host wird ueber
  die session erkannt. -> nur loeschen wenn es der eigene spieler ist.

#### 1.7 sitzung auf anderes geraet

die sitzung haengt am cookie, also an einem browser. mit einem kurzen code auf ein
anderes geraet mitnehmen, ohne account.

- geraet 1 zeigt auf anfrage code + qr (`/app/join/<game_id>?code=...`).
  scannen fuehrt direkt weiter, abtippen geht ueber "sitzung fortsetzen" im join.
- der code liegt nur in redis: `code -> (game_id, player_id)`, 5 min ttl (17.09.26).
  einer pro platz, ein neuer code macht den alten ungueltig.
  einloesen ueber `cache.delete()`, das gibt nur einmal True -> nur einmal gueltig.
  keine tabelle, nichts zu anonymisieren.
- beim einloesen bekommt der spieler eine neue `player_id`. das alte cookie zeigt
  dann ins leere, geraet 1 ist raus. das cookie-format aus 1.2 bleibt, kein
  zweiter logout fuer alle. kosten: der redis-roster ist nach `player_id`
  geschluesselt und muss aufgeraeumt werden. moves und votes haengen am FK und
  bleiben.
- "raus" gilt erst beim naechsten request. der offene websocket von geraet 1 bleibt
  verbunden und bekommt weiter alles mit. -> consumer schliesst sich selbst (4403),
  wenn `player.left` oder die neue `player_id` seinen spieler betrifft. das fehlt heute
  schon beim entfernen durch den host.
- der code ist ein bearer-token. wer ihn am beamer sieht, uebernimmt den platz.
  deshalb kurz gueltig und nur auf anfrage.
- gleicher mechanismus fuer 1.6, in beide richtungen: wer spaeter mit handy kommt,
  scannt den code eines host-gesteuerten spielers und uebernimmt. handy leer ->
  host uebernimmt zurueck (`controlled_by_host` umschalten + neue `player_id`).

### phase 2 – frontend neu

nicht aufhuebschen, neu bauen. struktur, tests und design nach dem gleichen muster
wie im anderen projekt (jac).

#### stand 18.09.26 – frontend gegen backend geprueft

phase 1 ist durch, das frontend kennt davon nichts. was auseinanderlaeuft:

- **die drei 1.4-endpoints ruft niemand auf.** `lookup/`, `join/` und `<id>/lobby/`
  liegen da, der join laeuft weiter ueber die django-formulare.
- **von 1.6 und 1.7 ist im frontend nichts da**: `<id>/pause/`, `<id>/resume/`,
  `POST <id>/player/`, `player/<pid>/code/`, `player/<pid>/takeover/`, `seat/<code>/`.
- **events die ankommen und niemand liest**: `game.paused`, `game.resumed`,
  `player.revoked`, `player.left`, `player.taken_over`, `player.handed_over`,
  `simulation.progress`. `player.revoked` ist der schlimmste - das geraet merkt
  nicht, dass sein platz weg ist, und zeigt weiter ein spiel das ihm nicht gehoert.
- `lobby.roster` in `wsTypes.ts` schickt das backend nicht mehr, der roster kommt
  als `roster.update`.
- `api/game/sessions/` (toter hook) und `player/<pid>/mute/` laufen beide ins leere.
  **`mute/` hat keine url**: `MuteUnmutePlayerView` haengt an keinem pfad, der knopf
  in `PlayerDetail.tsx` bekommt einen 404. entweder route nachziehen oder view raus -
  `is_muted` liefert die lobby schon mit.
- `GET api/game/<id>/` verlangt `IsAuthenticated`, spieler bekommen 403. der
  spielerpfad muss `<id>/<player_id>/` nehmen.
- **vier `useGameSocket`-aufrufe auf einer seite** (GamePlay, StatusBar, GameLayout,
  GameDetail), dazu der chat-socket. das ist 2.2.
- die alten spielscreens sind englisch, mit emoji und rot/gruen/gelb. weder `de.ts`
  noch die design-tokens kommen darin vor.

eine backend-zeile haengt mit drin: der QR-code zeigt auf `{BASE_URL}/join/<id>/`
(`game/models.py:94`). zeigt er auf `/app/join/<id>/`, ist der template-join raus.
alte QR-bilder bleiben auf dem alten pfad, deshalb muss `JoinSessionView` dorthin
weiterleiten. kleiner guide, blockiert nichts - die SPA-route steht vorher.

#### reihenfolge

sieben schnitte, jeder auf einem eigenen branch off `main`, jeder fuer sich
reviewbar und lauffaehig. der alte screen bleibt stehen, bis sein ersatz da ist.

- **F1 `frontend/join-lobby`** - join (lookup -> join -> lobby) und lobby gegen 1.4.
  hier entsteht die 2.2-form (REST-snapshot + ws-reducer) am kleinsten ort.
- **F2 `frontend/game-core`** - ein socket pro spiel, ein reducer, alle events aus
  phase 1 drin, identitaet ueber `whoami`, pause-banner, `player.revoked`. das ist 2.2.
- **F3 `frontend/round-play`** - der zug: agenten, verkehrsmittel, route, absenden,
  "x von y abgeschickt", simulationsfortschritt. pathfinding bleibt wie es ist.
  der zug-screen wird ueber den platz parametrisiert, nicht ueber "ich" - F4 setzt
  genau darauf auf.
- **F4 `frontend/host-desk`** - der host-screen als leitpult (entschieden 18.09.26):
  der host spielt nicht selbst mit. plaetze anlegen und entfernen, uebernehmen,
  reihum spielen mit verdecktem zwischenschritt, pause, code + qr. damit laeuft ein
  ganzes spiel auf einem rechner. das ist 1.6 + 1.7 + 2.7 zusammen.
- **F5 `frontend/between-rounds`** - stats -> diskussion -> voting -> patt, auf den
  phasen-events.
- **F6 `frontend/summary`** - auswertung am spielende.
- **F7 `frontend/map-editor`** - editor portieren, kein redesign.

nach F6 steht der prototyp. erst dann der UX-durchgang (2.6), dann phase 3.
vitest laeuft pro schnitt mit, e2e pro screen sobald er steht, der komplette
durchlauf am ende.

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
ein socket pro spiel, nicht einer pro komponente (heute drei game-sockets auf
einer seite). und nie einen websocket im selben task aufmachen wie einen
REST-call, safari haengt den fetch dann auf (siehe 2.4).

#### 2.3 routen

SPA uebernimmt: join, lobby, spiel, auswertung, map editor, host-login.
Django behaelt: landing (`/`), legal, admin. `backend/template/` schrumpft entsprechend.
der QR-code zeigt dann direkt auf die SPA-route.

#### 2.4 bugs (aus den testrunden)

- `usePlayerList` und `useGameSessionList` in `hooks/gameHooks.ts` rufen `useQuery`
  auf, geben das ergebnis aber nicht zurueck. tote hooks. `useGameSessionList` zeigt
  ausserdem auf `api/game/sessions/`, den es seit 1.4 nicht mehr gibt - ersatzlos raus.
- ✅ safari/iOS: host-lobby bleibt nach "spiel erstellen" im ladebildschirm, erst ein
  neuer tab (logo) zeigt sie. webkit haengt einen fetch auf, der im selben task wie
  ein neuer websocket losgeht - request kommt nie zurueck (nginx loggt 499).
  socket einen tick spaeter, auf main seit 16.09.26.
- ✅ erfolgsmeldung vom letzten spiel taucht beim naechsten "spiel erstellen" auf.
  `messages.success` vor dem redirect in die SPA, die SPA zeigt django-messages nie
  an. die drei stellen sind raus, auf main seit 16.09.26.
  offen: die `messages.error` in `PlayerCreateView.dispatch` sieht auch niemand.
- runden counter im frontend nicht richtig. vermutlich `round.started`, das nie ankam
  (1.1 split teil 1). im neuen frontend nochmal pruefen.
- daten im frontend nicht persistent
- maximum player trumpft agents, somehow connected. backend-haelfte ist mit 1.4
  erledigt (join gibt 409 `full`), bleibt die anzeige im frontend.
- karte ueber bildrand, buttons fuer auswahlmoeglichkeiten nicht sichtbar, legende fehlt,
  chat horizontal scroll, edges nicht anklickbar, logout im dark mode nicht lesbar
  (die alte liste aus der README - beim neubau abarbeiten und die README-liste leeren)

#### 2.5 deutsch

komplette UI auf deutsch, ueber `de.ts`. `LANGUAGE_CODE` auf `de-de`.

#### 2.7 host-gesteuerte spieler und geraetewechsel

frontend-haelfte von 1.6 und 1.7. -> F4.

**18.09.26: der host ist leitpult, kein spieler.** ziel ist, dass ein ganzes spiel
auf einem rechner laufen kann - die spieler kommen reihum an den host-rechner.
ob die lehrkraft mitspielt ist dann egal: sie legt sich einen platz an und steuert
den. die host-eigene `Player`-zeile bleibt stumm (nur cookie-traeger), so wie
`playing()` sie ohnehin schon behandelt. in der schule spielt die lehrkraft
nicht von sich aus mit.

- lobby: host legt spieler an und entfernt sie.
- spielscreen am host: spielerwechsel reihum, mit verdecktem zwischenschritt
  (beamer). "x von y abgeschickt" zaehlt die host-gesteuerten mit.
- join: zwei wege, spiel-id oder "sitzung fortsetzen" mit code.
- spielscreen am handy: "auf anderes geraet" zeigt code + qr.
- host kann einen spieler uebernehmen und wieder abgeben (qr fuer den platz).

#### 2.6 ui / ux

- design einmal durchziehen, dark/light sauber.
- ✅ landing neu (17.09.26): liniennetz statt platzhalterbild. vier linien (auto,
  bus & bahn, rad, zu fuss) laufen von "zu hause" bis "schule", jeder abschnitt haengt
  an einer station. impressum/datenschutz/cookies fest im footer. im hellen modus
  hatten alle django-seiten keine farben (`text-main`, `bg-surface` usw. gab es nie
  als klasse), repariert. ueberall duzen.
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
- ein spiel komplett am host-rechner, nur host-gesteuerte spieler (1.6).
- geraetewechsel mitten in der runde, altes geraet fliegt raus (1.7).
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
- `workflow-prod.yml` ist noch nie gelaufen, die live-kiste wird von hand deployed.
  entschieden 16.09.26: workflow bleibt wie beim alten staging. vier secrets
  (`PROD_HOST`, `PROD_USER`, `PROD_KEY`, `PROD_KNOWN_HOSTS`), ein normaler key fuer
  den user `deploy`, kein deploy-skript. ob github actions per ssh durchkommt, zeigt
  erst der erste lauf.
- die deploy-zeile auf main ist noch die alte (`/srv/commute`, `pull --ff-only`).
  rollback per `git push -f origin <alt>:prod` hat damit nie funktioniert,
  `pull --ff-only` sagt dann "Already up to date". neue zeile mit `/commute` und
  `checkout -B`, schritt 1 im deploy-guide.
- 17.09.26: deploy-guide zurueckgestellt, 1.6/1.7 gehen vor.
- ohne staging gibt es keine stufe mehr zwischen merge und live. das gate ist dann
  die testsuite, siehe 1.5. deploy nicht waehrend einer laufenden testrunde.
- kiste (16.09.26): debian 13, checkout unter `/commute` (nicht `/srv/commute`),
  platte 9.7G zu 81% voll. updates kommen rein (von wem?), rebootet hat keiner -
  21 tage mit neuerem kernel auf der platte. user `deploy` (docker, kein sudo) ist angelegt.
- **postgres 18 liegt in einem anonymen volume.** `postgres-data` haengt auf
  `/var/lib/postgresql/data`, dem pfad von vor 18, und ist leer. die daten liegen in
  `/var/lib/postgresql/18/docker`, lokal und auf der kiste. restart, reboot und deploy
  ueberlebt das, `docker compose down` + `up` nicht (leere db, altes volume verwaist).
  -> volume auf `/var/lib/postgresql` umhaengen, daten per dump/restore umziehen.
  vor der uebergabe. bis dahin auf der kiste nie `down` oder `volume prune`.
- backups gibt es keine.

offen aus phase 0, liegt alles nicht im repo:

- cert auf der live-kiste tauschen. geprueft 16.09.26: die kiste terminiert TLS selbst,
  mit genau dem alten self-signed cert aus dem repo (CN=localhost, laeuft 20.11.26 ab).
  jeder besucher klickt eine warnung weg, der key ist public.
  -> beim naechsten deploy neuen key erzeugen. danach ein richtiges zertifikat:
  lets encrypt ginge technisch (kein CAA, port 80 offen), vorher die TU fragen.
  HSTS erst danach.
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
