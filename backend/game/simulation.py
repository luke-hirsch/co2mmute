"""
The adapter between a game round and the traffic engine.

Rows in, `sim.linkqueue.LinkQueueEngine`, rows out. `TrafficSimulator` reads a
round's routes, the lines on its map version and the links they run on into a
`sim.scenario.Scenario`, lets the engine run the round, and writes what came
out: one `AgentSimulationResult` per round trip, the totals, the street
snapshots, the speeds the next round routes on, the replay and the log.

Decided here and not in the engine is everything that needs the map's rows:
which version a round runs on, which side of the street a line drives, and
what a game with no map falls back to.

`TrafficSimulator` keeps the name, path and signature it always had —
`game/signals.py` constructs it and tests patch the literal string — and it is
the engine as well as the adapter (a subclass), so everything a test reads off
a finished run is still there to read.
"""

import logging
import random
from collections.abc import Callable

from maps.models import BusLine, Edge, StreetPerRound, TrainLine

# The engine itself lives in `sim/`; these are re-exported because tests and
# older code import them from here.
from sim import (  # noqa: F401
    BIKE_PCU,
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
from sim.linkqueue import (  # noqa: F401
    DEPARTURE_WINDOW_MIN,
    FALLBACK_BUS_SPEED_KMH,
    FALLBACK_TRAIN_SPEED_KMH,
    HOME_PASS_EARLIEST_TICK,
    PASS_TICK_GUARD,
    REPLAY_FORMAT_VERSION,
    REPLAY_PEOPLE_PER_DOT,
    LinkQueueEngine,
    PTLeg,
)
from sim.outcome import RouteOutcome  # noqa: F401
from sim.scenario import Line, Link, Params, Route, Scenario

from game.models import (
    AgentRoute,
    AgentSimulationResult,
    EdgeTrafficSnapshot,
    GameRound,
    SimulationResult,
)

logger = logging.getLogger(__name__)

# Speeds for a game whose map is gone (`GameSession.game_map` is SET_NULL).
# A map states its own; these are only ever the last resort.
FALLBACK_WALK_SPEED_KMH = 5
FALLBACK_BIKE_SPEED_KMH = 20
FALLBACK_DEFAULT_CAR_SPEED_KMH = 50


class TrafficSimulator(LinkQueueEngine):
    """
    One round of a game, simulated: its rows in, the engine, its rows out.
    """

    def __init__(
        self,
        game_round: GameRound,
        scale: float = 100.0,
        seed: int | None = None,
        direction: str = AgentRoute.Direction.OUT,
        rng: random.Random | None = None,
    ):
        """
        Read the round into a scenario and set the engine up on it.

        Args:
            game_round: The game round to simulate
            scale: Meters per coordinate unit (for distance calculation)
            seed: Seed for this round's draws. Defaults to the round pk, so a
                round always replays identically — in a test, in a debugger, or
                after a worker restart. Pass one explicitly to sweep the same
                round over many seeds (calibration), which is the only reason
                the argument exists.
            direction: Which trip this pass simulates, `out` (the way to work)
                or `home`. A round trip is two passes over two fresh networks —
                see `run_simulation`. Only the routes of this direction load.
            rng: The generator to continue, for the home pass, so one round is
                still one seeded stream and replays identically.
        """
        self.game_round = game_round
        self.simulation_result: SimulationResult | None = None
        self.seed = game_round.pk if seed is None else seed
        # The rows behind the scenario's routes, by pk: the result rows point
        # at them, and the way home is paired with the way there through them.
        self.route_rows: dict[int, AgentRoute] = {}
        super().__init__(
            self._scenario(scale, direction),
            rng if rng is not None else random.Random(self.seed),
        )

    # --- rows in ------------------------------------------------------

    def _scenario(self, scale: float, direction: str) -> Scenario:
        """Everything the engine needs from this round, read once."""
        game_session = self.game_round.game
        game_map = game_session.game_map

        routes = self._read_routes(direction)
        bus_speeds, train_speeds = self._read_line_speeds(routes)
        lines = self._read_lines(bus_speeds, train_speeds)
        links = self._read_links(
            {seg.edge_id for route in routes for seg in route.segments}
            | {edge_id for line in lines for edge_id in line.edge_ids},
            scale,
        )

        return Scenario(
            params=Params(
                people_per_agent=game_session.people_per_agent,
                tick_duration_min=game_session.tick_duration_min,
                morning_departure_hour=game_session.morning_departure_hour,
                evening_departure_hour=game_session.evening_departure_hour,
                departure_std_dev_min=game_session.departure_std_dev_min,
                walk_speed_kmh=(
                    game_map.walk_speed_kmh if game_map else FALLBACK_WALK_SPEED_KMH
                ),
                bike_speed_kmh=(
                    game_map.bike_speed_kmh if game_map else FALLBACK_BIKE_SPEED_KMH
                ),
                default_car_speed_kmh=(
                    game_map.default_car_speed_kmh
                    if game_map
                    else FALLBACK_DEFAULT_CAR_SPEED_KMH
                ),
            ),
            links=tuple(links),
            routes=tuple(routes),
            lines=tuple(lines),
            bus_speeds=bus_speeds,
            train_speeds=train_speeds,
            direction=str(direction),
            title=(
                f"Round {self.game_round.round_number} "
                f"(Game: {game_session.game_name})"
            ),
            ref=f"round {self.game_round.pk}",
            scale=scale,
        )

    def _read_routes(self, direction: str) -> list[Route]:
        """This direction's routes, in the order the round's draws follow."""
        from game.models import PlayerMove

        player_moves = PlayerMove.objects.filter(session_round=self.game_round)
        logger.info(f"[SIM] Loading routes for {player_moves.count()} player moves")

        routes = []
        for move in player_moves:
            player_name = move.player.name or f"Player {move.player.player_id}"
            rows = AgentRoute.objects.filter(
                player_move=move, direction=direction
            ).prefetch_related("segments", "segments__edge")
            for route in rows:
                self.route_rows[route.pk] = route
                routes.append(
                    Route(
                        pk=route.pk,
                        agent_id=route.agent_id,
                        transport_mode=route.transport_mode,
                        segments=tuple(
                            Segment(
                                edge_id=row.edge_id,  # type: ignore
                                order=row.order,
                                mode=row.mode,
                                pt_line_id=row.pt_line_id,  # type: ignore
                            )
                            for row in route.segments.order_by("order")  # type: ignore
                        ),
                        # The report the host downloads names the player. It
                        # never reaches the server log.
                        label=(
                            f"{player_name}/Agent#{route.agent_id} "
                            f"({route.transport_mode})"
                        ),
                        total_distance_m=route.total_distance_m,
                        estimated_time_min=route.estimated_time_min,
                    )
                )
        return routes

    def _read_line_speeds(
        self, routes: list[Route]
    ) -> tuple[dict[int, float], dict[int, float]]:
        """The speed of every line a route names, on this version or not."""
        bus_line_ids = set()
        train_line_ids = set()
        for route in routes:
            for seg in route.segments:
                if seg.pt_line_id:
                    if seg.mode == "bus":
                        bus_line_ids.add(seg.pt_line_id)
                    elif seg.mode == "train":
                        train_line_ids.add(seg.pt_line_id)

        bus_speeds: dict[int, float] = {}
        train_speeds: dict[int, float] = {}
        if bus_line_ids:
            for bus_line in BusLine.objects.filter(id__in=bus_line_ids):
                bus_speeds[bus_line.pk] = bus_line.bus_speed_kmh
            logger.info(f"[SIM] Loaded {len(bus_speeds)} bus line speeds")
        if train_line_ids:
            for train_line in TrainLine.objects.filter(id__in=train_line_ids):
                train_speeds[train_line.pk] = train_line.train_speed_kmh
            logger.info(f"[SIM] Loaded {len(train_speeds)} train line speeds")
        return bus_speeds, train_speeds

    def _read_lines(
        self, bus_speeds: dict[int, float], train_speeds: dict[int, float]
    ) -> list[Line]:
        """Every PT line on the map version this round runs on, as it drives.

        Every line, not only the ridden ones: a timetable runs whether anyone
        is aboard or not, and a line nobody rides emitting nothing was the
        defect this guide exists to fix.

        `active_map_version` is set when the game starts (`GameSessionViewSet`
        writes the base version), so it is the right filter for a real round;
        the base version is the fallback for a round built by hand or in a
        test, and an unversioned map falls through to every line on it.

        The *chain* is filtered by the same version, not taken whole. A version
        that changes a street clones it and runs the line over the clone, so the
        unfiltered chain mixed the clone in with the original it replaced —
        `_register_pt_line`'s `usable` trim then cut the line at the first link
        that was not on this version's network, which is how a line with a
        perfectly good chain came to strand its riders and keep dispatching, and
        paying society CO2, to the end of the clock.
        """
        from maps.models import MapVersion
        from maps.versions import bus_chain_rows, train_chain_rows

        game_map = self.game_round.game.game_map
        if not game_map:
            return []

        version = (
            self.game_round.game.active_map_version
            or MapVersion.objects.filter(game_map=game_map, base_version=True).first()
        )

        bus_lines = BusLine.objects.filter(game_map=game_map)
        train_lines = TrainLine.objects.filter(game_map=game_map)
        if version is not None:
            bus_lines = bus_lines.filter(map_versions=version)
            train_lines = train_lines.filter(map_versions=version)

        streets = self._links_by_ends(game_map, version, streetedge__isnull=False)
        tracks = self._links_by_ends(game_map, version, trainedge__isnull=False)

        lines = []
        for line in bus_lines.distinct():
            bus_speeds.setdefault(line.pk, line.bus_speed_kmh)
            edges = [
                link.street_edge.edge
                for link in bus_chain_rows(line, version).select_related(
                    "street_edge__edge__start_node",
                    "street_edge__edge__end_node",
                )
            ]
            edges = self._its_own_way(line.name, edges, streets)
            lines.append(
                Line(
                    "bus",
                    line.pk,
                    line.name,
                    tuple(edge.pk for edge in edges),
                    line.intervall,
                    line.bus_capacity,
                )
            )

        for line in train_lines.distinct():
            train_speeds.setdefault(line.pk, line.train_speed_kmh)
            edges = [
                link.train_edge.edge
                for link in train_chain_rows(line, version).select_related(
                    "train_edge__edge__start_node",
                    "train_edge__edge__end_node",
                )
            ]
            edges = self._its_own_way(line.name, edges, tracks)
            lines.append(
                Line(
                    "train",
                    line.pk,
                    line.name,
                    tuple(edge.pk for edge in edges),
                    line.intervall,
                    line.train_capacity,
                )
            )
        return lines

    @staticmethod
    def _links_by_ends(game_map, version, **has_row) -> dict[tuple[int, int], list]:
        """Every link of one kind on this version, by (from node, to node)."""
        links = Edge.objects.filter(game_map=game_map, **has_row)
        if version is not None:
            links = links.filter(map_versions=version)
        by_ends: dict[tuple[int, int], list] = {}
        for edge in links.distinct().select_related("start_node", "end_node"):
            by_ends.setdefault((edge.start_node_id, edge.end_node_id), []).append(edge)  # type: ignore
        return by_ends

    @staticmethod
    def _its_own_way(name: str, edges: list, links: dict) -> list:
        """A line's links, each one the direction the line travels it.

        Each direction of a street is its own link with its own queue (F2a), and
        a line vehicle queues on the link its chain row names. But a row may
        name either direction — node_chain reads the travel order from the
        nodes, and the editor lets a line be drawn on either side — so the
        shipped map's bus `100` eastbound named the westbound links on five of
        its seven streets. On the way home it waited among the cars going home
        and at the front wanted the link they were coming from: two full links
        waiting on each other, which only the deadlock escape breaks.

        So a link named against the line's direction is swapped for the one
        going its way on this version, if there is exactly one the mode may use.
        None — a one-way street, a contraflow lane — or several, and the line
        drives what was drawn. The stops are nodes and do not move.
        """
        stops = node_chain([(e.start_node_id, e.end_node_id) for e in edges])
        own_way = list(edges)
        for i, edge in enumerate(edges[: max(0, len(stops) - 1)]):
            here, there = stops[i], stops[i + 1]
            if (edge.start_node_id, edge.end_node_id) != (there, here):
                continue
            candidates = links.get((here, there), [])
            if len(candidates) == 1:
                own_way[i] = candidates[0]
        swapped = sum(a.pk != b.pk for a, b in zip(edges, own_way))
        if swapped:
            logger.info(
                "[SIM] PT line %s is drawn on the other side of %s of its %s "
                "links; it drives its own side.",
                name,
                swapped,
                len(edges),
            )
        return own_way

    def _read_links(self, edge_ids: set[int], scale: float) -> list[Link]:
        """Every link a route or a line names, in the `Edge` model's ordering.

        The order is load-bearing: the engine draws each link's capacity in it
        and starts every tick's visiting shuffle from it. `Meta.ordering` is
        total (it ends on the pk), so the links a pass actually uses come out
        in the same relative order whatever else is in the set.
        """
        logger.info(f"[SIM] Initializing {len(edge_ids)} unique edges")
        edges = Edge.objects.filter(id__in=edge_ids).select_related(
            "start_node", "end_node", "game_map"
        )

        links = []
        for edge in edges:
            street_edge = edge.streetedge_set.first()  # type: ignore
            start_name = edge.start_node.name or f"Node {edge.start_node.pk}"
            end_name = edge.end_node.name or f"Node {edge.end_node.pk}"
            links.append(
                Link(
                    edge_id=edge.pk,
                    start_node_id=edge.start_node_id,  # type: ignore
                    end_node_id=edge.end_node_id,  # type: ignore
                    distance_m=edge.euclidean_2d_distance() * scale,
                    is_street=street_edge is not None,
                    speed_limit_kmh=street_edge.speed_limit if street_edge else 0.0,
                    lanes=street_edge.lanes if street_edge else 1,
                    has_dedicated_bus_lane=(
                        street_edge.dedicated_bus_lane if street_edge else False
                    ),
                    has_bike_lane=edge.bike_lane,
                    name=edge.name or "",
                    label=f"{start_name} → {end_name}",
                )
            )
        return links

    def _has_way_home(self) -> bool:
        return AgentRoute.objects.filter(
            player_move__session_round=self.game_round,
            direction=AgentRoute.Direction.HOME,
        ).exists()

    def _way_home(self, rng: random.Random) -> "TrafficSimulator":
        """The evening's simulator, continuing the morning's generator."""
        home = TrafficSimulator(
            self.game_round,
            scale=self.scale,
            seed=self.seed,
            direction=AgentRoute.Direction.HOME,
            rng=rng,
        )
        home.simulation_result = self.simulation_result
        return home

    # --- the run ------------------------------------------------------

    def run_simulation(
        self,
        max_ticks: int = PASS_TICK_GUARD,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> SimulationResult:
        """
        Run the full simulation, the way to work and the way home, and write it.

        The round itself is `LinkQueueEngine.run_round`; what is here is the
        row it runs under, which says RUNNING until everything is written and
        FAILED, with the log so far, if anything raised.

        Args:
            max_ticks: The guard, per pass — game/signals.py leaves it at the
                default. Tests pass a small one to stop a pass on purpose.
            on_progress: Called after every tick with (tick, max_ticks).
                progress_percent() is what a progress bar should show.

        Returns:
            SimulationResult with computed statistics
        """
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
            self.run_round(
                max_ticks,
                on_progress,
                way_home=self._way_home if self._has_way_home() else None,
            )
            self._save_results()

            # Update simulation status
            self.simulation_result.status = SimulationResult.Status.COMPLETED
            self.simulation_result.detailed_log = self.sim_log.get_text()
            self.simulation_result.replay = self.build_replay()
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

    # --- rows out -----------------------------------------------------

    def _save_results(self):
        """Write the round: one row per round trip, and the totals of both.

        The row sits on the way-to-work route. Its time is the way to work's and
        `mean_return_time_min` the way home's, and everything the Gruppe emits,
        pays or waits is the two trips added. A way to work with no way home
        reports a return time of zero, which is what it always did.
        """
        passes = [self] + ([self.home_pass] if self.home_pass else [])
        people = self.people_per_agent or 0

        EdgeTrafficSnapshot.objects.bulk_create(
            (
                EdgeTrafficSnapshot(
                    simulation=self.simulation_result,
                    edge_id=sample.edge_id,
                    time_tick=sample.time_tick,
                    vehicle_count=sample.vehicle_count,
                    waiting_count=sample.waiting_count,
                    speed_kmh=sample.speed_kmh,
                )
                for engine in passes
                for sample in engine.link_samples
            ),
            batch_size=2000,
        )

        way_home_of = {}
        if self.home_pass:
            for route in self.home_pass.route_rows.values():  # type: ignore
                way_home_of[(route.player_move_id, route.agent_id)] = route.pk  # type: ignore

        for route_pk, there in self.outcomes.items():
            route = self.route_rows[route_pk]
            home_pk = way_home_of.get((route.player_move_id, route.agent_id))  # type: ignore
            back = self.home_pass.outcomes.get(home_pk) if self.home_pass else None

            co2 = there.co2_g + (back.co2_g if back else 0.0)
            cost = there.cost_eur + (back.cost_eur if back else 0.0)
            paid = there.paid_eur + (back.paid_eur if back else 0.0)
            AgentSimulationResult.objects.create(
                simulation=self.simulation_result,
                agent_route=route,
                mean_trip_time_min=there.mean_trip_time_min,
                mean_return_time_min=back.mean_trip_time_min if back else 0.0,
                mean_cost_eur=cost / people if people else 0.0,
                mean_paid_eur=paid / people if people else 0.0,
                total_co2_g=co2,
                congestion_delay_min=there.mean_delay_min
                + (back.mean_delay_min if back else 0.0),
                wait_time_min=there.mean_wait_min
                + (back.mean_wait_min if back else 0.0),
            )

        total_co2 = sum(p.pass_total_co2_g for p in passes)
        total_cost = sum(p.pass_total_cost_eur for p in passes)
        self.simulation_result.total_co2_g = total_co2  # type: ignore
        self.simulation_result.total_cost_eur = total_cost  # type: ignore
        self.simulation_result.network_co2_g = sum(  # type: ignore
            p.pass_network_co2_g for p in passes
        )
        self.simulation_result.network_cost_eur = sum(  # type: ignore
            p.pass_network_cost_eur for p in passes
        )
        self.simulation_result.save()  # type: ignore

        logger.info(
            f"[SIM] Total CO2: {total_co2:.0f}g, Total cost: {total_cost:.2f}EUR"
        )

        # Update street speeds for next round
        self._update_street_speeds()

    def _update_street_speeds(self):
        """Store each street's observed car speed for the next round.

        The speed is the engine's (`observed_speeds`, both passes pooled); a
        link with no street under it has no row to store it on.
        """
        from maps.models import StreetEdge

        for edge_id, speed in self.observed_speeds().items():
            street_edge = StreetEdge.objects.filter(edge_id=edge_id).first()
            if not street_edge:
                continue
            StreetPerRound.objects.update_or_create(
                edge=street_edge,
                game_round=self.game_round,
                defaults={"speed_under_load": max(1, int(speed))},
            )
