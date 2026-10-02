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

Was die Doppelung nicht ist: eine Messung des Abends. Er ist heute ein Abbild des Morgens.

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

## 12. Was offen bleibt

- **Die Abfahrten liegen sehr eng beieinander.** `departure_std_dev_min = 10` heißt, dass praktisch
  alle innerhalb von 20 Minuten losfahren; real verteilt sich ein Berufsverkehr über eine Stunde und
  mehr. Bei σ = 45 statt 10 sinkt die Verspätung im 100-%-Auto-Fall von 56,9 auf 16,5 Minuten. Das
  ist eine Modellfrage, keine Kalibrierungsfrage — hier bewusst nicht angefasst.
- **Der Abend ist ein Abbild des Morgens.** Dieselbe Streuung der Abfahrten, dieselbe Spitze:
  `evening_departure_hour` verschiebt in der Simulation nichts, weil die Zeit ab Fensterbeginn läuft.
  Eine eigene Abendspitze wäre eine Modellfrage.
- **Das Budget von Berlin Mitte-West** bleibt bei 16.000 kg pro Runde, obwohl es seit Abschnitt 11
  auch ein Spiel beendet, das sich wie oben verbessert; mit 18.000 bliebe dieses 284 kg darunter.
- **Die Vorgabewerte anderer Karten sind ungeprüft.** Jede neue Karte startet mit 6.400 und 16.000 —
  den Werten von Berlin Mitte-West. Für eine kleinere Karte sind beide zu hoch. Die Karte sagt
  inzwischen selbst, ob ihre Zahlen gemessen sind (`GameMap.calibrated`, geht mit der JSON-Datei
  mit), und „Spiel anlegen" warnt, solange sie es nicht sind. Gemessen ist damit noch nichts: das
  heißt weiterhin Runden auf der Karte nachspielen (Abschnitt 13), die beiden Zahlen im Admin
  eintragen und dort den Haken setzen. Die mitgelieferte Datei hat ihn gesetzt.

## 13. Nachrechnen

Die Zahlen oben stammen nicht aus einem Play-Test, sondern aus wiederholten Läufen mit festem Seed
auf der ausgelieferten Karte. Wer sie nach einer Modelländerung neu braucht, spielt Runden auf der
betreffenden Karte nach — nicht: dreht an den Werten, bis sich ein Play-Test gut anfühlt. Die
Herleitung mit allen Messwerten steht in `backend/game/calibration.py`; wofür jede Zahl da ist,
steht als Testfall in `backend/game/tests/test_join.py`.
