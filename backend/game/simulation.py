import bisect
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

from maps.models import BusLine, Edge, StreetPerRound, TrainLine

# The engine itself lives in `sim/`
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
    PT_FARE_EUR,
    SATURATION_FLOW_VEH_PER_H_LANE,
    TRAIN_COST_PER_VEHICLE_KM,
    TRAIN_EMISSIONS_G_PER_VEHICLE_KM,
    EdgeState,
    PTLineState,
    PTVehicle,
    QueuedVehicle,
    Segment,
    SimulationLog,
    Vehicle,
    car_cost_eur_per_km,
    car_emissions_g_per_km,
    car_out_of_pocket_eur_per_km,
    draw_capacity_factor,
    draw_driver_speed_factor,
    generate_departure_minutes,
    node_chain,
)

from game.models import (
    AgentRoute,
    AgentSimulationResult,
    EdgeTrafficSnapshot,
    GameRound,
    SimulationResult,
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


@dataclass(frozen=True)
class PTLeg:
    """One unbroken run of a route's segments on one PT line.

    A route is a list of segments; a leg is the stretch of it spent on a single
    line. `first_index` and `last_index` are indices into that segment list, so
    a rider set down at the end of a leg resumes at `last_index + 1` — which is
    the walk to work, or the stop where it waits for the next line.
    """

    first_index: int
    last_index: int
    line_key: tuple[str, int]
    board_node: int
    alight_node: int


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
        self.held_at_origin: dict[int, int] = {}
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
        self.pt_by_vehicle: dict[int, PTVehicle] = {}

        # A line's own run through self.route_segments, under a key that cannot
        # be an AgentRoute pk. See §"the one structural idea".
        self.line_route_keys: dict[tuple[str, int], int] = {}

        # People standing at a stop: (line_key, node_id) -> vehicle ids, in the
        # order they got there. A rider waiting for M1 does not board U7, so the
        # line is part of the key.
        self.stop_queues: dict[tuple[tuple[str, int], int], list[int]] = {}

        # Which leg of which line each route rides: route_pk -> [PTLeg]
        self.route_pt_legs: dict[int, list[PTLeg]] = {}

        # Person-kilometres this route ACTUALLY rode on each line, accumulated
        # as people alight. Replaces the timetable guide's assumption that
        # everyone who submitted a PT route travelled on it.
        self.route_pt_person_km: dict[int, dict[tuple[str, int], float]] = {}

        # People on this route who boarded at least once, i.e. bought a ticket.
        self.route_fares: dict[int, int] = {}

        # Route data indexed by route.pk (globally unique)
        self.agent_routes: dict[int, AgentRoute] = {}
        self.route_segments: dict[int, list[Segment]] = {}

        # PT line speed cache: line_id -> speed_kmh
        self.bus_line_speeds: dict[int, int] = {}
        self.train_line_speeds: dict[int, int] = {}

        # PT line interval cache: line_id -> intervall_min
        self.bus_line_intervals: dict[int, int] = {}
        self.train_line_intervals: dict[int, int] = {}

        # PT sim in itself
        self.pt_lines: dict[tuple[str, int], PTLineState] = {}

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
        self._load_pt_legs()
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
                    "waits": [],
                    "mode": route.transport_mode,
                    "not_arrived": 0,
                }

        self.sim_log.set_route_labels(route_labels)
        logger.info(f"[SIM] Loaded {len(self.agent_routes)} agent routes")

        # Load PT line speeds and compute vehicle scaling
        self._load_pt_line_speeds()
        self._load_pt_lines()

    def _load_pt_lines(self):
        """Register every PT line on the map version this round runs on.

        Every line, not only the ridden ones: a timetable runs whether anyone
        is aboard or not, and a line nobody rides emitting nothing was the
        defect this guide exists to fix.

        `active_map_version` is set when the game starts (`GameSessionViewSet`
        writes the base version), so it is the right filter for a real round;
        the base version is the fallback for a round built by hand or in a
        test, and an unversioned map falls through to every line on it.
        """
        from maps.models import (
            BusLine,
            BusLineEdge,
            MapVersion,
            TrainLine,
            TrainLineEdge,
        )

        game_map = self.game_round.game.game_map
        if not game_map:
            return

        version = (
            self.game_round.game.active_map_version
            or MapVersion.objects.filter(game_map=game_map, base_version=True).first()
        )

        bus_lines = BusLine.objects.filter(game_map=game_map)
        train_lines = TrainLine.objects.filter(game_map=game_map)
        if version is not None:
            bus_lines = bus_lines.filter(map_versions=version)
            train_lines = train_lines.filter(map_versions=version)

        for line in bus_lines.distinct():
            self.bus_line_speeds.setdefault(line.pk, line.bus_speed_kmh)
            self.bus_line_intervals.setdefault(line.pk, line.intervall)
            edges = [
                link.street_edge.edge
                for link in BusLineEdge.objects.filter(bus_line=line).select_related(
                    "street_edge__edge__start_node",
                    "street_edge__edge__end_node",
                )
            ]
            self._register_pt_line(
                "bus", line.pk, line.name, edges, line.intervall, line.bus_capacity
            )

        for line in train_lines.distinct():
            self.train_line_speeds.setdefault(line.pk, line.train_speed_kmh)
            self.train_line_intervals.setdefault(line.pk, line.intervall)
            edges = [
                link.train_edge.edge
                for link in TrainLineEdge.objects.filter(
                    train_line=line
                ).select_related(
                    "train_edge__edge__start_node",
                    "train_edge__edge__end_node",
                )
            ]
            self._register_pt_line(
                "train", line.pk, line.name, edges, line.intervall, line.train_capacity
            )

        logger.info(f"[SIM] Loaded {len(self.pt_lines)} PT lines from the timetable")

    def _load_pt_legs(self):
        """Work out where each route boards and alights, per line it rides.

        A route is a chain of edges too, so its own node order comes from the
        same walk the line's does. Segment i runs from chain[i] to chain[i+1],
        which is what turns "segments 2 and 3 are on M1" into "gets on at
        Turmstraße, off at Hansaplatz".

        A route whose edges do not connect gets no legs at all: without a node
        order there is no way to say where it would board, and inventing one
        would put people on a bus at a stop the route never reaches. It rides
        nothing, arrives on foot, and the map gets a warning.
        """
        for route_pk, segments in self.route_segments.items():
            if route_pk < 0:
                continue  # a line's own run boards nobody
            ends = []
            for seg in segments:
                state = self.edge_states.get(seg.edge_id)  # type: ignore
                if state is None:
                    ends = []
                    break
                ends.append((state.start_node_id, state.end_node_id))
            chain = node_chain(ends)
            if len(chain) != len(segments) + 1:
                if any(seg.mode in ("bus", "train") for seg in segments):
                    logger.warning(
                        "[SIM] Route %s rides public transport but its edges do "
                        "not form a chain — nobody on it can board.",
                        route_pk,
                    )
                continue

            legs: list[PTLeg] = []
            index = 0
            while index < len(segments):
                seg = segments[index]
                line = self._pt_line_for(seg)
                if line is None:
                    index += 1
                    continue
                line_key = (seg.mode, int(seg.pt_line_id))  # type: ignore
                last = index
                while (
                    last + 1 < len(segments)
                    and segments[last + 1].mode == seg.mode
                    and segments[last + 1].pt_line_id == seg.pt_line_id
                ):
                    last += 1
                legs.append(
                    PTLeg(
                        first_index=index,
                        last_index=last,
                        line_key=line_key,
                        board_node=chain[index],
                        alight_node=chain[last + 1],
                    )
                )
                index = last + 1

            if legs:
                self.route_pt_legs[route_pk] = legs

    def _leg_at(self, route_pk: int, segment_index: int) -> "PTLeg | None":
        """The leg starting exactly at this segment, if one does."""
        for leg in self.route_pt_legs.get(route_pk, []):
            if leg.first_index == segment_index:
                return leg
        return None

    def _register_pt_line(
        self,
        mode: str,
        line_id: int,
        name: str,
        edges: list,
        interval_min: int,
        capacity: int,
    ):
        """Measure one line, put it in the registry, and give it a run to drive.

        The run is a synthetic entry in self.route_segments under a negative
        key. Every AgentRoute pk is a positive Postgres sequence value, so the
        two can never collide — and every `self.agent_results.get(route_pk)` in
        the accounting code already skips a key it does not know, which is what
        keeps a bus out of the per-agent numbers without a guard anywhere.
        """
        line_km = sum(e.euclidean_2d_distance() * self.scale for e in edges) / 1000
        interval = max(1, int(interval_min or 1))
        # round(), not floor(): a 7-minute interval over the two-hour window is
        # 17 departures, and flooring it would quietly shorten every timetable
        # whose interval does not divide 120.
        vehicles = max(1, round(DEPARTURE_WINDOW_MIN / interval))

        stops = node_chain([(e.start_node_id, e.end_node_id) for e in edges])
        # A line whose edges do not connect is run only as far as it does. The
        # serializer warns about the same map by name; this one is what stops a
        # vehicle walking off the end of its own stop list.
        usable = max(0, len(stops) - 1)
        edge_ids = [e.pk for e in edges][:usable]
        if edges and usable < len(edges):
            logger.warning(
                "[SIM] PT line %s (%s) breaks after %s of %s edges — its "
                "vehicles run only that far. Fix the map.",
                name,
                mode,
                usable,
                len(edges),
            )

        line_key = (mode, line_id)
        self.pt_lines[line_key] = PTLineState(
            line_id=line_id,
            mode=mode,
            name=name,
            line_km=line_km,
            interval_min=interval,
            capacity=max(1, int(capacity or 1)),
            vehicles=vehicles,
            edge_ids=edge_ids,
            stops=stops,
        )
        if line_km <= 0:
            logger.warning(
                "[SIM] PT line %s (%s) measures 0 km — no edges on this map "
                "version, so it emits nothing. Fix the map.",
                name,
                mode,
            )

        if not edge_ids:
            return

        route_key = -(len(self.line_route_keys) + 1)
        self.line_route_keys[line_key] = route_key
        self.route_segments[route_key] = [
            Segment(edge_id=edge_id, order=order, mode=mode, pt_line_id=line_id)
            for order, edge_id in enumerate(edge_ids)
        ]

    def _pt_line_for(self, segment) -> "PTLineState | None":
        """The registry entry a PT segment rides on, None for road modes.

        A PT segment whose line is not in the registry is a map that changed
        under a submitted route. It is logged and then costs nothing, which is
        wrong but is not worth inventing a line for — the route should not
        have validated.
        """
        if segment.mode not in ("bus", "train") or not segment.pt_line_id:
            return None
        line = self.pt_lines.get((segment.mode, int(segment.pt_line_id)))
        if line is None:
            logger.warning(
                "[SIM] Route segment rides %s line %s, which is not on this "
                "round's map version — it is charged nothing.",
                segment.mode,
                segment.pt_line_id,
            )
        return line

    def _attribute_pt_person_km(self):
        """Total up what each line actually carried.

        Was: every submitted PT segment x people_per_agent, counted before the
        round ran. Is: the person-kilometres booked in _alight, so a line is
        divided among the people who got on it and an agent whose people never
        boarded carries none of it.
        """
        for by_line in self.route_pt_person_km.values():
            for line_key, person_km in by_line.items():
                line = self.pt_lines.get(line_key)
                if line is not None:
                    line.person_km += person_km

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
                start_node_id=edge.start_node_id,  # type: ignore
                end_node_id=edge.end_node_id,  # type: ignore
                distance_m=distance_m,
                free_flow_speed_kmh=speed_limit,
                car_lanes=car_lanes,
                has_dedicated_bus_lane=has_dedicated_bus_lane,
                capacity_factor=draw_capacity_factor(self.rng),
            )

            # Build edge name for logging
            start_name = edge.start_node.name or f"Node {edge.start_node.pk}"
            end_name = edge.end_node.name or f"Node {edge.end_node.pk}"
            edge_names[edge.pk] = f"{start_name} → {end_name}"

        self.sim_log.set_edge_names(edge_names)
        logger.info(f"[SIM] Initialized {len(self.edge_states)} edge states")

    def _generate_departures(self, is_morning: bool = True):
        """When everyone wants to leave, and when every line's vehicles run.

        People — whatever mode they picked — draw the same normal distribution
        around base_hour. PT riders used to be spread evenly across the whole
        window instead, one clump per bus, which gave them no peak at all and
        so no peak penalty; the wait they were charged was a flat interval/2
        that assumed exactly that uniformity. Both go: they queue at a stop
        like everyone else and the wait falls out of it.

        Line vehicles are the other half, and they are NOT drawn: a timetable
        is not a random variable. They leave the terminus at i x interval from
        the start of the window.
        """
        base_hour = (
            self.morning_departure_hour if is_morning else self.evening_departure_hour
        )
        # Everything here is in minutes from the start of the departure window,
        # which opens at (base_hour - 1) * 60.

        for route_pk in self.agent_routes:
            departures = generate_departure_minutes(
                self.people_per_agent,
                base_hour,
                self.departure_std_dev_min,
                rng=self.rng,
            )
            self.departure_schedule[route_pk] = list(enumerate(departures))

        for line_key, line in self.pt_lines.items():
            route_key = self.line_route_keys.get(line_key)
            if route_key is None:
                continue
            self.departure_schedule[route_key] = [
                (i, float(i * line.interval_min)) for i in range(line.vehicles)
            ]

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

    def _begin_segment(self, vehicle_id: int, vehicle: Vehicle, at_min: float) -> bool:
        """Start the segment the vehicle is now on — road, or stop queue.

        This is the only difference between a person and a bus in the whole
        tick loop. A person whose next segment is a PT segment does not drive
        it: it joins the queue at the stop that segment starts from and waits
        for something to come. Everything else goes to _enter_edge unchanged.

        Returns False only where _enter_edge does — the link is full and the
        caller should try again next tick. Joining a stop queue always
        succeeds: a pavement does not fill up.
        """
        leg = self._leg_at(vehicle.route_pk, vehicle.segment_index)
        if leg is None:
            return self._enter_edge(vehicle_id, vehicle, at_min)

        vehicle.at_stop = True
        vehicle.queued = False
        vehicle.reached_stop_min = at_min
        self.stop_queues.setdefault((leg.line_key, leg.board_node), []).append(
            vehicle_id
        )
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
            line_key = None
            for key, route_key in self.line_route_keys.items():
                if route_key == route_pk:
                    line_key = key
                    break

            vehicle = Vehicle(
                route_pk=route_pk,
                person_index=person_index,
                mode=segments[0].mode,
                segment_index=0,
                passenger_count=1,
                wants_to_depart_min=depart_min,
                departed=True,
                # A bus runs to its timetable, not to a driver's taste, so it
                # takes NO draw — not merely a factor of 1.0. Drawing and
                # discarding would advance the round's generator and shift
                # every car departure behind it.
                speed_factor=1.0
                if line_key is not None
                else draw_driver_speed_factor(self.rng),
            )
            vehicle_id = self.next_vehicle_id

            if line_key is not None:
                if not self._enter_edge(vehicle_id, vehicle, max(depart_min, now)):
                    still_waiting.append((depart_min, route_pk, person_index))
                    continue
                self.next_vehicle_id += 1
                self.vehicles[vehicle_id] = vehicle
                line = self.pt_lines[line_key]
                pt = PTVehicle(
                    vehicle_id=vehicle_id,
                    line_key=line_key,
                    capacity=line.capacity,
                    departure_min=depart_min,
                )
                self.pt_vehicles.append(pt)
                self.pt_by_vehicle[vehicle_id] = pt
                # It is standing at its first stop the moment it sets off.
                self._serve_stop(pt, max(depart_min, now))
                continue

            if self._begin_segment(vehicle_id, vehicle, max(depart_min, now)):
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
                pt = self.pt_by_vehicle.get(head.vehicle_id)
                if pt is not None:
                    pt.stop_index = vehicle.segment_index
                    self._finish_run(pt, left_at)

            else:
                vehicle.mode = segments[vehicle.segment_index].mode
                pt = self.pt_by_vehicle.get(head.vehicle_id)
                if pt is not None:
                    pt.stop_index = vehicle.segment_index
                    self._serve_stop(pt, left_at)
                if forced or not self._begin_segment(head.vehicle_id, vehicle, left_at):
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
                    pt = self.pt_by_vehicle.get(vehicle_id)
                    if pt is not None:
                        pt.stop_index = vehicle.segment_index
                        self._finish_run(pt, left_at)
                    done.append(vehicle_id)
                    break
                vehicle.mode = segments[vehicle.segment_index].mode
                pt = self.pt_by_vehicle.get(vehicle_id)
                if pt is not None:
                    pt.stop_index = vehicle.segment_index
                    self._serve_stop(pt, left_at)
                if not self._begin_segment(vehicle_id, vehicle, left_at):
                    # It has just joined mixed traffic and the link is full;
                    # it waits where it is and retries next tick.
                    vehicle.segment_index -= 1
                    vehicle.ready_at_min = tick_end
                    break
                if vehicle.queued or vehicle.at_stop:
                    done.append(vehicle_id)  # somebody else's problem now
                    break
        for vehicle_id in done:
            self.free_running.discard(vehicle_id)

    def _serve_stop(self, pt: PTVehicle, at_min: float):
        """Alight, then board, at the stop this vehicle is standing at.

        Alight first, always: that is the order a door works in, and it is what
        frees the seat the person behind is waiting for. Doing it the other way
        round would refuse a boarding at a terminus where the bus empties.

        Dwell time is not modelled yet — the vehicle serves the stop in the
        instant it reaches it. It is the mechanism this design was chosen to
        keep possible (see "the alternative that was rejected"), not something
        this guide builds.
        """
        line = self.pt_lines.get(pt.line_key)
        if line is None or pt.finished:
            return
        if not 0 <= pt.stop_index < len(line.stops):
            return
        node = line.stops[pt.stop_index]

        for rider_id in list(pt.riders):
            rider = self.vehicles.get(rider_id)
            if rider is None:
                continue
            leg = self._current_leg(rider)
            if leg is not None and leg.alight_node == node:
                self._alight(pt, rider_id, rider, leg, at_min)

        queue = self.stop_queues.get((pt.line_key, node))
        if not queue:
            return
        while queue and pt.free_seats > 0:
            rider_id = queue.pop(0)
            rider = self.vehicles.get(rider_id)
            if rider is None or not rider.at_stop:
                continue
            rider.at_stop = False
            rider.aboard_of = pt.vehicle_id
            rider.wait_min += max(0.0, at_min - rider.reached_stop_min)
            if not rider.bought_ticket:
                rider.bought_ticket = True
                self.route_fares[rider.route_pk] = (
                    self.route_fares.get(rider.route_pk, 0) + 1
                )
            pt.riders.append(rider_id)
            pt.boarded_total += 1
            line.boarded += 1
        # Whoever is still standing here was refused for want of a seat.
        line.denied += len(queue)

    def _current_leg(self, rider: Vehicle) -> "PTLeg | None":
        """The leg a rider is currently riding, by its segment index."""
        for leg in self.route_pt_legs.get(rider.route_pk, []):
            if leg.first_index <= rider.segment_index <= leg.last_index:
                return leg
        return None

    def _alight(
        self,
        pt: PTVehicle,
        rider_id: int,
        rider: Vehicle,
        leg: "PTLeg",
        at_min: float,
    ):
        """Set one rider down and let it get on with its route.

        The person-kilometres it rode are booked to the line HERE rather than
        assumed from the submitted route: a line's personal shares are divided
        among the people who actually got on it, and the seats nobody filled
        belong to nobody. That is the seam back into
        `[backend]-pt-timetable-and-society.md`'s `share_of`.
        """
        pt.riders.remove(rider_id)
        rider.aboard_of = None

        ridden_km = 0.0
        segments = self.route_segments.get(rider.route_pk, [])
        for index in range(leg.first_index, leg.last_index + 1):
            state = self.edge_states.get(segments[index].edge_id)  # type: ignore
            if state:
                ridden_km += state.distance_m / 1000.0
        by_line = self.route_pt_person_km.setdefault(rider.route_pk, {})
        by_line[leg.line_key] = by_line.get(leg.line_key, 0.0) + ridden_km

        rider.segment_index = leg.last_index + 1
        if rider.segment_index >= len(segments):
            rider.arrived = True
            rider.arrived_min = at_min
            return
        rider.mode = segments[rider.segment_index].mode
        if self._begin_segment(rider_id, rider, at_min):
            if not rider.queued and not rider.at_stop:
                self.free_running.add(rider_id)
        else:
            # The street outside the stop is full. It stands on the pavement
            # and tries again next tick, which is what the door queue already
            # does for a car that cannot get out of its own road.
            rider.at_stop = True
            rider.reached_stop_min = at_min
            self.stop_queues.setdefault((leg.line_key, leg.alight_node), []).append(
                rider_id
            )

    def _finish_run(self, pt: PTVehicle, at_min: float):
        """The vehicle has reached the end of the line. Everybody off."""
        line = self.pt_lines.get(pt.line_key)
        pt.finished = True
        if line is None:
            return
        terminus = line.stops[-1] if line.stops else None
        for rider_id in list(pt.riders):
            rider = self.vehicles.get(rider_id)
            if rider is None:
                continue
            leg = self._current_leg(rider)
            if leg is None:
                pt.riders.remove(rider_id)
                rider.aboard_of = None
                continue
            if leg.alight_node != terminus:
                logger.warning(
                    "[SIM] %s reached its terminus with a rider still aboard "
                    "who wanted node %s — it is set down here.",
                    line.name,
                    leg.alight_node,
                )
            self._alight(pt, rider_id, rider, leg, at_min)

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
            if moved and self.waiting:
                # A discharge freed storage at somebody's front door. Without
                # this the origin link is filled once per tick and emptied
                # again inside the same tick, so it admits its STORAGE per
                # tick where the model means its FLOW — measured at 118/tick
                # on a link storing 118 and passing 157.
                self._spawn_vehicles(now, tick_end)

        for edge_id, edge_state in self.edge_states.items():
            if edge_id in released or not edge_state.queue:
                edge_state.blocked_since_tick = self.current_tick
        self._strand_hopeless_riders()
        self.held_at_origin = self._held_at_origin(tick_end)

    def _record_edge_traffic(self):
        """Record traffic snapshot for each edge."""
        if not self.simulation_result:
            return

        snapshots = []
        for edge_id, state in self.edge_states.items():
            held = self.held_at_origin.get(edge_id, 0)
            # `held` on its own is enough to record a row: an origin link with
            # a queue outside it and nothing on it is the case the heatmap was
            # blind to, and skipping it would keep it that way.
            if state.queue or state.traversal_count or held:
                snapshots.append(
                    EdgeTrafficSnapshot(
                        simulation=self.simulation_result,
                        edge_id=edge_id,
                        time_tick=self.current_tick,
                        vehicle_count=len(state.queue),
                        waiting_count=held,
                        speed_kmh=state.mean_speed_kmh,
                    )
                )

        if snapshots:
            EdgeTrafficSnapshot.objects.bulk_create(snapshots)

    def _held_at_origin(self, tick_end: float) -> dict[int, int]:
        """Who wanted to leave by now and is still standing at the front door.

        The queue no instrument could see. These vehicles sit in self.waiting,
        so the link they want samples empty: queued_edges reads 0, the
        snapshot reads one vehicle at free flow, and mean_speed_kmh — which
        feeds the CO2 factor and the route preview — stays at the speed limit.

        self.waiting is sorted by wanted departure, so the walk stops at the
        first vehicle that does not want to leave yet.
        """
        held: dict[int, int] = {}
        for depart_min, route_pk, _person_index in self.waiting:
            if depart_min > tick_end:
                break
            segments = self.route_segments.get(route_pk, [])
            if not segments:
                continue
            edge_id = segments[0].edge_id  # type: ignore
            held[edge_id] = held.get(edge_id, 0) + 1
        return held

    def _all_vehicles_arrived(self) -> bool:
        """Check if all vehicles have arrived."""
        for vehicle in self.vehicles.values():
            if vehicle.departed and not vehicle.arrived and not vehicle.stranded:
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
            trip_min = vehicle.arrived_min - vehicle.wants_to_depart_min
            delay_min = max(
                0.0,
                trip_min - self._free_flow_min(vehicle.route_pk, vehicle.speed_factor),
            )
            for _ in range(vehicle.passenger_count):
                agent_results["trip_times"].append(trip_min)
                agent_results["delays"].append(delay_min)
                agent_results["waits"].append(vehicle.wait_min)

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
            elapsed = max(0.0, sim_end_min - vehicle.wants_to_depart_min)
            delay = max(0.0, elapsed - self._free_flow_min(vehicle.route_pk))
            for _ in range(vehicle.passenger_count):
                agent_results["trip_times"].append(elapsed)
                agent_results["delays"].append(delay)
                agent_results["waits"].append(vehicle.wait_min)
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
            elapsed = sim_end_min - depart_min
            delay = max(0.0, elapsed - self._free_flow_min(route_pk))
            agent_results["trip_times"].append(elapsed)
            agent_results["delays"].append(delay)
            agent_results["waits"].append(0.0)
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
                legs = self.route_pt_legs.get(route_pk, [])
                route_line = (
                    f"  {self.sim_log._route_label(route_pk)}: "
                    f"distance={route.total_distance_m:.0f}m, "
                    f"est_time={route.estimated_time_min:.1f}min, "
                    f"segments={len(segments)}, "
                    f"people={self.people_per_agent}"
                )
                for leg in legs:
                    line = self.pt_lines.get(leg.line_key)
                    route_line += (
                        f", rides {line.name if line else leg.line_key[1]} "
                        f"{leg.board_node}→{leg.alight_node}"
                    )
                self.sim_log.write(route_line)

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
                f"({len(self.agent_routes)} routes x {self.people_per_agent} people, "
                f"plus {sum(l.vehicles for l in self.pt_lines.values())} PT runs "
                f"from {len(self.pt_lines)} lines)"
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
                    held_total = sum(self.held_at_origin.values())
                    tick_line = (
                        f"[tick {self.current_tick:>3}] "
                        f"waiting_to_depart={len(self.waiting)}, active={active}, "
                        f"arrived={arrived}/{len(self.vehicles)}, "
                        f"queued_edges={len(queued)}, "
                        f"held_at_door={held_total}, "
                        f"forced={self.forced_releases}"
                    )
                    self.sim_log.write(tick_line)

                    for eid, count in sorted(
                        self.held_at_origin.items(), key=lambda kv: -kv[1]
                    )[:5]:
                        es = self.edge_states.get(eid)
                        if es is None:
                            continue
                        self.sim_log.write(
                            f"    DOOR: {self.sim_log._edge_label(eid)} — "
                            f"{count} vehicles cannot get on "
                            f"(storage={es.storage_capacity_pcu:.0f}pcu, "
                            f"observed={es.mean_speed_kmh:.1f}km/h)"
                        )

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
                        f"queued_edges={len(queued)}, held_at_door={held_total}, "
                        f"forced={self.forced_releases}"
                    )
                elif self.held_at_origin:
                    # A door queue can open and fully drain between two
                    # decade-ticks — origin-admission lets a link discharge
                    # its whole flow capacity per tick, so a queue that used
                    # to take an hour to clear now can clear in under ten.
                    # Gating this on the same %10 as the full status line
                    # would make the log silently miss it, which is exactly
                    # the blindness this branch exists to remove.
                    held_total = sum(self.held_at_origin.values())
                    self.sim_log.write(
                        f"[tick {self.current_tick:>3}] held_at_door={held_total}"
                    )
                    for eid, count in sorted(
                        self.held_at_origin.items(), key=lambda kv: -kv[1]
                    )[:5]:
                        es = self.edge_states.get(eid)
                        if es is None:
                            continue
                        self.sim_log.write(
                            f"    DOOR: {self.sim_log._edge_label(eid)} — "
                            f"{count} vehicles cannot get on "
                            f"(storage={es.storage_capacity_pcu:.0f}pcu, "
                            f"observed={es.mean_speed_kmh:.1f}km/h)"
                        )
                    logger.info(
                        f"[SIM] Tick {self.current_tick}: held_at_door={held_total}"
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

        self._attribute_pt_person_km()

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
                mean_wait = (
                    sum(results["waits"]) / len(results["waits"])
                    if results["waits"]
                    else 0.0
                )
            else:
                mean_trip_time = sum(trip_times) / len(trip_times)
                min_trip_time = min(trip_times)
                max_trip_time = max(trip_times)
                mean_delay = sum(delays) / len(delays) if delays else 0.0
                mean_wait = (
                    sum(results["waits"]) / len(results["waits"])
                    if results["waits"]
                    else 0.0
                )

            # Calculate CO2 and cost based on mode and segments
            co2, cost, paid = self._calculate_emissions_and_cost(route)
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
                elif seg.mode in ("bus", "train"):
                    line = self.pt_lines.get((seg.mode, int(seg.pt_line_id or 0)))
                    if line is None:
                        self.sim_log.write(
                            f"    seg {seg.order} ({seg.mode}): {es.distance_m:.0f}m → "
                            f"line not on this map version, charged nothing"
                        )
                        continue
                    seg_person_km = dist_km * self.people_per_agent
                    seg_co2 = line.share_of(line.society_co2_g, seg_person_km)
                    self.sim_log.write(
                        f"    seg {seg.order} ({seg.mode}, {line.name}): "
                        f"{es.distance_m:.0f}m → {seg_co2:.0f}g, this route's share "
                        f"of {line.society_co2_g / 1000:.1f}kg "
                        f"({line.vehicles} veh × {line.line_km:.2f}km), "
                        f"{seg_person_km:.0f} of {line.person_km:.0f} Personen-km"
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
                mean_paid_eur=paid / self.people_per_agent
                if self.people_per_agent
                else 0.0,
                total_co2_g=co2,
                congestion_delay_min=mean_delay,
                wait_time_min=mean_wait,
            )

        # Totals. The network's own emissions are in the round total whether
        # anyone rode or not — the ridden lines are already inside total_co2
        # as the routes' shares, so only the lines nobody touched are added.
        network_co2 = sum(line.society_co2_g for line in self.pt_lines.values())
        network_cost = sum(line.society_cost_eur for line in self.pt_lines.values())
        unridden_co2 = sum(
            line.society_co2_g for line in self.pt_lines.values() if line.person_km <= 0
        )
        unridden_cost = sum(
            line.society_cost_eur
            for line in self.pt_lines.values()
            if line.person_km <= 0
        )
        total_co2 += unridden_co2
        total_cost += unridden_cost

        self.sim_log.header("TOTALS")
        self.sim_log.write(f"Total CO2: {total_co2:.0f}g ({total_co2 / 1000:.2f}kg)")
        self.sim_log.write(f"Total cost: €{total_cost:.2f}")
        self.sim_log.write(
            f"  of which the network's own timetable: {network_co2 / 1000:.2f}kg, "
            f"€{network_cost:.2f} over {len(self.pt_lines)} lines "
            f"({unridden_co2 / 1000:.2f}kg of it on lines nobody rode)"
        )
        self.sim_log.write(f"Routes processed: {len(self.agent_results)}")
        if self.pt_lines:
            self.sim_log.header("PUBLIC TRANSPORT")
            for line in self.pt_lines.values():
                self.sim_log.write(
                    f"  {line.name} ({line.mode}): {line.vehicles} runs x "
                    f"{line.line_km:.2f}km every {line.interval_min}min, "
                    f"{line.capacity} seats — {line.boarded} boarded, "
                    f"{line.denied} refused for want of a seat, "
                    f"{line.stranded} gave up, "
                    f"{line.person_km:.0f} Personen-km carried"
                )
        # Update totals
        self.simulation_result.total_co2_g = total_co2  # type: ignore
        self.simulation_result.total_cost_eur = total_cost  # type: ignore
        self.simulation_result.network_co2_g = network_co2  # type: ignore
        self.simulation_result.network_cost_eur = network_cost  # type: ignore
        self.simulation_result.save()  # type: ignore

        logger.info(
            f"[SIM] Total CO2: {total_co2:.0f}g, Total cost: {total_cost:.2f}EUR"
        )

        # Update street speeds for next round
        self._update_street_speeds()

    def _calculate_emissions_and_cost(
        self, route: AgentRoute
    ) -> tuple[float, float, float]:
        """CO2, cost and fare for one agent's route, for all its people.

        - Car: speed-dependent per car_emissions_g_per_km — a jam burns more
          per kilometre, and that is what makes clearing one worth a vote.
          Each person drives alone, so per-person is per-vehicle.
        - Bus/train: this route's slice of the LINE's own emissions and cost,
          weighted by the person-kilometres it contributes. Not divided by
          capacity: a timetable does not get cleaner because the seats are
          empty.
        - Bike/walk: nothing.

        The car side accumulates per person and multiplies once at the end,
        the way it always did. That is not a style choice — reordering it
        moves the last digits of every car figure and the golden master with
        them. The PT shares are class-scale already, so they are kept in a
        separate accumulator and added afterwards.

        Returns:
            (total_co2_g, total_cost_eur, total_paid_eur), all for the whole
            people_per_agent.
        """
        segments = self.route_segments.get(route.pk, [])
        if not segments:
            return 0.0, 0.0, 0.0

        per_person_co2 = 0.0
        per_person_cost = 0.0
        per_person_paid = 0.0
        class_co2 = 0.0
        class_cost = 0.0

        for seg in segments:
            edge_state = self.edge_states.get(seg.edge_id)  # type: ignore
            if not edge_state:
                continue

            distance_km = edge_state.distance_m / 1000

            if seg.mode == "car":
                # The speed this link actually ran at this round, not the
                # speed limit.
                speed_kmh = edge_state.mean_speed_kmh
                per_person_co2 += car_emissions_g_per_km(speed_kmh) * distance_km
                per_person_cost += car_cost_eur_per_km(speed_kmh) * distance_km
                per_person_paid += car_out_of_pocket_eur_per_km(speed_kmh) * distance_km
                continue

        # PT: this route's realised share of each line it actually rode.
        for line_key, person_km in self.route_pt_person_km.get(route.pk, {}).items():
            line = self.pt_lines.get(line_key)
            if line is None:
                continue
            class_co2 += line.share_of(line.society_co2_g, person_km)
            class_cost += line.share_of(line.society_cost_eur, person_km)

        # One Ticket per person who got on, however many times they changed —
        # and none for the people who never did.
        fare_total = PT_FARE_EUR * self.route_fares.get(route.pk, 0)

        return (
            per_person_co2 * self.people_per_agent + class_co2,
            per_person_cost * self.people_per_agent + class_cost,
            per_person_paid * self.people_per_agent + fare_total,
        )

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

    def _strand_hopeless_riders(self):
        """Give up on people no vehicle can ever reach.

        A line's last run is over and nothing of it is left in self.waiting:
        anyone still standing at one of its stops is not going to travel. They
        are marked rather than removed, so _record_non_arrivals books them the
        way it books a car that never got out of its road — at the time the
        clock stopped, as a lower bound.

        Without this the round burns its whole tick budget waiting for a bus
        that has already gone home.
        """
        for line_key, line in self.pt_lines.items():
            route_key = self.line_route_keys.get(line_key)
            if route_key is None:
                continue
            if any(
                not pt.finished for pt in self.pt_vehicles if pt.line_key == line_key
            ):
                continue
            if any(entry[1] == route_key for entry in self.waiting):
                continue
            for node in line.stops:
                queue = self.stop_queues.get((line_key, node))
                if not queue:
                    continue
                for rider_id in queue:
                    rider = self.vehicles.get(rider_id)
                    if rider is None or not rider.at_stop:
                        continue
                    rider.at_stop = False
                    rider.stranded = True
                    line.stranded += 1
                queue.clear()
