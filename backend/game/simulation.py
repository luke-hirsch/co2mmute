"""
Traffic Simulation Engine

Handles tick-by-tick traffic simulation where each agent represents 1000 simulated people.
Uses BPR (Bureau of Public Roads) function for congestion modeling.
"""

import logging
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from django.db import transaction

from game.models import (
    AgentRoute,
    RouteSegment,
    SimulationResult,
    AgentSimulationResult,
    EdgeTrafficSnapshot,
    GameRound,
)
from maps.models import Edge, StreetPerRound

logger = logging.getLogger(__name__)

# Simulation parameters
PEOPLE_PER_AGENT = 1000
TICK_DURATION_MIN = 5
MORNING_DEPARTURE_HOUR = 9  # 9:00 AM
EVENING_DEPARTURE_HOUR = 17  # 5:00 PM
DEPARTURE_STD_DEV_MIN = 10  # Standard deviation for departure times

# Speed constants
WALK_SPEED_KMH = 5
BIKE_SPEED_KMH = 20
DEFAULT_CAR_SPEED_KMH = 50
BUS_SPEED_KMH = 30
TRAIN_SPEED_KMH = 40


@dataclass
class Vehicle:
    """Represents a single vehicle/person in the simulation."""

    agent_id: int
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


@dataclass
class PTVehicle:
    """Represents a public transport vehicle (bus/train)."""

    line_id: int
    vehicle_type: str  # bus or train
    current_stop_index: int
    passenger_count: int
    capacity: int
    departure_tick: int  # When this vehicle starts its route


@dataclass
class EdgeState:
    """State of an edge during simulation."""

    edge_id: int
    distance_m: float
    free_flow_speed_kmh: float
    capacity: int  # Number of cars at optimal flow
    current_vehicles: Set[int] = field(default_factory=set)  # Vehicle IDs on this edge

    @property
    def volume(self) -> int:
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
    return free_flow_speed / (1 + 0.15 * (ratio ** 4))


def calculate_edge_capacity(distance_m: float) -> int:
    """
    Calculate edge capacity based on length.
    1 car per 50m at optimal flow.

    Args:
        distance_m: Edge length in meters

    Returns:
        Capacity in number of vehicles
    """
    return max(1, int(distance_m / 50))


def generate_departure_times(
    num_people: int,
    base_hour: int,
    std_dev_min: float = DEPARTURE_STD_DEV_MIN,
) -> List[int]:
    """
    Generate departure times using normal distribution.

    Args:
        num_people: Number of departure times to generate
        base_hour: Base departure hour (e.g., 9 for 9:00 AM)
        std_dev_min: Standard deviation in minutes

    Returns:
        List of departure ticks (5-min buckets relative to simulation start)
    """
    base_minutes = base_hour * 60
    departures = []

    for _ in range(num_people):
        # Generate departure time with normal distribution
        departure_min = random.gauss(base_minutes, std_dev_min)
        # Clamp to reasonable range (1 hour before to 1 hour after base time)
        departure_min = max(base_minutes - 60, min(base_minutes + 60, departure_min))
        # Convert to tick (5-min buckets)
        tick = int((departure_min - (base_hour - 1) * 60) / TICK_DURATION_MIN)
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

        # Edge states indexed by edge_id
        self.edge_states: Dict[int, EdgeState] = {}

        # Vehicles indexed by unique ID
        self.vehicles: Dict[int, Vehicle] = {}
        self.next_vehicle_id = 0

        # PT vehicles
        self.pt_vehicles: List[PTVehicle] = []

        # Route data indexed by agent_id
        self.agent_routes: Dict[int, AgentRoute] = {}
        self.route_segments: Dict[int, List[RouteSegment]] = {}

        # Departure schedules: agent_id -> list of (person_index, departure_tick)
        self.departure_schedule: Dict[int, List[Tuple[int, int]]] = {}

        # Results tracking
        self.agent_results: Dict[int, Dict] = {}  # agent_id -> results dict

        # Current simulation tick
        self.current_tick = 0

        # Callback for progress updates
        self.on_progress: Optional[callable] = None

    def _load_routes(self):
        """Load all agent routes for the round."""
        # Get all player moves for this round
        from game.models import PlayerMove

        player_moves = PlayerMove.objects.filter(session_round=self.game_round)
        logger.info(f"[SIM] Loading routes for {player_moves.count()} player moves")

        for move in player_moves:
            routes = AgentRoute.objects.filter(player_move=move).prefetch_related(
                "segments", "segments__edge"
            )
            for route in routes:
                self.agent_routes[route.agent_id] = route
                segments = list(route.segments.order_by("order"))
                self.route_segments[route.agent_id] = segments

                logger.debug(
                    f"[SIM] Agent {route.agent_id}: mode={route.transport_mode}, "
                    f"distance={route.total_distance_m:.0f}m, segments={len(segments)}"
                )

                # Initialize result tracking
                self.agent_results[route.agent_id] = {
                    "trip_times": [],
                    "delays": [],
                    "mode": route.transport_mode,
                }

        logger.info(f"[SIM] Loaded {len(self.agent_routes)} agent routes")

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

        for edge in edges:
            # Calculate distance
            distance_m = edge.euclidean_2d_distance() * self.scale

            # Get speed limit
            street_edge = edge.streetedge_set.first()
            if street_edge:
                speed_limit = street_edge.speed_limit
            else:
                speed_limit = DEFAULT_CAR_SPEED_KMH

            capacity = calculate_edge_capacity(distance_m)
            self.edge_states[edge.id] = EdgeState(
                edge_id=edge.id,
                distance_m=distance_m,
                free_flow_speed_kmh=speed_limit,
                capacity=capacity,
            )

            logger.debug(
                f"[SIM] Edge {edge.id}: dist={distance_m:.0f}m, "
                f"speed={speed_limit}km/h, capacity={capacity}"
            )

        logger.info(f"[SIM] Initialized {len(self.edge_states)} edge states")

    def _generate_departures(self, is_morning: bool = True):
        """Generate departure times for all agents."""
        base_hour = MORNING_DEPARTURE_HOUR if is_morning else EVENING_DEPARTURE_HOUR

        for agent_id in self.agent_routes:
            departures = generate_departure_times(PEOPLE_PER_AGENT, base_hour)
            self.departure_schedule[agent_id] = [
                (i, tick) for i, tick in enumerate(departures)
            ]

    def _spawn_vehicles(self):
        """Spawn vehicles that should depart at the current tick."""
        for agent_id, schedule in self.departure_schedule.items():
            route = self.agent_routes.get(agent_id)
            if not route:
                continue

            segments = self.route_segments.get(agent_id, [])
            if not segments:
                continue

            # Find people who should depart at this tick
            for person_index, departure_tick in schedule:
                if departure_tick == self.current_tick:
                    # Create vehicle
                    vehicle = Vehicle(
                        agent_id=agent_id,
                        person_index=person_index,
                        mode=segments[0].mode,  # Start with first segment mode
                        segment_index=0,
                        position_on_edge_m=0.0,
                        departed=True,
                    )

                    vehicle_id = self.next_vehicle_id
                    self.next_vehicle_id += 1
                    self.vehicles[vehicle_id] = vehicle

                    # Add to first edge
                    first_segment = segments[0]
                    if first_segment.edge_id in self.edge_states:
                        self.edge_states[first_segment.edge_id].current_vehicles.add(
                            vehicle_id
                        )

    def _move_vehicles(self):
        """Move all vehicles based on current conditions."""
        arrived_vehicles = []

        for vehicle_id, vehicle in self.vehicles.items():
            if vehicle.arrived or not vehicle.departed:
                continue

            segments = self.route_segments.get(vehicle.agent_id, [])
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

            # Calculate speed based on mode and congestion
            if vehicle.mode in ["car"]:
                current_speed = edge_state.get_current_speed()
                free_flow_time = (
                    edge_state.distance_m / 1000 / edge_state.free_flow_speed_kmh * 60
                )
                actual_time = edge_state.distance_m / 1000 / current_speed * 60
                delay = max(0, actual_time - free_flow_time)
            elif vehicle.mode == "bike":
                current_speed = BIKE_SPEED_KMH
                delay = 0
            elif vehicle.mode == "walk":
                current_speed = WALK_SPEED_KMH
                delay = 0
            elif vehicle.mode == "bus":
                current_speed = BUS_SPEED_KMH
                delay = 0
            elif vehicle.mode == "train":
                current_speed = TRAIN_SPEED_KMH
                delay = 0
            else:
                current_speed = WALK_SPEED_KMH
                delay = 0

            # Calculate distance traveled in this tick
            distance_this_tick = current_speed * 1000 / 60 * TICK_DURATION_MIN

            # Update position
            vehicle.position_on_edge_m += distance_this_tick
            vehicle.total_travel_time_min += TICK_DURATION_MIN
            vehicle.congestion_delay_min += delay

            # Check if vehicle has completed current segment
            remaining = edge_state.distance_m - vehicle.position_on_edge_m

            if remaining <= 0:
                # Remove from current edge
                edge_state.current_vehicles.discard(vehicle_id)

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
                        self.edge_states[next_segment.edge_id].current_vehicles.add(
                            vehicle_id
                        )

        # Record arrival times
        for vehicle_id in arrived_vehicles:
            vehicle = self.vehicles[vehicle_id]
            agent_results = self.agent_results.get(vehicle.agent_id)
            if agent_results:
                agent_results["trip_times"].append(vehicle.total_travel_time_min)
                agent_results["delays"].append(vehicle.congestion_delay_min)

    def _record_edge_traffic(self):
        """Record traffic snapshot for each edge."""
        if not self.simulation_result:
            return

        snapshots = []
        for edge_id, state in self.edge_states.items():
            if state.volume > 0:
                snapshots.append(
                    EdgeTrafficSnapshot(
                        simulation=self.simulation_result,
                        edge_id=edge_id,
                        time_tick=self.current_tick,
                        vehicle_count=state.volume,
                        speed_kmh=state.get_current_speed(),
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
            # Load data
            self._load_routes()
            self._initialize_edges()

            if not self.agent_routes:
                logger.warning("[SIM] No agent routes found, simulation will be empty")

            # Run morning commute
            self._generate_departures(is_morning=True)
            total_departures = sum(len(s) for s in self.departure_schedule.values())
            logger.info(
                f"[SIM] Generated {total_departures} departures for "
                f"{len(self.departure_schedule)} agents"
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
                new_arrived = sum(1 for v in self.vehicles.values() if v.arrived) - prev_arrived
                vehicles_arrived += new_arrived

                # Log progress every 20 ticks
                if self.current_tick % 20 == 0:
                    active = sum(1 for v in self.vehicles.values() if v.departed and not v.arrived)
                    arrived = sum(1 for v in self.vehicles.values() if v.arrived)

                    # Find congested edges
                    congested = [
                        (eid, s.volume, s.capacity, s.get_current_speed())
                        for eid, s in self.edge_states.items()
                        if s.volume > s.capacity * 0.5
                    ]

                    logger.info(
                        f"[SIM] Tick {self.current_tick}: active={active}, "
                        f"arrived={arrived}/{len(self.vehicles)}, congested_edges={len(congested)}"
                    )

                    if congested and self.current_tick % 40 == 0:
                        for eid, vol, cap, speed in congested[:3]:
                            logger.debug(
                                f"[SIM]   Edge {eid}: {vol}/{cap} vehicles, "
                                f"speed={speed:.1f}km/h"
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
                    logger.info(
                        f"[SIM] All {len(self.vehicles)} vehicles arrived at tick {self.current_tick}"
                    )
                    break

                self.current_tick += 1

            # Calculate final results
            self._calculate_results()

            # Update simulation status
            self.simulation_result.status = SimulationResult.Status.COMPLETED
            self.simulation_result.save()

            logger.info(
                f"[SIM] Simulation completed: {self.current_tick} ticks, "
                f"CO2={self.simulation_result.total_co2_g:.0f}g"
            )

        except Exception as e:
            logger.exception(f"[SIM] Simulation failed: {e}")
            if self.simulation_result:
                self.simulation_result.status = SimulationResult.Status.FAILED
                self.simulation_result.save()
            raise e

        return self.simulation_result

    def _calculate_results(self):
        """Calculate final results and store in database."""
        logger.info(f"[SIM] Calculating results for {len(self.agent_results)} agents")

        total_co2 = 0.0
        total_cost = 0.0

        for agent_id, results in self.agent_results.items():
            route = self.agent_routes.get(agent_id)
            if not route:
                logger.warning(f"[SIM] No route found for agent {agent_id}")
                continue

            trip_times = results["trip_times"]
            delays = results["delays"]

            if not trip_times:
                logger.warning(f"[SIM] No trip times recorded for agent {agent_id}")
                continue

            mean_trip_time = sum(trip_times) / len(trip_times)
            mean_delay = sum(delays) / len(delays) if delays else 0.0

            # Calculate CO2 based on mode
            co2 = self._calculate_co2(route, mean_trip_time)
            total_co2 += co2

            logger.debug(
                f"[SIM] Agent {agent_id} ({route.transport_mode}): "
                f"trips={len(trip_times)}, avg_time={mean_trip_time:.1f}min, "
                f"avg_delay={mean_delay:.1f}min, CO2={co2:.0f}g"
            )

            # Create agent result
            AgentSimulationResult.objects.create(
                simulation=self.simulation_result,
                agent_route=route,
                mean_trip_time_min=mean_trip_time,
                total_co2_g=co2,
                congestion_delay_min=mean_delay,
            )

        # Update totals
        self.simulation_result.total_co2_g = total_co2
        self.simulation_result.total_cost_eur = total_cost
        self.simulation_result.save()

        logger.info(f"[SIM] Total CO2: {total_co2:.0f}g, Total cost: {total_cost:.2f}EUR")

        # Update street speeds for next round
        self._update_street_speeds()

    def _calculate_co2(self, route: AgentRoute, mean_trip_time: float) -> float:
        """
        Calculate CO2 emissions for an agent's route.

        Uses emission factors based on transport mode.
        For public transport, emissions are divided by average occupancy.
        """
        # Base CO2 emissions per km (g/km)
        co2_per_km = {
            "car": 120,  # Average car
            "bike": 0,
            "walk": 0,
            "public": 30,  # Average PT (divided by occupancy)
        }

        distance_km = route.total_distance_m / 1000
        mode = route.transport_mode

        base_emission = co2_per_km.get(mode, 0)

        # For car, factor in congestion (more emissions at lower speeds)
        if mode == "car":
            # Estimate average speed from trip time
            if mean_trip_time > 0:
                avg_speed = distance_km / (mean_trip_time / 60)
                # Apply CO2 factor based on speed
                if avg_speed < 20:
                    base_emission *= 1.5
                elif avg_speed < 40:
                    base_emission *= 1.2
                elif avg_speed > 80:
                    base_emission *= 1.1

        # Total CO2 for all 1000 people represented by this agent
        return base_emission * distance_km * PEOPLE_PER_AGENT

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
