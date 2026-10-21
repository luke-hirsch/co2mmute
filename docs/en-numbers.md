# The model's numbers

Every number the game computes with: what it does in the game, value and unit, source, and where it
lives. The file and the constant's name are given, never a line number: `grep` finds a name.

Two files hold the model's numbers, no others:

- `backend/sim/constants.py` — the value, with its source in the comment beside it.
- `frontend/src/lib/constants.ts` — the copies the browser needs, under the same names.
  `frontend/tests/lib/constants.test.ts` reads the Python file and goes red when a copy disagrees.

Not here: guards and measurement procedure (`PASS_TICK_GUARD`, `SEEDS`, `PER_HOME`, the calibration's
search steps) are machinery, not numbers of the model.

## After you change one

How a number is changed, measured before and after, and kept is in the skill
`.agents/skills/sim-experiment/`. In short:

1. Change the number in `backend/sim/constants.py`, with its source in the comment. If the browser
   reads it, change the same number in `frontend/src/lib/constants.ts`; the test says if one side
   was forgotten.
2. Both golden masters (`backend/game/tests/test_sim_golden.py`) go red on purpose: the model says it
   changed. Regenerate with `GOLDEN_REGENERATE=1` and say so in the commit message.
3. Recalibrate every map (`manage.py calibrate_map <file> … --out`), then set the map's row (commuter
   count, share of the timetable, table). What a running game copied when it was created or
   started stays: the budget (`GameSession.max_CO2_level`), the Gruppe size (`people_per_agent`) and
   the share of the timetable (`timetable_factor`). The map's streets, lines and speeds it reads anew
   each round.
4. Update `docs/kalibrierung.md` and the figures in `docs/de-hintergrund.md` / `docs/en-background.md`
   (and their site copy `backend/template/docs/hintergrund.html`) if the number appears there: search
   for the value.

## Emissions

How much CO₂ a trip costs. A car is one vehicle with one person.

| Constant | Value | What it does | Source |
|---|---|---|---|
| `CAR_EMISSIONS_G_PER_KM` | 166.8 g CO₂e per vehicle-km | A car at 50 km/h. The curve below runs through this point. | a research value whose source was not recorded. For comparison: UBA, TREMOD 6.71B (10/2025), car 2024 at 164 g per person-km with 1.4 persons, upstream included: about 230 g per vehicle-km, a fleet mean over all roads. The figure is falling with the share of electric cars. |
| `BUS_EMISSIONS_G_PER_VEHICLE_KM` | 1200 g per bus-km | A bus emits per kilometre driven, whether anybody rides or not. | about 45 l/100 km × 2.64 kg CO₂/l; Berlin's fleet, BVG in Zahlen 2025; Standardisierte Bewertung 2016+; VBK Karlsruhe |
| `TRAIN_EMISSIONS_G_PER_VEHICLE_KM` | 3630 g per train-km | U-Bahn, S-Bahn and regional train: one value for all three. | 10 kWh per train-km × 363 g/kWh (UBA 2024, grid mix); Standardisierte Bewertung 2016+, S-Bahn Berlin, BVG |
| `TRAM_EMISSIONS_G_PER_VEHICLE_KM` | 1400 g per tram-km | A tram per kilometre driven. | 3.9 kWh per tram-km (Deiters 2009, Tab. 5) × 363 g/kWh, rounded down |
| `BUS_EMISSIONS_G_PER_PERSON_KM` | 90 g per person-km | How full Germany's buses are. Sets the share of the timetable the class pays (`GameMap.timetable_factor`); it prices no trip. | UBA, TREMOD 6.71B (10/2025), "Linienbus, Nahverkehr", 16 % occupancy |
| `TRAM_EMISSIONS_G_PER_PERSON_KM` | 42 g per person-km | the same for tram and U-Bahn | UBA, TREMOD, "Straßen-, Stadt- und U-Bahn", 19 % |
| `TRAIN_EMISSIONS_G_PER_PERSON_KM` | 44 g per person-km | the same for S-Bahn and regional train | UBA, TREMOD, "Eisenbahn, Nahverkehr", 30 % |
| `CAR_EF_ANCHOR_SPEED_KMH` | 50 km/h | The speed at which `CAR_EMISSIONS_G_PER_KM` holds. | — |
| `CAR_EF_MIN_SPEED_KMH` | 70 km/h | The speed at which a car emits least per km; in a jam and above it, more. | COPERT/HBEFA shape of the curve |
| `CAR_EF_DRAG_TERM` | 0.0028605 g·h²/km³ | The curve's air-drag term, `c`. | COPERT/HBEFA shape of the curve |
| `CAR_EF_IDLE_TERM` | derived | `a`, the curve's jam term, computed from `c` and the minimum. | derived |
| `CAR_EF_ROLLING_TERM` | derived | `b`, the rolling term, computed so the curve gives exactly `CAR_EMISSIONS_G_PER_KM` at 50 km/h. | derived |
| `MAX_CAR_EMISSION_FACTOR` | 2.0 (factor) | In a jam the emission rises to at most double; there is no speed floor. | no source |

The browser has the curve too (`frontend/src/lib/map/car-emissions.ts`) so the route search sees the
same cost: `CAR_EMISSIONS_G_PER_KM`, `CAR_EF_ANCHOR_SPEED_KMH`, `CAR_EF_MIN_SPEED_KMH`,
`CAR_EF_DRAG_TERM` and `MAX_CAR_EMISSION_FACTOR` are in `frontend/src/lib/constants.ts`.

## Costs and fare

| Constant | Value | What it does | Source |
|---|---|---|---|
| `CAR_COST_PER_KM` | 0.60 € per km | The full cost of a car kilometre. | ADAC Autokostenübersicht Frühjahr/Sommer 2026: new compact petrol cars 57-67 ct per km (i30 58.3, Ceed 56.9-60.3, Leon 64.7, A3 Sportback 59.8-61.7), five years, 15 000 km a year, depreciation without interest. A new car's depreciation makes that the high side for the cars on the road. Was 0.32 (source not recorded, likely the Pendlerpauschale). |
| `CAR_COST_TRAFFIC_SHARE` | 0.5 | The part of it that rises with traffic (fuel, stop-and-go); the rest is fixed. The fixed part is not what you pay for the trip. | known estimate |
| `BUS_COST_PER_VEHICLE_KM` | 3.94 € per bus-km | What a bus costs per kilometre, full or empty. | Deiters 2009, Tab. 5 (2.82 €), brought to 2025 with the consumer price index (× 1.399) |
| `TRAM_COST_PER_VEHICLE_KM` | 6.25 € per tram-km | the same for a tram | Deiters 2009, Tab. 5 (4.47 €), × 1.399 |
| `TRAIN_COST_PER_VEHICLE_KM` | 13.40 € per train-km | the same for a train, without the track charge | Ramboll 2023: nearly 20 €, a third of it infrastructure |
| `PT_FARE_EUR` | 1.30 € | The ticket per trip. What you pay minus what the trip costs is the subsidy. | a project default, no source |
| `BIKE_COST_PER_KM` | 0.03 € per km | Wear and repairs of the bike. The health benefit is missing; that is an open question for the group. | a project default, no source |

## Streets and capacity

| Constant | Value | What it does | Source |
|---|---|---|---|
| `JAM_DENSITY_VEH_PER_KM_LANE` | 133 vehicles per lane-km | How many cars fit in a kilometre of lane when all is standing (7.5 m each). This is a street's storage: when it is full, the street behind it stops. | no source in the comment |
| `SATURATION_FLOW_VEH_PER_H_LANE` | 1800 vehicles per hour and lane | How many cars a lane lets through per hour. | no source in the comment |
| `BUS_PCU` | 3.0 | A bus takes the room of three cars. | no source |
| `TRAM_PCU` | 5.3 | A tram in the car lane takes the room of 5.3 cars. | 40 m Flexity ÷ 7.5 m per car |
| `BIKE_PCU` | 0.2 | A bike takes a fifth of a car's room. | HCM/HBS |
| `BIKE_SATURATION_FLOW_VEH_PER_H_LANE` | 2000 bikes per hour and lane | Bikes have a budget of their own: a car jam holds no bike, and bikes hold no car. | order of magnitude of a cycle lane |
| `DEADLOCK_TICKS` | 4 ticks | When the first vehicle of a junction has not moved for this long, the junction is gridlocked and one vehicle is let go. | no source |

## Randomness

Drawn once per street and round (capacity) and once per person (desired speed). Nothing is multiplied
by noise afterwards.

| Constant | Value | What it does | Source |
|---|---|---|---|
| `CAPACITY_FACTOR_SIGMA` | 0.14 | How much a street's capacity varies from round to round (standard deviation). Deliberately below the literature: incidents are not modelled. | no source |
| `CAPACITY_FACTOR_CLAMP` | 0.60 to 1.40 | Bounds of that factor, so no capacity is zero or negative. | — |
| `DRIVER_SPEED_SIGMA` | 0.12 | How much people differ in the speed they want (standard deviation). | no source |
| `DRIVER_SPEED_CLAMP` | 0.70 to 1.40 | Bounds of that factor. | — |

## Departures and tick

| Constant | Value | What it does | Source |
|---|---|---|---|
| `TICK_DURATION_MIN` | 5 min | One tick of the simulation. Settable per game, see below. | — |
| `MORNING_DEPARTURE_HOUR` | 9 o'clock | The hour people set off around in the morning. | — |
| `EVENING_DEPARTURE_HOUR` | 17 o'clock | The hour they set off home around. | — |
| `DEPARTURE_STD_DEV_MIN` | 10 min | How widely people spread around that hour (standard deviation). | — |
| `EVENING_DEPARTURE_SPREAD` | 1.6 | The way home spreads this much wider than the way there. Only the ratio is sourced; the spread itself is the game's. | TU Dresden, SrV 2018 Berlin, Tabellenbericht, Tab. 8.2 and 8.2.1 |
| `DEPARTURE_WINDOW_MIN` | 120 min | The window of departures: an hour before to an hour after the departure hour. | follows the ±60 min clamp |

## Fallback speeds

Used when a map or a line states none, for example a game whose map was deleted. A map states its
own, see "Numbers of a map".

| Constant | Value | What it does |
|---|---|---|
| `FALLBACK_WALK_SPEED_KMH` | 5 km/h | on foot |
| `FALLBACK_BIKE_SPEED_KMH` | 20 km/h | bike |
| `FALLBACK_CAR_SPEED_KMH` | 50 km/h | car on a street with no limit |
| `FALLBACK_BUS_SPEED_KMH` | 30 km/h | a bus line without a speed |
| `FALLBACK_TRAIN_SPEED_KMH` | 40 km/h | a train line without a speed |

No source; they are a last resort. The browser's route search uses `FALLBACK_WALK_SPEED_KMH`,
`FALLBACK_BIKE_SPEED_KMH` and `FALLBACK_CAR_SPEED_KMH`.

## Limits in the browser

Only the browser applies them, in `frontend/src/lib/constants.ts`. They have no twin in Python.

| Constant | Value | What it does | Source |
|---|---|---|---|
| `MAX_WALK_M` | 5000 m | Nobody walks further: about an hour. | a project default, no source (2026-09-28) |
| `MAX_BIKE_M` | 15000 m | Nobody bikes further. | a project default, no source |
| `PT_MAX_WALK_DISTANCE_M` | 2000 m | The walk to the first stop and from the last one in the public transport search. | no source |

## The budget

Kilograms of CO₂ per person per round, there and back, the same on every map. The game ends at
budget × the map's commuters × rounds. The dial in the create form:

| Constant | Value | What it does | Source |
|---|---|---|---|
| `CO2_KG_PER_PERSON_NORMAL` | 2.4 kg | A commute inside Germany's 2030 climate target. | UBA Texte 224/2020, Tab. 4 (2.42 kg a trip in 2017) × KSG Anlage 2a (85 of 168 Mt) |
| `CO2_KG_PER_PERSON_STEP` | 0.2 kg | The dial's step. On Berlin, 0.5 kg is about a sixth of the class switching mode. | — |
| `CO2_KG_PER_PERSON_MIN` | 0.6 kg | Lower end, below the round where nobody drives on Berlin (0.72). | — |
| `CO2_KG_PER_PERSON_MAX` | 6.0 kg | Upper end, above the round where everybody drives (3.53). | — |

The same four values are in the browser. And the numbers for a round with no simulation results:

| Constant | Value | What it does | Source |
|---|---|---|---|
| `ESTIMATE_PUBLIC_G_PER_KM` | 60 g per km | Rough estimate for the summary of a round that has no results (rows from before the simulation wrote them). The car takes `CAR_EMISSIONS_G_PER_KM`. | no source, rough |
| `ESTIMATE_BIKE_G_PER_KM` | 18 g per km | the same for the bike | no source, rough |
| `ESTIMATE_PUBLIC_EUR_PER_KM` | 0.15 € per km | the same for public transport's cost | no source, rough |

## Numbers of a map

They belong to the map and are changed there, in the map editor or the admin. The values below are
only what a new row starts with. These places change together:

- `backend/maps/models.py` (`BusLine`, `TrainLine.DEFAULTS`, `GameMap`, `StreetEdge`)
- `backend/mapbuild/transit.py` (`BUS`, `TRAIN`)
- `frontend/src/lib/map/pt-defaults.ts` (`DEFAULT_PT_CAPACITY`, `DEFAULT_PT_SPEED_KMH`)
- `backend/maps/importer.py`: its own numbers for a file that leaves a field out (speeds 5/20/50,
  street 50 km/h, 1 lane, `max_lanes` 2, bus 5 min, 85 seats, 30 km/h; train lines read
  `TrainLine.DEFAULTS`). `max_lanes` is 2 there, 1 in the model.

| Number | Starting value | What it does |
|---|---|---|
| `GameMap.walk_speed_kmh` | 5 km/h | walking speed on this map |
| `GameMap.bike_speed_kmh` | 20 km/h | biking speed |
| `GameMap.default_car_speed_kmh` | 50 km/h | car where a street names no limit |
| `GameMap.district_commuters` | 6800 | How many commuters the map's streets carry in the rush hour. Measured (`calibrate_map`), not chosen. Source: TomTom Traffic Index 2025, 19.0 km/h in the rush hour. |
| `GameMap.timetable_factor` | 1.0 | The share of the timetable the class pays. 1 until measured. |
| `GameMap.co2_table` | — | kg per person per round at each car share; what the budget means on this map. Written by `calibrate_map --out`. |
| `Edge.circuity` | 1.0 | a road's length divided by the straight line |
| `StreetEdge.speed_limit` | 50 km/h | a street's speed limit |
| `StreetEdge.lanes` | 1 | a street's lanes (both directions) |
| `BusLine.bus_capacity`, `bus_speed_kmh`, `intervall` | 85 seats, 30 km/h, 5 min | A bus: size, speed, interval. The order of magnitude of a 12 m bus with standing room, no source. |
| `TrainLine.DEFAULTS` train | 1000 seats, 40 km/h | U-Bahn or S-Bahn. Order of magnitude, no source. |
| `TrainLine.DEFAULTS` tram | 248 seats, 30 km/h | Berlin's 40 m Flexity: 84 seats and 164 standing (Bombardier's datasheet). Speed as the bus (a project default, 2026-10-07): the model has no dwell time. |

How often a line runs comes, when a map is built, from the timetable (DELFI, 8 to 10 o'clock), else
from OSM, else from this table (`DEFAULT_INTERVAL` in `backend/mapbuild/timetable.py`):

| Kind | Interval |
|---|---|
| U-Bahn | 5 min |
| S-Bahn | 10 min |
| regional train | 60 min |
| tram | 15 min |
| bus | 20 min |

These are deliberately project defaults, with no source: a last resort, not a measured value.

## Numbers of a game

The host sets them when creating a game; the form starts at the values in `sim/constants.py`
(`TICK_DURATION_MIN`, `MORNING_DEPARTURE_HOUR`, `EVENING_DEPARTURE_HOUR`, `DEPARTURE_STD_DEV_MIN`,
`CO2_KG_PER_PERSON_NORMAL`). The `GameSession` model's defaults are functions that read these
constants (`backend/game/models.py`), so a change needs no migration. A game copies its map's share
of the timetable when it starts (`GameSession.timetable_factor`), so a recalibrated map never moves
a running game. Class size, Gruppen per person and rounds (`DEFAULT_MAX_PLAYERS` 16,
`DEFAULT_AGENT_PER_PLAYER` 4, `DEFAULT_MAX_ROUNDS` 6 in `backend/game/calibration.py`) are the form's
starting values, not numbers of the model.
