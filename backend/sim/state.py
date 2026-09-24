"""
The mutable state of a running simulation: links, queues and vehicles.

Moved out of `game/simulation.py` unchanged. These are the only objects the
tick loop touches, which is what makes the loop itself Django-free.
"""

from dataclasses import dataclass, field

from sim.constants import (
    JAM_DENSITY_VEH_PER_KM_LANE,
    SATURATION_FLOW_VEH_PER_H_LANE,
    pt_cost_eur_per_vehicle_km,
    pt_emissions_g_per_vehicle_km,
)


def node_chain(ends: list[tuple[int, int]]) -> list[int]:
    """Node ids a run of edges visits, in travel order.

    `ends` is each edge's (start_node_id, end_node_id) in the order the line or
    the route stores them. An edge may be stored either way round relative to
    the direction of travel — the map importer does not normalise that, and the
    shipped examples store every edge of every line reversed — so the chain is
    followed by matching node ids rather than by trusting start/end.

    The first edge is the one that needs care: on its own there is nothing to
    orient it against, so its direction is decided by whichever of its ends the
    *second* edge touches. Seeding it in stored order instead is what made every
    line report its first two nodes and stop (2026-09-19, `[backend]-pt-stops`).

    Returns [] for nothing, and stops early where the chain breaks — so a caller
    can tell a whole chain from a truncated one by its length, which is
    len(ends) + 1 exactly when nothing broke.
    """
    if not ends:
        return []

    first_start, first_end = ends[0]
    if len(ends) == 1:
        return [first_start, first_end]

    second = set(ends[1])
    if first_end in second:
        chain = [first_start, first_end]
    elif first_start in second:
        chain = [first_end, first_start]
    else:
        return [first_start, first_end]

    for start_id, end_id in ends[1:]:
        prev = chain[-1]
        if prev == start_id:
            chain.append(end_id)
        elif prev == end_id:
            chain.append(start_id)
        else:
            break

    return chain


@dataclass
class Vehicle:
    """One person (car/bike/walk) or one PT vehicle carrying many."""

    route_pk: int
    person_index: int
    mode: str
    segment_index: int
    passenger_count: int = 1

    # Drawn once at spawn and carried for the whole trip — see
    # draw_driver_speed_factor. Redrawing per link would average a long route
    # back to the mean and the dial would do nothing.
    speed_factor: float = 1.0

    wants_to_depart_min: float = 0.0  # when this person wanted to leave
    ready_at_min: float = 0.0  # earliest it may leave its current link
    entered_edge_min: float = 0.0
    arrived_min: float | None = None
    departed: bool = False
    arrived: bool = False
    queued: bool = False

    at_stop: bool = False
    aboard_of: int | None = None
    stranded: bool = False

    reached_stop_min: float = 0.0
    wait_min: float = 0.0
    bought_ticket: bool = False


@dataclass
class PTLineState:
    """One public transport line and the timetable it runs to.

    The unit is the LINE, not the route. Its vehicles are counted once for the
    round however many agents ride it — counting them per route is what made
    two agents on the same bus line emit two lines' worth — and they are
    counted whether anybody rides it or not, because a timetable does not ask.

    `person_km` is filled while the round's routes are attributed and is the
    divisor every personal figure uses. It is zero for a line nobody rode, and
    that is not a division by zero waiting to happen: nobody asks such a line
    for a personal figure, only for its society one.
    """

    line_id: int
    mode: str  # "bus" or "train"
    name: str
    line_km: float
    interval_min: int
    capacity: int
    vehicles: int
    person_km: float = 0.0

    edge_ids: list[int] = field(default_factory=list)
    stops: list[int] = field(default_factory=list)

    boarded: int = 0
    denied: int = 0
    stranded: int = 0

    @property
    def vehicle_km(self) -> float:
        """Vehicle-kilometres run inside the departure window."""
        return self.vehicles * self.line_km

    @property
    def society_co2_g(self) -> float:
        """What the line emits this round. Not a function of its riders."""
        return pt_emissions_g_per_vehicle_km(self.mode) * self.vehicle_km

    @property
    def society_cost_eur(self) -> float:
        """What running the line costs this round. Not a function of riders."""
        return pt_cost_eur_per_vehicle_km(self.mode) * self.vehicle_km

    def share_of(self, society_total: float, person_km: float) -> float:
        """This many person-kilometres' slice of a society total.

        Weighted by person-km rather than split per head: on a 13 km line a
        one-stop rider must not carry the same share as one going end to end,
        and the car beside them is priced per kilometre. Summed over every
        contribution this returns the society total exactly, which is the
        identity the whole design rests on.
        """
        if self.person_km <= 0:
            return 0.0
        return society_total * person_km / self.person_km


@dataclass
class PTVehicle:
    """One timetabled run of a line: a bus or train on the road, with people in it."""

    vehicle_id: int
    line_key: tuple[str, int]
    capacity: int
    departure_min: float
    stop_index: int = 0
    riders: list[int] = field(default_factory=list)
    boarded_total: int = 0
    finished: bool = False

    @property
    def free_seats(self) -> int:
        return max(0, self.capacity - len(self.riders))


@dataclass
class QueuedVehicle:
    """One vehicle sitting on a link, with the earliest minute it may leave."""

    vehicle_id: int
    ready_at_min: float
    pcu: float
    entered_at_min: float


@dataclass
class EdgeState:
    """A link in the queue model: free-flow time, flow capacity, storage."""

    edge_id: int
    distance_m: float
    free_flow_speed_kmh: float

    start_node_id: int = 0
    end_node_id: int = 0

    car_lanes: int = 1
    has_dedicated_bus_lane: bool = False

    # This round's capacity draw for this link — see draw_capacity_factor.
    # 1.0 means "no noise", so an EdgeState built by hand in a test behaves
    # exactly as it did before the stochastic layer.
    capacity_factor: float = 1.0

    queue: list[QueuedVehicle] = field(default_factory=list)
    occupancy_pcu: float = 0.0
    release_budget: float = 0.0
    blocked_since_tick: int = 0

    # Observed traversals, for the per-edge speed the snapshot stores.
    traversal_count: int = 0
    traversal_time_min: float = 0.0
    peak_occupancy_pcu: float = 0.0

    @property
    def free_flow_min(self) -> float:
        """Minutes to cross the link when it is empty."""
        if self.free_flow_speed_kmh <= 0:
            return 0.0
        return self.distance_m / 1000.0 / self.free_flow_speed_kmh * 60.0

    @property
    def open_to_cars(self) -> bool:
        """False on a bus gate: a street given over entirely to buses."""
        return self.car_lanes > 0

    @property
    def _capacity_lanes(self) -> int:
        """Never zero — see the fallback in _enter_edge.

        A link with no flow capacity can never discharge, so a car that
        reached a bus gate despite the client and the submit check would
        stand there until max_ticks and take the round's numbers with it.
        """
        return max(1, self.car_lanes)

    @property
    def storage_capacity_pcu(self) -> float:
        """How many car-equivalents stand on the link bumper to bumper."""
        return max(
            1.0,
            JAM_DENSITY_VEH_PER_KM_LANE
            * self._capacity_lanes
            * self.distance_m
            / 1000.0,
        )

    def flow_per_tick(self, tick_duration_min: int) -> float:
        """Car-equivalents the link discharges in one tick.

        Scaled by this round's capacity draw: capacity is a random variable,
        not a constant, and this is where the round-to-round variance enters
        the model.
        """
        return (
            SATURATION_FLOW_VEH_PER_H_LANE
            * self._capacity_lanes
            * self.capacity_factor
            * tick_duration_min
            / 60.0
        )

    def has_room_for(self, pcu: float) -> bool:
        """Whether one more vehicle of this size fits on the link.

        Asking "is it full?" before adding lets occupancy overshoot by up to
        one vehicle, and by three for a bus — a link with 39.9 of storage
        admitted a 40th car in testing. An empty link never refuses: a link
        too short to hold a single bus would otherwise block it forever.
        """
        if not self.queue:
            return True
        return self.occupancy_pcu + pcu <= self.storage_capacity_pcu

    @property
    def mean_speed_kmh(self) -> float:
        """Length over observed CAR traversal time; free flow if none crossed.

        Only cars are counted into traversal_count / traversal_time_min (see
        _discharge). A pedestrian takes 10.7 minutes over an 895 m edge where a
        car takes 1.07, so letting walkers into this mean would report an empty
        street as jammed — and this number feeds both the CO2 factor and the
        route preview the players see.
        """
        if self.traversal_count == 0 or self.traversal_time_min <= 0:
            return self.free_flow_speed_kmh
        mean_min = self.traversal_time_min / self.traversal_count
        return self.distance_m / 1000.0 / (mean_min / 60.0)
