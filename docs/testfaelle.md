# Testfälle

Was das Spiel können muss, Fall für Fall. Zwei Zwecke: nachhalten was tatsächlich läuft, und
die Vorlage für die Integrationstests aus Phase 3 — die werden aus dieser Liste geschrieben,
nicht neu erfunden.

**Status heißt:**

| Status | bedeutet |
| --- | --- |
| `geht` | einmal wirklich durchgespielt, im Browser oder von einem Test. Nicht "sieht richtig aus". |
| `ungeprüft` | gebaut, aber noch nie durchgespielt |
| `offen` | noch nicht gebaut |
| `kaputt` | durchgespielt und fällt durch |

Die Spalte **E2E** trägt den Playwright-Test, sobald es einen gibt. `-` heißt: von Hand geprüft.

Geprüft wird in WebKit — das ist Safari und jeder Browser auf dem iPhone — hell und dunkel,
390px und Desktop.

---

## J — beitreten

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| J-01 | Spiel-ID gibt es nicht | „Es gibt kein Spiel mit dieser ID.", zurück zur Eingabe | geht | - |
| J-02 | Lobby offen, kein Passwort | Name rein, Spieler angelegt, Lobby | geht | - |
| J-03 | Spiel läuft schon | 409 `started`, Formular gesperrt | geht | - |
| J-04 | Spiel ist vorbei | 409 `ended`, Formular gesperrt | geht | - |
| J-05 | Spiel ist voll | 409 `full`, Formular gesperrt | geht | - |
| J-06 | Passwort nötig, richtig | kommt rein | geht | - |
| J-07 | Passwort nötig, falsch | 403, Feld bleibt stehen, Name bleibt stehen | geht | - |
| J-08 | Passwort nötig, keins eingegeben | wie falsches Passwort | geht | - |
| J-09 | kein Name eingegeben | Meldung, gar kein Request | geht | - |
| J-10 | Spiel füllt sich während des Tippens | erst beim Absenden 409 `full` | offen | - |
| J-11 | QR-Code scannen | landet direkt auf `/app/join/<ID>` | offen | - |
| J-12 | „Sitzung fortsetzen" mit Platz-Code (1.7) | Platz übernommen, neue `player_id` | geht | - |
| J-13 | Code abgelaufen oder schon benutzt | 404, sagt dass der Code weg ist | geht | - |
| J-14 | Code, aber der Browser hat schon einen Platz | 409 `seated` | ungeprüft | - |
| J-15 | Code, aber man ist der Host des Spiels | 409 `host` | geht | - |
| J-16 | zweimal aus demselben Browser beitreten | kein zweiter Platz | offen | - |

## L — lobby

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| L-01 | eigener Platz | ist als „du" markiert | geht | - |
| L-02 | zweites Gerät tritt bei | erscheint **ohne Reload** | geht | - |
| L-03 | Spieler verlässt das Spiel | verschwindet aus der Liste | offen | - |
| L-04 | Gerät schließt den Tab | nach ~90 s „nicht verbunden", Eintrag bleibt | geht | - |
| L-05 | Host startet das Spiel | Lobby merkt es ohne Reload | geht | - |
| L-06 | Einstellungen | Agenten, Runden, CO₂-Budget, Chat stimmen | geht | - |
| L-07 | Host entfernt einen Spieler | dessen Gerät: „Dein Platz ist weg", mit Grund | geht | - |
| L-08 | Platzzahl | die Host-Zeile zählt nicht mit | geht | - |
| L-09 | Platz am Lehrerrechner (1.6) | ist als solcher markiert | geht | - |
| L-10 | Host legt einen Platz an (1.6) | erscheint bei allen, zählt gegen `max_players` | geht | - |
| L-11 | Host entfernt einen host-gesteuerten Platz | verschwindet, Runde wartet nicht mehr | geht | - |
| L-12 | „Spiel verlassen" | Platz weg, Cookies weg, zurück zum Start | geht | - |
| L-13 | Lobby ohne gültiges Cookie | 403 → „neu beitreten" | geht | - |
| L-14 | Spiel ohne Karte angelegt | Start gesperrt und sagt warum, statt stumm nichts zu tun | geht | - |

## V — verbindung

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| V-01 | Backend startet neu, Socket fällt weg | verbindet allein neu, Zustand stimmt danach — auch was währenddessen passiert ist | geht | - |
| V-02 | Socket wird abgelehnt (4403) | kein Reconnect-Sturm, Screen sagt was los ist | geht | - |
| V-03 | Verbindung weg | Hinweis am Screen, statt eingefrorenem Spiel | geht | - |
| V-04 | zwei Tabs desselben Spielers | zeigen dasselbe, keiner überschreibt den anderen | offen | - |
| V-05 | Safari: Socket und fetch im selben Task | fetch hängt nicht (2.4) | geht | - |
| V-06 | Backend-Neustart | niemand bleibt für immer „online" (Presence-TTL) | geht | - |
| V-07 | Handy sperrt und wacht wieder auf | Platz ist noch da, Cookie verlängert | offen | - |

## P — pause

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| P-01 | Host pausiert | Banner auf allen Screens, ohne Reload | geht | - |
| P-02 | Host hebt die Pause auf | Banner weg, ohne Reload | geht | - |
| P-03 | Zug abschicken während Pause | gar nicht erst möglich: Banner, Auswahl und Knopf gesperrt; die 409-Meldung greift für den Fall, dass die Pause zwischen Klick und Request kommt | geht | - |
| P-04 | Pause mitten in der Zwischenrunde | Phase bleibt stehen, nichts rutscht weiter | offen | - |
| P-05 | Pause über eine Schulstunde | Cookies verlängert, Platz danach noch da | offen | - |
| P-06 | Plätze umbauen während Pause | geht weiter (1.6) | geht | - |

## R — die runde

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| R-01 | Agenten der Runde | alle mit Start und Ziel sichtbar | geht | - |
| R-02 | Verkehrsmittel wählen | pro Agent, vier Linien | geht | - |
| R-03 | Route wählen | Vorschau über das Pathfinding | geht | - |
| R-04 | abschicken | Platz steht auf „abgeschickt" | geht | - |
| R-05 | Fortschritt | „x von y abgeschickt", host-gesteuerte zählen mit | geht | - |
| R-06 | letzter Spieler schickt ab | Runde wird gerechnet | geht | - |
| R-07 | Simulation läuft | Fortschritt kommt an (`simulation.progress`) | ungeprüft | - |
| R-08 | Auto auf einer Kante ohne Straße | wird abgelehnt (heute defekt, s. CLAUDE.md) | offen | - |
| R-09 | Rundenzähler | zeigt die richtige Runde (2.4-Bug) | ungeprüft | - |
| R-10 | Spieler verlässt mitten in der Runde | Runde kann trotzdem fertig werden | offen | - |
| R-11 | Reconnect mitten in der Runde | schon abgeschickte Wahl ist noch da | geht | - |
| R-12 | ÖPNV-Route gibt es nicht | sagt es und lässt eine andere Linie wählen | geht | - |
| R-13 | Chat während der Runde | erreichbar | offen | - |

## Z — zwischen den runden

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| Z-01 | Runde fertig | Ergebnis pro Spieler: CO₂, Kosten, Zeit | geht | - |
| Z-02 | alle haben gelesen | weiter zur Diskussion | geht | - |
| Z-03 | keine Kartenversionen zur Wahl | direkt die nächste Runde | geht | - |
| Z-04 | Host öffnet die Abstimmung | nur aus der Diskussion heraus | geht | - |
| Z-05 | abstimmen | Fortschritt „x von y" | geht | - |
| Z-06 | Gleichstand | Patt-Runde | geht | - |
| Z-07 | Patt: Mehrheit will nochmal | gleiche Optionen, Stimmen gelöscht | ungeprüft | - |
| Z-08 | Patt: Mehrheit will nicht | Karte bleibt wie sie ist | geht | - |
| Z-09 | Host beendet das Patt | „so lassen" | ungeprüft | - |
| Z-10 | Reconnect mitten in der Abstimmung | **dieselben** Optionen, nicht neu gezogen | geht | - |
| Z-11 | Gewinner wird angewendet | nächste Runde läuft auf der neuen Karte | geht | - |
| Z-12 | zweimal abstimmen | sagt „schon abgestimmt", statt einen Fehler zu zeigen | geht | - |
| Z-13 | Pause in einer Phase | Banner da, Phase läuft nicht weiter | geht | - |
| Z-14 | Host stimmt für seine Plätze ab | einer nach dem anderen, verdeckter Zwischenschritt | geht | - |

## E — spielende

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| E-01 | letzte Runde gespielt | Ende mit Grund `max_rounds` | geht | - |
| E-02 | CO₂-Budget überschritten | Ende mit Grund `co2_limit` | geht | - |
| E-03 | Auswertung | pro Spieler über alle Runden, drei Reihenfolgen, niemand gekürt | geht | - |
| E-04 | Host beendet von Hand | Ende, alle sehen es | geht | - |
| E-05 | Spiel endet wegen Inaktivität | meldet heute `max_rounds` — **falsch**, offen im Backend | kaputt | - |
| E-06 | nach dem Ende | Anonymisierung greift nach `ANONYMISE_GRACE_HOURS` | offen | - |
| E-07 | Auswertung Runde für Runde | eine Linie mit einem Halt pro Runde; bei nur einer Runde keine | geht | - |
| E-08 | Auswertung neu geladen | Zahlen und Grund stehen weiter da, ohne Socket | geht | - |
| E-09 | Auswertung auf dem Handy | eigener Platz in allen drei Listen mit „du" markiert | geht | - |

## H — das leitpult (host)

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| H-01 | Host spielt nicht mit | eigene Zeile bleibt stumm, Runde wartet nicht auf sie | geht | - |
| H-02 | Host legt einen Platz an | wird am Lehrerrechner gespielt | geht | - |
| H-03 | Host spielt die Plätze reihum | einer nach dem anderen | geht | - |
| H-04 | Wechsel zwischen zwei Plätzen | verdeckter Zwischenschritt, Beamer zeigt nichts | geht | - |
| H-05 | Host übernimmt den Platz eines Schülers | dessen Gerät fliegt raus (`taken_over`) | geht | - |
| H-06 | Host gibt den Platz per Code zurück | Handy scannt/tippt, Platz ist zurück | geht | - |
| H-07 | Code nach 5 Minuten | abgelaufen | ungeprüft | - |
| H-08 | neuer Code für denselben Platz | macht den alten ungültig | geht | - |
| H-09 | ganzes Spiel auf einem Rechner | läuft durch, ohne ein einziges Handy | geht | - |
| H-10 | Pause-Knopf | beim Host, wirkt überall | geht | - |

## C — chat

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| C-01 | Nachricht schicken | kommt bei allen an | offen | - |
| C-02 | neu verbinden | Verlauf ist da (100 Nachrichten, 2 h) | offen | - |
| C-03 | zu schnell tippen | Rate limit, verständliche Meldung | offen | - |
| C-04 | Chat ist aus | kein Chat sichtbar | offen | - |
| C-05 | Chat auf dem neuen Spielscreen | erreichbar wie auf dem alten | offen | - |

> Seit F5 (18.09.26) gibt es im Spiel **gar keinen Chat mehr**: er hing am alten Screen, der mit
> F5 gelöscht ist. Er kommt als eigener Chunk wieder, gegen `ChatConsumer` neu gebaut.

## K — karte und editor

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| K-01 | Karte im Spiel | Knoten, Kanten, Linien, Legende | geht | - |
| K-08 | Hintergrundbild im Spiel | liegt unter dem Graphen, richtig platziert | geht | - |
| K-02 | Karte auf dem Handy | passt aufs Bild, Auswahl erreichbar (2.4) | geht | - |
| K-03 | Kante anklicken | reagiert (2.4) | geht | - |
| K-04 | Editor lädt | Graph erscheint, auf Deutsch, mit Legende | geht | - |
| K-05 | Editor: Knoten und Kanten bearbeiten | speichert | geht | - |
| K-06 | Editor: Version anlegen | taucht in der Abstimmung auf | ungeprüft | - |
| K-07 | Karte importieren / exportieren | JSON rein und raus | ungeprüft | - |
| K-09 | Export → Import derselben Karte | Bild, Maße und Platzierung kommen mit | ungeprüft | - |
| K-10 | Hintergrundbild neben den Graphen geschoben | bleibt ganz sichtbar, wird nicht abgeschnitten | geht | - |
| K-11 | Kartendetail | Hintergrundbild liegt unter dem Graphen | geht | - |

## S — sonstiges

| ID | Fall | Erwartet | Status | E2E |
| --- | --- | --- | --- | --- |
| S-01 | Impressum, Datenschutz, Cookies | von jeder Seite erreichbar | ungeprüft | - |
| S-02 | heller und dunkler Modus | auf beiden Hälften, ein Schalter | ungeprüft | - |
| S-03 | 390px | kein horizontales Scrollen, nirgends | geht | - |
| S-04 | Spielernamen | tauchen in keinem Log auf | ungeprüft | - |
| S-05 | Anonymisierung | nach Spielende „Spieler N", Host wird „Host" | ungeprüft | - |
| S-06 | Rechtstexte in der SPA | Links auch im Spiel erreichbar | offen | - |
