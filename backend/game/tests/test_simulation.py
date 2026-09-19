"""
Comprehensive unit tests for traffic simulation.

Tests cover:
- Capacity calculation
- BPR congestion function
- Bus traffic integration (dedicated lanes vs regular streets)
- Speed loading from models
- EdgeState volume calculations
- Simulation parameter loading
- Full simulation integration
"""

from django.contrib.auth.models import User
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
    bpr_speed,
    calculate_edge_capacity,
    generate_departure_times,
)


class CapacityCalculationTests(TestCase):
    """Tests for the calculate_edge_capacity function."""

    def test_capacity_basic(self):
        """Test basic capacity calculation."""
        # 1km road, 50 km/h, 1 lane
        # Expected: 50 * 15 * 1 * 1 = 750 vehicles
        capacity = calculate_edge_capacity(1000, 50, 1)
        self.assertEqual(capacity, 750)

    def test_capacity_multiple_lanes(self):
        """Test capacity scales with lanes."""
        # 1km road, 50 km/h, 2 lanes
        # Expected: 50 * 15 * 1 * 2 = 1500 vehicles
        capacity = calculate_edge_capacity(1000, 50, 2)
        self.assertEqual(capacity, 1500)

    def test_capacity_different_speeds(self):
        """Test capacity scales with speed limit."""
        # 1km road, 30 km/h, 1 lane
        # Expected: 30 * 15 * 1 * 1 = 450 vehicles
        capacity_30 = calculate_edge_capacity(1000, 30, 1)
        self.assertEqual(capacity_30, 450)

        # 1km road, 80 km/h, 1 lane
        # Expected: 80 * 15 * 1 * 1 = 1200 vehicles
        capacity_80 = calculate_edge_capacity(1000, 80, 1)
        self.assertEqual(capacity_80, 1200)

    def test_capacity_short_road(self):
        """Test capacity for short roads."""
        # 100m road, 50 km/h, 1 lane
        # Expected: 50 * 15 * 0.1 * 1 = 75 vehicles
        capacity = calculate_edge_capacity(100, 50, 1)
        self.assertEqual(capacity, 75)

    def test_capacity_minimum_one(self):
        """Test capacity is at least 1."""
        # Very short road should still have capacity of 1
        capacity = calculate_edge_capacity(1, 30, 1)
        self.assertEqual(capacity, 1)

    def test_capacity_realistic_urban(self):
        """Test realistic urban street capacity."""
        # 500m urban street, 30 km/h, 2 lanes
        # Expected: 30 * 15 * 0.5 * 2 = 450 vehicles
        capacity = calculate_edge_capacity(500, 30, 2)
        self.assertEqual(capacity, 450)

    def test_capacity_realistic_highway(self):
        """Test realistic highway capacity."""
        # 2km highway, 100 km/h, 3 lanes
        # Expected: 100 * 15 * 2 * 3 = 9000 vehicles
        capacity = calculate_edge_capacity(2000, 100, 3)
        self.assertEqual(capacity, 9000)


class BPRSpeedFunctionTests(TestCase):
    """Tests for the BPR (Bureau of Public Roads) speed function."""

    def test_free_flow(self):
        """Test speed at zero volume."""
        speed = bpr_speed(50, 0, 100)
        self.assertEqual(speed, 50)

    def test_at_capacity(self):
        """Test speed at exactly capacity."""
        # At volume = capacity, ratio = 1
        # speed = 50 / (1 + 0.15 * 1^4) = 50 / 1.15 ≈ 43.48
        speed = bpr_speed(50, 100, 100)
        self.assertAlmostEqual(speed, 43.478, places=2)

    def test_over_capacity(self):
        """Test speed when over capacity."""
        # At volume = 2 * capacity, ratio = 2
        # speed = 50 / (1 + 0.15 * 2^4) = 50 / (1 + 0.15 * 16) = 50 / 3.4 ≈ 14.71
        speed = bpr_speed(50, 200, 100)
        self.assertAlmostEqual(speed, 14.706, places=2)

    def test_half_capacity(self):
        """Test speed at half capacity."""
        # At volume = 0.5 * capacity, ratio = 0.5
        # speed = 50 / (1 + 0.15 * 0.5^4) = 50 / (1 + 0.15 * 0.0625) ≈ 49.54
        speed = bpr_speed(50, 50, 100)
        self.assertAlmostEqual(speed, 49.537, places=2)

    def test_severe_congestion(self):
        """Test speed under severe congestion."""
        # At volume = 3 * capacity, ratio = 3
        # speed = 50 / (1 + 0.15 * 3^4) = 50 / (1 + 0.15 * 81) = 50 / 13.15 ≈ 3.80
        speed = bpr_speed(50, 300, 100)
        self.assertAlmostEqual(speed, 3.802, places=2)

    def test_zero_capacity(self):
        """Test that zero capacity returns free flow speed."""
        speed = bpr_speed(50, 100, 0)
        self.assertEqual(speed, 50)

    def test_negative_capacity(self):
        """Test that negative capacity returns free flow speed."""
        speed = bpr_speed(50, 100, -1)
        self.assertEqual(speed, 50)


class EdgeStateTests(TestCase):
    """Tests for EdgeState dataclass."""

    def test_volume_without_buses(self):
        """Test volume calculation with only cars."""
        edge_state = EdgeState(
            edge_id=1,
            distance_m=1000,
            free_flow_speed_kmh=50,
            capacity=100,
        )
        edge_state.current_vehicles = {1, 2, 3, 4, 5}

        self.assertEqual(edge_state.volume, 5)
        self.assertEqual(edge_state.total_vehicles, 5)

    def test_volume_with_buses_on_dedicated_lane(self):
        """Test volume excludes buses on dedicated lanes."""
        edge_state = EdgeState(
            edge_id=1,
            distance_m=1000,
            free_flow_speed_kmh=50,
            capacity=100,
            has_dedicated_bus_lane=True,
        )
        edge_state.current_vehicles = {1, 2, 3, 4, 5}  # 5 vehicles
        edge_state.buses_on_dedicated_lane = {4, 5}  # 2 buses

        # Volume should be 3 (total 5 - buses 2)
        self.assertEqual(edge_state.volume, 3)
        # Total vehicles should still be 5
        self.assertEqual(edge_state.total_vehicles, 5)

    def test_volume_all_buses_on_dedicated_lane(self):
        """Test volume when all vehicles are buses on dedicated lanes."""
        edge_state = EdgeState(
            edge_id=1,
            distance_m=1000,
            free_flow_speed_kmh=50,
            capacity=100,
            has_dedicated_bus_lane=True,
        )
        edge_state.current_vehicles = {1, 2, 3}
        edge_state.buses_on_dedicated_lane = {1, 2, 3}

        # Volume should be 0 (no traffic affecting congestion)
        self.assertEqual(edge_state.volume, 0)
        # Total vehicles should be 3
        self.assertEqual(edge_state.total_vehicles, 3)

    def test_get_current_speed_free_flow(self):
        """Test speed calculation with no congestion."""
        edge_state = EdgeState(
            edge_id=1,
            distance_m=1000,
            free_flow_speed_kmh=50,
            capacity=100,
        )

        self.assertEqual(edge_state.get_current_speed(), 50)

    def test_get_current_speed_congested(self):
        """Test speed calculation with congestion."""
        edge_state = EdgeState(
            edge_id=1,
            distance_m=1000,
            free_flow_speed_kmh=50,
            capacity=100,
        )
        edge_state.current_vehicles = set(range(100))  # At capacity

        # Should use BPR function
        expected_speed = bpr_speed(50, 100, 100)
        self.assertAlmostEqual(edge_state.get_current_speed(), expected_speed, places=2)

    def test_get_current_speed_with_buses_on_dedicated_lane(self):
        """Test speed is not affected by buses on dedicated lanes."""
        edge_state = EdgeState(
            edge_id=1,
            distance_m=1000,
            free_flow_speed_kmh=50,
            capacity=100,
            has_dedicated_bus_lane=True,
        )
        edge_state.current_vehicles = {1, 2, 3, 4, 5}  # 5 vehicles
        edge_state.buses_on_dedicated_lane = {4, 5}  # 2 buses

        # Volume for congestion is 3, not 5
        expected_speed = bpr_speed(50, 3, 100)
        self.assertAlmostEqual(edge_state.get_current_speed(), expected_speed, places=2)


class DepartureTimeGenerationTests(TestCase):
    """Tests for departure time generation."""

    def test_generates_correct_number(self):
        """Test that correct number of departure times are generated."""
        departures = generate_departure_times(
            num_people=100, base_hour=9, std_dev_min=10, tick_duration_min=5
        )
        self.assertEqual(len(departures), 100)

    def test_all_non_negative(self):
        """Test that all departure times are non-negative."""
        departures = generate_departure_times(
            num_people=100, base_hour=9, std_dev_min=10, tick_duration_min=5
        )
        self.assertTrue(all(t >= 0 for t in departures))

    def test_different_tick_duration(self):
        """Test departure times with different tick durations."""
        departures_5min = generate_departure_times(
            num_people=100, base_hour=9, std_dev_min=10, tick_duration_min=5
        )
        departures_10min = generate_departure_times(
            num_people=100, base_hour=9, std_dev_min=10, tick_duration_min=10
        )

        # With larger tick duration, tick numbers should generally be smaller
        # (because we're dividing by a larger number)
        avg_5min = sum(departures_5min) / len(departures_5min)
        avg_10min = sum(departures_10min) / len(departures_10min)
        self.assertGreater(avg_5min, avg_10min)

    def test_zero_std_dev(self):
        """Test with zero standard deviation (everyone departs at same time)."""
        departures = generate_departure_times(
            num_people=100, base_hour=9, std_dev_min=0, tick_duration_min=5
        )
        # All should be at the same tick
        self.assertEqual(len(set(departures)), 1)


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
    """Tests for bus traffic integration with dedicated lanes."""

    def test_bus_on_dedicated_lane_not_in_volume(self):
        """Test that buses on dedicated lanes don't affect traffic volume."""
        edge_state = EdgeState(
            edge_id=1,
            distance_m=1000,
            free_flow_speed_kmh=50,
            capacity=100,
            has_dedicated_bus_lane=True,
        )

        # Add 5 cars and 2 buses
        edge_state.current_vehicles = {1, 2, 3, 4, 5, 6, 7}
        edge_state.buses_on_dedicated_lane = {6, 7}

        # Volume should only count the 5 cars
        self.assertEqual(edge_state.volume, 5)
        # Speed should be calculated based on 5 vehicles, not 7
        expected_speed = bpr_speed(50, 5, 100)
        self.assertAlmostEqual(edge_state.get_current_speed(), expected_speed, places=2)

    def test_bus_on_regular_street_in_volume(self):
        """Test that buses on regular streets affect traffic volume."""
        edge_state = EdgeState(
            edge_id=1,
            distance_m=1000,
            free_flow_speed_kmh=50,
            capacity=100,
            has_dedicated_bus_lane=False,  # No dedicated lane
        )

        # Add 5 cars and 2 buses (all on same street)
        edge_state.current_vehicles = {1, 2, 3, 4, 5, 6, 7}
        # No buses on dedicated lane (none exists)

        # Volume should count all 7 vehicles
        self.assertEqual(edge_state.volume, 7)
        # Speed should be calculated based on 7 vehicles
        expected_speed = bpr_speed(50, 7, 100)
        self.assertAlmostEqual(edge_state.get_current_speed(), expected_speed, places=2)


<<<<<<< HEAD
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
        simulator = TrafficSimulator(self.game_round, scale=100.0)

        edge_state = simulator.edge_states[self.edge.pk]

        self.assertGreater(edge_state.get_current_speed(), 0)


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
        simulator.current_tick = 200
        simulator.vehicles[1] = Vehicle(
            route_pk=self.agent_route.pk,
            person_index=0,
            mode="car",
            segment_index=0,
            position_on_edge_m=10.0,
            total_travel_time_min=180.0,
            congestion_delay_min=150.0,
            departed=True,
            arrived=False,
            passenger_count=2,
        )

        simulator._record_non_arrivals()

        results = simulator.agent_results[self.agent_route.pk]
        self.assertEqual(results["not_arrived"], 2)
        self.assertEqual(results["trip_times"], [180.0, 180.0])
        self.assertEqual(results["delays"], [150.0, 150.0])

    def test_arrived_and_undeparted_vehicles_are_left_alone(self):
        from game.simulation import Vehicle

        simulator = TrafficSimulator(self.game_round, scale=100.0)
        simulator.vehicles[1] = Vehicle(
            route_pk=self.agent_route.pk,
            person_index=0,
            mode="car",
            segment_index=0,
            position_on_edge_m=0.0,
            departed=True,
            arrived=True,
        )
        simulator.vehicles[2] = Vehicle(
            route_pk=self.agent_route.pk,
            person_index=1,
            mode="car",
            segment_index=0,
            position_on_edge_m=0.0,
            departed=False,
            arrived=False,
        )

        simulator._record_non_arrivals()

        results = simulator.agent_results[self.agent_route.pk]
        self.assertEqual(results["not_arrived"], 0)
        self.assertEqual(results["trip_times"], [])
=======
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
    """A bus lane is one of the street's lanes, not an extra one.

    Today dedicated_bus_lane only removes buses from the volume count, so the
    lane is a free gift and voting for one is always right at no cost. Every
    bus-lane edge in the shipped maps has lanes == max_lanes.
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

    def test_bus_lane_costs_a_car_lane(self):
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

    def test_a_single_lane_street_with_a_bus_lane_keeps_one_car_lane(self):
        """Never zero: a street cars cannot enter at all would deadlock them."""
        edge = _street(
            self.game_map, self.version, self.nodes[0], self.nodes[1],
            lanes=1, bus_lane=True,
        )

        simulator = self._simulator_over(edge)

        self.assertEqual(simulator.edge_states[edge.pk].car_lanes, 1)


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
>>>>>>> 574e9a6 (tests: die strasse ist endlich, staus stauen sich zurueck (rot))
