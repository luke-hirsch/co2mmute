"""
The traffic engine, as a package rather than a module of the game app.

An engine has no models, views, URLs or migrations, so it is a package and not
a Django app. Three things follow from that, and they are the reasons it was
pulled out of `game/simulation.py`:

- **It is documentation.** `scenario.py` is the input contract in forty lines.
- **A second model can drop in.** A Nagel-Schreckenberg cellular automaton, say,
  is then a new file consuming the same scenario — comparable directly, rather
  than a rewrite of everything around it.
- **Tests and calibration stop needing a database.** Everything in here can be
  imported and run without a settings module.

`game.simulation.TrafficSimulator` keeps its name, path and signature and is
still the only thing the rest of the backend talks to. It is the adapter:
ORM rows in, engine, result rows out.
"""

from sim.constants import (
    BUS_COST_PER_VEHICLE_KM,
    BUS_EMISSIONS_G_PER_VEHICLE_KM,
    BUS_PCU,
    CAPACITY_FACTOR_CLAMP,
    CAPACITY_FACTOR_SIGMA,
    CAR_COST_PER_KM,
    CAR_COST_TRAFFIC_SHARE,
    CAR_EF_DRAG_TERM,
    CAR_EF_IDLE_TERM,
    CAR_EF_MIN_SPEED_KMH,
    CAR_EF_ROLLING_TERM,
    CAR_EMISSIONS_G_PER_KM,
    DEADLOCK_TICKS,
    DRIVER_SPEED_CLAMP,
    DRIVER_SPEED_SIGMA,
    JAM_DENSITY_VEH_PER_KM_LANE,
    MAX_CAR_EMISSION_FACTOR,
    PT_FARE_EUR,
    SATURATION_FLOW_VEH_PER_H_LANE,
    TRAIN_COST_PER_VEHICLE_KM,
    TRAIN_EMISSIONS_G_PER_VEHICLE_KM,
    car_cost_eur_per_km,
    car_emissions_g_per_km,
    car_out_of_pocket_eur_per_km,
    draw_capacity_factor,
    draw_driver_speed_factor,
    generate_departure_minutes,
)
from sim.log import SimulationLog
from sim.scenario import Segment
from sim.state import (
    EdgeState,
    PTLineState,
    PTVehicle,
    QueuedVehicle,
    Vehicle,
    node_chain,
)

__all__ = [
    "BUS_COST_PER_VEHICLE_KM",
    "BUS_EMISSIONS_G_PER_VEHICLE_KM",
    "BUS_PCU",
    "CAPACITY_FACTOR_CLAMP",
    "CAPACITY_FACTOR_SIGMA",
    "CAR_COST_PER_KM",
    "CAR_COST_TRAFFIC_SHARE",
    "CAR_EF_DRAG_TERM",
    "CAR_EF_IDLE_TERM",
    "CAR_EF_MIN_SPEED_KMH",
    "CAR_EF_ROLLING_TERM",
    "CAR_EMISSIONS_G_PER_KM",
    "DEADLOCK_TICKS",
    "DRIVER_SPEED_CLAMP",
    "DRIVER_SPEED_SIGMA",
    "JAM_DENSITY_VEH_PER_KM_LANE",
    "MAX_CAR_EMISSION_FACTOR",
    "PT_FARE_EUR",
    "SATURATION_FLOW_VEH_PER_H_LANE",
    "TRAIN_COST_PER_VEHICLE_KM",
    "TRAIN_EMISSIONS_G_PER_VEHICLE_KM",
    "EdgeState",
    "PTLineState",
    "PTVehicle",
    "QueuedVehicle",
    "Segment",
    "SimulationLog",
    "Vehicle",
    "car_cost_eur_per_km",
    "car_emissions_g_per_km",
    "car_out_of_pocket_eur_per_km",
    "draw_capacity_factor",
    "draw_driver_speed_factor",
    "generate_departure_minutes",
    "node_chain",
]
