# Kalibrierung: die Zahlen, gegen die gespielt wird

Stand 27.09.2026, ergänzt um den Kartendaten-Durchgang vom selben Tag (Abschnitt 8). Gemessen auf
`map_examples/Berlin_Mitte-West.json`, der einzigen Karte, die jemand spielt.

Zwei Einstellungen entscheiden, ob eine Runde etwas bedeutet: für wie viele Menschen eine Gruppe
steht, und wie viel CO₂ die Klasse ausgeben darf. Beide waren nie kalibriert. Ausgeliefert wurden
**1000 Menschen pro Gruppe gegen ein Budget von 500 kg** — auf einer Karte, deren Fahrplan allein
schon 2.449 kg pro Runde ausstößt, bevor irgendwer spielt. Jedes Spiel war nach Runde 1 vorbei.

Das ist jetzt geändert. Was sich geändert hat und warum, steht hier.

---

## 1. Was vorher passiert ist

Eine Gruppe im Auto legt auf dieser Karte im Schnitt 7,66 km zurück (Luftlinie über den kürzesten
Weg, gemessen über alle 36 Wohnort-Arbeitsplatz-Paare). Bei 1000 Menschen pro Gruppe sind das
1000 Autos auf einer Strecke. Eine volle Klasse — 16 Plätze, 4 Gruppen — schickt also 64.000
Autos über 90 Straßenkanten.

Das Modell rechnet das korrekt durch. Es verklemmt nicht, es bricht nicht ab, alle kommen an. Es
meldet nur eine **mittlere Fahrzeit von 298 Minuten für 7,66 km**. Fünf Stunden. Damit die Karte
diesen Verkehr aufnehmen könnte, bräuchte sie ungefähr fünfmal so viele Spuren — Berlin-Mitte ist
keine zehnspurige Rasterstadt. Nicht das Modell war falsch, sondern die Nachfrage.

Gleichzeitig lag das Budget bei 500 kg, während eine Runde je nach Modalsplit zwischen 2.449 und
11.140 kg kostet. Die beiden Zahlen hatten nie etwas miteinander zu tun.

---

## 2. Der Maßstab folgt der Klassengröße

Eine Karte bildet einen Ort ab, und ein Ort hat eine Zahl von Pendlern. Die Klasse **teilt diese
Pendler unter ihren Gruppen auf** — sie erzeugt keine neuen, wenn mehr Schüler kommen. Genau so
rechnet es jetzt:

```
Menschen pro Gruppe = Pendler des Stadtteils / (Plätze × Gruppen pro Platz)
```

Dass das trägt, ist gemessen. Bei konstant 6.400 Pendlern bleibt die Runde dieselbe Runde, egal wie
viele mitspielen:

| Plätze | Gruppen | Menschen/Gruppe | CO₂ Auto | Fahrzeit | Verspätung |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 64 | 100 | 8.691 kg | 20,4 min | 11,3 min |
| 8 | 32 | 200 | 8.630 kg | 20,2 min | 11,0 min |
| 4 | 16 | 400 | 8.904 kg | 20,8 min | 11,4 min |
| 2 | 8 | 800 | 8.652 kg | 20,7 min | 11,5 min |

CO₂ auf ±3 %, Verspätung auf ±0,5 Minuten. Nagelt man stattdessen den Maßstab auf eine feste Zahl,
sieht eine halb besetzte Klasse auf derselben Karte **0,4 Minuten Verspätung statt 11,3** und stößt
44 % des CO₂ aus. Dann hängt das Spiel davon ab, wer zum Unterricht erschienen ist.

Was dabei hätte schiefgehen können — weniger, dafür „dickere" Gruppen drängen sich auf weniger
Strecken — passiert nicht: die kürzesten Wege der ganzen Klasse benutzen ohnehin nur **29 der 90
Straßenkanten**. Das liegt an sechs Wohnorten und sechs Arbeitsplätzen, nicht daran, wie viele
Gruppen sie sich teilen.

## 3. 6.400 ist, was der Graph verkraftet

Nicht, was der Stadtteil hat. Berlin Mitte-West hat weit mehr Pendler. Aber der Graph abstrahiert
den Stadtteil auf seine Hauptachsen, also ist die Zahl, die er tragen kann, die Zahl, die **diese
Achsen** tragen.

Bei 6.400 Pendlern und 100 % Autoanteil laufen die meistbelasteten Kanten (Hansaplatz — Großer
Stern — Brandenburger Tor) auf etwa **115 % ihrer Kapazität**, und 7,66 km dauern 20,4 statt 9,5
Minuten im freien Fluss. Der Berufsverkehr in der Berliner Innenstadt läuft mit rund 24 km/h — das
sind dieselben 11 Minuten Verspätung. Die Zahl ist also an einem Wert draußen geeicht, nicht am
Spielgefühl.

Und der Stau bleibt eine Folge von Entscheidungen, nicht eine Gewissheit:

| Autoanteil | Runde gesamt | Fahrzeit | Verspätung |
| ---: | ---: | ---: | ---: |
| 100 % | 11.140 kg | 20,4 min | 11,3 min |
| 75 % | 8.616 kg | 13,9 min | 4,8 min |
| 50 % | 6.236 kg | 9,5 min | 0,4 min |
| 25 % | 4.385 kg | 9,5 min | 0,1 min |
| 0 % | 2.449 kg | — | — |

Diese Tabelle ist vor dem Kartendaten-Durchgang (Abschnitt 8) gemessen: der Fahrplan-Boden liegt
inzwischen bei 2.864 kg, und jede Runde mit Umsteigern kostet weniger als hier. Die Aussage bleibt.

Steigt die Hälfte der Klasse um, ist der Stau weg. Das ist physikalisch richtig — Stau ist ein
Schwellenphänomen dicht an der Kapazität — und es ist die Lektion, um die es geht.

## 4. Das Budget gilt pro Runde

Weil die Pendlerzahl konstant ist, kostet eine Runde, was sie kostet — unabhängig davon, wie viele
Schüler spielen. Das Budget braucht deshalb **keinen Term für die Gruppengröße**, nur die Rundenzahl:

```
CO₂-Budget = CO₂-Budget der Karte pro Runde × Runden
```

Für diese Karte: **8.000 kg pro Runde, also 48.000 kg für sechs Runden.**

Warum diese Zahl. Über sechs Runden gibt eine Klasse, die nie aus dem Auto steigt, 66.839 kg aus;
eine, die sich herunterarbeitet (100/75/50/50/25/25 % Autoanteil), 40.998 kg. Ein Budget muss
dazwischen liegen, sonst ist es keins. 48.000 kg tut das:

- Wer durchgehend fährt, ist **in Runde 5** raus.
- Wer umsteigt, fährt alle sechs Runden und hat 7 Tonnen übrig.

Es ist nicht das knappste Budget, das funktioniert, sondern die rundeste Zahl innerhalb der Spanne —
die Klasse muss sie im Kopf behalten können.

## 5. Beide Zahlen gehören zur Karte

`district_commuters` und `co2_budget_kg_per_round` stehen jetzt am `GameMap`, nicht im Code. Beides
sind Eigenschaften **dieses Graphen**: wie viel Verkehr seine Achsen tragen, und was eine spielbare
Runde auf seinen Entfernungen und mit seinem Fahrplan kostet. **Eine andere Stadt ist ein anderes
Paar.** Als Konstante im Code hätten die Messwerte eines Stadtteils eine Eigenschaft der Software
festgeschrieben.

Beide gehen beim Export mit und werden beim Import wieder eingelesen. Eine ältere Kartendatei ohne
diese Schlüssel behält die Vorgabewerte.

---

## 6. Eine Korrektur, die der Forschungsgruppe noch nicht vorlag

**Ein Zug stieß 3.500 g CO₂ pro Fahrzeugkilometer aus. Jetzt 1.500 g.**

Das ist kein Feintuning, das war falsch. 3.500 g/Zug-km entsprechen rund 9,6 kWh pro Zugkilometer —
ein dieselgeführter Fernzug. Eine Berliner U- oder S-Bahn braucht etwa 4 kWh pro Zugkilometer
einschließlich Nebenverbrauchern, und der deutsche Strommix lag 2024 bei 363 g CO₂/kWh (UBA). Das
sind 1.450 g, gerundet 1.500.

Bewusst der Strommix und nicht der Ökostromtarif des Betreibers: das ist die konservative Zahl und
die, die eine Klasse nachrechnen kann.

Es fällt stark ins Gewicht, weil der Fahrplan fährt, ob jemand mitfährt oder nicht. Auf dieser Karte
mit sechs Zuglinien setzt diese eine Zahl den Boden unter jeder Runde:

|  | vorher | jetzt |
| --- | ---: | ---: |
| Fahrplan pro Runde | 5.598 kg | 2.449 kg |
| davon Züge | 97 % | 95 % |
| Anteil an einer 100-%-Auto-Runde | 39 % | 22 % |

Vorher hätte der Fahrplan fast vier Zehntel jeder Runde bestimmt, ohne dass die Klasse daran etwas
ändern kann. Jetzt liegen 78 % in ihrer Hand.

**Der Bus bleibt bei 1.200 g/Bus-km** — das entspricht rund 40 l Diesel auf 100 km und stimmt. Die
Kostenseite (4,50 €/Bus-km, 12 €/Zug-km) ist unverändert: korrigiert wurde ein Emissionsfaktor, kein
Preis.

## 7. Eine zweite Korrektur: abgeschnittene Linien

Eine Linie, deren Kanten nicht durchgehend zusammenhängen, fährt nur so weit, wie sie kann — wurde
aber für ihre **volle** Länge mit CO₂ und Kosten belastet. Gemessen: auf einer Testlinie exakt das
Doppelte, auf der ausgelieferten Karte betrifft es `101` (fährt 4,04 von 6,33 km). Die Fahrzeuge
waren immer ehrlich; nur die Messung war es nicht. Auf dieser Karte macht das 33 kg pro Runde aus.

---

## 8. Eine dritte Korrektur: die Kartendaten

Die Kalibrierung stand auf einer Karte mit kaputten Linien. Was in der Datei stand:

- **Buslinie `100` hatte gar keine Kanten** — vier Haltestellen auf dem Plan, kein Bus, der sie
  anfährt. Brandenburger Tor und der Arbeitsplatz daneben waren damit **überhaupt nicht** mit Bus
  oder Bahn erreichbar: von den 36 Wohnort-Arbeitsplatz-Paaren hatten sechs keine ÖPNV-Verbindung.
- **`101` riss in der Mitte** und fuhr 4,04 von 6,33 km — die beiden fehlenden Kanten lagen in der
  Gegenrichtung derselben Linie.
- **Jede Linie hatte 60 Plätze**, Bus und Bahn gleich. Das ist die 60-Plätze-U-Bahn: 6.400 Menschen
  in 60er-Fahrzeugen zwingen den Fahrplan zu sehr vielen Zusatzfahrten.
- **`U2` fuhr hin sieben und zurück neun Kanten**, hielt also stadtauswärts an zwei Bahnhöfen nicht,
  die sie stadteinwärts anfährt.

Das ist korrigiert: alle zehn Linien sind durchgehend, jede Hin- und Rückrichtung hält an denselben
Bahnhöfen, Busse haben 85 Plätze und Züge 1.000. Gemessen über sechs Seeds, mit den Routen, die der
Router im Browser tatsächlich ausgibt:

| Autoanteil | Runde gesamt vorher | jetzt | Fahrplan vorher | jetzt | ÖPNV-Fahrzeit vorher | jetzt |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 % | 12.552 kg | 13.015 kg | 2.449 kg | 2.864 kg | — | — |
| 75 % | 10.368 kg | 10.003 kg | 2.645 kg | 2.969 kg | 60 min | 40 min |
| 50 % | 7.544 kg | 7.315 kg | 3.245 kg | 2.963 kg | 72 min | 29 min |
| 25 % | 6.681 kg | 5.071 kg | 4.026 kg | 3.054 kg | 78 min | 32 min |
| 0 % | 5.936 kg | 3.191 kg | 4.623 kg | 3.191 kg | 95 min | 41 min |

Drei Dinge daran sind wichtig:

- **Umsteigen lohnt sich jetzt.** Vorher bestrafte die Karte es doppelt: die 60er-Fahrzeuge trieben
  den Fahrplan auf 4.623 kg, und wer aufs Auto verzichten wollte, kam bei sechs von 36 Wegen gar
  nicht an — in der 0-%-Spalte sitzen deshalb vorher elf von 64 Gruppen im Auto, weil ihr Weg
  keine Verbindung hatte: 1.313 kg, die die Klasse nicht vermeiden konnte. Eine Runde ganz ohne Auto kostet jetzt **46 % weniger**.
- **Die Autoseite ändert sich nicht.** 100 % Auto: 10.103 → 10.150 kg (innerhalb der Streuung von
  1,4 %), Fahrzeit 22,5 min und Verspätung 12,4 min in beiden Fällen. Die zusätzlichen Busse auf der
  Straße kosten die Autos nichts messbares, und die acht Straßen, die jetzt Tempo 30 statt des
  Vorgabewerts 50 nennen, liegen auf keinem einzigen Autoweg der Klasse.
- **Der Fahrplan-Boden steigt um 415 kg**, weil mehr Linienkilometer gefahren werden (72,7 → 98,0
  km). Das sind 35,8 % statt 30,6 % einer 8.000-kg-Runde. Am Budget ändert das nichts: durchgehend
  fahren sprengt es weiter, umsteigen bleibt drin — aber der Abstand ist kleiner geworden, und beim
  nächsten Play-Test lohnt ein Blick darauf.

Die Zahlen dieser Tabelle stammen aus einem eigenen Messaufbau (64 Gruppen gleichmäßig über alle
36 Paare, Routen aus `ptRouting.ts` und `pathfinding.ts`) und sind deshalb **nicht** mit denen aus
Abschnitt 2 und 3 mischbar: dort war die Zuordnung der Gruppen zu Paaren eine andere, was dieselbe
Karte etwas weniger stauen lässt. Vergleichbar ist jeweils vorher gegen jetzt in einer Zeile.

---

## 9. Nachgemessen auf der Karte mit acht Versionen

Seit S16 ist die ausgelieferte Karte die mit acht Versionen, die auf dem Server gespielt wird,
repariert. Ihre Basisversion war nie in einer Runde simuliert worden. Gemessen am 01.10.2026 mit
demselben Aufbau wie Abschnitt 8 — 64 Gruppen zu je 100 Menschen gleichmäßig über die 36 Paare,
wer nicht Auto fährt, fährt Bus und Bahn, Routen aus dem Router des Spiels, sechs Seeds:

| Autoanteil | Runde gesamt | Auto | Fahrplan | Fahrzeit Auto | Verspätung | ÖPNV-Fahrzeit | Warten |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 % | 13.059 kg | 10.194 kg | 2.864 kg | 22,5 min | 12,5 min | — | — |
| 75 % | 9.884 kg | 6.903 kg | 2.981 kg | 15,4 min | 5,4 min | 32,5 min | 9,2 min |
| 50 % | 7.184 kg | 4.164 kg | 3.020 kg | 10,6 min | 0,7 min | 33,2 min | 11,6 min |
| 25 % | 5.345 kg | 2.207 kg | 3.139 kg | 10,8 min | 0,1 min | 41,1 min | 19,9 min |
| 0 % | 3.194 kg | — | 3.194 kg | — | — | 43,5 min | 21,9 min |

Die Streuung zwischen den Seeds liegt unter 2 %. In jeder Zeile liegt das Ergebnis innerhalb weniger
Prozent von Abschnitt 8; die 100-%-Zeile trifft dessen Fahrzeit und Verspätung fast genau (22,5 und
12,4 min dort). Der Fahrplan-Boden ist mit 2.864 kg derselbe.

Drei Dinge daran sind neu:

- **Das Budget liegt am Rand seiner Spanne.** Eine Runde, die sich herunterarbeitet — 100 / 75 / 50
  / 50 / 25 / 25 % Autoanteil — kommt über sechs Runden auf **48.001 kg** gegen ein Budget von 48.000.
  Wer durchgehend fährt, ist in Runde 4 raus, nicht in Runde 5. Mit **9.000 kg pro Runde** wäre die
  Geschichte aus Abschnitt 4 wieder da: durchgehend fahren endet in Runde 5, wer umsteigt, behält
  rund sechs Tonnen. Das ist ein Vorschlag, keine Änderung — die Zahl steht in der Kartendatei, und
  der erste Play-Test auf dieser Karte soll sie bestätigen oder verwerfen.
- **Der volle Bus ist die Warteschlange des ÖPNV.** Je mehr umsteigen, desto länger warten sie: von
  9 auf 22 Minuten an der Haltestelle. Das ist Gedränge, nicht die Auswahl der Wege — fahren auf
  allen 36 Paaren nur 25 statt 100 Menschen pro Gruppe Bus und Bahn, bleibt die Wartezeit bei
  7,6 Minuten, bei 42 statt rund 9.400 Abweisungen an der Haltestelle.
- **Der Maßstab hält auch hier.** 16, 8, 4 und 2 Plätze bei 6.400 Pendlern: CO₂ des Autos 10.194,
  10.211, 9.857 und 9.784 kg, Verspätung 12,5 / 12,6 / 11,0 / 12,5 min. Nagelt man die Gruppe auf
  100 Menschen fest, sehen acht Plätze 1,0 statt 12,5 Minuten Verspätung.

`docs/de-hintergrund.md` und `/hintergrund/` zeigen diese Zahlen, als Tabelle und als Abbildung.

---

## 10. Was offen bleibt

- **Die Abfahrten liegen sehr eng beieinander.** `departure_std_dev_min = 10` heißt, dass praktisch
  alle innerhalb von 20 Minuten losfahren; real verteilt sich ein Berufsverkehr über eine Stunde und
  mehr. Bei σ = 45 statt 10 sinkt die Verspätung im 100-%-Auto-Fall von 56,9 auf 16,5 Minuten. Das
  ist eine Modellfrage, keine Kalibrierungsfrage — hier bewusst nicht angefasst.
- **Der Abendverkehr wird nach wie vor nicht simuliert**, und beide Richtungen einer Straße teilen
  sich eine Warteschlange. Solange alle morgens zur Arbeit fahren, ist das egal.
- **Das Budget von Berlin Mitte-West** liegt auf der reparierten Karte am Rand seiner Spanne
  (Abschnitt 9); 9.000 kg pro Runde ist der Vorschlag für den nächsten Play-Test.
- **Die Vorgabewerte anderer Karten sind ungeprüft.** Jede neue Karte startet mit 6.400 und 8.000 —
  den Werten von Berlin Mitte-West. Für eine kleinere Karte sind beide zu hoch. Die Karte sagt
  inzwischen selbst, ob ihre Zahlen gemessen sind (`GameMap.calibrated`, geht mit der JSON-Datei
  mit), und „Spiel anlegen" warnt, solange sie es nicht sind. Gemessen ist damit noch nichts: das
  heißt weiterhin Runden auf der Karte nachspielen (Abschnitt 11), die beiden Zahlen im Admin
  eintragen und dort den Haken setzen. Die mitgelieferte Datei hat ihn gesetzt.

## 11. Nachrechnen

Die Zahlen oben stammen nicht aus einem Play-Test, sondern aus wiederholten Läufen mit festem Seed
auf der ausgelieferten Karte. Wer sie nach einer Modelländerung neu braucht, spielt Runden auf der
betreffenden Karte nach — nicht: dreht an den Werten, bis sich ein Play-Test gut anfühlt. Die
Herleitung mit allen Messwerten steht in `backend/game/calibration.py`; wofür jede Zahl da ist,
steht als Testfall in `backend/game/tests/test_join.py`.
