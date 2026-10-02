"""
What a pass gives back, besides the engine's own state.

Nothing in here is written anywhere by the engine. The adapter turns these into
rows once both passes have run; a calibration script reads them directly.
"""

from dataclasses import dataclass


@dataclass
class RouteOutcome:
    """What one pass worked out for one route, kept until both passes are done.

    The way to work's row in the database carries the way home's time as well,
    so nothing is written until the evening has run. Cost and CO2 are for the
    whole Gruppe, time and delay are the mean over its people.
    """

    mean_trip_time_min: float
    mean_delay_min: float
    mean_wait_min: float
    co2_g: float
    cost_eur: float
    paid_eur: float


@dataclass(frozen=True)
class LinkSample:
    """One link at the end of one tick, for the heatmap and the replay's streets.

    Taken every tick for every link with something on it, at the pass's own
    tick plus its offset (the evening sits after the morning on one axis). It
    used to be a database row written in the middle of the tick loop, which was
    the last thing tying the loop to Django; now it is collected, and the
    adapter writes the lot when the round is done.

    `waiting_count` is the queue outside the link: people who wanted to leave
    by now and whose first link would not let them on. They sit in the
    engine's waiting list rather than on the link, so without this the link
    would sample empty.
    """

    edge_id: int
    time_tick: int
    vehicle_count: int
    waiting_count: int
    speed_kmh: float
