import bisect
import logging
import math
import random
from collections.abc import Callable

from maps.models import BusLine, Edge, StreetPerRound, TrainLine

from game.models import (
    AgentRoute,
    AgentSimulationResult,
    EdgeTrafficSnapshot,
    GameRound,
    RouteSegment,
    SimulationResult,
)

# The engine itself lives in `sim/`, a plain package with no Django in it.
# This module is the adapter: ORM rows in, engine, result rows out. The names
# are re-exported rather than re-homed because ~25 call sites across the test
# suite, and `game/signals.py`, import them from here — the extraction is
# meant to be invisible above this seam.
from sim import (  # noqa: F401
    BUS_COST_PER_VEHICLE_KM,
    BUS_EMISSIONS_G_PER_VEHICLE_KM,
    BUS_PCU,
    CAR_COST_PER_KM,
    CAR_COST_TRAFFIC_SHARE,
    CAR_EF_DRAG_TERM,
    CAR_EF_IDLE_TERM,
    CAR_EF_MIN_SPEED_KMH,
    CAR_EF_ROLLING_TERM,
    CAR_EMISSIONS_G_PER_KM,
    DEADLOCK_TICKS,
    JAM_DENSITY_VEH_PER_KM_LANE,
    MAX_CAR_EMISSION_FACTOR,
    SATURATION_FLOW_VEH_PER_H_LANE,
    TRAIN_COST_PER_VEHICLE_KM,
    TRAIN_EMISSIONS_G_PER_VEHICLE_KM,
    EdgeState,
    PTVehicle,
    QueuedVehicle,
    Segment,
    SimulationLog,
    Vehicle,
    car_cost_eur_per_km,
    car_emissions_g_per_km,
    draw_capacity_factor,
    draw_driver_speed_factor,
    generate_departure_minutes,
)


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

# Departure window: matches the ±60 min clamp in generate_departure_minutes()
DEPARTURE_WINDOW_MIN = 120







class TrafficSimulator:
    """
    Main simulation engine for traffic simulation.

    Simulates the movement of vehicles through the network,
    accounting for congestion and public transport dynamics.
    """

    def __init__(
        self,
        game_round: GameRound,
        scale: float = 100.0,
        seed: int | None = None,
    ):
        """
        Initialize the simulator.

        Args:
            game_round: The game round to simulate
            scale: Meters per coordinate unit (for distance calculation)
            seed: Seed for this round's draws. Defaults to the round pk, so a
                round always replays identically — in a test, in a debugger, or
                after a worker restart. Pass one explicitly to sweep the same
                round over many seeds (calibration), which is the only reason
                the argument exists.
        """
        self.game_round = game_round
        self.scale = scale
        self.simulation_result: SimulationResult | None = None
        # A generator of its own rather than module-level `random`: the module
        # generator is process-wide shared state, so anything else drawing from
        # it would shift this round's departures.
        self.seed = game_round.pk if seed is None else seed
        self.rng = random.Random(self.seed)

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
        self.route_segments: dict[int, list[Segment]] = {}

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
        self.departure_schedule: dict[int, list[tuple[int, float]]] = {}

        # Results tracking
        self.agent_results: dict[int, dict] = {}  # route_pk -> results dict

        # Current simulation tick
        self.current_tick = 0

        # Callback for progress updates
        self.on_progress: Callable[[int, int], None] | None = None

        # Detailed simulation log
        self.sim_log = SimulationLog()

        # Sample vehicle IDs: route_pk -> vehicle_id (person_index=0, for detailed logging)
        self.sample_vehicles: dict[int, int] = {}

        # Load routes and initialize edges during construction
        self._load_routes()
        self._initialize_edges()
        self.free_running: set[int] = set()
        self.waiting: list[tuple[float, int, int]] = []
        self.forced_releases = 0

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
                # Convert the model rows into the engine's own Segment: four
                # fields and no Django. This is the whole of what used to tie
                # the tick loop to the database — every other thing it touches
                # was already a plain dataclass.
                segments = [
                    Segment(
                        edge_id=row.edge_id,  # type: ignore
                        order=row.order,
                        mode=row.mode,
                        pt_line_id=row.pt_line_id,  # type: ignore
                    )
                    for row in route.segments.order_by("order")  # type: ignore
                ]
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

            car_lanes = lanes
            if has_dedicated_bus_lane:
                car_lanes = max(0, lanes - 1)
                if car_lanes == 0:
                    logger.info(
                        "[SIM] Edge %s is a bus gate: closed to cars, open to "
                        "buses, bikes and pedestrians.",
                        edge.pk,
                    )

            self.edge_states[edge.pk] = EdgeState(
                edge_id=edge.pk,
                distance_m=distance_m,
                free_flow_speed_kmh=speed_limit,
                car_lanes=car_lanes,
                has_dedicated_bus_lane=has_dedicated_bus_lane,
                # Once per link per round. This is the dial that makes two
                # rounds with identical choices come back with different
                # numbers, and it is drawn here rather than per tick because
                # a road's capacity on a given day is one draw, not a fresh
                # surprise every five minutes.
                capacity_factor=draw_capacity_factor(self.rng),
            )

            # Build edge name for logging
            start_name = edge.start_node.name or f"Node {edge.start_node.pk}"
            end_name = edge.end_node.name or f"Node {edge.end_node.pk}"
            edge_names[edge.pk] = f"{start_name} → {end_name}"

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
        # Everything here is in minutes from the start of the departure window,
        # which opens at (base_hour - 1) * 60. generate_departure_minutes uses
        # the same time-zero, so 0.0 is the first minute of the window.

        for route_pk in self.agent_routes:
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
                    num_vehicles,
                    base_hour,
                    self.departure_std_dev_min,
                    rng=self.rng,
                )
                self.departure_schedule[route_pk] = list(enumerate(departures))

    def _queues_for_traffic(self, mode: str, edge_state: "EdgeState") -> bool:
        """Cars queue; buses queue only in mixed traffic."""
        if mode == "car":
            return True
        if mode == "bus":
            return not edge_state.has_dedicated_bus_lane
        return False

    def _pcu_for(self, mode: str) -> float:
        return BUS_PCU if mode == "bus" else 1.0

    def _state_for_segment(self, route_pk: int, segment_index: int):
        """The link a route's Nth segment runs on, or None past the end."""
        segments = self.route_segments.get(route_pk, [])
        if segment_index >= len(segments):
            return None
        return self.edge_states.get(segments[segment_index].edge_id)  # type: ignore

    def _free_speed_for(self, vehicle: Vehicle, edge_state: "EdgeState") -> float:
        """Uncongested speed for this vehicle on this link."""
        segments = self.route_segments.get(vehicle.route_pk, [])
        segment = segments[vehicle.segment_index]
        if vehicle.mode == "bus":
            if segment.pt_line_id and segment.pt_line_id in self.bus_line_speeds:
                return float(self.bus_line_speeds[segment.pt_line_id])
            return float(FALLBACK_BUS_SPEED_KMH)
        if vehicle.mode == "train":
            if segment.pt_line_id and segment.pt_line_id in self.train_line_speeds:
                return float(self.train_line_speeds[segment.pt_line_id])
            return float(FALLBACK_TRAIN_SPEED_KMH)
        if vehicle.mode == "bike":
            return float(self.bike_speed_kmh)
        if vehicle.mode == "walk":
            return float(self.walk_speed_kmh)
        # Cars only. A bus and a train run to a timetable rather than to a
        # driver's taste, and bikes and walkers do not queue, so a spread
        # there would add noise to numbers nothing is arguing about without
        # touching the mechanism this dial exists to feed.
        limit = edge_state.free_flow_speed_kmh or float(self.default_car_speed_kmh)
        return limit * vehicle.speed_factor

    def _enter_edge(self, vehicle_id: int, vehicle: Vehicle, at_min: float) -> bool:
        """Put a vehicle onto its current segment. False if the link is full."""
        edge_state = self._state_for_segment(vehicle.route_pk, vehicle.segment_index)
        if edge_state is None:
            vehicle.arrived = True
            vehicle.arrived_min = at_min
            return True

        speed = self._free_speed_for(vehicle, edge_state)
        travel_min = edge_state.distance_m / 1000.0 / speed * 60.0 if speed > 0 else 0.0
        vehicle.entered_edge_min = at_min
        vehicle.ready_at_min = at_min + travel_min

        if not self._queues_for_traffic(vehicle.mode, edge_state):
            vehicle.queued = False
            self.free_running.add(vehicle_id)
            return True

        if vehicle.mode == "car" and not edge_state.open_to_cars:
            logger.error(
                "[SIM] Car routed over edge %s, which is a bus lane closed to "
                "cars. Letting it through on one lane so the round completes — "
                "the route should have been rejected at submit.",
                edge_state.edge_id,
            )

        pcu = self._pcu_for(vehicle.mode)
        if not edge_state.has_room_for(pcu):
            return False

        queued = QueuedVehicle(
            vehicle_id=vehicle_id,
            ready_at_min=vehicle.ready_at_min,
            pcu=pcu,
            entered_at_min=at_min,
        )
        if edge_state.car_lanes > 1:
            # Overtaking, and the reason it is here rather than folded into a
            # smaller sigma. Giving drivers different speeds against a strict
            # FIFO queue means one slow driver at the head holds up everyone
            # behind — correct on a single lane, where you genuinely cannot
            # pass, and wrong on a multi-lane street, where the effect would
            # be a jam the road does not have. (It is why MATSim gives every
            # vehicle the same link speed.) Keeping the queue ordered by when
            # each vehicle is ready to leave IS overtaking; shrinking sigma
            # instead would only hide the missing mechanism.
            bisect.insort(edge_state.queue, queued, key=lambda q: q.ready_at_min)
        else:
            edge_state.queue.append(queued)
        edge_state.occupancy_pcu += pcu
        edge_state.peak_occupancy_pcu = max(
            edge_state.peak_occupancy_pcu, edge_state.occupancy_pcu
        )
        vehicle.queued = True
        return True

    def _spawn_vehicles(self, now: float, tick_end: float):
        """Release everyone who wanted to leave by the end of this tick.

        self.waiting is sorted by wanted departure across ALL routes. A vehicle
        whose first link is full stays in the list and tries again next tick —
        it is waiting at the front door, and its clock runs from when it wanted
        to leave, not from when the street let it in.
        """
        still_waiting = []
        for depart_min, route_pk, person_index in self.waiting:
            if depart_min > tick_end:
                still_waiting.append((depart_min, route_pk, person_index))
                continue

            segments = self.route_segments.get(route_pk, [])
            if not segments:
                continue

            _, passenger_count = self.route_vehicle_scaling.get(
                route_pk, (self.people_per_agent, 1)
            )
            vehicle = Vehicle(
                route_pk=route_pk,
                person_index=person_index,
                mode=segments[0].mode,
                segment_index=0,
                passenger_count=passenger_count,
                wants_to_depart_min=depart_min,
                departed=True,
                # Once, here, for the whole trip.
                speed_factor=draw_driver_speed_factor(self.rng),
            )
            vehicle_id = self.next_vehicle_id
            if self._enter_edge(vehicle_id, vehicle, max(depart_min, now)):
                self.next_vehicle_id += 1
                self.vehicles[vehicle_id] = vehicle
                if person_index == 0:
                    self.sample_vehicles[route_pk] = vehicle_id
            else:
                still_waiting.append((depart_min, route_pk, person_index))

        self.waiting = still_waiting

    def _discharge(
        self, edge_state: "EdgeState", now: float, tick_end: float, released: set[int]
    ) -> bool:
        """Release from the head of the queue while budget and space allow."""
        moved = False
        while edge_state.queue:
            head = edge_state.queue[0]
            if head.pcu > edge_state.release_budget:
                break
            if head.ready_at_min > tick_end:
                # The head has not finished crossing yet, and FIFO means
                # nobody behind it can pass either.
                break

            vehicle = self.vehicles[head.vehicle_id]
            next_state = self._state_for_segment(
                vehicle.route_pk, vehicle.segment_index + 1
            )

            if next_state is not None and not next_state.has_room_for(head.pcu):
                if self.current_tick - edge_state.blocked_since_tick < DEADLOCK_TICKS:
                    break
                self.forced_releases += 1
                forced = True
            else:
                forced = False

            left_at = max(head.ready_at_min, now)
            edge_state.queue.pop(0)
            edge_state.occupancy_pcu -= head.pcu
            edge_state.release_budget -= head.pcu
            if vehicle.mode == "car":
                # Cars only — see EdgeState.mean_speed_kmh. A bus runs at its
                # own line speed and would drag the mean the same way a walker
                # would.
                edge_state.traversal_count += 1
                edge_state.traversal_time_min += left_at - head.entered_at_min
            released.add(edge_state.edge_id)
            moved = True

            vehicle.segment_index += 1
            segments = self.route_segments.get(vehicle.route_pk, [])
            if vehicle.segment_index >= len(segments):
                vehicle.arrived = True
                vehicle.arrived_min = left_at
            else:
                vehicle.mode = segments[vehicle.segment_index].mode
                if forced or not self._enter_edge(head.vehicle_id, vehicle, left_at):
                    # Forced past a full link: put it there anyway, over
                    # storage. This only happens after DEADLOCK_TICKS.
                    self._force_enter(head.vehicle_id, vehicle, left_at)
        return moved

    def _force_enter(self, vehicle_id: int, vehicle: Vehicle, at_min: float):
        """Enter a full link regardless of storage (deadlock escape only)."""
        edge_state = self._state_for_segment(vehicle.route_pk, vehicle.segment_index)
        if edge_state is None:
            vehicle.arrived = True
            vehicle.arrived_min = at_min
            return
        pcu = self._pcu_for(vehicle.mode)
        speed = self._free_speed_for(vehicle, edge_state)
        travel_min = edge_state.distance_m / 1000.0 / speed * 60.0 if speed > 0 else 0.0
        vehicle.entered_edge_min = at_min
        vehicle.ready_at_min = at_min + travel_min
        vehicle.queued = True
        edge_state.queue.append(
            QueuedVehicle(vehicle_id, vehicle.ready_at_min, pcu, at_min)
        )
        edge_state.occupancy_pcu += pcu

    def _advance_free_running(self, now: float, tick_end: float):
        """Move everything that does not interact with car traffic."""
        done = []
        for vehicle_id in self.free_running:
            vehicle = self.vehicles[vehicle_id]
            while not vehicle.arrived and vehicle.ready_at_min <= tick_end:
                left_at = vehicle.ready_at_min
                segments = self.route_segments.get(vehicle.route_pk, [])
                # Deliberately NOT recorded into the edge's traversal stats:
                # nothing here is a car, and this is the number that becomes
                # the street's speed (see EdgeState.mean_speed_kmh).
                vehicle.segment_index += 1
                if vehicle.segment_index >= len(segments):
                    vehicle.arrived = True
                    vehicle.arrived_min = left_at
                    done.append(vehicle_id)
                    break
                vehicle.mode = segments[vehicle.segment_index].mode
                if not self._enter_edge(vehicle_id, vehicle, left_at):
                    # It has just joined mixed traffic and the link is full;
                    # it waits where it is and retries next tick.
                    vehicle.segment_index -= 1
                    vehicle.ready_at_min = tick_end
                    break
                if vehicle.queued:
                    done.append(vehicle_id)  # it is a queue's problem now
                    break
        for vehicle_id in done:
            self.free_running.discard(vehicle_id)

    def _advance_traffic(self):
        """One simulation tick."""
        now = self.current_tick * self.tick_duration_min
        tick_end = now + self.tick_duration_min

        for edge_state in self.edge_states.values():
            edge_state.release_budget = edge_state.flow_per_tick(self.tick_duration_min)

        self._spawn_vehicles(now, tick_end)
        self._advance_free_running(now, tick_end)

        # A vehicle may cross several links within one tick — its own clock
        # (ready_at_min) is what bounds it, not the tick. So keep making
        # passes until nothing moves.
        released: set[int] = set()
        moved = True
        while moved:
            moved = False
            for edge_state in self.edge_states.values():
                if self._discharge(edge_state, now, tick_end, released):
                    moved = True

        # A link is in trouble only if it moved NOTHING this tick while holding
        # a vehicle. Counting blocked *passes* instead of ticks makes the
        # storage limit leak — a queue overran its storage 34-fold in testing.
        for edge_id, edge_state in self.edge_states.items():
            if edge_id in released or not edge_state.queue:
                edge_state.blocked_since_tick = self.current_tick

    def _record_edge_traffic(self):
        """Record traffic snapshot for each edge."""
        if not self.simulation_result:
            return

        snapshots = []
        for edge_id, state in self.edge_states.items():
            if state.queue or state.traversal_count:
                snapshots.append(
                    EdgeTrafficSnapshot(
                        simulation=self.simulation_result,
                        edge_id=edge_id,
                        time_tick=self.current_tick,
                        vehicle_count=len(state.queue),
                        speed_kmh=state.mean_speed_kmh,
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

    def _record_arrivals(self):
        """Book every arrived vehicle at its measured door-to-door time.

        The clock starts when the person WANTED to leave, not when the street
        let them in: waiting at the front door because the road outside is
        full is part of the trip, and hiding it would make the worst rounds
        look the cheapest.
        """
        for vehicle in self.vehicles.values():
            if not vehicle.arrived or vehicle.arrived_min is None:
                continue
            agent_results = self.agent_results.get(vehicle.route_pk)
            if not agent_results:
                continue
            wait_min = self.route_pt_wait_min.get(vehicle.route_pk, 0.0)
            trip_min = vehicle.arrived_min - vehicle.wants_to_depart_min + wait_min
            delay_min = max(
                0.0,
                trip_min
                - self._free_flow_min(vehicle.route_pk, vehicle.speed_factor),
            )
            for _ in range(vehicle.passenger_count):
                agent_results["trip_times"].append(trip_min)
                agent_results["delays"].append(delay_min)

    def _free_flow_min(self, route_pk: int, speed_factor: float = 1.0) -> float:
        """The route's uncongested time — the baseline the delay is against.

        Measured against THIS driver's free-flow speed, not the speed limit.
        A driver who wants to do 45 in a 50 zone arrives later than the limit
        allows and is not delayed by anything; billing the difference as
        congestion delay would report a jam on an empty road. The factor
        applies to car segments only, which is the only mode it is drawn for.
        """
        total = 0.0
        for segment in self.route_segments.get(route_pk, []):
            edge_state = self.edge_states.get(segment.edge_id)  # type: ignore
            if not edge_state:
                continue
            speed = edge_state.free_flow_speed_kmh * speed_factor
            if segment.mode == "bike":
                speed = float(self.bike_speed_kmh)
            elif segment.mode == "walk":
                speed = float(self.walk_speed_kmh)
            elif segment.mode in ("bus", "train"):
                speed = float(
                    self.bus_line_speeds.get(
                        segment.pt_line_id or 0, FALLBACK_BUS_SPEED_KMH
                    )
                    if segment.mode == "bus"
                    else self.train_line_speeds.get(
                        segment.pt_line_id or 0, FALLBACK_TRAIN_SPEED_KMH
                    )
                )
            if speed > 0:
                total += edge_state.distance_m / 1000.0 / speed * 60.0
        return total

    def _record_non_arrivals(self):
        """Book the travellers who were still under way when time ran out.

        Two groups, and both have to be counted or the mean becomes a mean
        over survivors: vehicles still on a link, and people still at the
        front door because the first street never let them in. The second
        group is not in self.vehicles at all, so without this pass a route
        whose first link jammed would report only the lucky few.

        Their time is a lower bound — the clock stopped, the trip did not —
        which is what the log below says.
        """
        sim_end_min = self.current_tick * self.tick_duration_min
        stranded_routes = 0

        for vehicle in self.vehicles.values():
            if not vehicle.departed or vehicle.arrived:
                continue
            agent_results = self.agent_results.get(vehicle.route_pk)
            if not agent_results:
                continue
            wait_min = self.route_pt_wait_min.get(vehicle.route_pk, 0.0)
            elapsed = max(0.0, sim_end_min - vehicle.wants_to_depart_min) + wait_min
            delay = max(0.0, elapsed - self._free_flow_min(vehicle.route_pk))
            for _ in range(vehicle.passenger_count):
                agent_results["trip_times"].append(elapsed)
                agent_results["delays"].append(delay)
                agent_results["not_arrived"] += 1

        for depart_min, route_pk, _person_index in self.waiting:
            if depart_min > sim_end_min:
                # The simulation ended before this person wanted to leave at
                # all. Nothing happened to them, so nothing is recorded —
                # the same rule as an undeparted vehicle.
                continue
            agent_results = self.agent_results.get(route_pk)
            if not agent_results:
                continue
            _, passenger_count = self.route_vehicle_scaling.get(
                route_pk, (self.people_per_agent, 1)
            )
            wait_min = self.route_pt_wait_min.get(route_pk, 0.0)
            elapsed = sim_end_min - depart_min + wait_min
            delay = max(0.0, elapsed - self._free_flow_min(route_pk))
            for _ in range(passenger_count):
                agent_results["trip_times"].append(elapsed)
                agent_results["delays"].append(delay)
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
        on_progress: Callable[[int, int], None] | None = None,
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
                    es = self.edge_states.get(seg.edge_id)  # type: ignore
                    if es:
                        pt_info = ""
                        if seg.pt_line_id:
                            interval = self._get_pt_interval(seg.pt_line_id, seg.mode)
                            pt_info = (
                                f" | pt_line={seg.pt_line_id} | interval={interval}min"
                            )
                        self.sim_log.write(
                            f"    seg {seg.order}: {self.sim_log._edge_label(seg.edge_id)} | "  # type: ignore
                            f"mode={seg.mode} | dist={es.distance_m:.0f}m | "
                            f"free_flow={es.free_flow_speed_kmh:.0f}km/h "
                            f"({es.free_flow_min:.1f}min) | "
                            f"car_lanes={es.car_lanes} | "
                            f"storage={es.storage_capacity_pcu:.0f}pcu" + pt_info
                        )

            # Log edges
            self.sim_log.header("EDGES")
            for eid, es in sorted(self.edge_states.items()):
                self.sim_log.write(
                    f"  {self.sim_log._edge_label(eid)}: "
                    f"dist={es.distance_m:.0f}m, speed={es.free_flow_speed_kmh:.0f}km/h, "
                    f"car_lanes={es.car_lanes}, "
                    f"storage={es.storage_capacity_pcu:.0f}pcu, "
                    f"flow={es.flow_per_tick(self.tick_duration_min):.0f}pcu/tick"
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

            # Simulation loop. One call per tick: _advance_traffic() spawns,
            # moves the free-running modes and discharges every queue itself.
            self.current_tick = 0

            while self.current_tick < max_ticks:
                self._advance_traffic()

                # Log progress every 10 ticks to simulation log
                if self.current_tick % 10 == 0:
                    active = sum(
                        1
                        for v in self.vehicles.values()
                        if v.departed and not v.arrived
                    )
                    arrived = sum(1 for v in self.vehicles.values() if v.arrived)
                    queued = [
                        (eid, s)
                        for eid, s in self.edge_states.items()
                        if s.occupancy_pcu > s.storage_capacity_pcu * 0.5
                    ]
                    tick_line = (
                        f"[tick {self.current_tick:>3}] "
                        f"waiting_to_depart={len(self.waiting)}, active={active}, "
                        f"arrived={arrived}/{len(self.vehicles)}, "
                        f"queued_edges={len(queued)}, forced={self.forced_releases}"
                    )
                    self.sim_log.write(tick_line)

                    for eid, state in queued:
                        self.sim_log.write(
                            f"    QUEUE: {self.sim_log._edge_label(eid)} — "
                            f"{state.occupancy_pcu:.0f}/"
                            f"{state.storage_capacity_pcu:.0f}pcu in "
                            f"{len(state.queue)} vehicles, "
                            f"observed={state.mean_speed_kmh:.1f}km/h "
                            f"(free_flow={state.free_flow_speed_kmh:.0f}km/h)"
                        )

                    logger.info(
                        f"[SIM] Tick {self.current_tick}: "
                        f"waiting_to_depart={len(self.waiting)}, active={active}, "
                        f"arrived={arrived}/{len(self.vehicles)}, "
                        f"queued_edges={len(queued)}, forced={self.forced_releases}"
                    )

                # Record traffic every 5 ticks
                if self.current_tick % 5 == 0:
                    self._record_edge_traffic()

                # Progress callback
                if on_progress:
                    on_progress(self.current_tick, max_ticks)

                # Check if all vehicles arrived
                if not self.waiting and self._all_vehicles_arrived():
                    self.sim_log.write(
                        f"\n>>> All {len(self.vehicles)} vehicles arrived at tick {self.current_tick}"
                    )
                    logger.info(
                        f"[SIM] All {len(self.vehicles)} vehicles arrived at tick {self.current_tick}"
                    )
                    break

                self.current_tick += 1
            self._record_arrivals()
            # Whatever is still moving when the loop ends has to be counted too.
            self._record_non_arrivals()
            # Log sample vehicle summaries
            self.sim_log.header("SAMPLE VEHICLE TRIP SUMMARIES")
            for route_pk, vid in self.sample_vehicles.items():
                v = self.vehicles.get(vid)
                if not v:
                    continue
                free_flow = self._free_flow_min(route_pk)
                label = self.sim_log._route_label(route_pk)
                if v.arrived and v.arrived_min is not None:
                    trip_min = v.arrived_min - v.wants_to_depart_min
                    self.sim_log.write(
                        f"  {label}: wanted_to_leave={v.wants_to_depart_min:.1f}min, "
                        f"total_time={trip_min:.1f}min, "
                        f"free_flow={free_flow:.1f}min, "
                        f"congestion_delay={max(0.0, trip_min - free_flow):.2f}min, "
                        f"arrived=YES"
                    )
                else:
                    self.sim_log.write(
                        f"  {label}: wanted_to_leave={v.wants_to_depart_min:.1f}min, "
                        f"free_flow={free_flow:.1f}min, "
                        f"still on segment {v.segment_index}, arrived=NO"
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
            recorded = len(trip_times)
            not_arrived = results["not_arrived"]
            self.sim_log.write(
                f"  Travellers recorded: {recorded}/{self.people_per_agent}"
                + (f" — {not_arrived} of them still under way" if not_arrived else "")
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
                es = self.edge_states.get(seg.edge_id)  # type: ignore
                if not es:
                    continue
                dist_km = es.distance_m / 1000
                if seg.mode == "car":
                    speed = es.mean_speed_kmh
                    ef = car_emissions_g_per_km(speed)
                    seg_co2 = ef * dist_km
                    factor = ef / CAR_EMISSIONS_G_PER_KM
                    self.sim_log.write(
                        f"    seg {seg.order} ({seg.mode}): {es.distance_m:.0f}m at "
                        f"{speed:.1f}km/h → {seg_co2:.1f}g/person ({factor:.2f}× the "
                        f"50km/h rate, €{car_cost_eur_per_km(speed) * dist_km:.3f}/person) "
                        f"× {self.people_per_agent} = {seg_co2 * self.people_per_agent:.0f}g"
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
        - Car: speed-dependent, 166.8 g/vehicle-km at 50 km/h and up to twice
          that in stop-and-go (see car_emissions_g_per_km); each person drives
          alone → per-person = per-vehicle
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
                # The speed this link actually ran at this round, not the
                # speed limit: a jam burns more fuel per kilometre and eats
                # more brake, and that is what makes clearing one worth
                # voting for.
                speed_kmh = edge_state.mean_speed_kmh
                total_co2_per_person += car_emissions_g_per_km(speed_kmh) * distance_km
                total_cost_per_person += car_cost_eur_per_km(speed_kmh) * distance_km

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
        """Store each street's observed car speed for the next round.

        This is what StreetPerRound.speed_under_load has always been for. It
        was written from a mean over snapshots that were themselves means; now
        it is the one figure the run measured, and step 9 serves it to the
        route preview.
        """
        from maps.models import StreetEdge

        for edge_id, state in self.edge_states.items():
            if not state.traversal_count:
                continue
            street_edge = StreetEdge.objects.filter(edge_id=edge_id).first()
            if street_edge:
                StreetPerRound.objects.update_or_create(
                    edge=street_edge,
                    game_round=self.game_round,
                    defaults={"speed_under_load": max(1, int(state.mean_speed_kmh))},
                )
