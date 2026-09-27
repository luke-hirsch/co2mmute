# Kalibrierung: die Zahlen, gegen die gespielt wird

Stand 27.09.2026. Gemessen auf `map_examples/Berlin_Mitte-West.json`, der einzigen Karte, die
jemand spielt.

Zwei Einstellungen entscheiden, ob eine Runde etwas bedeutet: für wie viele Menschen ein Fahrgast
steht, und wie viel CO₂ die Klasse ausgeben darf. Beide waren nie kalibriert. Ausgeliefert wurden
**1000 Menschen pro Fahrgast gegen ein Budget von 500 kg** — auf einer Karte, deren Fahrplan allein
schon 2.449 kg pro Runde ausstößt, bevor irgendwer spielt. Jedes Spiel war nach Runde 1 vorbei.

Das ist jetzt geändert. Was sich geändert hat und warum, steht hier.

---

## 1. Was vorher passiert ist

Ein Auto-Fahrgast legt auf dieser Karte im Schnitt 7,66 km zurück (Luftlinie über den kürzesten
Weg, gemessen über alle 36 Wohnort-Arbeitsplatz-Paare). Bei 1000 Menschen pro Fahrgast sind das
1000 Autos auf einer Strecke. Eine volle Klasse — 16 Plätze, 4 Fahrgäste — schickt also 64.000
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
Pendler unter ihren Fahrgästen auf** — sie erzeugt keine neuen, wenn mehr Schüler kommen. Genau so
rechnet es jetzt:

```
Menschen pro Fahrgast = Pendler des Stadtteils / (Plätze × Fahrgäste pro Platz)
```

Dass das trägt, ist gemessen. Bei konstant 6.400 Pendlern bleibt die Runde dieselbe Runde, egal wie
viele mitspielen:

| Plätze | Fahrgäste | Menschen/Fahrgast | CO₂ Auto | Fahrzeit | Verspätung |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 64 | 100 | 8.691 kg | 20,4 min | 11,3 min |
| 8 | 32 | 200 | 8.630 kg | 20,2 min | 11,0 min |
| 4 | 16 | 400 | 8.904 kg | 20,8 min | 11,4 min |
| 2 | 8 | 800 | 8.652 kg | 20,7 min | 11,5 min |

CO₂ auf ±3 %, Verspätung auf ±0,5 Minuten. Nagelt man stattdessen den Maßstab auf eine feste Zahl,
sieht eine halb besetzte Klasse auf derselben Karte **0,4 Minuten Verspätung statt 11,3** und stößt
44 % des CO₂ aus. Dann hängt das Spiel davon ab, wer zum Unterricht erschienen ist.

Was dabei hätte schiefgehen können — weniger, dafür „dickere" Fahrgäste drängen sich auf weniger
Strecken — passiert nicht: die kürzesten Wege der ganzen Klasse benutzen ohnehin nur **29 der 90
Straßenkanten**. Das liegt an sechs Wohnorten und sechs Arbeitsplätzen, nicht daran, wie viele
Fahrgäste sie sich teilen.

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

Steigt die Hälfte der Klasse um, ist der Stau weg. Das ist physikalisch richtig — Stau ist ein
Schwellenphänomen dicht an der Kapazität — und es ist die Lektion, um die es geht.

## 4. Das Budget gilt pro Runde

Weil die Pendlerzahl konstant ist, kostet eine Runde, was sie kostet — unabhängig davon, wie viele
Schüler spielen. Das Budget braucht deshalb **keinen Fahrgast-Term**, nur die Rundenzahl:

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

## 6. Eine Korrektur, die der Gruppe noch nicht vorlag

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

## 8. Was offen bleibt

- **Der Vorschlag folgt der Klassengröße noch nicht live.** Das Formular „Spiel erstellen" ist
  serverseitig gerendert, die Ableitung passiert also einmal pro Seitenaufruf. Wer die Platzzahl
  ändert, muss die beiden Zahlen von Hand nachziehen. Das gehört in den React-Port des Formulars.
- **Die Abfahrten liegen sehr eng beieinander.** `departure_std_dev_min = 10` heißt, dass praktisch
  alle innerhalb von 20 Minuten losfahren; real verteilt sich ein Berufsverkehr über eine Stunde und
  mehr. Bei σ = 45 statt 10 sinkt die Verspätung im 100-%-Auto-Fall von 56,9 auf 16,5 Minuten. Das
  ist eine Modellfrage, keine Kalibrierungsfrage — hier bewusst nicht angefasst.
- **Der Abendverkehr wird nach wie vor nicht simuliert**, und beide Richtungen einer Straße teilen
  sich eine Warteschlange. Solange alle morgens zur Arbeit fahren, ist das egal.
- **Die Vorgabewerte anderer Karten sind ungeprüft.** Jede neue Karte startet mit 6.400 und 8.000 —
  den Werten von Berlin Mitte-West. Für eine kleinere Karte sind beide zu hoch.

## 9. Nachrechnen

Die Zahlen oben stammen nicht aus einem Play-Test, sondern aus wiederholten Läufen mit festem Seed
auf der ausgelieferten Karte. Wer sie nach einer Modelländerung neu braucht, spielt Runden auf der
betreffenden Karte nach — nicht: dreht an den Werten, bis sich ein Play-Test gut anfühlt. Die
Herleitung mit allen Messwerten steht in `backend/game/calibration.py`; wofür jede Zahl da ist,
steht als Testfall in `backend/game/tests/test_join.py`.
