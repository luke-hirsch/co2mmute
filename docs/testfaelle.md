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
| J-01 | Spiel-ID gibt es nicht                       | „Es gibt kein Spiel mit dieser ID.", zurück zur Eingabe | geht      | -   |
| J-02 | Lobby offen, kein Passwort                   | Name rein, Spieler angelegt, Lobby                      | geht      | -   |
| J-03 | Spiel läuft schon                            | 409 `started`, Formular gesperrt                        | geht      | -   |
| J-04 | Spiel ist vorbei                             | 409 `ended`, Formular gesperrt                          | geht      | -   |
| J-05 | Spiel ist voll                               | 409 `full`, Formular gesperrt                           | geht      | -   |
| J-06 | Passwort nötig, richtig                      | kommt rein                                              | geht      | -   |
| J-07 | Passwort nötig, falsch                       | 403, Feld bleibt stehen, Name bleibt stehen             | geht      | -   |
| J-08 | Passwort nötig, keins eingegeben             | wie falsches Passwort                                   | geht      | -   |
| J-09 | kein Name eingegeben                         | Meldung, gar kein Request                               | geht      | -   |
| J-10 | Spiel füllt sich während des Tippens         | erst beim Absenden 409 `full`                           | offen     | -   |
| J-11 | QR-Code scannen                              | landet direkt auf `/app/join/<ID>` (S22)                | geht      | -   |
| J-12 | „Sitzung fortsetzen" mit Platz-Code (1.7)    | Platz übernommen, neue `player_id`                      | geht      | -   |
| J-13 | Code abgelaufen oder schon benutzt           | 404, sagt dass der Code weg ist                         | geht      | -   |
| J-14 | Code, aber der Browser hat schon einen Platz | 409 `seated`                                            | ungeprüft | -   |
| J-15 | Code, aber man ist der Host des Spiels       | 409 `host`                                              | geht      | -   |
| J-16 | zweimal aus demselben Browser beitreten      | kein zweiter Platz                                      | offen     | -   |
| J-17 | alte Beitrittsseite `/join/`                 | 404 — der einzige Eingang ist `/app/join` (S22)         | geht      | `credentials.spec.ts` |
| J-18 | „Los“ auf der Startseite, mit ID             | landet auf `/app/join/<ID>` (S22)                       | geht      | `credentials.spec.ts` |
| J-19 | „Los“ auf der Startseite, ohne ID            | landet auf `/app/join`, das nach der ID fragt (S22)     | geht      | `credentials.spec.ts` |

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
| L-09 | Platz an der Leitstelle (1.6)               | ist als solcher markiert                                                                      | geht   | -              |
| L-10 | Host legt einen Platz an (1.6)             | erscheint bei allen, zählt gegen `max_players`                                                | geht   | -              |
| L-11 | Host entfernt einen host-gesteuerten Platz | verschwindet, Runde wartet nicht mehr                                                         | geht   | -              |
| L-12 | „Spiel verlassen"                          | Platz weg, Cookies weg, zurück zum Start                                                      | geht   | -              |
| L-13 | Lobby ohne gültiges Cookie                 | 403 → „neu beitreten"                                                                         | geht   | -              |
| L-14 | Spiel ohne Karte angelegt                  | Start gesperrt und sagt warum, statt stumm nichts zu tun; die API antwortet 409 `no-map` (S9) | geht   | -              |
| L-15 | Spiel mit Passwort                         | das Passwort steht an der Leitstelle unter der Spiel-ID, so wie es getippt wurde (F3)         | geht   | f3-lobby       |
| L-16 | „Einladung kopieren"                       | kopiert Name, Link, Spiel-ID und Passwort (F3)                                                | geht      | f3-lobby       |
| L-18 | Kopieren wird verweigert                   | der Text steht in einem Feld zum Markieren (F3)                                               | ungeprüft | -              |
| L-17 | Host schaltet den Chat in der Lobby        | aus und wieder an; die Handys folgen ohne Reload, der Chat verschwindet und kommt wieder (F3) | geht   | f3-lobby       |

## V — verbindung

| ID   | Fall                                    | Erwartet                                                                          | Status | E2E |
| ---- | --------------------------------------- | --------------------------------------------------------------------------------- | ------ | --- |
| V-01 | Backend startet neu, Socket fällt weg   | verbindet allein neu, Zustand stimmt danach — auch was währenddessen passiert ist | geht   | -   |
| V-02 | Socket wird abgelehnt (4403)            | kein Reconnect-Sturm, Screen sagt was los ist                                     | geht   | -   |
| V-03 | Verbindung weg                          | Hinweis am Screen, statt eingefrorenem Spiel                                      | geht   | -   |
| V-04 | zwei Tabs desselben Spielers            | zeigen dasselbe, keiner überschreibt den anderen                                  | offen  | -   |
| V-05 | Safari: Socket und fetch im selben Task | fetch hängt nicht (2.4)                                                           | geht   | -   |
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
| P-06 | Plätze umbauen während Pause      | geht weiter (1.6)                                                                                                                                | geht   | -   |

## R — die runde

| ID   | Fall                                                           | Erwartet                                                                                                                     | Status    | E2E                       |
| ---- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------- | ------------------------- |
| R-01 | Agenten der Runde                                              | alle mit Start und Ziel sichtbar                                                                                             | geht      | -                         |
| R-02 | Verkehrsmittel wählen                                          | pro Agent, vier Linien                                                                                                       | geht      | -                         |
| R-03 | Route wählen                                                   | Vorschau über das Pathfinding                                                                                                | geht      | -                         |
| R-04 | abschicken                                                     | Platz steht auf „abgeschickt"                                                                                                | geht      | -                         |
| R-05 | Fortschritt                                                    | „x von y abgeschickt", host-gesteuerte zählen mit                                                                            | geht      | -                         |
| R-06 | letzter Spieler schickt ab                                     | Runde wird gerechnet                                                                                                         | geht      | -                         |
| R-07 | Simulation läuft                                               | Fortschritt kommt an (`simulation.progress`) und zählt, wer zu Hause ist, über beide Wege bis 100 % (F2d)                     | ungeprüft | `test_rounds.py`          |
| R-08 | Auto auf einer Kante ohne Straße                               | wird abgelehnt, Client wie Server                                                                                            | geht      | `edge-rules.test.ts`      |
| R-09 | Rundenzähler                                                   | zeigt die richtige Runde (2.4-Bug)                                                                                           | ungeprüft | -                         |
| R-10 | Spieler verlässt mitten in der Runde                           | Runde kann trotzdem fertig werden                                                                                            | offen     | -                         |
| R-11 | Reconnect mitten in der Runde                                  | schon abgeschickte Wahl ist noch da                                                                                          | geht      | -                         |
| R-12 | ÖPNV-Route gibt es nicht                                       | sagt es und lässt eine andere Linie wählen                                                                                   | geht      | -                         |
| R-13 | Chat während der Runde                                         | erreichbar                                                                                                                   | geht      | `chat.spec.ts`            |
| R-14 | ÖPNV fahren und das letzte Stück laufen                        | Runde wird gerechnet, nicht abgebrochen                                                                                      | geht      | -                         |
| R-15 | Bus & Bahn auf der ausgelieferten Karte                        | findet für jedes der 36 Wohnort-Arbeitsplatz-Paare eine Verbindung (S5)                                                      | geht      | `replay.spec.ts`          |
| R-16 | Auto auf einem Tor (Busspur oder Radweg nimmt die letzte Spur) | wird gar nicht erst als Route angeboten, statt beim Abschicken abgelehnt (S6)                                                | geht      | `edge-rules.test.ts`      |
| R-17 | Luftlinie                                                      | steht am Gruppe, sobald er ausgewählt ist — vor jeder Wahl (S6)                                                            | geht      | -                         |
| R-18 | zu weit zu Fuß (über 5 km) oder mit dem Rad (über 15 km)       | der Modus ist nicht wählbar, wenn schon die Luftlinie zu weit ist; sonst sagt die Route, dass es zu weit ist (S6)            | geht      | `trip-limits.test.ts`     |
| R-19 | Stau der letzten Runde auf der Karte                           | dickere Linie, wo es langsamer war — keine Farbskala (S6)                                                                    | geht      | `traffic.test.ts`         |
| R-20 | „schnellste"                                                   | rechnet mit den gemessenen Geschwindigkeiten der letzten Runde, nicht mit dem Tempolimit (S6)                                | geht      | `maps.tests.test_traffic` |
| R-21 | Route auf der Karte                                            | in der Farbe und im Strich ihres Verkehrsmittels, nicht überall bernstein (S6)                                               | geht      | -                         |
| R-22 | Seite neu laden mitten in einer angefangenen Runde             | die schon gewählten Verkehrsmittel sind wieder da, die Routen werden neu gesucht; nicht gewählte Gruppen bleiben leer (S7) | geht      | `round-draft.spec.ts`     |
| R-23 | Hin- und Rückweg pro Gruppe                                    | unter der gefundenen Route steht „zurück x min“; abgeschickt werden beide Wege, der Rückweg mit demselben Verkehrsmittel gesucht | geht      | `round-draft.spec.ts`     |
| R-24 | Ziel erreichbar, aber kein Weg zurück (Einbahnstraße)          | „Die Gruppe kommt hin, aber nicht wieder nach Hause.“, kein Neu-Versuch, Losfahren bleibt gesperrt                         | ungeprüft | -                         |
| R-25 | Runde ohne Rückweg abschicken (direkt an der API)              | 400, `return_route` fehlt; ein Rückweg, der nicht am Zuhause endet oder gegen eine Einbahnstraße fährt, wird abgelehnt     | geht      | -                         |
| R-26 | Route suchen lassen                                            | erst wird die Suche gezeigt, in der Primärfarbe; die Route erscheint, wenn sie fertig ist, nicht vorher (F3)                 | geht      | `s24-spielbildschirme.spec.ts` |
| R-27 | sehr kurzer Weg                                                | die Suche ist trotzdem zu sehen, mindestens eine gute halbe Sekunde (F3)                                                     | geht      | `search-trace.test.ts`    |
| R-28 | Zuhause und Ziel auf dem Handy                                 | kleiner als bisher, decken die Straßen daneben nicht zu, sind aber noch zu finden (F3, 390px)                                | geht      | -                         |
| R-29 | zu Fuß durch den Tiergarten                                    | von einem Wohnort an der S-Bahn Bellevue zur Arbeit Brandenburger Tor, Lützowplatz oder TU Berlin lässt sich zu Fuß gehen, 2,8–4,1 km über die Wege im Tiergarten, gepunktet auf der Karte; zur Arbeit Justizministerium „Weiter als 5.0 km“ (F11, WebKit) | geht      | -                         |
| R-30 | Bus und Bahn mit derselben Nummer | eine Fahrt bleibt auf ihrer Linie: der Rückweg von Arbeit Brandenburger Tor nach Wohnort 4–6 fährt Bus 100 bis Großer Stern und steigt in die 101 um — vorher fuhr er als „Bus 100“ ab S Tiergarten auf den Gleisen der Stadtbahn weiter, weil Bus 2 und Zug 2 für eine Linie galten; jede Fahrt auf der ausgelieferten Karte geht von einer Haltestelle ihrer Linie zur nächsten (F8) | geht | `pt-routing.test.ts` |

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
| A-11 | jemand ist nicht angekommen   | sagt es, statt „alle sind angekommen" — gezählt vom Simulator, auch wer noch vor der Haustür stand (S25). Seit F2d läuft ein Weg, bis alle da sind: vorkommen kann es nur bei kaputten Kartendaten oder wenn die Fehlergrenze von 1000 Ticks greift | geht      | `counts.test.ts`, `test_simulation.py` |
| A-12 | Runde ohne Aufzeichnung       | sagt es in einer Zeile, die Zahlen stehen trotzdem da              | ungeprüft | -                |
| A-13 | ein Punkt sind 10 Menschen    | steht unter der Karte, als ganze Zahl (S25; vorher 50)             | geht      | `replay.spec.ts` |
| A-14 | kein Punkt gehört jemandem    | alle Geräte sehen dieselbe Animation, niemand ist markiert         | geht      | -                |
| A-15 | Leitstelle                      | zeigt dieselbe Animation, vor den Zahlen                           | geht      | `replay.spec.ts` |
| A-16 | 390px und dunkel              | Karte lesbar, keine Querscrollbar                                  | geht      | -                |
| A-17 | Bildrate                      | volle Karte, 6 400 Menschen: läuft rund in WebKit — 60 fps bei ~800 Punkten, auch bei ~1 450 (S25, Desktop; Telefon nicht gemessen) | geht      | -                |
| A-18 | zwei Minuten                  | Hin- und Rückweg, 6 400 Menschen: 120,0 s Wandzeit für 120 s Wiedergabe, 60 fps, auch bei 390px (F3, WebKit Desktop; Telefon nicht gemessen) | geht      | -                |

`A-08` bis `A-12` und `A-17` stehen offen, weil sie in dem Durchlauf nicht vorkamen: in der
gefahrenen Runde ist **jeder angekommen**, also war nur die ehrliche Variante des Schlussbilds nicht
zu sehen, und die Haltestellen-Schlange über die Zeit sowie die Bildrate mit sechs Plätzen sind noch
nicht gemessen.

## Z — zwischen den runden

| ID   | Fall                               | Erwartet                                                                                                                 | Status    | E2E             |
| ---- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------- | --------------- |
| Z-01 | Runde fertig                       | Ergebnis pro Spieler: CO₂, Kosten, Zeit                                                                                  | geht      | numbers.spec.ts |
| Z-02 | alle haben gelesen                 | weiter zur Diskussion                                                                                                    | geht      | f15-leitstelle  |
| Z-03 | keine Kartenversionen zur Wahl     | direkt die nächste Runde                                                                                                 | geht      | -               |
| Z-04 | Host öffnet die Abstimmung         | nur aus der Diskussion heraus                                                                                            | geht      | f15-leitstelle  |
| Z-05 | abstimmen                          | Fortschritt „x von y"                                                                                                    | geht      | f15-leitstelle  |
| Z-06 | Gleichstand                        | Patt-Runde                                                                                                               | geht      | -               |
| Z-07 | Patt: Mehrheit will nochmal        | gleiche Optionen, Stimmen gelöscht                                                                                       | ungeprüft | -               |
| Z-08 | Patt: Mehrheit will nicht          | Karte bleibt wie sie ist                                                                                                 | geht      | -               |
| Z-09 | Host beendet das Patt              | „so lassen"                                                                                                              | ungeprüft | -               |
| Z-10 | Reconnect mitten in der Abstimmung | **dieselben** Optionen, nicht neu gezogen                                                                                | geht      | -               |
| Z-11 | Gewinner wird angewendet           | nächste Runde läuft auf der neuen Karte                                                                                  | geht      | f15-leitstelle  |
| Z-12 | zweimal abstimmen                  | sagt „schon abgestimmt", statt einen Fehler zu zeigen                                                                    | geht      | -               |
| Z-13 | Pause in einer Phase               | Banner da, Phase läuft nicht weiter                                                                                      | geht      | -               |
| Z-14 | Host stimmt für seine Plätze ab    | einer nach dem anderen, verdeckter Zwischenschritt                                                                       | geht      | f15-leitstelle  |
| Z-15 | Tabelle nach der Runde             | steht auf „pro Person" und sagt, für wie viele Menschen eine Gruppe steht                                               | geht      | numbers.spec.ts |
| Z-16 | Schalter „alle Pendler"            | jede CO₂- und Kostenzelle wird eine andere Zahl; die Zeit bleibt der Schnitt pro Weg                                     | geht      | numbers.spec.ts |
| Z-17 | Zeilen ergeben nicht die Summe     | Zeile „Linien ohne Gruppen" schließt die Lücke genau, mit einem Satz warum                                             | geht      | numbers.spec.ts |
| Z-18 | bezahlt gegen gekostet             | steht unter der Tabelle; am eigenen Platz persönlich, an der Leitstelle für alle Pendler                                         | geht      | numbers.spec.ts |
| Z-19 | „Wie wird gerechnet?"              | Overlay mit Maßstab, Zeit, Kosten, Fahrplan und Stau                                                                     | geht      | numbers.spec.ts |
| Z-20 | Wartebildschirme                   | Erklärtext steht voll ausgeschrieben da — beim Warten auf die Runde und in der Diskussion, **nie** neben dem Stimmzettel | ungeprüft | -               |
| Z-21 | Zeit im Ergebnis                   | Hin- und Rückweg zusammen, als Mittel über die Gruppen; CO₂ und Kosten sind die Summe beider Wege                        | geht      | -               |
| Z-22 | Stau auf der Karte der Wahl        | die gerade gefahrene Runde, am Handy und an der Leitstelle; vorher stand dort die Runde davor, nach Runde 1 gar keine (F3) | geht      | f3-zwischen-den-runden |
| Z-23 | Karte in der Diskussion            | dieselbe Karte wie bei der Wahl, mit Stau, darüber oder daneben (F3)                                                     | geht      | f3-zwischen-den-runden |
| Z-24 | Leitstelle während der Wahl        | sagt, wie man abstimmt: tippen, klicken oder die Zahl; „reihum weitergeben“ steht nicht da, wenn an der Leitstelle niemand spielt (F3) | geht      | f3-zwischen-den-runden |
| Z-25 | jemand ist während der Wahl gegangen | „Plätze anzeigen“ an der Leitstelle, Platz entfernen, die Wahl schließt ohne den Platz (F3)                              | geht      | f3-zwischen-den-runden |
| Z-26 | Karte daneben auf dem Beamer       | die Spielbildschirme gehen bis an den Rand, die Karte bekommt die halbe Breite statt eines Drittels (F3)                 | geht      | -               |
| Z-27 | Plätze an der Leitstelle in der Wahl | „Gib den Rechner reihum weiter“ steht über der Liste der Plätze, die noch abstimmen (F3)                                 | geht      | f15-leitstelle  |
| Z-28 | eine Gruppe fährt Rad              | Kosten und „selbst bezahlt“ sind gleich, 0,03 € pro km und Person, kein CO₂; zu Fuß bleibt beides 0 (F12)                 | geht      | -               |
| Z-29 | Änderung auf der Karte             | jede Option hat „Auf der Karte zeigen“, in der Diskussion und auf dem Stimmzettel, am Handy und an der Leitstelle: die Karte zeigt, was sie gegenüber der gespielten Version ändert — Straßen blau, Bus & Bahn gelb, was wegfällt hohl; der Stau tritt so lange zurück | geht      | f15-leitstelle  |

## E — spielende

| ID   | Fall                             | Erwartet                                                                                           | Status    | E2E             |
| ---- | -------------------------------- | -------------------------------------------------------------------------------------------------- | --------- | --------------- |
| E-01 | letzte Runde gespielt            | Ende mit Grund `max_rounds`                                                                        | geht      | f15-leitstelle  |
| E-02 | CO₂-Budget überschritten         | Ende mit Grund `co2_limit`                                                                         | geht      | -               |
| E-03 | Auswertung                       | pro Spieler über alle Runden, drei Reihenfolgen, niemand gekürt                                    | geht      | -               |
| E-04 | Host beendet von Hand            | Ende, alle sehen es                                                                                | geht      | -               |
| E-05 | Spiel endet wegen Inaktivität    | meldet heute `max_rounds` — **falsch**, offen im Backend                                           | kaputt    | -               |
| E-06 | nach dem Ende                    | Anonymisierung greift nach `ANONYMISE_GRACE_HOURS`                                                 | offen     | -               |
| E-07 | Auswertung Runde für Runde       | eine Linie mit einem Halt pro Runde; bei nur einer Runde keine                                     | geht      | f15-leitstelle  |
| E-08 | Auswertung neu geladen           | Zahlen und Grund stehen weiter da, ohne Socket                                                     | geht      | -               |
| E-09 | Auswertung auf dem Handy         | eigener Platz in allen drei Listen mit „du" markiert                                               | geht      | -               |
| E-10 | Spiel mit den Vorgabewerten (S2) | endet **nicht** in Runde 1; sechs Runden sind fahrbar, wenn die Klasse umsteigt                    | geht      | -               |
| E-11 | Was der Fahrplan gekostet hat    | eigener Block, Klassenmaßstab, mit dem Anteil auf Linien, die niemand genutzt hat                  | geht      | numbers.spec.ts |
| E-12 | die drei Listen                  | sortieren pro Weg, nicht auf den Summen; wer vorzeitig raus ist, ist markiert; Schalter auch hier  | geht      | numbers.spec.ts |
| E-13 | Was ihr geändert habt      | eine Zeile pro Abstimmung mit Stimmen und Gewinner; ohne Abstimmung sagt es das                    | geht      | numbers.spec.ts |
| E-14 | „davon selbst bezahlt"           | in der Kostenliste, wenn man einen Namen aufklappt                                                 | geht      | numbers.spec.ts |
| E-15 | Auswertung mit Abstimmungen      | Karte mit mehreren Versionen: Gewinner, Stimmen, Patt und „von der Spielleitung beendet" stehen da | ungeprüft | -               |
| E-16 | Leitstelle am Spielende                    | „Zu deinen Spielen" führt nach `/app/host` (F3)                                               | geht      | f3-lobby       |
| E-17 | „Neues Spiel anlegen" am Spielende         | führt ins Formular, in der SPA statt über Django (F3)                                         | ungeprüft | -              |

## H — die leitstelle (host)

| ID   | Fall                                                     | Erwartet                                                                                                         | Status    | E2E                |
| ---- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------- | ------------------ |
| H-01 | Host spielt nicht mit                                    | eigene Zeile bleibt stumm, Runde wartet nicht auf sie                                                            | geht      | -                  |
| H-02 | Host legt einen Platz an                                 | wird an der Leitstelle gespielt                                                                                   | geht      | f15-leitstelle     |
| H-03 | Host spielt die Plätze reihum                            | einer nach dem anderen                                                                                           | geht      | f15-leitstelle     |
| H-04 | Wechsel zwischen zwei Plätzen                            | verdeckter Zwischenschritt, Beamer zeigt nichts                                                                  | geht      | f15-leitstelle     |
| H-05 | Host übernimmt den Platz eines Schülers                  | dessen Gerät fliegt raus (`taken_over`)                                                                          | geht      | -                  |
| H-06 | Host gibt den Platz per Code zurück                      | Handy scannt/tippt, Platz ist zurück                                                                             | geht      | -                  |
| H-07 | Code nach 5 Minuten                                      | abgelaufen                                                                                                       | ungeprüft | -                  |
| H-08 | neuer Code für denselben Platz                           | macht den alten ungültig                                                                                         | geht      | -                  |
| H-09 | ganzes Spiel auf einem Rechner                           | läuft durch, ohne ein einziges Handy                                                                             | geht      | f15-leitstelle     |
| H-10 | Pause-Knopf                                              | beim Host, wirkt überall                                                                                         | geht      | -                  |
| H-11 | Host beendet aus der Lobby                               | geht auch bei einem Spiel ohne Karte, Grund `host`                                                               | geht      | -                  |
| H-12 | Spiel anlegen: CO₂-Budget und Menschen pro Gruppe (S2) | vorgeschlagen werden 106 Menschen pro Gruppe und 2,4 kg pro Person und Runde („normal“), zusammen 97.920 kg für 6 Runden — nicht 500 und 1000 | geht      | `e2e/host.spec.ts` |
| H-13 | Spiel anlegen mit weniger Plätzen                        | Vorschlag folgt der Klassengröße sofort: 8 Plätze → 212 Menschen pro Gruppe, das Budget bleibt; 3 Runden → 48.960 kg | geht      | `e2e/host.spec.ts` |
| H-14 | Vorschlag überschreiben                                  | eigene Zahl bleibt stehen, auch wenn sich die Klassengröße danach ändert; „Vorschlag übernehmen" holt sie zurück | geht      | `e2e/host.spec.ts` |
| H-15 | Karte ohne Abstimmung auswählen                          | die Auswahl sagt, dass es auf dieser Karte nichts abzustimmen gibt                                               | geht      | -                  |
| H-16 | `/game/create/` aufrufen                                 | leitet in die SPA weiter; ohne Login erst zum Login                                                              | geht      | `e2e/host.spec.ts` |
| H-17 | Karte mit ungemessener Pendlerzahl auswählen (S21)       | Warnung: Menschen pro Gruppe ist nur ein Vorgabewert, und mit ihm das CO₂-Budget; die mitgelieferte Karte hat keine | geht      | `e2e/host.spec.ts` |
| H-18 | „Weitere Einstellungen" (S21)                            | zu, bis man es aufmacht; lehnt der Server ein Feld darin ab, geht es von selbst auf                              | geht      | -                  |
| H-19 | Platz übernehmen, nachdem die Leitstelle „Weiter für alle hier" gedrückt hat | der Knopf kommt wieder (der Platz hat nichts gelesen); ein Druck, und es geht weiter                             | geht      | f3-zwischen-den-runden |
| H-20 | Spiel anlegen: CO₂ pro Person und Runde (F8)             | Auswahl 1,0 bis 6,0 kg in Schritten von 0,2, „normal“ bei 2,4; 2,0 kg bei 3 Runden → 40.800 kg; das Spiel speichert die Kilo; der Server lehnt alles außerhalb der Auswahl auf Deutsch ab | geht      | `e2e/host.spec.ts`, `test_join` |

## C — chat

| ID   | Fall                            | Erwartet                                                                        | Status | E2E            |
| ---- | ------------------------------- | ------------------------------------------------------------------------------- | ------ | -------------- |
| C-01 | Nachricht schicken              | kommt bei allen an                                                              | geht   | `chat.spec.ts` |
| C-02 | neu verbinden                   | Verlauf ist da (100 Nachrichten, 2 h)                                           | geht   | `chat.spec.ts` |
| C-03 | zu schnell tippen               | Rate limit, verständliche Meldung                                               | geht   | `chat.spec.ts` |
| C-04 | Chat ist aus                    | kein Chat sichtbar                                                              | geht   | `chat.spec.ts` |
| C-05 | Chat auf dem neuen Spielscreen  | erreichbar wie auf dem alten                                                    | geht   | `chat.spec.ts` |
| C-06 | ungelesene Nachrichten          | Zähler am Knopf, solange der Chat zu ist (S8)                                   | geht   | `chat.spec.ts` |
| C-07 | Chat an- oder ausschalten       | im Formular unter „Weitere Einstellungen" (S21); in der Lobby nur über die API  | geht   | `chat.spec.ts` |
| C-08 | Platz stummschalten             | fragt vorher, Kennzeichen am Platz, Nachricht wird abgelehnt (S9)               | geht   | `mute.spec.ts` |
| C-09 | stummgeschaltet schreiben       | deutsche Begründung, Zeile kommt bei niemandem an (S9)                          | geht   | `mute.spec.ts` |
| C-10 | Stummschaltung aufheben         | ohne Rückfrage, ohne Neuverbinden wirksam (S9)                                  | geht   | `mute.spec.ts` |
| C-11 | eigene Host-Zeile stummschalten | gibt es nicht — der Host steht nicht in der Platzliste, die API sagt 409 `host` | geht   | -              |
| C-12 | Chat aus, Socket von Hand       | Server weist ab (4403), offener Socket bekommt „Chat ausgeschaltet" (S21)       | geht   | -              |

> Seit S8 (28.09.26) ist der Chat wieder da, neu gegen `ChatConsumer` gebaut und auf jedem
> Spielscreen erreichbar (`GameFrame` hängt ihn einmal ein). Von F5 (18.09.26) bis dahin gab es
> **gar keinen Chat**: er hing am alten Screen, der mit F5 gelöscht wurde.
>
> C-04 hängt am REST-Snapshot: `chat_enabled` kommt nur dort an, `game.state` trägt es nicht und
> kein Event meldet eine Änderung. Ein laufender Client zeigt den Chat also bis zum nächsten
> Neuladen weiter an — schreiben kann er seit S21 aber nicht mehr.
>
> C-12: bis S21 hat **nur der Client** `chat_enabled` gelesen. `ChatConsumer` hat nie
> nachgesehen, ein von Hand gebauter Socket konnte in einem Spiel mit ausgeschaltetem Chat
> weiterschreiben. Jetzt weist der Server beim Verbinden ab und prüft jede Nachricht noch einmal,
> wie beim Stummschalten. Geprüft in `game/tests/test_socket.py`, nicht im Browser — der Client
> öffnet in diesem Fall ja gar keinen Socket.
>
> C-08 bis C-11 sind neu mit S9 (28.09.26). `Player.is_muted` und `MuteUnmutePlayerView` gab es
> vorher schon, beides wirkungslos: die View hing an keiner URL und **kein Consumer hat das Feld
> gelesen**. Geprüft werden muss das mit zwei echten Geräten — ein Platz an der Leitstelle teilt
> Cookie und Socket mit dem Host, und der Host ist nie stummgeschaltet.

## K — karte und editor

| ID   | Fall                                                       | Erwartet                                                                                                                                                                                                                                  | Status    | E2E        |
| ---- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---------- |
| K-01 | Karte im Spiel                                             | Knoten, Kanten, Linien, Legende                                                                                                                                                                                                           | geht      | -          |
| K-08 | Hintergrundbild im Spiel                                   | liegt unter dem Graphen, richtig platziert                                                                                                                                                                                                | geht      | -          |
| K-02 | Karte auf dem Handy                                        | passt aufs Bild, Auswahl erreichbar (2.4)                                                                                                                                                                                                 | geht      | -          |
| K-03 | Kante anklicken                                            | reagiert (2.4)                                                                                                                                                                                                                            | geht      | -          |
| K-04 | Editor lädt                                                | Graph erscheint, auf Deutsch, mit Legende                                                                                                                                                                                                 | geht      | -          |
| K-05 | Editor: Knoten und Kanten bearbeiten                       | speichert                                                                                                                                                                                                                                 | geht      | -          |
| K-06 | Editor: Version anlegen                                    | taucht in der Abstimmung auf                                                                                                                                                                                                              | ungeprüft | -          |
| K-17 | Version anlegen lässt die anderen Versionen ganz           | eine Version über eine Straße zu zeichnen nimmt keiner anderen Version ihre Buslinie oder ihre Bahn: jede Version behält 136 Kanten und alle zehn Linien durchgehend (S15)                                                                | geht      | -          |
| K-18 | Kombiversion                                               | trägt beide Änderungen, alle sechs Bahnlinien und keine Straße doppelt (S15)                                                                                                                                                              | geht      | -          |
| K-19 | Linie in einer Version geändert                            | die Version fährt über die geänderte Straße, die Ausgangsversion über die alte (S15)                                                                                                                                                      | geht      | -          |
| K-20 | Export einer Version, deren Straße fehlt                   | lässt das Teilstück weg **und sagt welche Linie und welche Kante** — vorher still (S15)                                                                                                                                                   | geht      | -          |
| K-07 | Karte importieren / exportieren                            | JSON rein und raus                                                                                                                                                                                                                        | geht      | -          |
| K-21 | Ganze Karte exportieren                                    | `/export/` schreibt alle Versionen, die Abstimmung zwischen ihnen, beide Abstimmungstexte und zu jedem Knoten, jeder Kante und jeder Linie, in welche Version sie gehört (S14)                                                            | geht      | map-export |
| K-22 | Ganze Karte importieren                                    | dieselbe Datei ergibt dieselbe Karte mit allen Versionen: gemessen an der geseedeten Karte, 5 Versionen, je 136 Kanten, alle zehn Linien, jede `compatible_versions`-Verbindung (S14)                                                     | geht      | -          |
| K-23 | Linie, die je Version anders fährt                         | die Datei schreibt eine Route je Strecke statt eine je Version; nach dem Import fährt die eine Version über die Busspur-Kopie, die andere über die alte Straße (S14)                                                                      | geht      | -          |
| K-24 | Alte, flache Kartendatei                                   | eine Datei ohne `versions`-Block importiert unverändert in genau eine Basisversion — jede Datei in `map_examples/` ist eine (S14)                                                                                                         | geht      | -          |
| K-25 | Kaputte Kartendatei von Hand                               | ein Index, der ins Leere zeigt, keine oder zwei Basisversionen, eine namenlose Version: der Upload sagt was falsch ist, statt eine Karte mit einem Loch anzulegen (S14)                                                                   | geht      | -          |
| K-26 | Version, in der eine Linie keine Kante erreicht            | steht als leere Strecke in der Datei, statt zu fehlen — auf der Kopie der Box-Karte liest Bus `100` dort 0 Kanten, `101` 6 (S14, Vorbereitung für S16)                                                                                    | geht      | -          |
| K-27 | Die Karte der Box liegt als Datei vor                      | `map_examples/Berlin_Mitte-West.json` ist die gespielte Karte mit allen acht Versionen, den drei Eingriffen und den zwölf Abstimmungspaaren — vorher lag sie nur im pg-Dump (S16)                                                         | geht      | -          |
| K-28 | Weg ohne Straße darunter                                   | `"type": "path"`: die zwölf Fuß- und Radverbindungen (drei Wohnorte zur S-Bahn Bellevue, Justizministerium zum Checkpoint Charlie, seit F11 acht durch den Tiergarten und um den Potsdamer Platz) kommen ohne `StreetEdge` durch Export und Import — vorher erfand der Import 50 km/h und eine Spur (S16) | geht      | -          |
| K-29 | Busspuren in beide Richtungen                              | jede der 15 Achsen von 100 und 101 hat die Busspur hin **und** zurück; alle vier Linienrichtungen fahren in der Busspuren-Version vollständig darauf (S16)                                                                                | geht      | -          |
| K-30 | Bahn in jeder Kombiversion                                 | alle sechs Bahnlinien sind in allen acht Versionen, 67,27 Linien-km überall — vorher 0 in den vier erzeugten Kombinationen (S16)                                                                                                          | geht      | -          |
| K-31 | Keine Straße doppelt in einer Kombiversion                 | eine Kombiversion mit Busspuren trägt die Busspur-Kopie **statt** der alten Straße; Autospur-km fallen dort von 113,2 auf 82,5 (S16)                                                                                                      | geht      | -          |
| K-32 | Abstimmungstext einer Kombiversion                         | ist Deutsch und eine Frage wie bei den handgezeichneten Versionen — vorher „Apply changes: ...“ auf dem Wahlzettel (S16)                                                                                                                  | geht      | -          |
| K-33 | Zu Fuß zur Arbeit auf der ausgelieferten Karte             | 14 von 36 Wegen von einem Wohnort zur Arbeit sind hin und zurück höchstens 5 km lang, in jeder Version; der kürzeste ist 2,75 km, von Wohnort 2 durch den Tiergarten zur Arbeit Brandenburger Tor — vorher 3, in den Umgehungsstraßen-Versionen 9 (F11) | geht      | `test_example_map` |
| K-09 | Export → Import derselben Karte                            | Bild, Maße und Platzierung kommen mit                                                                                                                                                                                                     | ungeprüft | -          |
| K-13 | Export → Import: Linien                                    | Plätze, Takt und Tempo jeder Linie kommen mit (S5)                                                                                                                                                                                        | geht      | -          |
| K-14 | Export → Import: Kartenwerte                               | Platzzahl und die drei Geschwindigkeiten kommen mit; eine alte Datei ohne die Schlüssel behält die Vorgabewerte (S5)                                                                                                                      | geht      | -          |
| K-15 | Linien der ausgelieferten Karte                            | alle zwölf durchgehend **in jeder Version, zu der sie gehören**, Hin- und Rückrichtung halten an denselben Bahnhöfen, Bus 85 / Bahn 1000 Plätze, ein Tempo je Linienpaar (S16)                                                            | geht      | -          |
| K-16 | Karte neu importieren                                      | dieselbe Datei ergibt dieselbe Karte: 8 Versionen, 55 Knoten, 186 Kanten, 6 Bus- und 6 Zuglinien, 13x10, Pendlerzahl und Budget (S16)                                                                                                     | geht      | -          |
| K-12 | Export → Import: Pendlerzahl und CO₂-Budget der Karte (S2) | kommen mit; eine alte Datei ohne die Schlüssel behält die Vorgabewerte                                                                                                                                                                    | geht      | -          |
| K-10 | Hintergrundbild neben den Graphen geschoben                | bleibt ganz sichtbar, wird nicht abgeschnitten                                                                                                                                                                                            | geht      | -          |
| K-11 | Kartendetail                                               | Hintergrundbild liegt unter dem Graphen                                                                                                                                                                                                   | geht      | -          |
| K-33 | Karten-Upload auf Deutsch                                  | Beschriftungen, Hilfetexte und Absagen sind deutsch; die JSON-Schlüssel bleiben englisch, weil sie die Feldnamen der Karte sind (S17)                                                                                                     | geht      | -          |
| K-34 | Kartenschirme auf Deutsch                                  | Detailseite und Editor sagen nichts mehr auf Englisch — kein „All maps", kein englischer `confirm()`, keine Überschrift „Modify Edge" (S17)                                                                                              | geht      | -          |
| K-35 | Alle Karten                                                | `/app/maps` ist eine Liste mit Größe, Plätzen, Pendlern und ob es etwas abzustimmen gibt; „Alle Karten“ und das Löschen einer Karte landen dort statt auf dem Beitreten-Screen (S18)                                                     | geht      | -          |
| K-36 | Alte Kartenseiten                                          | `/map/list/` und `/map/<id>/` leiten in die SPA um; die Django-Seiten sind weg (S18)                                                                                                                                                     | geht      | -          |
| K-37 | Kartenbereich in den Farben der Seite                      | Liste, Detail und Editor nur in Blau, Bernstein und Tinte, hell und dunkel; Straße durchgezogen, Bahn gestrichelt, Weg gepunktet (S18)                                                                                                   | geht      | -          |
| K-38 | Editor auf dem Handy                                       | sagt, dass der Bildschirm zu klein ist; „Trotzdem anzeigen“ zeigt ihn doch (S18)                                                                                                                                                         | geht      | -          |
| K-39 | Karte hochladen in der SPA                                 | `/app/maps/upload` legt eine Karte aus der Datei an und öffnet sie; `/map/upload/` leitet dorthin um und nimmt selbst keine Datei mehr an (S19)                                                                                          | geht      | `map-upload.spec.ts`|
| K-40 | Kaputte Kartendatei in der SPA                             | alles, was in der Datei falsch ist, steht auf einmal und auf Deutsch unter dem Formular; ein vergebener Name steht am Namensfeld (S19)                                                                                                   | geht      | `map-upload.spec.ts`|
| K-41 | Aufbau der Datei                                           | hinter einem Schalter statt über dem Formular; nennt jeden Schlüssel, den der Import liest (S19)                                                                                                                                         | geht      | `map-upload.spec.ts`|
| K-42 | Karte löschen                                              | fragt in einem eigenen Dialog statt im Browser-Fenster, sagt, dass die Spiele bleiben; Abbrechen behält die Karte (S19)                                                                                                                  | geht      | `map-upload.spec.ts`|
| K-43 | Editor: Straße unter einer Kante anlegen                   | erscheint sofort, unter beiden Richtungen; der Knopf ist gesperrt, bis sie zu sehen ist — vorher gespeichert und bis zu einer Stunde nicht gezeigt, und ein zweiter Klick legte eine zweite Straße an (F10)                             | geht      | `f10-editor.spec.ts`|
| K-44 | Editor: Gegenrichtung anlegen                              | wird genau einmal angelegt; der Knopf bleibt gesperrt, bis die neue Richtung gezeichnet ist — vorher war er nach 20 ms wieder klickbar, über einer Anzeige, die noch „Einbahn“ sagte (F10)                                              | geht      | `f10-editor.spec.ts`|
| K-45 | Editor: in der Basis gezeichnet                            | Knoten, Kante, Straße oder Gleis sind in allen acht Versionen; eine Version mit eigener Kopie der Kante (Busspuren, Umgehungsstraße) behält ihre Kopie, und eine Version ohne einen der Knoten bekommt die Kante nicht (F10)              | geht      | `f10-editor.spec.ts`|
| K-46 | Editor: in einer Änderung gezeichnet                       | landet in der Änderung und in jeder Kombiversion, die sie enthält — nicht in der Basis, nicht in den anderen Änderungen (F10)                                                                                                           | geht      | -          |
| K-47 | Editor: dieselbe Kante zweimal                             | wird abgelehnt: „Diese Kante gibt es in dieser Version schon.“ Ebenso eine zweite Straße oder ein zweites Gleis unter einer Kante. Beide Richtungen über einer schon vorhandenen ziehen legt nur die fehlende an (F10)                     | geht      | -          |
| K-48 | Editor: Zeile ohne Version                                 | wird abgelehnt, auf Deutsch: „Ohne Version wäre das auf keiner Karte zu sehen.“ (F10)                                                                                                                                                  | geht      | -          |
| K-49 | Editor: zwei Kanten schnell hintereinander                 | solange die erste gespeichert wird, nimmt die Leinwand keine zweite an (F10)                                                                                                                                                             | geht      | -          |
| K-50 | Editor: Version löschen                                    | fragt in einem Dialog, was mitgeht: was nur in dieser Version steht (Knoten, Kanten, Straßen, Gleise, Linien), aus welcher Abstimmung sie fällt, welche Kombiversionen ihre Änderung behalten; danach ist genau das weg und keine Zeile steht in keiner Version (F14) | geht      | `f14-version-loeschen.spec.ts` |
| K-51 | Editor: Grundversion löschen                               | gibt es keinen Knopf dafür; über die API oder im Admin abgelehnt: „Die Grundversion lässt sich nicht löschen …“ (F14) | geht      | `f14-version-loeschen.spec.ts` |
| K-52 | Editor: Version löschen, während ein Spiel läuft           | abgelehnt, solange auf der Karte ein Spiel läuft, auch pausiert; der Dialog nennt das Spiel und bietet nur „Schließen“ (F14) | geht      | `f14-version-loeschen.spec.ts` |
| K-53 | Editor: Version löschen, auf der gespielt wurde            | abgelehnt, wenn ein Spiel auf ihr gespielt hat, sie zur Wahl stand, für sie gestimmt wurde oder über ihre Straßen gefahren ist — sonst gingen Wege und Stimmen mit; der Satz nennt die Spiele und den Ausweg „Verträglich mit“ (F14) | geht      | - |
| K-54 | Admin: Version löschen                                     | dieselbe Aufräumregel wie im Editor, einzeln und über „ausgewählte löschen“; die Bestätigungsseite nennt, was mitgeht, eine Ablehnung steht dort als geschützt und löscht nichts (F14) | geht      | - |
| K-55 | Wahlzettel fragt nach der einen Änderung | jede der 24 Optionen der ausgelieferten Karte stellt die Frage der Änderung, die der Schritt macht — hinzu ihre Frage, zurück ihre Rückfrage; von „Buslinie + Umgehungsstraßen“ zurück auf „Buslinie“ fragt nach dem Schließen der Umgehungsstraßen, nicht nach dem Bau der 147 (F16) | geht | - |
| K-56 | Bild auf dem Wahlzettel | entfällt: der Wahlzettel zeigt kein Bild mehr, sondern die Änderung selbst auf der Karte (Z-29); der Server schickt das Bild der Änderung weiter mit, gelesen wird es nicht. Die Grundversion fragt nie mit „Die Karte soll ...“ (F16) | geht | - |
| K-57 | Editor: Version ansehen | „Ansehen“ unter „Verwalten“ legt die Version auf die Karte und zeichnet, was sie gegenüber ihrer Ausgangsversion ändert, daneben in Worten: Busspuren = 15 Straßen, beide Richtungen, „eine Autospur wird Busspur“, keine Linie; Buslinie = Bus 147 hin und zurück; Umgehungsstraßen = Bundestag – Wohnort 2 neu und der Weg Botschaftsviertel – Philharmonie wird Straße | geht | `versionsvergleich.spec.ts` |
| K-58 | Editor: mit einer anderen Version vergleichen | „Verglichen mit“ nimmt jede Version; Grundversion gegen Busspuren zeigt die 30 Busspuren hohl, „die Busspur wird wieder Autospur“; eine Kombiversion gegen eine ihrer Änderungen ist genau die andere | geht | `versionsvergleich.spec.ts`, vitest |
| K-59 | Kartendatei prüfen | `./manage.py check_map datei.json` sagt zur ausgelieferten Karte „in Ordnung“; eine kaputte Datei bekommt jedes Problem mit seiner Regel genannt — eine Linie gegen ihre Richtung, zwei Kanten zwischen denselben Knoten, ein Wohnort ohne Weg zur Arbeit und zurück — und der Befehl endet mit Fehler (F8) | geht | `test_checks` |
| K-60 | Karte kalibrieren | `./manage.py calibrate_map datei.json --speed 19` auf der ausgelieferten Karte (Postgres): 6.800 Pendler, alle im Auto 19,4 km/h; Tabelle pro Person 4,17 / 3,16 / 2,41 / 1,96 / 1,53 kg, „normal, 2,4 kg, reicht hier, wenn 49 % der Gruppen Auto fahren“; `--commuters 6800` misst dieselbe Tabelle ohne Suche; eine Karte, die `check_map` nicht besteht, wird nicht gemessen (F8) | geht | `test_calibration` |
| K-61 | Tram in der Kartendatei | `"type": "tram"` kommt als Straße mit Gleis darin an, `tram_track` sagt `lane` (Vorgabe) oder `own`; eine Bahnlinie sagt `"kind": "tram"` und bekommt ohne eigene Zahlen 248 Plätze und 30 km/h; der Export schreibt alles so wieder hinaus, jede Bahnlinie mit ihrer Art; `tram_track` an einer anderen Art Kante, ein unbekannter Wert und eine unbekannte Art werden auf Deutsch abgelehnt (F8) | geht | `test_portability` |
| K-62 | Tram im Stau | auf Gleis in der Autospur steht die Tram mit den Autos in der Schlange und die Autos hinter ihr warten; auf eigenem Gleis fährt sie frei; „eigenes Gleis“ nimmt eine Spur, auf einer einspurigen Straße die letzte, und ein Auto darüber wird beim Abschicken abgelehnt; Gleis neben oder unter der Straße hält nichts auf (F8) | geht | `test_linkqueue`, `test_rounds` |
| K-63 | Editor: wo das Gleis liegt | an einer Kante mit Straße und Gleis steht „Gleis: daneben oder darunter / in der Autospur / eigenes Gleis (eine Spur)“ und geht für beide Richtungen mit „Speichern“, das Gleis-Abzeichen sagt dann „Bahn, in der Autospur“; ohne Gleis lehnt der Server es ab; wird das Gleis gelöscht, geht die Angabe mit (F8) | geht | `test_graph` |
| K-64 | Editor: Tramlinie | „+ Bahnlinie“ fragt nach der Art; „Tram“ startet mit 248 Plätzen und 30 km/h, „S- oder U-Bahn“ mit 1.000 und 40; die Liste zeigt „Tram“ (F8) | geht | - |
| K-65 | Editor: Version „eigenes Gleis“ | in einer Änderung das Gleis auf „eigenes Gleis“ gestellt: die Version hat eine Kopie der Straße, die Tram fährt dort darüber, die Basis behält das Gleis in der Autospur; „Ansehen“ unter „Verwalten“ sagt „eine Autospur wird eigenes Tramgleis“; eine geänderte Tramlinie bleibt eine Tram (F8) | geht | `test_versions`, `version-diff.test.ts` |
| K-66 | Kartendatei prüfen: Tram | `check_map` meldet eine S- oder U-Bahn auf Gleis in der Autospur und eine Tramstraße, die in einer Version kein Gleis hat (F8) | geht | `test_checks` |

## S — sonstiges

| ID   | Fall                            | Erwartet                                                                                                   | Status    | E2E                     |
| ---- | ------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------- | ----------------------- |
| S-01 | Impressum, Datenschutz, Cookies | von jeder Seite außerhalb des Spiels erreichbar, in der Fußzeile beider Hälften (S20)                      | geht      | `chrome.spec.ts`        |
| S-02 | heller und dunkler Modus        | auf beiden Hälften, ein Schalter                                                                           | ungeprüft | -                       |
| S-03 | 390px                           | kein horizontales Scrollen, nirgends                                                                       | geht      | -                       |
| S-04 | Spielernamen                    | tauchen beim Beitreten und beim Anlegen eines Platzes in keinem Log auf (S22)                              | geht      | -                       |
| S-05 | Anonymisierung                  | nach Spielende „Spieler N", Host wird „Host"                                                               | ungeprüft | -                       |
| S-07 | Spiel auf der Hostseite löschen | fragt vorher und sagt, was mitgeht; laufendes Spiel wird abgelehnt                                         | geht      | `e2e/host-page.spec.ts` |
| S-08 | Kopf- und Fußzeile unter `/app` | dieselben Punkte wie auf den Django-Seiten, Karten nur für Staff, Abmelden; nicht im Spiel, nicht im Editor (S20) | geht      | `chrome.spec.ts`        |
| S-09 | Passwort raten                  | nach 10 Fehlversuchen 429 mit deutscher Seite, 15 Minuten (S9)                                             | geht      | -                       |
| S-10 | Platz-Code raten                | nach 20 Fehlgriffen 429; gültige Codes zählen nie mit (S9)                                                 | geht      | -                       |
| S-11 | viele Konten anlegen            | nach 10 angelegten Konten pro Stunde 429; abgelehnte Formulare zählen nicht (S9)                           | geht      | -                       |
| S-12 | `robots.txt` und `llms.txt`     | beide unter `/`, nur über nginx — im Dev-Stack gibt es sie nicht                                           | ungeprüft | -                       |
| S-13 | Anmelden                        | landet direkt auf `/app/host`, der eigenen Seite mit Spielen und Konto — ein Sprung, nicht zwei (S22)      | geht      | `e2e/host.spec.ts`      |
| S-14 | Kontodaten ändern               | Anzeigename, Benutzername und E-Mail lassen sich speichern; ein vergebener Name wird auf Deutsch abgelehnt | geht      | `e2e/host-page.spec.ts` |
| S-15 | Konto löschen erreichbar        | ein Klick von der Hostseite auf die Bestätigungsseite                                                      | geht      | `e2e/host-page.spec.ts` |
| S-16 | `/game/<id>/share/`             | leitet in die Lobby, die ID und QR-Code ohnehin zeigt                                                      | geht      | -                       |
| S-17 | Wortwahl                        | eine Gruppe heißt überall Gruppe, der Hostrechner ist die Leitstelle, der weite Maßstab „alle Pendler"    | geht      | `numbers.spec.ts`       |
| S-18 | keine Schulwörter               | kein „Klasse", „Unterricht", „Lehrer", „Pult", „Schule" oder „Figur" — im Wörterbuch außer im Beispiel im Namensfeld (S17), in den Django-Seiten ohne Ausnahme (S23) | geht      | -                       |
| S-19 | Kopfzeile der Django-Seiten     | Menüs öffnen unter ihrem Knopf, Esc und Klick daneben schließen; Handy-Menü mit Unterlisten; nichts von fremden Servern | geht      | -                       |
| S-20 | Schriftzug                      | das Zeichen ist das C von CO₂mmute, der Rest steht in derselben Schrift wie die Seite; auf beiden Hälften gleich groß, hell wie dunkel lesbar (S20) | geht      | -                       |
| S-21 | Quellcode                       | Link aufs Repository in der Fußzeile beider Hälften (S20)                                                  | geht      | `chrome.spec.ts`        |
| S-22 | Breite von Kopf- und Fußzeile   | auf beiden Hälften gleich breit und gleich eingerückt; ein Screen unter `/app` ist nie breiter (S20)       | geht      | -                       |
| S-23 | Menü ohne Konto                 | wer mitspielt, sieht keine Karten und kein Abmelden, nur Anmelden (S20)                                            | geht      | `chrome.spec.ts`        |
| S-24 | falsches Passwort               | Meldung auf Deutsch über dem Formular, der Name bleibt stehen; ein unbekannter Name liest sich genauso (S22) | geht      | -                       |
| S-25 | Konto mit schwachem Passwort    | jede verletzte Regel als eigener deutscher Satz; die Regeln stehen schon vor dem Tippen unter dem Feld (S22) | geht      | `credentials.spec.ts`   |
| S-26 | Passwort vergessen              | Formular statt Serverfehler, deutsche Mail mit Link, der Link setzt ein neues Passwort; eine unbekannte Adresse sieht gleich aus (S22) | geht | `credentials.spec.ts` |
| S-27 | Passwort ändern                 | erst das bisherige, dann zweimal das neue; man bleibt angemeldet (S22)                                      | geht      | -                       |
| S-28 | „Angemeldet bleiben“            | ohne Haken endet die Anmeldung mit dem Browser, mit Haken nach 14 Tagen (S22)                               | geht      | -                       |
| S-29 | Abmelden                        | eigene Seite im Design, sagt dass die Spiele weiterlaufen (S22)                                            | geht      | -                       |
| S-30 | Django-Seiten im Design         | Anmelden, Konto und Passwort-Seiten so breit, so gesetzt und so gefärbt wie die SPA; hell und dunkel, 390px (S22) | geht | -                       |
| S-31 | Umweg auf der Startseite        | die Linie von Bus & Bahn verlässt das Bündel, überbrückt Rad- und Fußlinie, hält an einer eigenen Station zum Hintergrund und fädelt wieder ein; die anderen drei Linien laufen ohne Naht durch; hell und dunkel, 390px (S23) | geht | -                       |
| S-32 | `/docs/hintergrund/` ist das Dokument | trägt `docs/de-hintergrund.md` bis vor die Kalibrierung: dieselben Kapitel und Abschnitte in derselben Reihenfolge, dieselben Zahlen in beide Richtungen, dieselben Abbildungen (S23, unter `/docs/` seit F13) | geht | -                       |
| S-33 | Haltestellen auf den Docs-Seiten | auf breiten Schirmen läuft die Liste der Kapitel mit, die schon passierten sind gefüllt; auf dem Handy steht sie über dem Text; ohne JavaScript bleiben alle hohl und die Links gehen; Schnellstart und Ablaufdiagramme zeigen ihre Abschnitte als kleinere Halte unter dem Kapitel (S23, F13) | geht | -                       |
| S-34 | Abbildungen                     | Kante, CO₂-Kurve, Runde nach Autoanteil, Maßstab: zwei Farben und Tinte, hell und dunkel lesbar, auf 390px ohne Querscrollen, und als Bild für sich lesbar, wie die Docs sie zeigen (S23) | geht | -                       |
| S-35 | Herkunft                        | Startseite und Hintergrund nennen die Masterarbeit an der Freien Universität Berlin und die Weiterentwicklung an der TU Berlin (S23) | geht | -                       |
| S-36 | „Docs“ in der Kopfzeile          | auf beiden Hälften dasselbe Menü: Schnellstart, Hintergrund, Ablaufdiagramme, nichts auf Englisch; auf dem Handy genauso (F13) | geht | `chrome.spec.ts`        |
| S-37 | Docs auf Deutsch                 | drei Seiten unter `/docs/`, deutsch wie die ganze Seite; die englischen unter `/docs/en/` geben 404, ihr Text steht nur in `docs/`; `/hintergrund/` gibt 404, die Startseite führt zum neuen Ort (F13) | geht | `chrome.spec.ts`        |
| S-38 | Ablaufdiagramme auf der Seite    | zwölf Diagramme in den Farben der Seite, hell und dunkel lesbar; alle hochkant und höchstens 784px breit, ab 1280px in voller Größe neben den Haltestellen, schmaler kleiner — nichts scrollt seitwärts; auf 390px nimmt der Kasten die ganze Breite, über die Linie, und das ganze Diagramm ist zu sehen (F13) | geht | -                       |

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
