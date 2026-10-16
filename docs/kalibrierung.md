# Kalibrierung: die Zahlen, gegen die gespielt wird

Stand 27.09.2026, ergänzt um den Kartendaten-Durchgang vom selben Tag (Abschnitt 8). Gemessen auf
`map_examples/Berlin_Mitte-West.json`, der einzigen Karte, die jemand spielt.

Zwei Einstellungen entscheiden, ob eine Runde etwas bedeutet: für wie viele Menschen eine Gruppe
steht, und wie viel CO₂ die Klasse ausgeben darf. Beide waren nie kalibriert. Ausgeliefert wurden
**1000 Menschen pro Gruppe gegen ein Budget von 500 kg** — auf einer Karte, deren Fahrplan allein
schon 2.449 kg pro Runde ausstößt, bevor irgendwer spielt. Jedes Spiel war nach Runde 1 vorbei.

Das ist jetzt geändert. Was sich geändert hat und warum, steht hier.

Seit dem 7. Oktober 2026 ist das Budget eine Zahl pro Person und Runde, auf jeder Karte dieselbe, und
die Pendlerzahl ist am gemessenen Berufsverkehr Berlins geeicht (Abschnitt 13). Die Abschnitte davor
sind die Geschichte, in den Zahlen ihrer Zeit.

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
Minuten im freien Fluss. Damals hieß es, der Berufsverkehr in der Berliner Innenstadt laufe mit rund
24 km/h, das wären dieselben 11 Minuten Verspätung. Für die 24 km/h gab es keine Quelle; gemessen
sind 19,0 km/h (TomTom Traffic Index, Abschnitt 13). Geeicht ist die Zahl an einem Wert draußen,
nicht am Spielgefühl — seit Abschnitt 13 an einem mit Quelle.

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

(So bis zum 7. Oktober 2026. Seitdem gilt es pro Person und Runde, Abschnitt 13.)

Weil die Pendlerzahl konstant ist, kostet eine Runde, was sie kostet — unabhängig davon, wie viele
Schüler spielen. Das Budget braucht deshalb **keinen Term für die Gruppengröße**, nur die Rundenzahl:

```
CO₂-Budget = CO₂-Budget der Karte pro Runde × Runden
```

Für diese Karte: **16.000 kg pro Runde, also 96.000 kg für sechs Runden.** Seit dem 1. Oktober 2026
rechnet eine Runde Hin- und Rückweg (Abschnitt 10). Die Rechnung hier und bis Abschnitt 9 ist die
des Hinwegs allein, mit 8.000 kg pro Runde und 48.000 kg für sechs.

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

Seit Abschnitt 13 gehört nur noch die Pendlerzahl zur Karte; `co2_budget_kg_per_round` gibt es nicht
mehr. Eine ältere Datei, die den Schlüssel noch trägt, lässt sich weiter importieren, das Budget
bleibt dabei liegen.

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

Seit dem 28.09.2026 ist die ausgelieferte Karte die mit acht Versionen, die auf dem Server gespielt wird,
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

`docs/de-hintergrund.md` zeigt diese Zahlen, als Tabelle und als Abbildung.

---

## 10. Hin und zurück

Bis hierhin rechnete eine Runde nur den Weg zur Arbeit. Seit dem 1. Oktober 2026 rechnet sie auch den
Heimweg, als zweiten Durchlauf auf einem frischen Netz (`docs/de-hintergrund.md`, „Hin und zurück“).
Jede Gruppe hat dafür eine zweite Route, die der Client mit demselben Verkehrsmittel auf dem
gerichteten Graphen sucht. Auf Berlin Mitte-West ist sie in allen 36 Paaren und allen drei
Verkehrsmitteln der Hinweg andersherum, weil jede Kante ihre Gegenkante hat.

Alles, was eine Runde kostet, fällt damit zweimal an, und der Fahrplan fährt zweimal. Das Budget
musste mit. Es wurde nicht an einem anderen Parameter gedreht, sondern verdoppelt, und die Messung
zeigt, dass das ungefähr stimmt. Gleiches Verfahren wie in Abschnitt 9, 64 Gruppen zu je 100
Menschen, sechs Seeds, Routen aus dem echten Client-Router, am 1. Oktober 2026:

| Autoanteil | Runde gesamt |      Auto | Fahrplan | Fahrzeit Auto hin / zurück | Verspätung hin + zurück |
| ---------: | -----------: | --------: | -------: | -------------------------: | ----------------------: |
|      100 % |    25.614 kg | 19.885 kg | 5.729 kg |             22,5 / 19,8 min |                22,2 min |
|       75 % |    19.626 kg | 13.673 kg | 5.953 kg |             15,4 / 14,3 min |                 9,7 min |
|       50 % |    14.470 kg |  8.337 kg | 6.134 kg |             10,6 / 10,7 min |                 1,5 min |
|       25 % |    10.883 kg |  4.415 kg | 6.468 kg |             10,8 / 10,9 min |                 0,3 min |
|        0 % |     6.582 kg |         — | 6.582 kg |                           — |                       — |

Die Zeilen ohne Rückweg, im selben Lauf gemessen, sind die Tabelle aus Abschnitt 9 auf das Kilogramm
genau (13.059 / 9.884 / 7.184 / 5.345 / 3.194 kg). Das zeigt, dass die Umstellung der Simulation eine
Runde ohne Rückweg nicht verändert hat.

Das Verhältnis zur Runde mit Hinweg allein liegt je nach Autoanteil zwischen 1,96 und 2,06. Die Autoseite
verdoppelt sich auf 2,5 % genau (1,95 bis 2,00). Der Fahrplan-Boden verdoppelt sich, weil der
Fahrplan zweimal fährt, und ein wenig mehr, wo mehr Zusatzfahrten nötig werden. Der Heimweg läuft
auf den Gegenkanten, und jede Kante zieht ihre Kapazität neu; bei 100 % Auto ist er 2,7 Minuten
kürzer als der Hinweg.

**Das Budget liegt weiter am Rand**, jetzt knapp auf der anderen Seite. Wer sich herunterarbeitet
(100 / 75 / 50 / 50 / 25 / 25 %), kommt über sechs Runden auf **95.946 kg** gegen 96.000, vorher 48.001
gegen 48.000. Wer durchgehend fährt, kommt auf 153.684 kg und ist in Runde 4 raus (nach Runde 3 liegt
er bei 76.842, nach Runde 4 bei 102.456 kg). **18.000 kg pro Runde** wäre der Vorschlag für den
nächsten Play-Test, so wie 9.000 vorher: durchgehend fahren endet in Runde 5, wer umsteigt, behält
rund zwölf Tonnen. Die Zahl steht in der Kartendatei.

Was die Doppelung nicht ist: eine Messung des Abends. Er war damals ein Abbild des Morgens; seit dem
16. Oktober 2026 streut er 1,6-mal so breit (Abschnitt 18).

## 11. Die Linien fahren, bis alle zu Hause sind

Bis zum 2. Oktober 2026 fuhr eine Linie nach ihrem Fahrplan nur weiter, solange jemand auf sie wartete
oder in ihr saß. Seitdem fährt jede Linie, solange irgendjemand unterwegs ist, auch wenn niemand
mitfährt (`docs/de-hintergrund.md`, „Der ÖPNV fährt einen Fahrplan“): Busse fahren auch in den
ruhigen Stunden, und die Gesellschaft bezahlt sie.

Gleiches Verfahren wie in Abschnitt 10, am 2. Oktober 2026, mit Hin- und Rückweg. Die Routen sind neu
aus dem Client-Router gezogen, nachdem Bus 100, Stadtbahn und U7 auf die Straßenseite ihrer
Fahrtrichtung gelegt wurden; es sind dieselben Linien, nur die andere Seite der Straße. Vorher ist
das Modell desselben Tages ohne die Regel, nachher mit ihr:

| Autoanteil | Runde vorher | Runde nachher |      Auto | Fahrplan vorher | Fahrplan nachher |
| ---------: | -----------: | ------------: | --------: | --------------: | ---------------: |
|      100 % |    25.360 kg |     26.367 kg | 19.631 kg |        5.729 kg |         6.736 kg |
|       75 % |    19.497 kg |     20.323 kg | 13.530 kg |        5.966 kg |         6.792 kg |
|       50 % |    14.463 kg |     16.174 kg |  8.318 kg |        6.145 kg |         7.856 kg |
|       25 % |    10.879 kg |     14.340 kg |  4.415 kg |        6.464 kg |         9.925 kg |
|        0 % |     6.585 kg |     10.402 kg |         — |        6.585 kg |        10.402 kg |

Die Spalte vorher liegt unter Abschnitt 10, weil seitdem Abbiegespuren, Reißverschluss und Bus 100
auf seiner eigenen Straßenseite dazugekommen sind. Auto, Fahrzeiten und Wartezeiten bewegen sich
durch die Regel nicht. Nur der Fahrplan wird teurer, und am meisten dort, wo am meisten umgestiegen
wird: Mit Bus und Bahn dauert ein Weg 33 bis 44 Minuten, mit dem Auto 11 bis 22, und solange der
letzte Fahrgast unterwegs ist, fahren alle zwölf Linien. Ohne Auto fahren auf dem Hinweg 154 Busse
und Züge mehr als der Fahrplan, vorher 31. Niemand bleibt stehen, in keinem der gemessenen Fälle.

Nur der Hinweg, im selben Lauf: 13.326 / 10.247 / 8.036 / 7.118 / 5.151 kg, vorher 12.865 / 9.826 /
7.191 / 5.340 / 3.194 kg. Das ist die Tabelle in `docs/de-hintergrund.md`.

**Das Budget trennt die beiden Spiele nicht mehr.** Wer durchgehend fährt, kommt auf 158.201 kg und
ist in Runde 4 raus. Wer sich herunterarbeitet (100 / 75 / 50 / 50 / 25 / 25 %), kommt auf
**107.716 kg**, 11.716 kg über 96.000, vorher 95.541. Mit **18.000 kg pro Runde**, 108.000 für sechs,
endet durchgehend Fahren in Runde 5, und wer umsteigt, bleibt 284 kg darunter. **Die Karte behält
16.000** (entschieden am 2. Oktober 2026): Wer alle sechs Runden schaffen will, muss früher umsteigen
als die Klasse oben. Die Zahl steht in der Kartendatei.

## 12. Eine Regel für jede Karte

Bis hierhin sind die beiden Zahlen von Berlin Mitte-West von Hand gefunden, in Messreihen, die für
jede Frage neu gebaut wurden. Für jede weitere Karte gilt eine Regel, einmal pro Karte gemessen:

- **Pendler:** so viele, dass ein Morgen, an dem alle Auto fahren, so langsam ist wie der
  Berufsverkehr der echten Stadt. Das Tempo der Stadt kommt von außen, mit Quelle.
- **Budget pro Runde:** was eine Runde mit Hin- und Rückweg kostet, wenn die Hälfte der Gruppen Auto
  fährt und die andere Hälfte Bus und Bahn, auf zwei Stellen gerundet.
- **Der Anteil ist der Schwierigkeitsregler:** bei 40 % Auto wird das Budget knapper, bei 60 %
  großzügiger.

Seit Abschnitt 13 ist das Budget keine Zahl der Karte mehr. Die Pendler sucht der Befehl wie hier,
danach misst er, was das Budget pro Person auf der Karte reicht:

```
./manage.py calibrate_map karte.json --speed 19          # Pendler suchen, dann die Tabelle
./manage.py calibrate_map karte.json --commuters 6800    # Pendler behalten, nur die Tabelle
            [--seeds 6] [--map-version …] [--out neu.json]
```

Er prüft die Datei zuerst mit `check_map`, lädt sie in eine Datenbank, die danach wieder verschwindet,
und spielt echte Runden mit der Simulation des Spiels. Die Wege sucht der Router des Spiels
(`frontend/scripts/routes.mjs`, dafür braucht es Node und `npm ci` in `frontend/`): jeder Wohnort zu
jedem Arbeitsplatz und zurück, so wie der Rundenbildschirm sie zuerst anbietet. Die Gruppen verteilen
sich gleichmäßig auf die Paare, auf Berlin Mitte-West 72 Gruppen, zwei pro Paar. Bei einem
Autoanteil fährt jedes Paar seinen Anteil, bei der Hälfte also genau eine der beiden Gruppen. Eine
zufällige Hälfte aller Gruppen setzt in einer Runde die langen Wege ins Auto und in der nächsten die
kurzen: Auf Berlin streute die halbe Runde damit um 4 % zwischen den Seeds, mit festem Anteil pro
Paar um 0,5 %. Die Pendler sucht der Befehl in ganzen Menschen pro Gruppe. `--out` schreibt eine Kopie
der Datei mit der Pendlerzahl und `calibrated: true`.

Gemessen wird auf Postgres (`DJANGO_DB=postgres`), wie auf dem Server; nur dort spielen die Prozesse
die Runden eines Schritts nebeneinander. Die Simulation liest Strecken, Linien und Wege in der
Reihenfolge ihrer Nummern, nicht ihrer Namen, denn die sortiert jede Datenbank anders. So kommt
dieselbe Runde unter SQLite und unter Postgres gleich heraus.

Auf Berlin Mitte-West, gemessen am 5. Oktober 2026 auf Postgres, sechs Seeds, 6.400 Pendler:

| Autoanteil | Runde gesamt |      Auto |  Fahrplan | Fahrzeit Auto hin / zurück | Bus & Bahn | Warten |
| ---------: | -----------: | --------: | --------: | -------------------------: | ---------: | -----: |
|      100 % |    26.542 kg | 19.578 kg |  6.964 kg |            22,2 / 19,5 min |          — |      — |
|       75 % |    20.481 kg | 13.835 kg |  6.645 kg |            15,9 / 14,6 min |   31,4 min | 20,3 min |
|       50 % |    15.854 kg |  8.555 kg |  7.299 kg |            11,3 / 11,1 min |   32,7 min | 23,4 min |
|       25 % |    13.062 kg |  4.212 kg |  8.850 kg |            10,2 / 10,3 min |   37,5 min | 33,2 min |
|        0 % |    10.163 kg |         — | 10.163 kg |                          — |   41,9 min | 41,9 min |

- **Das Budget ist die Regel.** Die halbe Runde kostet 15.854 kg, gerundet 16.000, die Zahl, die die
  Karte trägt. Mit dem Aufbau aus Abschnitt 11, einer festen zufälligen Hälfte, waren es 16.174 kg.
- **Die Pendlerzahl ist es nicht ganz.** Bei 6.400 Pendlern fahren alle Autos morgens 20,7 km/h,
  nicht die 24 km/h, mit denen bis dahin gerechnet wurde. Mit 24 km/h ergibt die Regel 5.700 Pendler
  und ein Budget von 14.000 kg (die halbe Runde: 14.168 kg). Die 24 km/h hatten aber keine Quelle,
  und die Karte trug weiter 6.400 und 16.000 — bis Abschnitt 13.
- **Die Suche findet zurück.** Mit 20,8 km/h als Ziel kommt sie bei 6.400 Pendlern an.

Mit Abschnitt 11 ist die Tabelle nur Zeile für Zeile ungefähr vergleichbar (ohne Auto 10.163 gegen
10.402 kg): Der Aufbau ist ein anderer, 72 Gruppen und auf jedes Paar gleich viele statt 64, die auf
36 Paare nicht aufgehen.

## 13. Das Budget pro Person

Seit dem 7. Oktober 2026 ist das Budget keine Zahl der Karte mehr, sondern eine pro Person und Runde,
auf jeder Karte dieselbe:

```
CO₂-Budget = kg pro Person und Runde × Pendler der Karte × Runden
```

Warum. Ein Budget, das an jeder Karte selbst gemessen ist, lässt jede Stadt gleich schwer aussehen.
Pro Person ist eine Stadt mit langen Wegen oder wenig Bus und Bahn von selbst schwerer, und das ist
die Lektion, kein Fehler. Pro Karte gemessen wird nur noch die Pendlerzahl.

**Die Pendlerzahl.** Die 24 km/h aus Abschnitt 3 hatten keine Quelle. Die Quelle ist jetzt der
TomTom Traffic Index mit den Daten von 2025 (15. Ausgabe, Januar 2026): Berlin, Stadtgebiet,
**19,0 km/h im morgendlichen Berufsverkehr, 58,7 % Stau** — eine Fahrt dauert 58,7 % länger als bei
freier Fahrt. `calibrate_map --speed 19` findet auf Berlin Mitte-West **6.800 Pendler**: Bei 6.840
fahren alle Autos morgens 19,1 km/h, bei 6.912 schon 18,9.

Zwei Dinge sagt diese Zahl nicht:

- **Sie zählt keine Menschen.** TomTom misst den Verkehr, während der Rest der Stadt schon in der
  U-Bahn und auf dem Rad sitzt. Die 6.800 sind die Autonachfrage, die auf diesem Graphen den
  Berufsverkehr ergibt, wenn alle fahren — ein Anker mit einer Regel, keine Zahl aus der Statistik.
  Mit Berlins echter Verkehrsmittelwahl zu eichen, geht nicht: Die Karte hat mehr Busse und weniger
  Schiene als die Stadt.
- **Sie steht für etwas, das fehlt.** Das Modell hat keine Ampeln, seine freie Fahrt ist das
  Tempolimit, 46,1 km/h (TomToms Berlin fährt nachts um 30). Wer das Tempo trifft, lässt den Stau für
  die Ampeln mitstehen: Fahren alle Auto, dauert ein Weg 23,7 Minuten, 2,4-mal so lang wie bei
  freier Fahrt; in der Stadt ist es das 1,59-fache. Auf das Stauniveau statt auf das Tempo geeicht,
  29 km/h auf der freien Fahrt des Modells, wären es 4.800 Pendler gewesen. Entschieden ist das
  Tempo.

**Was eine Runde pro Person kostet.** Gemessen am 7. Oktober 2026 auf Postgres, sechs Seeds, 6.800
Pendler, Hin- und Rückweg (`calibrate_map --speed 19`). Pro Person heißt: die Runde geteilt durch
die 6.800 Pendler, so wie das Budget sie zählt.

| Autoanteil | pro Person | Runde gesamt |      Auto |  Fahrplan | Fahrzeit Auto hin / zurück | Bus & Bahn |   Warten |
| ---------: | ---------: | -----------: | --------: | --------: | -------------------------: | ---------: | -------: |
|      100 % |    4,17 kg |    28.379 kg | 21.080 kg |  7.299 kg |            23,7 / 22,4 min |          — |        — |
|       75 % |    3,16 kg |    21.498 kg | 14.773 kg |  6.725 kg |            16,8 / 15,4 min |   31,9 min | 20,6 min |
|       50 % |    2,41 kg |    16.420 kg |  9.122 kg |  7.299 kg |            11,6 / 11,7 min |   32,9 min | 24,0 min |
|       25 % |    1,96 kg |    13.340 kg |  4.449 kg |  8.890 kg |            10,2 / 10,3 min |   38,4 min | 34,8 min |
|        0 % |    1,53 kg |    10.402 kg |         — | 10.402 kg |                          — |   43,1 min | 44,2 min |

**Normal: 2,4 kg.** Die halbe Runde kostet 2,41 kg pro Person, auf den Schritt des Reglers gerundet
2,4. Das ist ab jetzt eine feste Zahl für alle Karten, einmal auf Berlin gemessen, ein Anker
(`CO2_KG_PER_PERSON_NORMAL` in `backend/game/calibration.py`). Auf Berlin Mitte-West reicht sie, wenn
49 % der Gruppen Auto fahren; für jede neue Karte sagt `calibrate_map`, welcher Anteil es dort ist.

**Der Regler.** „Spiel anlegen“ bietet 1,0 bis 6,0 kg in Schritten von 0,2. Der Schritt ist so fein,
weil auf Berlin 0,5 kg etwa ein Viertel der Klasse ist, das umsteigt. Unter 1,53 kg ist auf Berlin
keine Runde zu schaffen, über 4,17 kg jede. Das Spiel speichert, mit wie viel Kilo es gespielt wurde
(`GameSession.co2_kg_per_person`), und rechnet das Budget daraus: 2,4 × 6.800 × 6 = **97.920 kg** für
sechs Runden, bisher 96.000.

**Pendler der Karte, nicht Menschen auf der Karte.** Menschen pro Gruppe sind ganze Menschen: 106 ×
64 Gruppen sind 6.784, nicht 6.800. Gerechnet wird mit den Pendlern der Karte. Solange die Zahl
abgeleitet ist, macht das kaum etwas aus. Überschreibt aber jemand die Menschen pro Gruppe, um eine
Runde leichter zu machen, darf das Budget nicht mitschrumpfen: Der Fahrplan fährt, ob jemand
einsteigt oder nicht, und ein Budget aus zwanzig Menschen wäre vom Fahrplan allein in der ersten
Runde aufgebraucht.

**Die beiden Spiele.** Wer durchgehend Auto fährt, ist in Runde 4 raus. Wer sich herunterarbeitet
(100 / 75 / 50 / 50 / 25 / 25 %), kommt auf 109.397 kg, 16,09 kg pro Person, und überschreitet die
97.920 in der letzten Runde — wie seit Abschnitt 11. Mit 2,8 kg käme diese Klasse durch. Normal ist
trotzdem die halbe Runde, nicht das zweite Spiel.

**Was sich geändert hat.** `GameMap.co2_budget_kg_per_round` ist weg, Export und Import kennen es
nicht mehr. `calibrated` heißt jetzt: Die Pendlerzahl ist gemessen. `calibrate_map` sucht die
Pendler wie bisher und zeigt danach die Tabelle pro Person und den Anteil, den normal auf der Karte
kauft; `--share` gibt es nicht mehr. Die mitgelieferte Karte trägt 6.800. Eine Karte, die schon auf
einem Server liegt, behält ihre Zahl, bis sie neu importiert oder im Admin geändert wird — die
Migration ändert nur die Vorgabe.

## 14. Die Tram

Eine Tram ist eine Bahnlinie, die von Straßenbahnen gefahren wird (`TrainLine.kind`). Ob sie im Stau
steht, hängt an ihrem Gleis, nicht an ihr: Liegt es in der Autospur, wie auf der Friedrichstraße
nördlich des Bahnhofs, wo die M1 und die 12 fahren, steht sie mit den Autos in der Schlange und die
Autos hinter ihr. Hat sie ein eigenes Gleis, fährt sie frei, wie in der Mitte der Landsberger Allee.
„Eigenes Gleis" nimmt wie die Busspur eine Spur weg (`StreetEdge.tram_track`).

Ihre Zahlen, jede mit Quelle:

| Zahl         | Wert             | woher                                                                                      |
| ------------ | ---------------- | ------------------------------------------------------------------------------------------ |
| Plätze       | 248              | Flexity Berlin, 40 m: 84 Sitz- und 164 Stehplätze bei 4 Personen/m² (Bombardier)           |
| Tempo        | 30 km/h          | wie der Bus; BVG 2025: Tram 17,1, Bus 17,9 km/h, beide mit Halten und Verkehr (BVG in Zahlen) |
| CO₂          | 1.400 g/Tram-km  | 3,9 kWh/km einer 240-Platz-Niederflurtram (Bremen 2010, Deiters 2009, Tab. 5) × 363 g/kWh  |
| Kosten       | 6,25 €/Tram-km   | Tram 4,47 € je Fahrzeug-km (Deiters 2009, Tab. 5) × 1,399 Preisindex 2009 → 2025 (Abschnitt 17); war 7,10 € |
| Pkw-Einheiten | 5,3             | 40 m Tram ÷ 7,5 m je Auto im Stau (133 Fz/km und Spur)                                     |

Die Quellen für den Strom reichen von 2,76 kWh/km (Standardisierte Bewertung 2016, eine 30-m-Tram)
bis 4,55 kWh/km (die ganze Flotte der Wiener Linien 2012, Heizung eingeschlossen), also von 1.000
bis 1.650 g. Das Tempo der schnellsten Berliner Linien, rund 20 km/h (Senat, Drucksache 19/25552),
war der erste Vorschlag; neben dem Bus mit 30 machte es jede Tram langsamer als jeden Bus. Die 30 des
Busses lassen die Halte aus, weil das Modell keine Haltezeit kennt, und eine Tram fährt in der Spitze
schneller als ein Bus.

Gemessen auf der ausgelieferten Karte, sechs Seeds, normal, 6.800 Pendler:

- **Eine M1 von Hegelplatz über die Georgenstraße zum Friedrichstadtpalast** fährt leer. Vom
  S-Bahnhof Friedrichstraße geht man die 400 m zu Fuß, und kein Auto nimmt die beiden Straßen.
- **Die 101 als Tram** (Bundesallee bis Lessingstraße, Gleis in der Autospur) trägt bei 20 km/h
  1.128 Menschen pro Runde statt 1.692 als Bus, bei 30 km/h alle 1.692. Die Autos dort fahren bei
  normal 48 km/h, ein Stau, der die Tram aufhält, entsteht nicht. 5,3 oder 3 Pkw-Einheiten machen
  keinen messbaren Unterschied.
- **Dieselbe Tram auf eigenem Gleis** nimmt jeder der zweispurigen Straßen eine Spur: die Autos dort
  fallen auf 28 km/h, eine Autofahrt dauert 22,5 statt 11,6 Minuten, die Runde kostet 2,63 statt
  2,39 kg pro Person. Das eigene Gleis lohnt sich nur, wo die Straße schon im Stau steht.

Die ausgelieferte Karte hat keine Tram; beide Golden Masters bleiben, wie sie waren.

## 15. Große Karten: jede Runde zieht ihre Paare

Eine aus OpenStreetMap gebaute Karte hat viele Wohnorte und viele Arbeitsorte: der Ausschnitt von
Berlin Mitte-West 31 und 49, ganz Berlin 236 und 220. Spielt jede Runde jedes Paar, trägt jedes Paar
mindestens einen ganzen Menschen, auf ganz Berlin also mindestens 51.920 Pendler — mehr, als die
Regel dort findet. Und die Suche geht in Schritten von einem Menschen pro Gruppe, auf dem Ausschnitt
von 1.519 Pendlern, 8 %: Bei 18.228 fahren alle Autos 30,1 km/h, bei 19.747 stehen sie (3,2 km/h).
19 km/h liegt dazwischen und wird nie gemessen; der Befehl antwortet 18.000.

Darum zieht eine Runde auf so einer Karte ihre Paare, wie ein Spiel sie austeilt: Jeder Wohnort
spielt in jeder Runde, mit `--per-home` Arbeitsorten, für jeden Seed neu gezogen. Die Arbeitsorte
werden gemischt und reihum ausgeteilt, so dass jeder gleich oft drankommt (höchstens einmal mehr) und
kein Wohnort einen doppelt hat. Über die Seeds kommt jeder Wohnort zu jedem Arbeitsort, im Mittel
also dasselbe wie jedes Paar. Bei einem Autoanteil fährt jeder Wohnort seinen Anteil. Es bleiben
mindestens 64 Gruppen, eine volle Klasse. Ohne `--per-home` zieht jeder Wohnort vier: Die Tabelle
unten zeigt, dass vier nicht mehr streuen als sieben oder vierzehn, und sie suchen in den feinsten
Schritten. Spielt ein Wohnort ohnehin jeden Arbeitsort, bleibt alles wie in Abschnitt 12 — auf der
ausgelieferten Karte (sechs Wohnorte, sechs Arbeitsorte) braucht die volle Klasse elf pro Wohnort,
mehr als es gibt. Wer jedes Paar spielen will, gibt `--per-home` so groß, wie die Karte Arbeitsorte
hat.

```
./manage.py calibrate_map karte.json --speed 19
./manage.py calibrate_map karte.json --speed 19 --per-home 8
```

Was das Ziehen kostet, gemessen am 13. Oktober 2026 auf dem Ausschnitt (31 Wohnorte, 49 Arbeitsorte,
nur Autos, also fahren bei jedem Anteil alle), Postgres, zwölf Seeds, bei jeder Größe genau
dieselben Menschen auf der Karte:

| Arbeitsorte pro Wohnort | Gruppen | 12.152 Pendler: alle im Auto | kg pro Person | 18.228 Pendler: alle im Auto | kg pro Person | Sekunden pro Seed |
| ----------------------: | ------: | ---------------------------: | ------------: | ---------------------------: | ------------: | ----------------: |
|                       4 |     124 |              37,1 ± 1,8 km/h |  2,05 ± 3,3 % |              25,8 ± 8,0 km/h |  2,20 ± 3,9 % |                14 |
|                       7 |     217 |              36,3 ± 2,5 km/h |  2,06 ± 3,4 % |              23,9 ± 9,3 km/h |  2,19 ± 5,0 % |                18 |
|                      14 |     434 |              36,7 ± 1,5 km/h |  2,09 ± 2,2 % |              24,2 ± 9,9 km/h |  2,24 ± 3,5 % |                28 |
|                      28 |     868 |              36,6 ± 1,1 km/h |  2,08 ± 1,0 % |             11,9 ± 12,8 km/h |  2,23 ± 1,3 % |                48 |
|            alle 49 Paare |   1.519 |              36,6 ± 1,1 km/h |  2,08 ± 0,3 % |              23,6 ± 9,7 km/h |  2,22 ± 1,2 % |                86 |

(± ist die Streuung zwischen den Seeds, nicht der Fehler des Mittels; die Kalibrierung mittelt über
sechs.)

- **Ruhig kostet das Ziehen wenig.** Bei 12.152 Pendlern streut das Tempo um höchstens gut einen
  km/h mehr als die Simulation von selbst, das kg pro Person um 1 bis 3 % statt 0,3 %. Die Mittel
  liegen innerhalb von 1,5 % beieinander.
- **Kurz vor dem Kippen streut die Simulation selbst.** Bei 18.228 Pendlern und jedem Paar stehen an
  zwei von zwölf Seeds alle (4,2 und 4,9 km/h), an einem fahren sie 16 km/h, an den übrigen neun 27
  bis 32. Mit sieben gezogenen Arbeitsorten ist es dasselbe Bild (2,9 und 8,4 km/h, sonst 21 bis
  35). Das Ziehen ändert daran nichts.
- **Die Zeit wächst mit den Gruppen.** Eine Runde dauert etwa proportional zu den Gruppen, die sie
  spielt.

Kalibriert mit sieben gezogenen Arbeitsorten und sechs Seeds (`--speed 19 --per-home 7`, 13 Minuten)
sucht der Befehl in Schritten von 217 Pendlern, 1,1 %, und findet den Rand: 18.662 Pendler fahren im
Mittel der sechs Seeds 27,2 km/h, 19.096 nur noch 16,2. Auf zwei Stellen gerundet sind beide 19.000,
und die Tabelle spielt 19.096 — jenseits des Randes. 19 km/h liegt auf dieser Karte genau dort, wo
sie kippt (Abschnitt 18).

Ein Schritt der Suche ist ein Mensch pro Gruppe. Weniger Gruppen heißt also feinere Schritte, und
mehr Gruppen heißt weniger Streuung durch das Ziehen.

Ganz Berlin (236 Wohnorte, 220 Arbeitsorte) mit acht gezogenen Arbeitsorten und sechs Seeds
(`--speed 19 --per-home 8`): 3 Stunden 11 Minuten, davon gut eine halbe Stunde für die 51.920
Wege, 3,4 GB Speicher. 1.888 Gruppen, also Schritte von 1.888 Pendlern, 5 %. Gemessen, im Mittel
der sechs Seeds: 35.872 Pendler 20,5 km/h, 37.760 38,5, 39.648 15,7, 43.424 14,9. Mehr Pendler
fahren hier nicht immer langsamer, und 19 km/h trifft keine Zahl; der Befehl antwortet 38.000, wo
alle 38,5 km/h fahren. Je Seed ist es auf Berlin nicht gemessen; auf dem Ausschnitt waren es Seeds,
an denen alles stand. Bei 60.416 Pendlern kommen an zwei der sechs Seeds rund 2.750 Menschen nach
1.000 Takten, 83 Stunden, nicht an, und die Sperre der Simulation bricht den Hinweg ab.

**Was da kippt, ist ein Kreisverkehr** (gemessen am 15. und 16. Oktober 2026). Steht eine gebaute
Karte, steht ein Ring: auf dem Ausschnitt die fünf Kanten des Ernst-Reuter-Platzes, 68 bis 101 m
lang, auf ganz Berlin dazu der Moritzplatz, drei einspurige Kanten. Wer einfuhr, nahm den Platz auf
dem Ring so oft wie der Ring selbst, bis jede Kante voll war mit Autos, die auf die nächste wollten,
und nur noch die Sperre gegen das Verklemmen bewegte sie, ein Auto je Kante alle 20 Minuten. Seitdem
hat der Ring Vorfahrt, auf `roundabout` und `circular` gleich (Hintergrund, „Die
Mindestgeschwindigkeit“). Alle im Auto, sechs Seeds: Auf dem Ausschnitt fährt Seed 106 bei 20.000
Pendlern 22,5 km/h und ist nach 145 Minuten durch, vorher 2,6 km/h in 1.505 Minuten; die anderen
fünf liegen höchstens 0,6 km/h neben dem, was sie waren. Die Suche ist eine Kurve ohne Kante und antwortet 23.000
bei 19,2 km/h, vorher 20.000 bei 10,1. Ganz Berlin bei 38.704: 37,1 bis 39,7 km/h auf allen Seeds,
vorher 4,8 bis 39,4. Nur `roundabout`, die StVO beim Wort, ließe den Ernst-Reuter-Platz stehen: Er
ist `circular`. Die ausgelieferte Karte hat keinen Ring, ihre Zahlen bleiben.

## 16. Der Anteil am Fahrplan

Seit dem 15. Oktober 2026 bezahlen die Pendler einen Anteil am Fahrplan, CO₂ und Kosten, nicht mehr
den ganzen.

**Warum.** Die Linien einer Karte fahren den Fahrplan ihrer Stadt, gemacht für deren Millionen. Die
Pendler der Karte sind die Autonachfrage, die den Berufsverkehr ergibt (Abschnitt 13), ein paar
Tausend: auf den aus OpenStreetMap gebauten Karten 1 bis 4 % der Einwohner, auf ganz Berlin 38.000
von 3,6 Millionen. Allein in Bus und Bahn bezahlten sie die Plätze mit, auf denen in der Stadt andere
sitzen. Der leere Fahrplan kostete auf ganz Berlin 2,02 kg pro Person und Runde, 84 % von normal, und
keine Runde war zu schaffen. Auf Berlin Mitte-West kam ein Personenkilometer mit Bus und Bahn bei
50 % Auto auf 144 g; das Umweltbundesamt rechnet für Deutschland 90 g im Bus, 42 g in Tram und
U-Bahn, 44 g im Nahverkehrszug. Das Ticket von 1,30 € deckte 17 % dessen, was eine Fahrt kostete.

**Die Regel.**

```
Anteil = Personenkilometer der Mitfahrenden × g pro Personenkilometer beim Umweltbundesamt
         ÷ CO₂ des Grundfahrplans
```

gemessen in der Runde, in der die Hälfte der Gruppen Auto fährt, über alle Seeds, auf zwei Stellen,
höchstens 1. Der Grundfahrplan ist der Fahrplan im Abfahrtsfenster, hin und zurück, ohne die Fahrten
danach. Mit dem Anteil malgenommen wird jeder Fahrzeugkilometer, CO₂ und Kosten: die Anteile der
Mitfahrenden, die Linien, die niemand benutzt hat, und die Fahrten nach dem Fahrplan. Eine Karte, deren
Linien lange nach dem Fahrplan fahren, weil Leute an vollen Haltestellen warten, bleibt deshalb
teuer. Die Runde ändert der Anteil nicht, nur die Rechnung, und das Ticket bleibt das Ticket.
Höchstens 1, weil die Pendler sonst mehr bezahlten, als die Busse ausstoßen, wenn sie voller fahren
als im deutschen Mittel.

`calibrate_map` misst ihn, schreibt ihn mit `--out` in die Datei (`timetable_factor`), und er geht mit
Export und Import mit. Eine Karte, die niemand gemessen hat, bezahlt den ganzen Fahrplan; wer eine
Karte baut, kann den Anteil im Admin setzen. Ein Spiel übernimmt ihn, wenn es beginnt
(`GameSession.timetable_factor`): Wird die Karte neu gemessen, während jemand auf ihr spielt, bleibt
dessen Spiel, wie es war.

**Die Quelle.** Umweltbundesamt, TREMOD 6.71B (10/2025), „Vergleich der durchschnittlichen Emissionen
einzelner Verkehrsmittel im Personenverkehr in Deutschland 2024", mit der Vorkette, Strom im
deutschen Mix:

| Modus | pro Personenkilometer | Zeile beim Umweltbundesamt   | Auslastung |
| ----- | --------------------: | ---------------------------- | ---------: |
| Bus   |                  90 g | Linienbus, Nahverkehr        |       16 % |
| Tram  |                  42 g | Straßen-, Stadt- und U-Bahn  |       19 % |
| Zug   |                  44 g | Eisenbahn, Nahverkehr        |       30 % |

Eine U-Bahn steht dort in der Zeile der Tram, zwei Gramm daneben; eine Zuglinie sagt im Spiel nicht,
welche sie ist (`sim/constants.py`). Der Faktor pro Fahrzeugkilometer hebt sich in der gemessenen
Runde heraus: Der Grundfahrplan kostet dort, was die Mitfahrenden beim Umweltbundesamt ausstoßen, was
auch immer pro Zugkilometer dasteht.

**Verworfen** wurde ein Anteil über die Einwohner: der Fahrplan der Karte × Pendler ÷ Einwohner ÷
(Fahrplan der Karte ÷ Fahrplan des ganzen Gebiets), pro Person das, was Bus und Bahn im Gebiet pro
Einwohner ausstoßen, 41 bis 53 g. Gegen das Umweltbundesamt kam ein Personenkilometer damit auf 7 g,
und das Ticket bezahlte das Dreifache dessen, was die Fahrt kostete: Es verteilt den Fahrplan über
alle Einwohner, als säßen alle in den zwei Stunden in Bus und Bahn. Es brauchte die Einwohner und den
Fahrplan des ganzen Gebiets dazu, und für Callenberg gab es keine Fläche, auf der beides stand.

**Auf Berlin Mitte-West: 0,48.** Bei 50 % Auto stoßen die Mitfahrenden, Bus und Bahn so voll wie in
Deutschland, 2.725 kg aus, der Grundfahrplan 5.729 kg. Gemessen am 15. Oktober 2026 auf Postgres,
sechs Seeds, 6.800 Pendler, Hin- und Rückweg (`calibrate_map --commuters 6800`); der Fahrplan ist der
Anteil, den die Pendler bezahlen:

| Autoanteil | pro Person | Runde gesamt |      Auto | Fahrplan | Fahrzeit Auto hin / zurück | Bus & Bahn |   Warten |
| ---------: | ---------: | -----------: | --------: | -------: | -------------------------: | ---------: | -------: |
|      100 % |    3,62 kg |    24.584 kg | 21.080 kg | 3.503 kg |            23,7 / 22,4 min |          — |        — |
|       75 % |    2,65 kg |    18.023 kg | 14.773 kg | 3.250 kg |            16,8 / 15,4 min |   31,6 min | 19,9 min |
|       50 % |    1,86 kg |    12.625 kg |  9.122 kg | 3.503 kg |            11,6 / 11,7 min |   33,4 min | 24,6 min |
|       25 % |    1,28 kg |     8.717 kg |  4.449 kg | 4.267 kg |            10,2 / 10,3 min |   38,8 min | 35,7 min |
|        0 % |    0,73 kg |     4.993 kg |         — | 4.993 kg |                          — |   43,4 min | 44,9 min |

Mit dem Anteil kostet eine Fahrt mit Bus und Bahn rund 3,60 € statt 7,65 €, und das Ticket deckt
36 % davon; die Landesgutachten des VDV kamen 2024 auf 21 bis 30 % (Rheinland-Pfalz,
Schleswig-Holstein, Mecklenburg-Vorpommern). Gemessen an einem Seed unter SQLite, nachgerechnet,
nicht gesucht.

**Normal bleibt 2,4 kg und hat jetzt eine Quelle.** Es war die halbe Runde auf Berlin Mitte-West
(2,41 kg, Abschnitt 13); die kostet jetzt 1,86. Statt einer neuen Messung eine Zahl von außen: was
Deutschlands Klimaziel für 2030 einem Arbeitsweg lässt. Ein Arbeitsweg stieß 2017 im Mittel 2,42 kg
CO₂ aus (Umweltbundesamt, Texte 224/2020, „CO₂-Fußabdrücke im Alltagsverkehr", Tab. 4, aus
„Mobilität in Deutschland 2017" und TREMOD, mit der Vorkette), hin und zurück 4,84 kg. Das
Klimaschutzgesetz gibt dem Verkehr für 2030 85 Mio. t (Anlage 2a, Fassung vom 15. Juli 2024; die
Sektoren sind seitdem nicht mehr einzeln verbindlich, die Mengen stehen noch da); 2017 stieß er
168 Mio. t aus (Umweltbundesamt). Um so viel gekürzt, bleiben einem Pendler am Tag 2,45 kg, auf den
Schritt des Reglers 2,4. Es ist ein Mittel über Deutschland, lange Wege eingeschlossen — Arbeitswege
über 50 km sind 5 % der Wege und 30 % ihres CO₂ (ebd., Tab. 11) —, eine Stadt ist deshalb von selbst
leichter als das Mittel.

Auf Berlin Mitte-West reicht normal jetzt, wenn 67 % der Gruppen Auto fahren. Wer durchgehend fährt,
ist in Runde 4 raus (4 × 24.584 kg = 98.336 kg gegen 97.920). Wer sich herunterarbeitet
(100 / 75 / 50 / 50 / 25 / 25 %), kommt auf 85.291 kg, 12,54 kg pro Person gegen 14,4, und kommt
durch.

**Der Regler** geht jetzt von 0,6 bis 6,0 kg. Er soll unter die Runde reichen, in der niemand Auto
fährt, damit sich ein Spiel unschaffbar stellen lässt, und die kostet auf Berlin Mitte-West jetzt
0,73 kg; mit 1,0 als unterstem Wert ging das nicht mehr.

## 17. Der Zug, noch einmal

Abschnitt 6 setzte den Zug von 3.500 g auf 1.500 g. Die Begründung, eine Berliner U- oder S-Bahn
brauche „etwa 4 kWh" pro Zugkilometer, hatte keine Quelle. Gemessen an Quellen ist sie zu niedrig:
4 kWh braucht eine einzelne Einheit, so viel wie eine 40-m-Tram. Ein ganzer Zug in der Spitze braucht
mehr:

| Quelle | kWh je Zugkilometer |
| --- | ---: |
| Regionalzug, Triebwagen und vier Wagen (Standardisierte Bewertung 2016+, Blatt 7-4, Prognose 2030) | 9,04 |
| S-Bahn Berlin, 390 GWh im Jahr durch 27,9 Mio. Zugkm 2024 (abgeleitet, mit Heizung und Nebenverbrauchern) | rund 14 |
| BVG, 454,6 GWh Strom 2025 durch 20,3 + 21,5 Mio. Zugkm (Obergrenze: der Strom speist auch E-Busse, Bahnhöfe, Höfe) | höchstens 10,9 |

Jetzt gilt **ein Wert für U-, S- und Regionalbahn: 10 kWh × 363 g/kWh = 3.630 g/Zug-km.** Auch der
frühere Wert von 3.500 g war also nicht der dieselgeführte Fernzug, für den wir ihn hielten.

Mit dem Zug ändern sich zwei Kosten, beide mit Quelle:

- **Zug 13,40 € je Zugkilometer** (vorher 12 €): knapp 20 € Produktionskosten (Ramboll 2023) ohne
  das Drittel Trassenentgelt (33 %, Tabelle 5). Das Auto trägt in diesem Spiel keine Infrastruktur,
  der Zug deshalb auch nicht. Der Zuschuss der Berliner S-Bahn allein liegt bei mindestens 17 €.
- **Bus 3,94 €, Tram 6,25 €** (vorher 4,50 € und 7,10 €): Deiters' 2,82 € und 4,47 € von 2009, mal
  dem Verbraucherpreisindex 2025 durch 2009. 2009 steht bei 92,2 (Basis 2015), 2025 bei 121,9
  (Basis 2020), 2020 bei 105,8 (Basis 2015): 121,9 × 105,8 / 100 / 92,2 = 1,399. Der Index misst alle
  Preise, nicht Löhne und Energie im Nahverkehr.

Der Bus bleibt bei 1.200 g. Das sind rund 45 l auf 100 km, nicht 40: 55 % der BVG-Busse sind
Gelenk- oder 15-m-Busse, die Standardisierte Bewertung rechnet 0,32 l/km für einen Solobus und
0,44 l/km für einen Gelenkbus.

Die Zahlen aus den Abschnitten 9 bis 16 (Fahrplan pro Runde, Anteil am Fahrplan, die Tabelle der
Budgets) sind mit 1.500 g gemessen. Mit 3.630 g steigt der Fahrplan jeder Karte mit Zuglinien, und
`timetable_factor` und `co2_table` sind neu zu messen.

## 18. Was offen bleibt

- **Die Abfahrten liegen sehr eng beieinander.** `departure_std_dev_min = 10` heißt, dass praktisch
  alle innerhalb von 20 Minuten losfahren; real verteilt sich ein Berufsverkehr über eine Stunde und
  mehr. Bei σ = 45 statt 10 sinkt die Verspätung im 100-%-Auto-Fall von 56,9 auf 16,5 Minuten. Das
  ist eine Modellfrage, keine Kalibrierungsfrage — hier bewusst nicht angefasst.
- **Der Abend streut 1,6-mal so breit wie der Morgen** (SrV 2018 Berlin, Hintergrund „Hin und
  zurück"), sonst ist er der Morgen: `evening_departure_hour` verschiebt in der Simulation nichts,
  weil die Zeit ab Fensterbeginn läuft.
- **Der Anteil am Fahrplan steht für Mitfahrende, die es nicht gibt.** Er rechnet, als säßen in Bus und
  Bahn so viele, wie in Deutschland im Mittel mitfahren; in der Simulation sitzen dort nur die
  Pendler der Karte, die Busse sind nicht voller (Abschnitt 16). Gemessen ist er an der Runde, in der
  die Hälfte Auto fährt, mit den Zahlen des Umweltbundesamts für Deutschland; eine Karte im Ausland
  bekommt dieselben.
- **Die gebauten Karten haben ihren Anteil noch nicht.** Gemessen ist er auf Berlin Mitte-West
  (Abschnitt 16); der Ausschnitt aus OpenStreetMap, Bremen, Callenberg und ganz Berlin bekommen ihn
  mit dem nächsten Lauf von `calibrate_map`.
- **Keine Ampeln.** Die Pendlerzahl trifft das Tempo des Berufsverkehrs, und der Stau steht dabei
  für die Ampeln mit, die das Modell nicht hat (Abschnitt 13).
- **Die Vorgabe anderer Karten ist ungeprüft.** Jede neue Karte startet mit 6.800 Pendlern, der Zahl
  von Berlin Mitte-West. Für eine kleinere Karte ist das zu viel, und mit den Pendlern das Budget. Die
  Karte sagt selbst, ob ihre Zahl gemessen ist (`GameMap.calibrated`, geht mit der JSON-Datei mit),
  und „Spiel anlegen" warnt, solange sie es nicht ist. `calibrate_map` misst sie (Abschnitt 12),
  `--out` setzt den Haken in der Datei. Die mitgelieferte Datei hat ihn gesetzt.
- **Die gebauten Karten kippen an keinem Kreisverkehr mehr** (Abschnitt 15), und eine Schleife aus
  Straßen verklemmt sich am Abend nicht mehr. Auf dem Ausschnitt, bei 23.000 Pendlern und alle im
  Auto, stand an einem von sechs Seeds der Heimweg 4.070 Minuten auf 16 Kanten in Mitte, jede auf die
  nächste wartend, an der viele Arbeitsorte liegen: Wer dort losfuhr, nahm jeden Platz, den die
  Sperre frei machte. Seit wer losfährt den Verkehr auf der Straße zuerst lässt und der Abend
  breiter streut (16. Oktober 2026), ist jeder der sechs Heimwege nach höchstens 155 Minuten zu Ende;
  eine der beiden Regeln allein ließ die Schleife (870 Minuten) oder eine andere (640) stehen.

## 19. Nachrechnen

Die Zahlen oben stammen nicht aus einem Play-Test, sondern aus wiederholten Läufen mit festem Seed
auf der ausgelieferten Karte. Wer sie nach einer Modelländerung neu braucht, spielt Runden auf der
betreffenden Karte nach, mit `calibrate_map` (Abschnitt 12) — nicht: dreht an den Werten, bis sich
ein Play-Test gut anfühlt. Die
Herleitung mit allen Messwerten steht in `backend/game/calibration.py`; wofür jede Zahl da ist,
steht als Testfall in `backend/game/tests/test_join.py` und `test_calibration.py`.
