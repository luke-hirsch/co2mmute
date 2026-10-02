"""
What the game asks of a traffic model.

`game.simulation.TrafficSimulator` is written against this and nothing else of
the engine underneath it: build it from a `Scenario` and a generator, run the
round, read the outcome. `sim.linkqueue.LinkQueueEngine` is the one engine
there is. A second one — a cellular automaton, say — is a new module that
satisfies this protocol over the same scenario, and the two can then run the
same round side by side.

A round is two passes, the way to work and the way home, on two fresh networks:
`run_round` runs this engine's pass and then, if it is handed a way home, builds
the evening's engine with the generator the morning left off at — so one round
is still one seeded stream — and runs that. The outcome is read off both.
"""

import random
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from sim.log import SimulationLog
from sim.outcome import LinkSample, RouteOutcome
from sim.scenario import Scenario


@runtime_checkable
class Engine(Protocol):
    """One pass over one scenario, and the round it belongs to."""

    # Per person-route: what this pass worked out, read after run_round.
    outcomes: dict[int, RouteOutcome]
    # The pass's totals. The network's own CO2 and cost are in the totals
    # already; they are kept apart so a screen can show the difference.
    pass_total_co2_g: float
    pass_total_cost_eur: float
    pass_network_co2_g: float
    pass_network_cost_eur: float
    # Every link with something on it, every tick, on the round's one axis.
    link_samples: list[LinkSample]
    # The evening's engine, once there is one.
    home_pass: "Engine | None"
    # The report the host downloads; the evening's is appended to the morning's.
    sim_log: SimulationLog

    def __init__(self, scenario: Scenario, rng: random.Random) -> None: ...

    def run_round(
        self,
        max_ticks: int,
        on_progress: Callable[[int, int], None] | None = None,
        way_home: "Callable[[random.Random], Engine] | None" = None,
    ) -> None:
        """Run the way to work, then the way home if there is one."""
        ...

    def progress_percent(self) -> int:
        """People done over both passes, for a progress bar."""
        ...

    def observed_speeds(self) -> dict[int, float]:
        """Each link's car speed as driven, pooled over both passes, in km/h."""
        ...

    def build_replay(self) -> dict:
        """The recording the replay screen draws, both passes on one clock."""
        ...
