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
