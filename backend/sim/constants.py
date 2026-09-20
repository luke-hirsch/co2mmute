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
# continuous function of the average speed on a link. The three terms are
# physical — a/v is the time-proportional part (idling, stop-and-go, burning
# fuel while covering no ground), b is rolling resistance per km, c*v**2 is
# aerodynamic drag — which is why the curve is U-shaped with its minimum at
# 70 km/h rather than monotonic.
#
# a and b are DERIVED from c and two calibration conditions rather than
# written out as rounded literals, so both conditions hold exactly instead of
# to four digits:
#   minimum at 70 km/h   ->  a = 2*c*70**3
#   EF(50) == 166.8      ->  b = 166.8 - a/50 - c*2500
# The third condition, EF(10) == 1.9 * EF(50), is what fixes c. It is the one
# judgement call in here: how dear stop-and-go is. Everything else is identity.
CAR_EF_MIN_SPEED_KMH = 70.0
CAR_EF_DRAG_TERM = 0.0028605  # c, g*h^2/km^3
CAR_EF_IDLE_TERM = 2 * CAR_EF_DRAG_TERM * CAR_EF_MIN_SPEED_KMH**3  # a, g/h
CAR_EF_ROLLING_TERM = (  # b, g per km
    CAR_EMISSIONS_G_PER_KM
    - CAR_EF_IDLE_TERM / 50.0
    - CAR_EF_DRAG_TERM * 50.0**2
)

# a/v diverges at v -> 0, and a diverging function is no more accurate than a
# flat one down there. The FACTOR is capped rather than the speed floored: it
# bites below 9.2 km/h, where a car is idling rather than driving and an
# average-speed model has nothing left to say. 2.00x is also a number a class
# can hold in its head.
MAX_CAR_EMISSION_FACTOR = 2.0

# Cost factors from Mobility models (defaults)
CAR_COST_PER_KM = 0.32  # € per vehicle-km
BUS_COST_PER_VEHICLE_KM = 4.5  # € per bus-km
TRAIN_COST_PER_VEHICLE_KM = 12.0  # € per train-km

# 0.32 €/km is a Vollkosten figure, so not all of it can follow the emission
# curve. Roughly half of it is metered by how the car is actually driven:
# fuel is 166.8 g/km / ~2320 g per litre = ~7.2 l/100km, about 0.126 €/km at
# ~1.75 €/l, and stop-and-go wear on brakes, clutch and tyres adds ~0.034.
# The other half — depreciation, insurance, tax — is per kilometre whatever
# the traffic does. Fuel tracks the CO2 factor EXACTLY rather than on a curve
# of its own, because CO2 is fuel burnt: one physics, two units.
CAR_COST_TRAFFIC_SHARE = 0.5

# Physical road constants, replacing the old capacity model. That one put 750
# vehicles on a kilometre of one lane (speed_limit * 15), about five times what
# fits, so an edge only counted as congested in a state that cannot exist.
#
# A car is ~4.5 m and occupies ~7.5 m at a standstill -> ~133 veh/km/lane.
# One lane discharges ~1800 veh/h at capacity (HCM base saturation flow is
# ~1900 pc/h/ln; 1800 is the common working figure for an urban arterial).
JAM_DENSITY_VEH_PER_KM_LANE = 133.0
SATURATION_FLOW_VEH_PER_H_LANE = 1800.0

# A bus takes about three car lengths in mixed traffic (passenger car units).
BUS_PCU = 3.0

# A junction whose head has not moved for this many consecutive ticks is
# gridlocked, not busy: routes are holding each other's streets and nothing
# downstream will free up on its own. It then releases its tick's budget
# anyway, over storage, and the release is counted. Liveness beats storage.
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
    # Arithmetic guard, not a model floor: a zero-length link would divide by
    # zero. The cap below is the modelling decision.
    speed = max(float(speed_kmh), 1.0)
    factor = (
        CAR_EF_IDLE_TERM / speed
        + CAR_EF_ROLLING_TERM
        + CAR_EF_DRAG_TERM * speed * speed
    )
    return min(factor, MAX_CAR_EMISSION_FACTOR * CAR_EMISSIONS_G_PER_KM)


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
#
# Nothing in the model was random but the departure draw, so two rounds with
# identical choices came back identical to the decimal. The literature says
# day-to-day variability is real and large — sigma is around 25% of mean
# travel time in an urban peak and up to 75% in central Stockholm, and 55% of
# congestion is non-recurrent (FHWA) — while day-to-day DEMAND moves only
# about 10%.
#
# ~10% in, 25-75% out. The amplifier is the non-linearity near capacity, and
# the link queue model already has it: spillback, FIFO and a finite discharge
# budget. So the inputs get modest noise and the existing mechanism produces
# the spread. Nothing multiplies the result by a random number — that would
# wobble an empty map exactly as hard as a jammed one, which is backwards.

# Capacity is a random variable rather than a constant (Brilon, Geistefeldt
# and Zurlinden fit a Weibull to it). A truncated normal is used here because
# it is centred on the calibrated figure by construction, which keeps the
# deterministic model as the mean of the stochastic one.
#
# THIS IS THE ONLY DIAL THAT MAKES ROUND 2 DIFFER FROM ROUND 1. Per-driver
# noise averages away over a thousand people; a per-link, per-round draw does
# not.
# Calibrated, not guessed: a twenty-seed sweep over a two-approach merge puts
# the coefficient of variation of car trip time at 12.7% with sigma 0.10,
# 17.6% with 0.14 and 22.1% with 0.18, against a near-zero 0.3% in free flow
# in every case. 0.14 is the smallest value that lands inside the 15-30% band
# the literature reports for urban peaks.
#
# It is deliberately not pushed to the 25% those studies centre on. 55% of
# real congestion is non-recurrent — incidents, weather, work zones — and none
# of that is modelled here. Inflating capacity variance until it stands in for
# an incident model would put the right number on screen for the wrong reason.
# Reaching 25% honestly means modelling incidents, which is a game-design
# decision rather than a modelling one.
CAPACITY_FACTOR_SIGMA = 0.14
CAPACITY_FACTOR_CLAMP = (0.60, 1.40)

# Drivers do not all want to go the same speed. This is the within-round
# spread and it is drawn once per vehicle at spawn, never per link: a driver
# who is fast on one street has to stay fast on the next, or a long route
# averages back to the mean and the dial does nothing.
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
