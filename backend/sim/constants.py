"""
Physical constants of the traffic model, and the two curves that read off them.

Moved out of `game/simulation.py` unchanged. Nothing here imports Django: these
are numbers about roads and cars, not about this game's database, and keeping
them importable without a settings module is what lets the engine be tested and
calibrated as a script.
"""

import random

# Emission factors from Mobility models (defaults)
CAR_EMISSIONS_G_PER_KM = 166.8  # g CO2e per vehicle-km (1 person = 1 vehicle)
BUS_EMISSIONS_G_PER_VEHICLE_KM = 1200.0  # g CO2e per bus-km
TRAIN_EMISSIONS_G_PER_VEHICLE_KM = 3500.0  # g CO2e per train-km

# Speed-dependent CO2 for cars, COPERT/HBEFA-style: an emission factor as a
# continuous function of the average speed on a link.
CAR_EF_MIN_SPEED_KMH = 70.0
CAR_EF_DRAG_TERM = 0.0028605  # c, g*h^2/km^3
CAR_EF_IDLE_TERM = 2 * CAR_EF_DRAG_TERM * CAR_EF_MIN_SPEED_KMH**3  # a, g/h
CAR_EF_ROLLING_TERM = (  # b, g per km
    CAR_EMISSIONS_G_PER_KM - CAR_EF_IDLE_TERM / 50.0 - CAR_EF_DRAG_TERM * 50.0**2
)

# a/v diverges at v -> 0,The FACTOR is capped
MAX_CAR_EMISSION_FACTOR = 2.0

# Cost factors from Mobility models (defaults)
CAR_COST_PER_KM = 0.32  # € per vehicle-km
BUS_COST_PER_VEHICLE_KM = 4.5  # € per bus-km
TRAIN_COST_PER_VEHICLE_KM = 12.0  # € per train-km

# known estimate
CAR_COST_TRAFFIC_SHARE = 0.5

JAM_DENSITY_VEH_PER_KM_LANE = 133.0
SATURATION_FLOW_VEH_PER_H_LANE = 1800.0

# bus size = 3x car
BUS_PCU = 3.0

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


# --- public transport stuff -------------------------------------------------
# personal costs (aka ticket)
PT_FARE_EUR = 1.30


def pt_emissions_g_per_vehicle_km(mode: str) -> float:
    """CO2 per vehicle-km for a PT vehicle. Per VEHICLE, never per seat.

    Dividing by capacity is what made an empty bus as clean as a full one and
    a line nobody rides free. The seats do not come into it: the vehicle runs
    because the timetable says so.
    """
    return (
        TRAIN_EMISSIONS_G_PER_VEHICLE_KM
        if mode == "train"
        else BUS_EMISSIONS_G_PER_VEHICLE_KM
    )


def pt_cost_eur_per_vehicle_km(mode: str) -> float:
    """Operating cost per vehicle-km for a PT vehicle. Per VEHICLE."""
    return TRAIN_COST_PER_VEHICLE_KM if mode == "train" else BUS_COST_PER_VEHICLE_KM


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
