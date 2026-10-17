# Testfälle

Was das Spiel können muss, Fall für Fall. Zwei Zwecke: nachhalten was tatsächlich läuft, und
die Vorlage für die Integrationstests — die werden aus dieser Liste geschrieben,
nicht neu erfunden.

**Status heißt:**

| Status      | bedeutet                                                                                  |
| ----------- | ----------------------------------------------------------------------------------------- |
| `geht`      | einmal wirklich durchgespielt, im Browser oder von einem Test. Nicht "sieht richtig aus". |
| `ungeprüft` | gebaut, aber noch nie durchgespielt                                                       |
| `offen`     | noch nicht gebaut                                                                         |
| `kaputt`    | durchgespielt und fällt durch                                                             |

Die Spalte **E2E** trägt den Playwright-Test, sobald es einen gibt. `-` heißt: von Hand geprüft.

Geprüft wird in WebKit — das ist Safari und jeder Browser auf dem iPhone — hell und dunkel,
390px und Desktop.

---

## J — beitreten

| ID   | Fall                                         | Erwartet                                                | Status    | E2E |
| ---- | -------------------------------------------- | ------------------------------------------------------- | --------- | --- |
| J-01 | Spiel-ID gibt es nicht                       | „Diesen Code gibt es nicht. …", zurück zur Eingabe      | geht      | -   |
| J-02 | Lobby offen, kein Passwort                   | Name rein, Spieler angelegt, Lobby                      | geht      | -   |
| J-03 | Spiel läuft schon                            | 409 `started`, Formular gesperrt                        | geht      | -   |
| J-04 | Spiel ist vorbei                             | 409 `ended`, Formular gesperrt                          | geht      | -   |
| J-05 | Spiel ist voll                               | 409 `full`, Formular gesperrt                           | geht      | -   |
| J-06 | Passwort nötig, richtig                      | kommt rein                                              | geht      | -   |
| J-07 | Passwort nötig, falsch                       | 403, Feld bleibt stehen, Name bleibt stehen             | geht      | -   |
| J-08 | Passwort nötig, keins eingegeben             | wie falsches Passwort                                   | geht      | -   |
| J-09 | kein Name eingegeben                         | Meldung, gar kein Request                               | geht      | -   |
| J-10 | Spiel füllt sich während des Tippens         | erst beim Absenden 409 `full`                           | offen     | -   |
| J-11 | QR-Code scannen                              | landet direkt auf `/app/join/<ID>`                      | geht      | -   |
| J-12 | Platz-Code ins Feld auf `/app/join`          | „Du übernimmst den Platz von …“, dann Platz übernommen, neue `player_id` | geht | `codes.spec.ts` |
| J-13 | Code abgelaufen oder schon benutzt           | 404, sagt dass der Code weg ist                         | geht      | -   |
| J-14 | Code, aber der Browser hat schon einen Platz | 409 `seated`                                            | ungeprüft | -   |
| J-15 | Code, aber man ist der Host des Spiels       | 409 `host`                                              | geht      | -   |
| J-16 | zweimal aus demselben Browser beitreten      | kein zweiter Platz                                      | offen     | -   |
| J-17 | alte Beitrittsseite `/join/`                 | 404 — der einzige Eingang ist `/app/join`               | geht      | `credentials.spec.ts` |
| J-18 | „Los“ auf der Startseite, mit ID             | landet auf `/app/join/<ID>`                             | geht      | `credentials.spec.ts` |
| J-19 | „Los“ auf der Startseite, ohne ID            | landet auf `/app/join`, das nach der ID fragt           | geht      | `credentials.spec.ts` |
| J-20 | Startseite: das ID-Feld | der Platzhalter sagt „z. B. 4F2A9C“, damit man ihn nicht für eine ID hält, die man eintippen soll; bei 375px passt er ins Feld, bei 320px wird er abgeschnitten | geht | - |
| J-21 | Spiel-ID ins Feld auf `/app/join`            | Namensfeld, dann Lobby                                  | geht      | `codes.spec.ts` |
| J-22 | alte Wege `/api/game/lookup/`, `join/`, `seat/` | keine Antwort mehr, kein Redirect                       | geht      | `codes.spec.ts` |
| J-23 | Platz-Code vertippt, mehr als 20 Mal         | 429, die Spiel-ID geht weiter                           | geht      | `test_throttle.py` |

## L — lobby

| ID   | Fall                                       | Erwartet                                                                                      | Status | E2E            |
| ---- | ------------------------------------------ | --------------------------------------------------------------------------------------------- | ------ | -------------- |
| L-01 | eigener Platz                              | ist als „du" markiert                                                                         | geht   | -              |
| L-02 | zweites Gerät tritt bei                    | erscheint **ohne Reload**                                                                     | geht   | -              |
| L-03 | Spieler verlässt das Spiel                 | verschwindet aus der Liste                                                                    | offen  | -              |
| L-04 | Gerät schließt den Tab                     | nach ~90 s „nicht verbunden", Eintrag bleibt                                                  | geht   | -              |
| L-05 | Host startet das Spiel                     | Lobby merkt es ohne Reload                                                                    | geht   | -              |
| L-06 | Einstellungen                              | Agenten, Runden, CO₂-Budget, Chat stimmen                                                     | geht   | `chat.spec.ts` |
| L-07 | Host entfernt einen Spieler                | dessen Gerät: „Dein Platz ist weg", mit Grund                                                 | geht   | -              |
| L-08 | Platzzahl                                  | die Host-Zeile zählt nicht mit                                                                | geht   | -              |
| L-09 | Platz an der Leitstelle                     | ist als solcher markiert                                                                      | geht   | -              |
| L-10 | Host legt einen Platz an                   | erscheint bei allen, zählt gegen `max_players`                                                | geht   | -              |
| L-11 | Host entfernt einen host-gesteuerten Platz | verschwindet, Runde wartet nicht mehr                                                         | geht   | -              |
| L-12 | „Spiel verlassen"                          | Platz weg, Cookies weg, zurück zum Start                                                      | geht   | -              |
| L-13 | Lobby ohne gültiges Cookie                 | 403 → „neu beitreten"                                                                         | geht   | -              |
| L-14 | Spiel ohne Karte angelegt                  | Start gesperrt und sagt warum, statt stumm nichts zu tun; die API antwortet 409 `no-map`      | geht   | -              |
| L-15 | Spiel mit Passwort                         | das Passwort steht an der Leitstelle unter der Spiel-ID, so wie es getippt wurde              | geht   | lobby          |
| L-16 | „Einladung kopieren"                       | kopiert Name, Link, Spiel-ID und Passwort                                                     | geht      | lobby          |
| L-18 | Kopieren wird verweigert                   | der Text steht in einem Feld zum Markieren                                                    | ungeprüft | -              |
| L-17 | Host schaltet den Chat in der Lobby        | aus und wieder an; die Handys folgen ohne Reload, der Chat verschwindet und kommt wieder      | geht   | lobby          |

## V — verbindung

| ID   | Fall                                    | Erwartet                                                                          | Status | E2E |
| ---- | --------------------------------------- | --------------------------------------------------------------------------------- | ------ | --- |
| V-01 | Backend startet neu, Socket fällt weg   | verbindet allein neu, Zustand stimmt danach — auch was währenddessen passiert ist | geht   | -   |
| V-02 | Socket wird abgelehnt (4403)            | kein Reconnect-Sturm, Screen sagt was los ist                                     | geht   | -   |
| V-03 | Verbindung weg                          | Hinweis am Screen, statt eingefrorenem Spiel                                      | geht   | -   |
| V-04 | zwei Tabs desselben Spielers            | zeigen dasselbe, keiner überschreibt den anderen                                  | offen  | -   |
| V-05 | Safari: Socket und fetch im selben Task | fetch hängt nicht                                                                 | geht   | -   |
| V-06 | Backend-Neustart                        | niemand bleibt für immer „online" (Presence-TTL)                                  | geht   | -   |
| V-07 | Handy sperrt und wacht wieder auf       | Platz ist noch da, Cookie verlängert                                              | offen  | -   |

## P — pause

| ID   | Fall                              | Erwartet                                                                                                                                         | Status | E2E |
| ---- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------ | --- |
| P-01 | Host pausiert                     | Banner auf allen Screens, ohne Reload                                                                                                            | geht   | -   |
| P-02 | Host hebt die Pause auf           | Banner weg, ohne Reload                                                                                                                          | geht   | -   |
| P-03 | Zug abschicken während Pause      | gar nicht erst möglich: Banner, Auswahl und Knopf gesperrt; die 409-Meldung greift für den Fall, dass die Pause zwischen Klick und Request kommt | geht   | -   |
| P-04 | Pause mitten in der Zwischenrunde | Phase bleibt stehen, nichts rutscht weiter                                                                                                       | offen  | -   |
| P-05 | Pause über eine Schulstunde       | Cookies verlängert, Platz danach noch da                                                                                                         | offen  | -   |
| P-06 | Plätze umbauen während Pause      | geht weiter                                                                                                                                      | geht   | -   |

## R — die runde

| ID   | Fall                                                           | Erwartet                                                                                                                     | Status    | E2E                       |
| ---- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------- | ------------------------- |
| R-01 | Agenten der Runde                                              | alle mit Start und Ziel sichtbar                                                                                             | geht      | -                         |
| R-02 | Verkehrsmittel wählen                                          | pro Agent, vier Linien                                                                                                       | geht      | -                         |
| R-03 | Route wählen                                                   | Vorschau über das Pathfinding                                                                                                | geht      | -                         |
| R-04 | abschicken                                                     | Platz steht auf „abgeschickt"                                                                                                | geht      | -                         |
| R-05 | Fortschritt                                                    | „x von y abgeschickt", host-gesteuerte zählen mit                                                                            | geht      | -                         |
| R-06 | letzter Spieler schickt ab                                     | Runde wird gerechnet                                                                                                         | geht      | -                         |
| R-07 | Simulation läuft                                               | Fortschritt kommt an (`simulation.progress`) und zählt, wer zu Hause ist, über beide Wege bis 100 %                           | ungeprüft | `test_rounds.py`          |
| R-08 | Auto auf einer Kante ohne Straße                               | wird abgelehnt, Client wie Server                                                                                            | geht      | `edge-rules.test.ts`      |
| R-09 | Rundenzähler                                                   | zeigt die richtige Runde                                                                                                     | ungeprüft | -                         |
| R-10 | Spieler verlässt mitten in der Runde                           | Runde kann trotzdem fertig werden                                                                                            | offen     | -                         |
| R-11 | Reconnect mitten in der Runde                                  | schon abgeschickte Wahl ist noch da                                                                                          | geht      | -                         |
| R-12 | ÖPNV-Route gibt es nicht                                       | sagt es und lässt eine andere Linie wählen                                                                                   | geht      | -                         |
| R-13 | Chat während der Runde                                         | erreichbar                                                                                                                   | geht      | `chat.spec.ts`            |
| R-14 | ÖPNV fahren und das letzte Stück laufen                        | Runde wird gerechnet, nicht abgebrochen                                                                                      | geht      | -                         |
| R-15 | Bus & Bahn auf der ausgelieferten Karte                        | findet für jedes der 36 Wohnort-Arbeitsplatz-Paare eine Verbindung                                                           | geht      | `replay.spec.ts`          |
| R-16 | Auto auf einem Tor (Busspur oder Radweg nimmt die letzte Spur) | wird gar nicht erst als Route angeboten, statt beim Abschicken abgelehnt                                                     | geht      | `edge-rules.test.ts`      |
| R-17 | Luftlinie                                                      | steht am Gruppe, sobald er ausgewählt ist — vor jeder Wahl                                                                 | geht      | -                         |
| R-18 | zu weit zu Fuß (über 5 km) oder mit dem Rad (über 15 km)       | der Modus ist nicht wählbar, wenn schon die Luftlinie zu weit ist; sonst sagt die Route, dass es zu weit ist                 | geht      | `trip-limits.test.ts`     |
| R-19 | Stau im Mittel der Runden bisher auf der Karte                 | dickere Linie, wo es langsamer war — keine Farbskala                                                                         | geht      | `traffic.test.ts`         |
| R-20 | „schnellste"                                                   | rechnet mit den gemessenen Geschwindigkeiten im Mittel der Runden bisher, nicht mit dem Tempolimit                         | geht      | `maps.tests.test_traffic` |
| R-21 | Route auf der Karte                                            | in der Farbe und im Strich ihres Verkehrsmittels, nicht überall bernstein                                                    | geht      | -                         |
| R-22 | Seite neu laden mitten in einer angefangenen Runde             | die schon gewählten Verkehrsmittel sind wieder da, die Routen werden neu gesucht; nicht gewählte Gruppen bleiben leer      | geht      | `round-draft.spec.ts`     |
| R-23 | Hin- und Rückweg pro Gruppe                                    | unter der gefundenen Route steht „zurück x min“; abgeschickt werden beide Wege, der Rückweg mit demselben Verkehrsmittel gesucht | geht      | `round-draft.spec.ts`     |
| R-24 | Ziel erreichbar, aber kein Weg zurück (Einbahnstraße)          | „Die Gruppe kommt hin, aber nicht wieder nach Hause.“, kein Neu-Versuch, Losfahren bleibt gesperrt                         | ungeprüft | -                         |
| R-25 | Runde ohne Rückweg abschicken (direkt an der API)              | 400, `return_route` fehlt; ein Rückweg, der nicht am Zuhause endet oder gegen eine Einbahnstraße fährt, wird abgelehnt     | geht      | -                         |
| R-26 | Route suchen lassen                                            | erst wird die Suche gezeigt, in der Primärfarbe; die Route erscheint, wenn sie fertig ist, nicht vorher                      | geht      | `spielbildschirme.spec.ts`     |
| R-27 | sehr kurzer Weg                                                | die Suche ist trotzdem zu sehen, mindestens eine gute halbe Sekunde                                                          | geht      | `search-trace.test.ts`    |
| R-28 | Zuhause und Ziel auf dem Handy                                 | kleiner als bisher, decken die Straßen daneben nicht zu, sind aber noch zu finden (390px)                                    | geht      | -                         |
| R-29 | zu Fuß durch den Tiergarten                                    | von einem Wohnort an der S-Bahn Bellevue zur Arbeit Brandenburger Tor, Lützowplatz oder TU Berlin lässt sich zu Fuß gehen, 2,8–4,1 km über die Wege im Tiergarten, gepunktet auf der Karte; zur Arbeit Justizministerium „Weiter als 5.0 km“ (WebKit)      | geht      | -                         |
| R-30 | Bus und Bahn mit derselben Nummer | eine Fahrt bleibt auf ihrer Linie: der Rückweg von Arbeit Brandenburger Tor nach Wohnort 4–6 fährt Bus 100 bis Großer Stern und steigt in die 101 um — vorher fuhr er als „Bus 100“ ab S Tiergarten auf den Gleisen der Stadtbahn weiter, weil Bus 2 und Zug 2 für eine Linie galten; jede Fahrt auf der ausgelieferten Karte geht von einer Haltestelle ihrer Linie zur nächsten      | geht | `pt-routing.test.ts` |
| R-31 | Bus und Bahn: der Fußweg am Ende | hält die schnellste Linie mehr als 2 km zu Fuß vom Ziel, nimmt der Router die langsamere, die näher hält, statt gar keine Verbindung zu finden; auf der ausgelieferten Karte mit „wenigste Umstiege“ 12 der 72 Wege jeder Version, die vorher keine Verbindung hatten; mit „schnellste“ bleibt jeder Weg, wie er war      | geht | `pt-routing.test.ts` |
| R-32 | Bus und Bahn: einsteigen an der Haltestelle | eine Kreuzung, an der nur die Hin- und die Rückrichtung derselben Linie vorbeifahren, ist keine Haltestelle („101“ und „101 reverse“ sind eine Linie, auch „U2 Reverse“); wo zwei Linien sich kreuzen, kann man weiter umsteigen      | geht | `pt-routing.test.ts` |
| R-33 | Bus und Bahn heißt fahren | einsteigen und an derselben Haltestelle gleich wieder aussteigen ist keine Fahrt: wo sonst nur Laufen bliebe, heißt es „keine Verbindung“, und der Weg zur ersten Haltestelle bleibt unter 2 km — vorher verlängerte ein Ein- und Aussteigen ihn bis 5,5 km      | geht | `pt-routing.test.ts` |
| R-34 | eine Station mit dem Zug, dann zu Fuß | kommt an, auch wenn Einsteigen und Aussteigen in denselben Takt fallen — vorher ging der Fußweg danach nie weiter, der Durchlauf lief bis an die Grenze von 1000 Ticks und jede Linie fuhr für ihn weiter (gebaute Box, 75 % Auto: 686 Menschen in einer Runde); auf der ausgelieferten Karte war es nie so, ihre Zahlen bleiben      | geht | `test_linkqueue` |
| R-35 | Bus und Bahn: eine Linie hält zweimal an derselben Haltestelle | wer an der Stader Landstraße zu Arbeit Lesum will, steigt nur in die 94 auf dem Weg hinein, nicht in die auf dem Weg hinaus, die nie mehr hinkommt — vorher fuhr er mit ihr bis ans Ende und sprang von dort zu seiner Haltestelle (gebautes Bremen, 50 % Auto: 549 Fahrgäste auf dem Hinweg); der Router fährt nicht vom zweiten Halt in den ersten weiter (die 58 an Sodenmatt noch einmal um die Schleife), sondern steigt dort um und wartet      | geht | `test_linkqueue`, `pt-routing.test.ts` |
| R-36 | Bus und Bahn: ein Ring fährt im Kreis | eine Linie, die endet, wo sie anfängt (S41, die 58 in Bremen), fährt weiter: wer über den Anfang hinaus will, bleibt sitzen und fährt mit der nächsten Abfahrt weiter, die Zeit bis dahin ist Wartezeit, im Router wie in der Simulation — vorher wurde er am Ende abgesetzt und lief vom Halt hinter dem Anfang weiter      | geht | `test_linkqueue`, `pt-routing.test.ts` |
| R-37 | Bus: von der Busspur auf eine kurze Straße | wo nur ein Bus Platz hat, fährt der zuerst angekommene zuerst weiter — vorher war die Reihenfolge beliebig, und ein Bus mit Fahrgästen ließ jeden Takt einen späteren, leeren vor (gebautes Berlin, X83 an der Egestorffstraße: ~30 h, und jede Linie fuhr für seine Fahrgäste weiter); auf der ausgelieferten Karte bleibt jede Runde bis aufs Gramm      | geht | `test_linkqueue` |
| R-38 | Bus und Bahn: der Anteil am Fahrplan | eine Runde rechnet jeden Fahrzeugkilometer, CO₂ und Kosten, mit dem Anteil des Spiels: die Anteile der Mitfahrenden, die Linien, die niemand benutzt hat, die Fahrten nach dem Fahrplan; die Runde selbst bleibt dieselbe, das Ticket auch; ein Spiel übernimmt den Anteil seiner Karte, wenn es beginnt, und behält ihn, wenn die Karte danach neu gemessen wird; eine Karte ohne Anteil bezahlt den ganzen Fahrplan      | geht | `test_linkqueue`, `test_simulation`, `test_models` |
| R-39 | Pendlertypen in der Runde | jede Gruppe zeigt unter ihrem Ziel ihren Pendlertyp, Name und Satz; die Gruppen eines Platzes bekommen verschiedene, solange die Liste reicht, danach geht es von vorn los; ein Spiel ohne Pendlertypen zeigt keinen | geht | `test_personas` |
| R-40 | Wo eine Gruppe wohnt | jede Gruppe nennt ihren Wohnort und ihr Ziel („Wohnort 3 → Arbeit TU Berlin“), die Karte zeigt das Zuhause der gewählten Gruppe; aus: alle Gruppen eines Platzes wohnen am selben Ort, der nächste Platz bekommt einen freien; „ausbalanciert“: die Gruppen eines Platzes wohnen an verschiedenen Orten über die Karte verteilt, jeder Wohnort und jeder Arbeitsplatz hat gleich viele Gruppen, ± 1, ein Platz, der gegangen ist, gibt seine Wohnorte frei; eine Route, die nicht am Zuhause ihrer Gruppe beginnt, lehnt der Server ab | geht | `test_deal`, `test_rounds` |
| R-41 | Wer losfährt, lässt den Verkehr zuerst | ein Auto, das an seiner Tür auf eine Straße will, wartet, solange auf einer Straße in diesen Knoten ein Auto durch ist, das auf dieselbe Kante will; es fährt, sobald das Auto abbiegt, noch nicht durch ist oder die Straße in diesem Takt nichts mehr schicken kann; erst die Straße, dann die Tür; ein Bus fährt an seiner Endhaltestelle pünktlich ab. Vorher nahmen die Autos von der Tür den Platz auf einer vollen Straße zuerst, jeden Takt, und auf der gebauten Box blieb der Heimweg 4.070 Minuten auf einer Schleife von sechzehn Straßen in Mitte stehen | geht | `test_linkqueue` (`PullingOutGivesWayTests`) |
| R-42 | Der Heimweg streut breiter als der Hinweg | die Abfahrten am Abend streuen 1,6-mal so breit wie die am Morgen (SrV 2018 Berlin: Feierabend ist zu mehr verschiedenen Zeiten) | geht | `test_linkqueue` (`EveningSpreadTests`) |
| R-43 | Dieselbe Runde unter sqlite und Postgres | die Simulation liest Kanten, Linien und Wege in der Reihenfolge der Zeilen, nicht ihrer Namen; Namen sortieren die beiden Datenbanken verschieden, und eine Runde mit Mitfahrenden lag um 1,5 % auseinander | geht | `test_simulation` (`ReadOrderTests`) |

## A — die animation

Die Animation ist der erste Teil der Statistik-Phase, keine eigene Phase: erst zuschauen, dann
lesen, dann „Weiter". Sie blockiert nie — überspringen ist ein Klick, und eine Runde ohne
Aufzeichnung zeigt einfach ihre Zahlen.

| ID   | Fall                          | Erwartet                                                           | Status    | E2E              |
| ---- | ----------------------------- | ------------------------------------------------------------------ | --------- | ---------------- |
| A-01 | Runde ist gefahren            | die Animation läuft zuerst, die Zahlen kommen danach               | geht      | `replay.spec.ts` |
| A-02 | „Überspringen"                | Zahlen und „Weiter" sofort da                                      | geht      | `replay.spec.ts` |
| A-03 | „Nochmal ansehen"             | läuft von vorn, die Zahlen bleiben stehen                          | geht      | `replay.spec.ts` |
| A-04 | „Anhalten" und weiter         | Punkte stehen still, die Uhr auch                                  | geht      | `replay.spec.ts` |
| A-05 | Uhr                           | läuft in Simulationsminuten und wird im Abfluss sichtbar schneller | geht      | -                |
| A-06 | Stau                          | Punkte, die stehen bleiben; die Straße wird dicker                 | geht      | -                |
| A-07 | Warteschlange vor der Haustür | Gruppe am Knoten, **nicht** auf der Kante                          | geht      | -                |
| A-08 | Haltestelle                   | Gruppe wächst und schrumpft, Bus rollt mit und ohne Gruppen      | ungeprüft | -                |
| A-09 | Gruppe im Bus               | wird nicht zusätzlich als eigener Punkt gezeichnet                 | ungeprüft | -                |
| A-10 | Ende                          | hält ein paar Sekunden auf dem letzten Moment                      | geht      | -                |
| A-11 | jemand ist nicht angekommen   | sagt es, statt „alle sind angekommen" — gezählt vom Simulator, auch wer noch vor der Haustür stand. Ein Weg läuft, bis alle da sind: vorkommen kann es nur bei kaputten Kartendaten oder wenn die Fehlergrenze von 1000 Ticks greift       | geht      | `counts.test.ts`, `test_simulation.py` |
| A-12 | Runde ohne Aufzeichnung       | sagt es in einer Zeile, die Zahlen stehen trotzdem da              | ungeprüft | -                |
| A-13 | ein Punkt sind 10 Menschen    | steht unter der Karte, als ganze Zahl (vorher 50)                  | geht      | `replay.spec.ts` |
| A-14 | kein Punkt gehört jemandem    | alle Geräte sehen dieselbe Animation, niemand ist markiert         | geht      | -                |
| A-15 | Leitstelle                      | zeigt dieselbe Animation, vor den Zahlen                           | geht      | `replay.spec.ts` |
| A-16 | 390px und dunkel              | Karte lesbar, keine Querscrollbar                                  | geht      | -                |
| A-17 | Bildrate                      | volle Karte, 6 400 Menschen: läuft rund in WebKit — 60 fps bei ~800 Punkten, auch bei ~1 450 (Desktop; Telefon nicht gemessen)      | geht      | -                |
| A-18 | zwei Minuten                  | Hin- und Rückweg, 6 400 Menschen: 120,0 s Wandzeit für 120 s Wiedergabe, 60 fps, auch bei 390px (WebKit Desktop; Telefon nicht gemessen)     | geht      | -                |

`A-08` bis `A-12` und `A-17` stehen offen, weil sie in dem Durchlauf nicht vorkamen: in der
gefahrenen Runde ist **jeder angekommen**, also war nur die ehrliche Variante des Schlussbilds nicht
zu sehen, und die Haltestellen-Schlange über die Zeit sowie die Bildrate mit sechs Plätzen sind noch
nicht gemessen.

## Z — zwischen den runden

| ID   | Fall                               | Erwartet                                                                                                                 | Status    | E2E             |
| ---- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------- | --------------- |
| Z-01 | Runde fertig                       | Ergebnis pro Spieler: CO₂, Kosten, Zeit                                                                                  | geht      | numbers.spec.ts |
| Z-02 | alle haben gelesen                 | weiter zur Diskussion                                                                                                    | geht      | leitstelle      |
| Z-03 | keine Kartenversionen zur Wahl     | direkt die nächste Runde                                                                                                 | geht      | -               |
| Z-04 | Host öffnet die Abstimmung         | nur aus der Diskussion heraus                                                                                            | geht      | leitstelle      |
| Z-05 | abstimmen                          | Fortschritt „x von y"                                                                                                    | geht      | leitstelle      |
| Z-06 | Gleichstand                        | Patt-Runde                                                                                                               | geht      | -               |
| Z-07 | Patt: Mehrheit will nochmal        | gleiche Optionen, Stimmen gelöscht                                                                                       | ungeprüft | -               |
| Z-08 | Patt: Mehrheit will nicht          | Karte bleibt wie sie ist                                                                                                 | geht      | -               |
| Z-09 | Host beendet das Patt              | „so lassen"                                                                                                              | ungeprüft | -               |
| Z-10 | Reconnect mitten in der Abstimmung | **dieselben** Optionen, nicht neu gezogen                                                                                | geht      | -               |
| Z-11 | Gewinner wird angewendet           | nächste Runde läuft auf der neuen Karte                                                                                  | geht      | leitstelle      |
| Z-12 | zweimal abstimmen                  | sagt „schon abgestimmt", statt einen Fehler zu zeigen                                                                    | geht      | -               |
| Z-13 | Pause in einer Phase               | Banner da, Phase läuft nicht weiter                                                                                      | geht      | -               |
| Z-14 | Host stimmt für seine Plätze ab    | einer nach dem anderen, verdeckter Zwischenschritt                                                                       | geht      | leitstelle      |
| Z-15 | Tabelle nach der Runde             | steht auf „pro Person" und sagt, für wie viele Menschen eine Gruppe steht                                               | geht      | numbers.spec.ts |
| Z-16 | Schalter „alle Pendler"            | jede CO₂- und Kostenzelle wird eine andere Zahl; die Zeit bleibt der Schnitt pro Weg                                     | geht      | numbers.spec.ts |
| Z-17 | Zeilen ergeben nicht die Summe     | Zeile „Linien ohne Gruppen" schließt die Lücke genau, mit einem Satz warum                                             | geht      | numbers.spec.ts |
| Z-18 | bezahlt gegen gekostet             | steht unter der Tabelle; am eigenen Platz persönlich, an der Leitstelle für alle Pendler                                         | geht      | numbers.spec.ts |
| Z-19 | „Wie wird gerechnet?"              | Overlay mit Maßstab, Zeit, Kosten, Fahrplan und Stau                                                                     | geht      | numbers.spec.ts |
| Z-20 | Wartebildschirme                   | Erklärtext steht voll ausgeschrieben da — beim Warten auf die Runde und in der Diskussion, **nie** neben dem Stimmzettel | ungeprüft | -               |
| Z-21 | Zeit im Ergebnis                   | Hin- und Rückweg zusammen, als Mittel über die Gruppen; CO₂ und Kosten sind die Summe beider Wege                        | geht      | -               |
| Z-22 | Stau auf der Karte der Wahl        | die gerade gefahrene Runde, am Handy und an der Leitstelle; vorher stand dort die Runde davor, nach Runde 1 gar keine      | geht      | zwischen-den-runden    |
| Z-23 | Karte in der Diskussion            | dieselbe Karte wie bei der Wahl, mit Stau, darüber oder daneben                                                          | geht      | zwischen-den-runden    |
| Z-24 | Leitstelle während der Wahl        | sagt, wie man abstimmt: tippen, klicken oder die Zahl; „reihum weitergeben“ steht nicht da, wenn an der Leitstelle niemand spielt      | geht      | zwischen-den-runden    |
| Z-25 | jemand ist während der Wahl gegangen | „Plätze anzeigen“ an der Leitstelle, Platz entfernen, die Wahl schließt ohne den Platz                                   | geht      | zwischen-den-runden    |
| Z-26 | Karte daneben auf dem Beamer       | die Spielbildschirme gehen bis an den Rand, die Karte bekommt die halbe Breite statt eines Drittels                      | geht      | -               |
| Z-27 | Plätze an der Leitstelle in der Wahl | „Gib den Rechner reihum weiter“ steht über der Liste der Plätze, die noch abstimmen                                      | geht      | leitstelle      |
| Z-28 | eine Gruppe fährt Rad              | Kosten und „selbst bezahlt“ sind gleich, 0,03 € pro km und Person, kein CO₂; zu Fuß bleibt beides 0                       | geht      | -               |
| Z-29 | Änderung auf der Karte             | jede Option hat „Auf der Karte zeigen“, in der Diskussion und auf dem Stimmzettel, am Handy und an der Leitstelle: die Karte zeigt, was sie gegenüber der gespielten Version ändert — Straßen blau, Bus & Bahn gelb, was wegfällt hohl; der Stau tritt so lange zurück | geht      | leitstelle      |

## E — spielende

| ID   | Fall                             | Erwartet                                                                                           | Status    | E2E             |
| ---- | -------------------------------- | -------------------------------------------------------------------------------------------------- | --------- | --------------- |
| E-01 | letzte Runde gespielt            | Ende mit Grund `max_rounds`                                                                        | geht      | leitstelle      |
| E-02 | CO₂-Budget überschritten         | Ende mit Grund `co2_limit`                                                                         | geht      | -               |
| E-03 | Auswertung                       | pro Spieler über alle Runden, drei Reihenfolgen, niemand gekürt                                    | geht      | -               |
| E-04 | Host beendet von Hand            | Ende, alle sehen es                                                                                | geht      | -               |
| E-05 | Spiel endet wegen Inaktivität    | meldet heute `max_rounds` — **falsch**, offen im Backend                                           | kaputt    | -               |
| E-06 | nach dem Ende                    | Anonymisierung greift nach `ANONYMISE_GRACE_HOURS`                                                 | offen     | -               |
| E-07 | Auswertung Runde für Runde       | eine Linie mit einem Halt pro Runde; bei nur einer Runde keine                                     | geht      | leitstelle      |
| E-08 | Auswertung neu geladen           | Zahlen und Grund stehen weiter da, ohne Socket                                                     | geht      | -               |
| E-09 | Auswertung auf dem Handy         | eigener Platz in allen drei Listen mit „du" markiert                                               | geht      | -               |
| E-10 | Spiel mit den Vorgabewerten      | endet **nicht** in Runde 1; sechs Runden sind fahrbar, wenn die Klasse umsteigt                    | geht      | -               |
| E-11 | Was der Fahrplan gekostet hat    | eigener Block, Klassenmaßstab, mit dem Anteil auf Linien, die niemand genutzt hat                  | geht      | numbers.spec.ts |
| E-12 | die drei Listen                  | sortieren pro Weg, nicht auf den Summen; wer vorzeitig raus ist, ist markiert; Schalter auch hier  | geht      | numbers.spec.ts |
| E-13 | Was ihr geändert habt      | eine Zeile pro Abstimmung mit Stimmen und Gewinner; ohne Abstimmung sagt es das                    | geht      | numbers.spec.ts |
| E-14 | „davon selbst bezahlt"           | in der Kostenliste, wenn man einen Namen aufklappt                                                 | geht      | numbers.spec.ts |
| E-15 | Auswertung mit Abstimmungen      | Karte mit mehreren Versionen: Gewinner, Stimmen, Patt und „von der Spielleitung beendet" stehen da | ungeprüft | -               |
| E-16 | Leitstelle am Spielende                    | „Zu deinen Spielen" führt nach `/app/host`                                                    | geht      | lobby          |
| E-17 | „Neues Spiel anlegen" am Spielende         | führt ins Formular, in der SPA statt über Django                                              | ungeprüft | -              |
| E-18 | „Meine Gruppen“ | nur in einem Spiel mit Pendlertypen und nur mit eigenem Platz, also nicht an der Leitstelle; pro Gruppe Zuhause und Ziel, Pendlertyp, wie oft womit, Zeit, Strecke, Tempo, selbst bezahlt, CO₂, Umstiege, ein Tag hin und zurück im Schnitt über die Runden; zurück auf „pro Person“ stehen die drei Listen wieder da | geht | `test_rounds`, `tests/lib/game/groups.test.ts` |

## H — die leitstelle (host)

| ID   | Fall                                                     | Erwartet                                                                                                         | Status    | E2E                |
| ---- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------- | ------------------ |
| H-01 | Host spielt nicht mit                                    | eigene Zeile bleibt stumm, Runde wartet nicht auf sie                                                            | geht      | -                  |
| H-02 | Host legt einen Platz an                                 | wird an der Leitstelle gespielt                                                                                   | geht      | leitstelle         |
| H-03 | Host spielt die Plätze reihum                            | einer nach dem anderen                                                                                           | geht      | leitstelle         |
| H-04 | Wechsel zwischen zwei Plätzen                            | verdeckter Zwischenschritt, Beamer zeigt nichts                                                                  | geht      | leitstelle         |
| H-05 | Host übernimmt den Platz eines Schülers                  | dessen Gerät fliegt raus (`taken_over`)                                                                          | geht      | -                  |
| H-06 | Host gibt den Platz per Code zurück                      | Handy scannt/tippt, Platz ist zurück                                                                             | geht      | -                  |
| H-07 | Code nach 5 Minuten                                      | abgelaufen                                                                                                       | ungeprüft | -                  |
| H-08 | neuer Code für denselben Platz                           | macht den alten ungültig                                                                                         | geht      | -                  |
| H-09 | ganzes Spiel auf einem Rechner                           | läuft durch, ohne ein einziges Handy                                                                             | geht      | leitstelle         |
| H-10 | Pause-Knopf                                              | beim Host, wirkt überall                                                                                         | geht      | -                  |
| H-11 | Host beendet aus der Lobby                               | geht auch bei einem Spiel ohne Karte, Grund `host`                                                               | geht      | -                  |
| H-12 | Spiel anlegen: CO₂-Budget und Menschen pro Gruppe      | vorgeschlagen werden 106 Menschen pro Gruppe und 2,4 kg pro Person und Runde („normal“), zusammen 97.920 kg für 6 Runden — nicht 500 und 1000 | geht      | `e2e/host.spec.ts` |
| H-13 | Spiel anlegen mit weniger Plätzen                        | Vorschlag folgt der Klassengröße sofort: 8 Plätze → 212 Menschen pro Gruppe, das Budget bleibt; 3 Runden → 48.960 kg | geht      | `e2e/host.spec.ts` |
| H-14 | Vorschlag überschreiben                                  | eigene Zahl bleibt stehen, auch wenn sich die Klassengröße danach ändert; „Vorschlag übernehmen" holt sie zurück | geht      | `e2e/host.spec.ts` |
| H-15 | Karte ohne Abstimmung auswählen                          | die Auswahl sagt, dass es auf dieser Karte nichts abzustimmen gibt                                               | geht      | -                  |
| H-16 | `/game/create/` aufrufen                                 | leitet in die SPA weiter; ohne Login erst zum Login                                                              | geht      | `e2e/host.spec.ts` |
| H-17 | Karte mit ungemessener Pendlerzahl auswählen             | Warnung: Menschen pro Gruppe ist nur ein Vorgabewert, und mit ihm das CO₂-Budget; die mitgelieferte Karte hat keine | geht      | `e2e/host.spec.ts` |
| H-18 | „Weitere Einstellungen"                                  | zu, bis man es aufmacht; lehnt der Server ein Feld darin ab, geht es von selbst auf                              | geht      | -                  |
| H-19 | Platz übernehmen, nachdem die Leitstelle „Weiter für alle hier" gedrückt hat | der Knopf kommt wieder (der Platz hat nichts gelesen); ein Druck, und es geht weiter                             | geht      | zwischen-den-runden    |
| H-20 | Spiel anlegen: CO₂ pro Person und Runde                  | Auswahl 0,6 bis 6,0 kg in Schritten von 0,2, „normal“ bei 2,4; 2,0 kg bei 3 Runden → 40.800 kg; das Spiel speichert die Kilo; der Server lehnt alles außerhalb der Auswahl auf Deutsch ab | geht      | `e2e/host.spec.ts`, `test_join` |
| H-21 | Spiel anlegen: Pendlertypen | Schalter „verteilen“ unter „Gruppen pro Person“, aus als Vorgabe; an: die sieben Standardtypen, alle angehakt, eigene dazu (Enter fügt hinzu, schickt das Formular nicht ab), eigene wieder entfernen; alle abgehakt: „Wähle mindestens einen Pendlertyp.“ unter der Liste, kein Spiel; das Spiel bekommt Kopien, ein eigener taucht im nächsten Formular nicht auf, ein später geänderter Standardtyp ändert kein Spiel | geht | `test_personas`, `tests/lib/game/personas.test.ts` |
| H-22 | Spiel anlegen: Wohnorte | Schalter „ausbalanciert“ unter den Pendlertypen, aus als Vorgabe; das Spiel speichert ihn; in der Lobby lässt er sich nicht mehr ändern | geht | `test_deal` |
| H-23 | Spiel anlegen: mehr Gruppen pro Person als Plätze | 2 Plätze mit 3 Gruppen pro Person werden angelegt (201); die Grenze „Gruppen pro Person höchstens so viele wie Plätze“ gibt es nicht mehr, sie stammte aus der Zeit, in der jede Gruppe allein spielte | geht | `test_join` |

## C — chat

| ID   | Fall                            | Erwartet                                                                        | Status | E2E            |
| ---- | ------------------------------- | ------------------------------------------------------------------------------- | ------ | -------------- |
| C-01 | Nachricht schicken              | kommt bei allen an                                                              | geht   | `chat.spec.ts` |
| C-02 | neu verbinden                   | Verlauf ist da (100 Nachrichten, 2 h)                                           | geht   | `chat.spec.ts` |
| C-03 | zu schnell tippen               | Rate limit, verständliche Meldung                                               | geht   | `chat.spec.ts` |
| C-04 | Chat ist aus                    | kein Chat sichtbar                                                              | geht   | `chat.spec.ts` |
| C-05 | Chat auf dem neuen Spielscreen  | erreichbar wie auf dem alten                                                    | geht   | `chat.spec.ts` |
| C-06 | ungelesene Nachrichten          | Zähler am Knopf, solange der Chat zu ist                                        | geht   | `chat.spec.ts` |
| C-07 | Chat an- oder ausschalten       | im Formular unter „Weitere Einstellungen"; in der Lobby nur über die API        | geht   | `chat.spec.ts` |
| C-08 | Platz stummschalten             | fragt vorher, Kennzeichen am Platz, Nachricht wird abgelehnt                    | geht   | `mute.spec.ts` |
| C-09 | stummgeschaltet schreiben       | deutsche Begründung, Zeile kommt bei niemandem an                               | geht   | `mute.spec.ts` |
| C-10 | Stummschaltung aufheben         | ohne Rückfrage, ohne Neuverbinden wirksam                                       | geht   | `mute.spec.ts` |
| C-11 | eigene Host-Zeile stummschalten | gibt es nicht — der Host steht nicht in der Platzliste, die API sagt 409 `host` | geht   | -              |
| C-12 | Chat aus, Socket von Hand       | Server weist ab (4403), offener Socket bekommt „Chat ausgeschaltet"             | geht   | -              |

> Seit dem 28.09.26 ist der Chat wieder da, neu gegen `ChatConsumer` gebaut und auf jedem
> Spielscreen erreichbar (`GameFrame` hängt ihn einmal ein). Vom 18.09.26 bis dahin gab es
> **gar keinen Chat**: er hing am alten Screen, der an dem Tag gelöscht wurde.
>
> C-04 hängt am REST-Snapshot: `chat_enabled` kommt nur dort an, `game.state` trägt es nicht und
> kein Event meldet eine Änderung. Ein laufender Client zeigt den Chat also bis zum nächsten
> Neuladen weiter an — schreiben kann er aber nicht mehr.
>
> C-12: bis zum 30.09.26 hat **nur der Client** `chat_enabled` gelesen. `ChatConsumer` hat nie
> nachgesehen, ein von Hand gebauter Socket konnte in einem Spiel mit ausgeschaltetem Chat
> weiterschreiben. Jetzt weist der Server beim Verbinden ab und prüft jede Nachricht noch einmal,
> wie beim Stummschalten. Geprüft in `game/tests/test_socket.py`, nicht im Browser — der Client
> öffnet in diesem Fall ja gar keinen Socket.
>
> C-08 bis C-11 sind neu seit dem 28.09.26. `Player.is_muted` und `MuteUnmutePlayerView` gab es
> vorher schon, beides wirkungslos: die View hing an keiner URL und **kein Consumer hat das Feld
> gelesen**. Geprüft werden muss das mit zwei echten Geräten — ein Platz an der Leitstelle teilt
> Cookie und Socket mit dem Host, und der Host ist nie stummgeschaltet.

## K — karte und editor

| ID   | Fall                                                       | Erwartet                                                                                                                                                                                                                                  | Status    | E2E        |
| ---- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---------- |
| K-01 | Karte im Spiel                                             | Knoten, Kanten, Linien, Legende                                                                                                                                                                                                           | geht      | -          |
| K-08 | Hintergrundbild im Spiel                                   | liegt unter dem Graphen, richtig platziert                                                                                                                                                                                                | geht      | -          |
| K-02 | Karte auf dem Handy                                        | passt aufs Bild, Auswahl erreichbar                                                                                                                                                                                                       | geht      | -          |
| K-03 | Kante anklicken                                            | reagiert                                                                                                                                                                                                                                  | geht      | -          |
| K-04 | Editor lädt                                                | Graph erscheint, auf Deutsch, mit Legende                                                                                                                                                                                                 | geht      | -          |
| K-05 | Editor: Knoten und Kanten bearbeiten                       | speichert                                                                                                                                                                                                                                 | geht      | -          |
| K-06 | Editor: Version anlegen                                    | taucht in der Abstimmung auf                                                                                                                                                                                                              | ungeprüft | -          |
| K-17 | Version anlegen lässt die anderen Versionen ganz           | eine Version über eine Straße zu zeichnen nimmt keiner anderen Version ihre Buslinie oder ihre Bahn: jede Version behält 136 Kanten und alle zehn Linien durchgehend                                                                      | geht      | -          |
| K-18 | Kombiversion                                               | trägt beide Änderungen, alle sechs Bahnlinien und keine Straße doppelt                                                                                                                                                                    | geht      | -          |
| K-19 | Linie in einer Version geändert                            | die Version fährt über die geänderte Straße, die Ausgangsversion über die alte                                                                                                                                                            | geht      | -          |
| K-20 | Export einer Version, deren Straße fehlt                   | lässt das Teilstück weg **und sagt welche Linie und welche Kante** — vorher still                                                                                                                                                         | geht      | -          |
| K-07 | Karte importieren / exportieren                            | JSON rein und raus                                                                                                                                                                                                                        | geht      | -          |
| K-21 | Ganze Karte exportieren                                    | `/export/` schreibt alle Versionen, die Abstimmung zwischen ihnen, beide Abstimmungstexte und zu jedem Knoten, jeder Kante und jeder Linie, in welche Version sie gehört                                                                  | geht      | map-export |
| K-22 | Ganze Karte importieren                                    | dieselbe Datei ergibt dieselbe Karte mit allen Versionen: gemessen an der geseedeten Karte, 5 Versionen, je 136 Kanten, alle zehn Linien, jede `compatible_versions`-Verbindung                                                           | geht      | -          |
| K-23 | Linie, die je Version anders fährt                         | die Datei schreibt eine Route je Strecke statt eine je Version; nach dem Import fährt die eine Version über die Busspur-Kopie, die andere über die alte Straße                                                                            | geht      | -          |
| K-24 | Alte, flache Kartendatei                                   | eine Datei ohne `versions`-Block importiert unverändert in genau eine Basisversion — jede Datei in `map_examples/` ist eine                                                                                                               | geht      | -          |
| K-25 | Kaputte Kartendatei von Hand                               | ein Index, der ins Leere zeigt, keine oder zwei Basisversionen, eine namenlose Version: der Upload sagt was falsch ist, statt eine Karte mit einem Loch anzulegen                                                                         | geht      | -          |
| K-26 | Version, in der eine Linie keine Kante erreicht            | steht als leere Strecke in der Datei, statt zu fehlen — auf der Kopie der Box-Karte liest Bus `100` dort 0 Kanten, `101` 6 (Vorbereitung für die Reparatur)                                                                               | geht      | -          |
| K-27 | Die Karte der Box liegt als Datei vor                      | `map_examples/Berlin_Mitte-West.json` ist die gespielte Karte mit allen acht Versionen, den drei Eingriffen und den zwölf Abstimmungspaaren — vorher lag sie nur im pg-Dump                                                               | geht      | -          |
| K-28 | Weg ohne Straße darunter                                   | `"type": "path"`: die zwölf Fuß- und Radverbindungen (drei Wohnorte zur S-Bahn Bellevue, Justizministerium zum Checkpoint Charlie, seit dem 02.10.26 acht durch den Tiergarten und um den Potsdamer Platz) kommen ohne `StreetEdge` durch Export und Import — vorher erfand der Import 50 km/h und eine Spur  | geht      | -          |
| K-29 | Busspuren in beide Richtungen                              | jede der 15 Achsen von 100 und 101 hat die Busspur hin **und** zurück; alle vier Linienrichtungen fahren in der Busspuren-Version vollständig darauf                                                                                      | geht      | -          |
| K-30 | Bahn in jeder Kombiversion                                 | alle sechs Bahnlinien sind in allen acht Versionen, 67,27 Linien-km überall — vorher 0 in den vier erzeugten Kombinationen                                                                                                                | geht      | -          |
| K-31 | Keine Straße doppelt in einer Kombiversion                 | eine Kombiversion mit Busspuren trägt die Busspur-Kopie **statt** der alten Straße; Autospur-km fallen dort von 113,2 auf 82,5                                                                                                            | geht      | -          |
| K-32 | Abstimmungstext einer Kombiversion                         | ist Deutsch und eine Frage wie bei den handgezeichneten Versionen — vorher „Apply changes: ...“ auf dem Wahlzettel                                                                                                                        | geht      | -          |
| K-33 | Zu Fuß zur Arbeit auf der ausgelieferten Karte             | 14 von 36 Wegen von einem Wohnort zur Arbeit sind hin und zurück höchstens 5 km lang, in jeder Version; der kürzeste ist 2,75 km, von Wohnort 2 durch den Tiergarten zur Arbeit Brandenburger Tor — vorher 3, in den Umgehungsstraßen-Versionen 9       | geht      | `test_example_map` |
| K-09 | Export → Import derselben Karte                            | Bild, Maße und Platzierung kommen mit                                                                                                                                                                                                     | ungeprüft | -          |
| K-13 | Export → Import: Linien                                    | Plätze, Takt und Tempo jeder Linie kommen mit                                                                                                                                                                                             | geht      | -          |
| K-14 | Export → Import: Kartenwerte                               | Platzzahl und die drei Geschwindigkeiten kommen mit; eine alte Datei ohne die Schlüssel behält die Vorgabewerte                                                                                                                           | geht      | -          |
| K-15 | Linien der ausgelieferten Karte                            | alle zwölf durchgehend **in jeder Version, zu der sie gehören**, Hin- und Rückrichtung halten an denselben Bahnhöfen, Bus 85 / Bahn 1000 Plätze, ein Tempo je Linienpaar                                                                  | geht      | -          |
| K-16 | Karte neu importieren                                      | dieselbe Datei ergibt dieselbe Karte: 8 Versionen, 55 Knoten, 186 Kanten, 6 Bus- und 6 Zuglinien, 13x10, Pendlerzahl und Budget                                                                                                           | geht      | -          |
| K-12 | Export → Import: Pendlerzahl und CO₂-Budget der Karte      | kommen mit; eine alte Datei ohne die Schlüssel behält die Vorgabewerte                                                                                                                                                                    | geht      | -          |
| K-10 | Hintergrundbild neben den Graphen geschoben                | bleibt ganz sichtbar, wird nicht abgeschnitten                                                                                                                                                                                            | geht      | -          |
| K-11 | Kartendetail                                               | Hintergrundbild liegt unter dem Graphen                                                                                                                                                                                                   | geht      | -          |
| K-33 | Karten-Upload auf Deutsch                                  | Beschriftungen, Hilfetexte und Absagen sind deutsch; die JSON-Schlüssel bleiben englisch, weil sie die Feldnamen der Karte sind                                                                                                           | geht      | -          |
| K-34 | Kartenschirme auf Deutsch                                  | Detailseite und Editor sagen nichts mehr auf Englisch — kein „All maps", kein englischer `confirm()`, keine Überschrift „Modify Edge"                                                                                                    | geht      | -          |
| K-35 | Alle Karten                                                | `/app/maps` ist eine Liste mit Größe, Plätzen, Pendlern und ob es etwas abzustimmen gibt; „Alle Karten“ und das Löschen einer Karte landen dort statt auf dem Beitreten-Screen                                                           | geht      | -          |
| K-36 | Alte Kartenseiten                                          | `/map/list/` und `/map/<id>/` leiten in die SPA um; die Django-Seiten sind weg                                                                                                                                                           | geht      | -          |
| K-37 | Kartenbereich in den Farben der Seite                      | Liste, Detail und Editor nur in Blau, Bernstein und Tinte, hell und dunkel; Straße durchgezogen, Bahn gestrichelt, Weg gepunktet                                                                                                         | geht      | -          |
| K-38 | Editor auf dem Handy                                       | sagt, dass der Bildschirm zu klein ist; „Trotzdem anzeigen“ zeigt ihn doch                                                                                                                                                               | geht      | -          |
| K-39 | Karte hochladen in der SPA                                 | `/app/maps/upload` legt eine Karte aus der Datei an und öffnet sie; `/map/upload/` leitet dorthin um und nimmt selbst keine Datei mehr an                                                                                                | geht      | `map-upload.spec.ts`|
| K-40 | Kaputte Kartendatei in der SPA                             | alles, was in der Datei falsch ist, steht auf einmal und auf Deutsch unter dem Formular; ein vergebener Name steht am Namensfeld                                                                                                         | geht      | `map-upload.spec.ts`|
| K-41 | Aufbau der Datei                                           | hinter einem Schalter statt über dem Formular; nennt jeden Schlüssel, den der Import liest                                                                                                                                               | geht      | `map-upload.spec.ts`|
| K-42 | Karte löschen                                              | fragt in einem eigenen Dialog statt im Browser-Fenster, sagt, dass eine Karte, auf der schon gespielt wurde, bleibt; Abbrechen behält die Karte                                                                                                                        | geht      | `map-upload.spec.ts`|
| K-43 | Editor: Straße unter einer Kante anlegen                   | erscheint sofort, unter beiden Richtungen; der Knopf ist gesperrt, bis sie zu sehen ist — vorher gespeichert und bis zu einer Stunde nicht gezeigt, und ein zweiter Klick legte eine zweite Straße an                                   | geht      | `editor.spec.ts`|
| K-44 | Editor: Gegenrichtung anlegen                              | wird genau einmal angelegt; der Knopf bleibt gesperrt, bis die neue Richtung gezeichnet ist — vorher war er nach 20 ms wieder klickbar, über einer Anzeige, die noch „Einbahn“ sagte                                                    | geht      | `editor.spec.ts`|
| K-45 | Editor: in der Basis gezeichnet                            | Knoten, Kante, Straße oder Gleis sind in allen acht Versionen; eine Version mit eigener Kopie der Kante (Busspuren, Umgehungsstraße) behält ihre Kopie, und eine Version ohne einen der Knoten bekommt die Kante nicht                    | geht      | `editor.spec.ts`|
| K-46 | Editor: in einer Änderung gezeichnet                       | landet in der Änderung und in jeder Kombiversion, die sie enthält — nicht in der Basis, nicht in den anderen Änderungen                                                                                                                 | geht      | -          |
| K-47 | Editor: dieselbe Kante zweimal                             | wird abgelehnt: „Diese Kante gibt es in dieser Version schon.“ Ebenso eine zweite Straße oder ein zweites Gleis unter einer Kante. Beide Richtungen über einer schon vorhandenen ziehen legt nur die fehlende an                           | geht      | -          |
| K-48 | Editor: Zeile ohne Version                                 | wird abgelehnt, auf Deutsch: „Ohne Version wäre das auf keiner Karte zu sehen.“                                                                                                                                                        | geht      | -          |
| K-49 | Editor: zwei Kanten schnell hintereinander                 | solange die erste gespeichert wird, nimmt die Leinwand keine zweite an                                                                                                                                                                   | geht      | -          |
| K-50 | Editor: Version löschen                                    | fragt in einem Dialog, was mitgeht: was nur in dieser Version steht (Knoten, Kanten, Straßen, Gleise, Linien), aus welcher Abstimmung sie fällt, welche Kombiversionen ihre Änderung behalten; danach ist genau das weg und keine Zeile steht in keiner Version       | geht      | `version-loeschen.spec.ts`     |
| K-51 | Editor: Grundversion löschen                               | gibt es keinen Knopf dafür; über die API oder im Admin abgelehnt: „Die Grundversion lässt sich nicht löschen …“       | geht      | `version-loeschen.spec.ts`     |
| K-52 | Editor: Version löschen, während ein Spiel läuft           | abgelehnt, solange auf der Karte ein Spiel läuft, auch pausiert; der Dialog nennt das Spiel und bietet nur „Schließen“       | geht      | `version-loeschen.spec.ts`     |
| K-53 | Editor: Version löschen, auf der gespielt wurde            | abgelehnt, wenn ein Spiel auf ihr gespielt hat, sie zur Wahl stand, für sie gestimmt wurde oder über ihre Straßen gefahren ist — sonst gingen Wege und Stimmen mit; der Satz nennt die Spiele und den Ausweg „Verträglich mit“       | geht      | - |
| K-54 | Admin: Version löschen                                     | dieselbe Aufräumregel wie im Editor, einzeln und über „ausgewählte löschen“; die Bestätigungsseite nennt, was mitgeht, eine Ablehnung steht dort als geschützt und löscht nichts       | geht      | - |
| K-55 | Wahlzettel fragt nach der einen Änderung | jede der 24 Optionen der ausgelieferten Karte stellt die Frage der Änderung, die der Schritt macht — hinzu ihre Frage, zurück ihre Rückfrage; von „Buslinie + Umgehungsstraßen“ zurück auf „Buslinie“ fragt nach dem Schließen der Umgehungsstraßen, nicht nach dem Bau der 147       | geht | - |
| K-56 | Bild auf dem Wahlzettel | entfällt: der Wahlzettel zeigt kein Bild mehr, sondern die Änderung selbst auf der Karte (Z-29); der Server schickt das Bild der Änderung weiter mit, gelesen wird es nicht. Die Grundversion fragt nie mit „Die Karte soll ...“       | geht | - |
| K-57 | Editor: Version ansehen | „Ansehen“ unter „Verwalten“ legt die Version auf die Karte und zeichnet, was sie gegenüber ihrer Ausgangsversion ändert, daneben in Worten: Busspuren = 15 Straßen, beide Richtungen, „eine Autospur wird Busspur“, keine Linie; Buslinie = Bus 147 hin und zurück; Umgehungsstraßen = Bundestag – Wohnort 2 neu und der Weg Botschaftsviertel – Philharmonie wird Straße | geht | `versionsvergleich.spec.ts` |
| K-58 | Editor: mit einer anderen Version vergleichen | „Verglichen mit“ nimmt jede Version; Grundversion gegen Busspuren zeigt die 30 Busspuren hohl, „die Busspur wird wieder Autospur“; eine Kombiversion gegen eine ihrer Änderungen ist genau die andere | geht | `versionsvergleich.spec.ts`, vitest |
| K-59 | Kartendatei prüfen | `./manage.py check_map datei.json` sagt zur ausgelieferten Karte „in Ordnung“; eine kaputte Datei bekommt jedes Problem mit seiner Regel genannt — eine Linie gegen ihre Richtung, zwei Kanten zwischen denselben Knoten, ein Wohnort ohne Weg zur Arbeit und zurück — und der Befehl endet mit Fehler      | geht | `test_checks` |
| K-60 | Karte kalibrieren | `./manage.py calibrate_map datei.json --speed 19` auf der ausgelieferten Karte (Postgres): 6.800 Pendler, alle im Auto 19,4 km/h; Tabelle pro Person 4,17 / 3,16 / 2,41 / 1,96 / 1,53 kg, „normal, 2,4 kg, reicht hier, wenn 49 % der Gruppen Auto fahren“; `--commuters 6800` misst dieselbe Tabelle ohne Suche; eine Karte, die `check_map` nicht besteht, wird nicht gemessen      | geht | `test_calibration` |
| K-61 | Tram in der Kartendatei | `"type": "tram"` kommt als Straße mit Gleis darin an, `tram_track` sagt `lane` (Vorgabe) oder `own`; eine Bahnlinie sagt `"kind": "tram"` und bekommt ohne eigene Zahlen 248 Plätze und 30 km/h; der Export schreibt alles so wieder hinaus, jede Bahnlinie mit ihrer Art; `tram_track` an einer anderen Art Kante, ein unbekannter Wert und eine unbekannte Art werden auf Deutsch abgelehnt      | geht | `test_portability` |
| K-62 | Tram im Stau | auf Gleis in der Autospur steht die Tram mit den Autos in der Schlange und die Autos hinter ihr warten; auf eigenem Gleis fährt sie frei; „eigenes Gleis“ nimmt eine Spur, auf einer einspurigen Straße die letzte, und ein Auto darüber wird beim Abschicken abgelehnt; Gleis neben oder unter der Straße hält nichts auf      | geht | `test_linkqueue`, `test_rounds` |
| K-63 | Editor: wo das Gleis liegt | an einer Kante mit Straße und Gleis steht „Gleis: daneben oder darunter / in der Autospur / eigenes Gleis (eine Spur)“ und geht für beide Richtungen mit „Speichern“, das Gleis-Abzeichen sagt dann „Bahn, in der Autospur“; ohne Gleis lehnt der Server es ab; wird das Gleis gelöscht, geht die Angabe mit      | geht | `test_graph` |
| K-64 | Editor: Tramlinie | „+ Bahnlinie“ fragt nach der Art; „Tram“ startet mit 248 Plätzen und 30 km/h, „S- oder U-Bahn“ mit 1.000 und 40; die Liste zeigt „Tram“      | geht | - |
| K-65 | Editor: Version „eigenes Gleis“ | in einer Änderung das Gleis auf „eigenes Gleis“ gestellt: die Version hat eine Kopie der Straße, die Tram fährt dort darüber, die Basis behält das Gleis in der Autospur; „Ansehen“ unter „Verwalten“ sagt „eine Autospur wird eigenes Tramgleis“; eine geänderte Tramlinie bleibt eine Tram      | geht | `test_versions`, `version-diff.test.ts` |
| K-66 | Kartendatei prüfen: Tram | `check_map` meldet eine S- oder U-Bahn auf Gleis in der Autospur und eine Tramstraße, die in einer Version kein Gleis hat      | geht | `test_checks` |
| K-67 | Straßenlänge in der Kartendatei | `circuity` an einer Kante kommt an und geht mit dem Export wieder hinaus, an jeder Kante, 1 an einer geraden; eine Datei ohne kommt mit geraden Kanten an; ein Wort statt einer Zahl wird auf Deutsch abgelehnt      | geht | `test_portability` |
| K-68 | Straßenlänge im Spiel | eine Kante mit `circuity` 1,5 ist für die Router (`distance_m`) und für die Simulation anderthalbmal so lang wie die Luftlinie, und ein Auto braucht entsprechend länger; eine Fahrt mit Bus und Bahn auch — über ein Gleis, dreimal so lang wie seine Luftlinie, nimmt der Router den Bus, wenn der dadurch schneller ist; die Grenzen für Fuß und Rad bleiben die Luftlinie      | geht | `test_graph`, `test_simulation`, `pt-routing.test.ts` |
| K-69 | Editor: Straßenlänge | „Länge“ an einer Kante ist die Straße; einen Knoten verschieben streckt die Straße mit; „+ Gegenrichtung anlegen“ und eine Änderung an der Straße in einer Version behalten die Länge; weniger als 1 lehnt der Server ab      | geht | `test_graph`, `test_versions`, `map-editor.test.ts` |
| K-70 | Kartendatei prüfen: Straßenlänge | `check_map` meldet eine Kante mit `circuity` unter 1 — kürzer als die Luftlinie      | geht | `test_checks` |
| K-71 | Karte kalibrieren: Paare ziehen | `calibrate_map datei.json --speed 19 --per-home 7` auf einer Karte mit mehr Arbeitsorten als 7: „je Wohnort 7 gezogen“, jeder Wohnort spielt jede Runde, jeder Arbeitsort gleich oft (± 1), kein Wohnort einen doppelt, jeder Seed neu gezogen; ohne `--per-home` „je Wohnort 4 gezogen“, auf der ausgelieferten Karte (sechs Arbeitsorte) jedes Paar wie bisher; `--per-home 0` lehnt der Befehl ab      | geht | `test_calibration` |
| K-72 | Karte kalibrieren: schneller | `calibrate_map` routet nur die Paare, die die Seeds ziehen, im Auto und mit Bus und Bahn („1519 Wege, 616 davon gespielt“ auf der gebauten Box), und spielt auf Postgres die Runden eines Schritts nebeneinander („6 Seeds in 6 Prozessen“, `--workers`); die Tabelle ist Byte für Byte dieselbe wie eine nach der anderen (Callenberg, Box); unter sqlite „in einem Prozess“; `--workers 0` lehnt der Befehl ab      | geht | `test_calibration`, `trip-search.test.ts` |
| K-73 | Karte kalibrieren: Anteil am Fahrplan | `calibrate_map` auf der ausgelieferten Karte: „Anteil am Fahrplan: 0,22“ — bei 50 % Auto stoßen die Mitfahrenden, so voll wie Bus und Bahn in Deutschland, 2.725 kg aus, der Grundfahrplan 12.606 kg —, die Tabelle mit dem Anteil (100 % 3,53 kg, 0 % 0,72 kg), normal bei 67 % Auto; nie mehr als 1; ohne Mitfahrende „nicht messbar“ und die Datei behält ihren; `--out` schreibt `timetable_factor`, Export und Import nehmen ihn mit, ein Wert, der kein Anteil ist, bleibt draußen      | geht | `test_calibration`, `test_portability`, `test_example_map` |
| K-74 | Karte löschen, auf der ein Spiel war | abgelehnt, solange ein Spiel auf ihr läuft, und wenn eins auf ihr war, auch eins, das nie begonnen hat — sonst gingen die gefahrenen Wege und die Abstimmungen mit; die Seite zeigt den Satz des Servers mit den Spielen; ohne das Spiel geht die Karte; im Admin dasselbe, einzeln und über „ausgewählte löschen“ | geht | `map-upload.spec.ts`, `test_versions` |
| K-75 | Admin: Kombiversionen erzeugen | die Aktion „Generate combination versions“ baut dieselben Kombiversionen wie „Kombinationen erzeugen“ im Editor: beide Änderungen, die Bahnlinien mit ihren Ketten, keine Straße doppelt, die Frage auf Deutsch, die Abstimmung wie dort | geht | `test_versions` |
| K-76 | Karte bauen | `build_map --bbox 53.06,8.775,53.095,8.84 --name "Bremen Mitte"` aus dem Cache, ohne Netz: schreibt die Datei und den Bericht (Straßen, Wohn- und Arbeitsorte, Anbindung, Karte, Bus und Bahn), `check_map` in Ordnung; dieselbe Datei unter jedem Hash-Seed; ein Ort und `--bbox` zugleich: abgelehnt; Overpass nicht erreichbar: ein Satz, kein Zerteilen der Box; zu groß für Overpass: in Vierteln | geht | `mapbuild/tests` |
| K-77 | Kreisverkehr: der Ring hat Vorfahrt | eine gebaute Karte trägt an den Kanten eines Rings OSMs `junction` (`roundabout` oder `circular`, auf dem Ausschnitt von Bremen der Rembertiring), Import, Export und eine Version, die eine Ringstraße ändert, tragen es mit; in der Runde wartet, wer von außen auf den Ring will, solange auf dem Ring ein Auto durch ist, das auf dieselbe Kante will, und die Sperre gegen das Verklemmen zählt das Warten nicht. Ein kleiner Platz mit Ring, 800 Autos in wenigen Minuten: ohne Vorfahrt steht er stundenlang, mit ihr ist jeder in einer Viertelstunde durch | geht | `test_linkqueue`, `test_build`, `test_portability`, `test_versions` |
| K-78 | Editor: Namen für Gezeichnetes | im Graph-Modus heißt ein neuer Knoten nach der Karte, ab 1 gezählt („<Karte> Knoten 1“, dann „<Karte> Knoten 2“), eine neue Kante „<Karte> Kante 1“, in beiden Richtungen; im Knoten- und im Kantenfeld ist „Speichern“ aus, solange der Name leer ist oder auf „Knoten/Kante/Node/Edge“ und eine Zahl endet, darunter „Gib einen besseren Namen.“; mit einem echten Namen speichert es | geht | `names.test`, `editor.spec` |

## S — sonstiges

| ID   | Fall                            | Erwartet                                                                                                   | Status    | E2E                     |
| ---- | ------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------- | ----------------------- |
| S-01 | Impressum, Datenschutz, Cookies | von jeder Seite außerhalb des Spiels erreichbar, in der Fußzeile beider Hälften                            | geht      | `chrome.spec.ts`        |
| S-02 | heller und dunkler Modus        | auf beiden Hälften, ein Schalter                                                                           | ungeprüft | -                       |
| S-03 | 390px                           | kein horizontales Scrollen, nirgends                                                                       | geht      | -                       |
| S-04 | Spielernamen                    | tauchen beim Beitreten und beim Anlegen eines Platzes in keinem Log auf                                    | geht      | -                       |
| S-05 | Anonymisierung                  | nach Spielende „Spieler N", Host wird „Host"                                                               | ungeprüft | -                       |
| S-07 | Spiel auf der Hostseite löschen | fragt vorher und sagt, was mitgeht; laufendes Spiel wird abgelehnt                                         | geht      | `e2e/host-page.spec.ts` |
| S-08 | Kopf- und Fußzeile unter `/app` | dieselben Punkte wie auf den Django-Seiten, Karten nur für Staff, Abmelden; nicht im Spiel, nicht im Editor       | geht      | `chrome.spec.ts`        |
| S-09 | Passwort raten                  | nach 10 Fehlversuchen 429 mit deutscher Seite, 15 Minuten                                                  | geht      | -                       |
| S-10 | Platz-Code raten                | nach 20 Fehlgriffen 429; gültige Codes zählen nie mit                                                      | geht      | -                       |
| S-11 | viele Konten anlegen            | nach 10 angelegten Konten pro Stunde 429; abgelehnte Formulare zählen nicht                                | geht      | -                       |
| S-12 | `robots.txt` und `llms.txt`     | beide unter `/`, nur über nginx — im Dev-Stack gibt es sie nicht                                           | ungeprüft | -                       |
| S-13 | Anmelden                        | landet direkt auf `/app/host`, der eigenen Seite mit Spielen und Konto — ein Sprung, nicht zwei            | geht      | `e2e/host.spec.ts`      |
| S-14 | Kontodaten ändern               | Anzeigename, Benutzername und E-Mail lassen sich speichern; ein vergebener Name wird auf Deutsch abgelehnt | geht      | `e2e/host-page.spec.ts` |
| S-15 | Konto löschen erreichbar        | ein Klick von der Hostseite auf die Bestätigungsseite                                                      | geht      | `e2e/host-page.spec.ts` |
| S-16 | `/game/<id>/share/`             | leitet in die Lobby, die ID und QR-Code ohnehin zeigt                                                      | geht      | -                       |
| S-17 | Wortwahl                        | eine Gruppe heißt überall Gruppe, der Hostrechner ist die Leitstelle, der weite Maßstab „alle Pendler"    | geht      | `numbers.spec.ts`       |
| S-18 | keine Schulwörter               | kein „Klasse", „Unterricht", „Lehrer", „Pult", „Schule" oder „Figur" — im Wörterbuch außer im Beispiel im Namensfeld, in den Django-Seiten ohne Ausnahme             | geht      | -                       |
| S-19 | Kopfzeile der Django-Seiten     | Menüs öffnen unter ihrem Knopf, Esc und Klick daneben schließen; Handy-Menü mit Unterlisten; nichts von fremden Servern | geht      | -                       |
| S-20 | Schriftzug                      | das Zeichen ist das C von CO₂mmute, der Rest steht in derselben Schrift wie die Seite; auf beiden Hälften gleich groß, hell wie dunkel lesbar       | geht      | -                       |
| S-21 | Quellcode                       | Link aufs Repository in der Fußzeile beider Hälften                                                        | geht      | `chrome.spec.ts`        |
| S-22 | Breite von Kopf- und Fußzeile   | auf beiden Hälften gleich breit und gleich eingerückt; ein Screen unter `/app` ist nie breiter             | geht      | -                       |
| S-23 | Menü ohne Konto                 | wer mitspielt, sieht keine Karten und kein Abmelden, nur Anmelden                                                  | geht      | `chrome.spec.ts`        |
| S-24 | falsches Passwort               | Meldung auf Deutsch über dem Formular, der Name bleibt stehen; ein unbekannter Name liest sich genauso       | geht      | -                       |
| S-25 | Konto mit schwachem Passwort    | jede verletzte Regel als eigener deutscher Satz; die Regeln stehen schon vor dem Tippen unter dem Feld       | geht      | `credentials.spec.ts`   |
| S-26 | Passwort vergessen              | Formular statt Serverfehler, deutsche Mail mit Link, der Link setzt ein neues Passwort; eine unbekannte Adresse sieht gleich aus       | geht | `credentials.spec.ts` |
| S-27 | Passwort ändern                 | erst das bisherige, dann zweimal das neue; man bleibt angemeldet                                            | geht      | -                       |
| S-28 | „Angemeldet bleiben“            | ohne Haken endet die Anmeldung mit dem Browser, mit Haken nach 14 Tagen                                     | geht      | -                       |
| S-29 | Abmelden                        | eigene Seite im Design, sagt dass die Spiele weiterlaufen                                                  | geht      | -                       |
| S-30 | Django-Seiten im Design         | Anmelden, Konto und Passwort-Seiten so breit, so gesetzt und so gefärbt wie die SPA; hell und dunkel, 390px       | geht | -                       |
| S-31 | Umweg auf der Startseite        | die Linie von Bus & Bahn verlässt das Bündel, überbrückt Rad- und Fußlinie, hält an einer eigenen Station zum Hintergrund und fädelt wieder ein; die anderen drei Linien laufen ohne Naht durch; hell und dunkel, 390px       | geht | -                       |
| S-32 | `/docs/hintergrund/` ist das Dokument | trägt `docs/de-hintergrund.md` bis vor die Kalibrierung: dieselben Kapitel und Abschnitte in derselben Reihenfolge, dieselben Zahlen in beide Richtungen, dieselben Abbildungen (unter `/docs/` seit dem 03.10.26)  | geht | -                       |
| S-33 | Haltestellen auf den Docs-Seiten | auf breiten Schirmen läuft die Liste der Kapitel mit, die schon passierten sind gefüllt; auf dem Handy steht sie über dem Text; ohne JavaScript bleiben alle hohl und die Links gehen; Schnellstart und Ablaufdiagramme zeigen ihre Abschnitte als kleinere Halte unter dem Kapitel            | geht | -                       |
| S-34 | Abbildungen                     | Kante, CO₂-Kurve, Runde nach Autoanteil, Maßstab: zwei Farben und Tinte, hell und dunkel lesbar, auf 390px ohne Querscrollen, und als Bild für sich lesbar, wie die Docs sie zeigen       | geht | -                       |
| S-35 | Herkunft                        | Startseite und Hintergrund nennen die Masterarbeit an der Freien Universität Berlin und die Weiterentwicklung an der TU Berlin       | geht | -                       |
| S-36 | „Docs“ in der Kopfzeile          | auf beiden Hälften dasselbe Menü: Schnellstart, Hintergrund, Ablaufdiagramme, nichts auf Englisch; auf dem Handy genauso       | geht | `chrome.spec.ts`        |
| S-37 | Docs auf Deutsch                 | drei Seiten unter `/docs/`, deutsch wie die ganze Seite; die englischen unter `/docs/en/` geben 404, ihr Text steht nur in `docs/`; `/hintergrund/` gibt 404, die Startseite führt zum neuen Ort       | geht | `chrome.spec.ts`        |
| S-38 | Ablaufdiagramme auf der Seite    | zwölf Diagramme in den Farben der Seite, hell und dunkel lesbar; alle hochkant und höchstens 784px breit, ab 1280px in voller Größe neben den Haltestellen, schmaler kleiner — nichts scrollt seitwärts; auf 390px nimmt der Kasten die ganze Breite, über die Linie, und das ganze Diagramm ist zu sehen       | geht | -                       |

> S-09 bis S-11 zählen **Fehlversuche** (Login, Platz-Code) bzw. **Erfolge** (Konten), nie einfach
> Anfragen: eine Klasse hängt hinter _einem_ Schulanschluss, und wer richtige Codes einlöst, würde
> sich sonst selbst aussperren. Die IP-Adresse wird dabei nicht gespeichert, sondern gehasht —
> `legal/dsgvo.html` §2.5 sagt das.
>
> Achtung beim Prüfen von S-09: der Zähler gilt pro Anschluss, also sperrt ein Testlauf auch die
> eigenen e2e-Logins für 15 Minuten aus. Zurücksetzen mit
> `cache.delete(f"throttle:login:{client_key(request)}")`.
>
> S-12 steht auf `ungeprüft`, weil beide Dateien vom nginx-Image kommen: `devops/dev.sh` serviert
> sie nicht, ein Nachweis braucht also `docker compose up -d --build nginx` oder die Box.
