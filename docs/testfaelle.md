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
| J-11 | QR-Code scannen                              | landet direkt auf `/app/join/<ID>`                      | offen     | -   |
| J-12 | „Sitzung fortsetzen" mit Platz-Code (1.7)    | Platz übernommen, neue `player_id`                      | geht      | -   |
| J-13 | Code abgelaufen oder schon benutzt           | 404, sagt dass der Code weg ist                         | geht      | -   |
| J-14 | Code, aber der Browser hat schon einen Platz | 409 `seated`                                            | ungeprüft | -   |
| J-15 | Code, aber man ist der Host des Spiels       | 409 `host`                                              | geht      | -   |
| J-16 | zweimal aus demselben Browser beitreten      | kein zweiter Platz                                      | offen     | -   |

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
| R-07 | Simulation läuft                                               | Fortschritt kommt an (`simulation.progress`)                                                                                 | ungeprüft | -                         |
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
| A-11 | jemand ist nicht angekommen   | sagt es, statt „alle sind angekommen"                              | ungeprüft | -                |
| A-12 | Runde ohne Aufzeichnung       | sagt es in einer Zeile, die Zahlen stehen trotzdem da              | ungeprüft | -                |
| A-13 | ein Punkt sind 50 Menschen    | steht unter der Karte                                              | geht      | -                |
| A-14 | kein Punkt gehört jemandem    | alle Geräte sehen dieselbe Animation, niemand ist markiert         | geht      | -                |
| A-15 | Leitstelle                      | zeigt dieselbe Animation, vor den Zahlen                           | geht      | `replay.spec.ts` |
| A-16 | 390px und dunkel              | Karte lesbar, keine Querscrollbar                                  | geht      | -                |
| A-17 | Bildrate                      | große Karte, sechs Plätze: läuft rund in WebKit                    | ungeprüft | -                |

`A-08` bis `A-12` und `A-17` stehen offen, weil sie in dem Durchlauf nicht vorkamen: in der
gefahrenen Runde ist **jeder angekommen**, also war nur die ehrliche Variante des Schlussbilds nicht
zu sehen, und die Haltestellen-Schlange über die Zeit sowie die Bildrate mit sechs Plätzen sind noch
nicht gemessen.

## Z — zwischen den runden

| ID   | Fall                               | Erwartet                                                                                                                 | Status    | E2E             |
| ---- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------- | --------------- |
| Z-01 | Runde fertig                       | Ergebnis pro Spieler: CO₂, Kosten, Zeit                                                                                  | geht      | numbers.spec.ts |
| Z-02 | alle haben gelesen                 | weiter zur Diskussion                                                                                                    | geht      | -               |
| Z-03 | keine Kartenversionen zur Wahl     | direkt die nächste Runde                                                                                                 | geht      | -               |
| Z-04 | Host öffnet die Abstimmung         | nur aus der Diskussion heraus                                                                                            | geht      | -               |
| Z-05 | abstimmen                          | Fortschritt „x von y"                                                                                                    | geht      | -               |
| Z-06 | Gleichstand                        | Patt-Runde                                                                                                               | geht      | -               |
| Z-07 | Patt: Mehrheit will nochmal        | gleiche Optionen, Stimmen gelöscht                                                                                       | ungeprüft | -               |
| Z-08 | Patt: Mehrheit will nicht          | Karte bleibt wie sie ist                                                                                                 | geht      | -               |
| Z-09 | Host beendet das Patt              | „so lassen"                                                                                                              | ungeprüft | -               |
| Z-10 | Reconnect mitten in der Abstimmung | **dieselben** Optionen, nicht neu gezogen                                                                                | geht      | -               |
| Z-11 | Gewinner wird angewendet           | nächste Runde läuft auf der neuen Karte                                                                                  | geht      | -               |
| Z-12 | zweimal abstimmen                  | sagt „schon abgestimmt", statt einen Fehler zu zeigen                                                                    | geht      | -               |
| Z-13 | Pause in einer Phase               | Banner da, Phase läuft nicht weiter                                                                                      | geht      | -               |
| Z-14 | Host stimmt für seine Plätze ab    | einer nach dem anderen, verdeckter Zwischenschritt                                                                       | geht      | -               |
| Z-15 | Tabelle nach der Runde             | steht auf „pro Person" und sagt, für wie viele Menschen eine Gruppe steht                                               | geht      | numbers.spec.ts |
| Z-16 | Schalter „alle Pendler"            | jede CO₂- und Kostenzelle wird eine andere Zahl; die Zeit bleibt der Schnitt pro Weg                                     | geht      | numbers.spec.ts |
| Z-17 | Zeilen ergeben nicht die Summe     | Zeile „Linien ohne Gruppen" schließt die Lücke genau, mit einem Satz warum                                             | geht      | numbers.spec.ts |
| Z-18 | bezahlt gegen gekostet             | steht unter der Tabelle; am eigenen Platz persönlich, an der Leitstelle für alle Pendler                                         | geht      | numbers.spec.ts |
| Z-19 | „Wie wird gerechnet?"              | Overlay mit Maßstab, Zeit, Kosten, Fahrplan und Stau                                                                     | geht      | numbers.spec.ts |
| Z-20 | Wartebildschirme                   | Erklärtext steht voll ausgeschrieben da — beim Warten auf die Runde und in der Diskussion, **nie** neben dem Stimmzettel | ungeprüft | -               |

## E — spielende

| ID   | Fall                             | Erwartet                                                                                           | Status    | E2E             |
| ---- | -------------------------------- | -------------------------------------------------------------------------------------------------- | --------- | --------------- |
| E-01 | letzte Runde gespielt            | Ende mit Grund `max_rounds`                                                                        | geht      | -               |
| E-02 | CO₂-Budget überschritten         | Ende mit Grund `co2_limit`                                                                         | geht      | -               |
| E-03 | Auswertung                       | pro Spieler über alle Runden, drei Reihenfolgen, niemand gekürt                                    | geht      | -               |
| E-04 | Host beendet von Hand            | Ende, alle sehen es                                                                                | geht      | -               |
| E-05 | Spiel endet wegen Inaktivität    | meldet heute `max_rounds` — **falsch**, offen im Backend                                           | kaputt    | -               |
| E-06 | nach dem Ende                    | Anonymisierung greift nach `ANONYMISE_GRACE_HOURS`                                                 | offen     | -               |
| E-07 | Auswertung Runde für Runde       | eine Linie mit einem Halt pro Runde; bei nur einer Runde keine                                     | geht      | -               |
| E-08 | Auswertung neu geladen           | Zahlen und Grund stehen weiter da, ohne Socket                                                     | geht      | -               |
| E-09 | Auswertung auf dem Handy         | eigener Platz in allen drei Listen mit „du" markiert                                               | geht      | -               |
| E-10 | Spiel mit den Vorgabewerten (S2) | endet **nicht** in Runde 1; sechs Runden sind fahrbar, wenn die Klasse umsteigt                    | geht      | -               |
| E-11 | Was der Fahrplan gekostet hat    | eigener Block, Klassenmaßstab, mit dem Anteil auf Linien, die niemand genutzt hat                  | geht      | numbers.spec.ts |
| E-12 | die drei Listen                  | sortieren pro Weg, nicht auf den Summen; wer vorzeitig raus ist, ist markiert; Schalter auch hier  | geht      | numbers.spec.ts |
| E-13 | Was ihr geändert habt      | eine Zeile pro Abstimmung mit Stimmen und Gewinner; ohne Abstimmung sagt es das                    | geht      | numbers.spec.ts |
| E-14 | „davon selbst bezahlt"           | in der Kostenliste, wenn man einen Namen aufklappt                                                 | geht      | numbers.spec.ts |
| E-15 | Auswertung mit Abstimmungen      | Karte mit mehreren Versionen: Gewinner, Stimmen, Patt und „von der Spielleitung beendet" stehen da | ungeprüft | -               |

## H — die leitstelle (host)

| ID   | Fall                                                     | Erwartet                                                                                                         | Status    | E2E                |
| ---- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------- | ------------------ |
| H-01 | Host spielt nicht mit                                    | eigene Zeile bleibt stumm, Runde wartet nicht auf sie                                                            | geht      | -                  |
| H-02 | Host legt einen Platz an                                 | wird an der Leitstelle gespielt                                                                                   | geht      | -                  |
| H-03 | Host spielt die Plätze reihum                            | einer nach dem anderen                                                                                           | geht      | -                  |
| H-04 | Wechsel zwischen zwei Plätzen                            | verdeckter Zwischenschritt, Beamer zeigt nichts                                                                  | geht      | -                  |
| H-05 | Host übernimmt den Platz eines Schülers                  | dessen Gerät fliegt raus (`taken_over`)                                                                          | geht      | -                  |
| H-06 | Host gibt den Platz per Code zurück                      | Handy scannt/tippt, Platz ist zurück                                                                             | geht      | -                  |
| H-07 | Code nach 5 Minuten                                      | abgelaufen                                                                                                       | ungeprüft | -                  |
| H-08 | neuer Code für denselben Platz                           | macht den alten ungültig                                                                                         | geht      | -                  |
| H-09 | ganzes Spiel auf einem Rechner                           | läuft durch, ohne ein einziges Handy                                                                             | geht      | -                  |
| H-10 | Pause-Knopf                                              | beim Host, wirkt überall                                                                                         | geht      | -                  |
| H-11 | Host beendet aus der Lobby                               | geht auch bei einem Spiel ohne Karte, Grund `host`                                                               | geht      | -                  |
| H-12 | Spiel anlegen: CO₂-Budget und Menschen pro Gruppe (S2) | vorgeschlagen werden 48.000 kg und 100, nicht 500 und 1000                                                       | geht      | `e2e/host.spec.ts` |
| H-13 | Spiel anlegen mit weniger Plätzen                        | Vorschlag folgt der Klassengröße sofort: 8 Plätze → 200 Menschen pro Gruppe, 3 Runden → 24.000 kg              | geht      | `e2e/host.spec.ts` |
| H-14 | Vorschlag überschreiben                                  | eigene Zahl bleibt stehen, auch wenn sich die Klassengröße danach ändert; „Vorschlag übernehmen" holt sie zurück | geht      | `e2e/host.spec.ts` |
| H-15 | Karte ohne Abstimmung auswählen                          | die Auswahl sagt, dass es auf dieser Karte nichts abzustimmen gibt                                               | geht      | -                  |
| H-16 | `/game/create/` aufrufen                                 | leitet in die SPA weiter; ohne Login erst zum Login                                                              | geht      | `e2e/host.spec.ts` |

## C — chat

| ID   | Fall                            | Erwartet                                                                        | Status | E2E            |
| ---- | ------------------------------- | ------------------------------------------------------------------------------- | ------ | -------------- |
| C-01 | Nachricht schicken              | kommt bei allen an                                                              | geht   | `chat.spec.ts` |
| C-02 | neu verbinden                   | Verlauf ist da (100 Nachrichten, 2 h)                                           | geht   | `chat.spec.ts` |
| C-03 | zu schnell tippen               | Rate limit, verständliche Meldung                                               | geht   | `chat.spec.ts` |
| C-04 | Chat ist aus                    | kein Chat sichtbar                                                              | geht   | `chat.spec.ts` |
| C-05 | Chat auf dem neuen Spielscreen  | erreichbar wie auf dem alten                                                    | geht   | `chat.spec.ts` |
| C-06 | ungelesene Nachrichten          | Zähler am Knopf, solange der Chat zu ist (S8)                                   | geht   | `chat.spec.ts` |
| C-07 | Chat an- oder ausschalten       | es gibt keinen Schalter — weder im Formular noch in der Lobby, nur über die API | offen  | -              |
| C-08 | Platz stummschalten             | fragt vorher, Kennzeichen am Platz, Nachricht wird abgelehnt (S9)               | geht   | `mute.spec.ts` |
| C-09 | stummgeschaltet schreiben       | deutsche Begründung, Zeile kommt bei niemandem an (S9)                          | geht   | `mute.spec.ts` |
| C-10 | Stummschaltung aufheben         | ohne Rückfrage, ohne Neuverbinden wirksam (S9)                                  | geht   | `mute.spec.ts` |
| C-11 | eigene Host-Zeile stummschalten | gibt es nicht — der Host steht nicht in der Platzliste, die API sagt 409 `host` | geht   | -              |

> Seit S8 (28.09.26) ist der Chat wieder da, neu gegen `ChatConsumer` gebaut und auf jedem
> Spielscreen erreichbar (`GameFrame` hängt ihn einmal ein). Von F5 (18.09.26) bis dahin gab es
> **gar keinen Chat**: er hing am alten Screen, der mit F5 gelöscht wurde.
>
> C-04 hängt am REST-Snapshot: `chat_enabled` kommt nur dort an, `game.state` trägt es nicht und
> kein Event meldet eine Änderung. Ein laufender Client merkt das Ausschalten also erst beim
> nächsten Neuladen.
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
| K-28 | Weg ohne Straße darunter                                   | `"type": "path"`: die vier Fuß- und Radverbindungen (drei Wohnorte zur S-Bahn Bellevue, Justizministerium zum Checkpoint Charlie) kommen ohne `StreetEdge` durch Export und Import — vorher erfand der Import 50 km/h und eine Spur (S16) | geht      | -          |
| K-29 | Busspuren in beide Richtungen                              | jede der 15 Achsen von 100 und 101 hat die Busspur hin **und** zurück; alle vier Linienrichtungen fahren in der Busspuren-Version vollständig darauf (S16)                                                                                | geht      | -          |
| K-30 | Bahn in jeder Kombiversion                                 | alle sechs Bahnlinien sind in allen acht Versionen, 67,27 Linien-km überall — vorher 0 in den vier erzeugten Kombinationen (S16)                                                                                                          | geht      | -          |
| K-31 | Keine Straße doppelt in einer Kombiversion                 | eine Kombiversion mit Busspuren trägt die Busspur-Kopie **statt** der alten Straße; Autospur-km fallen dort von 113,2 auf 82,5 (S16)                                                                                                      | geht      | -          |
| K-32 | Abstimmungstext einer Kombiversion                         | ist Deutsch und eine Frage wie bei den handgezeichneten Versionen — vorher „Apply changes: ...“ auf dem Wahlzettel (S16)                                                                                                                  | geht      | -          |
| K-09 | Export → Import derselben Karte                            | Bild, Maße und Platzierung kommen mit                                                                                                                                                                                                     | ungeprüft | -          |
| K-13 | Export → Import: Linien                                    | Plätze, Takt und Tempo jeder Linie kommen mit (S5)                                                                                                                                                                                        | geht      | -          |
| K-14 | Export → Import: Kartenwerte                               | Platzzahl und die drei Geschwindigkeiten kommen mit; eine alte Datei ohne die Schlüssel behält die Vorgabewerte (S5)                                                                                                                      | geht      | -          |
| K-15 | Linien der ausgelieferten Karte                            | alle zwölf durchgehend **in jeder Version, zu der sie gehören**, Hin- und Rückrichtung halten an denselben Bahnhöfen, Bus 85 / Bahn 1000 Plätze, ein Tempo je Linienpaar (S16)                                                            | geht      | -          |
| K-16 | Karte neu importieren                                      | dieselbe Datei ergibt dieselbe Karte: 8 Versionen, 55 Knoten, 170 Kanten, 6 Bus- und 6 Zuglinien, 13x10, Pendlerzahl und Budget (S16)                                                                                                     | geht      | -          |
| K-12 | Export → Import: Pendlerzahl und CO₂-Budget der Karte (S2) | kommen mit; eine alte Datei ohne die Schlüssel behält die Vorgabewerte                                                                                                                                                                    | geht      | -          |
| K-10 | Hintergrundbild neben den Graphen geschoben                | bleibt ganz sichtbar, wird nicht abgeschnitten                                                                                                                                                                                            | geht      | -          |
| K-11 | Kartendetail                                               | Hintergrundbild liegt unter dem Graphen                                                                                                                                                                                                   | geht      | -          |
| K-33 | Karten-Upload auf Deutsch                                  | Beschriftungen, Hilfetexte und Absagen sind deutsch; die JSON-Schlüssel bleiben englisch, weil sie die Feldnamen der Karte sind (S17)                                                                                                     | geht      | -          |
| K-34 | Kartenschirme auf Deutsch                                  | Detailseite und Editor sagen nichts mehr auf Englisch — kein „All maps", kein englischer `confirm()`, keine Überschrift „Modify Edge" (S17)                                                                                              | geht      | -          |
| K-35 | Alle Karten                                                | `/app/maps` ist eine Liste mit Größe, Plätzen, Pendlern und ob es etwas abzustimmen gibt; „Alle Karten“ und das Löschen einer Karte landen dort statt auf dem Beitreten-Screen (S18)                                                     | geht      | -          |
| K-36 | Alte Kartenseiten                                          | `/map/list/` und `/map/<id>/` leiten in die SPA um; die Django-Seiten sind weg (S18)                                                                                                                                                     | geht      | -          |
| K-37 | Kartenbereich in den Farben der Seite                      | Liste, Detail und Editor nur in Blau, Bernstein und Tinte, hell und dunkel; Straße durchgezogen, Bahn gestrichelt, Weg gepunktet (S18)                                                                                                   | geht      | -          |
| K-38 | Editor auf dem Handy                                       | sagt, dass der Bildschirm zu klein ist; „Trotzdem anzeigen“ zeigt ihn doch (S18)                                                                                                                                                         | geht      | -          |

## S — sonstiges

| ID   | Fall                            | Erwartet                                                                                                   | Status    | E2E                     |
| ---- | ------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------- | ----------------------- |
| S-01 | Impressum, Datenschutz, Cookies | von jeder Seite erreichbar                                                                                 | ungeprüft | -                       |
| S-02 | heller und dunkler Modus        | auf beiden Hälften, ein Schalter                                                                           | ungeprüft | -                       |
| S-03 | 390px                           | kein horizontales Scrollen, nirgends                                                                       | geht      | -                       |
| S-04 | Spielernamen                    | tauchen in keinem Log auf                                                                                  | ungeprüft | -                       |
| S-05 | Anonymisierung                  | nach Spielende „Spieler N", Host wird „Host"                                                               | ungeprüft | -                       |
| S-06 | Rechtstexte in der SPA          | Links auch im Spiel erreichbar                                                                             | offen     | -                       |
| S-07 | Spiel auf der Hostseite löschen | fragt vorher und sagt, was mitgeht; laufendes Spiel wird abgelehnt                                         | geht      | `e2e/host-page.spec.ts` |
| S-08 | Kopfzeile unter `/app`          | auf den Beitreten-Screens, nicht im Spiel, nicht im Editor                                                 | geht      | -                       |
| S-09 | Passwort raten                  | nach 10 Fehlversuchen 429 mit deutscher Seite, 15 Minuten (S9)                                             | geht      | -                       |
| S-10 | Platz-Code raten                | nach 20 Fehlgriffen 429; gültige Codes zählen nie mit (S9)                                                 | geht      | -                       |
| S-11 | viele Konten anlegen            | nach 10 angelegten Konten pro Stunde 429; abgelehnte Formulare zählen nicht (S9)                           | geht      | -                       |
| S-12 | `robots.txt` und `llms.txt`     | beide unter `/`, nur über nginx — im Dev-Stack gibt es sie nicht                                           | ungeprüft | -                       |
| S-13 | Anmelden                        | landet auf `/app/host`, der eigenen Seite mit Spielen und Konto                                            | geht      | `e2e/host.spec.ts`      |
| S-14 | Kontodaten ändern               | Anzeigename, Benutzername und E-Mail lassen sich speichern; ein vergebener Name wird auf Deutsch abgelehnt | geht      | `e2e/host-page.spec.ts` |
| S-15 | Konto löschen erreichbar        | ein Klick von der Hostseite auf die Bestätigungsseite                                                      | geht      | `e2e/host-page.spec.ts` |
| S-16 | `/game/<id>/share/`             | leitet in die Lobby, die ID und QR-Code ohnehin zeigt                                                      | geht      | -                       |
| S-17 | Wortwahl                        | eine Gruppe heißt überall Gruppe, der Hostrechner ist die Leitstelle, der weite Maßstab „alle Pendler"    | geht      | `numbers.spec.ts`       |
| S-18 | keine Schulwörter               | kein „Klasse", „Unterricht", „Lehrer" oder „Pult" im Wörterbuch — außer im Beispiel im Namensfeld (S17)   | geht      | -                       |

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
