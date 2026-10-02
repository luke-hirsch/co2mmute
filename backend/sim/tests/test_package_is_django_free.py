"""
The one invariant that stops the seam rotting back shut.

`sim/` is worth having only as long as it can be imported, tested and
calibrated without a Django settings module. That property is easy to lose by
accident — one convenience import of `game.models` somewhere in the engine and
it is gone, with nothing failing to say so.

It cannot be checked in-process, because by the time Django's test runner has
started, Django is imported. So it is checked in a subprocess.
"""

import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parents[2]

PROBE = """
import sys
import sim
import sim.constants, sim.engine, sim.linkqueue, sim.log, sim.outcome
import sim.scenario, sim.state
leaked = sorted(m for m in sys.modules if m == "django" or m.startswith("django."))
if leaked:
    print("DJANGO:" + ",".join(leaked[:5]))
    sys.exit(1)
print("CLEAN")
"""


class SimPackageIsDjangoFreeTests(SimpleTestCase):
    """Importing the engine must not drag Django in."""

    def test_importing_sim_does_not_import_django(self):
        proc = subprocess.run(
            [sys.executable, "-c", PROBE],
            cwd=BACKEND,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            proc.returncode,
            0,
            f"stdout={proc.stdout!r} stderr={proc.stderr[-800:]!r}",
        )
        self.assertIn("CLEAN", proc.stdout)

    def test_the_engine_runs_a_round_without_a_settings_module(self):
        """Not just importable — usable, a whole round. This is what calibration needs."""
        probe = """
import random
from sim import car_emissions_g_per_km, generate_departure_minutes
from sim.scenario import Segment
from sim.state import EdgeState

assert abs(car_emissions_g_per_km(50.0) - 166.8) < 1e-9
assert len(generate_departure_minutes(10, 9, 5.0, rng=random.Random(1))) == 10
assert Segment(edge_id=1, order=1, mode="car").pt_line_id is None
assert EdgeState(edge_id=1, distance_m=1000.0, free_flow_speed_kmh=50.0).free_flow_min > 0

# A whole round, not just the arithmetic: that is what calibration runs.
from sim import LinkQueueEngine, Link, Params, Route, Scenario
link = Link(edge_id=1, start_node_id=1, end_node_id=2, distance_m=500.0,
            is_street=True, speed_limit_kmh=50)
route = Route(pk=1, agent_id=1, transport_mode="car",
              segments=(Segment(edge_id=1, order=1, mode="car"),))
engine = LinkQueueEngine(
    Scenario(params=Params(people_per_agent=20, walk_speed_kmh=5,
                           bike_speed_kmh=20, default_car_speed_kmh=50),
             links=(link,), routes=(route,)),
    random.Random(1),
)
engine.run_round()
assert len(engine.agent_results[1]["trip_times"]) == 20
assert engine.outcomes[1].co2_g > 0
print("RAN")
"""
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=BACKEND,
            capture_output=True,
            text=True,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertIn("RAN", proc.stdout)
