"""
Unit tests for the traffic simulation.

Tests cover:
- The link queue model: flow capacity, storage, spillback, deadlock escape
- Speed-dependent CO2 and cost for cars, and that a jam costs more of both
- Free-flow trip times (no longer quantised to whole ticks)
- Dedicated bus lanes and bus gates
- Bike lanes: a lane taken from the cars, and a bike in mixed traffic
- Bus traffic integration (a dedicated lane costs the cars nothing)
- Departure minutes, and that they are fair across routes
- Speed loading from models, and the speed_limit = 0 fallback
- Non-arrival accounting
- Simulation parameter loading
"""

from django.contrib.auth.models import User
from django.db import models
from django.test import SimpleTestCase, TestCase, override_settings
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
    SimulationResult,
)
from game.tests._helpers import TEST_BACKENDS
from game.simulation import (
    EdgeState,
    TrafficSimulator,
    draw_driver_speed_factor,
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
        ).map_versions.add(self.map_version)

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
        ).map_versions.add(self.map_version)

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
        # Every waiting entry is exactly one person since
        # `[backend]-pt-boarding.md` deleted route_vehicle_scaling; this test
        # used to have to say so.
        # (wanted departure, route, person, desired-speed factor) — the
        # factor is drawn with the departure now rather than at each spawn
        # attempt, so it rides along on the waiting list.
        simulator.waiting = [
            (820.0, self.agent_route.pk, 0, 1.0),
            # Wanted to leave after the clock stopped: nothing happened to
            # them, so nothing is recorded.
            (1200.0, self.agent_route.pk, 1, 1.0),
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


def _street(
    game_map,
    version,
    start,
    end,
    speed_limit=50,
    lanes=1,
    bus_lane=False,
    bike_lane=False,
):
    edge = Edge.objects.create(
        game_map=game_map,
        start_node=start,
        end_node=end,
        max_lanes=lanes,
        bike_lane=bike_lane,
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


def _route(
    game_round,
    player,
    edges,
    mode="car",
    agent_id=1,
    distance=None,
    direction="out",
):
    move, _ = PlayerMove.objects.get_or_create(
        session_round=game_round, player=player, action="route_submit"
    )
    route = AgentRoute.objects.create(
        player_move=move,
        agent_id=agent_id,
        direction=direction,
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

    Measured over five pinned seeds rather than one unpinned round, because
    the thing being asserted is a BIAS and a single round is mostly noise. On
    one draw the two means part by up to 17 % with the spawn loop working
    correctly (3 of 40 seeds break a 10 % bound); pooling five takes the worst
    block of 40 to 4.4 %. Unfairness of the kind this guards is a factor, not
    a few per cent, so the bound loses nothing by sitting at 7 %.

    Unpinned it drew its seed from the round pk, which climbs with however
    many rounds the suite made earlier — so adding tests anywhere before it
    could turn it red without touching the model. It did, on 2026-09-25.
    """

    SEEDS = (0, 1, 2, 3, 4)

    def setUp(self):
        self.user = User.objects.create_user(username="fair", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Fair map", 3)
        self.edges = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(2)
        ]
        self.session = _session(self.user, self.game_map, people_per_agent=400, std_dev=1)
        self.anna = Player.objects.create(name="Anna", game=self.session)
        self.ben = Player.objects.create(name="Ben", game=self.session)

    def _round_with_both(self, round_number):
        """A round of its own per seed — SimulationResult is one per round."""
        game_round = GameRound.objects.create(
            game=self.session, round_number=round_number
        )
        return (
            game_round,
            _route(game_round, self.anna, self.edges, agent_id=1),
            _route(game_round, self.ben, self.edges, agent_id=2),
        )

    def test_both_routes_wait_about_equally(self):
        from game.tests._helpers import muted

        times_a, times_b = [], []
        for seed in self.SEEDS:
            game_round, route_a, route_b = self._round_with_both(seed + 1)
            simulator = TrafficSimulator(game_round, scale=100.0, seed=seed)
            with muted():
                simulator.run_simulation(max_ticks=200)
            times_a += simulator.agent_results[route_a.pk]["trip_times"]
            times_b += simulator.agent_results[route_b.pk]["trip_times"]

        mean_a = sum(times_a) / len(times_a)
        mean_b = sum(times_b) / len(times_b)

        self.assertLess(
            abs(mean_a - mean_b) / max(mean_a, mean_b),
            0.07,
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
            # One car per link per DEADLOCK_TICKS: a hard lock drains slowly.
            # This ring needs ~680 ticks with the shuffled visiting order (~330
            # when the two links strictly alternated): it depends on which link
            # escapes first.
            simulator.run_simulation(max_ticks=1000)

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


    def test_one_escape_frees_one_car_not_the_budget(self):
        from game.tests._helpers import muted
        from sim.constants import DEADLOCK_TICKS

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        forced_at = []
        real = simulator._pick_head

        def spy(edge_state, tick_end):
            pick = real(edge_state, tick_end)
            if pick is not None and pick[1]:
                forced_at.append((edge_state.edge_id, simulator.current_tick))
            return pick

        simulator._pick_head = spy
        with muted():
            simulator.run_simulation(max_ticks=300)

        self.assertTrue(forced_at, "the run never forced anything")
        last = {}
        for edge_id, tick in forced_at:
            if edge_id in last:
                self.assertGreaterEqual(
                    tick - last[edge_id],
                    DEADLOCK_TICKS,
                    f"link {edge_id} forced twice within {DEADLOCK_TICKS} ticks",
                )
            last[edge_id] = tick


class FairMergeTests(TestCase):
    """Links feeding one junction take turns at being served first.

    A fixed visiting order lets whichever feeder comes first in the dict take
    every slot a discharge frees, so the others sit until the escape fires.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="fairmerge", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Fair map", 3, step_units=1.0)
        first = _street(self.game_map, self.version, self.nodes[0], self.nodes[1])
        second = _street(self.game_map, self.version, self.nodes[1], self.nodes[2])
        self.session = _session(self.user, self.game_map, people_per_agent=300, std_dev=1)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        anna = Player.objects.create(name="Anna", game=self.session)
        ben = Player.objects.create(name="Ben", game=self.session)
        _route(self.game_round, anna, [first, second], agent_id=1)
        _route(self.game_round, ben, [second, first], agent_id=2)

    def test_every_feeder_of_a_junction_goes_first_equally_often(self):
        # The zipper: three feeders of one junction, next to each other in the
        # dict, among twenty other links. Whoever is visited first takes the
        # room a discharge frees, so each must be first on about a third of the
        # ticks. A rotation by one link per tick gives the first feeder 21 of
        # every 23 ticks and the other two one each.
        simulator = TrafficSimulator(self.game_round, scale=100.0)
        simulator.edge_states = {pk: f"link {pk}" for pk in range(23)}
        feeders = ["link 0", "link 1", "link 2"]

        first = {feeder: 0 for feeder in feeders}
        for tick in range(300):
            simulator.current_tick = tick
            order = simulator._visiting_order()
            first[min(feeders, key=order.index)] += 1

        for feeder, count in first.items():
            self.assertGreater(count, 70, f"{feeder} went first on {count} of 300 ticks")


class TurnQueueTests(TestCase):
    """One queue per street on one lane; one per next street on two or more.

    A feeder splits at a junction into a street (B) whose door a flood of
    other people has filled, and a free one (C). On a single lane a driver
    waiting to turn into B does block everybody behind, whichever way they are
    going. On two lanes the cars bound for C pass the ones bound for B.
    """

    def _play(self, feeder_lanes, seed=7):
        from game.tests._helpers import muted

        user = User.objects.create_user(
            username=f"turn{feeder_lanes}", password="12345"
        )
        game_map, version, nodes = _grid_map("Turn map", 5, step_units=10.0)
        feeder = _street(
            game_map, version, nodes[0], nodes[1], lanes=feeder_lanes
        )
        into_b = _street(game_map, version, nodes[1], nodes[2])
        past_b = _street(game_map, version, nodes[2], nodes[3])
        into_c = _street(game_map, version, nodes[1], nodes[4])
        session = _session(user, game_map, people_per_agent=300, std_dev=1)
        game_round = GameRound.objects.create(game=session, round_number=1)
        flood = Player.objects.create(name="Flut", game=session)
        to_b = Player.objects.create(name="B", game=session)
        to_c = Player.objects.create(name="C", game=session)
        # Three Gruppen start on B's own door and keep it full for half an hour.
        for agent_id in (1, 2, 3):
            _route(game_round, flood, [into_b, past_b], agent_id=agent_id)
        route_b = _route(game_round, to_b, [feeder, into_b], agent_id=1)
        route_c = _route(game_round, to_c, [feeder, into_c], agent_id=1)

        simulator = TrafficSimulator(game_round, scale=100.0, seed=seed)
        with muted():
            simulator.run_simulation(max_ticks=300)
        return simulator, route_b, route_c

    @staticmethod
    def _mean(values):
        return sum(values) / len(values)

    def test_on_one_lane_a_blocked_turn_holds_everybody_behind(self):
        simulator, _, route_c = self._play(feeder_lanes=1)

        delays = simulator.agent_results[route_c.pk]["delays"]

        self.assertGreater(self._mean(delays), 5.0)

    def test_on_two_lanes_a_blocked_turn_holds_nobody_else(self):
        one_lane, _, one_lane_c = self._play(feeder_lanes=1)
        simulator, route_b, route_c = self._play(feeder_lanes=2)

        held_c = self._mean(one_lane.agent_results[one_lane_c.pk]["delays"])
        delays_c = simulator.agent_results[route_c.pk]["delays"]
        delays_b = simulator.agent_results[route_b.pk]["delays"]

        # Not zero: 600 cars still share the feeder's flow. A third of what the
        # same people suffer behind a blocked head is the mechanism, not noise.
        self.assertLess(self._mean(delays_c), held_c / 3)
        # The turn queue itself is still a queue: B is held, only C is not.
        self.assertGreater(self._mean(delays_b), 5.0)

    def test_everybody_still_arrives_on_two_lanes(self):
        simulator, route_b, route_c = self._play(feeder_lanes=2)

        for route in (route_b, route_c):
            self.assertEqual(simulator.agent_results[route.pk]["not_arrived"], 0)


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

        # people=5, not 400: 400 cars wanting to leave in the same minute on
        # one lane is not an empty road, it is a lane at its flow capacity.
        # It only read as free flow while the origin link admitted its storage
        # per tick and spread the load over ten ticks instead of three.
        free = self._play_chain("Anchor map", people=5)

        expected = CAR_EMISSIONS_G_PER_KM * 0.9
        self.assertLess(
            abs(free["co2_per_person"] - expected) / expected,
            0.015,
            f'{free["co2_per_person"]:.3f} against {expected:.3f}',
        )

    def test_an_empty_fifty_route_still_costs_about_the_old_number(self):
        """Same tolerance, same reason — cost rides the emission curve."""
        from game.simulation import CAR_COST_PER_KM

        free = self._play_chain("Anchor cost map", people=5)

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


class OriginAdmissionTests(TestCase):
    """A trip's first link admits its FLOW per tick, not its STORAGE.

    `_advance_traffic` spawns once, before the `while moved:` discharge loop,
    so the origin link is filled once per tick and emptied again inside the
    same tick. With a 5-minute tick over a link a car crosses in 0.36 min it
    should cycle four or five times; it cycles once. Measured on the live map:
    exactly 118 vehicles per tick on a link whose storage is 118 and whose
    flow is 157 — 1416 veh/h against a nominal 1800.

    The fixture makes the two numbers far apart on purpose: 300 m of one lane
    holds 39.9 vehicles and discharges 150 of them per tick, so "admits its
    storage" and "admits its flow" are a factor of 3.75 apart and no reading of
    the noise can confuse them.
    """

    SEED = 20260921

    def setUp(self):
        self.user = User.objects.create_user(username="origin", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Origin map", 4)
        self.edges = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(3)
        ]
        # Everyone wants to leave at the same minute, so the waiting list is
        # never the thing that throttles admission.
        self.session = _session(
            self.user, self.game_map, people_per_agent=1000, std_dev=1
        )
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.player = Player.objects.create(name="Fahrer", game=self.session)
        self.route = _route(self.game_round, self.player, self.edges)

    def _run(self):
        """Run the round, sampling the waiting list once per tick.

        `on_progress` fires after `_advance_traffic`, so the difference between
        two samples is exactly what the network admitted in that tick.
        """
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0, seed=self.SEED)
        waiting = []

        def probe(tick, total):
            waiting.append(len(simulator.waiting))

        with muted():
            simulator.run_simulation(max_ticks=200, on_progress=probe)
        return simulator, waiting

    def _admissions(self, waiting):
        return [a - b for a, b in zip(waiting, waiting[1:])]

    def test_the_first_link_admits_more_than_it_holds(self):
        """The decisive one. Storage is 39.9; anything near it is the bug."""
        simulator, waiting = self._run()
        storage = simulator.edge_states[self.edges[0].pk].storage_capacity_pcu

        best = max(self._admissions(waiting))

        self.assertGreater(
            best,
            storage * 2,
            f"best tick admitted {best:.0f} against a storage of {storage:.0f} "
            f"— the origin link still cycles once per tick",
        )

    def test_admission_is_the_links_flow_capacity(self):
        """Not just 'more than storage': the number the model means is flow."""
        simulator, waiting = self._run()
        flow = simulator.edge_states[self.edges[0].pk].flow_per_tick(
            self.session.tick_duration_min
        )

        best = max(self._admissions(waiting))

        self.assertGreater(best, flow * 0.8, f"{best:.0f} against a flow of {flow:.0f}")

    def test_a_thousand_cars_are_on_the_road_inside_ten_ticks(self):
        """1000 at 150/tick is seven ticks. At 40/tick it is twenty-five."""
        _, waiting = self._run()

        opened = next(i for i, left in enumerate(waiting) if left < 1000)
        emptied = next(i for i, left in enumerate(waiting) if left == 0)

        self.assertLess(
            emptied - opened,
            10,
            f"the waiting list took {emptied - opened} ticks to clear",
        )

    def test_everybody_still_arrives(self):
        """The invariant the change must not cost: no one is left standing."""
        simulator, _ = self._run()

        results = simulator.agent_results[self.route.pk]

        self.assertEqual(results["not_arrived"], 0)
        self.assertEqual(len(results["trip_times"]), 1000)


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


# ---------------------------------------------------------------------------
# PT runs to its timetable — society vs personal numbers
# `.claude/plans/to-do/[backend]-pt-timetable-and-society.md`
#
# Every new symbol below is imported INSIDE the test that needs it. A missing
# `PTLineState` at module level would raise on import and silently delete the
# other two thousand lines of this file from the run — which is exactly the
# failure mode `test_all_python_sources_parse` cannot see.
# ---------------------------------------------------------------------------


class PTScenarioMixin:
    """Two 1 km links in a row, one bus line and one train line over both.

    Distances are chosen so every expected figure is a round number at
    scale=100: each edge is 10 units long, so 1 km, and a line over both is
    2 km. The bus runs every 10 minutes — 12 vehicles in the 120-minute
    departure window — and the train every 5, so 24. That makes

        bus   society CO2 = 12 x 2 km x 1200 g =  28 800 g
        train society CO2 = 24 x 2 km x 1500 g =  72 000 g

    and the same shape in euro. None of it depends on people_per_agent: a
    share is person-km over person-km, so the scale cancels.
    """

    def _pt_map(self, label="PT map", bus_interval=10, train_interval=5,
                bus_capacity=85, train_capacity=1000):
        game_map = GameMap.objects.create(
            name=label, x_dim=100, y_dim=100, scale=100.0
        )
        version = MapVersion.objects.create(
            game_map=game_map, name="Base", base_version=True
        )
        nodes = []
        for i in range(3):
            node = Node.objects.create(
                game_map=game_map, name=f"N{i}", x_position=i * 10, y_position=0
            )
            node.map_versions.add(version)
            nodes.append(node)

        edges = [
            _street(game_map, version, nodes[0], nodes[1], lanes=2),
            _street(game_map, version, nodes[1], nodes[2], lanes=2),
        ]

        bus_line = BusLine.objects.create(
            game_map=game_map,
            name="M1",
            intervall=bus_interval,
            bus_capacity=bus_capacity,
        )
        bus_line.map_versions.add(version)
        for order, edge in enumerate(edges):
            BusLineEdge.objects.create(
                bus_line=bus_line,
                street_edge=edge.streetedge_set.first(),
                order=order,
            ).map_versions.add(version)

        train_edges = []
        for edge in edges:
            train_edge = TrainEdge.objects.create(edge=edge)
            train_edge.map_versions.add(version)
            train_edges.append(train_edge)
        train_line = TrainLine.objects.create(
            game_map=game_map,
            name="U1",
            intervall=train_interval,
            train_capacity=train_capacity,
        )
        train_line.map_versions.add(version)
        for order, train_edge in enumerate(train_edges):
            TrainLineEdge.objects.create(
                train_line=train_line, train_edge=train_edge, order=order
            ).map_versions.add(version)

        return game_map, version, edges, bus_line, train_line

    def _pt_session(self, game_map, version, people=100):
        session = _session(self.user, game_map, people_per_agent=people, std_dev=5)
        session.active_map_version = version
        session.save(update_fields=["active_map_version"])
        return session

    def _pt_route(
        self, game_round, player, edges, mode, line, agent_id=1, direction="out"
    ):
        """A route whose segments name a PT line, which `_route` cannot do."""
        move, _ = PlayerMove.objects.get_or_create(
            session_round=game_round, player=player, action="route_submit"
        )
        route = AgentRoute.objects.create(
            player_move=move,
            agent_id=agent_id,
            direction=direction,
            transport_mode="public",
            total_distance_m=1000.0 * len(edges),
            estimated_time_min=5.0,
        )
        for order, edge in enumerate(edges, start=1):
            RouteSegment.objects.create(
                agent_route=route,
                order=order,
                edge=edge,
                mode=mode,
                pt_line_id=line.pk,
            )
        return route

    def _run(self, game_round, seed=606, max_ticks=300):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(game_round, scale=100.0, seed=seed)
        with muted():
            simulator.run_simulation(max_ticks=max_ticks)
        return simulator


class PTLineRegistryTests(PTScenarioMixin, TestCase):
    """The unit is the LINE, and every line on the version is in the registry.

    Today vehicles are counted per AgentRoute, so two agents riding M1 count
    M1's buses twice and a line nobody rides is not counted at all. A timetable
    is a property of the map, not of who chose it.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptregistry", password="12345")

    def test_a_line_nobody_rides_is_still_registered(self):
        """The whole finding, in the loading step: the timetable does not ask."""
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Anna", game=session)
        _route(game_round, player, edges, mode="car", agent_id=1)

        simulator = TrafficSimulator(game_round, scale=100.0)

        self.assertIn(("bus", bus_line.pk), simulator.pt_lines)
        self.assertIn(("train", train_line.pk), simulator.pt_lines)

    def test_the_round_loads_the_chain_of_the_version_it_runs_on(self):
        """A line's route is per version, so the timetable has to ask which one.

        The registry used to take the whole chain and let `_register_pt_line`
        trim it to whatever was on this version's network. With the chain shared
        between versions that meant a link this version had replaced sat in the
        middle of the list, the trim cut the line there, and the riders past the
        cut were stranded — which keeps the line dispatching and paying society
        CO2 to the end of the clock. Two versions of one line, two lengths, and
        a round that names its version gets its own.
        """
        from maps.models import MapVersion, StreetEdge

        game_map, version, edges, bus_line, _ = self._pt_map()
        short = MapVersion.objects.create(game_map=game_map, name="Kurzfahrt")
        for element in (
            *edges,
            *[node for edge in edges for node in (edge.start_node, edge.end_node)],
        ):
            element.map_versions.add(short)
        for se in StreetEdge.objects.filter(edge__in=edges):
            se.map_versions.add(short)
        bus_line.map_versions.add(short)
        rows = list(bus_line.buslineedge_set.order_by("order"))
        for row in rows:
            row.map_versions.add(short)
        rows[-1].map_versions.remove(short)  # the short version stops one early

        for active, expected_km in ((version, 2.0), (short, 1.0)):
            with self.subTest(version=active.name):
                session = self._pt_session(game_map, active)
                game_round = GameRound.objects.create(game=session, round_number=1)

                simulator = TrafficSimulator(game_round, scale=100.0)

                self.assertAlmostEqual(
                    simulator.pt_lines[("bus", bus_line.pk)].line_km,
                    expected_km,
                    places=6,
                )

    def test_line_km_is_the_geometry_times_the_scale(self):
        game_map, version, edges, bus_line, _ = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)

        simulator = TrafficSimulator(game_round, scale=100.0)

        self.assertAlmostEqual(
            simulator.pt_lines[("bus", bus_line.pk)].line_km, 2.0, places=6
        )

    def test_vehicles_come_from_the_interval_not_from_demand(self):
        game_map, version, _, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)

        simulator = TrafficSimulator(game_round, scale=100.0)

        # DEPARTURE_WINDOW_MIN is 120. `base_vehicles` is the timetable;
        # `vehicles` counts what actually left, and nothing has left yet.
        self.assertEqual(simulator.pt_lines[("bus", bus_line.pk)].base_vehicles, 12)
        self.assertEqual(
            simulator.pt_lines[("train", train_line.pk)].base_vehicles, 24
        )

    def test_an_interval_that_does_not_divide_the_window_rounds(self):
        """floor() would quietly shorten every timetable with an odd interval."""
        game_map, version, _, bus_line, _ = self._pt_map(bus_interval=7)
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)

        simulator = TrafficSimulator(game_round, scale=100.0)

        self.assertEqual(simulator.pt_lines[("bus", bus_line.pk)].base_vehicles, 17)

    def test_a_bus_and_a_train_with_the_same_id_do_not_collide(self):
        """RouteSegment.pt_line_id is a bare id from two different sequences.

        Keyed by that id alone, registering the train would overwrite the bus
        and every M1 rider would silently be charged U1's emissions. The pk is
        forced equal here because a natural collision is a matter of luck.
        """
        game_map, version, edges, bus_line, train_line = self._pt_map()
        train_line.delete()
        twin = TrainLine.objects.create(
            pk=bus_line.pk,
            game_map=game_map,
            name="U-twin",
            intervall=5,
            train_capacity=1000,
        )
        twin.map_versions.add(version)
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)

        simulator = TrafficSimulator(game_round, scale=100.0)

        self.assertEqual(len(simulator.pt_lines), 2)
        self.assertEqual(simulator.pt_lines[("bus", bus_line.pk)].mode, "bus")
        self.assertEqual(simulator.pt_lines[("train", twin.pk)].mode, "train")

    def test_falls_back_to_the_base_version_without_an_active_one(self):
        """active_map_version is only set when a game starts through the API."""
        game_map, version, _, bus_line, _ = self._pt_map()
        session = _session(self.user, game_map, people_per_agent=100)
        self.assertIsNone(session.active_map_version)
        game_round = GameRound.objects.create(game=session, round_number=1)

        simulator = TrafficSimulator(game_round, scale=100.0)

        self.assertIn(("bus", bus_line.pk), simulator.pt_lines)

    def test_a_line_on_another_version_is_not_registered(self):
        """A version is a filter over one shared graph — so is its timetable."""
        game_map, version, _, _, _ = self._pt_map()
        other = MapVersion.objects.create(game_map=game_map, name="Other")
        only_there = BusLine.objects.create(
            game_map=game_map, name="M-other", intervall=10, bus_capacity=85
        )
        only_there.map_versions.add(other)
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)

        simulator = TrafficSimulator(game_round, scale=100.0)

        self.assertNotIn(("bus", only_there.pk), simulator.pt_lines)


class PTSocietyFiguresTests(PTScenarioMixin, TestCase):
    """A line emits because it runs, not because someone is aboard.

    `_calculate_emissions_and_cost` divides by `capacity` today, which makes a
    full bus and an empty one identical per person and a line nobody rides
    free. Both halves of that are wrong and they are the same line of code.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptsociety", password="12345")

    def _round_with(self, mode="car", **map_kwargs):
        game_map, version, edges, bus_line, train_line = self._pt_map(**map_kwargs)
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Anna", game=session)
        if mode == "car":
            _route(game_round, player, edges, mode="car", agent_id=1)
        else:
            self._pt_route(game_round, player, edges, "bus", bus_line, agent_id=1)
        return game_map, version, edges, bus_line, train_line, game_round

    def test_society_is_vehicles_times_km_times_the_vehicle_factor(self):
        _, _, _, bus_line, _, game_round = self._round_with()

        # The round has to RUN: since `pt-service-period` the figure comes off
        # the runs actually dispatched, which is 0 on a fresh simulator.
        simulator = self._run(game_round)
        line = simulator.pt_lines[("bus", bus_line.pk)]

        # 12 vehicles x 2 km x 1200 g/vehicle-km
        self.assertAlmostEqual(line.society_co2_g, 28_800.0, places=3)
        # 12 vehicles x 2 km x 4.50 €/vehicle-km
        self.assertAlmostEqual(line.society_cost_eur, 108.0, places=3)

    def test_capacity_does_not_touch_the_society_figure(self):
        """The seats are not what burns the diesel.

        This is the test that makes the capacity data pass safe: after this
        change nothing on the emissions path reads bus_capacity at all, so a
        60-seat U-Bahn can be corrected to 1000 without moving a number.

        Since `[backend]-pt-service-period.md` this is a statement about the
        emissions ARITHMETIC, which still never reads bus_capacity — and it
        holds outright here, where nobody rides the line so no extra run is
        ever dispatched. On a line the peak overloads, capacity decides how
        many extra buses go, and those emit.
        """
        _, _, _, small_line, _, small_round = self._round_with(bus_capacity=20)
        _, _, _, large_line, _, large_round = self._round_with(
            bus_capacity=500, label="PT map large"
        )

        small = self._run(small_round)
        large = self._run(large_round)

        self.assertAlmostEqual(
            small.pt_lines[("bus", small_line.pk)].society_co2_g,
            large.pt_lines[("bus", large_line.pk)].society_co2_g,
            places=3,
        )
        self.assertAlmostEqual(
            small.pt_lines[("bus", small_line.pk)].society_co2_g, 28_800.0, places=3
        )

    def test_a_line_nobody_rides_is_in_the_round_total(self):
        """Everybody drives; the buses and trains still ran."""
        from game.models import SimulationResult

        _, _, _, _, _, game_round = self._round_with(mode="car")

        self._run(game_round)

        result = SimulationResult.objects.get(game_round=game_round)
        # 28 800 g of bus + 72 000 g of train, plus whatever the car did.
        self.assertGreater(result.total_co2_g, 100_800.0)

    def test_network_co2_is_the_whole_timetable(self):
        from game.models import SimulationResult

        _, _, _, _, _, game_round = self._round_with(mode="car")

        self._run(game_round)

        result = SimulationResult.objects.get(game_round=game_round)
        self.assertAlmostEqual(result.network_co2_g, 100_800.0, places=2)
        self.assertAlmostEqual(result.network_cost_eur, 108.0 + 576.0, places=2)

    def test_the_total_is_the_routes_plus_the_lines_nobody_rode(self):
        """The identity the screen has to explain: rows + network = headline."""
        from game.models import AgentSimulationResult, SimulationResult

        _, _, _, _, _, game_round = self._round_with(mode="car")

        self._run(game_round)

        result = SimulationResult.objects.get(game_round=game_round)
        rows = AgentSimulationResult.objects.filter(simulation=result)
        row_total = sum(row.total_co2_g for row in rows)

        self.assertAlmostEqual(
            result.total_co2_g, row_total + result.network_co2_g, places=2
        )


class PTPersonalShareTests(PTScenarioMixin, TestCase):
    """personal = society x person-km / person-km, and the shares add up.

    This is where "the more people take the bus the better it looks per
    person" actually comes from. Today it does not happen at all: the figure
    is society / capacity whoever else is aboard.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptshare", password="12345")

    def test_one_rider_carries_the_whole_line(self):
        from game.models import AgentSimulationResult

        game_map, version, edges, bus_line, _ = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        route = self._pt_route(game_round, anna, edges, "bus", bus_line, agent_id=1)

        self._run(game_round)

        result = AgentSimulationResult.objects.get(agent_route=route)
        self.assertAlmostEqual(result.total_co2_g, 28_800.0, places=2)

    def test_two_agents_on_one_line_halve_each_others_share(self):
        from game.models import AgentSimulationResult

        game_map, version, edges, bus_line, _ = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        ben = Player.objects.create(name="Ben", game=session)
        first = self._pt_route(game_round, anna, edges, "bus", bus_line, agent_id=1)
        second = self._pt_route(game_round, ben, edges, "bus", bus_line, agent_id=2)

        self._run(game_round)

        one = AgentSimulationResult.objects.get(agent_route=first)
        two = AgentSimulationResult.objects.get(agent_route=second)
        self.assertAlmostEqual(one.total_co2_g, 14_400.0, places=2)
        self.assertAlmostEqual(two.total_co2_g, 14_400.0, places=2)

    def test_the_shares_add_up_to_the_line(self):
        """The identity the whole design rests on."""
        from game.models import AgentSimulationResult

        game_map, version, edges, bus_line, _ = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        ben = Player.objects.create(name="Ben", game=session)
        self._pt_route(game_round, anna, edges, "bus", bus_line, agent_id=1)
        self._pt_route(game_round, ben, edges[:1], "bus", bus_line, agent_id=2)

        self._run(game_round)

        rows = AgentSimulationResult.objects.filter(
            agent_route__player_move__session_round=game_round
        )
        self.assertAlmostEqual(
            sum(row.total_co2_g for row in rows), 28_800.0, places=2
        )

    def test_a_short_ride_carries_less_than_a_long_one(self):
        """Per head rather than per person-km, a one-stop hop would pay full.

        Anna rides both kilometres, Ben one. Three person-km on the line, so
        Anna carries two thirds of it and Ben one.
        """
        from game.models import AgentSimulationResult

        game_map, version, edges, bus_line, _ = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        ben = Player.objects.create(name="Ben", game=session)
        long_route = self._pt_route(game_round, anna, edges, "bus", bus_line, agent_id=1)
        short_route = self._pt_route(
            game_round, ben, edges[:1], "bus", bus_line, agent_id=2
        )

        self._run(game_round)

        long_result = AgentSimulationResult.objects.get(agent_route=long_route)
        short_result = AgentSimulationResult.objects.get(agent_route=short_route)
        self.assertAlmostEqual(long_result.total_co2_g, 19_200.0, places=2)
        self.assertAlmostEqual(short_result.total_co2_g, 9_600.0, places=2)


class PTFareAndOutOfPocketTests(PTScenarioMixin, TestCase):
    """*Was du zahlst* beside *was es kostet* — on both modes.

    The PT gap between the two IS the subsidy, which is the only reason a fare
    is in the model at all. The car's contrast needs no new constant:
    CAR_COST_TRAFFIC_SHARE already splits the Vollkosten in half.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptfare", password="12345")

    def test_the_car_pays_the_traffic_metered_half(self):
        from sim.constants import (
            CAR_COST_PER_KM,
            CAR_COST_TRAFFIC_SHARE,
            car_out_of_pocket_eur_per_km,
        )

        self.assertAlmostEqual(
            car_out_of_pocket_eur_per_km(50.0),
            CAR_COST_PER_KM * CAR_COST_TRAFFIC_SHARE,
            places=10,
        )

    def test_what_a_jam_costs_is_felt_entirely_out_of_pocket(self):
        """Abschreibung does not rise in a jam; fuel and brakes do."""
        from sim.constants import car_cost_eur_per_km, car_out_of_pocket_eur_per_km

        free = car_out_of_pocket_eur_per_km(50.0)
        jammed = car_out_of_pocket_eur_per_km(10.0)

        self.assertGreater(jammed, free)
        self.assertAlmostEqual(
            jammed - free,
            car_cost_eur_per_km(10.0) - car_cost_eur_per_km(50.0),
            places=10,
        )

    def test_a_pt_trip_pays_one_ticket(self):
        from game.models import AgentSimulationResult
        from sim.constants import PT_FARE_EUR

        game_map, version, edges, bus_line, _ = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        route = self._pt_route(game_round, anna, edges, "bus", bus_line, agent_id=1)

        self._run(game_round)

        result = AgentSimulationResult.objects.get(agent_route=route)
        self.assertAlmostEqual(result.mean_paid_eur, PT_FARE_EUR, places=6)

    def test_a_transfer_is_still_one_ticket(self):
        """One Ticket for the trip, not one per Umstieg."""
        from game.models import AgentSimulationResult
        from sim.constants import PT_FARE_EUR

        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        move = PlayerMove.objects.create(
            session_round=game_round, player=anna, action="route_submit"
        )
        route = AgentRoute.objects.create(
            player_move=move,
            agent_id=1,
            transport_mode="public",
            total_distance_m=2000.0,
            estimated_time_min=5.0,
        )
        RouteSegment.objects.create(
            agent_route=route, order=1, edge=edges[0], mode="bus",
            pt_line_id=bus_line.pk,
        )
        RouteSegment.objects.create(
            agent_route=route, order=2, edge=edges[1], mode="train",
            pt_line_id=train_line.pk,
        )

        self._run(game_round)

        result = AgentSimulationResult.objects.get(agent_route=route)
        self.assertAlmostEqual(result.mean_paid_eur, PT_FARE_EUR, places=6)

    def test_a_driver_pays_less_than_the_trip_costs(self):
        from game.models import AgentSimulationResult

        game_map, version, edges, _, _ = self._pt_map()
        session = self._pt_session(game_map, version, people=20)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        route = _route(game_round, anna, edges, mode="car", agent_id=1)

        self._run(game_round)

        result = AgentSimulationResult.objects.get(agent_route=route)
        self.assertGreater(result.mean_paid_eur, 0.0)
        self.assertLess(result.mean_paid_eur, result.mean_cost_eur)

    def test_a_walker_pays_nothing(self):
        from game.models import AgentSimulationResult

        game_map, version, edges, _, _ = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = GameRound.objects.create(game=session, round_number=1)
        anna = Player.objects.create(name="Anna", game=session)
        route = _route(game_round, anna, edges, mode="walk", agent_id=1)

        self._run(game_round)

        result = AgentSimulationResult.objects.get(agent_route=route)
        self.assertAlmostEqual(result.mean_paid_eur, 0.0, places=6)


# ---------------------------------------------------------------------------
# Passengers board buses — the PT half of the tick loop
# `.claude/plans/to-do/[backend]-pt-boarding.md`
#
# Every new symbol below is imported INSIDE the test that needs it, for the
# reason given above PTScenarioMixin: a missing name at module level would
# raise on import and silently delete the rest of this file from the run.
# ---------------------------------------------------------------------------


class PTBoardingScenarioMixin(PTScenarioMixin):
    """The timetable fixture, plus routes that walk to the stop and change.

    The two-link map already has a bus line and a train line over BOTH links,
    so a route that rides the bus over link 0 and the train over link 1 is a
    transfer at the middle node without needing another map.
    """

    def _mixed_route(self, game_round, player, legs, agent_id=1):
        """A route built from (edge, mode, line) triples, in order.

        `line` is None for a walk or a car segment. This is what `_pt_route`
        cannot do: it gives every segment the same line.
        """
        move, _ = PlayerMove.objects.get_or_create(
            session_round=game_round, player=player, action="route_submit"
        )
        route = AgentRoute.objects.create(
            player_move=move,
            agent_id=agent_id,
            transport_mode="public",
            total_distance_m=1000.0 * len(legs),
            estimated_time_min=5.0,
        )
        for order, (edge, mode, line) in enumerate(legs, start=1):
            RouteSegment.objects.create(
                agent_route=route,
                order=order,
                edge=edge,
                mode=mode,
                pt_line_id=line.pk if line is not None else None,
            )
        return route

    def _player(self, session, name="Rider"):
        return Player.objects.create(name=name, game=session)

    def _round(self, session):
        return GameRound.objects.create(game=session, round_number=1)

    def _waits(self, simulator):
        """Every rider's measured wait, for the people who took a PT leg."""
        return [
            v.wait_min
            for v in simulator.vehicles.values()
            if getattr(v, "bought_ticket", False)
        ]

    def _broken_line_map(self):
        """A line whose edges do not connect — the shape S5/S7/M48 have.

        Three links in a row, and a bus line over the FIRST and the THIRD.
        node_chain cannot walk that, so _register_pt_line trims the line to
        the part that does connect: stops [N1, N2], one usable edge. A route
        riding the line over the third link boards at N2, which no vehicle of
        the line ever stands at.

        This is the only fixture left in which somebody genuinely cannot
        travel, now that a full bus is a wait. Both the give-up tests and
        PTRealisedShareTests use it.
        """
        game_map = GameMap.objects.create(
            name="Broken line", x_dim=100, y_dim=100, scale=100.0
        )
        version = MapVersion.objects.create(
            game_map=game_map, name="Base", base_version=True
        )
        nodes = []
        for i in range(4):
            node = Node.objects.create(
                game_map=game_map, name=f"B{i}", x_position=i * 10, y_position=0
            )
            node.map_versions.add(version)
            nodes.append(node)
        edges = [
            _street(game_map, version, nodes[i], nodes[i + 1], lanes=2)
            for i in range(3)
        ]
        bus_line = BusLine.objects.create(
            game_map=game_map, name="M48", intervall=10, bus_capacity=85
        )
        bus_line.map_versions.add(version)
        for order, edge in enumerate([edges[0], edges[2]]):
            BusLineEdge.objects.create(
                bus_line=bus_line,
                street_edge=edge.streetedge_set.first(),
                order=order,
            ).map_versions.add(version)
        return game_map, version, edges, bus_line, nodes

    def _broken_line_round(self, people=1000):
        """A round whose only agent rides the unreachable part of the line."""
        game_map, version, edges, bus_line, _nodes = self._broken_line_map()
        session = _session(
            self.user, game_map, people_per_agent=people, std_dev=10
        )
        session.active_map_version = version
        session.save(update_fields=["active_map_version"])
        game_round = self._round(session)
        player = self._player(session)
        route = self._pt_route(
            game_round, player, [edges[2]], "bus", bus_line, agent_id=1
        )
        return game_round, route, bus_line


class NodeChainTests(TestCase):
    """The walk that turns a bag of edges into a list of places.

    It already exists once, in `maps/serializer._stops_in_travel_order`, and
    the engine needs the identical answer to run a line stop by stop. Two
    copies of a walk this subtle is the drift this guide collapses.
    """

    def test_a_forward_chain_is_its_own_node_list(self):
        from sim import node_chain

        self.assertEqual(node_chain([(1, 2), (2, 3), (3, 4)]), [1, 2, 3, 4])

    def test_every_edge_stored_backwards_still_chains(self):
        """The shipped example maps store every edge of every line reversed.

        This is the case that made every line report two stops and break
        (2026-09-19). The first edge is the hard one: on its own nothing
        orients it, so its direction comes from whichever end the second
        edge touches.
        """
        from sim import node_chain

        self.assertEqual(node_chain([(2, 1), (3, 2), (4, 3)]), [1, 2, 3, 4])

    def test_a_single_edge_is_taken_as_stored(self):
        from sim import node_chain

        self.assertEqual(node_chain([(7, 9)]), [7, 9])

    def test_a_broken_chain_stops_where_it_breaks(self):
        """Shorter than len(edges) + 1 is how a caller spots a broken map."""
        from sim import node_chain

        chain = node_chain([(1, 2), (2, 3), (88, 99)])
        self.assertEqual(chain, [1, 2, 3])
        self.assertLess(len(chain), 4)


class PTLineRunsTheRoadTests(PTBoardingScenarioMixin, TestCase):
    """A line's vehicles drive the line, whoever rides them.

    Today a "PT vehicle" is spawned from an AgentRoute and runs only that
    agent's segments. So two agents on one line each get the line's full
    twelve buses, and a line nobody rides puts nothing on the road at all.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptroad", password="12345")

    def test_a_line_nobody_rides_still_runs_its_vehicles(self):
        """The timetable does not ask whether anyone wants it."""
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        player = self._player(session)
        # A car route, so nothing in this round touches public transport.
        _route(game_round, player, edges, mode="car")

        simulator = self._run(game_round)

        bus_runs = [
            pt for pt in simulator.pt_vehicles if pt.line_key == ("bus", bus_line.pk)
        ]
        self.assertEqual(len(bus_runs), 12)

    def test_the_vehicle_count_is_the_timetables_not_the_demands(self):
        """12 buses at a 10-minute interval over the 120-minute window."""
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        simulator = self._run(game_round)

        bus_runs = [
            pt for pt in simulator.pt_vehicles if pt.line_key == ("bus", bus_line.pk)
        ]
        train_runs = [
            pt
            for pt in simulator.pt_vehicles
            if pt.line_key == ("train", train_line.pk)
        ]
        self.assertEqual(len(bus_runs), 12)
        self.assertEqual(len(train_runs), 24)

    def test_two_agents_on_one_line_get_one_set_of_vehicles(self):
        """The double count, in one assertion.

        `_compute_vehicle_scaling` runs per AgentRoute, so today the M1 both
        agents ride is counted twice — 24 buses for a line that runs 12.
        """
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        one = self._player(session, name="One")
        two = self._player(session, name="Two")
        self._pt_route(game_round, one, edges, "bus", bus_line, agent_id=1)
        self._pt_route(game_round, two, edges, "bus", bus_line, agent_id=2)

        simulator = self._run(game_round)

        bus_runs = [
            pt for pt in simulator.pt_vehicles if pt.line_key == ("bus", bus_line.pk)
        ]
        self.assertEqual(len(bus_runs), 12)

    def test_a_run_covers_the_whole_line_not_one_agents_segments(self):
        """A rider going one stop does not shorten the bus's route."""
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        player = self._player(session)
        # Rides link 0 only — one stop of a two-stop line.
        self._pt_route(game_round, player, edges[:1], "bus", bus_line)

        simulator = self._run(game_round)

        route_key = simulator.line_route_keys[("bus", bus_line.pk)]
        self.assertEqual(len(simulator.route_segments[route_key]), 2)

    def test_a_line_vehicle_is_not_an_agent_result(self):
        """The negative route key keeps buses out of the per-agent numbers."""
        from game.models import AgentSimulationResult

        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        simulator = self._run(game_round)

        self.assertEqual(len(simulator.agent_results), 1)
        self.assertEqual(AgentSimulationResult.objects.count(), 1)
        self.assertTrue(
            all(key < 0 for key in simulator.line_route_keys.values()),
            "a line's own run must not use a key an AgentRoute could have",
        )


class PTBoardingTests(PTBoardingScenarioMixin, TestCase):
    """People get on, and only as many as fit."""

    def setUp(self):
        self.user = User.objects.create_user(username="ptboard", password="12345")

    def test_a_rider_boards_and_arrives(self):
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=20)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(line.boarded, 20)
        self.assertEqual(simulator.agent_results[
            list(simulator.agent_routes)[0]
        ]["not_arrived"], 0)

    def test_a_full_vehicle_refuses_the_surplus(self):
        """Capacity constrains boarding, and a refusal is a wait.

        Five seats a bus against a hundred people queuing: almost everybody is
        turned away at least once. Since `pt-service-period` the line keeps
        running until they are all carried, so the cost of the shortfall lands
        in the time column rather than in a headcount of people who vanished.

        `denied` counts REFUSALS, not people — `line.denied += len(queue)` runs
        on every stop visit, so one person turned away four times is four of
        them. That is why the assertion is above 100 for a hundred people.
        """
        game_map, version, edges, bus_line, train_line = self._pt_map(bus_capacity=5)
        session = self._pt_session(game_map, version, people=100)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertGreater(line.denied, 100)
        self.assertEqual(line.boarded, 100)
        self.assertEqual(line.stranded, 0)

    def test_whoever_is_refused_takes_the_next_one(self):
        """A refusal is a wait, not a dead end, while service is still coming."""
        game_map, version, edges, bus_line, train_line = self._pt_map(bus_capacity=10)
        session = self._pt_session(game_map, version, people=40)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        carrying = [pt for pt in simulator.pt_vehicles
                    if pt.line_key == ("bus", bus_line.pk) and pt.boarded_total]
        self.assertGreater(line.denied, 0, "40 people, 10 seats a bus")
        self.assertGreater(
            len(carrying), 1, "the refused must have caught a later run"
        )

    def test_a_rider_alights_where_its_own_leg_ends(self):
        """Not at the terminus: the leg's node is the rider's, not the line's.

        The route rides link 0 only, so it gets off at the middle node while
        the bus carries on to the end.
        """
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        player = self._player(session)
        route = self._pt_route(game_round, player, edges[:1], "bus", bus_line)

        simulator = self._run(game_round)

        legs = simulator.route_pt_legs[route.pk]
        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(len(legs), 1)
        self.assertEqual(legs[0].board_node, line.stops[0])
        self.assertEqual(legs[0].alight_node, line.stops[1])
        self.assertNotEqual(legs[0].alight_node, line.stops[-1])

    def test_a_rider_walking_to_the_stop_waits_there(self):
        """The interception in _advance_free_running, in one observation.

        A walker that is not taken out of free_running when it reaches its
        stop keeps walking its own route and arrives at work without ever
        taking the bus.
        """
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        player = self._player(session)
        route = self._mixed_route(
            game_round,
            player,
            [(edges[0], "walk", None), (edges[1], "bus", bus_line)],
        )

        simulator = self._run(game_round)

        legs = simulator.route_pt_legs[route.pk]
        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(len(legs), 1)
        self.assertEqual(legs[0].first_index, 1)
        self.assertEqual(legs[0].board_node, line.stops[1])
        self.assertEqual(line.boarded, 10)

    def test_a_transfer_re_queues_and_pays_one_fare(self):
        """Bus over link 0, train over link 1: a change at the middle node.

        One Ticket for the trip, however many times they change — the fare is
        per trip, which is what a Ticket is.
        """
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        player = self._player(session)
        route = self._mixed_route(
            game_round,
            player,
            [(edges[0], "bus", bus_line), (edges[1], "train", train_line)],
        )

        simulator = self._run(game_round)

        legs = simulator.route_pt_legs[route.pk]
        self.assertEqual(len(legs), 2)
        self.assertEqual(legs[0].line_key, ("bus", bus_line.pk))
        self.assertEqual(legs[1].line_key, ("train", train_line.pk))
        self.assertEqual(legs[0].alight_node, legs[1].board_node)
        self.assertEqual(simulator.route_fares.get(route.pk), 10)


class PTWaitTimeTests(PTBoardingScenarioMixin, TestCase):
    """wait_time_min stops being interval / 2 asserted, and starts being read.

    Note what is NOT claimed here. With people arriving uniformly at a stop
    and seats to spare, the MEAN wait really is about interval / 2 — the old
    constant was the right answer to the easy case. What it could never do is
    differ between two people, or rise when the bus is full.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptwait", password="12345")

    def test_the_wait_is_written_at_all(self):
        from game.models import AgentSimulationResult

        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=20)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        self._run(game_round)

        result = AgentSimulationResult.objects.get()
        self.assertGreater(result.wait_time_min, 0.0)

    def test_two_people_do_not_wait_the_same_amount(self):
        """A constant cannot have a spread. A queue can."""
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=40)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        simulator = self._run(game_round)

        waits = self._waits(simulator)
        self.assertGreater(len(waits), 1)
        self.assertGreater(max(waits) - min(waits), 0.5)

    def test_a_full_line_makes_people_wait_longer(self):
        """The mechanism the old constant could not have: capacity.

        Same line, same interval, same people — only the seats differ, and
        interval / 2 would answer identically for both.
        """
        def mean_wait(capacity):
            game_map, version, edges, bus_line, _ = self._pt_map(
                bus_capacity=capacity
            )
            session = self._pt_session(game_map, version, people=60)
            game_round = self._round(session)
            player = self._player(session)
            self._pt_route(game_round, player, edges, "bus", bus_line)
            simulator = self._run(game_round)
            waits = self._waits(simulator)
            return sum(waits) / len(waits) if waits else 0.0

        roomy = mean_wait(85)
        tight = mean_wait(5)
        self.assertGreater(tight, roomy)


class PTTripTimeTests(PTBoardingScenarioMixin, TestCase):
    """The wait is inside the trip time, not added on top of it."""

    def setUp(self):
        self.user = User.objects.create_user(username="pttrip", password="12345")

    def test_the_wait_is_not_added_on_top_of_the_measured_trip(self):
        """Door to door is arrival minus wanted departure. Full stop.

        The clock has been running since the person wanted to leave and the
        standing at the stop happened inside it. The old code added a flat
        interval / 2 to a time that did not contain the wait, and will now be
        adding it to one that does.
        """
        from game.models import AgentSimulationResult

        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=20)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        simulator = self._run(game_round)

        measured = [
            v.arrived_min - v.wants_to_depart_min
            for v in simulator.vehicles.values()
            if v.arrived and v.arrived_min is not None and v.route_pk > 0
        ]
        self.assertTrue(measured)
        expected = sum(measured) / len(measured)

        result = AgentSimulationResult.objects.get()
        self.assertAlmostEqual(result.mean_trip_time_min, expected, places=6)


class PTFullLineIsAWaitTests(PTBoardingScenarioMixin, TestCase):
    """Nobody is left behind for want of a seat; the shortfall is time.

    This class replaces PTStrandedTests, whose three tests asserted that
    capacity strands the surplus. That is exactly what
    `[backend]-pt-service-period.md` deletes (Lukas, 2026-09-25): students
    already have CO2 and cost to argue about, and a count of people who did
    not arrive is a third axis that ranks against neither.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptwait", password="12345")

    def _tiny_bus_round(self):
        """Two seats a bus against a hundred people. 55 runs carry them all."""
        game_map, version, edges, bus_line, _train = self._pt_map(bus_capacity=2)
        session = self._pt_session(game_map, version, people=100)
        game_round = self._round(session)
        player = self._player(session)
        route = self._pt_route(game_round, player, edges, "bus", bus_line)
        return game_round, route, bus_line

    def test_more_people_than_seats_is_a_wait(self):
        """The headline, on the fixture that used to strand three quarters."""
        game_round, route, bus_line = self._tiny_bus_round()

        simulator = self._run(game_round, max_ticks=300)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(line.stranded, 0)
        self.assertEqual(line.boarded, 100)
        self.assertEqual(simulator.agent_results[route.pk]["not_arrived"], 0)

    def test_the_shortfall_shows_up_as_time(self):
        """Where the vanished people went: into the time column.

        Without this the test above is satisfied by a line that teleports
        everybody. Two seats every ten minutes genuinely cannot move a hundred
        people quickly, and the trip time has to say so.
        """
        game_round, route, _bus_line = self._tiny_bus_round()

        simulator = self._run(game_round, max_ticks=300)

        trips = simulator.agent_results[route.pk]["trip_times"]
        self.assertEqual(len(trips), 100)
        self.assertGreater(sum(trips) / len(trips), 120.0)

    def test_the_line_pays_for_every_run_it_put_on(self):
        """55 runs against a 12-run timetable, and all 55 emit."""
        game_round, _route, bus_line = self._tiny_bus_round()

        simulator = self._run(game_round, max_ticks=300)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertGreater(line.vehicles, line.base_vehicles)
        self.assertAlmostEqual(
            line.society_co2_g,
            line.vehicles * line.line_km * 1200.0,
            places=3,
        )


class PTRealisedShareTests(PTBoardingScenarioMixin, TestCase):
    """A line is divided among the people who got on it.

    `[backend]-pt-timetable-and-society.md` divided it among the people who
    SUBMITTED a route over it, because at the time there was no other number
    to use. There is now.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptshare", password="12345")

    def test_person_km_is_what_was_ridden_not_what_was_submitted(self):
        """A line carries what got on it, not what was submitted over it.

        This used to be shown with a 2-seat bus: 100 people submit, 24 places
        exist, so person_km came out far under the submitted 200. Since
        `[backend]-pt-service-period.md` a full bus is a WAIT — the line keeps
        running until all 100 are carried — so capacity no longer separates
        the two figures at all.

        What still separates them is a line whose edges do not connect.
        _register_pt_line trims it to the part that forms a chain, the route's
        board node is not among the stops any vehicle stands at, and a
        thousand people submit a ride that nobody takes. person_km is 0 while
        the submitted figure is 1000 x 1 km.
        """
        from game.simulation import TrafficSimulator

        game_round, route, bus_line = self._broken_line_round(people=1000)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(line.boarded, 0)
        self.assertEqual(line.person_km, 0.0)
        self.assertAlmostEqual(line.person_km, line.boarded * 1.0, places=6)
        # And the society figure stands regardless — it is the map's.
        self.assertGreater(line.society_co2_g, 0.0)

    def test_an_agent_whose_people_never_boarded_carries_none_of_it(self):
        """Nobody pays for a bus they could not get on.

        The train line here has no route over it at all, so its society
        figure stands while no agent carries a gram of it.
        """
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=10)
        game_round = self._round(session)
        player = self._player(session)
        self._pt_route(game_round, player, edges, "bus", bus_line)

        simulator = self._run(game_round)

        train = simulator.pt_lines[("train", train_line.pk)]
        self.assertEqual(train.person_km, 0.0)
        self.assertGreater(train.society_co2_g, 0.0)

    def test_the_shares_still_add_up_to_the_line(self):
        """The identity the whole design rests on, over the boarders."""
        game_map, version, edges, bus_line, train_line = self._pt_map(bus_capacity=10)
        session = self._pt_session(game_map, version, people=40)
        game_round = self._round(session)
        one = self._player(session, name="One")
        two = self._player(session, name="Two")
        route_a = self._pt_route(game_round, one, edges, "bus", bus_line, agent_id=1)
        route_b = self._pt_route(game_round, two, edges, "bus", bus_line, agent_id=2)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        shares = 0.0
        for route_pk in (route_a.pk, route_b.pk):
            person_km = simulator.route_pt_person_km.get(route_pk, {}).get(
                ("bus", bus_line.pk), 0.0
            )
            shares += line.share_of(line.society_co2_g, person_km)
        self.assertAlmostEqual(shares, line.society_co2_g, places=6)


# ---------------------------------------------------------------------------
# Bikes — see `.claude/plans/to-do/[backend]-bike-lane-and-traffic.md`.
#
# Two separate claims, and they are tested separately:
#
#   1. A bike lane takes a car lane, floored at zero, exactly as a bus lane
#      already does. On a one-lane street that closes it to cars — a
#      Fahrradstraße — and that is the trade-off the class votes on.
#   2. A bike queues if and only if it shares space with cars: a street edge
#      with no bike lane. It takes space, it is overtaken, and it filters past
#      a jam because it discharges on a budget of its own.
#
# The named simplifications, both deliberate and both pinned below: car
# congestion does not slow a bike, and a bike does not slow a car. Any
# coupling beyond the shared storage would be a number invented to look right.
# ---------------------------------------------------------------------------


class BikeLaneTakesACarLaneTests(TestCase):
    """`lanes` counts the whole street, the bike lane included.

    Same convention as the bus lane, and for the same reason: under the other
    one every bike-lane version needs two edits that have to agree. Lukas, on
    why a bike lane may close a street outright: "in real life, if you have a
    road with limited space and you want to introduce a bike lane, you have to
    decide — do I take a lane away, or do I take parking away? We are not
    modelling parking. So it is taking space from the car and distributing it
    to the bike. And if that means a road gets closed for the car entirely,
    then this is what it is. People can decide and vote about it."

    On the shipped map that is 54 of 90 street edges.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="radweg", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Bike lane map", 3)

    def _simulator_over(self, edge):
        session = _session(self.user, self.game_map)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Radlerin", game=session)
        _route(game_round, player, [edge], mode="bike")
        return TrafficSimulator(game_round, scale=100.0, seed=17)

    def test_a_bike_lane_takes_one_of_the_streets_lanes(self):
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=2, bike_lane=True,
        )

        simulator = self._simulator_over(edge)

        self.assertEqual(simulator.edge_states[edge.pk].car_lanes, 1)

    def test_a_street_without_a_bike_lane_keeps_all_its_lanes(self):
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=2, bike_lane=False,
        )

        simulator = self._simulator_over(edge)

        self.assertEqual(simulator.edge_states[edge.pk].car_lanes, 2)

    def test_a_bus_lane_and_a_bike_lane_take_two(self):
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=3, bus_lane=True, bike_lane=True,
        )

        simulator = self._simulator_over(edge)

        self.assertEqual(simulator.edge_states[edge.pk].car_lanes, 1)

    def test_a_single_lane_street_with_a_bike_lane_closes_to_cars(self):
        """A Fahrradstraße, and the same machinery as the bus gate."""
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=1, bike_lane=True,
        )

        state = self._simulator_over(edge).edge_states[edge.pk]

        self.assertEqual(state.car_lanes, 0)
        self.assertFalse(state.open_to_cars)

    def test_a_two_lane_street_with_both_reservations_closes_to_cars(self):
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=2, bus_lane=True, bike_lane=True,
        )

        state = self._simulator_over(edge).edge_states[edge.pk]

        self.assertEqual(state.car_lanes, 0)
        self.assertFalse(state.open_to_cars)

    def test_car_lanes_never_go_negative(self):
        """max(0, ...) rather than a bare subtraction: a negative lane count
        would make _capacity_lanes' max(1, ...) silently hand the street back
        to the cars."""
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=1, bus_lane=True, bike_lane=True,
        )

        self.assertEqual(self._simulator_over(edge).edge_states[edge.pk].car_lanes, 0)

    def test_the_street_still_has_usable_capacity_numbers(self):
        """Zero car lanes must not mean zero flow — see _capacity_lanes."""
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=1, bike_lane=True,
        )

        state = self._simulator_over(edge).edge_states[edge.pk]

        self.assertGreater(state.storage_capacity_pcu, 0)
        self.assertGreater(state.flow_per_tick(5), 0)


class BikeQueueingRuleTests(TestCase):
    """A bike queues iff it shares space with cars.

    The rule has to be readable off the link alone, which is why EdgeState
    carries `is_street` and `has_bike_lane` rather than the simulator looking
    the edge back up. Both default to the values that leave every EdgeState
    built by hand in the older tests behaving exactly as it did before.
    """

    def _state(self, is_street, has_bike_lane=False):
        return EdgeState(
            edge_id=1,
            distance_m=1000.0,
            free_flow_speed_kmh=50.0,
            car_lanes=1,
            is_street=is_street,
            has_bike_lane=has_bike_lane,
        )

    def test_a_bike_on_a_plain_street_is_in_traffic(self):
        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertTrue(
            simulator._queues_for_traffic("bike", self._state(is_street=True))
        )

    def test_a_bike_on_a_street_with_a_bike_lane_runs_free(self):
        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertFalse(
            simulator._queues_for_traffic(
                "bike", self._state(is_street=True, has_bike_lane=True)
            )
        )

    def test_a_bike_on_a_path_runs_free(self):
        """No street, so no cars to share with — a park path or a towpath."""
        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertFalse(
            simulator._queues_for_traffic("bike", self._state(is_street=False))
        )

    def test_a_bike_alongside_a_railway_runs_free(self):
        """The S-Bahn-with-a-path case: rail carries no StreetEdge either."""
        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertFalse(
            simulator._queues_for_traffic(
                "bike", self._state(is_street=False, has_bike_lane=True)
            )
        )

    def test_a_walker_never_queues(self):
        """Pedestrians stay outside the queue model deliberately."""
        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertFalse(
            simulator._queues_for_traffic("walk", self._state(is_street=True))
        )

    def test_a_cyclist_takes_less_room_than_a_driver(self):
        from game.simulation import BIKE_PCU

        simulator = TrafficSimulator.__new__(TrafficSimulator)

        self.assertEqual(simulator._pcu_for("bike"), BIKE_PCU)
        self.assertLess(BIKE_PCU, 1.0)


class BikeInTrafficTests(TestCase):
    """What a bike in mixed traffic does to the street, and the street to it.

    `departure_std_dev_min=0` on purpose: every person leaves at the same
    minute, so the two runs a test compares differ in nothing but the traffic
    that is there. A non-zero spread draws from the simulator's own rng, and
    adding a second route would shift every later draw — the trip times would
    then differ for a reason that has nothing to do with the claim.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="verkehr", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Bike traffic map", 2)

    def _run(self, modes, bike_lane=False, people=300):
        from game.tests._helpers import muted

        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=1, bike_lane=bike_lane,
        )
        session = _session(self.user, self.game_map, people_per_agent=people, std_dev=0)
        game_round = GameRound.objects.create(game=session, round_number=1)
        routes = {}
        for index, mode in enumerate(modes):
            player = Player.objects.create(name=f"Agent {index}", game=session)
            routes[mode] = _route(game_round, player, [edge], mode=mode)
        simulator = TrafficSimulator(game_round, scale=100.0, seed=4711)
        with muted():
            simulator.run_simulation(max_ticks=200)
        return simulator, edge, routes

    def _trip_times(self, simulator, route):
        return simulator.agent_results[route.pk]["trip_times"]

    def test_bikes_occupy_the_street(self):
        """The trade-off a bike lane buys the cars, and it arrives for free.

        Cyclists really do take storage on a mixed street, so taking them off
        it visibly frees space. Today they consume none: `peak_occupancy_pcu`
        on a bike-only street reads 0.0.
        """
        simulator, edge, _ = self._run(["bike"])

        self.assertGreater(simulator.edge_states[edge.pk].peak_occupancy_pcu, 0.0)

    def test_bikes_on_a_bike_lane_occupy_nothing(self):
        """Separated infrastructure is not the carriageway."""
        simulator, edge, _ = self._run(["bike"], bike_lane=True)

        self.assertEqual(simulator.edge_states[edge.pk].peak_occupancy_pcu, 0.0)

    def test_a_bike_in_traffic_is_delayed_by_other_bikes(self):
        """300 cyclists leaving at the same minute are a queue of cyclists.

        Today every bike trip is exactly its free-flow estimate — mean, min
        and max identical, delay 0.00 — on every edge of every map.
        """
        simulator, _, routes = self._run(["bike"])

        delays = simulator.agent_results[routes["bike"].pk]["delays"]

        self.assertGreater(max(delays), 0.0)

    def test_a_bike_on_a_bike_lane_is_never_delayed(self):
        simulator, _, routes = self._run(["bike"], bike_lane=True)

        delays = simulator.agent_results[routes["bike"].pk]["delays"]

        self.assertEqual(max(delays), 0.0)

    def test_the_car_jam_does_not_slow_the_bike(self):
        """The named simplification, stated as a test so it stays deliberate.

        A bike in mixed traffic is delayed by other bikes and by nothing else.
        The driver-side argument for a bike lane comes through the shared
        storage, not through a made-up coupling.
        """
        alone, _, alone_routes = self._run(["bike"])
        with_cars, _, mixed_routes = self._run(["bike", "car"])

        self.assertEqual(
            self._trip_times(with_cars, mixed_routes["bike"]),
            self._trip_times(alone, alone_routes["bike"]),
        )

    def test_a_car_is_never_stuck_behind_a_bike(self):
        """The other half of the same simplification.

        A cyclist on a one-lane street really would hold a driver up. The
        model says they do not: cars and bikes are separate lines on the link
        and each discharges on its own budget, so a car passes a bike without
        any code for overtaking. Green today because bikes are not on the link
        at all — it is here to stay green, and it is exactly what breaks if
        the bikes are ever put into `queue` instead of `bike_queue`.

        Deliberately uncongested: what is being pinned is that the bike is not
        in the way, not that the street is empty.
        """
        simulator, _, routes = self._run(["car", "bike"], people=30)

        delays = simulator.agent_results[routes["car"].pk]["delays"]

        # Zero to floating-point noise, not to the bit: a delay is a trip time
        # minus a free-flow time, and both are sums of divisions.
        self.assertAlmostEqual(max(delays), 0.0, places=6)

    def test_bikes_and_cars_share_the_links_storage(self):
        """The driver-side argument for a bike lane, and the only coupling.

        Cyclists take room on a mixed street whether or not they slow anyone,
        so taking them off it frees storage the cars can use — which is the
        trade-off the class is voting on. It is also the *only* way bikes
        reach the cars at all: there is no term anywhere that makes a queue of
        cars slower because there are bicycles in it.

        Thirty of each on 300 m of one lane: 30.0 PCU of cars alone, 36.0 with
        the bikes, against 39.9 of storage — so both runs fit and the
        difference is the bikes rather than a spillback.
        """
        alone, cars_only_edge, _ = self._run(["car"], people=30)
        with_bikes, mixed_edge, _ = self._run(["car", "bike"], people=30)

        self.assertGreater(
            with_bikes.edge_states[mixed_edge.pk].peak_occupancy_pcu,
            alone.edge_states[cars_only_edge.pk].peak_occupancy_pcu,
        )

    def test_a_street_full_of_cars_still_admits_a_bike(self):
        """A physically full street does not turn a cyclist away; they squeeze
        in. So a bike skips the storage check while still adding its PCU, and
        none of the 300 are left standing at the front door."""
        simulator, _, routes = self._run(["bike", "car"])

        results = simulator.agent_results[routes["bike"].pk]

        self.assertEqual(results["not_arrived"], 0)
        self.assertEqual(len(results["trip_times"]), 300)

    def test_bikes_do_not_move_the_streets_observed_speed(self):
        """`mean_speed_kmh` stays cars-only, the way it already is for walkers.

        It feeds the CO2 factor and the route preview, so a bike crossing at
        20 km/h must not report a 50 street as congested.
        """
        simulator, edge, _ = self._run(["bike"])

        state = simulator.edge_states[edge.pk]

        self.assertEqual(state.traversal_count, 0)
        self.assertEqual(state.mean_speed_kmh, state.free_flow_speed_kmh)


class DriverSpeedIsDrawnOncePerPersonTests(TestCase):
    """A desired speed belongs to the traveller, not to the attempt.

    `draw_driver_speed_factor` is documented as one draw per vehicle carried
    for the whole trip — redrawing per link would average a long route back to
    the mean and the dial would do nothing. It was drawn in `_spawn_vehicles`,
    which is retried: a traveller whose first street is full stays on the
    waiting list and is rebuilt from scratch next tick, with a fresh draw.
    Someone held at the door for three ticks was dealt three desired speeds
    and kept the last.

    The expensive half is not the unfairness, it is that the round's random
    stream then depends on the pattern of spawn refusals. Any change touching
    link occupancy re-rolls every later driver, so the result moves by far
    more than the change itself — and in an arbitrary direction. Measured on
    the golden-master scenario while adding bikes to traffic: the mechanism is
    worth +0.2 min of car delay, and the re-rolled drivers turned that into
    -2.0 min. A golden master cannot do its job against that.

    The draw moves to where the departures are built: once per person, carried
    through every retry.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="einmal", password="12345")

    def _run(self, people, lanes):
        from unittest import mock

        from game.tests._helpers import muted

        game_map, version, nodes = _grid_map(f"Draws {people} {lanes}", 3)
        edges = [
            _street(game_map, version, nodes[0], nodes[1], lanes=lanes),
            _street(game_map, version, nodes[1], nodes[2], lanes=lanes),
        ]
        session = _session(self.user, game_map, people_per_agent=people, std_dev=1)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Fahrerin", game=session)
        _route(game_round, player, edges)

        simulator = TrafficSimulator(game_round, scale=100.0, seed=2026)
        with mock.patch(
            "game.simulation.draw_driver_speed_factor",
            side_effect=draw_driver_speed_factor,
        ) as draws:
            with muted():
                simulator.run_simulation(max_ticks=400)
        return simulator, draws.call_count

    def test_a_crowd_held_at_the_door_is_still_drawn_for_once_each(self):
        """900 cars onto one lane: the door turns most of them away for ticks.

        Storage on 300 m of one lane is 39.9 vehicles, so all but forty are
        refused on the first tick and come back on the next.
        """
        _, draws = self._run(people=900, lanes=1)

        self.assertEqual(draws, 900)

    def test_nobody_is_drawn_for_twice_when_nobody_is_refused(self):
        """The control. Without it the test above would also pass if the
        draw moved somewhere it never runs at all."""
        _, draws = self._run(people=20, lanes=3)

        self.assertEqual(draws, 20)

    def test_everyone_still_gets_a_speed_of_their_own(self):
        """Moving the draw must not quietly turn the dial off."""
        simulator, _ = self._run(people=900, lanes=1)

        factors = {v.speed_factor for v in simulator.vehicles.values()}

        self.assertGreater(len(factors), 100)


# ---------------------------------------------------------------------------
# The line runs as long as people need it — `[backend]-pt-service-period.md`
#
# Same rule as the PT block above: every new symbol is imported inside the
# test that needs it, so a missing name cannot raise at module level and
# silently delete the rest of this file from the run.
# ---------------------------------------------------------------------------


class PTServicePeriodTests(PTBoardingScenarioMixin, TestCase):
    """A line runs as long as people need it, and nobody is left behind.

    Two halves, and the second is what makes the first safe:

    - There is NO PT service period. A line dispatches while somebody still
      needs it, bounded only by max_ticks — the same clock the road runs on.
      run_simulation(max_ticks=200) at tick_duration_min=5 gives the street a
      thousand simulated minutes; the line used to get a hundred and twenty.
      A full bus is a WAIT, and the wait is already inside the trip time,
      because _record_arrivals measures from wants_to_depart_min.
    - The ONE case that cannot be waited out is a stop the line does not
      serve, because its edges do not connect. That is a map-data defect, and
      it has to be given up on rather than waited for — otherwise the line
      dispatches to the end of the clock and pays society CO2 for every run.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptservice", password="12345")

    def _busy_round(self, people=1000, std_dev=10, capacity=85, interval=10, agents=1):
        game_map, version, edges, bus_line, _train = self._pt_map(
            bus_capacity=capacity, bus_interval=interval
        )
        session = _session(
            self.user, game_map, people_per_agent=people, std_dev=std_dev
        )
        session.active_map_version = version
        session.save(update_fields=["active_map_version"])
        game_round = self._round(session)
        player = self._player(session)
        routes = [
            self._pt_route(game_round, player, edges, "bus", bus_line, agent_id=a)
            for a in range(1, agents + 1)
        ]
        return game_round, routes, bus_line

    # -- the floor: a line is a property of the map ------------------------

    def test_a_line_nobody_rides_runs_exactly_its_timetable(self):
        """The property the base_vehicles split exists to protect.

        Demand may buy EXTRA runs; it may never buy fewer than the timetable,
        and a line nobody rides must cost exactly what the map says it costs.
        12 runs x 2 km x 1200 g = 28.8 kg, unchanged from
        `pt-timetable-and-society`.
        """
        game_map, version, edges, bus_line, _train = self._pt_map()
        session = self._pt_session(game_map, version, people=100)
        game_round = self._round(session)
        player = self._player(session)
        _route(game_round, player, edges, mode="car", agent_id=1)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(line.base_vehicles, 12)
        self.assertEqual(line.vehicles, 12)
        self.assertAlmostEqual(line.society_co2_g, 28_800.0, places=3)

    def test_a_round_nobody_rides_does_not_run_to_the_end_of_the_clock(self):
        """CONTROL — the regression this design most easily causes.

        Runs are pre-generated to the whole clock and cancelled when nobody
        needs them. If a cancelled run were DEFERRED rather than dropped from
        self.waiting, the tick loop would stay alive until its departure
        minute and every round with a line on the map would burn the full
        budget. This passes on `main` and must keep passing.
        """
        game_map, version, edges, _bus, _train = self._pt_map()
        session = self._pt_session(game_map, version, people=20)
        game_round = self._round(session)
        player = self._player(session)
        _route(game_round, player, edges, mode="car", agent_id=1)

        simulator = self._run(game_round, max_ticks=300)

        self.assertLess(simulator.current_tick, 60)

    # -- no cap ------------------------------------------------------------

    def test_the_peak_gets_the_extra_runs_it_needs(self):
        """12 timetabled runs cannot move 1000 people; 17 can.

        Five of the twelve pass the stop before the peak and carry almost
        nobody — 12 x 85 = 1020 nominal seats moved 615 people on `main`. That
        part is real and stays. What was wrong is that there was no 09:10 bus.
        """
        game_round, routes, bus_line = self._busy_round()

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(line.base_vehicles, 12)
        self.assertGreater(line.vehicles, 12)
        self.assertEqual(line.boarded, 1000)

    def test_a_full_line_is_a_wait_not_a_dead_end(self):
        """THE HEADLINE. 385 of 1000 vanish on `main`; none should.

        Two agents, 2000 people against 85 seats every ten minutes: the capped
        design stranded 342 of them. Here the line puts on 29 runs and carries
        everybody.
        """
        game_round, routes, bus_line = self._busy_round(agents=2)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(line.stranded, 0)
        self.assertEqual(line.boarded, 2000)
        for route in routes:
            self.assertEqual(simulator.agent_results[route.pk]["not_arrived"], 0)

    def test_the_wait_shows_up_in_the_trip_time(self):
        """The currency claim: a refused rider pays in minutes.

        The clock starts at wants_to_depart_min, so standing at the stop is
        already inside the trip time and needs no new field. Two agents of a
        thousand on an 85-seat line average over an hour and a half; the same
        line carrying a single agent that fits averages well under one.
        """
        crowded_round, crowded_routes, _line = self._busy_round(agents=2)
        roomy_round, roomy_routes, _line2 = self._busy_round(capacity=1000)

        crowded = self._run(crowded_round)
        roomy = self._run(roomy_round)

        crowded_trips = [
            x
            for route in crowded_routes
            for x in crowded.agent_results[route.pk]["trip_times"]
        ]
        roomy_trips = roomy.agent_results[roomy_routes[0].pk]["trip_times"]
        crowded_mean = sum(crowded_trips) / len(crowded_trips)
        roomy_mean = sum(roomy_trips) / len(roomy_trips)

        self.assertGreater(crowded_mean, 60.0)
        self.assertLess(roomy_mean, 20.0)
        self.assertGreater(crowded_mean, roomy_mean * 3)

    def test_a_run_that_leaves_the_depot_is_paid_for(self):
        """The price. Society emissions come off the runs dispatched.

        A line that had to put on five extra buses pays for five extra buses,
        which is what "you needed 17, not 12" has to cost to be worth saying.
        """
        game_round, _routes, bus_line = self._busy_round()

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertGreater(line.society_co2_g, 28_800.0)
        self.assertAlmostEqual(
            line.society_co2_g,
            line.vehicles * line.line_km * 1200.0,
            places=3,
        )

    def test_the_clock_is_the_only_bound(self):
        """"As long as people need it" still ends where the road ends.

        A thousand people against ten seats cannot be carried inside the
        simulation, so the line runs to max_ticks and the shortfall lands in
        not_arrived — the same bucket, with the same arithmetic, as a car
        still on a jammed link. Nobody is `stranded`: that word now means the
        map is broken.
        """
        game_round, routes, bus_line = self._busy_round(capacity=10)

        simulator = self._run(game_round, max_ticks=60)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(simulator.current_tick, 60)
        self.assertEqual(line.stranded, 0)
        self.assertGreater(simulator.agent_results[routes[0].pk]["not_arrived"], 0)
        # And every run it managed is scheduled inside the clock, not past it.
        self.assertLessEqual(line.vehicles, 60 * 5 // line.interval_min + 1)

    def test_a_rider_heading_for_a_transfer_keeps_the_next_line_running(self):
        """The third group in _line_still_wanted, isolated.

        Somebody riding the bus towards a change onto the train is in neither
        of the cheap groups — not standing at a train stop, not still at home.
        Without them the train could cancel the run their route needs while
        they are still on the bus.
        """
        game_map, version, edges, bus_line, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=100)
        game_round = self._round(session)
        player = self._player(session)
        self._mixed_route(
            game_round,
            player,
            [(edges[0], "bus", bus_line), (edges[1], "train", train_line)],
            agent_id=1,
        )

        from game.tests._helpers import muted

        simulator = TrafficSimulator(game_round, scale=100.0, seed=606)
        train_key = ("train", train_line.pk)
        self.assertIn(train_key, simulator.routes_by_line)

        with muted():
            simulator.run_simulation(max_ticks=200)

        train = simulator.pt_lines[train_key]
        self.assertEqual(train.stranded, 0)
        self.assertGreater(train.boarded, 0)

    # -- the one thing that cannot be waited out ---------------------------

    def test_a_stop_the_line_does_not_serve_is_given_up_on(self):
        """The narrowed give-up: map data, not capacity.

        The line's edges do not connect, so _register_pt_line trims it and its
        vehicles never stand at the node this route boards at. No amount of
        extra service helps.
        """
        game_round, route, bus_line = self._broken_line_round(people=1000)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(line.boarded, 0)
        self.assertEqual(line.stranded, 1000)
        self.assertEqual(simulator.agent_results[route.pk]["not_arrived"], 1000)

    def test_a_broken_line_does_not_dispatch_to_the_end_of_the_clock(self):
        """WHY the give-up is kept, and it is not about speed.

        People queued at a stop keep _line_still_wanted true. Without the
        give-up this line would dispatch every run the clock allows and pay
        society CO2 for each: measured, 101 runs and 242 kg over the full 200
        ticks, against 12 runs and 28.8 kg with it. A map-data defect would
        quietly multiply the round's CO2 eightfold.

        The gram figure is pinned now that `line_km` is trimmed to the part
        the vehicles reach: this line breaks after one of its two edges, so it
        drives 1 km and is charged for 1 km. It used to be charged for 2, and
        the assertion was against base_vehicles alone so as not to bless that.
        """
        game_round, _route, bus_line = self._broken_line_round(people=1000)

        simulator = self._run(game_round, max_ticks=200)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        self.assertEqual(line.vehicles, line.base_vehicles)
        self.assertAlmostEqual(
            line.society_co2_g,
            line.base_vehicles * line.line_km * 1200.0,
            places=3,
        )
        self.assertLess(simulator.current_tick, 60)

    def test_a_truncated_line_is_charged_only_for_what_it_drives(self):
        """A line emits over the part of itself its vehicles can reach.

        `line_km` used to be summed over every edge handed to
        _register_pt_line, while the `usable` trim below it only shortened
        `edge_ids` — so a line that breaks after one of its two edges was
        charged society CO2 and cost for both. On the shipped map that is five
        lines (S5, S7, M1, M48, 265 on v1), and `101`/`101 reverse` on
        Berlin_Mitte-West, whose PT emissions were overstated by whatever part
        of them is unreachable.

        The vehicles were always honest: they run to the end of `edge_ids` and
        stop. Only the measurement disagreed with them.
        """
        game_round, _route, bus_line = self._broken_line_round(people=10)

        simulator = self._run(game_round)

        line = simulator.pt_lines[("bus", bus_line.pk)]
        driven = len(line.edge_ids) * 1.0
        self.assertEqual(driven, 1.0)
        self.assertAlmostEqual(line.line_km, driven, places=6)

    def test_somebody_still_standing_when_the_clock_stops_waited(self):
        """The one line kept from the closed `nicht-angekommen`.

        wait_min is credited at boarding, so the people who stood longest —
        still standing when the clock stopped — used to be recorded as having
        waited nothing. The person who waited most contributed zero.
        """
        game_round, routes, _bus_line = self._busy_round(capacity=10)

        simulator = self._run(game_round, max_ticks=40)

        never_boarded = [
            v.wait_min
            for v in simulator.vehicles.values()
            if v.route_pk == routes[0].pk
            and not v.arrived
            and not v.bought_ticket
            and v.reached_stop_min > 0
        ]
        self.assertGreater(len(never_boarded), 0)
        self.assertGreater(max(never_boarded), 0.0)


class ReplaySamplingTests(TestCase):
    """Who the replay follows, and the rule that it costs the round nothing.

    The sample is taken by person index, never by a draw. A draw here would
    come from `self.rng` and re-roll every later driver — the exact failure
    that moved `draw_driver_speed_factor` out of `_spawn_vehicles`, and one
    that would move the result by far more than a recorder is worth. The sharp
    test for it is the generator's own state after the run
    (`test_the_recorder_never_draws_from_the_rng`): if anything in the recorder
    touched it, the two runs end in different places.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="replay", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Replay map", 3)

    def _run(self, people=200, stride=None, lanes=2, seed=4711):
        from game.tests._helpers import muted

        edges = [
            _street(self.game_map, self.version, self.nodes[0], self.nodes[1],
                    lanes=lanes),
            _street(self.game_map, self.version, self.nodes[1], self.nodes[2],
                    lanes=lanes),
        ]
        session = _session(self.user, self.game_map, people_per_agent=people, std_dev=0)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Fahrerin", game=session)
        route = _route(game_round, player, edges, mode="car")
        simulator = TrafficSimulator(game_round, scale=100.0, seed=seed)
        if stride is not None:
            simulator.trace_stride = stride
        with muted():
            simulator.run_simulation(max_ticks=200)
        return simulator, route, edges

    def test_one_dot_stands_for_a_fixed_number_of_people(self):
        """Not a fixed number of dots: the ratio is what a class is told."""
        from game.simulation import REPLAY_PEOPLE_PER_DOT

        simulator, route, _ = self._run(people=200)

        self.assertEqual(simulator.trace_stride, REPLAY_PEOPLE_PER_DOT)
        followed = [
            v
            for vid, v in simulator.vehicles.items()
            if vid in simulator.trace and v.route_pk == route.pk
        ]
        self.assertEqual(len(followed), 200 // REPLAY_PEOPLE_PER_DOT)

    def test_one_dot_is_ten_people(self):
        """Lukas's pick in S25, on measured consequences.

        At fifty, a jam of fifty cars drew as one or two dots, and a third of
        the jam moments on the shipped map showed one dot or none — "only one
        car on the edge, but it still got slower". At ten, a jam is seven to
        twelve dots and practically never fewer than two.
        """
        from game.simulation import REPLAY_PEOPLE_PER_DOT

        self.assertEqual(REPLAY_PEOPLE_PER_DOT, 10)

    def test_the_sample_is_taken_by_person_index(self):
        simulator, route, _ = self._run(people=200, stride=50)

        indices = sorted(
            simulator.vehicles[vid].person_index
            for vid in simulator.trace
            if simulator.vehicles[vid].route_pk == route.pk
        )

        self.assertEqual(indices, [0, 50, 100, 150])

    def test_the_label_is_the_real_ratio_when_a_gruppe_does_not_divide(self):
        """205 people at a stride of 10 are 21 dots, not 20.5.

        Index 0, 10, …, 200 are sampled, so each dot stands for 205 / 21 = 9.76
        people. Writing the stride instead would overstate every crowd drawn
        from the sample — at the old stride of fifty a class of fifteen had 106
        people to a Gruppe, three dots each, and the screen said fifty where it
        was thirty-five.
        """
        simulator, _, _ = self._run(people=205, stride=10)

        replay = simulator.simulation_result.replay

        self.assertEqual(replay["people_per_dot"], round(205 / 21, 2))

    def test_a_gruppe_smaller_than_the_stride_is_one_dot_of_itself(self):
        """Index 0 is always sampled, so seven people are one dot of seven."""
        simulator, _, _ = self._run(people=7, stride=10)

        replay = simulator.simulation_result.replay

        self.assertEqual(replay["people_per_dot"], 7)

    def test_the_recorder_never_draws_from_the_rng(self):
        """Two strides, one seed: the generator must end in the same place.

        Following every person instead of every fiftieth changes how much is
        recorded and nothing else. If this fails, something in the recorder is
        drawing — and every driver after that draw got a different speed.
        """
        few, _, _ = self._run(people=200, stride=50)
        every, _, _ = self._run(people=200, stride=1)

        self.assertEqual(few.rng.getstate(), every.rng.getstate())

    def test_the_recorder_does_not_move_the_result(self):
        """The same claim, read off the numbers a player sees.

        Passes trivially before the recorder exists — it only starts testing
        anything once `trace_stride` is real, which is why the rng-state test
        above is the one to trust while typing.
        """
        few, few_route, _ = self._run(people=200, stride=50)
        every, every_route, _ = self._run(people=200, stride=1)

        self.assertEqual(
            [round(t, 6) for t in few.agent_results[few_route.pk]["trip_times"]],
            [round(t, 6) for t in every.agent_results[every_route.pk]["trip_times"]],
        )


class ReplayLineVehicleTests(PTBoardingScenarioMixin, TestCase):
    """Every line vehicle is followed, whatever the stride.

    There are only a few dozen per round, and a rider's "r" leg has to resolve
    to one — a bus the replay did not record is a passenger floating down the
    street with nothing under them.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="linien", password="12345")

    def _run(self, stride=10_000, capacity=1000, people=100):
        from game.tests._helpers import muted

        game_map, version, edges, bus_line, train_line = self._pt_map(
            bus_capacity=capacity
        )
        session = self._pt_session(game_map, version, people=people)
        game_round = self._round(session)
        player = self._player(session)
        route = self._pt_route(game_round, player, edges, "bus", bus_line)
        simulator = TrafficSimulator(game_round, scale=100.0, seed=99)
        simulator.trace_stride = stride
        with muted():
            simulator.run_simulation(max_ticks=200)
        return simulator, route, bus_line

    def test_every_line_vehicle_is_followed(self):
        simulator, _, _ = self._run()

        line_vehicle_ids = {pt.vehicle_id for pt in simulator.pt_vehicles}

        self.assertTrue(line_vehicle_ids)
        self.assertTrue(line_vehicle_ids <= set(simulator.trace))

    def test_a_line_vehicle_is_followed_even_though_no_person_is(self):
        """The stride is high enough that essentially no passenger is recorded.

        Sampling is by person index, never a draw, and index 0 is always
        caught by the modulo (0 % anything == 0) — a harmless floor of one
        traced person per route, whatever the stride. What this guards is the
        line vehicle itself, which _trace follows unconditionally because
        route_pk < 0 skips the modulo entirely.
        """
        simulator, route, _ = self._run(stride=10_000)

        people = [
            vid
            for vid in simulator.trace
            if simulator.vehicles[vid].route_pk == route.pk
        ]

        self.assertLessEqual(len(people), 1)
        self.assertTrue({pt.vehicle_id for pt in simulator.pt_vehicles})


class ReplayTraceTests(TestCase):
    """The shape of what comes out: legs that join up, and an honest ending."""

    def setUp(self):
        self.user = User.objects.create_user(username="spur", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Trace map", 3)

    def _run(self, people=200, lanes=2, max_ticks=200):
        from game.tests._helpers import muted

        edges = [
            _street(self.game_map, self.version, self.nodes[0], self.nodes[1],
                    lanes=lanes),
            _street(self.game_map, self.version, self.nodes[1], self.nodes[2],
                    lanes=lanes),
        ]
        session = _session(self.user, self.game_map, people_per_agent=people, std_dev=0)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Fahrerin", game=session)
        route = _route(game_round, player, edges, mode="car")
        simulator = TrafficSimulator(game_round, scale=100.0, seed=4711)
        with muted():
            result = simulator.run_simulation(max_ticks=max_ticks)
        result.refresh_from_db()
        return simulator, result.replay, route, edges

    def test_the_payload_says_what_it_is(self):
        from game.simulation import REPLAY_FORMAT_VERSION

        _, replay, _, _ = self._run()

        self.assertEqual(replay["version"], REPLAY_FORMAT_VERSION)
        self.assertEqual(replay["people_per_dot"], 10)
        self.assertEqual(replay["window_min"], 120)
        self.assertGreater(replay["end_min"], 0)
        self.assertTrue(replay["dots"])

    def test_a_dots_legs_are_continuous(self):
        """Entering link N+1 IS leaving link N, so there is never a gap.

        The whole wire format rests on this: one timestamp per event, and the
        frontend interpolates between them. A gap would be a dot that vanishes.
        """
        _, replay, _, _ = self._run()

        for dot in replay["dots"]:
            ends = [leg[3] for leg in dot["legs"][:-1]]
            starts = [leg[2] for leg in dot["legs"][1:]]
            self.assertEqual(ends, starts, dot)

    def test_a_leg_never_ends_before_it_starts(self):
        _, replay, _, _ = self._run()

        for dot in replay["dots"]:
            for leg in dot["legs"]:
                self.assertGreater(leg[3], leg[2], dot)

    def test_an_edge_leg_says_which_way_it_was_entered(self):
        """An edge is stored in either direction, so the dot needs the node.

        Without it the frontend draws half the map's traffic backwards.
        """
        _, replay, _, edges = self._run()

        first = replay["dots"][0]
        edge_legs = [leg for leg in first["legs"] if leg[0] == "e"]

        self.assertEqual(edge_legs[0][1], edges[0].pk)
        self.assertEqual(edge_legs[0][4], self.nodes[0].pk)
        self.assertEqual(edge_legs[1][1], edges[1].pk)
        self.assertEqual(edge_legs[1][4], self.nodes[1].pk)

    def test_a_dot_that_got_there_says_arrived(self):
        _, replay, _, _ = self._run()

        self.assertEqual({dot["end"] for dot in replay["dots"]}, {"arrived"})

    def test_a_round_where_everybody_arrived_says_nobody_is_missing(self):
        _, replay, _, _ = self._run()

        self.assertEqual(replay.get("endings"), {"unfinished": 0, "stranded": 0})

    def test_the_ending_counts_the_people_the_results_count(self):
        """The beat reads the simulator's own count, not the sample.

        The clock stops ten minutes after 2000 people wanted to leave down one
        lane, so most of them are still at their front door. They never became
        vehicles, so the sample has no dot for any of them — counting dots
        would leave them out of exactly the round the sentence is for, and say
        "Alle sind angekommen" if every sampled person had made it.
        """
        simulator, replay, route, _ = self._run(people=2000, lanes=1, max_ticks=14)

        booked = simulator.agent_results[route.pk]["not_arrived"]
        held = [w for w in simulator.waiting if w[1] == route.pk]
        from_dots = sum(
            1 for dot in replay["dots"] if dot["end"] == "unfinished"
        ) * replay["people_per_dot"]

        self.assertTrue(held)
        self.assertEqual(replay.get("endings"), {"unfinished": booked, "stranded": 0})
        self.assertLess(from_dots, booked)

    def test_the_door_queue_is_the_gap_before_the_first_leg(self):
        """The queue no instrument could see before `stau-sichtbar`.

        2000 people leaving in the same minute down one lane cannot all get
        on; the ones held back want to leave before their first leg starts,
        and that difference is what the animation draws as a crowd at home.
        """
        _, replay, _, _ = self._run(people=2000, lanes=1)

        held = [dot for dot in replay["dots"] if dot["legs"][0][2] > dot["wants"]]

        self.assertTrue(held)

    def test_a_dot_carries_the_agent_it_belongs_to(self):
        """So a player can pick their own commuters out of the traffic."""
        _, replay, route, _ = self._run()

        dot = replay["dots"][0]

        self.assertEqual(dot["route"], route.pk)
        self.assertEqual(dot["agent"], route.agent_id)
        self.assertEqual(dot["mode"], "car")
        self.assertIsNone(dot["line"])


class ReplayPTTraceTests(PTBoardingScenarioMixin, TestCase):
    """Standing at a stop, riding a bus, and being left behind by one."""

    def setUp(self):
        self.user = User.objects.create_user(username="fahrgast", password="12345")

    def _run(self, capacity=1000, people=100, max_ticks=200):
        from game.tests._helpers import muted

        game_map, version, edges, bus_line, train_line = self._pt_map(
            bus_capacity=capacity
        )
        session = self._pt_session(game_map, version, people=people)
        game_round = self._round(session)
        player = self._player(session)
        route = self._pt_route(game_round, player, edges, "bus", bus_line)
        simulator = TrafficSimulator(game_round, scale=100.0, seed=99)
        with muted():
            result = simulator.run_simulation(max_ticks=max_ticks)
        result.refresh_from_db()
        return simulator, result.replay, route

    def test_a_rider_stands_at_a_stop_before_it_rides(self):
        _, replay, route = self._run()

        riders = [dot for dot in replay["dots"] if dot["route"] == route.pk]
        kinds = [leg[0] for leg in riders[0]["legs"]]

        self.assertIn("s", kinds)
        self.assertIn("r", kinds)
        self.assertLess(kinds.index("s"), kinds.index("r"))

    def test_a_ride_names_a_vehicle_the_replay_also_carries(self):
        """Otherwise the passenger has nothing under them to be drawn on."""
        _, replay, route = self._run()

        ids = {dot["id"] for dot in replay["dots"]}
        rides = [
            leg[1]
            for dot in replay["dots"]
            if dot["route"] == route.pk
            for leg in dot["legs"]
            if leg[0] == "r"
        ]

        self.assertTrue(rides)
        for vehicle_id in rides:
            self.assertIn(vehicle_id, ids)

    def test_a_line_vehicle_is_a_dot_with_a_name_and_no_agent(self):
        """Named by ITS OWN line — the map also carries a same-departure U1.

        Both the bus (M1) and the train (U1) dispatch their first run at
        minute 0, and the more negative route key (U1's, registered second)
        sorts first in self.waiting, so dots[0] with a line is not reliably
        the bus. Filtering by name is what the test actually claims.
        """
        _, replay, _ = self._run()

        buses = [dot for dot in replay["dots"] if dot["line"] == "M1"]

        self.assertTrue(buses)
        self.assertIsNone(buses[0]["route"])
        self.assertIsNone(buses[0]["agent"])

    def test_whoever_never_got_a_seat_is_marked_stranded(self):
        """The map-data give-up leaves people standing, and the replay has to say so.

        Since `pt-service-period`, `stranded` no longer means a full bus — it
        means the line's edges do not reach a stop a route asks it to serve.
        The two-link map's bus and train lines are fully connected, so a
        merely undersized line (capacity=1) now ends `unfinished`, waiting out
        the clock, not `stranded`. Only the broken-line fixture — a route
        boarding past where the line's edges stop connecting — produces this
        ending; the beat at the end of the animation cannot claim everybody
        arrived while a stop like that is still full of people.
        """
        from game.tests._helpers import muted

        game_round, route, _bus_line = self._broken_line_round()
        simulator = TrafficSimulator(game_round, scale=100.0, seed=99)
        with muted():
            result = simulator.run_simulation(max_ticks=200)
        result.refresh_from_db()

        endings = {
            dot["end"] for dot in result.replay["dots"] if dot["route"] == route.pk
        }

        self.assertIn("stranded", endings)

    def test_the_stranded_count_is_people_not_dots(self):
        """Every stranded person, sampled or not, and nobody counted twice."""
        from game.tests._helpers import muted

        game_round, route, _bus_line = self._broken_line_round()
        simulator = TrafficSimulator(game_round, scale=100.0, seed=99)
        with muted():
            result = simulator.run_simulation(max_ticks=200)
        result.refresh_from_db()

        stranded = sum(
            v.passenger_count
            for v in simulator.vehicles.values()
            if v.route_pk == route.pk and v.stranded
        )
        endings = result.replay.get("endings") or {}

        self.assertGreater(stranded, 0)
        self.assertEqual(endings.get("stranded"), stranded)
        self.assertEqual(
            endings.get("unfinished", 0) + endings.get("stranded", 0),
            simulator.agent_results[route.pk]["not_arrived"],
        )


@override_settings(**TEST_BACKENDS)
class ReplayEndpointTests(TestCase):
    """`api/game/<id>/round/<n>/replay/` — one fetch for the whole animation."""

    def setUp(self):
        self.user = User.objects.create_user(username="wirt", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Endpoint map", 3)

    def _played_round(self, people=4000, simulate=True):
        from game.tests._helpers import muted

        edges = [
            _street(self.game_map, self.version, self.nodes[0], self.nodes[1], lanes=2),
            _street(self.game_map, self.version, self.nodes[1], self.nodes[2], lanes=2),
        ]
        session = _session(self.user, self.game_map, people_per_agent=people, std_dev=0)
        game_round = GameRound.objects.create(game=session, round_number=1)
        player = Player.objects.create(name="Fahrerin", game=session)
        _route(game_round, player, edges, mode="car")
        if simulate:
            with muted():
                TrafficSimulator(game_round, scale=100.0, seed=4711).run_simulation(
                    max_ticks=200
                )
        return session, game_round

    def _url(self, session, round_number=1):
        return f"/api/game/{session.game_id}/round/{round_number}/replay/"

    def test_the_route_resolves_to_the_replay_view(self):
        """Pinned with resolve(), not a status code.

        `game/urls.py` ordering is load-bearing: a literal prefix below the two
        dynamic patterns lands in `GetYourOwnGame` and returns a plausible 403
        instead of a 404. A status-code assertion cannot tell those apart.
        """
        from django.urls import resolve

        match = resolve("/api/game/ABCDEF/round/1/replay/")

        self.assertEqual(match.url_name, "round-replay")

    def test_the_host_gets_the_dots_and_the_street_fill(self):
        session, _ = self._played_round()
        self.client.force_login(self.user)

        response = self.client.get(self._url(session))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["round_number"], 1)
        self.assertEqual(payload["tick_duration_min"], session.tick_duration_min)
        self.assertEqual(payload["people_per_agent"], session.people_per_agent)
        self.assertTrue(payload["replay"]["dots"])
        self.assertTrue(payload["ticks"])

    def test_the_recording_is_compressed_for_a_browser_that_accepts_it(self):
        """The biggest payload in the game, over school wifi, and nginx does not gzip.

        At ten people to a dot the shipped map's recording is ~240 KiB of JSON
        and ~40 KiB compressed. Safe to compress because it carries no secret —
        BREACH needs one in the same body as something the attacker controls.
        """
        import gzip
        import json

        session, _ = self._played_round()
        self.client.force_login(self.user)

        response = self.client.get(self._url(session), HTTP_ACCEPT_ENCODING="gzip")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Content-Encoding"), "gzip")
        payload = json.loads(gzip.decompress(response.content))
        self.assertTrue(payload["replay"]["dots"])

    def test_a_client_that_does_not_ask_for_gzip_gets_plain_json(self):
        session, _ = self._played_round()
        self.client.force_login(self.user)

        response = self.client.get(self._url(session))

        self.assertIsNone(response.get("Content-Encoding"))
        self.assertTrue(response.json()["replay"]["dots"])

    def test_somebody_with_no_access_is_refused(self):
        session, _ = self._played_round()

        response = self.client.get(self._url(session))

        self.assertEqual(response.status_code, 403)

    def test_the_street_fill_arrives_once_per_tick(self):
        """Not once per fifth tick: nine frames for a morning is a chart.

        The ticks come back consecutively from the first one that had anything
        on it, which is what lets the animation step the street fill smoothly.
        """
        session, _ = self._played_round()
        self.client.force_login(self.user)

        ticks = [entry["t"] for entry in self.client.get(self._url(session)).json()["ticks"]]

        self.assertGreater(len(ticks), 9)
        self.assertEqual(ticks, sorted(ticks))
        self.assertEqual(ticks, list(range(ticks[0], ticks[0] + len(ticks))))

    def test_an_edge_row_carries_the_people_still_at_their_front_door(self):
        session, _ = self._played_round()
        self.client.force_login(self.user)

        rows = self.client.get(self._url(session)).json()["ticks"][0]["edges"]

        self.assertEqual(len(rows[0]), 4)

    def test_a_round_recorded_before_this_existed_still_answers(self):
        """An old round keeps every number it ever had; only the dots are gone."""
        session, game_round = self._played_round()
        SimulationResult.objects.filter(game_round=game_round).update(replay=None)
        self.client.force_login(self.user)

        response = self.client.get(self._url(session))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["replay"])

    def test_a_round_that_never_ran_is_a_404(self):
        """The route has to exist first, or this passes against a missing URL.

        Django's own 404 for an unrouted path is indistinguishable from the
        view's 404 for a round with no simulation — so resolve() goes in the
        same test rather than trusting the status code alone.
        """
        from django.urls import resolve

        session, _ = self._played_round(simulate=False)
        resolve(self._url(session))
        self.client.force_login(self.user)

        response = self.client.get(self._url(session))

        self.assertEqual(response.status_code, 404)


@override_settings(**TEST_BACKENDS)
class AlightingIntoFreeRunningTests(PTBoardingScenarioMixin, TestCase):
    """Getting off a train and walking the last block must not kill the round.

    _advance_free_running iterates self.free_running directly. A PT vehicle
    that free-runs — a train always, a bus on a dedicated lane — serves its
    stops from inside that loop, and a rider alighting onto a walk or a cycle
    track is added to the very set being iterated, so Python raises
    "Set changed size during iteration" and the whole simulation dies on the
    first tick.

    A bus in mixed traffic never hit it: it is discharged from the queue
    instead, a different loop, and the rider it sets down is picked up on the
    next tick. That is the behaviour this loop has to match.

    Seen for real on 2026-09-25: two seats, one driving and one on Bus & Bahn,
    and the whole round reported 0 g / 0,00 EUR / 0 min.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="alighting", password="12345")

    def _ride_then_walk(self, mode="train", bus_lane=False):
        """Ride the first link on a line, walk the second one home."""
        game_map, version, edges, bus_line, train_line = self._pt_map()
        if bus_lane:
            street = edges[0].streetedge_set.first()
            street.dedicated_bus_lane = True
            street.lanes = 2
            street.save(update_fields=["dedicated_bus_lane", "lanes"])
        session = self._pt_session(game_map, version, people=100)
        game_round = self._round(session)
        player = self._player(session)
        line = train_line if mode == "train" else bus_line
        route = self._mixed_route(
            game_round,
            player,
            [(edges[0], mode, line), (edges[1], "walk", None)],
        )
        return game_round, route

    def test_a_train_rider_who_walks_the_last_block_arrives(self):
        game_round, route = self._ride_then_walk()

        simulator = self._run(game_round)

        trips = simulator.agent_results[route.pk]["trip_times"]
        self.assertTrue(trips, msg="the walk leg after the train produced no trip")

    def test_the_round_is_not_free(self):
        """The symptom as the class saw it: every figure zero."""
        game_map, version, edges, _bus, train_line = self._pt_map()
        session = self._pt_session(game_map, version, people=100)
        game_round = self._round(session)
        player = self._player(session)
        self._mixed_route(
            game_round,
            player,
            [(edges[0], "train", train_line), (edges[1], "walk", None)],
        )

        from game.tests._helpers import muted

        simulator = TrafficSimulator(game_round, scale=100.0, seed=606)
        with muted():
            result = simulator.run_simulation(max_ticks=300)

        self.assertGreater(
            result.total_co2_g,
            0.0,
            msg="a round with a train line running cannot emit nothing",
        )

    def test_a_bus_on_its_own_lane_sets_its_riders_down_too(self):
        """The same loop, reached the other way: a bus that does not queue."""
        game_round, route = self._ride_then_walk(mode="bus", bus_lane=True)

        simulator = self._run(game_round)

        trips = simulator.agent_results[route.pk]["trip_times"]
        self.assertTrue(trips, msg="the walk leg after the bus produced no trip")

    def test_the_walk_is_timed_from_the_moment_it_got_off(self):
        """Deferring the walk to the next tick must not lengthen the trip.

        arrived_min comes off ready_at_min, which _enter_edge set from the
        alighting time, so which tick picks the walker up cannot move it. The
        train takes 1 km at its line speed and the walk 1 km at walk speed;
        anything near a tick more than that is the loop inventing delay.
        """
        game_round, route = self._ride_then_walk()

        simulator = self._run(game_round)

        trips = simulator.agent_results[route.pk]["trip_times"]
        walk_min = 1.0 / simulator.walk_speed_kmh * 60.0
        self.assertLess(
            min(trips),
            walk_min + simulator.tick_duration_min + 10.0,
            msg="the walk after the train is being charged a whole extra tick",
        )


class PTEmissionFactorTests(SimpleTestCase):
    """The two per-vehicle factors the timetable is charged at.

    They are not free parameters: the timetable runs whether anyone rides or
    not, so on a map with six train lines these two numbers set the floor
    under every round's CO2. On Berlin_Mitte-West that floor was 5 597 kg a
    round, 97 % of it trains, against a shipped budget of 500 kg — which is
    how S2's calibration started.
    """

    def test_a_bus_is_a_diesel_city_bus(self):
        """~40 l/100 km diesel x 2.64 kg CO2/l, the figure that was right."""
        from sim.constants import BUS_EMISSIONS_G_PER_VEHICLE_KM

        self.assertAlmostEqual(BUS_EMISSIONS_G_PER_VEHICLE_KM, 1200.0, places=6)

    def test_a_train_is_an_electric_metro_on_the_grid_mix(self):
        """3500 g/train-km implied 9.6 kWh/train-km — a diesel mainline train.

        A Berlin U- or S-Bahn train draws about 4 kWh per train-km including
        auxiliaries, and the German grid mix was 363 g CO2/kWh in 2024 (UBA).
        4 x 0.363 = 1.45 kg, so 1500 g/train-km. Not the operator's own green
        tariff, deliberately: the grid mix is the conservative figure and it is
        the one a class can check.
        """
        from sim.constants import TRAIN_EMISSIONS_G_PER_VEHICLE_KM

        self.assertAlmostEqual(TRAIN_EMISSIONS_G_PER_VEHICLE_KM, 1500.0, places=6)

    def test_a_train_still_costs_more_per_vehicle_km_than_a_bus(self):
        """The cost side is untouched — only the emission factor moved.

        Worth pinning together: correcting CO2 without cost is exactly what
        makes the two disagree about which mode is expensive, and the fare-vs-
        Vollkosten contrast rests on the cost side being left alone.
        """
        from sim.constants import (
            BUS_COST_PER_VEHICLE_KM,
            TRAIN_COST_PER_VEHICLE_KM,
        )

        self.assertAlmostEqual(BUS_COST_PER_VEHICLE_KM, 4.5, places=6)
        self.assertAlmostEqual(TRAIN_COST_PER_VEHICLE_KM, 12.0, places=6)


class RoundTripTests(TestCase):
    """A commute is there and back, and the evening is a round of its own.

    The evening trip is a second pass over a fresh network, not a second half of
    one long clock: eight hours separate the two peaks, so nothing of the
    morning is still on the road, and a single clock would have kept every line
    dispatching empty through the day while the evening riders waited in the
    list — society CO2 for buses nobody could board.

    One result row per round trip, on the way-to-work route: the time of the way
    home is `mean_return_time_min` (the column was there from the start and
    nothing ever wrote it), and CO2 and cost are both trips'.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="roundtrip", password="12345")
        self.game_map, self.version, self.nodes = _grid_map("Round trip map", 4)
        # Two-way street: every direction is an Edge row of its own, which is
        # also how a one-way street is the absence of one.
        self.there = [
            _street(self.game_map, self.version, self.nodes[i], self.nodes[i + 1])
            for i in range(3)
        ]
        self.back = [
            _street(self.game_map, self.version, self.nodes[i + 1], self.nodes[i])
            for i in reversed(range(3))
        ]
        self.session = _session(self.user, self.game_map, people_per_agent=5)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.player = Player.objects.create(name="Pendler", game=self.session)

    def _run(self, seed=7):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0, seed=seed)
        with muted():
            result = simulator.run_simulation(max_ticks=200)
        return simulator, result

    def _rows(self, result):
        return list(result.agent_results.select_related("agent_route"))

    def test_the_way_home_is_simulated_and_reported_on_the_same_row(self):
        out = _route(self.game_round, self.player, self.there)
        _route(self.game_round, self.player, self.back, direction="home")

        _simulator, result = self._run()

        rows = self._rows(result)
        self.assertEqual([row.agent_route_id for row in rows], [out.pk])
        # 900 m at 50 km/h is about 1.1 min each way.
        self.assertGreater(rows[0].mean_trip_time_min, 0.5)
        self.assertGreater(rows[0].mean_return_time_min, 0.5)
        self.assertLess(rows[0].mean_return_time_min, 5.0)

    def test_a_round_with_no_way_home_reports_none(self):
        _route(self.game_round, self.player, self.there)

        _simulator, result = self._run()

        self.assertEqual(self._rows(result)[0].mean_return_time_min, 0.0)

    def test_the_evening_is_charged_on_top_of_the_morning(self):
        _route(self.game_round, self.player, self.there)
        _simulator, one_way = self._run()

        AgentRoute.objects.all().delete()
        SimulationResult.objects.all().delete()
        _route(self.game_round, self.player, self.there)
        _route(self.game_round, self.player, self.back, direction="home")
        _simulator, both_ways = self._run()

        # The same 900 m, driven the other way — so twice, give or take the
        # speed spread of five drivers.
        self.assertAlmostEqual(
            both_ways.total_co2_g / one_way.total_co2_g, 2.0, delta=0.1
        )
        self.assertAlmostEqual(
            both_ways.total_cost_eur / one_way.total_cost_eur, 2.0, delta=0.1
        )
        row = self._rows(both_ways)[0]
        self.assertAlmostEqual(row.total_co2_g, both_ways.total_co2_g, places=3)

    def test_the_evening_runs_on_a_fresh_network(self):
        """The same streets, driven twice: the morning leaves nothing behind.

        400 cars take a one-lane street in the morning; if the evening started
        on that state the second wave would queue behind the first.
        """
        self.session.people_per_agent = 400
        self.session.save()
        _route(self.game_round, self.player, self.there)
        _route(self.game_round, self.player, self.there, direction="home")

        simulator, result = self._run()

        row = self._rows(result)[0]
        self.assertAlmostEqual(
            row.mean_return_time_min, row.mean_trip_time_min,
            delta=0.5 * row.mean_trip_time_min,
        )
        self.assertEqual(
            simulator.home_pass.edge_states[self.there[0].pk].traversal_count, 400
        )

    def test_the_street_speeds_come_from_both_directions(self):
        _route(self.game_round, self.player, self.there)
        _route(self.game_round, self.player, self.back, direction="home")

        _simulator, _result = self._run()

        from maps.models import StreetPerRound

        driven = set(
            StreetPerRound.objects.filter(game_round=self.game_round).values_list(
                "edge__edge_id", flat=True
            )
        )
        self.assertEqual(driven, {e.pk for e in self.there + self.back})


class RoundTripPTTests(PTScenarioMixin, TestCase):
    """The timetable runs in the evening too, and the society pays for it twice.

    The fixture's lines only run one way, which is the New York case a circle
    line is: the way home is the same line again. Both passes board their own
    people on their own network, and the network's CO2 is the two timetables
    added — which is why the round's budget doubles with the trip, instead of
    the people being halved.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="rtpt", password="12345")
        self.game_map, self.version, self.edges, self.bus, _train = self._pt_map(
            "Round trip PT"
        )
        self.session = self._pt_session(self.game_map, self.version, people=100)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.player = Player.objects.create(name="Fahrgast", game=self.session)

    def _home_ride(self):
        return self._pt_route(
            self.game_round,
            self.player,
            self.edges,
            "bus",
            self.bus,
            direction="home",
        )

    def test_the_timetable_is_charged_for_both_trips(self):
        self._pt_route(self.game_round, self.player, self.edges, "bus", self.bus)
        one_way = self._run(self.game_round).simulation_result

        AgentRoute.objects.all().delete()
        SimulationResult.objects.all().delete()
        self._pt_route(self.game_round, self.player, self.edges, "bus", self.bus)
        self._home_ride()
        both = self._run(self.game_round).simulation_result

        self.assertGreater(one_way.network_co2_g, 0)
        self.assertAlmostEqual(
            both.network_co2_g / one_way.network_co2_g, 2.0, places=6
        )
        self.assertAlmostEqual(
            both.total_co2_g / one_way.total_co2_g, 2.0, delta=0.01
        )

    def test_the_evening_riders_board_in_the_evening(self):
        self._pt_route(self.game_round, self.player, self.edges, "bus", self.bus)
        self._home_ride()

        simulator = self._run(self.game_round)

        row = simulator.simulation_result.agent_results.get()
        self.assertGreater(row.mean_trip_time_min, 0)
        self.assertGreater(row.mean_return_time_min, 0)
        self.assertEqual(
            sum(line.boarded for line in simulator.home_pass.pt_lines.values()),
            100,
        )
        # Two Tickets' worth: one per person per trip.
        self.assertAlmostEqual(row.mean_paid_eur, 2 * 1.30, places=6)


class ReplayWayHomeTests(RoundTripTests):
    """The replay carries both passes, the evening on the same screen clock.

    The home pass runs on a simulator of its own with a clock that starts at 0
    and vehicle ids that start at 0, so merging it means moving both: its
    minutes by `max_ticks * tick_duration_min` (the same offset its street
    snapshots already carry) and its ids past the morning's, `"r"` legs
    included, because they name a line vehicle by id. Inherits the fixture;
    the inherited tests run again, which is cheap.
    """

    def _replay(self, both_ways=True, max_ticks=200):
        from game.tests._helpers import muted

        _route(self.game_round, self.player, self.there)
        if both_ways:
            _route(self.game_round, self.player, self.back, direction="home")
        simulator = TrafficSimulator(self.game_round, scale=100.0, seed=7)
        with muted():
            result = simulator.run_simulation(max_ticks=max_ticks)
        result.refresh_from_db()
        return simulator, result.replay

    def test_the_format_says_the_evening_is_in_it(self):
        from game.simulation import REPLAY_FORMAT_VERSION

        _, replay = self._replay()

        self.assertEqual(REPLAY_FORMAT_VERSION, 2)
        self.assertEqual(replay["version"], 2)

    def test_both_passes_are_dots(self):
        _, replay = self._replay()

        passes = {dot["pass"] for dot in replay["dots"]}

        self.assertEqual(passes, {"out", "home"})

    def test_a_round_without_a_way_home_has_morning_dots_only(self):
        _, replay = self._replay(both_ways=False)

        self.assertEqual({dot["pass"] for dot in replay["dots"]}, {"out"})
        self.assertIsNone(replay["home_start_min"])

    def test_the_evening_starts_where_the_street_snapshots_say(self):
        simulator, replay = self._replay(max_ticks=200)

        offset = 200 * simulator.tick_duration_min
        self.assertEqual(replay["home_start_min"], offset)
        home = [d for d in replay["dots"] if d["pass"] == "home"]
        out = [d for d in replay["dots"] if d["pass"] == "out"]
        self.assertGreaterEqual(min(d["legs"][0][2] for d in home), offset)
        self.assertLess(max(d["legs"][-1][3] for d in out), offset)
        self.assertGreaterEqual(replay["end_min"], max(d["legs"][-1][3] for d in home))

    def test_the_evening_wants_are_on_the_same_clock(self):
        simulator, replay = self._replay(max_ticks=200)

        offset = 200 * simulator.tick_duration_min
        for dot in replay["dots"]:
            if dot["pass"] == "home":
                self.assertGreaterEqual(dot["wants"], offset)

    def test_no_two_dots_share_an_id(self):
        _, replay = self._replay()

        ids = [dot["id"] for dot in replay["dots"]]

        self.assertEqual(len(ids), len(set(ids)))

    def test_the_evening_dots_cross_the_way_back(self):
        _, replay = self._replay()

        home = [d for d in replay["dots"] if d["pass"] == "home"]
        back_edges = {edge.pk for edge in self.back}
        self.assertTrue(home)
        for dot in home:
            self.assertTrue({leg[1] for leg in dot["legs"]} <= back_edges)

    def test_endings_count_both_passes(self):
        simulator, replay = self._replay()

        home = simulator.home_pass
        self.assertEqual(
            replay["endings"]["unfinished"],
            simulator.non_arrivals["unfinished"] + home.non_arrivals["unfinished"],
        )


class EverybodyGetsHomeTests(TestCase):
    """A pass runs until everybody is home; the clock is only a guard (F2d).

    Lukas, 2026-10-02: "we should not strand people". A pass used to stop at
    max_ticks=200 whatever was still on the road, and since a forced release
    frees one car per link per DEADLOCK_TICKS a genuine lock can need far
    longer — the ring below needs ~680 ticks. Measured on the shipped map, no
    round came near 200 (worst 153 of 200 at four times the demand on one-lane
    streets), but a cut-off that does not bite on one map is not a guarantee.
    So run_simulation's default is a guard set well above anything a round
    needs, game/signals.py calls it without a limit of its own, and a pass
    that does hit the guard is logged as the bug it is.

    The fixture is DeadlockEscapeTests' ring, with a way home added so the
    evening's place on the round's clock can be checked behind a long morning.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="everybody", password="12345")
        self.game_map, self.version, self.nodes = _grid_map(
            "Everybody map", 3, step_units=1.0
        )
        self.first = _street(self.game_map, self.version, self.nodes[0], self.nodes[1])
        self.second = _street(self.game_map, self.version, self.nodes[1], self.nodes[2])
        self.session = _session(self.user, self.game_map, people_per_agent=300, std_dev=1)
        self.game_round = GameRound.objects.create(game=self.session, round_number=1)
        self.anna = Player.objects.create(name="Anna", game=self.session)
        self.ben = Player.objects.create(name="Ben", game=self.session)
        self.route_a = _route(self.game_round, self.anna, [self.first, self.second], agent_id=1)
        self.route_b = _route(self.game_round, self.ben, [self.second, self.first], agent_id=2)

    def _run(self, **kwargs):
        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0, seed=11)
        with muted():
            simulator.run_simulation(**kwargs)
        return simulator

    def test_a_locked_pass_runs_past_the_old_clock_until_everybody_is_home(self):
        simulator = self._run()

        self.assertGreater(
            simulator.current_tick,
            200,
            "the ring finished inside the old clock, so it proves nothing here",
        )
        for route in (self.route_a, self.route_b):
            self.assertEqual(
                simulator.agent_results[route.pk]["not_arrived"],
                0,
                "the default clock left people on the road",
            )
        self.assertEqual(simulator.non_arrivals["unfinished"], 0)

    def test_a_pass_stopped_by_the_guard_is_logged_as_a_bug(self):
        """The guard is not a game rule. Hitting it means the model is broken."""
        simulator = TrafficSimulator(self.game_round, scale=100.0, seed=11)
        # assertLogs takes the logger over, so the expected noise stays in it.
        with self.assertLogs("game.simulation", "ERROR") as log:
            simulator.run_simulation(max_ticks=50)

        self.assertTrue(
            any("guard" in line and "not home" in line for line in log.output),
            log.output,
        )

    def test_the_evening_starts_after_a_long_morning(self):
        """The replay's evening keeps its 1000 minutes unless the morning ran past.

        Both passes share one axis — the evening's street snapshots and dots
        are moved by `tick_offset` — so an evening that began before the
        morning ended would draw the two on top of each other.
        """
        _route(self.game_round, self.anna, [self.first], agent_id=1, direction="home")

        simulator = self._run()

        morning_end = simulator.current_tick
        home = simulator.home_pass
        self.assertGreater(morning_end, 200)
        self.assertEqual(home.tick_offset, morning_end + 1)
        simulator.simulation_result.refresh_from_db()
        replay = simulator.simulation_result.replay
        self.assertEqual(replay["home_start_min"], (morning_end + 1) * 5)
        out_dots = [d for d in replay["dots"] if d["pass"] == "out"]
        home_dots = [d for d in replay["dots"] if d["pass"] == "home"]
        self.assertLessEqual(
            max(d["legs"][-1][3] for d in out_dots), replay["home_start_min"]
        )
        self.assertGreaterEqual(
            min(d["legs"][0][2] for d in home_dots), replay["home_start_min"]
        )


class EveningStaysAtItsHourTests(RoundTripTests):
    """CONTROL: a round that ends on time keeps the evening at 1000 minutes.

    Raising the default clock to a guard must not move the evening with it.
    The offset used to BE max_ticks; with a guard of a thousand ticks that
    would put every evening at minute 5000 and leave the replay a four-day
    lunch break. Inherits the round-trip fixture; its tests run again, which
    is cheap.
    """

    def test_the_evening_starts_at_minute_1000_on_the_default_clock(self):
        _route(self.game_round, self.player, self.there)
        _route(self.game_round, self.player, self.back, direction="home")

        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0, seed=7)
        with muted():
            result = simulator.run_simulation()
        result.refresh_from_db()

        self.assertEqual(simulator.home_pass.tick_offset, 200)
        self.assertEqual(result.replay["home_start_min"], 1000)

    def test_progress_runs_over_both_passes_to_a_hundred(self):
        """The bar used to be tick / max_ticks, which means nothing once a pass
        has no fixed length: with a guard of a thousand it would sit at 2 %."""
        _route(self.game_round, self.player, self.there)
        _route(self.game_round, self.player, self.back, direction="home")

        from game.tests._helpers import muted

        simulator = TrafficSimulator(self.game_round, scale=100.0, seed=7)
        seen = []
        with muted():
            simulator.run_simulation(
                on_progress=lambda _tick, _total: seen.append(simulator.progress_percent())
            )

        self.assertEqual(seen, sorted(seen), "progress went backwards")
        self.assertLess(seen[0], 50)
        self.assertIn(50, seen, "the way to work is half the round")
        self.assertEqual(seen[-1], 100)



class LinesDriveTheirOwnWayTests(PTBoardingScenarioMixin, TestCase):
    """A line drives the link that goes ITS way, whichever way the map drew it.

    Each direction of a street is its own link with its own queue (F2a), and a
    line vehicle queues on the link its chain row names. The editor lets a line
    be drawn on either direction — node_chain reads the travel order from the
    nodes — and the shipped map's bus `100` eastbound named the westbound links
    for five of its seven streets. On the way home it waited among the cars
    going home, and at the front wanted the link those cars were coming from:
    two full links waiting on each other, which only the deadlock escape breaks.
    With lines running past the timetable that never cleared (F2d).

    The fixture is a corridor N0 - N1 - N2, 1 km a link, drawn eastbound and
    the lines drawn on the westbound links.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ownway", password="12345")

    def _corridor(self, east=True, lanes=1):
        game_map, version, nodes = _grid_map("Corridor", 3, step_units=10.0)
        west = [
            _street(game_map, version, nodes[1], nodes[0], lanes=lanes),
            _street(game_map, version, nodes[2], nodes[1], lanes=lanes),
        ]
        east_edges = []
        if east:
            east_edges = [
                _street(game_map, version, nodes[0], nodes[1], lanes=lanes),
                _street(game_map, version, nodes[1], nodes[2], lanes=lanes),
            ]
        return game_map, version, nodes, east_edges, west

    def _rails(self, game_map, version, pairs):
        rails = []
        for start, end in pairs:
            edge = Edge.objects.create(game_map=game_map, start_node=start, end_node=end)
            edge.map_versions.add(version)
            TrainEdge.objects.create(edge=edge).map_versions.add(version)
            rails.append(edge)
        return rails

    def _bus_line(self, game_map, versions, chains, name="100"):
        """`chains` is {version: [edge, ...]} — the rows each version runs on."""
        line = BusLine.objects.create(game_map=game_map, name=name, intervall=10)
        line.map_versions.add(*versions)
        for version, edges in chains.items():
            for order, edge in enumerate(edges):
                BusLineEdge.objects.create(
                    bus_line=line, street_edge=edge.streetedge_set.first(), order=order
                ).map_versions.add(version)
        return line

    def _train_line(self, game_map, version, edges, name="S1"):
        line = TrainLine.objects.create(game_map=game_map, name=name, intervall=10)
        line.map_versions.add(version)
        for order, edge in enumerate(edges):
            TrainLineEdge.objects.create(
                train_line=line, train_edge=edge.trainedge_set.first(), order=order
            ).map_versions.add(version)
        return line

    def _simulator(self, game_map, version, car_edges, people=10):
        session = self._pt_session(game_map, version, people=people)
        game_round = self._round(session)
        _route(game_round, self._player(session), car_edges, mode="car")
        return TrafficSimulator(game_round, scale=100.0, seed=7)

    def _run_links(self, simulator, mode, line):
        key = simulator.line_route_keys[(mode, line.pk)]
        return [segment.edge_id for segment in simulator.route_segments[key]]

    def test_a_bus_drawn_on_the_other_side_drives_its_own(self):
        game_map, version, nodes, east, west = self._corridor()
        line = self._bus_line(game_map, [version], {version: west})

        simulator = self._simulator(game_map, version, list(reversed(west)))

        self.assertEqual(self._run_links(simulator, "bus", line), [e.pk for e in east])
        # The stops are the nodes, and those did not move.
        self.assertEqual(
            simulator.pt_lines[("bus", line.pk)].stops, [n.pk for n in nodes]
        )

    def test_a_train_drawn_on_the_other_track_runs_its_own(self):
        game_map, version, nodes = _grid_map("Rail corridor", 3, step_units=10.0)
        west = self._rails(game_map, version, [(nodes[1], nodes[0]), (nodes[2], nodes[1])])
        east = self._rails(game_map, version, [(nodes[0], nodes[1]), (nodes[1], nodes[2])])
        street = _street(game_map, version, nodes[0], nodes[1])
        line = self._train_line(game_map, version, west)

        simulator = self._simulator(game_map, version, [street])

        self.assertEqual(self._run_links(simulator, "train", line), [e.pk for e in east])

    def test_a_jam_going_the_other_way_does_not_hold_the_bus(self):
        """The symptom: westbound full of cars, the eastbound bus at free flow.

        Drawn on the westbound links, the bus queues behind the cars and then
        locks against them; on its own side the street is empty.
        """
        game_map, version, nodes, east, west = self._corridor()
        line = self._bus_line(game_map, [version], {version: west})
        session = self._pt_session(game_map, version, people=600)
        session.departure_std_dev_min = 1
        session.save(update_fields=["departure_std_dev_min"])
        game_round = self._round(session)
        _route(game_round, self._player(session), list(reversed(west)), mode="car")

        simulator = self._run(game_round, seed=7, max_ticks=300)

        runs = [pt for pt in simulator.pt_vehicles if pt.line_key == ("bus", line.pk)]
        self.assertTrue(runs)
        free_flow_min = 2.0 / line.bus_speed_kmh * 60
        for pt in runs:
            vehicle = simulator.vehicles[pt.vehicle_id]
            with self.subTest(departure=pt.departure_min):
                self.assertTrue(vehicle.arrived, "a bus never reached the end of its line")
                self.assertLessEqual(
                    vehicle.arrived_min - pt.departure_min,
                    free_flow_min + simulator.tick_duration_min,
                )

    def test_a_line_against_a_one_way_street_drives_it_as_drawn(self):
        """No link goes the line's way, so there is nothing to swap to: a contraflow lane."""
        game_map, version, nodes, _east, west = self._corridor(east=False)
        line = self._bus_line(game_map, [version], {version: west})

        simulator = self._simulator(game_map, version, list(reversed(west)))

        self.assertEqual(self._run_links(simulator, "bus", line), [e.pk for e in west])

    def test_a_bus_is_not_swapped_onto_a_railway(self):
        """The link going the bus's way is track only — a bus cannot drive it."""
        game_map, version, nodes, _east, west = self._corridor(east=False)
        self._rails(game_map, version, [(nodes[0], nodes[1]), (nodes[1], nodes[2])])
        line = self._bus_line(game_map, [version], {version: west})

        simulator = self._simulator(game_map, version, list(reversed(west)))

        self.assertEqual(self._run_links(simulator, "bus", line), [e.pk for e in west])

    def test_the_other_side_is_the_one_in_the_rounds_version(self):
        """`Busspuren` clones both sides of the street; each version swaps to its own.

        Looked up by its two ends alone, the base version's bus would find the
        clone and drive a street nobody else is on — which is the mistake the
        measurement that found this first made.
        """
        game_map, base, nodes, east, west = self._corridor()
        busspuren = MapVersion.objects.create(game_map=game_map, name="Busspuren")
        for node in nodes:
            node.map_versions.add(busspuren)
        clone_west = [
            _street(game_map, busspuren, nodes[1], nodes[0], lanes=2, bus_lane=True),
            _street(game_map, busspuren, nodes[2], nodes[1], lanes=2, bus_lane=True),
        ]
        clone_east = [
            _street(game_map, busspuren, nodes[0], nodes[1], lanes=2, bus_lane=True),
            _street(game_map, busspuren, nodes[1], nodes[2], lanes=2, bus_lane=True),
        ]
        line = self._bus_line(
            game_map, [base, busspuren], {base: west, busspuren: clone_west}
        )

        on_base = self._simulator(game_map, base, list(reversed(west)))
        on_busspuren = self._simulator(game_map, busspuren, list(reversed(clone_west)))

        self.assertEqual(self._run_links(on_base, "bus", line), [e.pk for e in east])
        self.assertEqual(
            self._run_links(on_busspuren, "bus", line), [e.pk for e in clone_east]
        )


class LinesRunUntilEverybodyIsHomeTests(PTBoardingScenarioMixin, TestCase):
    """PT keeps driving until the last person is home (Lukas, 2026-10-02).

    "Just fair and truthful; public transport also works during the quieter
    midday hours, at least in bigger cities." The base timetable covers the
    120-minute departure window; past it a run used to leave only for a PT
    rider. Now it also leaves while anybody at all is under way — in a car, on
    a bike, on foot, at a stop or still at the front door — and the round pays
    society CO2 for it.

    It counts PEOPLE. A line vehicle is itself under way, so a rule that
    counted it would keep the line dispatching itself until the guard.

    The fixture's lines are nobody's: one car route, over a 30 km street at
    20 km/h that the lines do not run on, so the car is still out at minute
    150 where the timetable ends at 120.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ptlate", password="12345")
        game_map, version, edges, self.bus, self.train = self._pt_map()
        # Wide enough for a node 30 km out; the fixture map is 10 km across.
        GameMap.objects.filter(pk=game_map.pk).update(x_dim=400)
        game_map.refresh_from_db()
        far = Node.objects.create(
            game_map=game_map, name="Far", x_position=320, y_position=0
        )
        far.map_versions.add(version)
        long_street = _street(
            game_map, version, edges[1].end_node, far, speed_limit=20
        )
        session = self._pt_session(game_map, version, people=100)
        self.game_round = self._round(session)
        player = self._player(session)
        self.route = _route(self.game_round, player, [long_street], mode="car")

    def _last_home_min(self, simulator):
        return max(
            v.arrived_min
            for v in simulator.vehicles.values()
            if v.route_pk == self.route.pk and v.arrived
        )

    def test_a_line_nobody_rides_runs_while_a_car_is_still_out(self):
        simulator = self._run(self.game_round)

        last_home = self._last_home_min(simulator)
        self.assertGreater(last_home, 140, "the car was home inside the timetable")
        for key in (("bus", self.bus.pk), ("train", self.train.pk)):
            line = simulator.pt_lines[key]
            self.assertGreater(line.vehicles, line.base_vehicles)
            # Every run that was due while the car was out left the depot.
            self.assertGreaterEqual(
                line.vehicles * line.interval_min, last_home,
                f"{line.name} stopped while somebody was still on the road",
            )

    def test_the_line_stops_once_only_line_vehicles_are_left(self):
        """Passes on `main`, where the line stops at its timetable. It is what
        a rule counting every vehicle, its own included, breaks."""
        simulator = self._run(self.game_round)

        last_home = self._last_home_min(simulator)
        tick = simulator.tick_duration_min
        for key in (("bus", self.bus.pk), ("train", self.train.pk)):
            line = simulator.pt_lines[key]
            # The last run left in the tick the last person got home, or before.
            self.assertLess(
                (line.vehicles - 1) * line.interval_min, last_home + tick,
                f"{line.name} dispatched after everybody was home",
            )
        # And the pass ended once the runs on the road had finished, not at
        # the guard.
        self.assertLess(simulator.current_tick * tick, last_home + 30)

    def test_the_extra_runs_are_paid_for(self):
        simulator = self._run(self.game_round)

        bus = simulator.pt_lines[("bus", self.bus.pk)]
        self.assertGreater(bus.society_co2_g, 28_800.0)
        self.assertAlmostEqual(
            bus.society_co2_g, bus.vehicles * bus.line_km * 1200.0, places=3
        )
        self.assertAlmostEqual(
            simulator.pass_total_co2_g - sum(
                simulator.outcomes[pk].co2_g for pk in simulator.outcomes
            ),
            sum(line.society_co2_g for line in simulator.pt_lines.values()),
            places=3,
        )
