"""
Every number of the model, and the two curves that read off them.

This file and `frontend/src/lib/constants.ts` are the only places a number of
the model is written down; the frontend test `tests/lib/constants.test.ts` fails
when a copy there disagrees with this file. Nothing here imports Django: these
are numbers about roads, cars and a game's clock, not about the database, and
keeping them importable without a settings module is what lets the engine be
tested and calibrated as a script.

Per-map numbers (a street's lanes and speed, a line's seats) are the map's data
and are edited in the editor or the admin; their defaults for new rows are in
`maps/models.py`. The guards of the engine (tick limit, seeds, search steps) are
machinery and stay where they are used.
"""

import random

# Emission factors. These are the only ones: the game's database carries none.
CAR_EMISSIONS_G_PER_KM = 166.8  # g CO2e per vehicle-km (1 person = 1 vehicle)
# A city bus: ~45 l/100 km x 2.64 kg CO2/l = 1188 g, rounded to 1200. Berlin's
# fleet is 55 % articulated or 15 m (838 of 1532, BVG in Zahlen 2025). The
# Standardisierte Bewertung 2016+ has 0.32 l/km for a 12 m solo bus and 0.44 for
# an articulated one; Karlsruhe's VBK reports 111 and 138 kg CO2 per 100 km
# (42 and 52 l/100 km at 2.64 kg/l, 2012).
BUS_EMISSIONS_G_PER_VEHICLE_KM = 1200.0  # g CO2e per bus-km
# An electric U-, S- or regional train as it runs at rush hour: 10 kWh per
# train-km times the German grid mix of 363 g CO2/kWh (UBA, 2024) = 3630 g. Not
# the operator's own green tariff: the grid mix is the conservative figure and
# the one a class can check. One constant for all three kinds, the middle of:
#   - a regional set of one motor coach and four coaches, 9.04 kWh/km
#     (Standardisierte Bewertung 2016+, Blatt 7-4, "DoSto ETZ", 2030 forecast);
#   - S-Bahn Berlin, about 14 kWh per train-km: ~390 GWh a year over 27.9 M
#     train-km in 2024 (derived; heating and auxiliaries included);
#   - BVG, at most 10.9 kWh per U-Bahn or tram train-km: 454.6 GWh bought in
#     2025 over 20.3 + 21.5 M train-km (an upper bound, the GWh also feed
#     e-buses, stations and depots).
# The 4 kWh this used to carry was one unit, 40 m of tram, not a train. It was
# 3500 before the first calibration and 1500 afterwards; neither was sourced.
# It matters more than it looks: the timetable runs whether anyone rides it or
# not, so on a map with six train lines this number alone sets the floor under
# every round.
TRAIN_EMISSIONS_G_PER_VEHICLE_KM = 3630.0  # g CO2e per train-km
# A low-floor tram of 30 to 40 m: 3.9 kWh per tram-km, the figure Bremen's
# 240-place trams drew in 2010 (Deiters 2009, Tab. 5, with the Standardisierte
# Bewertung's own rates beside it), times the same 363 g CO2/kWh as the train.
# 1416 g, rounded down to 1400. The sources span 2.76 kWh (Standardisierte
# Bewertung 2016, a 30 m car) to 4.55 (Wiener Linien's whole fleet in 2012,
# heating and all); Berlin's Flexity is a 40 m car with 248 places.
TRAM_EMISSIONS_G_PER_VEHICLE_KM = 1400.0  # g CO2e per tram-km

# What a person-km by bus and train emits in Germany, at the occupancy the
# country's buses and trains actually run at: Umweltbundesamt, TREMOD 6.71B
# (10/2025), "Vergleich der durchschnittlichen Emissionen einzelner
# Verkehrsmittel im Personenverkehr in Deutschland 2024", g CO2e per person-km
# with the energy's upstream chain, electricity at the German grid mix. Bus:
# "Linienbus, Nahverkehr", 90 g at 16 % occupancy. Tram: "Straßen-, Stadt- und
# U-Bahn", 42 g at 19 %. Train: "Eisenbahn, Nahverkehr", 44 g at 30 % — the
# S-Bahn and the regional train; a U-Bahn is in the tram's row, two grams
# apart, and a train line here does not say which it is.
# Not what a ride emits in the game: a line emits per vehicle-km above, however
# full. These say how much of that the class pays, `GameMap.timetable_factor`,
# which `calibrate_map` measures with them.
BUS_EMISSIONS_G_PER_PERSON_KM = 90.0
TRAM_EMISSIONS_G_PER_PERSON_KM = 42.0
TRAIN_EMISSIONS_G_PER_PERSON_KM = 44.0

# Speed-dependent CO2 for cars, COPERT/HBEFA-style: an emission factor as a
# continuous function of the average speed on a link.
CAR_EF_ANCHOR_SPEED_KMH = 50.0  # CAR_EMISSIONS_G_PER_KM is the figure at this speed
CAR_EF_MIN_SPEED_KMH = 70.0
CAR_EF_DRAG_TERM = 0.0028605  # c, g*h^2/km^3
CAR_EF_IDLE_TERM = 2 * CAR_EF_DRAG_TERM * CAR_EF_MIN_SPEED_KMH**3  # a, g/h
CAR_EF_ROLLING_TERM = (  # b, g per km
    CAR_EMISSIONS_G_PER_KM
    - CAR_EF_IDLE_TERM / CAR_EF_ANCHOR_SPEED_KMH
    - CAR_EF_DRAG_TERM * CAR_EF_ANCHOR_SPEED_KMH**2
)

# a/v diverges at v -> 0,The FACTOR is capped
MAX_CAR_EMISSION_FACTOR = 2.0

# Cost factors, likewise the only ones.
CAR_COST_PER_KM = 0.32  # € per vehicle-km
# Deiters 2009, Tab. 5, on the Standardisierte Bewertung's rates: a 12 m solo
# bus costs 2.82 € per vehicle-km and a low-floor tram 4.47. Both brought to
# 2025 prices with the consumer price index (Destatis, annual average): 2009 is
# 92.2 on the 2015 base (Lange Reihen ab 1948, Dec 2022), 2025 is 121.9 on the
# 2020 base, and 2020 is 105.8 on the old base, so the factor is
# 121.9 x 105.8 / 100 / 92.2 = 1.399. Bus 2.82 x 1.399 = 3.94, tram
# 4.47 x 1.399 = 6.25. An index of all prices, not of transport wages and
# energy: it is a bridge over sixteen years, not a measured 2025 cost.
BUS_COST_PER_VEHICLE_KM = 3.94  # € per bus-km
TRAM_COST_PER_VEHICLE_KM = 6.25  # € per tram-km
# A train without the track charge: Ramboll (Ermittlung des Finanzbedarfs fuer
# den OEPNV bis 2031, 2023) puts regional rail at nearly 20 € production cost
# per train-km, a third of it (33 %, Tabelle 5) infrastructure charges. 20 x
# 0.67 = 13.40. The car carries no infrastructure cost in this game, so the
# train does not either. Berlin's S-Bahn subsidy alone is at least 17 € per
# train-km (Senat, 2024), so this is the low side.
TRAIN_COST_PER_VEHICLE_KM = 13.40  # € per train-km

# known estimate
CAR_COST_TRAFFIC_SHARE = 0.5

# A bike's upkeep: wear, repairs, depreciation, and theft as an average inside
# it. All of it is the rider's own, so it is both "was es kostet" and "was du
# zahlst" — there is no share for anybody else to carry. It was zero, which
# priced the bike wrong rather than cheap, and left walking nothing to win but
# losing time. What the figure leaves out is the health benefit, which would
# make the bike's cost to society negative, and walking's too; that is open
# with the group. Flat per km: a jam does not wear a chain faster.
BIKE_COST_PER_KM = 0.03  # € per bike-km

# Speeds when a map or a scenario does not state one. A map states its own
# (`GameMap.walk_speed_kmh` and the like); a game whose map is gone
# (`GameSession.game_map` is SET_NULL) and a line without a speed use these.
FALLBACK_WALK_SPEED_KMH = 5
FALLBACK_BIKE_SPEED_KMH = 20
FALLBACK_CAR_SPEED_KMH = 50
FALLBACK_BUS_SPEED_KMH = 30
FALLBACK_TRAIN_SPEED_KMH = 40

# Per game, as the create form and the model start it: a tick of the queue
# model, the hours the morning and the evening are played around, and the
# spread of departures around them.
TICK_DURATION_MIN = 5
MORNING_DEPARTURE_HOUR = 9
EVENING_DEPARTURE_HOUR = 17
DEPARTURE_STD_DEV_MIN = 10

# Departure window: matches the ±60 min clamp in generate_departure_minutes()
DEPARTURE_WINDOW_MIN = 120

JAM_DENSITY_VEH_PER_KM_LANE = 133.0
SATURATION_FLOW_VEH_PER_H_LANE = 1800.0

# bus size = 3x car
BUS_PCU = 3.0

# A tram where its rails lie in the car lane, in the same units: Berlin's
# Flexity is 40 m long, and a car takes 7.5 m of a jammed lane
# (1000 / JAM_DENSITY_VEH_PER_KM_LANE), so 5.3 cars' worth of street.
TRAM_PCU = 5.3

# A bicycle in mixed traffic, in the same units. HCM/HBS put a bicycle at
# roughly a fifth of a car: it is short, and riders do not keep a car's
# following distance. Small, but not nothing — a thousand cyclists on one
# street really do take the room of two hundred cars, which is the whole
# driver-side argument for giving them a lane of their own.
BIKE_PCU = 0.2

# Bikes discharge on a budget of their own, so the car flow limit never holds
# a cyclist: in a car jam the bike is at its own speed while the cars crawl,
# which is what "filtering" means here. A one-directional cycle lane carries
# on the order of 2000 bikes/h; at the demand a school class generates it
# almost never binds, and that is the point — a bike in traffic is delayed by
# other bikes and by nothing else.
BIKE_SATURATION_FLOW_VEH_PER_H_LANE = 2000.0

# A junction whose head has not moved for this many consecutive ticks is
# gridlocked
DEADLOCK_TICKS = 4


def car_emissions_g_per_km(speed_kmh: float) -> float:
    """CO2 per vehicle-km for a car travelling at this average speed.

    COPERT/HBEFA-style average-speed emission modelling. Returns exactly
    CAR_EMISSIONS_G_PER_KM at 50 km/h, and never more than
    MAX_CAR_EMISSION_FACTOR times it.

    Args:
        speed_kmh: Mean speed observed on the link.

    Returns:
        Grams of CO2 per vehicle-kilometre, for one person in one car.
    """

    speed = max(float(speed_kmh), 1.0)
    factor = (
        CAR_EF_IDLE_TERM / speed
        + CAR_EF_ROLLING_TERM
        + CAR_EF_DRAG_TERM * speed * speed
    )
    return min(factor, MAX_CAR_EMISSION_FACTOR * CAR_EMISSIONS_G_PER_KM)


def car_out_of_pocket_eur_per_km(speed_kmh: float) -> float:
    """The part of the Vollkosten a driver feels on this trip.

    CAR_COST_TRAFFIC_SHARE of the 0,32 €/km is fuel and stop-and-go wear and
    rides on the emission curve; the rest — depreciation, insurance, tax — is
    paid whether the car moves today or not, so it is not what this trip
    costs you. Returns exactly CAR_COST_PER_KM * CAR_COST_TRAFFIC_SHARE at
    50 km/h.

    This is "was du zahlst" to car_cost_eur_per_km's "was es kostet". The two
    together are the personal/society contrast on the car side, and they need
    no constant that is not already here.
    """
    return car_cost_eur_per_km(speed_kmh) - CAR_COST_PER_KM * (
        1.0 - CAR_COST_TRAFFIC_SHARE
    )


def car_cost_eur_per_km(speed_kmh: float) -> float:
    """Cost per vehicle-km for a car travelling at this average speed.

    CAR_COST_TRAFFIC_SHARE of the Vollkosten figure is fuel and stop-and-go
    wear and rides on the emission curve; the rest is flat. Returns exactly
    CAR_COST_PER_KM at 50 km/h.

    Args:
        speed_kmh: Mean speed observed on the link.

    Returns:
        Euro per vehicle-kilometre, for one person in one car.
    """
    factor = car_emissions_g_per_km(speed_kmh) / CAR_EMISSIONS_G_PER_KM
    return CAR_COST_PER_KM * (
        1.0 - CAR_COST_TRAFFIC_SHARE + CAR_COST_TRAFFIC_SHARE * factor
    )


# The budget: kg of CO2 per person per round, there and back, the same on
# every map. Normal is a commute inside Germany's 2030 climate target: a
# commute trip emitted 2.42 kg in 2017 (Umweltbundesamt, Texte 224/2020,
# Tab. 4, from MiD 2017 and TREMOD, upstream included), 4.84 there and back;
# the climate law gives transport 85 Mt in 2030 (KSG, Anlage 2a) against 168
# in 2017 (UBA), and cut by as much a commuter's day is 2.45 kg — 2.4 on the
# step. It was Berlin Mitte-West's half-driving round (2.41) until the class
# paid its share of the timetable (2026-10-15), which made that round 1.86;
# the figure stayed and got a source. A national mean, long commutes
# included, so a city is easier than the mean by itself. The step is 0.2
# because on Berlin 0.5 kg is about a sixth of the class switching mode. The
# range runs below a round nobody drives on Berlin (0.72) and above one
# everybody does (3.53), so a host can make a game unwinnable or free.
CO2_KG_PER_PERSON_NORMAL = 2.4
CO2_KG_PER_PERSON_STEP = 0.2
CO2_KG_PER_PERSON_MIN = 0.6
CO2_KG_PER_PERSON_MAX = 6.0

# A summary of a round that has no simulation results (rows from before the
# simulation wrote them) estimates public transport and bike per passenger-km
# from these; the car uses the figures above. Rough, not sourced.
ESTIMATE_PUBLIC_G_PER_KM = 60.0
ESTIMATE_BIKE_G_PER_KM = 18.0
ESTIMATE_PUBLIC_EUR_PER_KM = 0.15

# --- public transport stuff -------------------------------------------------
# personal costs (aka ticket)
PT_FARE_EUR = 1.30


def pt_emissions_g_per_vehicle_km(vehicle: str) -> float:
    """CO2 per vehicle-km for a PT vehicle. Per VEHICLE, never per seat.

    `vehicle` is "bus", "train" or "tram" — a line's kind where it has one,
    its mode where it does not (`PTLineState.vehicle`).

    Dividing by capacity is what made an empty bus as clean as a full one and
    a line nobody rides free. The seats do not come into it: the vehicle runs
    because the timetable says so.
    """
    if vehicle == "train":
        return TRAIN_EMISSIONS_G_PER_VEHICLE_KM
    if vehicle == "tram":
        return TRAM_EMISSIONS_G_PER_VEHICLE_KM
    return BUS_EMISSIONS_G_PER_VEHICLE_KM


def pt_emissions_g_per_person_km(vehicle: str) -> float:
    """CO2 per person-km at the occupancy Germany's buses and trains run at.

    Not what the game charges a rider — that is the line's own emissions per
    vehicle-km, shared by person-km. What it is for: how full the class's
    buses would be if the riders the game does not have were aboard, which is
    the share of the timetable the class pays (`calibration.timetable_factor`).
    """
    if vehicle == "train":
        return TRAIN_EMISSIONS_G_PER_PERSON_KM
    if vehicle == "tram":
        return TRAM_EMISSIONS_G_PER_PERSON_KM
    return BUS_EMISSIONS_G_PER_PERSON_KM


def pt_cost_eur_per_vehicle_km(vehicle: str) -> float:
    """Operating cost per vehicle-km for a PT vehicle. Per VEHICLE."""
    if vehicle == "train":
        return TRAIN_COST_PER_VEHICLE_KM
    if vehicle == "tram":
        return TRAM_COST_PER_VEHICLE_KM
    return BUS_COST_PER_VEHICLE_KM


# The way home leaves over a longer stretch than the way there: the evening's
# σ is the morning's times this. SrV 2018, Berlin, a mean weekday, car trips:
# 33,5 % of those from home to work start in the busiest hour, 20,8 % of those
# from work home; fitted to the hourly shares, the evening's spread is 1,61
# times the morning's (SD, interquartile range and central 68 % alike; the 16
# big cities of the same survey 1,74). TU Dresden, "Mobilität in Städten — SrV
# 2018", Tabellenbericht Berlin, Tab. 8.2 and 8.2.1. Only the ratio is taken:
# the round's σ is the game's, and the calibration's count goes with it.
EVENING_DEPARTURE_SPREAD = 1.6


def generate_departure_minutes(
    num_people: int,
    base_hour: int,
    std_dev_min: float,
    rng: random.Random | None = None,
) -> list[float]:
    """
    Draw departure times from a normal distribution around base_hour.

    Returns minutes from the start of the departure window, which begins
    60 minutes before base_hour (DEPARTURE_WINDOW_MIN is 120 wide). Floats,
    not tick buckets: bucketing here quantised every trip to the tick before
    the simulation had started, and the tick is a simulation step, not a
    property of when people leave the house.

    Args:
        rng: The generator to draw from. The simulator passes its own, seeded
            from the round, so a round is reproducible. Defaults to the module
            generator for the handful of direct callers that only care about
            the shape of the distribution.
    """
    draw = rng if rng is not None else random
    base_minutes = base_hour * 60
    window_start = (base_hour - 1) * 60
    departures = []
    for _ in range(num_people):
        departure_min = draw.gauss(base_minutes, std_dev_min)
        departure_min = max(base_minutes - 60, min(base_minutes + 60, departure_min))
        departures.append(max(0.0, departure_min - window_start))
    return departures


# --- The stochastic layer -------------------------------------------------
#  cars are not all same size
CAPACITY_FACTOR_SIGMA = 0.14
CAPACITY_FACTOR_CLAMP = (0.60, 1.40)

# Drivers do not all want to go the same speed.
DRIVER_SPEED_SIGMA = 0.12
DRIVER_SPEED_CLAMP = (0.70, 1.40)


def _truncated_normal(rng: random.Random, sigma: float, clamp: tuple) -> float:
    """A factor around 1.0, clamped so it can never be zero or negative.

    Clamping rather than resampling: resampling until a draw lands in range
    is unbounded work for a tail that is already negligible at these sigmas,
    and it distorts the distribution in the same direction anyway.
    """
    low, high = clamp
    return max(low, min(high, rng.gauss(1.0, sigma)))


def draw_capacity_factor(rng: random.Random) -> float:
    """This round's capacity multiplier for one link."""
    return _truncated_normal(rng, CAPACITY_FACTOR_SIGMA, CAPACITY_FACTOR_CLAMP)


def draw_driver_speed_factor(rng: random.Random) -> float:
    """One driver's desired-speed multiplier, for the whole of their trip."""
    return _truncated_normal(rng, DRIVER_SPEED_SIGMA, DRIVER_SPEED_CLAMP)
