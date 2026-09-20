"""
The input contract of the engine.

This file is the documentation: it says exactly what the simulation needs to
know about a round, in about forty lines, instead of leaving it implicit across
three hundred lines of ORM queries in the adapter.

Nothing here imports Django. `game/simulation.py` builds these from model rows;
a calibration script or a second engine can build them from anything at all.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """One leg of a route: which link, in which order, by which mode.

    The engine used to read these four attributes straight off `RouteSegment`
    model rows, which is the one thing that kept the tick loop tied to the
    database. Same four fields, no Django.
    """

    edge_id: int
    order: int
    mode: str
    pt_line_id: int | None = None
