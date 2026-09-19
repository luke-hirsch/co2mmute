import io
import logging
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field

from maps.models import BusLine, Edge, StreetPerRound, TrainLine

from game.models import (
    AgentRoute,
    AgentSimulationResult,
    EdgeTrafficSnapshot,
    GameRound,
    RouteSegment,
    SimulationResult,
)

# Emission factors from Mobility models (defaults)
CAR_EMISSIONS_G_PER_KM = 166.8  # g CO2e per vehicle-km (1 person = 1 vehicle)
BUS_EMISSIONS_G_PER_VEHICLE_KM = 1200.0  # g CO2e per bus-km
TRAIN_EMISSIONS_G_PER_VEHICLE_KM = 3500.0  # g CO2e per train-km

# Cost factors from Mobility models (defaults)
CAR_COST_PER_KM = 0.32  # € per vehicle-km
BUS_COST_PER_VEHICLE_KM = 4.5  # € per bus-km
TRAIN_COST_PER_VEHICLE_KM = 12.0  # € per train-km

logger = logging.getLogger(__name__)

# Simulation parameters - fallback values if not set in GameSession
FALLBACK_PEOPLE_PER_AGENT = 1000
FALLBACK_TICK_DURATION_MIN = 5
FALLBACK_MORNING_DEPARTURE_HOUR = 9  # 9:00 AM
FALLBACK_EVENING_DEPARTURE_HOUR = 17  # 5:00 PM
FALLBACK_DEPARTURE_STD_DEV_MIN = 10  # Standard deviation for departure times

# Speed constants are now loaded from GameMap model
# These fallback values are used only if the map doesn't specify speeds
FALLBACK_WALK_SPEED_KMH = 5
FALLBACK_BIKE_SPEED_KMH = 20
FALLBACK_DEFAULT_CAR_SPEED_KMH = 50
FALLBACK_BUS_SPEED_KMH = 30
FALLBACK_TRAIN_SPEED_KMH = 40
FALLBACK_BUS_INTERVAL_MIN = 10
FALLBACK_TRAIN_INTERVAL_MIN = 10

# Departure window: matches the ±60 min clamp in generate_departure_times()
DEPARTURE_WINDOW_MIN = 120

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


@dataclass
class Vehicle:
    """One person (car/bike/walk) or one PT vehicle carrying many."""

    route_pk: int
    person_index: int
    mode: str
    segment_index: int
    passenger_count: int = 1

    wants_to_depart_min: float = 0.0  # when this person wanted to leave
    ready_at_min: float = 0.0  # earliest it may leave its current link
    entered_edge_min: float = 0.0
    arrived_min: float | None = None
    departed: bool = False
    arrived: bool = False
    queued: bool = False


@dataclass
class PTVehicle:
    """Represents a public transport vehicle (bus/train)."""

    line_id: int
    vehicle_type: str  # bus or train
    current_stop_index: int
    passenger_count: int
    capacity: int
    departure_tick: int  # When this vehicle starts its route


class SimulationLog:
    """Collects detailed simulation logs into a downloadable text report."""

    def __init__(self):
        self._buf = io.StringIO()
        self._edge_names: dict[int, str] = {}  # edge_id -> name
        self._route_labels: dict[int, str] = {}  # route_pk -> "Player/Agent#N (mode)"
        # Per-edge per-route sample tracking: (route_pk, edge_id) -> {enter_tick, exit_tick, ...}
        self._sample_edge_events: dict[tuple[int, int], dict] = {}

    def set_edge_names(self, edge_names: dict[int, str]):
        self._edge_names = edge_names

    def set_route_labels(self, route_labels: dict[int, str]):
        self._route_labels = route_labels

    def _edge_label(self, edge_id: int) -> str:
        name = self._edge_names.get(edge_id, "")
        return f"Edge {edge_id} ({name})" if name else f"Edge {edge_id}"

    def _route_label(self, route_pk: int) -> str:
        return self._route_labels.get(route_pk, f"Route {route_pk}")

    def write(self, line: str):
        self._buf.write(line + "\n")

    def header(self, text: str):
        sep = "=" * 70
        self._buf.write(f"\n{sep}\n{text}\n{sep}\n")

    def subheader(self, text: str):
        self._buf.write(f"\n--- {text} ---\n")

    def get_text(self) -> str:
        return self._buf.getvalue()


@dataclass
class QueuedVehicle:
    """One vehicle sitting on a link, with the earliest minute it may leave."""

    vehicle_id: int
    ready_at_min: float
    pcu: float
    entered_at_min: float


@dataclass
class EdgeState:
    """A link in the queue model: free-flow time, flow capacity, storage."""

    edge_id: int
    distance_m: float
    free_flow_speed_kmh: float
    car_lanes: int = 1
    has_dedicated_bus_lane: bool = False

    queue: list[QueuedVehicle] = field(default_factory=list)
    occupancy_pcu: float = 0.0
    release_budget: float = 0.0
    blocked_since_tick: int = 0

    # Observed traversals, for the per-edge speed the snapshot stores.
    traversal_count: int = 0
    traversal_time_min: float = 0.0
    peak_occupancy_pcu: float = 0.0

    @property
    def free_flow_min(self) -> float:
        """Minutes to cross the link when it is empty."""
        if self.free_flow_speed_kmh <= 0:
            return 0.0
        return self.distance_m / 1000.0 / self.free_flow_speed_kmh * 60.0

    @property
    def open_to_cars(self) -> bool:
        """False on a bus gate: a street given over entirely to buses."""
        return self.car_lanes > 0

    @property
    def _capacity_lanes(self) -> int:
        """Never zero — see the fallback in _enter_edge.

        A link with no flow capacity can never discharge, so a car that
        reached a bus gate despite the client and the submit check would
        stand there until max_ticks and take the round's numbers with it.
        """
        return max(1, self.car_lanes)

    @property
    def storage_capacity_pcu(self) -> float:
        """How many car-equivalents stand on the link bumper to bumper."""
        return max(
            1.0,
            JAM_DENSITY_VEH_PER_KM_LANE
            * self._capacity_lanes
            * self.distance_m
            / 1000.0,
        )

    def flow_per_tick(self, tick_duration_min: int) -> float:
        """Car-equivalents the link discharges in one tick."""
        return (
            SATURATION_FLOW_VEH_PER_H_LANE
            * self._capacity_lanes
            * tick_duration_min
            / 60.0
        )

    def has_room_for(self, pcu: float) -> bool:
        """Whether one more vehicle of this size fits on the link.

        Asking "is it full?" before adding lets occupancy overshoot by up to
        one vehicle, and by three for a bus — a link with 39.9 of storage
        admitted a 40th car in testing. An empty link never refuses: a link
        too short to hold a single bus would otherwise block it forever.
        """
        if not self.queue:
            return True
        return self.occupancy_pcu + pcu <= self.storage_capacity_pcu

    @property
    def mean_speed_kmh(self) -> float:
        """Length over observed CAR traversal time; free flow if none crossed.

        Only cars are counted into traversal_count / traversal_time_min (see
        _discharge). A pedestrian takes 10.7 minutes over an 895 m edge where a
        car takes 1.07, so letting walkers into this mean would report an empty
        street as jammed — and this number feeds both the CO2 factor and the
        route preview the players see.
        """
        if self.traversal_count == 0 or self.traversal_time_min <= 0:
            return self.free_flow_speed_kmh
        mean_min = self.traversal_time_min / self.traversal_count
        return self.distance_m / 1000.0 / (mean_min / 60.0)


def generate_departure_minutes(
    num_people: int,
    base_hour: int,
    std_dev_min: float,
) -> list[float]:
    """
    Draw departure times from a normal distribution around base_hour.

    Returns minutes from the start of the departure window, which begins
    60 minutes before base_hour (DEPARTURE_WINDOW_MIN is 120 wide). Floats,
    not tick buckets: bucketing here quantised every trip to the tick before
    the simulation had started, and the tick is a simulation step, not a
    property of when people leave the house.
    """
    base_minutes = base_hour * 60
    window_start = (base_hour - 1) * 60
    departures = []
    for _ in range(num_people):
        departure_min = random.gauss(base_minutes, std_dev_min)
        departure_min = max(base_minutes - 60, min(base_minutes + 60, departure_min))
        departures.append(max(0.0, departure_min - window_start))
    return departures


class TrafficSimulator:
    """
    Main simulation engine for traffic simulation.

    Simulates the movement of vehicles through the network,
    accounting for congestion and public transport dynamics.
    """

    def __init__(self, game_round: GameRound, scale: float = 100.0):
        """
        Initialize the simulator.

        Args:
            game_round: The game round to simulate
            scale: Meters per coordinate unit (for distance calculation)
        """
        self.game_round = game_round
        self.scale = scale
        self.simulation_result: SimulationResult | None = None

        # Load simulation parameters from GameSession
        game_session = game_round.game
        self.people_per_agent = game_session.people_per_agent
        self.tick_duration_min = game_session.tick_duration_min
        self.morning_departure_hour = game_session.morning_departure_hour
        self.evening_departure_hour = game_session.evening_departure_hour
        self.departure_std_dev_min = game_session.departure_std_dev_min

        # Load speed settings from GameMap
        game_map = game_round.game.game_map
        if game_map:
            self.walk_speed_kmh = game_map.walk_speed_kmh
            self.bike_speed_kmh = game_map.bike_speed_kmh
            self.default_car_speed_kmh = game_map.default_car_speed_kmh
        else:
            # Use fallback values if no map is set
            self.walk_speed_kmh = FALLBACK_WALK_SPEED_KMH
            self.bike_speed_kmh = FALLBACK_BIKE_SPEED_KMH
            self.default_car_speed_kmh = FALLBACK_DEFAULT_CAR_SPEED_KMH

        # Edge states indexed by edge_id
        self.edge_states: dict[int, EdgeState] = {}

        # Vehicles indexed by unique ID
        self.vehicles: dict[int, Vehicle] = {}
        self.next_vehicle_id = 0

        # PT vehicles
        self.pt_vehicles: list[PTVehicle] = []

        # Route data indexed by route.pk (globally unique)
        self.agent_routes: dict[int, AgentRoute] = {}
        self.route_segments: dict[int, list[RouteSegment]] = {}

        # PT line speed cache: line_id -> speed_kmh
        self.bus_line_speeds: dict[int, int] = {}
        self.train_line_speeds: dict[int, int] = {}

        # PT line interval cache: line_id -> intervall_min
        self.bus_line_intervals: dict[int, int] = {}
        self.train_line_intervals: dict[int, int] = {}

        # Per-route PT wait time (interval/2): route_pk -> wait_min
        self.route_pt_wait_min: dict[int, float] = {}

        # Vehicle scaling for PT routes: route_pk -> (num_vehicles, passenger_count)
        self.route_vehicle_scaling: dict[int, tuple[int, int]] = {}

        # Departure schedules: route_pk -> list of (person_index, departure_tick)
        self.departure_schedule: dict[int, list[tuple[int, int]]] = {}

        # Results tracking
        self.agent_results: dict[int, dict] = {}  # route_pk -> results dict

        # Current simulation tick
        self.current_tick = 0

        # Callback for progress updates
        self.on_progress: callable | None = None  # type: ignore

        # Detailed simulation log
        self.sim_log = SimulationLog()

        # Sample vehicle IDs: route_pk -> vehicle_id (person_index=0, for detailed logging)
        self.sample_vehicles: dict[int, int] = {}

        # Load routes and initialize edges during construction
        self._load_routes()
        self._initialize_edges()

    def _load_routes(self):
        """Load all agent routes for the round."""
        from game.models import PlayerMove

        player_moves = PlayerMove.objects.filter(session_round=self.game_round)
        logger.info(f"[SIM] Loading routes for {player_moves.count()} player moves")

        route_labels = {}
        for move in player_moves:
            player_name = move.player.name or f"Player {move.player.player_id}"
            routes = AgentRoute.objects.filter(player_move=move).prefetch_related(
                "segments", "segments__edge"
            )
            for route in routes:
                self.agent_routes[route.pk] = route
                segments = list(route.segments.order_by("order"))  # type: ignore
                self.route_segments[route.pk] = segments

                label = f"{player_name}/Agent#{route.agent_id} ({route.transport_mode})"
                route_labels[route.pk] = label

                logger.debug(
                    f"[SIM] Route {route.pk} (agent {route.agent_id}): "
                    f"mode={route.transport_mode}, "
                    f"distance={route.total_distance_m:.0f}m, segments={len(segments)}"
                )

                # Initialize result tracking
                self.agent_results[route.pk] = {
                    "trip_times": [],
                    "delays": [],
                    "mode": route.transport_mode,
                    "not_arrived": 0,
                }

        self.sim_log.set_route_labels(route_labels)
        logger.info(f"[SIM] Loaded {len(self.agent_routes)} agent routes")

        # Load PT line speeds and compute vehicle scaling
        self._load_pt_line_speeds()
        self._compute_vehicle_scaling()

    def _compute_vehicle_scaling(self):
        """Compute how many actual vehicles to spawn per route.

        For car/bike/walk: 1 vehicle per person (people_per_agent vehicles).
        For bus/train: number of vehicles is determined by BOTH interval and capacity:
          - num_vehicles = floor(DEPARTURE_WINDOW_MIN / interval_min)  [physical frequency]
          - passengers_per_vehicle = min(capacity, ceil(people_per_agent / num_vehicles))
          - If num_vehicles * capacity < people_per_agent, buses are over capacity (logged as warning).
        """
        for route_pk, segments in self.route_segments.items():
            # Find the minimum PT capacity and interval across all PT segments in this route
            min_pt_capacity = None
            min_interval = None
            for seg in segments:
                if seg.mode in ("bus", "train"):
                    cap = self._get_pt_capacity(seg.pt_line_id, seg.mode)
                    if min_pt_capacity is None or cap < min_pt_capacity:
                        min_pt_capacity = cap
                    interval = self._get_pt_interval(seg.pt_line_id, seg.mode)
                    if min_interval is None or interval < min_interval:
                        min_interval = interval

            if min_pt_capacity and min_pt_capacity > 1:
                # Number of physical buses/trains in the departure window
                num_vehicles = max(1, round(DEPARTURE_WINDOW_MIN / (min_interval or 1)))
                # Each vehicle carries min(capacity, ceil(people/vehicles)) passengers
                passenger_count = min(
                    int(min_pt_capacity),
                    math.ceil(self.people_per_agent / num_vehicles),
                )
                total_seats = num_vehicles * passenger_count
                overcapacity = total_seats < self.people_per_agent
                self.route_vehicle_scaling[route_pk] = (num_vehicles, passenger_count)
                self.route_pt_wait_min[route_pk] = (min_interval or 1) / 2.0

                log_msg = (
                    f"[SIM] Route {route_pk}: PT scaling — "
                    f"{num_vehicles} vehicles × {passenger_count} passengers "
                    f"(interval={min_interval}min, capacity={min_pt_capacity:.0f}, "
                    f"total_seats={total_seats})"
                )
                if overcapacity:
                    log_msg += (
                        f" — WARNING: overcapacity! "
                        f"{total_seats} seats < {self.people_per_agent} people"
                    )
                    logger.warning(log_msg)
                else:
                    logger.info(log_msg)
            else:
                # Car/bike/walk: 1 person per vehicle
                self.route_vehicle_scaling[route_pk] = (self.people_per_agent, 1)

    def _load_pt_line_speeds(self):
        """Load bus and train line speeds from database."""
        from maps.models import BusLine, TrainLine

        # Collect unique PT line IDs from route segments
        bus_line_ids = set()
        train_line_ids = set()

        for segments in self.route_segments.values():
            for seg in segments:
                if seg.pt_line_id:
                    if seg.mode == "bus":
                        bus_line_ids.add(seg.pt_line_id)
                    elif seg.mode == "train":
                        train_line_ids.add(seg.pt_line_id)

        # Load bus line speeds and intervals
        if bus_line_ids:
            bus_lines = BusLine.objects.filter(id__in=bus_line_ids)
            for bus_line in bus_lines:
                self.bus_line_speeds[bus_line.pk] = bus_line.bus_speed_kmh
                self.bus_line_intervals[bus_line.pk] = bus_line.intervall
            logger.info(
                f"[SIM] Loaded {len(self.bus_line_speeds)} bus line speeds/intervals"
            )

        # Load train line speeds and intervals
        if train_line_ids:
            train_lines = TrainLine.objects.filter(id__in=train_line_ids)
            for train_line in train_lines:
                self.train_line_speeds[train_line.pk] = train_line.train_speed_kmh
                self.train_line_intervals[train_line.pk] = train_line.intervall
            logger.info(
                f"[SIM] Loaded {len(self.train_line_speeds)} train line speeds/intervals"
            )

    def _initialize_edges(self):
        """Initialize edge states from the map."""
        # Get unique edges from all routes
        edge_ids = set()
        for segments in self.route_segments.values():
            for seg in segments:
                edge_ids.add(seg.edge_id)  # type: ignore

        logger.info(f"[SIM] Initializing {len(edge_ids)} unique edges")

        # Load edges and initialize states
        edges = Edge.objects.filter(id__in=edge_ids).select_related(
            "start_node", "end_node", "game_map"
        )

        edge_names = {}
        for edge in edges:
            # Calculate distance
            distance_m = edge.euclidean_2d_distance() * self.scale

            # Get speed limit, lanes, and bus lane info from StreetEdge
            street_edge = edge.streetedge_set.first()  # type: ignore
            if street_edge:
                speed_limit = street_edge.speed_limit
                lanes = street_edge.lanes
                has_dedicated_bus_lane = street_edge.dedicated_bus_lane
            else:
                speed_limit = self.default_car_speed_kmh
                lanes = 1
                has_dedicated_bus_lane = False

            if speed_limit <= 0:
                logger.warning(
                    "[SIM] Edge %s (%s) has speed_limit=%s — falling back to the "
                    "map default of %s km/h. Fix the map.",
                    edge.pk,
                    edge.name or "unnamed",
                    speed_limit,
                    self.default_car_speed_kmh,
                )
                speed_limit = self.default_car_speed_kmh

            capacity = calculate_edge_capacity(distance_m, speed_limit, lanes)
            self.edge_states[edge.pk] = EdgeState(
                edge_id=edge.pk,
                distance_m=distance_m,
                free_flow_speed_kmh=speed_limit,
                capacity=capacity,
                lanes=lanes,
                has_dedicated_bus_lane=has_dedicated_bus_lane,
            )

            # Build edge name for logging
            start_name = edge.start_node.name or f"Node {edge.start_node.pk}"
            end_name = edge.end_node.name or f"Node {edge.end_node.pk}"
            edge_names[edge.pk] = f"{start_name} → {end_name}"

            logger.debug(
                f"[SIM] Edge {edge.pk}: dist={distance_m:.0f}m, "
                f"speed={speed_limit}km/h, lanes={lanes}, capacity={capacity}, "
                f"dedicated_bus_lane={has_dedicated_bus_lane}"
            )

        self.sim_log.set_edge_names(edge_names)
        logger.info(f"[SIM] Initialized {len(self.edge_states)} edge states")

    def _generate_departures(self, is_morning: bool = True):
        """Generate departure times for all agents.

        Car/bike/walk: random normal distribution around base_hour (existing behaviour).
        Bus/train: evenly spaced at the line's interval, starting at the beginning of the
                   departure window (base_hour - 60 min), so that buses are spread across
                   the full DEPARTURE_WINDOW_MIN period.
        """
        base_hour = (
            self.morning_departure_hour if is_morning else self.evening_departure_hour
        )
        # Tick corresponding to (base_hour - 1), i.e. the start of the ±60 min window.
        # generate_departure_times uses (base_hour-1)*60 as time-zero, so offset=0 is that point.
        window_start_tick = 0

        for route_pk in self.agent_routes:
            route = self.agent_routes[route_pk]
            num_vehicles, _ = self.route_vehicle_scaling.get(
                route_pk, (self.people_per_agent, 1)
            )

            # Determine if this route uses public transport
            segments = self.route_segments.get(route_pk, [])
            pt_mode = next(
                (seg.mode for seg in segments if seg.mode in ("bus", "train")), None
            )

            if pt_mode:
                pt_line_id = next(
                    (seg.pt_line_id for seg in segments if seg.mode == pt_mode), None
                )
                interval_min = self._get_pt_interval(pt_line_id, pt_mode)
                self.departure_schedule[route_pk] = [
                    (i, float(i * interval_min)) for i in range(num_vehicles)
                ]
            else:
                departures = generate_departure_minutes(
                    num_vehicles, base_hour, self.departure_std_dev_min
                )
                self.departure_schedule[route_pk] = list(enumerate(departures))

    def _spawn_vehicles(self):
        """Spawn vehicles that should depart at the current tick."""
        for route_pk, schedule in self.departure_schedule.items():
            route = self.agent_routes.get(route_pk)
            if not route:
                continue

            segments = self.route_segments.get(route_pk, [])
            if not segments:
                continue

            _, passenger_count = self.route_vehicle_scaling.get(
                route_pk, (self.people_per_agent, 1)
            )

            # Find vehicles that should depart at this tick
            for person_index, departure_tick in schedule:
                if departure_tick == self.current_tick:
                    # Create vehicle
                    vehicle = Vehicle(
                        route_pk=route_pk,
                        person_index=person_index,
                        mode=segments[0].mode,  # Start with first segment mode
                        segment_index=0,
                        position_on_edge_m=0.0,
                        departed=True,
                        passenger_count=passenger_count,
                    )

                    vehicle_id = self.next_vehicle_id
                    self.next_vehicle_id += 1
                    self.vehicles[vehicle_id] = vehicle

                    # Track first vehicle (person_index=0) as sample for detailed logging
                    if person_index == 0:
                        self.sample_vehicles[route_pk] = vehicle_id

                    # Add to first edge
                    first_segment = segments[0]
                    if first_segment.edge_id in self.edge_states:
                        edge_state = self.edge_states[first_segment.edge_id]
                        edge_state.current_vehicles.add(vehicle_id)

                        # Track buses on dedicated lanes separately
                        if vehicle.mode == "bus" and edge_state.has_dedicated_bus_lane:
                            edge_state.buses_on_dedicated_lane.add(vehicle_id)

    def _move_vehicles(self):
        """Move all vehicles based on current conditions."""
        arrived_vehicles = []

        for vehicle_id, vehicle in self.vehicles.items():
            if vehicle.arrived or not vehicle.departed:
                continue

            segments = self.route_segments.get(vehicle.route_pk, [])
            if vehicle.segment_index >= len(segments):
                vehicle.arrived = True
                arrived_vehicles.append(vehicle_id)
                continue

            current_segment = segments[vehicle.segment_index]
            edge_state = self.edge_states.get(current_segment.edge_id)

            if not edge_state:
                # Skip if edge not found (shouldn't happen)
                vehicle.segment_index += 1
                continue

            # Calculate speed based on mode and congestion.
            # Delay is computed per-tick as the fraction of tick lost to congestion.
            if vehicle.mode in ["car"]:
                # Cars experience full congestion
                current_speed = edge_state.get_current_speed()
                base_speed = edge_state.free_flow_speed_kmh
                delay = (
                    self.tick_duration_min * max(0, 1 - current_speed / base_speed)
                    if base_speed > 0
                    else 0
                )
            elif vehicle.mode == "bus":
                # Get bus speed from PT line or use fallback
                if (
                    current_segment.pt_line_id
                    and current_segment.pt_line_id in self.bus_line_speeds
                ):
                    bus_speed = self.bus_line_speeds[current_segment.pt_line_id]
                else:
                    bus_speed = FALLBACK_BUS_SPEED_KMH

                # Buses on dedicated lanes bypass traffic, otherwise affected by congestion
                if edge_state.has_dedicated_bus_lane:
                    # Dedicated bus lane: use fixed bus speed, no delay
                    current_speed = bus_speed
                    delay = 0
                else:
                    # No dedicated lane: buses stuck in traffic like cars
                    current_speed = min(bus_speed, edge_state.get_current_speed())
                    delay = (
                        self.tick_duration_min * max(0, 1 - current_speed / bus_speed)
                        if bus_speed > 0
                        else 0
                    )
            elif vehicle.mode == "train":
                # Get train speed from PT line or use fallback
                if (
                    current_segment.pt_line_id
                    and current_segment.pt_line_id in self.train_line_speeds
                ):
                    train_speed = self.train_line_speeds[current_segment.pt_line_id]
                else:
                    train_speed = FALLBACK_TRAIN_SPEED_KMH
                current_speed = train_speed
                delay = 0
            elif vehicle.mode == "bike":
                current_speed = self.bike_speed_kmh
                delay = 0
            elif vehicle.mode == "walk":
                current_speed = self.walk_speed_kmh
                delay = 0
            else:
                current_speed = self.walk_speed_kmh
                delay = 0

            # Calculate distance traveled in this tick
            distance_this_tick = current_speed * 1000 / 60 * self.tick_duration_min

            # Update position
            vehicle.position_on_edge_m += distance_this_tick
            vehicle.total_travel_time_min += self.tick_duration_min
            vehicle.congestion_delay_min += delay

            # Check if vehicle has completed current segment
            remaining = edge_state.distance_m - vehicle.position_on_edge_m

            if remaining <= 0:
                # Log per-edge detail for sample vehicles
                is_sample = self.sample_vehicles.get(vehicle.route_pk) == vehicle_id
                if is_sample:
                    free_flow = edge_state.free_flow_speed_kmh
                    ff_time_min = (
                        edge_state.distance_m / 1000 / free_flow * 60
                        if free_flow > 0
                        else 0
                    )
                    actual_time_min = (
                        edge_state.distance_m / 1000 / max(current_speed, 0.1) * 60
                    )
                    self.sim_log.write(
                        f"  [tick {self.current_tick:>3}] {self.sim_log._route_label(vehicle.route_pk)} | "
                        f"{self.sim_log._edge_label(current_segment.edge_id)} | "
                        f"mode={vehicle.mode} | "
                        f"dist={edge_state.distance_m:.0f}m | "
                        f"free_flow={free_flow:.0f}km/h ({ff_time_min:.1f}min) | "
                        f"actual={current_speed:.1f}km/h ({actual_time_min:.1f}min) | "
                        f"delay={delay:.2f}min | "
                        f"vehicles_on_edge={edge_state.total_vehicles} | "
                        f"volume/capacity={edge_state.volume}/{edge_state.capacity}"
                    )

                # Remove from current edge
                edge_state.current_vehicles.discard(vehicle_id)
                edge_state.buses_on_dedicated_lane.discard(vehicle_id)

                # Move to next segment
                vehicle.segment_index += 1
                vehicle.position_on_edge_m = abs(remaining)  # Carry over excess

                if vehicle.segment_index >= len(segments):
                    vehicle.arrived = True
                    arrived_vehicles.append(vehicle_id)
                else:
                    # Update mode for new segment
                    next_segment = segments[vehicle.segment_index]
                    vehicle.mode = next_segment.mode

                    # Add to next edge
                    if next_segment.edge_id in self.edge_states:
                        next_edge_state = self.edge_states[next_segment.edge_id]
                        next_edge_state.current_vehicles.add(vehicle_id)

                        # Track buses on dedicated lanes
                        if (
                            vehicle.mode == "bus"
                            and next_edge_state.has_dedicated_bus_lane
                        ):
                            next_edge_state.buses_on_dedicated_lane.add(vehicle_id)

        # Record arrival times (each vehicle may represent multiple passengers).
        # For PT routes, add the average wait time (interval/2) to trip time —
        # passengers arrive at the stop and wait for the next bus/train on average.
        for vehicle_id in arrived_vehicles:
            vehicle = self.vehicles[vehicle_id]
            agent_results = self.agent_results.get(vehicle.route_pk)
            if agent_results:
                wait_min = self.route_pt_wait_min.get(vehicle.route_pk, 0.0)
                total_time = vehicle.total_travel_time_min + wait_min
                for _ in range(vehicle.passenger_count):
                    agent_results["trip_times"].append(total_time)
                    agent_results["delays"].append(vehicle.congestion_delay_min)

    def _record_edge_traffic(self):
        """Record traffic snapshot for each edge."""
        if not self.simulation_result:
            return

        snapshots = []
        for edge_id, state in self.edge_states.items():
            if state.total_vehicles > 0:
                snapshots.append(
                    EdgeTrafficSnapshot(
                        simulation=self.simulation_result,
                        edge_id=edge_id,
                        time_tick=self.current_tick,
                        vehicle_count=state.total_vehicles,  # Total vehicles for visualization
                        speed_kmh=state.get_current_speed(),  # Speed based on congestion volume
                    )
                )

        if snapshots:
            EdgeTrafficSnapshot.objects.bulk_create(snapshots)

    def _all_vehicles_arrived(self) -> bool:
        """Check if all vehicles have arrived."""
        for vehicle in self.vehicles.values():
            if vehicle.departed and not vehicle.arrived:
                return False
        return True

    def _record_non_arrivals(self):
        """Book the vehicles that were still on the road when time ran out."""
        stranded_routes = 0
        for vehicle in self.vehicles.values():
            if not vehicle.departed or vehicle.arrived:
                continue
            agent_results = self.agent_results.get(vehicle.route_pk)
            if not agent_results:
                continue
            wait_min = self.route_pt_wait_min.get(vehicle.route_pk, 0.0)
            total_time = vehicle.total_travel_time_min + wait_min
            for _ in range(vehicle.passenger_count):
                agent_results["trip_times"].append(total_time)
                agent_results["delays"].append(vehicle.congestion_delay_min)
                agent_results["not_arrived"] += 1

        for route_pk, results in self.agent_results.items():
            if results["not_arrived"]:
                stranded_routes += 1
                self.sim_log.write(
                    f"  DID NOT ARRIVE: {self.sim_log._route_label(route_pk)} — "
                    f"{results['not_arrived']} of "
                    f"{len(results['trip_times'])} travellers were still under way "
                    f"when the simulation ended"
                )

        if stranded_routes:
            logger.warning(
                "[SIM] %s route(s) had travellers still under way at tick %s — "
                "their times are a lower bound",
                stranded_routes,
                self.current_tick,
            )

    def run_simulation(
        self,
        max_ticks: int = 200,
        on_progress: callable | None = None,
    ) -> SimulationResult:
        """
        Run the full simulation.

        Args:
            max_ticks: Maximum number of ticks before stopping
            on_progress: Callback for progress updates (tick, total_ticks)

        Returns:
            SimulationResult with computed statistics
        """
        self.on_progress = on_progress

        logger.info(
            f"[SIM] Starting simulation for round {self.game_round.round_number}, "
            f"scale={self.scale}, max_ticks={max_ticks}"
        )

        # Create simulation result record
        self.simulation_result = SimulationResult.objects.create(
            game_round=self.game_round,
            status=SimulationResult.Status.RUNNING,
        )

        try:
            # Write log header
            self.sim_log.header(
                f"SIMULATION LOG — Round {self.game_round.round_number} "
                f"(Game: {self.game_round.game.game_name})"
            )
            self.sim_log.write(f"Scale: {self.scale} m/unit")
            self.sim_log.write(f"People per agent: {self.people_per_agent}")
            self.sim_log.write(f"Tick duration: {self.tick_duration_min} min")
            self.sim_log.write(f"Max ticks: {max_ticks}")
            self.sim_log.write(f"Walk speed: {self.walk_speed_kmh} km/h")
            self.sim_log.write(f"Bike speed: {self.bike_speed_kmh} km/h")
            self.sim_log.write(f"Default car speed: {self.default_car_speed_kmh} km/h")

            # Log routes
            self.sim_log.header("ROUTES")
            for route_pk, route in self.agent_routes.items():
                segments = self.route_segments.get(route_pk, [])
                num_vehicles, passenger_count = self.route_vehicle_scaling.get(
                    route_pk, (self.people_per_agent, 1)
                )
                wait_min = self.route_pt_wait_min.get(route_pk, 0.0)
                route_line = (
                    f"  {self.sim_log._route_label(route_pk)}: "
                    f"distance={route.total_distance_m:.0f}m, "
                    f"est_time={route.estimated_time_min:.1f}min, "
                    f"segments={len(segments)}, "
                    f"vehicles={num_vehicles}×{passenger_count}pax"
                )
                if wait_min:
                    total_seats = num_vehicles * passenger_count
                    overcap = total_seats < self.people_per_agent
                    route_line += f", avg_wait={wait_min:.1f}min" + (
                        f" [OVERCAPACITY: {total_seats}/{self.people_per_agent} seats]"
                        if overcap
                        else ""
                    )
                self.sim_log.write(route_line)
                for seg in segments:
                    es = self.edge_states.get(seg.edge_id)
                    if es:
                        pt_info = ""
                        if seg.pt_line_id:
                            interval = self._get_pt_interval(seg.pt_line_id, seg.mode)
                            pt_info = (
                                f" | pt_line={seg.pt_line_id} | interval={interval}min"
                            )
                        self.sim_log.write(
                            f"    seg {seg.order}: {self.sim_log._edge_label(seg.edge_id)} | "
                            f"mode={seg.mode} | dist={es.distance_m:.0f}m | "
                            f"free_flow={es.free_flow_speed_kmh:.0f}km/h | "
                            f"capacity={es.capacity} | lanes={es.lanes}" + pt_info
                        )

            # Log edges
            self.sim_log.header("EDGES")
            for eid, es in sorted(self.edge_states.items()):
                self.sim_log.write(
                    f"  {self.sim_log._edge_label(eid)}: "
                    f"dist={es.distance_m:.0f}m, speed={es.free_flow_speed_kmh:.0f}km/h, "
                    f"lanes={es.lanes}, capacity={es.capacity}"
                    + (", DEDICATED BUS LANE" if es.has_dedicated_bus_lane else "")
                )

            # Routes and edges are already loaded in __init__
            if not self.agent_routes:
                logger.warning("[SIM] No agent routes found, simulation will be empty")

            # Run morning commute
            self._generate_departures(is_morning=True)
            self.waiting: list[tuple[float, int, int]] = sorted(
                (depart_min, route_pk, person_index)
                for route_pk, schedule in self.departure_schedule.items()
                for person_index, depart_min in schedule
            )

            total_departures = sum(len(s) for s in self.departure_schedule.values())
            logger.info(
                f"[SIM] Generated {total_departures} departures for "
                f"{len(self.departure_schedule)} agents"
            )

            self.sim_log.header("SIMULATION TICK LOG (sample vehicle per route)")
            self.sim_log.write(
                f"Total vehicles to spawn: {total_departures} "
                f"({len(self.departure_schedule)} routes, {self.people_per_agent} people/agent, "
                f"PT vehicles scaled by interval+capacity, car/bike/walk by people_per_agent)"
            )

            # Simulation loop
            self.current_tick = 0
            vehicles_spawned = 0
            vehicles_arrived = 0

            while self.current_tick < max_ticks:
                prev_vehicle_count = len(self.vehicles)
                self._spawn_vehicles()
                new_spawned = len(self.vehicles) - prev_vehicle_count
                vehicles_spawned += new_spawned

                prev_arrived = sum(1 for v in self.vehicles.values() if v.arrived)
                self._move_vehicles()
                new_arrived = (
                    sum(1 for v in self.vehicles.values() if v.arrived) - prev_arrived
                )
                vehicles_arrived += new_arrived

                # Log progress every 10 ticks to simulation log
                if self.current_tick % 10 == 0:
                    active = sum(
                        1
                        for v in self.vehicles.values()
                        if v.departed and not v.arrived
                    )
                    arrived = sum(1 for v in self.vehicles.values() if v.arrived)

                    # Find congested edges
                    congested = [
                        (eid, s.volume, s.capacity, s.get_current_speed())
                        for eid, s in self.edge_states.items()
                        if s.volume > s.capacity * 0.5
                    ]

                    tick_line = (
                        f"[tick {self.current_tick:>3}] "
                        f"spawned={len(self.vehicles)}, active={active}, "
                        f"arrived={arrived}/{len(self.vehicles)}, "
                        f"congested_edges={len(congested)}"
                    )
                    self.sim_log.write(tick_line)

                    for eid, vol, cap, speed in congested:
                        self.sim_log.write(
                            f"    CONGESTION: {self.sim_log._edge_label(eid)} — "
                            f"{vol}/{cap} vehicles, speed={speed:.1f}km/h "
                            f"(free_flow={self.edge_states[eid].free_flow_speed_kmh:.0f}km/h)"
                        )

                    logger.info(
                        f"[SIM] Tick {self.current_tick}: active={active}, "
                        f"arrived={arrived}/{len(self.vehicles)}, congested_edges={len(congested)}"
                    )

                # Record traffic every 5 ticks
                if self.current_tick % 5 == 0:
                    self._record_edge_traffic()

                # Progress callback
                if on_progress:
                    on_progress(self.current_tick, max_ticks)

                # Check if all vehicles arrived
                if (
                    self.current_tick > 20
                    and self._all_vehicles_arrived()
                    and len(self.vehicles) > 0
                ):
                    self.sim_log.write(
                        f"\n>>> All {len(self.vehicles)} vehicles arrived at tick {self.current_tick}"
                    )
                    logger.info(
                        f"[SIM] All {len(self.vehicles)} vehicles arrived at tick {self.current_tick}"
                    )
                    break

                self.current_tick += 1

            # Whatever is still moving when the loop ends has to be counted too.
            self._record_non_arrivals()
            # Log sample vehicle summaries
            self.sim_log.header("SAMPLE VEHICLE TRIP SUMMARIES")
            for route_pk, vid in self.sample_vehicles.items():
                v = self.vehicles.get(vid)
                if v:
                    self.sim_log.write(
                        f"  {self.sim_log._route_label(route_pk)}: "
                        f"total_time={v.total_travel_time_min:.1f}min, "
                        f"congestion_delay={v.congestion_delay_min:.2f}min, "
                        f"arrived={'YES' if v.arrived else 'NO'}"
                    )

            # Calculate final results
            self._calculate_results()

            # Update simulation status
            self.simulation_result.status = SimulationResult.Status.COMPLETED
            self.simulation_result.detailed_log = self.sim_log.get_text()
            self.simulation_result.save()

            logger.info(
                f"[SIM] Simulation completed: {self.current_tick} ticks, "
                f"CO2={self.simulation_result.total_co2_g:.0f}g"
            )

        except Exception as e:
            logger.exception(f"[SIM] Simulation failed: {e}")
            if self.simulation_result:
                self.simulation_result.status = SimulationResult.Status.FAILED
                self.simulation_result.detailed_log = self.sim_log.get_text()
                self.simulation_result.save()
            raise e

        return self.simulation_result

    def _calculate_results(self):
        """Calculate final results and store in database."""
        logger.info(f"[SIM] Calculating results for {len(self.agent_results)} agents")

        self.sim_log.header("RESULTS — PER ROUTE")

        total_co2 = 0.0
        total_cost = 0.0

        for route_pk, results in self.agent_results.items():
            route = self.agent_routes.get(route_pk)
            if not route:
                logger.warning(f"[SIM] No route found for route_pk {route_pk}")
                self.sim_log.write(f"  WARNING: No route found for route_pk {route_pk}")
                continue

            trip_times = results["trip_times"]
            delays = results["delays"]

            if not trip_times:
                # Nothing departed on this route at all — after
                # _record_non_arrivals() this no longer means "nobody arrived".
                # There is no measurement to report, so the pathfinding estimate
                # stands in, and the log says that it is an estimate.
                logger.warning(
                    f"[SIM] No vehicles simulated for route_pk {route_pk} — "
                    f"reporting the pathfinding estimate"
                )
                self.sim_log.write(
                    f"  NOT SIMULATED: {self.sim_log._route_label(route_pk)} — "
                    f"no vehicle departed; the time below is the pathfinding "
                    f"estimate, not a measurement"
                )
                mean_trip_time = route.estimated_time_min
                min_trip_time = route.estimated_time_min
                max_trip_time = route.estimated_time_min
                mean_delay = 0.0
            else:
                mean_trip_time = sum(trip_times) / len(trip_times)
                min_trip_time = min(trip_times)
                max_trip_time = max(trip_times)
                mean_delay = sum(delays) / len(delays) if delays else 0.0

            # Calculate CO2 and cost based on mode and segments
            co2, cost = self._calculate_emissions_and_cost(route)
            total_co2 += co2
            total_cost += cost

            co2_per_person = co2 / self.people_per_agent if self.people_per_agent else 0
            cost_per_person = (
                cost / self.people_per_agent if self.people_per_agent else 0
            )

            self.sim_log.subheader(self.sim_log._route_label(route_pk))
            self.sim_log.write(f"  Distance: {route.total_distance_m:.0f}m")
            self.sim_log.write(
                f"  Estimated time (pathfinding): {route.estimated_time_min:.1f}min"
            )
            self.sim_log.write(
                f"  Simulated trip time: "
                f"mean={mean_trip_time:.1f}min, min={min_trip_time:.1f}min, max={max_trip_time:.1f}min"
            )
            self.sim_log.write(f"  Mean congestion delay: {mean_delay:.2f}min")
            self.sim_log.write(
                f"  Vehicles arrived: {len(trip_times)}/{self.people_per_agent}"
            )
            self.sim_log.write(
                f"  CO2: {co2:.0f}g total ({co2_per_person:.1f}g per person, {co2 / 1000:.2f}kg total)"
            )
            self.sim_log.write(
                f"  Cost: €{cost:.2f} total (€{cost_per_person:.4f} per person)"
            )

            # Per-segment emission breakdown
            segments = self.route_segments.get(route_pk, [])
            for seg in segments:
                es = self.edge_states.get(seg.edge_id)
                if not es:
                    continue
                dist_km = es.distance_m / 1000
                if seg.mode == "car":
                    seg_co2 = CAR_EMISSIONS_G_PER_KM * dist_km
                    self.sim_log.write(
                        f"    seg {seg.order} ({seg.mode}): {es.distance_m:.0f}m → "
                        f"{seg_co2:.1f}g/person × {self.people_per_agent} = {seg_co2 * self.people_per_agent:.0f}g"
                    )
                elif seg.mode == "bus":
                    cap = self._get_pt_capacity(seg.pt_line_id, "bus")
                    seg_co2 = BUS_EMISSIONS_G_PER_VEHICLE_KM * dist_km / cap
                    self.sim_log.write(
                        f"    seg {seg.order} ({seg.mode}, cap={cap:.0f}): {es.distance_m:.0f}m → "
                        f"{seg_co2:.2f}g/person × {self.people_per_agent} = {seg_co2 * self.people_per_agent:.0f}g"
                    )
                elif seg.mode == "train":
                    cap = self._get_pt_capacity(seg.pt_line_id, "train")
                    seg_co2 = TRAIN_EMISSIONS_G_PER_VEHICLE_KM * dist_km / cap
                    self.sim_log.write(
                        f"    seg {seg.order} ({seg.mode}, cap={cap:.0f}): {es.distance_m:.0f}m → "
                        f"{seg_co2:.2f}g/person × {self.people_per_agent} = {seg_co2 * self.people_per_agent:.0f}g"
                    )
                else:
                    self.sim_log.write(
                        f"    seg {seg.order} ({seg.mode}): {es.distance_m:.0f}m → 0g (zero emission)"
                    )

            logger.debug(
                f"[SIM] Route {route_pk} (agent {route.agent_id}, {route.transport_mode}): "
                f"trips={len(trip_times)}, avg_time={mean_trip_time:.1f}min, "
                f"avg_delay={mean_delay:.1f}min, CO2={co2:.0f}g, cost={cost:.2f}EUR"
            )

            # Create agent result
            AgentSimulationResult.objects.create(
                simulation=self.simulation_result,
                agent_route=route,
                mean_trip_time_min=mean_trip_time,
                mean_cost_eur=cost / self.people_per_agent
                if self.people_per_agent
                else 0.0,
                total_co2_g=co2,
                congestion_delay_min=mean_delay,
            )

        # Totals
        self.sim_log.header("TOTALS")
        self.sim_log.write(f"Total CO2: {total_co2:.0f}g ({total_co2 / 1000:.2f}kg)")
        self.sim_log.write(f"Total cost: €{total_cost:.2f}")
        self.sim_log.write(f"Routes processed: {len(self.agent_results)}")

        # Update totals
        self.simulation_result.total_co2_g = total_co2
        self.simulation_result.total_cost_eur = total_cost
        self.simulation_result.save()

        logger.info(
            f"[SIM] Total CO2: {total_co2:.0f}g, Total cost: {total_cost:.2f}EUR"
        )

        # Update street speeds for next round
        self._update_street_speeds()

    def _calculate_emissions_and_cost(self, route: AgentRoute) -> tuple[float, float]:
        """
        Calculate CO2 emissions and cost for an agent's route.

        Uses Mobility model emission/cost factors per segment:
        - Car: 166.8 g/vehicle-km, each person drives alone → per-person = per-vehicle
        - Bus: 1200 g/vehicle-km ÷ capacity = per-person g/km
        - Train: 3500 g/vehicle-km ÷ capacity = per-person g/km
        - Bike/Walk: 0 emissions, 0 cost

        Returns:
            Tuple of (total_co2_g, total_cost_eur) for all people_per_agent persons.
        """
        segments = self.route_segments.get(route.pk, [])
        if not segments:
            return 0.0, 0.0

        total_co2_per_person = 0.0
        total_cost_per_person = 0.0

        for seg in segments:
            edge_state = self.edge_states.get(seg.edge_id)
            if not edge_state:
                continue

            distance_km = edge_state.distance_m / 1000

            if seg.mode == "car":
                total_co2_per_person += CAR_EMISSIONS_G_PER_KM * distance_km
                total_cost_per_person += CAR_COST_PER_KM * distance_km

            elif seg.mode == "bus":
                # Get bus capacity for per-person calculation
                capacity = self._get_pt_capacity(seg.pt_line_id, "bus")
                total_co2_per_person += (
                    BUS_EMISSIONS_G_PER_VEHICLE_KM * distance_km / capacity
                )
                total_cost_per_person += (
                    BUS_COST_PER_VEHICLE_KM * distance_km / capacity
                )

            elif seg.mode == "train":
                # Get train capacity for per-person calculation
                capacity = self._get_pt_capacity(seg.pt_line_id, "train")
                total_co2_per_person += (
                    TRAIN_EMISSIONS_G_PER_VEHICLE_KM * distance_km / capacity
                )
                total_cost_per_person += (
                    TRAIN_COST_PER_VEHICLE_KM * distance_km / capacity
                )

            # bike and walk: 0 emissions, 0 cost

        # Multiply by people_per_agent (each agent represents N persons)
        total_co2 = total_co2_per_person * self.people_per_agent
        total_cost = total_cost_per_person * self.people_per_agent

        return total_co2, total_cost

    def _get_pt_capacity(self, pt_line_id: int | None, mode: str) -> float:
        """Get the passenger capacity for a PT line. Returns a default if not found."""
        if not pt_line_id:
            return 60.0 if mode == "bus" else 500.0

        if mode == "bus":
            if not hasattr(self, "_bus_capacities"):
                self._bus_capacities: dict[int, int] = {}
            if pt_line_id not in self._bus_capacities:
                bus_line = BusLine.objects.filter(id=pt_line_id).first()
                self._bus_capacities[pt_line_id] = (
                    bus_line.bus_capacity if bus_line else 60
                )
            return max(1.0, float(self._bus_capacities[pt_line_id]))

        if mode == "train":
            if not hasattr(self, "_train_capacities"):
                self._train_capacities: dict[int, int] = {}
            if pt_line_id not in self._train_capacities:
                train_line = TrainLine.objects.filter(id=pt_line_id).first()
                self._train_capacities[pt_line_id] = (
                    train_line.train_capacity if train_line else 500
                )
            return max(1.0, float(self._train_capacities[pt_line_id]))

        return 60.0

    def _get_pt_interval(self, pt_line_id: int | None, mode: str) -> int:
        """Get the interval in minutes for a PT line. Returns a fallback if not found."""
        if not pt_line_id:
            return (
                FALLBACK_BUS_INTERVAL_MIN
                if mode == "bus"
                else FALLBACK_TRAIN_INTERVAL_MIN
            )

        if mode == "bus":
            return self.bus_line_intervals.get(pt_line_id, FALLBACK_BUS_INTERVAL_MIN)

        if mode == "train":
            return self.train_line_intervals.get(
                pt_line_id, FALLBACK_TRAIN_INTERVAL_MIN
            )

        return FALLBACK_BUS_INTERVAL_MIN

    def _update_street_speeds(self):
        """Update StreetPerRound with average speeds from simulation."""
        # Calculate average speed per edge
        edge_speeds: dict[int, list[float]] = defaultdict(list)

        for snapshot in EdgeTrafficSnapshot.objects.filter(
            simulation=self.simulation_result
        ):
            edge_speeds[snapshot.edge_id].append(snapshot.speed_kmh)

        # Update or create StreetPerRound records
        for edge_id, speeds in edge_speeds.items():
            avg_speed = sum(speeds) / len(speeds) if speeds else None
            if avg_speed:
                # Find StreetEdge for this edge
                from maps.models import StreetEdge

                street_edge = StreetEdge.objects.filter(edge_id=edge_id).first()
                if street_edge:
                    StreetPerRound.objects.update_or_create(
                        edge=street_edge,
                        game_round=self.game_round,
                        defaults={"speed_under_load": int(avg_speed)},
                    )


def run_round_simulation(game_round: GameRound) -> SimulationResult:
    """
    Convenience function to run simulation for a game round.

    Args:
        game_round: The GameRound to simulate

    Returns:
        SimulationResult with computed statistics
    """
    # Get scale from game map
    scale = game_round.game.game_map.scale if game_round.game.game_map else 100.0

    simulator = TrafficSimulator(game_round, scale=scale)
    return simulator.run_simulation()
