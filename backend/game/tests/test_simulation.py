"""
Unit tests for the traffic simulation.

Tests cover:
- The link queue model: flow capacity, storage, spillback, deadlock escape
- Speed-dependent CO2 and cost for cars, and that a jam costs more of both
- Free-flow trip times (no longer quantised to whole ticks)
- Dedicated bus lanes and bus gates
- Bus traffic integration (a dedicated lane costs the cars nothing)
- Departure minutes, and that they are fair across routes
- Speed loading from models, and the speed_limit = 0 fallback
- Non-arrival accounting
- Simulation parameter loading
"""

from django.contrib.auth.models import User
from django.db import models
from django.test import TestCase
from maps.models import (
    BusLine,
    BusLineEdge,
    Edge,
    GameMap,
    MapVersion,
    Node,
    StreetEdge,
    TrainEdge,
    TrainLine,
    TrainLineEdge,
)

from game.models import (
    AgentRoute,
    GameRound,
    GameSession,
    Player,
    PlayerMove,
    RouteSegment,
)
from game.simulation import (
    EdgeState,
    TrafficSimulator,
)


class SimulationParameterLoadingTests(TestCase):
    """Tests for loading simulation parameters from models."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="12345")

        # Create GameMap with custom speeds
        self.game_map = GameMap.objects.create(
            name="Test Map",
            x_dim=10,
            y_dim=10,
            scale=100.0,
            walk_speed_kmh=4,
            bike_speed_kmh=25,
            default_car_speed_kmh=60,
        )

        # Create GameSession with custom simulation parameters
        self.game_session = GameSession.objects.create(
            game_host=self.user,
            game_name="Test Game",
            game_map=self.game_map,
            max_players=4,
            agent_per_player=2,
            max_rounds=5,
            max_CO2_level=1000,
            people_per_agent=500,
            tick_duration_min=10,
            morning_departure_hour=8,
            evening_departure_hour=18,
            departure_std_dev_min=15,
        )

        # Create GameRound
        self.game_round = GameRound.objects.create(
            game=self.game_session,
            round_number=1,
        )

    def test_loads_simulation_parameters(self):
        """Test that simulation parameters are loaded from GameSession."""
        simulator = TrafficSimulator(self.game_round, scale=100.0)

        self.assertEqual(simulator.people_per_agent, 500)
        self.assertEqual(simulator.tick_duration_min, 10)
        self.assertEqual(simulator.morning_departure_hour, 8)
        self.assertEqual(simulator.evening_departure_hour, 18)
        self.assertEqual(simulator.departure_std_dev_min, 15)

    def test_loads_speed_parameters(self):
        """Test that speed parameters are loaded from GameMap."""
        simulator = TrafficSimulator(self.game_round, scale=100.0)

        self.assertEqual(simulator.walk_speed_kmh, 4)
        self.assertEqual(simulator.bike_speed_kmh, 25)
        self.assertEqual(simulator.default_car_speed_kmh, 60)

    def test_fallback_speeds_when_no_map(self):
        """Test that fallback speeds are used when no map is set."""
        # Create session without map
        game_session_no_map = GameSession.objects.create(
            game_host=self.user,
            game_name="Test Game No Map",
            game_map=None,
            max_players=4,
            agent_per_player=2,
            max_rounds=5,
            max_CO2_level=1000,
        )

        game_round_no_map = GameRound.objects.create(
            game=game_session_no_map,
            round_number=1,
        )

        simulator = TrafficSimulator(game_round_no_map, scale=100.0)

        # Should use fallback values
        from game.simulation import (
            FALLBACK_BIKE_SPEED_KMH,
            FALLBACK_DEFAULT_CAR_SPEED_KMH,
            FALLBACK_WALK_SPEED_KMH,
        )

        self.assertEqual(simulator.walk_speed_kmh, FALLBACK_WALK_SPEED_KMH)
        self.assertEqual(simulator.bike_speed_kmh, FALLBACK_BIKE_SPEED_KMH)
        self.assertEqual(
            simulator.default_car_speed_kmh, FALLBACK_DEFAULT_CAR_SPEED_KMH
        )


class PTLineSpeedLoadingTests(TestCase):
    """Tests for loading PT line speeds."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="12345")

        # Create GameMap
        self.game_map = GameMap.objects.create(
            name="Test Map",
            x_dim=10,
            y_dim=10,
            scale=100.0,
        )

        # Create MapVersion
        self.map_version = MapVersion.objects.create(
            game_map=self.game_map,
            name="Base Version",
            base_version=True,
        )

        # Create nodes
        self.node1 = Node.objects.create(
            game_map=self.game_map,
            x_position=0,
            y_position=0,
        )
        self.node1.map_versions.add(self.map_version)

        self.node2 = Node.objects.create(
            game_map=self.game_map,
            x_position=1,
            y_position=1,
        )
        self.node2.map_versions.add(self.map_version)

        # Create edge
        self.edge = Edge.objects.create(
            game_map=self.game_map,
            start_node=self.node1,
            end_node=self.node2,
        )
        self.edge.map_versions.add(self.map_version)

        # Create StreetEdge
        self.street_edge = StreetEdge.objects.create(
            edge=self.edge,
            speed_limit=50,
            lanes=2,
        )
        self.street_edge.map_versions.add(self.map_version)

        # Create BusLine with custom speed
        self.bus_line = BusLine.objects.create(
            game_map=self.game_map,
            name="Express Bus",
            bus_capacity=50,
            bus_speed_kmh=45,
        )
        self.bus_line.map_versions.add(self.map_version)
        BusLineEdge.objects.create(
            bus_line=self.bus_line, street_edge=self.street_edge, order=0
        )

        # Create TrainEdge
        self.train_edge = TrainEdge.objects.create(
            edge=self.edge,
        )
        self.train_edge.map_versions.add(self.map_version)

        # Create TrainLine with custom speed
        self.train_line = TrainLine.objects.create(
            game_map=self.game_map,
            name="Metro",
            train_capacity=200,
            train_speed_kmh=60,
        )
        self.train_line.map_versions.add(self.map_version)
        TrainLineEdge.objects.create(
            train_line=self.train_line, train_edge=self.train_edge, order=0
        )

        # Create GameSession
        self.game_session = GameSession.objects.create(
            game_host=self.user,
            game_name="Test Game",
            game_map=self.game_map,
            max_players=4,
            agent_per_player=2,
            max_rounds=5,
            max_CO2_level=1000,
        )

        # Create GameRound
        self.game_round = GameRound.objects.create(
            game=self.game_session,
            round_number=1,
        )

        # Create Player
        self.player = Player.objects.create(
            name="Test Player",
            game=self.game_session,
        )

        # Create PlayerMove
        self.player_move = PlayerMove.objects.create(
            session_round=self.game_round,
            player=self.player,
            action="route_submit",
        )

        # Create AgentRoute with bus mode
        self.agent_route = AgentRoute.objects.create(
            player_move=self.player_move,
            agent_id=1,
            transport_mode="public",
            total_distance_m=1000,
            estimated_time_min=10,
        )

        # Create RouteSegment with bus
        self.route_segment = RouteSegment.objects.create(
            agent_route=self.agent_route,
            order=1,
            edge=self.edge,
            mode="bus",
            pt_line_id=self.bus_line.pk,
        )

    def test_loads_bus_line_speeds(self):
        """Test that bus line speeds are loaded correctly."""
        simulator = TrafficSimulator(self.game_round, scale=100.0)

        # Bus line speed should be loaded
        self.assertIn(self.bus_line.pk, simulator.bus_line_speeds)
        self.assertEqual(simulator.bus_line_speeds[self.bus_line.id], 45)

    def test_loads_train_line_speeds(self):
        """Test that train line speeds are loaded correctly."""
        # Create route segment with train
        route_segment_train = RouteSegment.objects.create(
            agent_route=self.agent_route,
            order=2,
            edge=self.edge,
            mode="train",
            pt_line_id=self.train_line.pk,
        )

        simulator = TrafficSimulator(self.game_round, scale=100.0)

        # Train line speed should be loaded
        self.assertIn(self.train_line.pk, simulator.train_line_speeds)
        self.assertEqual(simulator.train_line_speeds[self.train_line.id], 60)


class BusTrafficIntegrationTests(TestCase):
    """A bus on a dedicated lane does not sit in the car queue.

    Rewritten for the queue model: the intent is unchanged, but "not in the
    volume count" is now "does not occupy the carriageway".
    """

    def _state(self, bus_lane):
        return EdgeState(
            edge_id=1,
            distance_m=1000.0,
            free_flow_speed_kmh=50.0,
            car_lanes=1,
            has_dedicated_bus_lane=bus_lane,
        )

    def test_bus_on_dedicated_lane_does_not_queue(self):
        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertFalse(
            simulator._queues_for_traffic("bus", self._state(bus_lane=True))
        )

    def test_bus_on_regular_street_queues_with_the_cars(self):
        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertTrue(
            simulator._queues_for_traffic("bus", self._state(bus_lane=False))
        )

    def test_a_bus_takes_more_room_than_a_car(self):
        from game.simulation import BUS_PCU

        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertEqual(simulator._pcu_for("bus"), BUS_PCU)
        self.assertEqual(simulator._pcu_for("car"), 1.0)


class ZeroSpeedLimitEdgeTests(TestCase):
    """A street with speed_limit = 0 must not become a zero-speed edge.

    Eight such rows ship with the example maps (Tiergartenstr., Verlängerung
    Alt-Moabit). A car on one can never advance at any volume, and its delay
    records as 0 because the delay term is guarded on base_speed > 0 — so the
    one edge that is completely stuck also reports no congestion.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="zerospeed", password="12345")
        self.game_map = GameMap.objects.create(
            name="Zero Speed Map",
            x_dim=10,
            y_dim=10,
            scale=100.0,
            default_car_speed_kmh=60,
        )
        self.map_version = MapVersion.objects.create(
            game_map=self.game_map, name="Base", base_version=True
        )
        self.node1 = Node.objects.create(
            game_map=self.game_map, x_position=0, y_position=0
        )
        self.node1.map_versions.add(self.map_version)
        self.node2 = Node.objects.create(
            game_map=self.game_map, x_position=2, y_position=0
        )
        self.node2.map_versions.add(self.map_version)

        self.edge = Edge.objects.create(
            game_map=self.game_map,
            name="Tiergartenstr.",
            start_node=self.node1,
            end_node=self.node2,
        )
        self.edge.map_versions.add(self.map_version)

        # The defect, exactly as it ships in map_examples/Berlin_Mitte-West.json
        self.street_edge = StreetEdge.objects.create(
            edge=self.edge, speed_limit=0, lanes=1
        )
        self.street_edge.map_versions.add(self.map_version)

        self.game_session = GameSession.objects.create(
            game_host=self.user,
            game_name="Zero Speed Game",
            game_map=self.game_map,
            max_players=4,
            agent_per_player=1,
            max_rounds=3,
            max_CO2_level=1000,
        )
        self.game_round = GameRound.objects.create(
            game=self.game_session, round_number=1
        )
        self.player = Player.objects.create(name="Fahrer", game=self.game_session)
        self.player_move = PlayerMove.objects.create(
            session_round=self.game_round,
            player=self.player,
            action="route_submit",
        )
        self.agent_route = AgentRoute.objects.create(
            player_move=self.player_move,
            agent_id=1,
            transport_mode="car",
            total_distance_m=200,
            estimated_time_min=5,
        )
        RouteSegment.objects.create(
            agent_route=self.agent_route,
            order=1,
            edge=self.edge,
            mode="car",
        )

    def test_zero_speed_limit_falls_back_to_the_map_default(self):
        simulator = TrafficSimulator(self.game_round, scale=100.0)

        edge_state = simulator.edge_states[self.edge.pk]

        self.assertEqual(edge_state.free_flow_speed_kmh, 60)

    def test_a_car_on_such_an_edge_can_move(self):
        """In the queue model "can move" is two numbers, not a speed.

        A link needs a free-flow time that is finite and a flow capacity
        that is not zero; either one at zero is a link nobody ever leaves.
        """
        simulator = TrafficSimulator(self.game_round, scale=100.0)

        edge_state = simulator.edge_states[self.edge.pk]

        self.assertGreater(edge_state.free_flow_min, 0)
        self.assertGreater(edge_state.flow_per_tick(tick_duration_min=5), 0)
        self.assertGreater(edge_state.mean_speed_kmh, 0)


class NonArrivalAccountingTests(TestCase):
    """Vehicles still under way when the clock stops have to be counted.

    trip_times is appended on arrival only, so a round that did not finish
    reported a mean over its survivors while CO2 and cost billed the whole
    route for everyone — and a route where nobody arrived fell back to the
    client's free-flow estimate with delay 0, which renders total gridlock as
    the fastest trip on the screen.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="stranded", password="12345")
        self.game_map = GameMap.objects.create(
            name="Stranded Map", x_dim=10, y_dim=10, scale=100.0
        )
        self.map_version = MapVersion.objects.create(
            game_map=self.game_map, name="Base", base_version=True
        )
        self.node1 = Node.objects.create(
            game_map=self.game_map, x_position=0, y_position=0
        )
        self.node1.map_versions.add(self.map_version)
        self.node2 = Node.objects.create(
            game_map=self.game_map, x_position=3, y_position=0
        )
        self.node2.map_versions.add(self.map_version)
        self.edge = Edge.objects.create(
            game_map=self.game_map, start_node=self.node1, end_node=self.node2
        )
        self.edge.map_versions.add(self.map_version)
        self.street_edge = StreetEdge.objects.create(
            edge=self.edge, speed_limit=50, lanes=1
        )
        self.street_edge.map_versions.add(self.map_version)

        self.game_session = GameSession.objects.create(
            game_host=self.user,
            game_name="Stranded Game",
            game_map=self.game_map,
            max_players=4,
            agent_per_player=1,
            max_rounds=3,
            max_CO2_level=1000,
        )
        self.game_round = GameRound.objects.create(
            game=self.game_session, round_number=1
        )
        self.player = Player.objects.create(name="Fahrer", game=self.game_session)
        self.player_move = PlayerMove.objects.create(
            session_round=self.game_round,
            player=self.player,
            action="route_submit",
        )
        self.agent_route = AgentRoute.objects.create(
            player_move=self.player_move,
            agent_id=1,
            transport_mode="car",
            total_distance_m=300,
            estimated_time_min=7,
        )
        RouteSegment.objects.create(
            agent_route=self.agent_route, order=1, edge=self.edge, mode="car"
        )

    def test_result_tracking_starts_with_a_non_arrival_counter(self):
        simulator = TrafficSimulator(self.game_round, scale=100.0)

        results = simulator.agent_results[self.agent_route.pk]

        self.assertEqual(results["not_arrived"], 0)

    def test_stranded_vehicles_are_recorded_at_their_elapsed_time(self):
        from game.simulation import Vehicle

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        # tick 200 at 5 min a tick: the clock stopped at minute 1000, and
        # this person wanted to leave at 820, so they have been under way
        # for 180 minutes and are still not there.
        simulator.current_tick = 200
        simulator.vehicles[1] = Vehicle(
            route_pk=self.agent_route.pk,
            person_index=0,
            mode="car",
            segment_index=0,
            wants_to_depart_min=820.0,
            departed=True,
            arrived=False,
            passenger_count=2,
        )

        simulator._record_non_arrivals()

        results = simulator.agent_results[self.agent_route.pk]
        self.assertEqual(results["not_arrived"], 2)
        self.assertEqual(results["trip_times"], [180.0, 180.0])
        # 300 m at 50 km/h is 0.36 min of free flow; the rest is delay.
        for delay in results["delays"]:
            self.assertAlmostEqual(delay, 180.0 - 0.36, places=2)

    def test_people_still_at_the_front_door_are_counted_too(self):
        """A first link that is full every tick strands people invisibly.

        They never become a Vehicle, so without this they would drop out of
        the round's numbers altogether while CO2 and cost still billed them.
        """
        simulator = TrafficSimulator(self.game_round, scale=100.0)
        simulator.current_tick = 200
        simulator.route_vehicle_scaling[self.agent_route.pk] = (1, 1)
        simulator.waiting = [
            (820.0, self.agent_route.pk, 0),
            # Wanted to leave after the clock stopped: nothing happened to
            # them, so nothing is recorded.
            (1200.0, self.agent_route.pk, 1),
        ]

        simulator._record_non_arrivals()

        results = simulator.agent_results[self.agent_route.pk]
        self.assertEqual(results["not_arrived"], 1)
        self.assertEqual(results["trip_times"], [180.0])

    def test_arrived_and_undeparted_vehicles_are_left_alone(self):
        from game.simulation import Vehicle

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        simulator.vehicles[1] = Vehicle(
            route_pk=self.agent_route.pk,
            person_index=0,
            mode="car",
            segment_index=0,
            departed=True,
            arrived=True,
        )
        simulator.vehicles[2] = Vehicle(
            route_pk=self.agent_route.pk,
            person_index=1,
            mode="car",
            segment_index=0,
            departed=False,
            arrived=False,
        )

        simulator._record_non_arrivals()

        results = simulator.agent_results[self.agent_route.pk]
        self.assertEqual(results["not_arrived"], 0)
        self.assertEqual(results["trip_times"], [])
# =============================================================================
# The link queue model — .claude/plans/to-do/[backend]-sim-link-model.md
#
# Names that do not exist yet are imported INSIDE each test on purpose: a
# module-level import of a missing name would error the whole file and hide
# the tests above it.
# =============================================================================


def _grid_map(name, node_count, step_units=3.0, scale=100.0):
    """A straight chain of nodes, `step_units * scale` metres apart."""
    game_map = GameMap.objects.create(
        name=name, x_dim=1000, y_dim=1000, scale=scale
    )
    version = MapVersion.objects.create(
        game_map=game_map, name="Base", base_version=True
    )
    nodes = []
    for i in range(node_count):
        node = Node.objects.create(
            game_map=game_map, x_position=i * step_units, y_position=0
        )
        node.map_versions.add(version)
        nodes.append(node)
    return game_map, version, nodes


def _street(game_map, version, start, end, speed_limit=50, lanes=1, bus_lane=False):
    edge = Edge.objects.create(
        game_map=game_map, start_node=start, end_node=end, max_lanes=lanes
    )
    edge.map_versions.add(version)
    street = StreetEdge.objects.create(
        edge=edge,
        speed_limit=speed_limit,
        lanes=lanes,
        dedicated_bus_lane=bus_lane,
    )
    street.map_versions.add(version)
    return edge


def _session(host, game_map, people_per_agent=10, std_dev=10):
    return GameSession.objects.create(
        game_host=host,
        game_name="Link model",
        game_map=game_map,
        max_players=4,
        agent_per_player=1,
        max_rounds=3,
        max_CO2_level=1000000,
        people_per_agent=people_per_agent,
        departure_std_dev_min=std_dev,
    )


def _route(game_round, player, edges, mode="car", agent_id=1, distance=None):
    move, _ = PlayerMove.objects.get_or_create(
        session_round=game_round, player=player, action="route_submit"
    )
    route = AgentRoute.objects.create(
        player_move=move,
        agent_id=agent_id,
        transport_mode=mode,
        total_distance_m=distance or (300.0 * len(edges)),
        estimated_time_min=1.0,
    )
    for order, edge in enumerate(edges, start=1):
        RouteSegment.objects.create(
            agent_route=route, order=order, edge=edge, mode=mode
        )
    return route


class LinkCapacityTests(TestCase):
    """Storage and flow capacity are physical numbers, not speed * 15.

    The old calculate_edge_capacity allowed 750 vehicles on a kilometre of one
    lane — about five times what fits — so an edge only counted as congested
    in a state that cannot exist.
    """

    def _state(self, **kwargs):
        from game.simulation import EdgeState

        defaults = dict(
            edge_id=1, distance_m=1000.0, free_flow_speed_kmh=50.0, car_lanes=1
        )
        defaults.update(kwargs)
        return EdgeState(**defaults)

    def test_storage_is_jam_density_times_lanes_times_km(self):
        from game.simulation import JAM_DENSITY_VEH_PER_KM_LANE

        state = self._state(distance_m=1000.0, car_lanes=1)

        self.assertAlmostEqual(
            state.storage_capacity_pcu, JAM_DENSITY_VEH_PER_KM_LANE, places=2
        )

    def test_storage_scales_with_lanes_and_length(self):
        two_lanes = self._state(distance_m=500.0, car_lanes=2)
        one_lane = self._state(distance_m=500.0, car_lanes=1)

        self.assertAlmostEqual(two_lanes.storage_capacity_pcu, one_lane.storage_capacity_pcu * 2)

    def test_storage_is_never_below_one_vehicle(self):
        """A very short link must still hold somebody, or nothing can enter."""
        state = self._state(distance_m=1.0, car_lanes=1)

        self.assertGreaterEqual(state.storage_capacity_pcu, 1.0)

    def test_flow_capacity_is_saturation_flow_per_lane(self):
        from game.simulation import SATURATION_FLOW_VEH_PER_H_LANE

        state = self._state(car_lanes=1)

        # One hour's worth at a 60 minute tick.
        self.assertAlmostEqual(
            state.flow_per_tick(60), SATURATION_FLOW_VEH_PER_H_LANE, places=2
        )

    def test_flow_capacity_does_not_depend_on_the_speed_limit(self):
        """A 30 zone discharges like a 50 street; only free-flow time differs.

        The old formula made capacity proportional to the speed limit, so a
        30 zone held fewer cars than the same street at 50 — backwards.
        """
        slow = self._state(free_flow_speed_kmh=30.0)
        fast = self._state(free_flow_speed_kmh=50.0)

        self.assertAlmostEqual(slow.flow_per_tick(5), fast.flow_per_tick(5))
        self.assertGreater(slow.free_flow_min, fast.free_flow_min)

    def test_free_flow_minutes_from_length_and_speed(self):
        state = self._state(distance_m=1000.0, free_flow_speed_kmh=60.0)

        self.assertAlmostEqual(state.free_flow_min, 1.0, places=3)


class DedicatedBusLaneTests(TestCase):
    """`lanes` counts the whole street, the bus lane included.

    Two conventions were possible: (A) lanes = car lanes with the bus lane on
    top, or (B) lanes = total including it. B, decided by Lukas 2026-09-19:
    under A every bus-lane version needs two edits that have to agree, and the
    forgotten second one leaves cars with every lane while the editor looks
    right. Under B ticking Busspur IS the trade-off. It is also how OSM counts
    lanes.

    On a one-lane street the tick closes it to cars entirely — a bus gate.
    That is enforced in the client's pathfinding and at submit; the simulator
    only has to not hang if a car reaches one anyway, which is what
    _capacity_lanes is for.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="buslane", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Bus lane map", 3)

    def _simulator_over(self, edge):
        session = _session(self.user, self.game_map)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Fahrer", game=session)
        _route(game_round, player, [edge])
        return TrafficSimulator(game_round, scale=100.0)

    def test_a_bus_lane_takes_one_of_the_streets_lanes(self):
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=2, bus_lane=True,
        )

        simulator = self._simulator_over(edge)

        self.assertEqual(simulator.edge_states[edge.pk].car_lanes, 1)

    def test_a_street_without_a_bus_lane_keeps_all_its_lanes(self):
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=2, bus_lane=False,
        )

        simulator = self._simulator_over(edge)

        self.assertEqual(simulator.edge_states[edge.pk].car_lanes, 2)

    def test_a_three_lane_street_keeps_two_for_cars(self):
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=3, bus_lane=True,
        )

        simulator = self._simulator_over(edge)

        self.assertEqual(simulator.edge_states[edge.pk].car_lanes, 2)

    def test_a_single_lane_bus_street_becomes_a_bus_gate(self):
        """Closed to cars, still open to buses, bikes and pedestrians.

        Edge 507 on "E2E Berlin" (v8 "Busspur Hauptstraße") is exactly this.
        """
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=1, bus_lane=True,
        )

        simulator = self._simulator_over(edge)
        state = simulator.edge_states[edge.pk]

        self.assertEqual(state.car_lanes, 0)
        self.assertFalse(state.open_to_cars)

    def test_a_bus_gate_still_has_usable_capacity_numbers(self):
        """Zero lanes must not mean zero flow: a car that reached one anyway
        would never discharge and would hang the round to max_ticks."""
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=1, bus_lane=True,
        )

        state = self._simulator_over(edge).edge_states[edge.pk]

        self.assertGreater(state.storage_capacity_pcu, 0)
        self.assertGreater(state.flow_per_tick(5), 0)

    def test_an_ordinary_street_is_open_to_cars(self):
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=2, bus_lane=True,
        )

        self.assertTrue(self._simulator_over(edge).edge_states[edge.pk].open_to_cars)


class FreeFlowTripTimeTests(TestCase):
    """A trip on an empty network takes its free-flow time.

    This is the four-times bug. _move_vehicles advances a vehicle once per
    tick and takes at most ONE segment boundary, adding tick_duration_min to
    the clock unconditionally — so a trip costs (segments x 5) minutes however
    fast the road is. Berlin's median street edge is 895 m and a car at
    50 km/h covers 4167 m in a five-minute tick.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="freeflow", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Free flow map", 6)
        self.edges = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(5)
        ]
        self.session = _session(self.user, self.game_map, people_per_agent=5)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.player = Player.objects.create(name="Fahrer", game=self.session)
        self.route = _route(self.game_round, self.player, self.edges)

    def _run(self):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        with muted():
            simulator.run_simulation(max_ticks=200)
        return simulator

    def test_five_short_edges_take_their_free_flow_time(self):
        """1500 m at 50 km/h is 1.8 min. Today it reports 25.0 — five ticks."""
        simulator = self._run()

        trip_times = simulator.agent_results[self.route.pk]["trip_times"]
        mean_trip = sum(trip_times) / len(trip_times)

        self.assertLess(mean_trip, 5.0)
        self.assertAlmostEqual(mean_trip, 1.8, delta=1.0)

    def test_trip_time_is_not_a_multiple_of_the_tick(self):
        """Every trip time today ends in 0 or 5, whatever the distance."""
        simulator = self._run()

        trip_times = simulator.agent_results[self.route.pk]["trip_times"]

        self.assertTrue(
            any(abs(t % self.session.tick_duration_min) > 0.01 for t in trip_times),
            f"every trip time is a whole number of ticks: {sorted(set(trip_times))}",
        )

    def test_an_empty_network_records_no_delay(self):
        simulator = self._run()

        delays = simulator.agent_results[self.route.pk]["delays"]

        self.assertAlmostEqual(max(delays), 0.0, delta=0.5)


class QueueAndSpillbackTests(TestCase):
    """Congestion is a queue, and a link never holds more than fits on it."""

    def setUp(self):
        self.user = User.objects.create_user(username="queue", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Queue map", 4)
        self.edges = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(3)
        ]
        # 600 cars over one lane: 1800 veh/h discharges 150 per 5 min tick,
        # so this cannot clear in under four ticks however fast the road is.
        self.session = _session(self.user, self.game_map, people_per_agent=600, std_dev=1)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.player = Player.objects.create(name="Fahrer", game=self.session)
        self.route = _route(self.game_round, self.player, self.edges)

    def _run(self):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        with muted():
            simulator.run_simulation(max_ticks=200)
        return simulator

    def test_demand_past_flow_capacity_queues(self):
        """900 m of free flow is 1.08 min; 600 cars through one lane is not."""
        simulator = self._run()

        trip_times = simulator.agent_results[self.route.pk]["trip_times"]

        self.assertGreater(max(trip_times), 10.0)

    def test_a_link_never_holds_more_than_its_storage(self):
        """The invariant the old model had no concept of at all."""
        simulator = self._run()

        if simulator.forced_releases:
            self.skipTest("deadlock escape fired; storage is deliberately exceeded")
        for edge_state in simulator.edge_states.values():
            self.assertLessEqual(
                edge_state.peak_occupancy_pcu,
                edge_state.storage_capacity_pcu,
                f"edge {edge_state.edge_id} overran its storage",
            )

    def test_everybody_still_arrives(self):
        """A queue drains. Nothing may be left standing on an open network."""
        simulator = self._run()

        results = simulator.agent_results[self.route.pk]

        self.assertEqual(results["not_arrived"], 0)
        self.assertEqual(len(results["trip_times"]), 600)

    def test_congestion_is_recorded_as_delay(self):
        simulator = self._run()

        delays = simulator.agent_results[self.route.pk]["delays"]

        self.assertGreater(max(delays), 1.0)

    def test_the_queue_discharges_over_time(self):
        """The decisive one: a queue serves people at different times.

        Today all 600 cars report the identical trip time — three segments,
        three ticks, 15 minutes each — because the model has no queue at all
        and the tick is the only clock. A link that discharges at 150 vehicles
        per tick cannot deliver 600 people at the same moment.
        """
        simulator = self._run()

        trip_times = simulator.agent_results[self.route.pk]["trip_times"]
        spread = max(trip_times) - min(trip_times)

        self.assertGreater(
            spread,
            10.0,
            f"all 600 travellers arrived within {spread:.1f} min of each other",
        )


class FairDepartureTests(TestCase):
    """Two players' agents on the same jammed street wait the same time.

    Draining each route's waiting list in turn — the obvious way to write the
    spawn loop — gave the first route free flow and the last an hour's wait,
    purely from dict order. In a classroom that is one player's agents always
    beating another's onto a shared street.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="fair", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Fair map", 3)
        self.edges = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(2)
        ]
        self.session = _session(self.user, self.game_map, people_per_agent=400, std_dev=1)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.anna = Player.objects.create(name="Anna", game=self.session)
        self.ben = Player.objects.create(name="Ben", game=self.session)
        self.route_a = _route(self.game_round, self.anna, self.edges, agent_id=1)
        self.route_b = _route(self.game_round, self.ben, self.edges, agent_id=2)

    def test_both_routes_wait_about_equally(self):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        with muted():
            simulator.run_simulation(max_ticks=200)

        times_a = simulator.agent_results[self.route_a.pk]["trip_times"]
        times_b = simulator.agent_results[self.route_b.pk]["trip_times"]
        mean_a = sum(times_a) / len(times_a)
        mean_b = sum(times_b) / len(times_b)

        self.assertLess(
            abs(mean_a - mean_b) / max(mean_a, mean_b),
            0.1,
            f"one route was served ahead of the other: {mean_a:.1f} vs {mean_b:.1f} min",
        )


class DeadlockEscapeTests(TestCase):
    """Two routes holding each other's street must still finish.

    A queue model can deadlock where a real city does. The rule is that a
    junction blocked for DEADLOCK_TICKS consecutive ticks releases its budget
    anyway, over storage, and counts the release.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="deadlock", password="12345")
        # Short links so storage is small and they fill immediately.
        self.game_map, self.version, self.nodes = _grid_map(
            "Deadlock map", 3, step_units=1.0
        )
        self.first = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1]
        )
        self.second = _street(
            self.game_map, self.version, self.nodes[1], self.nodes[2]
        )
        self.session = _session(self.user, self.game_map, people_per_agent=300, std_dev=1)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.anna = Player.objects.create(name="Anna", game=self.session)
        self.ben = Player.objects.create(name="Ben", game=self.session)
        # Each route needs the link the other one is standing on.
        self.route_a = _route(
            self.game_round, self.anna, [self.first, self.second], agent_id=1
        )
        self.route_b = _route(
            self.game_round, self.ben, [self.second, self.first], agent_id=2
        )

    def test_the_gridlock_resolves(self):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        with muted():
            simulator.run_simulation(max_ticks=300)

        for route in (self.route_a, self.route_b):
            results = simulator.agent_results[route.pk]
            self.assertEqual(
                results["not_arrived"],
                0,
                "vehicles were left standing in a deadlock",
            )

    def test_the_escape_is_counted(self):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        with muted():
            simulator.run_simulation(max_ticks=300)

        self.assertGreater(
            simulator.forced_releases,
            0,
            "the deadlock rule never fired, so the run was not actually locked",
        )


class ObservedEdgeSpeedTests(TestCase):
    """Per-edge speed is an output of the run, and it is the CAR speed.

    A pedestrian takes 10.7 minutes over an 895 m edge where a car takes 1.07.
    Letting walkers into this mean would report an empty street as jammed —
    and this number feeds both the CO2 factor and the players' route preview.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="speeds", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Speed map", 3)
        self.edges = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(2)
        ]
        self.session = _session(self.user, self.game_map, people_per_agent=5)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.player = Player.objects.create(name="Fahrer", game=self.session)

    def test_an_empty_edge_reports_free_flow(self):
        from game.simulation import EdgeState

        state = EdgeState(
            edge_id=1, distance_m=900.0, free_flow_speed_kmh=50.0, car_lanes=1
        )

        self.assertAlmostEqual(state.mean_speed_kmh, 50.0, places=2)

    def test_a_walked_edge_does_not_report_walking_pace(self):
        from game.tests._helpers import muted

        _route(self.game_round, self.player, self.edges, mode="walk")
        simulator = TrafficSimulator(self.game_round, scale=100.0)
        with muted():
            simulator.run_simulation(max_ticks=300)

        for edge in self.edges:
            self.assertAlmostEqual(
                simulator.edge_states[edge.pk].mean_speed_kmh, 50.0, places=1
            )


class DepartureMinuteTests(TestCase):
    """Departures are minutes, not tick buckets.

    Bucketing quantised every trip to five minutes before the simulation had
    started. The tick is a simulation step, not a property of when people
    leave the house.
    """

    def test_returns_minutes_within_the_window(self):
        from game.simulation import generate_departure_minutes

        departures = generate_departure_minutes(200, base_hour=9, std_dev_min=10)

        self.assertEqual(len(departures), 200)
        self.assertTrue(all(0.0 <= d <= 120.0 for d in departures))

    def test_not_every_departure_is_a_whole_tick(self):
        from game.simulation import generate_departure_minutes

        departures = generate_departure_minutes(200, base_hour=9, std_dev_min=10)

        self.assertTrue(any(abs(d % 5) > 0.01 for d in departures))

    def test_zero_std_dev_puts_everyone_at_the_base_hour(self):
        from game.simulation import generate_departure_minutes

        departures = generate_departure_minutes(20, base_hour=9, std_dev_min=0)

        # 60 minutes into a window that starts at base_hour - 1.
        self.assertTrue(all(abs(d - 60.0) < 0.01 for d in departures))


class CarEmissionCurveTests(TestCase):
    """CO2 per kilometre is a function of the speed the link actually ran at.

    COPERT/HBEFA-style average-speed emission modelling — the same lineage as
    the link model itself. Three physical terms: a/v is the time-proportional
    part (idling and stop-and-go, burning fuel while covering no ground), b is
    rolling resistance, c*v**2 is drag, which is why the curve is U-shaped and
    a motorway is not the optimum either.
    """

    def test_the_curve_is_anchored_at_fifty(self):
        """The one that keeps an uncongested 50 km/h round emitting what it did.

        a and b are derived from c and this condition, so it holds to
        floating-point rounding rather than to four digits.
        """
        from game.simulation import CAR_EMISSIONS_G_PER_KM, car_emissions_g_per_km

        self.assertAlmostEqual(
            car_emissions_g_per_km(50.0), CAR_EMISSIONS_G_PER_KM, places=6
        )

    def test_stop_and_go_burns_more_per_kilometre(self):
        """10 km/h is 1.9x the 50 km/h rate — the one judgement call in here."""
        from game.simulation import CAR_EMISSIONS_G_PER_KM, car_emissions_g_per_km

        self.assertAlmostEqual(
            car_emissions_g_per_km(10.0) / CAR_EMISSIONS_G_PER_KM, 1.9, places=3
        )

    def test_the_curve_falls_all_the_way_from_ten_to_fifty(self):
        from game.simulation import car_emissions_g_per_km

        for slower, faster in ((10.0, 20.0), (20.0, 30.0), (30.0, 40.0), (40.0, 50.0)):
            with self.subTest(slower=slower):
                self.assertGreater(
                    car_emissions_g_per_km(slower), car_emissions_g_per_km(faster)
                )

    def test_the_curve_is_u_shaped(self):
        """Drag is why a motorway costs more than the 70 km/h minimum."""
        from game.simulation import car_emissions_g_per_km

        self.assertLess(car_emissions_g_per_km(70.0), car_emissions_g_per_km(50.0))
        self.assertLess(car_emissions_g_per_km(70.0), car_emissions_g_per_km(120.0))

    def test_the_factor_is_capped_at_two(self):
        """a/v diverges, and a diverging function is not an accurate one."""
        from game.simulation import (
            CAR_EMISSIONS_G_PER_KM,
            MAX_CAR_EMISSION_FACTOR,
            car_emissions_g_per_km,
        )

        self.assertAlmostEqual(
            car_emissions_g_per_km(1.0),
            MAX_CAR_EMISSION_FACTOR * CAR_EMISSIONS_G_PER_KM,
            places=6,
        )

    def test_it_is_flat_below_the_cap(self):
        """The cap bites at 9.2 km/h; gridlock and a crawl bill the same."""
        from game.simulation import car_emissions_g_per_km

        self.assertAlmostEqual(
            car_emissions_g_per_km(1.0), car_emissions_g_per_km(9.0), places=6
        )

    def test_no_speed_ever_exceeds_the_cap(self):
        from game.simulation import (
            CAR_EMISSIONS_G_PER_KM,
            MAX_CAR_EMISSION_FACTOR,
            car_emissions_g_per_km,
        )

        ceiling = MAX_CAR_EMISSION_FACTOR * CAR_EMISSIONS_G_PER_KM
        for tenths in range(0, 2000, 7):
            speed = tenths / 10.0
            with self.subTest(speed=speed):
                value = car_emissions_g_per_km(speed)
                self.assertGreater(value, 0.0)
                self.assertLessEqual(value, ceiling + 1e-9)

    def test_a_standstill_does_not_divide_by_zero(self):
        """mean_speed_kmh can be 0 on a zero-length link. Arithmetic, not model."""
        from game.simulation import car_emissions_g_per_km

        self.assertGreater(car_emissions_g_per_km(0.0), 0.0)


class CarCostCurveTests(TestCase):
    """Half the per-kilometre cost rides on the emission curve.

    0.32 €/km is a Vollkosten figure, so it cannot all follow: fuel (~0.126)
    and stop-and-go wear on brakes, clutch and tyres (~0.034) are metered by
    how the car is driven, depreciation, insurance and tax are not. Fuel
    tracks the CO2 factor exactly rather than on a curve of its own, because
    CO2 is fuel burnt — one physics, two units.
    """

    def test_the_cost_is_anchored_at_fifty(self):
        from game.simulation import CAR_COST_PER_KM, car_cost_eur_per_km

        self.assertAlmostEqual(car_cost_eur_per_km(50.0), CAR_COST_PER_KM, places=6)

    def test_a_jam_costs_more_money(self):
        from game.simulation import car_cost_eur_per_km

        self.assertGreater(car_cost_eur_per_km(15.0), car_cost_eur_per_km(50.0))

    def test_only_the_traffic_share_moves(self):
        """At the 2.00x CO2 cap money is 1.50x, not 2.00x."""
        from game.simulation import (
            CAR_COST_PER_KM,
            CAR_COST_TRAFFIC_SHARE,
            MAX_CAR_EMISSION_FACTOR,
            car_cost_eur_per_km,
        )

        expected = CAR_COST_PER_KM * (
            1.0
            - CAR_COST_TRAFFIC_SHARE
            + CAR_COST_TRAFFIC_SHARE * MAX_CAR_EMISSION_FACTOR
        )

        self.assertAlmostEqual(car_cost_eur_per_km(1.0), expected, places=6)
        self.assertLess(car_cost_eur_per_km(1.0), MAX_CAR_EMISSION_FACTOR * CAR_COST_PER_KM)

    def test_the_cost_is_capped_where_the_emissions_are(self):
        from game.simulation import car_cost_eur_per_km

        self.assertAlmostEqual(
            car_cost_eur_per_km(1.0), car_cost_eur_per_km(9.0), places=6
        )


class CongestedRouteCostsMoreTests(TestCase):
    """The goal. Everything above it is arithmetic.

    The same route, the same distance, the same mode, run once on an empty
    network and once with 800 cars merging onto one lane. Today both come back
    identical to the decimal, because CO2 and cost are distance times a
    constant — so a bus lane that unjams a street shows a zero benefit on the
    metric the game is lost by.

    The jam has to be a MERGE, not a single chain. _advance_traffic keeps
    discharging until nothing moves, so a chain fed from one origin drains
    end to end within a tick and the queue forms at the front door instead of
    on a link: every traversal is free flow and the street reports 50 km/h
    however long the line outside is. Two approaches feeding one lane is what
    holds cars ON a link — and it is also what a real map does, since players
    start at different homes and converge.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="jamco2", password="12345")

    def _merge_map(self, label):
        """Two 1.4 km approaches merging into one 300 m lane.

        The approaches have to be long enough to HOLD the queue: one lane
        passes 150 cars a tick, so approaches storing less than that between
        them empty completely every tick and the line forms at the front door
        again. 1.4 km stores 188 cars each.
        """
        game_map = GameMap.objects.create(name=label, x_dim=1000, y_dim=1000, scale=100.0)
        version = MapVersion.objects.create(
            game_map=game_map, name="Base", base_version=True
        )
        coords = {"north": (0, 20), "south": (0, 0), "merge": (10, 10), "work": (13, 10)}
        nodes = {}
        for name, (x, y) in coords.items():
            node = Node.objects.create(game_map=game_map, x_position=x, y_position=y)
            node.map_versions.add(version)
            nodes[name] = node
        shared = _street(game_map, version, nodes["merge"], nodes["work"])
        return game_map, version, nodes, shared

    def _play_merge(self, label, people, seed=606):
        """Both players drive their approach and then the shared lane.

        The seed is pinned for the same reason as _play_chain below. Left to
        the round pk, the jam these three tests rest on is drawn fresh every
        run: over twenty seeds the approach came out between 24.6 and 45.0
        km/h, three of them at or above the 40.0 the guard allows. Postgres
        sequences do not roll back, so the pk climbs through the suite and the
        draw moves the moment a test that creates a round is added anywhere
        before this one; sqlite reuses the rowid after each rollback, so a run
        outside the container draws seed 1 every time — 45.00 km/h, no jam at
        all, and a red guard that says nothing about the model.
        """
        from game.models import AgentSimulationResult
        from game.tests._helpers import muted

        game_map, version, nodes, shared = self._merge_map(label)
        north = _street(game_map, version, nodes["north"], nodes["merge"])
        south = _street(game_map, version, nodes["south"], nodes["merge"])

        session = _session(self.user, game_map, people_per_agent=people, std_dev=1)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        ben = Player.objects.create(name="Ben", game=session)
        route = _route(game_round, anna, [north, shared], agent_id=1)
        _route(game_round, ben, [south, shared], agent_id=2)

        simulator = TrafficSimulator(game_round, scale=100.0, seed=seed)
        with muted():
            simulator.run_simulation(max_ticks=400)

        result = AgentSimulationResult.objects.get(agent_route=route)
        return {
            "co2_per_person": result.total_co2_g / people,
            "cost_per_person": result.mean_cost_eur,
            "approach_speed": simulator.edge_states[north.pk].mean_speed_kmh,
        }

    def _play_chain(self, label, people, speed_limit=50, seed=606):
        """A plain 3 x 300 m chain, one driver on it — free flow by construction.

        The seed is pinned. Without it the simulator seeds off the round pk,
        which depends on how many rounds earlier tests in the same run
        happened to create — so these assertions passed alone and failed in a
        full suite, which is the worst way for a test to fail.
        """
        from game.models import AgentSimulationResult
        from game.tests._helpers import muted

        game_map, version, nodes = _grid_map(label, 4)
        edges = [
            _street(game_map, version, nodes[i], nodes[i + 1], speed_limit=speed_limit)
            for i in range(3)
        ]
        session = _session(self.user, game_map, people_per_agent=people, std_dev=1)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Fahrer", game=session)
        route = _route(game_round, player, edges)

        simulator = TrafficSimulator(game_round, scale=100.0, seed=seed)
        with muted():
            simulator.run_simulation(max_ticks=300)

        result = AgentSimulationResult.objects.get(agent_route=route)
        return {
            "co2_per_person": result.total_co2_g / people,
            "cost_per_person": result.mean_cost_eur,
        }

    def test_the_jam_really_is_a_jam(self):
        """Guard for the two below: if this fails they prove nothing."""
        jammed = self._play_merge("Jam map", people=400)

        self.assertLess(
            jammed["approach_speed"],
            40.0,
            f"800 cars merging onto one lane left the approach at "
            f"{jammed['approach_speed']:.1f} km/h",
        )

    def test_a_jammed_route_emits_more_per_person(self):
        free = self._play_merge("Free map", people=5)
        jammed = self._play_merge("Jam map", people=400)

        self.assertGreater(
            jammed["co2_per_person"],
            free["co2_per_person"] * 1.05,
            f"{jammed['co2_per_person']:.2f} g/person jammed against "
            f"{free['co2_per_person']:.2f} in free flow",
        )

    def test_a_jammed_route_costs_more_per_person(self):
        free = self._play_merge("Free map", people=5)
        jammed = self._play_merge("Jam map", people=400)

        self.assertGreater(
            jammed["cost_per_person"],
            free["cost_per_person"] * 1.02,
            f"EUR {jammed['cost_per_person']:.4f}/person jammed against "
            f"EUR {free['cost_per_person']:.4f} in free flow",
        )

    def test_an_empty_fifty_route_still_emits_about_the_old_number(self):
        """The anchor, with the one tolerance the stochastic layer costs it.

        EF(50) is still exactly CAR_EMISSIONS_G_PER_KM — that identity is
        pinned in CarEmissionCurveTests and did not move. What moved is what
        an empty road OBSERVES: drivers now want slightly different speeds
        (DRIVER_SPEED_SIGMA), and the mean speed a link reports is length over
        mean traversal time, which is a harmonic mean. A mix of 44 and 56 has
        a lower harmonic mean than a uniform 50, and the emission curve is
        convex, so an empty 50 road reads a few tenths of a percent above the
        anchor rather than exactly on it.

        That is real — a spread of speeds does burn more fuel than everyone
        driving the mean — and it is under 1%. The assertion is a percentage
        rather than four decimal places for exactly that reason; tightening it
        back would be pinning the absence of driver heterogeneity.
        """
        from game.simulation import CAR_EMISSIONS_G_PER_KM

        free = self._play_chain("Anchor map", people=400)

        expected = CAR_EMISSIONS_G_PER_KM * 0.9
        self.assertLess(
            abs(free["co2_per_person"] - expected) / expected,
            0.015,
            f'{free["co2_per_person"]:.3f} against {expected:.3f}',
        )

    def test_an_empty_fifty_route_still_costs_about_the_old_number(self):
        """Same tolerance, same reason — cost rides the emission curve."""
        from game.simulation import CAR_COST_PER_KM

        free = self._play_chain("Anchor cost map", people=400)

        expected = CAR_COST_PER_KM * 0.9
        self.assertLess(
            abs(free["cost_per_person"] - expected) / expected,
            0.015,
            f'{free["cost_per_person"]:.5f} against {expected:.5f}',
        )

    def test_a_thirty_zone_emits_more_than_a_fifty_zone_even_empty(self):
        """Pinned deliberately: this is the surprising half of the change.

        An average-speed model cannot tell a steady 30 from a 50 street with a
        queue on it, so a Tempo-30 street bills 1.13x even with nobody on it.
        That is real in every HBEFA-style model, and the example maps are full
        of 30 zones — so it shifts the baseline of a real game, not just the
        jammed part of it. Better named in a test than found in a round.
        """
        fifty = self._play_chain("Fifty zone", people=5, speed_limit=50)
        thirty = self._play_chain("Thirty zone", people=5, speed_limit=30)

        self.assertGreater(
            thirty["co2_per_person"],
            fifty["co2_per_person"] * 1.10,
            f"{thirty['co2_per_person']:.2f} g/person at 30 against "
            f"{fifty['co2_per_person']:.2f} at 50",
        )


class SeededRandomnessTests(TestCase):
    """The draw is seeded off the round, so a round is reproducible.

    Everything the stochastic layer adds later depends on this landing
    first: without a seeded generator there is no golden master, and with
    no golden master there is no proof that moving the engine into its own
    package changed nothing.

    The seed is the round pk rather than a wall clock, so re-running a
    round — in a test, in a debugger, or after a worker restart — draws the
    same departures it drew the first time.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="seeded", password="12345")

    def _round(self):
        game_map = GameMap.objects.create(
            name="Seeded", x_dim=1000, y_dim=1000, scale=100.0
        )
        version = MapVersion.objects.create(
            game_map=game_map, name="Base", base_version=True
        )
        a = Node.objects.create(game_map=game_map, x_position=0, y_position=0)
        b = Node.objects.create(game_map=game_map, x_position=3, y_position=0)
        for node in (a, b):
            node.map_versions.add(version)
        edge = _street(game_map, version, a, b)
        session = _session(self.user, game_map, people_per_agent=200)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Anna", game=session)
        _route(game_round, player, [edge], agent_id=1)
        return game_round

    def test_generate_departure_minutes_is_reproducible_with_an_explicit_rng(self):
        import random as _random

        from game.simulation import generate_departure_minutes

        first = generate_departure_minutes(
            50, base_hour=9, std_dev_min=10, rng=_random.Random(4242)
        )
        second = generate_departure_minutes(
            50, base_hour=9, std_dev_min=10, rng=_random.Random(4242)
        )

        self.assertEqual(first, second)

    def test_a_different_seed_draws_a_different_schedule(self):
        import random as _random

        from game.simulation import generate_departure_minutes

        first = generate_departure_minutes(
            50, base_hour=9, std_dev_min=10, rng=_random.Random(1)
        )
        second = generate_departure_minutes(
            50, base_hour=9, std_dev_min=10, rng=_random.Random(2)
        )

        self.assertNotEqual(first, second)

    def test_the_simulator_carries_its_own_generator(self):
        import random as _random

        game_round = self._round()

        simulator = TrafficSimulator(game_round, scale=100.0)

        self.assertIsInstance(simulator.rng, _random.Random)

    def test_two_simulators_on_one_round_schedule_identically(self):
        game_round = self._round()

        first = TrafficSimulator(game_round, scale=100.0)
        first._generate_departures(is_morning=True)
        second = TrafficSimulator(game_round, scale=100.0)
        second._generate_departures(is_morning=True)

        self.assertEqual(first.departure_schedule, second.departure_schedule)

    def test_the_module_level_random_does_not_steer_the_simulation(self):
        """Seeding the global generator must not change what the round draws.

        If it does, the engine is still reaching for module-level `random`
        somewhere and the round is only accidentally reproducible.
        """
        import random as _random

        game_round = self._round()

        _random.seed(1)
        first = TrafficSimulator(game_round, scale=100.0)
        first._generate_departures(is_morning=True)
        _random.seed(99999)
        second = TrafficSimulator(game_round, scale=100.0)
        second._generate_departures(is_morning=True)

        self.assertEqual(first.departure_schedule, second.departure_schedule)


class StochasticRoundTests(TestCase):
    """The noise has to reach the round, and with the right shape.

    Large when the network is loaded, near zero when it is free-flowing.
    That is both the better physics and the better game: a jammed network is
    an unreliable one, and clearing a jam buys predictability as well as
    minutes. A flat percentage on the result would wobble an empty map just
    as hard, which is backwards.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="noisy", password="12345")

    def _merge_round(self, label, people, seed):
        """Two approaches onto one lane — the shape that actually queues."""
        from game.tests._helpers import muted

        game_map = GameMap.objects.create(
            name=label, x_dim=1000, y_dim=1000, scale=100.0
        )
        version = MapVersion.objects.create(
            game_map=game_map, name="Base", base_version=True
        )
        coords = {"north": (0, 20), "south": (0, 0), "merge": (10, 10), "work": (13, 10)}
        nodes = {}
        for name, (x, y) in coords.items():
            node = Node.objects.create(game_map=game_map, x_position=x, y_position=y)
            node.map_versions.add(version)
            nodes[name] = node
        shared = _street(game_map, version, nodes["merge"], nodes["work"])
        north = _street(game_map, version, nodes["north"], nodes["merge"])
        south = _street(game_map, version, nodes["south"], nodes["merge"])

        session = _session(self.user, game_map, people_per_agent=people, std_dev=5)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        ben = Player.objects.create(name="Ben", game=session)
        route = _route(game_round, anna, [north, shared], agent_id=1)
        _route(game_round, ben, [south, shared], agent_id=2)

        simulator = TrafficSimulator(game_round, scale=100.0, seed=seed)
        with muted():
            simulator.run_simulation(max_ticks=400)
        return simulator, route

    def _trip_time(self, simulator, route):
        from game.models import AgentSimulationResult

        return AgentSimulationResult.objects.get(agent_route=route).mean_trip_time_min

    def test_the_same_seed_still_reproduces_the_round(self):
        """Noise must not cost reproducibility — the golden master needs it."""
        first, r1 = self._merge_round("same-a", 600, seed=99)
        second, r2 = self._merge_round("same-b", 600, seed=99)

        self.assertAlmostEqual(
            self._trip_time(first, r1), self._trip_time(second, r2), places=9
        )

    def test_a_different_seed_changes_a_congested_round(self):
        """The whole point: two identical rounds must not be identical."""
        times = [
            self._trip_time(*self._merge_round(f"cong-{seed}", 600, seed=seed))
            for seed in (1, 2, 3, 4, 5)
        ]

        self.assertGreater(
            len(set(round(t, 6) for t in times)),
            1,
            f"every seed gave the same trip time: {times}",
        )

    def test_the_spread_is_near_zero_in_free_flow(self):
        """An empty network is predictable. Noise must not invent variance."""
        import statistics

        times = [
            self._trip_time(*self._merge_round(f"free-{seed}", 4, seed=seed))
            for seed in (1, 2, 3, 4, 5)
        ]

        mean = statistics.fmean(times)
        cv = statistics.pstdev(times) / mean if mean else 0.0
        self.assertLess(cv, 0.05, f"free flow should be steady, got CV={cv:.3f}: {times}")

    def test_congestion_is_more_variable_than_free_flow(self):
        """The shape claim, stated as a comparison rather than a threshold."""
        import statistics

        def cv(people, tag):
            times = [
                self._trip_time(*self._merge_round(f"{tag}-{s}", people, seed=s))
                for s in (1, 2, 3, 4, 5)
            ]
            mean = statistics.fmean(times)
            return statistics.pstdev(times) / mean if mean else 0.0

        self.assertGreater(cv(600, "shape-cong"), cv(4, "shape-free"))


class DriverSpeedFactorIsPerVehicleTests(TestCase):
    """Drawn once at spawn, never per edge.

    A driver who is fast on one link has to stay fast on the next. Redrawing
    per edge would average every trip back to the mean over a long route,
    which is the quiet way for a variance dial to do nothing at all.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="perveh", password="12345")

    def test_a_vehicle_keeps_its_speed_factor_across_segments(self):
        from game.tests._helpers import muted

        game_map = GameMap.objects.create(
            name="Chain", x_dim=1000, y_dim=1000, scale=100.0
        )
        version = MapVersion.objects.create(
            game_map=game_map, name="Base", base_version=True
        )
        nodes = []
        for i in range(4):
            node = Node.objects.create(game_map=game_map, x_position=i * 3, y_position=0)
            node.map_versions.add(version)
            nodes.append(node)
        edges = [
            _street(game_map, version, nodes[i], nodes[i + 1]) for i in range(3)
        ]

        session = _session(self.user, game_map, people_per_agent=20, std_dev=1)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Anna", game=session)
        _route(game_round, player, edges, agent_id=1)

        simulator = TrafficSimulator(game_round, scale=100.0, seed=17)
        seen = {}
        original = simulator._free_speed_for

        def spy(vehicle, edge_state):
            seen.setdefault(id(vehicle), set()).add(vehicle.speed_factor)
            return original(vehicle, edge_state)

        simulator._free_speed_for = spy
        with muted():
            simulator.run_simulation(max_ticks=200)

        self.assertTrue(seen, "no vehicle was ever speed-checked")
        multi = {k: v for k, v in seen.items() if len(v) > 1}
        self.assertEqual(multi, {}, f"speed_factor was redrawn mid-trip: {multi}")

    def test_not_every_driver_gets_the_same_factor(self):
        from sim.constants import draw_driver_speed_factor
        import random as _random

        rng = _random.Random(3)
        draws = {round(draw_driver_speed_factor(rng), 9) for _ in range(50)}

        self.assertGreater(len(draws), 1)


class OriginQueueVisibilityTests(TestCase):
    """The queue at the front door has to show up on an instrument.

    A round in which every car driver lost an hour reported `queued_edges=0`
    and `forced=0` at every logged tick, edge snapshots of max 1 vehicle at
    46.7 km/h, and a mean link speed at free flow — because the vehicles were
    never on the link. They were in `self.waiting`, which nothing measures.

    So the heatmap would paint the bottleneck green and the Tempo-30 streets
    as the problem, and the tick log says the network is empty. This is what
    makes finding 5 (the heatmap on the stats screen) safe to build.
    """

    SEED = 20260921

    def setUp(self):
        self.user = User.objects.create_user(username="door", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Door map", 4)
        self.edges = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(3)
        ]
        self.session = _session(
            self.user, self.game_map, people_per_agent=1000, std_dev=1
        )
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.player = Player.objects.create(name="Fahrer", game=self.session)
        self.route = _route(self.game_round, self.player, self.edges)

    def _run(self):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0, seed=self.SEED)
        samples = []

        def probe(tick, total):
            samples.append(dict(getattr(simulator, "held_at_origin", {})))

        with muted():
            result = simulator.run_simulation(max_ticks=200, on_progress=probe)
        return simulator, result, samples

    def test_the_door_queue_is_counted(self):
        """A thousand cars on one lane cannot all be on the road at once."""
        _, _, samples = self._run()

        worst = max((sum(s.values()) for s in samples), default=0)

        self.assertGreater(
            worst, 100, "nothing counted the vehicles held at the front door"
        )

    def test_the_door_queue_is_charged_to_the_link_they_want(self):
        """Not a global number: a heatmap needs to know WHICH street."""
        _, _, samples = self._run()

        worst = max(samples, key=lambda s: sum(s.values()), default={})

        self.assertEqual(list(worst), [self.edges[0].pk])

    def test_the_tick_log_names_the_door_queue(self):
        _, result, _ = self._run()

        lines = [
            line
            for line in result.detailed_log.splitlines()
            if "held_at_door=" in line and "held_at_door=0," not in line
        ]

        self.assertTrue(lines, "no tick line reports a non-empty front door")

    def test_the_snapshot_records_the_door_queue(self):
        from game.models import EdgeTrafficSnapshot

        _, result, _ = self._run()

        held = EdgeTrafficSnapshot.objects.filter(
            simulation=result, waiting_count__gt=0
        )

        self.assertTrue(held.exists())

    def test_a_link_that_looks_empty_is_still_snapshotted(self):
        """The exact shape of the bug: one vehicle on the link, hundreds outside."""
        from game.models import EdgeTrafficSnapshot

        _, result, _ = self._run()

        hidden = EdgeTrafficSnapshot.objects.filter(
            simulation=result,
            edge_id=self.edges[0].pk,
            waiting_count__gt=models.F("vehicle_count"),
        )

        self.assertTrue(
            hidden.exists(),
            "no snapshot shows more vehicles waiting to get on than on the link",
        )


class TrafficHeatmapPayloadTests(TestCase):
    """`api/game/<id>/round/<n>/traffic/` has to carry the door queue too.

    Here rather than in test_rounds.py: the endpoint reports simulation
    output, and the map helpers that build a graph to report on live in this
    file. Rows are written by hand — this is about the payload, not about
    reproducing a jam.
    """

    def setUp(self):
        from django.conf import settings

        from co2mmute.utils import sign_value
        from game.models import EdgeTrafficSnapshot, SimulationResult

        self.user = User.objects.create_user(username="heat", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Heat map", 3)
        self.edges = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(2)
        ]
        from game.tests._helpers import muted

        with muted():
            self.session = _session(self.user, self.game_map)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.result = SimulationResult.objects.create(
            game_round=self.game_round, status=SimulationResult.Status.COMPLETED
        )
        # The bottleneck: nothing on the link, 400 people outside it.
        EdgeTrafficSnapshot.objects.create(
            simulation=self.result,
            edge_id=self.edges[0].pk,
            time_tick=5,
            vehicle_count=1,
            waiting_count=400,
            speed_kmh=49.2,
        )
        # An ordinary busy link, for contrast.
        EdgeTrafficSnapshot.objects.create(
            simulation=self.result,
            edge_id=self.edges[1].pk,
            time_tick=5,
            vehicle_count=30,
            waiting_count=0,
            speed_kmh=25.0,
        )
        self.client.cookies[
            f"{settings.COOKIE_GAME_PREFIX}{self.session.game_id}"
        ] = sign_value(
            f"{self.session.game_id}:test-token", settings.COOKIE_GAME_SALT
        )

    def _get(self):
        return self.client.get(
            f"/api/game/{self.session.game_id}/round/1/traffic/"
        )

    def test_the_payload_carries_the_door_queue(self):
        response = self._get()

        edges = {e["edge_id"]: e for e in response.json()["edges"]}

        self.assertEqual(edges[self.edges[0].pk]["max_waiting_count"], 400)

    def test_a_link_with_nobody_waiting_reports_zero(self):
        response = self._get()

        edges = {e["edge_id"]: e for e in response.json()["edges"]}

        self.assertEqual(edges[self.edges[1].pk]["max_waiting_count"], 0)

    def test_the_speed_ratio_is_unchanged(self):
        """The door queue is a second number, not a correction to this one.

        A link at 49.2 of 50 km/h IS running at free flow; the 400 people
        outside it are a different fact about the same street. Folding them
        into one figure would be putting the right colour on the map for the
        wrong reason.
        """
        response = self._get()

        edges = {e["edge_id"]: e for e in response.json()["edges"]}

        self.assertAlmostEqual(
            edges[self.edges[0].pk]["congestion_ratio"], 0.016, places=3
        )
