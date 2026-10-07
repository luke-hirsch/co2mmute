"""
The link queue model: the engine itself, one pass of a round at a time.

The mesoscopic model MATSim uses, Kai Nagel's line of work at TU Berlin. A link
has a free-flow time, a flow capacity and a storage capacity; a vehicle cannot
leave before its free-flow time is up, then queues and is discharged at the
link's flow, and a full downstream link blocks everything behind it. Public
transport runs a timetable over the same links and boards real riders at its
stops. Departures are drawn per person, in minutes, and served from one
network-wide list.

Built from a `sim.scenario.Scenario` and a generator, and nothing else: no
Django, no rows. `game.simulation.TrafficSimulator` is the adapter that builds
the scenario from a round and writes the outcome back, and it is the only thing
the rest of the backend talks to. Here a calibration script or a test can run a
round with no database at all.

Moved here from `game/simulation.py` unchanged in what it computes — two golden
masters, one of them over public transport and both ways, pin that.
"""

import bisect
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

from sim.constants import (
    BIKE_COST_PER_KM,
    BIKE_PCU,
    BUS_PCU,
    TRAM_PCU,
    CAR_EMISSIONS_G_PER_KM,
    DEADLOCK_TICKS,
    PT_FARE_EUR,
    car_cost_eur_per_km,
    car_emissions_g_per_km,
    car_out_of_pocket_eur_per_km,
    draw_capacity_factor,
    draw_driver_speed_factor,
    generate_departure_minutes,
)
from sim.log import SimulationLog
from sim.outcome import LinkSample, RouteOutcome
from sim.scenario import Link, Route, Scenario, Segment
from sim.state import (
    EdgeState,
    PTLineState,
    PTVehicle,
    QueuedVehicle,
    Vehicle,
    node_chain,
)

logger = logging.getLogger(__name__)

# A line's speed when the scenario does not name one.
FALLBACK_BUS_SPEED_KMH = 30
FALLBACK_TRAIN_SPEED_KMH = 40

# Departure window: matches the ±60 min clamp in generate_departure_minutes()
DEPARTURE_WINDOW_MIN = 120

# A pass runs until everybody is home (F2d, Lukas 2026-10-02: "we should not
# strand people"), so this is not a clock the round is played against. It is a
# guard against a model or map bug running forever, and reaching it is logged
# as one. Measured on the shipped map: the game as played needs at most 35
# ticks a pass, four times the calibrated demand with every street cut to one
# lane 153, and the deadlock test's synthetic two-street ring ~680.
PASS_TICK_GUARD = 1000

# Where the evening starts on the round's one axis — its street snapshots and
# replay dots are moved by this many ticks — unless the morning ran past it.
# It used to be max_ticks itself, 200 at 5 min a tick, and it stays there so
# stored recordings keep their shape: tied to the guard, every evening would
# start at minute 5000.
HOME_PASS_EARLIEST_TICK = 200

# One dot on the replay stands for about this many people (S25, Lukas's pick
# on measured consequences). It was 50, calibrated for 1000 people per agent:
# at the derived ~100, a jam of fifty cars drew as one or two dots, and a third
# of the jam moments on the shipped map showed one dot or none — "only one car
# on the edge, but it still got slower". At 10 a jam is seven to twelve dots,
# the shipped map carries ~640 person dots (WebKit holds 60 fps at twice that
# on a desktop), and the recording is ~240 KiB, ~40 KiB as the view sends it.
# What the screen names is the real ratio, which only equals this when it
# divides the Gruppe — see _people_per_dot.
#
# The sample is taken by PERSON INDEX and never by a draw. A draw here would
# come from self.rng and re-roll every later driver, which is the exact failure
# that moved draw_driver_speed_factor out of _spawn_vehicles — and it would
# move the round's result by far more than this recorder is worth.
REPLAY_PEOPLE_PER_DOT = 10

# Bumped when the wire format changes, so a stored replay from an older round
# can be recognised and skipped rather than mis-drawn.
#
# 2: the way home is in it (F2). Dots carry `pass`, the payload `home_start_min`,
# and the evening's minutes and ids are already moved onto the morning's clock.
REPLAY_FORMAT_VERSION = 2


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


class LinkQueueEngine:
    """
    One pass of a round over a link queue network, tick by tick.

    Satisfies `sim.engine.Engine`. Build it from a scenario and a generator,
    `run_round()`, then read `outcomes`, the pass totals, `link_samples`,
    `observed_speeds()` and `build_replay()`.
    """

    def __init__(self, scenario: Scenario, rng: random.Random):
        """
        Set up one pass: the network, the routes and the lines, nothing run.

        Args:
            scenario: What this pass simulates — see `sim.scenario`. Its order
                is the round's: routes and links are taken in the order given,
                because that is the order the draws are taken in.
            rng: The round's generator. The way home is handed the one the way
                to work left off at, so one round is one seeded stream and
                replays identically — in a test, in a debugger, or after a
                worker restart.
        """
        params = scenario.params
        # Kept whole: what this pass was asked, for a test or a calibration
        # script to run again without the database that produced it.
        self.scenario = scenario
        self.scale = scenario.scale
        self.direction = scenario.direction
        self.title = scenario.title
        self.ref = scenario.ref
        # The evening pass, once the way to work has run. Kept so a test (and
        # the log) can read what the second network saw.
        self.home_pass: "LinkQueueEngine | None" = None
        # What this pass worked out per route, before anything is written: the
        # way to work needs the way home's numbers to make its row.
        self.outcomes: dict[int, RouteOutcome] = {}
        self.pass_total_co2_g = 0.0
        self.pass_total_cost_eur = 0.0
        self.pass_network_co2_g = 0.0
        self.pass_network_cost_eur = 0.0
        # Every link with something on it, every tick. See _record_edge_traffic.
        self.link_samples: list[LinkSample] = []
        # Added to every sample's tick, so the evening's sit after the
        # morning's under one (simulation, edge, time_tick) key.
        self.tick_offset = 0
        # A generator of its own rather than module-level `random`: the module
        # generator is process-wide shared state, so anything else drawing from
        # it would shift this round's departures.
        self.rng = rng
        self.held_at_origin: dict[int, int] = {}
        self.people_per_agent = params.people_per_agent
        self.tick_duration_min = params.tick_duration_min
        self.morning_departure_hour = params.morning_departure_hour
        self.evening_departure_hour = params.evening_departure_hour
        self.departure_std_dev_min = params.departure_std_dev_min
        self.walk_speed_kmh = params.walk_speed_kmh
        self.bike_speed_kmh = params.bike_speed_kmh
        self.default_car_speed_kmh = params.default_car_speed_kmh

        # Edge states indexed by edge_id
        self.edge_states: dict[int, EdgeState] = {}

        # Vehicles indexed by unique ID
        self.vehicles: dict[int, Vehicle] = {}
        self.next_vehicle_id = 0

        # PT vehicles
        self.pt_vehicles: list[PTVehicle] = []
        self.pt_by_vehicle: dict[int, PTVehicle] = {}

        # A line's own run through self.route_segments, under a key that cannot
        # be a person's (theirs are positive — see sim.scenario.Route).
        self.line_route_keys: dict[tuple[str, int], int] = {}

        # The reverse, so the tick loop can ask "which line is this negative
        # route?" without walking the dict on every spawn.
        self.line_by_route_key: dict[int, tuple[str, int]] = {}

        # Which routes ride which line; built with the legs. The runs past the
        # base timetable need it to answer "does anybody still want this?".
        self.routes_by_line: dict[tuple[str, int], set[int]] = {}

        # Refreshed once a tick: whether each line still has unserved demand.
        self.line_wanted: dict[tuple[str, int], bool] = {}

        # Refreshed with it: whether any person at all is still out. A line
        # keeps running while they are, ridden or not — see _run_is_cancelled.
        self.anyone_under_way = False

        # Whether a way home will follow this pass. Set by run_round; the
        # progress bar needs it before the evening exists.
        self.expects_way_home = False

        # (line_key, node) that a run of the line has actually stood at, and
        # the lines with at least one run that finished its whole journey.
        # Together they answer the only question capacity cannot: is this
        # person waiting at a stop the line does not serve? See
        # _strand_hopeless_riders.
        self.line_served_nodes: set[tuple[tuple[str, int], int]] = set()
        self.line_has_finished_run: set[tuple[str, int]] = set()

        # How long a line may keep dispatching. Set from max_ticks at the top
        # of each pass — the road's clock, not a PT constant. The default
        # matches run_round's own default so an engine constructed and
        # poked at in a test does not schedule a billion runs.
        self.max_service_min: float = float(PASS_TICK_GUARD * self.tick_duration_min)

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
        self.agent_routes: dict[int, Route] = {}
        self.route_segments: dict[int, list[Segment]] = {}
        # The node ids a route visits, in travel order — route_pk -> [node_id].
        # An edge is stored in either direction (see sim.state.node_chain), so
        # the replay cannot tell which way a dot crosses a link without this.
        # Index i of a route's segments runs from chain[i] to chain[i + 1].
        self.route_nodes: dict[int, list[int]] = {}

        # PT line speeds: line_id -> speed_kmh. May name lines that are not
        # in self.pt_lines — see sim.scenario.Scenario.
        self.bus_line_speeds: dict[int, float] = dict(scenario.bus_speeds)
        self.train_line_speeds: dict[int, float] = dict(scenario.train_speeds)

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

        # The replay trace: vehicle_id -> [(at_min, kind, ref, from_node)].
        # Only sampled people and line vehicles are in here — see _trace.
        self.trace: dict[int, list[tuple[float, str, int | None, int | None]]] = {}
        self.trace_stride = max(1, REPLAY_PEOPLE_PER_DOT)

        # Who did not get there, in PEOPLE, as _record_non_arrivals books them.
        # The replay's closing sentence reads this rather than the sample: the
        # people still at their front door when the clock stops never became
        # vehicles, so no dot exists for any of them.
        self.non_arrivals: dict[str, int] = {"unfinished": 0, "stranded": 0}

        # Load routes and initialize edges during construction
        self._load_routes(scenario)
        self._initialize_edges(scenario)
        self._load_pt_legs()
        self.free_running: set[int] = set()
        self.waiting: list[tuple[float, int, int, float]] = []
        self.forced_releases = 0

    def _load_routes(self, scenario: Scenario):
        """Take this pass's routes and lines in, in the scenario's order.

        The order is the round's: it decides who draws which departure, so it
        is the order the adapter read them in, never re-sorted here. A route
        or a line naming a link the scenario does not carry is a broken
        scenario, and is refused rather than run on a guess.
        """
        links = {link.edge_id: link for link in scenario.links}
        named = {seg.edge_id for route in scenario.routes for seg in route.segments}
        named.update(edge_id for line in scenario.lines for edge_id in line.edge_ids)
        missing = sorted(named - links.keys())
        if missing:
            raise ValueError(
                f"The scenario names links it does not carry: {missing[:10]}"
            )

        route_labels = {}
        for route in scenario.routes:
            segments = list(route.segments)
            self.agent_routes[route.pk] = route
            self.route_segments[route.pk] = segments
            # Same helper the PT lines use. A route whose edges do not
            # connect yields a short chain; _trace falls back to no
            # direction rather than to a wrong one.
            self.route_nodes[route.pk] = node_chain(
                [
                    (links[seg.edge_id].start_node_id, links[seg.edge_id].end_node_id)
                    for seg in segments
                ]
            )
            if route.label:
                route_labels[route.pk] = route.label

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

        # Every line on the map version, not only the ridden ones: a timetable
        # runs whether anyone is aboard or not.
        for line in scenario.lines:
            self._register_pt_line(
                line.mode,
                line.line_id,
                line.name,
                [links[edge_id] for edge_id in line.edge_ids],
                line.interval_min,
                line.capacity,
                kind=line.kind,
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

        for route_pk, legs in self.route_pt_legs.items():
            for leg in legs:
                self.routes_by_line.setdefault(leg.line_key, set()).add(route_pk)

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
        edges: list[Link],
        interval_min: int,
        capacity: int,
        kind: str = "",
    ):
        """Measure one line, put it in the registry, and give it a run to drive.

        The run is a synthetic entry in self.route_segments under a negative
        key. Every person-route key is positive (`sim.scenario.Route`), so the
        two can never collide — and every `self.agent_results.get(route_pk)` in
        the accounting code already skips a key it does not know, which is what
        keeps a bus out of the per-agent numbers without a guard anywhere.
        """
        interval = max(1, int(interval_min or 1))
        # round(), not floor(): a 7-minute interval over the two-hour window is
        # 17 departures, and flooring it would quietly shorten every timetable
        # whose interval does not divide 120.
        base_vehicles = max(1, round(DEPARTURE_WINDOW_MIN / interval))

        stops = node_chain([(e.start_node_id, e.end_node_id) for e in edges])
        # A line whose edges do not connect is run only as far as it does. The
        # serializer warns about the same map by name; this one is what stops a
        # vehicle walking off the end of its own stop list.
        usable = max(0, len(stops) - 1)
        edge_ids = [e.edge_id for e in edges][:usable]
        # Measured over the trimmed edges, not all of them: a line is charged
        # society CO2 and cost for the kilometres its vehicles actually drive.
        # Summing before the trim charged a broken line for the part it can
        # never reach, which on Berlin_Mitte-West is `101` (4.04 of 6.33 km).
        line_km = sum(e.distance_m for e in edges[:usable]) / 1000
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
            base_vehicles=base_vehicles,
            edge_ids=edge_ids,
            stops=stops,
            kind=kind,
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
        self.line_by_route_key[route_key] = line_key
        self.route_segments[route_key] = [
            Segment(edge_id=edge_id, order=order, mode=mode, pt_line_id=line_id)
            for order, edge_id in enumerate(edge_ids)
        ]
        # `stops` is already this line's node chain; `usable` trimmed the edges
        # to the part that connects, so trim the chain to match.
        self.route_nodes[route_key] = stops[: usable + 1]

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

    def _initialize_edges(self, scenario: Scenario):
        """One EdgeState per link a route or a line drives, with its draw.

        In the scenario's link order, which is the order the capacity factors
        are drawn in — so a scenario carrying extra links (the game passes a
        line's whole chain, though only the part that connects is run) draws
        exactly what it would without them.
        """
        # Get unique edges from all routes
        edge_ids = set()
        for segments in self.route_segments.values():
            for seg in segments:
                edge_ids.add(seg.edge_id)  # type: ignore

        logger.info(f"[SIM] Initializing {len(edge_ids)} unique edges")

        edge_names = {}
        for link in scenario.links:
            if link.edge_id not in edge_ids:
                continue
            distance_m = link.distance_m

            # Speed limit, lanes, bus lane and rails come with the street
            if link.is_street:
                speed_limit = link.speed_limit_kmh
                lanes = link.lanes
                has_dedicated_bus_lane = link.has_dedicated_bus_lane
                tram_track = link.tram_track
            else:
                speed_limit = self.default_car_speed_kmh
                lanes = 1
                has_dedicated_bus_lane = False
                tram_track = ""

            if speed_limit <= 0:
                logger.warning(
                    "[SIM] Edge %s (%s) has speed_limit=%s — falling back to the "
                    "map default of %s km/h. Fix the map.",
                    link.edge_id,
                    link.name or "unnamed",
                    speed_limit,
                    self.default_car_speed_kmh,
                )
                speed_limit = self.default_car_speed_kmh

            # `lanes` counts the whole street, every reservation included, so
            # ticking "Busspur" or "Radweg" IS the trade-off. Zero car lanes
            # is legal and makes the street a gate — Lukas: "if that means a
            # road gets closed for the car entirely, then this is what it is.
            # People can decide and vote about it."
            # A link with no street under it is a path — a way for bikes and
            # pedestrians, and no car lane at all. `_validate_routes` and
            # `canUseEdge` both already refuse a car there, so nothing can
            # reach this with a car today; leaving `car_lanes = lanes` meant
            # the same fact was answered two different ways in two places,
            # which is the shape of every bug in this file's history.
            is_street = link.is_street
            has_bike_lane = link.has_bike_lane
            car_lanes = lanes if is_street else 0
            if is_street:
                reserved = []
                if has_dedicated_bus_lane:
                    reserved.append("a bus lane")
                if has_bike_lane:
                    reserved.append("a bike lane")
                # A tram's own track is a lane taken from the street like the
                # two above. Rails in the car lane take nothing: the cars
                # drive on them, and the tram waits with the cars.
                if tram_track == "own":
                    reserved.append("a tram track")
                car_lanes = max(0, lanes - len(reserved))
                if car_lanes == 0 and reserved:
                    logger.info(
                        "[SIM] Edge %s is a gate (%s): closed to cars, open "
                        "to buses, trams, bikes and pedestrians.",
                        link.edge_id,
                        " and ".join(reserved),
                    )

            self.edge_states[link.edge_id] = EdgeState(
                edge_id=link.edge_id,
                start_node_id=link.start_node_id,
                end_node_id=link.end_node_id,
                distance_m=distance_m,
                free_flow_speed_kmh=speed_limit,
                car_lanes=car_lanes,
                has_dedicated_bus_lane=has_dedicated_bus_lane,
                rails_in_car_lane=tram_track == "lane",
                is_street=is_street,
                has_bike_lane=has_bike_lane,
                capacity_factor=draw_capacity_factor(self.rng),
            )

            if link.label:
                edge_names[link.edge_id] = link.label

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
            # Scheduled to the SIMULATION's clock, not to the departure window
            # and not to a PT-specific cap. Every run past base_vehicles is a
            # candidate that _run_is_cancelled keeps in the depot unless
            # somebody still needs the line. Pre-generating and cancelling is
            # what lets the whole departure list stay sorted once, across the
            # network, which is the rule that stopped the first route getting
            # free flow and the last an hour's wait.
            runs = max(1, int(self.max_service_min // line.interval_min) + 1)
            self.departure_schedule[route_key] = [
                (i, float(i * line.interval_min)) for i in range(runs)
            ]

    def _queues_for_traffic(self, mode: str, edge_state: "EdgeState") -> bool:
        """Cars queue; buses, trams and bikes queue only in mixed traffic.

        A bike is in traffic iff it shares space with cars — a street edge
        with no bike lane. A path, a cycle track and a rail alignment with a
        way alongside all free-run. Pedestrians stay outside the queue model
        deliberately.

        Anything on rails queues only where the rails lie in the car lane — a
        fact of the street, not of the line, which is why it asks the mode and
        not the kind: on Friedrichstraße north the M1 waits with the cars, on
        Landsberger Allee's median track it passes them.
        """
        if mode == "car":
            return True
        if mode == "bus":
            return not edge_state.has_dedicated_bus_lane
        if mode == "train":
            return edge_state.rails_in_car_lane
        if mode == "bike":
            return edge_state.bikes_share_the_road
        return False

    def _pcu_for(self, vehicle: str) -> float:
        """Car-equivalents one vehicle takes in a queue.

        `vehicle` is what drives — "car", "bus", "bike", "tram" — which for a
        line's own run is the line's kind (`_vehicle_of`).
        """
        if vehicle == "bus":
            return BUS_PCU
        if vehicle == "tram":
            return TRAM_PCU
        if vehicle == "bike":
            return BIKE_PCU
        return 1.0

    def _vehicle_of(self, vehicle: Vehicle) -> str:
        """What a vehicle is, for its size: a line run's kind, else its mode."""
        line_key = self.line_by_route_key.get(vehicle.route_pk)
        line = self.pt_lines.get(line_key) if line_key is not None else None
        return line.vehicle if line is not None else vehicle.mode

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

        if vehicle.mode == "bike":
            # Its own line on the link: bikes and cars never wait for each
            # other, which is both "a car overtakes a bike" and "a bike
            # filters past a jam" without a mechanism for either.
            #
            # No storage check. A physically full street does not turn a
            # cyclist away; they squeeze in. The PCU is added all the same —
            # that is how a crowd of cyclists takes room from the cars, and it
            # is the only coupling between the two.
            #
            # Ordered by readiness rather than strictly FIFO, because one
            # cyclist can always pass another.
            pcu = self._pcu_for(self._vehicle_of(vehicle))
            bisect.insort(
                edge_state.bike_queue,
                QueuedVehicle(
                    vehicle_id=vehicle_id,
                    ready_at_min=vehicle.ready_at_min,
                    pcu=pcu,
                    entered_at_min=at_min,
                ),
                key=lambda q: q.ready_at_min,
            )
            edge_state.occupancy_pcu += pcu
            edge_state.peak_occupancy_pcu = max(
                edge_state.peak_occupancy_pcu, edge_state.occupancy_pcu
            )
            vehicle.queued = True
            return True

        if vehicle.mode == "car" and not edge_state.open_to_cars:
            logger.error(
                "[SIM] Car routed over edge %s, which is a bus lane closed to "
                "cars. Letting it through on one lane so the round completes — "
                "the route should have been rejected at submit.",
                edge_state.edge_id,
            )

        pcu = self._pcu_for(self._vehicle_of(vehicle))
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
            # Resolved before the call, because _enter_edge advances nothing but
            # returns True for "the route ends here" as well as for "it is on".
            state = self._state_for_segment(vehicle.route_pk, vehicle.segment_index)
            if not self._enter_edge(vehicle_id, vehicle, at_min):
                return False
            if state is not None:
                self._trace(vehicle_id, vehicle, at_min, "e", state.edge_id)
            return True

        vehicle.at_stop = True
        vehicle.queued = False
        vehicle.reached_stop_min = at_min
        self.stop_queues.setdefault((leg.line_key, leg.board_node), []).append(
            vehicle_id
        )
        self._trace(vehicle_id, vehicle, at_min, "s", leg.board_node)
        return True

    def _line_still_wanted(self, line_key: tuple[str, int]) -> bool:
        """Whether anybody still needs a run of this line.

        Three groups, and all three have to count or a run gets cancelled out
        from under somebody:

        - people standing at one of its stops,
        - people who have not left the house yet, still in self.waiting,
        - people riding ANOTHER line towards a transfer onto this one. They
          are in neither of the first two groups, so without them a two-line
          route could lose its second bus while its rider is still on the
          first.

        A leg counts only while it has not started — leg.first_index at or
        after the rider's current segment. Somebody already aboard has
        boarded, and needs no further run.

        The stop-queue check is first because it is the cheap one: a dict
        lookup per stop, against a walk over every vehicle.
        """
        line = self.pt_lines.get(line_key)
        if line is None:
            return False

        for node in line.stops:
            if self.stop_queues.get((line_key, node)):
                return True

        routes = self.routes_by_line.get(line_key)
        if not routes:
            return False

        for entry in self.waiting:
            if entry[1] in routes:
                return True

        for vehicle in self.vehicles.values():
            if not vehicle.departed or vehicle.arrived or vehicle.stranded:
                continue
            if vehicle.route_pk not in routes:
                continue
            for leg in self.route_pt_legs.get(vehicle.route_pk, []):
                if (
                    leg.line_key == line_key
                    and leg.first_index >= vehicle.segment_index
                ):
                    return True
        return False

    def _refresh_line_demand(self):
        """Answer _line_still_wanted once a tick, for every line.

        _spawn_vehicles runs several times within one tick — the discharge
        loop calls it again whenever storage frees up — and the answer must
        not change underneath it. A run cancelled on the second pass because
        the first pass emptied the stop is a run somebody was waiting for.
        """
        self.line_wanted = {
            line_key: self._line_still_wanted(line_key) for line_key in self.pt_lines
        }
        self.anyone_under_way = self._anyone_under_way()

    def _anyone_under_way(self) -> bool:
        """Whether any PERSON is still out: on a link, at a stop, aboard, at the door.

        Line vehicles do not count. A run is under way by definition, so a
        rule that counted it would keep its line dispatching itself until the
        guard. Nor does somebody stranded at a stop no run reaches: that is the
        map-data case, and waiting for them is what _strand_hopeless_riders
        exists to stop — the broken-line fixture measured 101 runs against 12.
        """
        for vehicle in self.vehicles.values():
            if vehicle.route_pk >= 0 and not vehicle.arrived and not vehicle.stranded:
                return True
        return any(route_pk >= 0 for _depart, route_pk, _index, _speed in self.waiting)

    def _run_is_cancelled(self, line_key: tuple[str, int], run_index: int) -> bool:
        """Whether this timetabled run stays in the depot.

        The base timetable always goes: a line runs whether or not anybody
        rides it, which is what keeps its society emissions a property of the
        map rather than of the round. Past that, a run leaves while somebody
        still needs the line, AND while anybody at all is still out (F2d,
        Lukas 2026-10-02: PT keeps driving until the last car is home — "just
        fair and truthful", buses run through the quiet hours too). A jammed
        round therefore pays society CO2 for the buses that ran through its
        car tail. A run emits only if it leaves.

        A cancelled run is DROPPED from self.waiting, not deferred. An entry
        left in the list keeps the tick loop alive until its departure minute,
        so every round would run to the end of the clock, even one where
        everybody arrived in twenty minutes.
        """
        line = self.pt_lines.get(line_key)
        if line is None or run_index < line.base_vehicles:
            return False
        if self.anyone_under_way:
            return False
        return not self.line_wanted.get(line_key, False)

    def _all_departures_are_done(self) -> bool:
        """Whether anything left in self.waiting will actually still leave.

        A run nobody needs is not a pending departure. Counting it would hold
        the loop open to the end of the clock on every round that has a line
        on the map, however quickly the people got to work.

        A person's route key is positive, so line_by_route_key.get returns
        None and the walk returns False — somebody still to leave the house is
        always a pending departure.
        """
        for _depart_min, route_pk, person_index, _speed_factor in self.waiting:
            line_key = self.line_by_route_key.get(route_pk)
            if line_key is None or not self._run_is_cancelled(line_key, person_index):
                return False
        return True

    def _spawn_vehicles(self, now: float, tick_end: float):
        """Release everyone who wanted to leave by the end of this tick.

        self.waiting is sorted by wanted departure across ALL routes. A vehicle
        whose first link is full stays in the list and tries again next tick —
        it is waiting at the front door, and its clock runs from when it wanted
        to leave, not from when the street let it in.
        """
        still_waiting = []
        waiting = self.waiting
        for at, (depart_min, route_pk, person_index, speed_factor) in enumerate(waiting):
            if depart_min > tick_end:
                # Sorted by wanted departure, so everything from here on is
                # still in the future and stays exactly as it is. Copying it
                # entry by entry cost the whole list on every call, several
                # times a tick, and the list holds every run the clock allows —
                # five times as many since the clock became a guard (F2d).
                still_waiting.extend(waiting[at:])
                break

            segments = self.route_segments.get(route_pk, [])
            if not segments:
                continue
            line_key = self.line_by_route_key.get(route_pk)
            if line_key is not None and self._run_is_cancelled(line_key, person_index):
                continue

            vehicle = Vehicle(
                route_pk=route_pk,
                person_index=person_index,
                mode=segments[0].mode,
                segment_index=0,
                passenger_count=1,
                wants_to_depart_min=depart_min,
                departed=True,
                # Drawn once for this person when the departures were built,
                # and carried across every retry at the door.
                speed_factor=speed_factor,
            )
            vehicle_id = self.next_vehicle_id

            if line_key is not None:
                if not self._enter_edge(vehicle_id, vehicle, max(depart_min, now)):
                    still_waiting.append(
                        (depart_min, route_pk, person_index, speed_factor)
                    )
                    continue
                self.next_vehicle_id += 1
                self.vehicles[vehicle_id] = vehicle
                line = self.pt_lines[line_key]
                # It left the terminus, so it is on the road and it emits.
                line.vehicles += 1
                pt = PTVehicle(
                    vehicle_id=vehicle_id,
                    line_key=line_key,
                    capacity=line.capacity,
                    departure_min=depart_min,
                )
                self.pt_vehicles.append(pt)
                self.pt_by_vehicle[vehicle_id] = pt
                self._trace(
                    vehicle_id, vehicle, max(depart_min, now), "e", segments[0].edge_id
                )
                # It is standing at its first stop the moment it sets off.
                self._serve_stop(pt, max(depart_min, now))
                continue

            if self._begin_segment(vehicle_id, vehicle, max(depart_min, now)):
                self.next_vehicle_id += 1
                self.vehicles[vehicle_id] = vehicle
                if person_index == 0:
                    self.sample_vehicles[route_pk] = vehicle_id
            else:
                still_waiting.append((depart_min, route_pk, person_index, speed_factor))

        self.waiting = still_waiting

    def _pick_head(
        self, edge_state: "EdgeState", tick_end: float
    ) -> tuple[int, bool] | None:
        """Which queued vehicle leaves next: (index, forced), or None.

        One lane is one queue: only the head may leave, so a driver waiting to
        turn into a full street holds up everybody behind, whichever way they
        are going. Two or more lanes give each NEXT street its own queue — a
        turn lane — sharing the street's flow budget and its storage, so the
        cars bound for a street with room pass the ones bound for a full one.
        Within one next street the order is still the queue's own. This is
        deliberately not plain MATSim, whose link has one queue at any width.

        The deadlock escape is per junction: the first blocked head is forced
        only when nobody on the link can move and it has stood for
        DEADLOCK_TICKS.
        """
        multi_lane = edge_state.car_lanes > 1
        seen: set[int | None] = set()
        first_blocked: int | None = None

        for index, head in enumerate(edge_state.queue):
            if head.ready_at_min > tick_end:
                # Not through yet. On one lane nobody behind it passes; on
                # several the queue is ordered by readiness, and a vehicle
                # forced in over storage may sit out of order, so keep looking.
                if not multi_lane:
                    return None
                continue

            vehicle = self.vehicles[head.vehicle_id]
            next_state = self._state_for_segment(
                vehicle.route_pk, vehicle.segment_index + 1
            )
            turn = next_state.edge_id if next_state is not None else None
            if turn in seen:
                continue
            seen.add(turn)

            blocked = next_state is not None and not next_state.has_room_for(head.pcu)
            if not blocked:
                if head.pcu > edge_state.release_budget:
                    return None
                return index, False
            if first_blocked is None:
                first_blocked = index
            if not multi_lane:
                break

        if (
            first_blocked is not None
            and self.current_tick - edge_state.blocked_since_tick >= DEADLOCK_TICKS
        ):
            if edge_state.queue[first_blocked].pcu > edge_state.release_budget:
                return None
            return first_blocked, True
        return None

    def _discharge(
        self, edge_state: "EdgeState", now: float, tick_end: float, released: set[int]
    ) -> bool:
        """Release from the head of the queue while budget and space allow."""
        moved = False
        while edge_state.queue:
            pick = self._pick_head(edge_state, tick_end)
            if pick is None:
                break
            index, forced = pick
            head = edge_state.queue[index]
            vehicle = self.vehicles[head.vehicle_id]
            if forced:
                self.forced_releases += 1
                # One escape frees one car. Without this the next head is
                # forced too, and the whole release budget goes in one tick.
                edge_state.blocked_since_tick = self.current_tick

            left_at = max(head.ready_at_min, now)
            edge_state.queue.pop(index)
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

    def _discharge_bikes(
        self, edge_state: "EdgeState", now: float, tick_end: float
    ) -> bool:
        """Release from the head of the bike line.

        Much simpler than _discharge, and each omission is deliberate:

        - **no downstream storage check** — a bike is never refused entry, so
          it can never be blocked and never spills back;
        - **no deadlock escape** — nothing to escape, for the same reason;
        - **no traversal recording** — traversal_count and traversal_time_min
          are cars only and must stay so. They become EdgeState.mean_speed_kmh,
          which feeds the CO2 curve and the route preview, and a bike crossing
          at 20 km/h would report an empty 50 street as congested;
        - **not in `released`** — that set is what tells _advance_traffic a
          junction is alive, and the deadlock escape is a CAR mechanism. A
          link whose cars are gridlocked while its cyclists ride past is
          exactly the case the escape exists for, and counting the bikes as
          movement would reset blocked_since_tick every tick and hang the
          round to max_ticks.

        The return value is still needed: a bike leaving frees occupancy the
        cars share, so the tick's `while moved:` loop has to run again.
        """
        moved = False
        while edge_state.bike_queue:
            head = edge_state.bike_queue[0]
            if edge_state.bike_release_budget < 1.0:
                break
            if head.ready_at_min > tick_end:
                break

            vehicle = self.vehicles[head.vehicle_id]
            left_at = max(head.ready_at_min, now)
            edge_state.bike_queue.pop(0)
            edge_state.occupancy_pcu -= head.pcu
            edge_state.bike_release_budget -= 1.0
            moved = True

            vehicle.segment_index += 1
            segments = self.route_segments.get(vehicle.route_pk, [])
            if vehicle.segment_index >= len(segments):
                vehicle.arrived = True
                vehicle.arrived_min = left_at
            else:
                # _begin_segment puts it back into free_running itself if the
                # next link is a cycle track or a path, and sends it to a stop
                # queue if the route changes to a PT leg here.
                vehicle.mode = segments[vehicle.segment_index].mode
                if not self._begin_segment(head.vehicle_id, vehicle, left_at):
                    # Only reachable if the route changes mode here and the
                    # next link is a full street.
                    self._force_enter(head.vehicle_id, vehicle, left_at)
        return moved

    def _force_enter(self, vehicle_id: int, vehicle: Vehicle, at_min: float):
        """Enter a full link regardless of storage (deadlock escape only)."""
        edge_state = self._state_for_segment(vehicle.route_pk, vehicle.segment_index)
        if edge_state is None:
            vehicle.arrived = True
            vehicle.arrived_min = at_min
            return
        pcu = self._pcu_for(self._vehicle_of(vehicle))
        speed = self._free_speed_for(vehicle, edge_state)
        travel_min = edge_state.distance_m / 1000.0 / speed * 60.0 if speed > 0 else 0.0
        vehicle.entered_edge_min = at_min
        vehicle.ready_at_min = at_min + travel_min
        vehicle.queued = True
        edge_state.queue.append(
            QueuedVehicle(vehicle_id, vehicle.ready_at_min, pcu, at_min)
        )
        edge_state.occupancy_pcu += pcu
        self._trace(vehicle_id, vehicle, at_min, "e", edge_state.edge_id)

    def _advance_free_running(self, now: float, tick_end: float):
        """Move everything that does not interact with car traffic.

        Over a snapshot, because the set grows underneath: a PT vehicle that
        free-runs — a train always, a bus on a dedicated lane — serves its
        stops from in here, and _alight puts a rider whose next leg is a walk
        or a cycle track straight back into self.free_running. Iterating the
        live set raised "Set changed size during iteration" and killed the
        whole round on its first tick.

        Whoever is added mid-pass is walked on the next tick, which is what
        already happens to a rider set down by a bus in mixed traffic: that
        one is discharged from the queue, after this loop has run. It costs
        no time either way — arrived_min comes off ready_at_min, which
        _enter_edge set from the moment the doors opened, so the tick that
        picks the walker up cannot move the trip.
        """
        done = []
        for vehicle_id in list(self.free_running):
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
        self.line_served_nodes.add((pt.line_key, node))

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
            self._trace(rider_id, rider, at_min, "r", pt.vehicle_id)
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
            self._trace(rider_id, rider, at_min, "s", leg.alight_node)

    def _finish_run(self, pt: PTVehicle, at_min: float):
        """The vehicle has reached the end of the line. Everybody off."""
        line = self.pt_lines.get(pt.line_key)
        pt.finished = True
        self.line_has_finished_run.add(pt.line_key)
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

    def _visiting_order(self) -> list["EdgeState"]:
        """The order this tick's discharge passes visit the links in.

        Of the links feeding one junction, the one visited first takes every
        slot a discharge frees, and the others only move when the deadlock
        escape fires. So the order is shuffled every tick: over a round each
        feeder goes first equally often — the zipper (Reißverschluss), on
        average rather than car by car. The generator is seeded from the tick
        alone, so `self.rng` is untouched and no other draw moves.

        Not a rotation: rotating by one link per tick puts a feeder first for
        as many ticks as the gap before it in dict order, which is arbitrary.
        """
        states = list(self.edge_states.values())
        random.Random(self.current_tick).shuffle(states)
        return states

    def _advance_traffic(self):
        """One simulation tick."""
        now = self.current_tick * self.tick_duration_min
        tick_end = now + self.tick_duration_min

        for edge_state in self.edge_states.values():
            edge_state.release_budget = edge_state.flow_per_tick(self.tick_duration_min)
            edge_state.bike_release_budget = edge_state.bike_flow_per_tick(
                self.tick_duration_min
            )

        self._refresh_line_demand()
        self._spawn_vehicles(now, tick_end)
        self._advance_free_running(now, tick_end)

        # A vehicle may cross several links within one tick — its own clock
        # (ready_at_min) is what bounds it, not the tick. So keep making
        # passes until nothing moves.
        states = self._visiting_order()
        released: set[int] = set()
        moved = True
        while moved:
            moved = False
            for edge_state in states:
                if self._discharge(edge_state, now, tick_end, released):
                    moved = True
                if self._discharge_bikes(edge_state, now, tick_end):
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
        self._strand_hopeless_riders(tick_end)
        self.held_at_origin = self._held_at_origin(tick_end)

    def _record_edge_traffic(self):
        """Sample every link with something on it, as this tick leaves it.

        Collected, not written: the adapter turns `link_samples` into rows once
        the round is done. Written here, row by row in the middle of the tick
        loop, it was the last thing that tied the loop to the database.
        """
        for edge_id, state in self.edge_states.items():
            held = self.held_at_origin.get(edge_id, 0)
            # `held` on its own is enough to record a row: an origin link with
            # a queue outside it and nothing on it is the case the heatmap was
            # blind to, and skipping it would keep it that way.
            if state.queue or state.traversal_count or held:
                self.link_samples.append(
                    LinkSample(
                        edge_id=edge_id,
                        time_tick=self.tick_offset + self.current_tick,
                        vehicle_count=len(state.queue),
                        waiting_count=held,
                        speed_kmh=state.mean_speed_kmh,
                    )
                )

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
        for depart_min, route_pk, _person_index, _speed_factor in self.waiting:
            if depart_min > tick_end:
                break
            segments = self.route_segments.get(route_pk, [])
            if not segments:
                continue
            edge_id = segments[0].edge_id  # type: ignore
            held[edge_id] = held.get(edge_id, 0) + 1
        return held

    def progress_percent(self) -> int:
        """How far the round is, by people done, over both passes.

        The bar used to be tick / max_ticks, which stopped meaning anything once
        a pass ran until everybody was home: against the guard it would sit at
        2 % and jump to the result. With a way home the morning is the first
        half and the evening the second. Somebody stranded at a stop no run
        reaches counts as done — nothing more will happen to them.
        """
        if self.home_pass is not None:
            return int(50 + 50 * self.home_pass._share_done())
        return int((50 if self.expects_way_home else 100) * self._share_done())

    def _share_done(self) -> float:
        people = sum(
            len(schedule)
            for route_pk, schedule in self.departure_schedule.items()
            if route_pk >= 0 and self.route_segments.get(route_pk)
        )
        if not people:
            return 1.0
        done = sum(
            1
            for vehicle in self.vehicles.values()
            if vehicle.route_pk >= 0 and (vehicle.arrived or vehicle.stranded)
        )
        return min(1.0, done / people)

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

    def _trace(
        self,
        vehicle_id: int,
        vehicle: Vehicle,
        at_min: float,
        kind: str,
        ref: int | None,
    ):
        """Record one position change for a vehicle the replay follows.

        `kind` is where it is from now until its next event:
          "e" — crossing edge `ref`, entering it at node `from_node`
          "s" — standing at node `ref`, waiting for a line
          "r" — riding vehicle `ref`, so its position is that vehicle's

        One timestamp per event is enough: entering link N+1 IS leaving link N,
        because the caller passes the same `left_at` to both. _build_replay
        pairs them and closes the last one from the vehicle's own arrival.

        Sampling is by person index, never by a draw — see REPLAY_PEOPLE_PER_DOT.
        A line vehicle (route_pk < 0) is always followed: there are only a few
        dozen per round and a rider's "r" leg has to resolve to one.
        """
        if vehicle.route_pk >= 0 and vehicle.person_index % self.trace_stride:
            return

        from_node = None
        if kind == "e":
            chain = self.route_nodes.get(vehicle.route_pk, [])
            if 0 <= vehicle.segment_index < len(chain):
                from_node = chain[vehicle.segment_index]

        self.trace.setdefault(vehicle_id, []).append((at_min, kind, ref, from_node))

    def build_replay(self) -> dict:
        """Turn the event log into legs the frontend can interpolate.

        A leg is a pair of consecutive events; the tail is closed from the
        vehicle's own arrival, so no arrival site needs a hook of its own.
        Everything here is a time the simulation computed, in continuous
        minutes from the start of the departure window — never a tick bucket,
        which is why playback smoothness does not depend on tick_duration_min.

        The way home is a second engine with a clock and vehicle ids of its
        own. Its dots are appended with both moved: minutes by the same offset
        its street snapshots carry (`tick_offset`), ids past the morning's, so
        one id still names one vehicle and an `"r"` leg still resolves to it.
        """
        dots, end_min = self._replay_dots("out", 0.0, 0)
        home = self.home_pass
        home_start = None
        endings = dict(self.non_arrivals)
        people = {self: self._people_and_dots()}

        if home is not None:
            home_start = home.tick_offset * home.tick_duration_min
            id_offset = 1 + max((dot["id"] for dot in dots), default=-1)
            home_dots, home_end = home._replay_dots("home", home_start, id_offset)
            dots += home_dots
            end_min = max(end_min, home_end)
            for ending, count in home.non_arrivals.items():
                endings[ending] += count
            people[home] = home._people_and_dots()

        dots.sort(key=lambda dot: dot["id"])
        total_people = sum(p for p, _ in people.values())
        total_dots = sum(d for _, d in people.values())
        return {
            "version": REPLAY_FORMAT_VERSION,
            "people_per_dot": (
                round(total_people / total_dots, 2)
                if total_dots
                else float(self.trace_stride)
            ),
            "tick_duration_min": self.tick_duration_min,
            "window_min": DEPARTURE_WINDOW_MIN,
            "end_min": round(end_min, 2),
            # Where the evening's clock starts, None when there is no evening.
            # The screen's midday fast-forward is the gap before this.
            "home_start_min": home_start,
            "dots": dots,
            # People, not dots. Added inside format 1: a recording without it
            # is read the old way, from the sample.
            "endings": endings,
        }

    def _replay_dots(
        self, which: str, time_offset: float, id_offset: int
    ) -> tuple[list, float]:
        """This pass's dots, moved onto the round's clock. See _build_replay."""
        stopped_at = self.current_tick * self.tick_duration_min
        dots = []
        end_min = 0.0

        for vehicle_id, events in self.trace.items():
            vehicle = self.vehicles.get(vehicle_id)
            if vehicle is None or not events:
                continue

            if vehicle.arrived and vehicle.arrived_min is not None:
                closed_at, ending = vehicle.arrived_min, "arrived"
            elif vehicle.stranded:
                closed_at, ending = stopped_at, "stranded"
            else:
                closed_at, ending = stopped_at, "unfinished"

            legs = []
            for index, (at_min, kind, ref, from_node) in enumerate(events):
                until = events[index + 1][0] if index + 1 < len(events) else closed_at
                if until <= at_min:
                    # Two events at the same instant: a link crossed in no time,
                    # or a rider set down and picked up again. Nothing to draw.
                    continue
                if kind == "r" and ref is not None:
                    ref += id_offset
                legs.append(
                    [
                        kind,
                        ref,
                        round(at_min + time_offset, 2),
                        round(until + time_offset, 2),
                        from_node,
                    ]
                )

            if not legs:
                continue
            end_min = max(end_min, legs[-1][3])

            pt = self.pt_by_vehicle.get(vehicle_id)
            line = self.pt_lines.get(pt.line_key) if pt else None
            route = self.agent_routes.get(vehicle.route_pk)
            dots.append(
                {
                    "id": vehicle_id + id_offset,
                    "pass": which,
                    # None for a line vehicle: it belongs to nobody's agent.
                    "route": vehicle.route_pk if vehicle.route_pk >= 0 else None,
                    "agent": route.agent_id if route else None,
                    "line": line.name if line else None,
                    "mode": (
                        route.transport_mode
                        if route
                        else (line.mode if line else vehicle.mode)
                    ),
                    # When this person wanted to leave. The gap between `wants`
                    # and the first leg IS the queue at the front door — the
                    # thing no instrument could see before stau-sichtbar.
                    "wants": round(vehicle.wants_to_depart_min + time_offset, 2),
                    "legs": legs,
                    "end": ending,
                }
            )

        return dots, end_min

    def _people_and_dots(self) -> tuple[int, int]:
        """People this pass carries and the dots sampled from them."""
        people = sampled = 0
        for route_pk, schedule in self.departure_schedule.items():
            if route_pk < 0:
                continue
            people += len(schedule)
            sampled += -(-len(schedule) // self.trace_stride)
        return people, sampled

    def _people_per_dot(self) -> float:
        """How many people one person-dot stands for, as actually sampled.

        Each route samples index 0, stride, 2·stride, …, so a Gruppe of n is
        ceil(n / stride) dots, and the stride is the ratio only when it divides
        n: 205 people at 10 are 21 dots of 9.76. The screen prints this number
        and multiplies a crowd at a stop by it, so it has to be the real one.
        """
        people, sampled = self._people_and_dots()
        if not sampled:
            return float(self.trace_stride)
        return round(people / sampled, 2)

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
            if vehicle.at_stop:
                # wait_min is otherwise only credited at boarding
                # (_serve_stop), so the people who stood longest — still
                # standing when the clock stopped — would read as having
                # waited nothing.
                vehicle.wait_min += max(0.0, sim_end_min - vehicle.reached_stop_min)
            elapsed = max(0.0, sim_end_min - vehicle.wants_to_depart_min)
            delay = max(0.0, elapsed - self._free_flow_min(vehicle.route_pk))
            for _ in range(vehicle.passenger_count):
                agent_results["trip_times"].append(elapsed)
                agent_results["delays"].append(delay)
                agent_results["waits"].append(vehicle.wait_min)
                agent_results["not_arrived"] += 1
            ending = "stranded" if vehicle.stranded else "unfinished"
            self.non_arrivals[ending] += vehicle.passenger_count

        for depart_min, route_pk, _person_index, _speed_factor in self.waiting:
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
            # Still at the front door: no vehicle, so no dot. Only here.
            self.non_arrivals["unfinished"] += 1

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

    def run_round(
        self,
        max_ticks: int = PASS_TICK_GUARD,
        on_progress: Callable[[int, int], None] | None = None,
        way_home: "Callable[[random.Random], LinkQueueEngine] | None" = None,
    ):
        """
        Run the round: the way to work on this engine, and the way home.

        A commute is a round trip, so a round is two passes. The morning is
        this engine; the evening is a sibling built for the `home` routes —
        a fresh network, not a second half of one long clock. Eight hours lie
        between the two peaks, so nothing of the morning is still on the road,
        and a single clock would have kept every line dispatching through the
        day for the evening riders waiting in the list, charging society CO2
        for buses nobody could board. The sibling continues this pass's random
        stream, so the round is still one seeded run — which is why it is
        built here, from the generator as the morning left it, and not before.

        A round with no way home — every route written before the evening
        existed, and every one a test builds by hand — runs the morning alone,
        exactly as before.

        A pass runs until everybody is home. `max_ticks` is a guard against
        a bug, not a clock, and a pass that reaches it is logged as an error.

        Args:
            max_ticks: The guard, per pass. Tests pass a small one to stop a
                pass on purpose.
            on_progress: Called after every tick with (tick, max_ticks).
                progress_percent() is what a progress bar should show.
            way_home: Builds the evening's engine from the generator. None
                when there is no way home.
        """
        self.expects_way_home = way_home is not None
        self._run_pass(max_ticks, on_progress)
        self._compute_outcomes()

        if way_home is not None:
            self.home_pass = way_home(self.rng)
            # After the morning on the round's one axis: the samples are keyed
            # (edge, time_tick), so an evening starting before the morning
            # ended would collide with it.
            self.home_pass.tick_offset = max(
                HOME_PASS_EARLIEST_TICK, self.current_tick + 1
            )
            self.home_pass._run_pass(max_ticks, on_progress)
            self.home_pass._compute_outcomes()
            self.sim_log.header("THE WAY HOME")
            self.sim_log.write(self.home_pass.sim_log.get_text())

    def _run_pass(
        self,
        max_ticks: int,
        on_progress: Callable[[int, int], None] | None,
    ):
        """One trip, on this engine's own network: depart, drive, arrive."""
        self.on_progress = on_progress

        # Write log header
        self.sim_log.header(
            f"SIMULATION LOG — {self.title}"
            + (" — the way home" if self.direction == "home" else "")
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

        # A line's service period is the simulation's own clock — the same
        # one the road runs on. There is no PT service cap; a full bus is a
        # wait, and the wait is already inside the trip time because the
        # clock starts at wants_to_depart_min.
        self.max_service_min = float(max_ticks * self.tick_duration_min)

        # Run morning commute
        self._generate_departures(is_morning=self.direction == "out")
        # The desired-speed draw belongs to the PERSON, not to the
        # attempt. It used to happen in _spawn_vehicles, where a traveller
        # the street turns away is discarded and rebuilt next tick with a
        # fresh draw — so someone held at the door for three ticks was
        # dealt three different desired speeds and kept the last. Worse,
        # it made the whole round's random stream depend on the pattern of
        # refusals, so any change to link occupancy re-rolled every later
        # driver and moved results by far more than the change itself.
        self.waiting: list[tuple[float, int, int, float]] = sorted(
            (
                (
                    depart_min,
                    route_pk,
                    person_index,
                    # A line vehicle runs to its timetable, not to a
                    # driver's taste, so it takes NO draw — not merely a
                    # factor of 1.0. Its route key is the negative one
                    # _register_pt_line gave it.
                    1.0 if route_pk < 0 else draw_driver_speed_factor(self.rng),
                )
                for route_pk, schedule in self.departure_schedule.items()
                for person_index, depart_min in schedule
            ),
            # Explicitly on the first three: the draw must never decide
            # who leaves first.
            key=lambda entry: entry[:3],
        )

        total_departures = sum(len(s) for s in self.departure_schedule.values())
        logger.info(
            f"[SIM] Generated {total_departures} departures for "
            f"{len(self.departure_schedule)} agents"
        )

        self.sim_log.header("SIMULATION TICK LOG (sample vehicle per route)")
        scheduled_runs = sum(
            len(self.departure_schedule.get(key, []))
            for key in self.line_by_route_key
        )
        base_runs = sum(l.base_vehicles for l in self.pt_lines.values())
        self.sim_log.write(
            f"Total vehicles to spawn: {total_departures - scheduled_runs} people "
            f"({len(self.agent_routes)} routes x {self.people_per_agent}), plus "
            f"{base_runs} timetabled PT runs from {len(self.pt_lines)} lines and "
            f"as many more as the demand asks for"
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

            # Record traffic every tick. Every fifth was one sample per 25
            # simulated minutes — nine frames for a whole morning, which is
            # a chart, not an animation. The per-edge filter in
            # _record_edge_traffic keeps this to the active links.
            self._record_edge_traffic()

            # Progress callback
            if on_progress:
                on_progress(self.current_tick, max_ticks)

            # Check if all vehicles arrived
            if self._all_departures_are_done() and self._all_vehicles_arrived():
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
        not_home = self.non_arrivals["unfinished"] + self.non_arrivals["stranded"]
        if self.current_tick >= max_ticks and not_home:
            logger.error(
                f"[SIM] The {max_ticks}-tick guard stopped the {self.direction} "
                f"pass of {self.ref} with {not_home} people not "
                f"home. A pass runs until everybody is home, so this is a bug in "
                f"the model or in the map."
            )
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

    def _compute_outcomes(self):
        """Work out this pass's results per route. Writes nothing.

        What a route costs is read off the network as it stands at the end of
        THIS pass — the speeds its links ran at, the timetable its lines ran —
        so it has to be taken before the next pass replaces nothing but could
        just as well sit beside it. The rows come after both passes, in
        `_save_results`.
        """
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
                elif seg.mode == "bike":
                    self.sim_log.write(
                        f"    seg {seg.order} ({seg.mode}): {es.distance_m:.0f}m → 0g "
                        f"(zero emission, €{BIKE_COST_PER_KM * dist_km:.3f}/person)"
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

            self.outcomes[route_pk] = RouteOutcome(
                mean_trip_time_min=mean_trip_time,
                mean_delay_min=mean_delay,
                mean_wait_min=mean_wait,
                co2_g=co2,
                cost_eur=cost,
                paid_eur=paid,
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
                extra = line.vehicles - line.base_vehicles
                runs = f"{line.vehicles} runs"
                if extra > 0:
                    runs += f" ({line.base_vehicles} timetabled + {extra} extra)"
                self.sim_log.write(
                    f"  {line.name} ({line.mode}): {runs} x "
                    f"{line.line_km:.2f}km every {line.interval_min}min, "
                    f"{line.capacity} seats — {line.boarded} boarded, "
                    f"{line.denied} refusals at the stop, "
                    f"{line.stranded} waiting at a stop it does not serve, "
                    f"{line.person_km:.0f} Personen-km carried"
                )
        self.pass_total_co2_g = total_co2
        self.pass_total_cost_eur = total_cost
        self.pass_network_co2_g = network_co2
        self.pass_network_cost_eur = network_cost

    def _calculate_emissions_and_cost(
        self, route: Route
    ) -> tuple[float, float, float]:
        """CO2, cost and fare for one agent's route, for all its people.

        - Car: speed-dependent per car_emissions_g_per_km — a jam burns more
          per kilometre, and that is what makes clearing one worth a vote.
          Each person drives alone, so per-person is per-vehicle.
        - Bus/train: this route's slice of the LINE's own emissions and cost,
          weighted by the person-kilometres it contributes. Not divided by
          capacity: a timetable does not get cleaner because the seats are
          empty.
        - Bike: BIKE_COST_PER_KM, flat, in both cost and paid — the rider
          carries all of it. No CO2.
        - Walk: nothing.

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

            if seg.mode == "bike":
                per_person_cost += BIKE_COST_PER_KM * distance_km
                per_person_paid += BIKE_COST_PER_KM * distance_km
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

    def observed_speeds(self) -> dict[int, float]:
        """Each link's car speed as driven this round, for the next one's router.

        This is what StreetPerRound.speed_under_load has always been for. It
        was written from a mean over snapshots that were themselves means; now
        it is the one figure the run measured.

        Both passes, pooled per link: a street the evening drives again (a
        loop, a one-way pair) has crossings from both, and the speed is the
        length over the mean of all of them — the same figure
        EdgeState.mean_speed_kmh gives for one pass. Only links a car crossed.
        """
        crossings: dict[int, tuple[int, float, EdgeState]] = {}
        for engine in [self] + ([self.home_pass] if self.home_pass else []):
            for edge_id, state in engine.edge_states.items():
                if not state.traversal_count:
                    continue
                count, minutes, _ = crossings.get(edge_id, (0, 0.0, state))
                crossings[edge_id] = (
                    count + state.traversal_count,
                    minutes + state.traversal_time_min,
                    state,
                )

        return {
            edge_id: (
                state.distance_m / 1000.0 / (minutes / count / 60.0)
                if minutes > 0
                else state.free_flow_speed_kmh
            )
            for edge_id, (count, minutes, state) in crossings.items()
        }

    def _strand_hopeless_riders(self, at_min: float):
        """Give up only on a stop no vehicle of this line will ever serve.

        Capacity never strands anybody. A full bus is a WAIT: the line keeps
        running as long as somebody needs it, for as long as the simulation
        runs, and the wait is already inside the trip time because the clock
        starts at wants_to_depart_min. Somebody the clock genuinely runs out
        on is booked by _record_non_arrivals exactly as a car still on a
        jammed link is — a real lower bound on a real trip.

        What cannot be waited out is a stop the line does not actually serve:
        a route naming a board node that _register_pt_line trimmed off the
        line, because the line's edges do not connect. That is a MAP DATA
        defect, not a capacity outcome, and several lines on map v1 have it
        (S5, S7, M1, M48, 265). Once ONE run has finished its whole journey
        the set of nodes this line serves is known, so anybody queued anywhere
        else is waiting for nothing.

        Leaving them there is not merely slow: they keep _line_still_wanted
        true, so the line would dispatch to the end of the clock and pay
        society CO2 for every run. Measured on a deliberately disconnected
        line, 1000 people waiting at a stop it does not serve: with this
        method, 12 runs and 28.8 kg over 22 ticks; without it, 101 runs and
        242 kg over the full 200.

        A rider _alight put back into this queue because the street outside
        the stop was full is not touched, and now cannot be: the line demonstrably
        serves the node it just set them down at, so the loop skips it before
        the _leg_at guard is even reached.
        """
        for line_key, line in self.pt_lines.items():
            if line_key not in self.line_has_finished_run:
                continue
            for (queue_line, node), queue in list(self.stop_queues.items()):
                if queue_line != line_key or not queue:
                    continue
                if (line_key, node) in self.line_served_nodes:
                    continue
                remaining = []
                for rider_id in queue:
                    rider = self.vehicles.get(rider_id)
                    if rider is None or not rider.at_stop:
                        continue
                    leg = self._leg_at(rider.route_pk, rider.segment_index)
                    if leg is None or leg.line_key != line_key:
                        remaining.append(rider_id)
                        continue
                    rider.at_stop = False
                    rider.stranded = True
                    rider.wait_min += max(0.0, at_min - rider.reached_stop_min)
                    line.stranded += 1
                    logger.warning(
                        "[SIM] %s does not serve node %s, which a route asks "
                        "it to. Check the map data.",
                        line.name,
                        node,
                    )
                queue[:] = remaining
