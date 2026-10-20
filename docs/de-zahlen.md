# Die Zahlen des Modells

Jede Zahl, die das Spiel rechnet: was sie im Spiel tut, Wert und Einheit, Quelle, und wo sie steht.
Die Datei und der Name der Konstante stehen dabei, keine Zeilennummer: `grep` findet den Namen.

Zwei Dateien halten die Zahlen des Modells, sonst keine:

- `backend/sim/constants.py` — der Wert, mit seiner Quelle im Kommentar daneben.
- `frontend/src/lib/constants.ts` — die Kopien, die der Browser braucht, unter denselben Namen.
  `frontend/tests/lib/constants.test.ts` liest die Python-Datei und wird rot, wenn eine Kopie nicht
  mehr stimmt.

Was nicht hier steht: Wächter und Messverfahren (`PASS_TICK_GUARD`, `SEEDS`, `PER_HOME`, die
Suchschritte der Kalibrierung) sind Technik, keine Zahlen des Modells.

## Nach einer Änderung

1. Die Zahl in `backend/sim/constants.py` ändern, mit Quelle im Kommentar. Braucht der Browser sie,
   dieselbe Zahl in `frontend/src/lib/constants.ts`; der Test sagt, wenn eine Seite vergessen wurde.
2. Die beiden Golden Masters (`backend/game/tests/test_sim_golden.py`) werden absichtlich rot: das
   Modell sagt, dass es sich geändert hat. Mit `GOLDEN_REGENERATE=1` neu schreiben und das in der
   Commit-Nachricht sagen.
3. Jede Karte neu kalibrieren (`manage.py calibrate_map <Datei> … --out`), dann die Zeile der Karte
   setzen (Pendlerzahl, Anteil am Fahrplan, Tabelle). Was ein laufendes Spiel beim Anlegen oder
   Start kopiert hat, bleibt: Budget (`GameSession.max_CO2_level`), Gruppengröße (`people_per_agent`)
   und Fahrplananteil (`timetable_factor`). Straßen, Linien und Tempi der Karte liest es dagegen jede
   Runde neu.
4. `docs/kalibrierung.md` und die Zahlen in `docs/de-hintergrund.md` / `docs/en-background.md` (und
   ihre Seitenkopie `backend/template/docs/hintergrund.html`) nachziehen, wenn die Zahl dort vorkommt:
   den Wert suchen.

## Emissionen

Wie viel CO₂ eine Fahrt kostet. Ein Auto ist ein Fahrzeug mit einer Person.

| Konstante | Wert | Was sie tut | Quelle |
|---|---|---|---|
| `CAR_EMISSIONS_G_PER_KM` | 166,8 g CO₂e je Fahrzeug-km | Ein Auto bei 50 km/h. Die Kurve unten läuft durch diesen Punkt. | keine Quelle im Kommentar |
| `BUS_EMISSIONS_G_PER_VEHICLE_KM` | 1200 g je Bus-km | Ein Bus stößt je gefahrenem Kilometer aus, ob jemand mitfährt oder nicht. | ca. 45 l/100 km × 2,64 kg CO₂/l; Berliner Flotte BVG in Zahlen 2025; Standardisierte Bewertung 2016+; VBK Karlsruhe |
| `TRAIN_EMISSIONS_G_PER_VEHICLE_KM` | 3630 g je Zug-km | U-, S- und Regionalbahn: ein Wert für alle drei. | 10 kWh je Zug-km × 363 g/kWh (UBA 2024, Strommix); Standardisierte Bewertung 2016+, S-Bahn Berlin, BVG |
| `TRAM_EMISSIONS_G_PER_VEHICLE_KM` | 1400 g je Tram-km | Eine Tram je gefahrenem Kilometer. | 3,9 kWh je Tram-km (Deiters 2009, Tab. 5) × 363 g/kWh, abgerundet |
| `BUS_EMISSIONS_G_PER_PERSON_KM` | 90 g je Personen-km | Wie voll Deutschlands Busse sind. Bestimmt, welchen Anteil des Fahrplans die Klasse bezahlt (`GameMap.timetable_factor`); berechnet keine Fahrt. | UBA, TREMOD 6.71B (10/2025), „Linienbus, Nahverkehr“, 16 % Auslastung |
| `TRAM_EMISSIONS_G_PER_PERSON_KM` | 42 g je Personen-km | dasselbe für Tram und U-Bahn | UBA, TREMOD, „Straßen-, Stadt- und U-Bahn“, 19 % |
| `TRAIN_EMISSIONS_G_PER_PERSON_KM` | 44 g je Personen-km | dasselbe für S-Bahn und Regionalzug | UBA, TREMOD, „Eisenbahn, Nahverkehr“, 30 % |
| `CAR_EF_ANCHOR_SPEED_KMH` | 50 km/h | Die Geschwindigkeit, bei der `CAR_EMISSIONS_G_PER_KM` gilt. | — |
| `CAR_EF_MIN_SPEED_KMH` | 70 km/h | Bei dieser Geschwindigkeit stößt ein Auto je km am wenigsten aus; im Stau und darüber mehr. | COPERT/HBEFA-Form der Kurve |
| `CAR_EF_DRAG_TERM` | 0,0028605 g·h²/km³ | Der Luftwiderstand der Kurve, `c`. | COPERT/HBEFA-Form der Kurve |
| `CAR_EF_IDLE_TERM` | abgeleitet | `a`, der Stau-Anteil der Kurve, aus `c` und dem Minimum berechnet. | abgeleitet |
| `CAR_EF_ROLLING_TERM` | abgeleitet | `b`, der Rollanteil, so berechnet, dass bei 50 km/h genau `CAR_EMISSIONS_G_PER_KM` herauskommt. | abgeleitet |
| `MAX_CAR_EMISSION_FACTOR` | 2,0 (Faktor) | Im Stau steigt der Ausstoß höchstens auf das Doppelte; eine Mindestgeschwindigkeit gibt es nicht. | keine Quelle |

Der Browser kennt die Kurve auch (`frontend/src/lib/map/car-emissions.ts`), damit die Routensuche
dieselben Kosten sieht: `CAR_EMISSIONS_G_PER_KM`, `CAR_EF_ANCHOR_SPEED_KMH`, `CAR_EF_MIN_SPEED_KMH`,
`CAR_EF_DRAG_TERM` und `MAX_CAR_EMISSION_FACTOR` stehen in `frontend/src/lib/constants.ts`.

## Kosten und Fahrkarte

| Konstante | Wert | Was sie tut | Quelle |
|---|---|---|---|
| `CAR_COST_PER_KM` | 0,32 € je km | Die Vollkosten eines Autokilometers. | keine Quelle im Kommentar |
| `CAR_COST_TRAFFIC_SHARE` | 0,5 | Der Teil davon, der mit dem Verkehr steigt (Sprit, Stop-and-go); der Rest ist fest. Der feste Teil zählt nicht zu dem, was du für die Fahrt zahlst. | bekannte Schätzung |
| `BUS_COST_PER_VEHICLE_KM` | 3,94 € je Bus-km | Was ein Bus je Kilometer kostet, ob besetzt oder leer. | Deiters 2009, Tab. 5 (2,82 €), mit dem Verbraucherpreisindex auf 2025 (× 1,399) |
| `TRAM_COST_PER_VEHICLE_KM` | 6,25 € je Tram-km | dasselbe für eine Tram | Deiters 2009, Tab. 5 (4,47 €), × 1,399 |
| `TRAIN_COST_PER_VEHICLE_KM` | 13,40 € je Zug-km | dasselbe für einen Zug, ohne Trassenentgelt | Ramboll 2023: knapp 20 €, davon 33 % Infrastruktur |
| `PT_FARE_EUR` | 1,30 € | Die Fahrkarte je Fahrt. Was du zahlst minus was die Fahrt kostet ist der Zuschuss. | Vorgabe des Projekts, ohne Quelle |
| `BIKE_COST_PER_KM` | 0,03 € je km | Verschleiß und Reparatur des Rads. Der Nutzen für die Gesundheit fehlt noch; das ist eine offene Frage an die Gruppe. | Vorgabe des Projekts, ohne Quelle |

## Straßen und Kapazität

| Konstante | Wert | Was sie tut | Quelle |
|---|---|---|---|
| `JAM_DENSITY_VEH_PER_KM_LANE` | 133 Fahrzeuge je Spur-km | So viele Autos passen in einen Kilometer Spur, wenn alles steht (7,5 m je Auto). Das ist der Speicher einer Straße: ist er voll, hält die Straße dahinter an. | keine Quelle im Kommentar |
| `SATURATION_FLOW_VEH_PER_H_LANE` | 1800 Fahrzeuge je Stunde und Spur | So viele Autos lässt eine Spur je Stunde durch. | keine Quelle im Kommentar |
| `BUS_PCU` | 3,0 | Ein Bus nimmt so viel Platz wie drei Autos. | keine Quelle |
| `TRAM_PCU` | 5,3 | Eine Tram im Autostreifen nimmt so viel Platz wie 5,3 Autos. | 40 m Flexity ÷ 7,5 m je Auto |
| `BIKE_PCU` | 0,2 | Ein Rad nimmt ein Fünftel eines Autos ein. | HCM/HBS |
| `BIKE_SATURATION_FLOW_VEH_PER_H_LANE` | 2000 Räder je Stunde und Spur | Räder haben ein eigenes Durchlassbudget: ein Autostau hält kein Rad auf, und Räder halten kein Auto auf. | Größenordnung einer Radspur |
| `DEADLOCK_TICKS` | 4 Takte | Rührt sich der erste Wagen eines Knotens so lange nicht, ist der Knoten verklemmt, und ein Wagen wird freigelassen. | keine Quelle |

## Zufall

Gezogen wird einmal je Straße und Runde (Kapazität) und einmal je Person (Wunschtempo). Nichts wird
nachträglich mit Rauschen multipliziert.

| Konstante | Wert | Was sie tut | Quelle |
|---|---|---|---|
| `CAPACITY_FACTOR_SIGMA` | 0,14 | Wie unterschiedlich die Kapazität einer Straße von Runde zu Runde ausfällt (Standardabweichung). Bewusst unter dem Wert der Literatur: Unfälle werden nicht modelliert. | keine Quelle |
| `CAPACITY_FACTOR_CLAMP` | 0,60 bis 1,40 | Grenzen dieses Faktors, damit keine Kapazität null oder negativ wird. | — |
| `DRIVER_SPEED_SIGMA` | 0,12 | Wie unterschiedlich schnell Leute fahren wollen (Standardabweichung). | keine Quelle |
| `DRIVER_SPEED_CLAMP` | 0,70 bis 1,40 | Grenzen dieses Faktors. | — |

## Abfahrten und Takt

| Konstante | Wert | Was sie tut | Quelle |
|---|---|---|---|
| `TICK_DURATION_MIN` | 5 min | Ein Takt der Simulation. Je Spiel einstellbar, siehe unten. | — |
| `MORNING_DEPARTURE_HOUR` | 9 Uhr | Um diese Stunde fahren die Leute morgens los. | — |
| `EVENING_DEPARTURE_HOUR` | 17 Uhr | Um diese Stunde fahren sie abends zurück. | — |
| `DEPARTURE_STD_DEV_MIN` | 10 min | Wie breit die Leute um diese Stunde streuen (Standardabweichung). | — |
| `EVENING_DEPARTURE_SPREAD` | 1,6 | Der Heimweg streut so viel breiter als der Hinweg. Nur das Verhältnis ist belegt, die Streuung selbst ist die des Spiels. | TU Dresden, SrV 2018 Berlin, Tabellenbericht, Tab. 8.2 und 8.2.1 |
| `DEPARTURE_WINDOW_MIN` | 120 min | Das Fenster der Abfahrten: eine Stunde vor bis eine Stunde nach der Abfahrtsstunde. | folgt der Begrenzung auf ±60 min |

## Fallback-Geschwindigkeiten

Wenn eine Karte oder eine Linie keine nennt, etwa bei einem Spiel, dessen Karte gelöscht wurde. Eine
Karte nennt ihre eigenen, siehe „Zahlen einer Karte“.

| Konstante | Wert | Was sie tut |
|---|---|---|
| `FALLBACK_WALK_SPEED_KMH` | 5 km/h | zu Fuß |
| `FALLBACK_BIKE_SPEED_KMH` | 20 km/h | Rad |
| `FALLBACK_CAR_SPEED_KMH` | 50 km/h | Auto ohne Tempolimit |
| `FALLBACK_BUS_SPEED_KMH` | 30 km/h | eine Buslinie ohne Tempo |
| `FALLBACK_TRAIN_SPEED_KMH` | 40 km/h | eine Zuglinie ohne Tempo |

Keine Quelle; sie gelten nur als letzter Ausweg. Der Browser rechnet bei der Routensuche mit
`FALLBACK_WALK_SPEED_KMH`, `FALLBACK_BIKE_SPEED_KMH` und `FALLBACK_CAR_SPEED_KMH`.

## Obergrenzen im Browser

Nur der Browser wendet sie an, in `frontend/src/lib/constants.ts`. Sie haben keine Entsprechung in
Python.

| Konstante | Wert | Was sie tut | Quelle |
|---|---|---|---|
| `MAX_WALK_M` | 5000 m | Weiter läuft niemand: etwa eine Stunde. | Vorgabe des Projekts, ohne Quelle (2026-09-28) |
| `MAX_BIKE_M` | 15000 m | Weiter fährt niemand Rad. | Vorgabe des Projekts, ohne Quelle |
| `PT_MAX_WALK_DISTANCE_M` | 2000 m | Der Weg zur ersten und von der letzten Haltestelle in der ÖPNV-Suche. | keine Quelle |

## Das Budget

Kilogramm CO₂ je Person und Runde, hin und zurück, auf jeder Karte gleich. Das Spiel endet bei Budget
× Pendler der Karte × Runden. Der Regler im Anlege-Formular:

| Konstante | Wert | Was sie tut | Quelle |
|---|---|---|---|
| `CO2_KG_PER_PERSON_NORMAL` | 2,4 kg | Eine Fahrt zur Arbeit innerhalb von Deutschlands Klimaziel 2030. | UBA Texte 224/2020, Tab. 4 (2,42 kg je Fahrt 2017) × KSG Anlage 2a (85 von 168 Mt) |
| `CO2_KG_PER_PERSON_STEP` | 0,2 kg | Schrittweite des Reglers. Auf Berlin ist 0,5 kg etwa ein Sechstel der Klasse, die das Verkehrsmittel wechselt. | — |
| `CO2_KG_PER_PERSON_MIN` | 0,6 kg | Untere Grenze, unter der Runde ohne Auto auf Berlin (0,72). | — |
| `CO2_KG_PER_PERSON_MAX` | 6,0 kg | Obere Grenze, über der Runde, in der alle fahren (3,53). | — |

Dieselben vier Werte stehen im Browser. Zusätzlich gibt es Zahlen für Fälle ohne Simulationsergebnis:

| Konstante | Wert | Was sie tut | Quelle |
|---|---|---|---|
| `ESTIMATE_PUBLIC_G_PER_KM` | 60 g je km | Grobe Schätzung für die Zusammenfassung einer Runde, die keine Ergebnisse hat (Zeilen aus der Zeit vor der Simulation). Das Auto nimmt `CAR_EMISSIONS_G_PER_KM`. | keine Quelle, grob |
| `ESTIMATE_BIKE_G_PER_KM` | 18 g je km | dasselbe für das Rad | keine Quelle, grob |
| `ESTIMATE_PUBLIC_EUR_PER_KM` | 0,15 € je km | dasselbe für die Kosten des ÖPNV | keine Quelle, grob |

## Zahlen einer Karte

Sie gehören zur Karte und werden dort geändert, im Karteneditor oder im Admin. Die Werte unten sind
nur, womit eine neue Zeile beginnt. Diese Stellen ändern sich zusammen:

- `backend/maps/models.py` (`BusLine`, `TrainLine.DEFAULTS`, `GameMap`, `StreetEdge`)
- `backend/mapbuild/transit.py` (`BUS`, `TRAIN`)
- `frontend/src/lib/map/pt-defaults.ts` (`DEFAULT_PT_CAPACITY`, `DEFAULT_PT_SPEED_KMH`)
- `backend/maps/importer.py`: eigene Zahlen für eine Datei, die ein Feld weglässt (Tempi 5/20/50,
  Straße 50 km/h, 1 Spur, `max_lanes` 2, Bus 5 min, 85 Plätze, 30 km/h; die Zuglinien lesen
  `TrainLine.DEFAULTS`). `max_lanes` ist dort 2, im Modell 1.

| Zahl | Anfangswert | Was sie tut |
|---|---|---|
| `GameMap.walk_speed_kmh` | 5 km/h | Tempo zu Fuß auf dieser Karte |
| `GameMap.bike_speed_kmh` | 20 km/h | Tempo mit dem Rad |
| `GameMap.default_car_speed_kmh` | 50 km/h | Auto, wo die Straße kein Limit nennt |
| `GameMap.district_commuters` | 6800 | Wie viele Pendler die Straßen der Karte im Berufsverkehr verkraften. Wird gemessen (`calibrate_map`), nicht gewählt. Quelle: TomTom Traffic Index 2025, 19,0 km/h im Berufsverkehr. |
| `GameMap.timetable_factor` | 1,0 | Welchen Anteil des Fahrplans die Klasse bezahlt. 1, bis gemessen. |
| `GameMap.co2_table` | — | kg je Person und Runde bei jedem Autoanteil; was das Budget auf dieser Karte bedeutet. Schreibt `calibrate_map --out`. |
| `Edge.circuity` | 1,0 | Länge der Straße geteilt durch die Luftlinie |
| `StreetEdge.speed_limit` | 50 km/h | Tempolimit einer Straße |
| `StreetEdge.lanes` | 1 | Spuren einer Straße (beide Richtungen) |
| `BusLine.bus_capacity`, `bus_speed_kmh`, `intervall` | 85 Plätze, 30 km/h, 5 min | Ein Bus: Größe, Tempo, Takt. Größenordnung eines 12-m-Busses mit Stehplätzen, keine Quelle. |
| `TrainLine.DEFAULTS` Zug | 1000 Plätze, 40 km/h | U- oder S-Bahn. Größenordnung, keine Quelle. |
| `TrainLine.DEFAULTS` Tram | 248 Plätze, 30 km/h | Berlins 40-m-Flexity: 84 Sitz- und 164 Stehplätze (Bombardier-Datenblatt). Tempo wie der Bus (Vorgabe des Projekts, 2026-10-07): das Modell hat keine Haltezeit. |

Wie oft eine Linie fährt, kommt beim Bau einer Karte aus dem Fahrplan (DELFI, 8 bis 10 Uhr), sonst aus
OSM, sonst aus dieser Tabelle (`DEFAULT_INTERVAL` in `backend/mapbuild/timetable.py`):

| Art | Takt |
|---|---|
| U-Bahn | 5 min |
| S-Bahn | 10 min |
| Regionalzug | 60 min |
| Tram | 15 min |
| Bus | 20 min |

Das sind bewusst Vorgaben des Projekts, ohne Quelle: ein letzter Ausweg, kein belegter Wert.

## Zahlen eines Spiels

Der Host stellt sie beim Anlegen ein; das Formular beginnt bei den Werten aus `sim/constants.py`
(`TICK_DURATION_MIN`, `MORNING_DEPARTURE_HOUR`, `EVENING_DEPARTURE_HOUR`, `DEPARTURE_STD_DEV_MIN`,
`CO2_KG_PER_PERSON_NORMAL`). Die Standardwerte des Modells `GameSession` sind Funktionen, die diese
Konstanten lesen (`backend/game/models.py`); eine Änderung braucht deshalb keine Migration. Ein
Spiel kopiert den Fahrplananteil seiner Karte beim Start (`GameSession.timetable_factor`), damit eine
neu kalibrierte Karte kein laufendes Spiel verschiebt. Klassengröße, Gruppen je Person und Runden
(`DEFAULT_MAX_PLAYERS` 16, `DEFAULT_AGENT_PER_PLAYER` 4, `DEFAULT_MAX_ROUNDS` 6 in
`backend/game/calibration.py`) sind die Anfangswerte des Formulars, keine Zahlen des Modells.
