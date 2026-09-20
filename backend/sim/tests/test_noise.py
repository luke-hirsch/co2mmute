"""
The stochastic layer, tested without a database.

Day-to-day variability in real networks is large — sigma is roughly 25% of
mean travel time in an urban peak and up to 75% — while demand itself moves
only about 10%. The amplifier between the two is the non-linearity near
capacity, and the link queue model already has it. So the inputs get modest,
physically-motivated noise and the existing mechanism produces the spread;
nothing wobbles the output directly.

Two dials, and they do different jobs:

- capacity, drawn once per link per round — the only one that makes round 2
  differ from round 1, because per-driver noise averages away over a thousand
  people;
- driver speed, drawn once per vehicle at spawn — the within-round spread.
"""

import random
import statistics

from django.test import SimpleTestCase

from sim.constants import (
    CAPACITY_FACTOR_CLAMP,
    CAPACITY_FACTOR_SIGMA,
    DRIVER_SPEED_CLAMP,
    DRIVER_SPEED_SIGMA,
    draw_capacity_factor,
    draw_driver_speed_factor,
)


class CapacityFactorTests(SimpleTestCase):
    """Capacity is a random variable, not a constant (Brilon/Geistefeldt)."""

    def test_it_is_reproducible_from_a_seed(self):
        first = [draw_capacity_factor(random.Random(7)) for _ in range(5)]
        second = [draw_capacity_factor(random.Random(7)) for _ in range(5)]

        self.assertEqual(first, second)

    def test_it_is_never_zero_or_negative(self):
        rng = random.Random(1)

        draws = [draw_capacity_factor(rng) for _ in range(2000)]

        self.assertTrue(all(d > 0 for d in draws), min(draws))

    def test_it_is_clamped_to_the_stated_range(self):
        rng = random.Random(2)

        draws = [draw_capacity_factor(rng) for _ in range(5000)]

        low, high = CAPACITY_FACTOR_CLAMP
        self.assertGreaterEqual(min(draws), low)
        self.assertLessEqual(max(draws), high)

    def test_it_is_centred_on_one_with_the_stated_spread(self):
        """A dial that quietly biases capacity would bias every round."""
        rng = random.Random(3)

        draws = [draw_capacity_factor(rng) for _ in range(20000)]

        self.assertAlmostEqual(statistics.fmean(draws), 1.0, places=2)
        self.assertAlmostEqual(
            statistics.pstdev(draws), CAPACITY_FACTOR_SIGMA, places=2
        )


class DriverSpeedFactorTests(SimpleTestCase):
    """Drivers do not all want to go the same speed."""

    def test_it_is_reproducible_from_a_seed(self):
        first = [draw_driver_speed_factor(random.Random(11)) for _ in range(5)]
        second = [draw_driver_speed_factor(random.Random(11)) for _ in range(5)]

        self.assertEqual(first, second)

    def test_it_is_never_zero_or_negative(self):
        rng = random.Random(4)

        draws = [draw_driver_speed_factor(rng) for _ in range(2000)]

        self.assertTrue(all(d > 0 for d in draws), min(draws))

    def test_it_is_clamped_to_the_stated_range(self):
        rng = random.Random(5)

        draws = [draw_driver_speed_factor(rng) for _ in range(5000)]

        low, high = DRIVER_SPEED_CLAMP
        self.assertGreaterEqual(min(draws), low)
        self.assertLessEqual(max(draws), high)

    def test_it_is_centred_on_one_with_the_stated_spread(self):
        rng = random.Random(6)

        draws = [draw_driver_speed_factor(rng) for _ in range(20000)]

        self.assertAlmostEqual(statistics.fmean(draws), 1.0, places=2)
        self.assertAlmostEqual(statistics.pstdev(draws), DRIVER_SPEED_SIGMA, places=2)


class CapacityFactorReachesTheLinkTests(SimpleTestCase):
    """EdgeState.flow_per_tick has to actually use it."""

    def test_the_factor_scales_the_discharge_rate(self):
        from sim.state import EdgeState

        plain = EdgeState(edge_id=1, distance_m=1000.0, free_flow_speed_kmh=50.0)
        halved = EdgeState(
            edge_id=2,
            distance_m=1000.0,
            free_flow_speed_kmh=50.0,
            capacity_factor=0.5,
        )

        self.assertAlmostEqual(
            halved.flow_per_tick(5), plain.flow_per_tick(5) * 0.5, places=6
        )

    def test_it_defaults_to_one_so_an_unseeded_link_is_unchanged(self):
        from sim.state import EdgeState

        state = EdgeState(edge_id=1, distance_m=1000.0, free_flow_speed_kmh=50.0)

        self.assertEqual(state.capacity_factor, 1.0)
        self.assertAlmostEqual(state.flow_per_tick(5), 150.0, places=6)
