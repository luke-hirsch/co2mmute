import io
import logging
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

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


@dataclass
class Vehicle:
    """Represents a single vehicle/person in the simulation."""

    route_pk: int
    person_index: int  # 0-999 for each agent
    mode: str  # car, bus, train, bike, walk
    segment_index: int  # Current segment in route
    position_on_edge_m: float  # Position along current edge
    total_travel_time_min: float = 0.0
    congestion_delay_min: float = 0.0
    departed: bool = False
    arrived: bool = False
    waiting_for_pt: bool = False
    pt_vehicle_id: Optional[int] = None
    passenger_count: int = 1  # Number of people this vehicle carries (>1 for PT vehicles)


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
        self._edge_names: Dict[int, str] = {}  # edge_id -> name
        self._route_labels: Dict[int, str] = {}  # route_pk -> "Player/Agent#N (mode)"
        # Per-edge per-route sample tracking: (route_pk, edge_id) -> {enter_tick, exit_tick, ...}
        self._sample_edge_events: Dict[Tuple[int, int], Dict] = {}

    def set_edge_names(self, edge_names: Dict[int, str]):
        self._edge_names = edge_names

    def set_route_labels(self, route_labels: Dict[int, str]):
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
class EdgeState:
    """State of an edge during simulation."""

    edge_id: int
    distance_m: float
    free_flow_speed_kmh: float
    capacity: int  # Number of cars at optimal flow
    lanes: int = 1
    has_dedicated_bus_lane: bool = False
    current_vehicles: Set[int] = field(
        default_factory=set
    )  # All vehicle IDs on this edge
    buses_on_dedicated_lane: Set[int] = field(
        default_factory=set
    )  # Buses using dedicated lane

    @property
    def volume(self) -> int:
        """Return traffic volume affecting congestion (excludes buses on dedicated lanes)."""
        return len(self.current_vehicles) - len(self.buses_on_dedicated_lane)

    @property
    def total_vehicles(self) -> int:
        """Return total number of vehicles (including all buses)."""
        return len(self.current_vehicles)

    def get_current_speed(self) -> float:
        """Calculate current speed using BPR function."""
        if self.capacity == 0:
            return self.free_flow_speed_kmh
        return bpr_speed(self.free_flow_speed_kmh, self.volume, self.capacity)


def bpr_speed(free_flow_speed: float, volume: int, capacity: int) -> float:
    """
    Bureau of Public Roads (BPR) function for calculating speed under congestion.

    speed = free_flow / (1 + 0.15 * (volume/capacity)^4)

    Args:
        free_flow_speed: Speed limit or free flow speed in km/h
        volume: Current number of vehicles on the edge
        capacity: Edge capacity (vehicles at optimal flow)

    Returns:
        Adjusted speed in km/h
    """
    if capacity <= 0:
        return free_flow_speed
    ratio = volume / capacity
    return free_flow_speed / (1 + 0.15 * (ratio**4))


def calculate_edge_capacity(
    distance_m: float, speed_limit_kmh: float = 50, lanes: int = 1
) -> int:
    """
    Calculate edge capacity based on length, speed limit, and lanes.

    Uses a more realistic capacity model:
    - Capacity per lane ≈ speed_limit * 15 vehicles per km per hour
    - This accounts for required spacing at different speeds
    - At 30 km/h: ~450 vehicles/km/lane (every 2.2m)
    - At 50 km/h: ~750 vehicles/km/lane (every 1.3m)
    - At 80 km/h: ~1200 vehicles/km/lane (every 0.8m)

    Args:
        distance_m: Edge length in meters
        speed_limit_kmh: Speed limit in km/h
        lanes: Number of lanes

    Returns:
        Capacity in number of vehicles
    """
    # Calculate capacity per lane per km
    capacity_per_lane_per_km = speed_limit_kmh * 15

    # Calculate total capacity for this edge
    distance_km = distance_m / 1000
    capacity = int(capacity_per_lane_per_km * lanes * distance_km)

    return max(1, capacity)


def generate_departure_times(
    num_people: int,
    base_hour: int,
    std_dev_min: float,
    tick_duration_min: int = 5,
) -> List[int]:
    """
    Generate departure times using normal distribution.

    Args:
        num_people: Number of departure times to generate
        base_hour: Base departure hour (e.g., 9 for 9:00 AM)
        std_dev_min: Standard deviation in minutes
        tick_duration_min: Duration of each tick in minutes

    Returns:
        List of departure ticks (tick buckets relative to simulation start)
    """
    base_minutes = base_hour * 60
    departures = []

    for _ in range(num_people):
        # Generate departure time with normal distribution
        departure_min = random.gauss(base_minutes, std_dev_min)
        # Clamp to reasonable range (1 hour before to 1 hour after base time)
        departure_min = max(base_minutes - 60, min(base_minutes + 60, departure_min))
        # Convert to tick (tick_duration_min buckets)
        tick = int((departure_min - (base_hour - 1) * 60) / tick_duration_min)
        departures.append(max(0, tick))

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
        self.simulation_result: Optional[SimulationResult] = None

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
        self.edge_states: Dict[int, EdgeState] = {}

        # Vehicles indexed by unique ID
        self.vehicles: Dict[int, Vehicle] = {}
        self.next_vehicle_id = 0

        # PT vehicles
        self.pt_vehicles: List[PTVehicle] = []

        # Route data indexed by route.pk (globally unique)
        self.agent_routes: Dict[int, AgentRoute] = {}
        self.route_segments: Dict[int, List[RouteSegment]] = {}

        # PT line speed cache: line_id -> speed_kmh
        self.bus_line_speeds: Dict[int, int] = {}
        self.train_line_speeds: Dict[int, int] = {}

        # PT line interval cache: line_id -> intervall_min
        self.bus_line_intervals: Dict[int, int] = {}
        self.train_line_intervals: Dict[int, int] = {}

        # Per-route PT wait time (interval/2): route_pk -> wait_min
        self.route_pt_wait_min: Dict[int, float] = {}

        # Vehicle scaling for PT routes: route_pk -> (num_vehicles, passenger_count)
        self.route_vehicle_scaling: Dict[int, Tuple[int, int]] = {}

        # Departure schedules: route_pk -> list of (person_index, departure_tick)
        self.departure_schedule: Dict[int, List[Tuple[int, int]]] = {}

        # Results tracking
        self.agent_results: Dict[int, Dict] = {}  # route_pk -> results dict

        # Current simulation tick
        self.current_tick = 0

        # Callback for progress updates
        self.on_progress: Optional[callable] = None

        # Detailed simulation log
        self.sim_log = SimulationLog()

        # Sample vehicle IDs: route_pk -> vehicle_id (person_index=0, for detailed logging)
        self.sample_vehicles: Dict[int, int] = {}

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
                segments = list(route.segments.order_by("order"))
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
                num_vehicles = max(1, round(DEPARTURE_WINDOW_MIN / min_interval))
                # Each vehicle carries min(capacity, ceil(people/vehicles)) passengers
                passenger_count = min(
                    int(min_pt_capacity),
                    math.ceil(self.people_per_agent / num_vehicles),
                )
                total_seats = num_vehicles * passenger_count
                overcapacity = total_seats < self.people_per_agent
                self.route_vehicle_scaling[route_pk] = (num_vehicles, passenger_count)
                self.route_pt_wait_min[route_pk] = min_interval / 2.0

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
            logger.info(f"[SIM] Loaded {len(self.bus_line_speeds)} bus line speeds/intervals")

        # Load train line speeds and intervals
        if train_line_ids:
            train_lines = TrainLine.objects.filter(id__in=train_line_ids)
            for train_line in train_lines:
                self.train_line_speeds[train_line.pk] = train_line.train_speed_kmh
                self.train_line_intervals[train_line.pk] = train_line.intervall
            logger.info(f"[SIM] Loaded {len(self.train_line_speeds)} train line speeds/intervals")

    def _initialize_edges(self):
        """Initialize edge states from the map."""
        # Get unique edges from all routes
        edge_ids = set()
        for segments in self.route_segments.values():
            for seg in segments:
                edge_ids.add(seg.edge_id)

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
            street_edge = edge.streetedge_set.first()
            if street_edge:
                speed_limit = street_edge.speed_limit
                lanes = street_edge.lanes
                has_dedicated_bus_lane = street_edge.dedicated_bus_lane
            else:
                speed_limit = self.default_car_speed_kmh
                lanes = 1
                has_dedicated_bus_lane = False

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
                # PT route: evenly spaced departures across the departure window
                pt_line_id = next(
                    (seg.pt_line_id for seg in segments if seg.mode == pt_mode), None
                )
                interval_min = self._get_pt_interval(pt_line_id, pt_mode)
                interval_ticks = max(1, round(interval_min / self.tick_duration_min))
                self.departure_schedule[route_pk] = [
                    (i, window_start_tick + i * interval_ticks)
                    for i in range(num_vehicles)
                ]
            else:
                # Car/bike/walk: random normal distribution (unchanged)
                departures = generate_departure_times(
                    num_vehicles,
                    base_hour,
                    self.departure_std_dev_min,
                    self.tick_duration_min,
                )
                self.departure_schedule[route_pk] = [
                    (i, tick) for i, tick in enumerate(departures)
                ]

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
                delay = self.tick_duration_min * max(
                    0, 1 - current_speed / base_speed
                ) if base_speed > 0 else 0
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
                    delay = self.tick_duration_min * max(
                        0, 1 - current_speed / bus_speed
                    ) if bus_speed > 0 else 0
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

    def run_simulation(
        self,
        max_ticks: int = 200,
        on_progress: Optional[callable] = None,
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
                    route_line += (
                        f", avg_wait={wait_min:.1f}min"
                        + (
                            f" [OVERCAPACITY: {total_seats}/{self.people_per_agent} seats]"
                            if overcap
                            else ""
                        )
                    )
                self.sim_log.write(route_line)
                for seg in segments:
                    es = self.edge_states.get(seg.edge_id)
                    if es:
                        pt_info = ""
                        if seg.pt_line_id:
                            interval = self._get_pt_interval(seg.pt_line_id, seg.mode)
                            pt_info = f" | pt_line={seg.pt_line_id} | interval={interval}min"
                        self.sim_log.write(
                            f"    seg {seg.order}: {self.sim_log._edge_label(seg.edge_id)} | "
                            f"mode={seg.mode} | dist={es.distance_m:.0f}m | "
                            f"free_flow={es.free_flow_speed_kmh:.0f}km/h | "
                            f"capacity={es.capacity} | lanes={es.lanes}"
                            + pt_info
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
                logger.warning(f"[SIM] No trip times recorded for route_pk {route_pk}")
                self.sim_log.write(
                    f"  WARNING: No trip times for {self.sim_log._route_label(route_pk)} "
                    f"(0/{self.people_per_agent} vehicles arrived)"
                )
                # Use pathfinding estimate as fallback — but still calculate CO2
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

    def _calculate_emissions_and_cost(self, route: AgentRoute) -> Tuple[float, float]:
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

    def _get_pt_capacity(self, pt_line_id: Optional[int], mode: str) -> float:
        """Get the passenger capacity for a PT line. Returns a default if not found."""
        if not pt_line_id:
            return 60.0 if mode == "bus" else 500.0

        if mode == "bus":
            if not hasattr(self, "_bus_capacities"):
                self._bus_capacities: Dict[int, int] = {}
            if pt_line_id not in self._bus_capacities:
                bus_line = BusLine.objects.filter(id=pt_line_id).first()
                self._bus_capacities[pt_line_id] = (
                    bus_line.bus_capacity if bus_line else 60
                )
            return max(1.0, float(self._bus_capacities[pt_line_id]))

        if mode == "train":
            if not hasattr(self, "_train_capacities"):
                self._train_capacities: Dict[int, int] = {}
            if pt_line_id not in self._train_capacities:
                train_line = TrainLine.objects.filter(id=pt_line_id).first()
                self._train_capacities[pt_line_id] = (
                    train_line.train_capacity if train_line else 500
                )
            return max(1.0, float(self._train_capacities[pt_line_id]))

        return 60.0

    def _get_pt_interval(self, pt_line_id: Optional[int], mode: str) -> int:
        """Get the interval in minutes for a PT line. Returns a fallback if not found."""
        if not pt_line_id:
            return FALLBACK_BUS_INTERVAL_MIN if mode == "bus" else FALLBACK_TRAIN_INTERVAL_MIN

        if mode == "bus":
            return self.bus_line_intervals.get(pt_line_id, FALLBACK_BUS_INTERVAL_MIN)

        if mode == "train":
            return self.train_line_intervals.get(pt_line_id, FALLBACK_TRAIN_INTERVAL_MIN)

        return FALLBACK_BUS_INTERVAL_MIN

    def _update_street_speeds(self):
        """Update StreetPerRound with average speeds from simulation."""
        # Calculate average speed per edge
        edge_speeds: Dict[int, List[float]] = defaultdict(list)

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
