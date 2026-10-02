"""
The input contract of the engine.

This file is the documentation: it says exactly what the simulation needs to
know about one pass of a round — the links, the routes, the lines and a handful
of numbers — instead of leaving it implicit across three hundred lines of ORM
queries in the adapter.

Nothing here imports Django. `game/simulation.py` builds these from model rows;
a calibration script or a second engine can build them from anything at all.

What the adapter decides and the engine never sees: which map version a round
runs on, which side of the street a line drives (`_its_own_way`), and what a
missing map falls back to. What the engine decides from the raw facts given
here: how many lanes are left for cars, who queues, and everything after.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Segment:
    """One leg of a route: which link, in which order, by which mode.

    The engine used to read these four attributes straight off `RouteSegment`
    model rows, which is the one thing that kept the tick loop tied to the
    database. Same four fields, no Django.
    """

    edge_id: int
    order: int
    mode: str
    pt_line_id: int | None = None


@dataclass(frozen=True)
class Link:
    """One directed link: a street, a railway, or a path.

    Raw facts, not the model's reading of them. `lanes` counts the whole street,
    every reservation included, and the engine takes a car lane off it for a bus
    lane and for a bike lane. A link with no street under it (`is_street`
    false) is rail or a path: no car lane at all, whatever `lanes` says.

    `speed_limit_kmh` is read only on a street; zero or less there means "not
    set", and the engine falls back to the map's default car speed and says so.
    """

    edge_id: int
    start_node_id: int
    end_node_id: int
    distance_m: float
    is_street: bool = False
    speed_limit_kmh: float = 0.0
    lanes: int = 1
    has_dedicated_bus_lane: bool = False
    has_bike_lane: bool = False
    # The map's own name for the link, for the server log, and "A → B" for the
    # report the host downloads.
    name: str = ""
    label: str = ""


@dataclass(frozen=True)
class Route:
    """One Gruppe's way, there or home: a chain of segments and who it is.

    `pk` is the route's key. Every person-route key is positive — the engine
    gives its own line runs negative ones, and `route_pk < 0` is how it tells a
    bus from a person — so in the game it is the `AgentRoute` pk, and anywhere
    else any positive integer that is unique within the scenario.

    The distance and the estimate are the router's, and are only reported: the
    estimate stands in for a route nobody on it departed on.
    """

    pk: int
    agent_id: int
    transport_mode: str
    segments: tuple[Segment, ...]
    label: str = ""
    total_distance_m: float = 0.0
    estimated_time_min: float = 0.0


@dataclass(frozen=True)
class Line:
    """One public transport line, as it runs on this pass's map.

    `edge_ids` in travel order, each the link the line actually drives. The
    engine runs it as far as the links connect and charges only that far.
    """

    mode: str  # "bus" or "train"
    line_id: int
    name: str
    edge_ids: tuple[int, ...]
    interval_min: int
    capacity: int


@dataclass(frozen=True)
class Params:
    """The numbers a game sets: how many people, when they leave, how fast.

    `people_per_agent` is derived from the class size in the game
    (`game.calibration`), never picked; here it is just a number.
    """

    people_per_agent: int
    walk_speed_kmh: float
    bike_speed_kmh: float
    default_car_speed_kmh: float
    tick_duration_min: int = 5
    morning_departure_hour: int = 9
    evening_departure_hour: int = 17
    departure_std_dev_min: float = 10


@dataclass(frozen=True)
class Scenario:
    """Everything one pass needs: the way to work, or the way home.

    `links` must hold every link a route or a line names, and their ORDER
    matters: it is the order the per-link capacity draws are taken in, and the
    order a tick's visiting shuffle starts from. The game passes them in the
    `Edge` model's own ordering.

    `bus_speeds` and `train_speeds` are per line id. They may name lines that
    are not in `lines` — a route riding a line this map version dropped is
    still measured at that line's speed — which is why they are not on `Line`.

    `title` heads the report ("Round 2 (Game: Klasse 8b)"); `scale` is only
    printed in it, since every distance here is already in metres. `ref` is how
    the server log names the round ("round 412") — never a game's or a
    player's name, because an error there is mailed to the admins.
    """

    params: Params
    links: tuple[Link, ...]
    routes: tuple[Route, ...]
    lines: tuple[Line, ...] = ()
    bus_speeds: Mapping[int, float] = field(default_factory=dict)
    train_speeds: Mapping[int, float] = field(default_factory=dict)
    direction: str = "out"  # or "home"
    title: str = ""
    ref: str = "the round"
    scale: float = 100.0
