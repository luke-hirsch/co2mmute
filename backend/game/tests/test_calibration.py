"""Calibrating a map: the rule, the search, and rounds played on a real map.

The rule: a map's budget per round is what a round costs when half the
Gruppen drive and the rest ride, rounded to a number a class can hold; its
commuters are as many as make a round where everybody drives as slow as the
city's own rush hour. `game/calibration.py` holds the rule, `game/measure.py`
plays the rounds it is measured on.

The search and the rule are tested on made-up rounds, where the answer is
known exactly. The rounds themselves are played on the six-node map from
`maps/tests/test_checks.py`, with routes written by hand — the game's router
is TypeScript, and the suite does not run Node.
"""

import json
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase, override_settings

from game import calibration
from game.measure import MapRounds, RoutesRefused
from game.models import GameSession, Player
from game.tests._helpers import TEST_BACKENDS, TempMediaRootMixin, create_host, muted
from maps.importer import MapImporter
from maps.models import BusLine, Edge, MapVersion
from maps.tests.test_checks import small_map


class RoundFigureTests(SimpleTestCase):
    """Two significant figures: 16 174 kg is a 16 000 kg budget."""

    def test_the_shipped_budget_is_its_own_measurement_rounded(self):
        self.assertEqual(calibration.round_figure(16174), 16000)

    def test_two_figures_at_every_size(self):
        cases = {6437: 6400, 853: 850, 95: 95, 1249: 1200, 128_400: 130_000}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(calibration.round_figure(value), expected)

    def test_a_half_rounds_up(self):
        self.assertEqual(calibration.round_figure(15500), 16000)
        self.assertEqual(calibration.round_figure(6450), 6500)

    def test_nothing_is_nothing(self):
        self.assertEqual(calibration.round_figure(0), 0)


def slowing(free_kmh=50.0, knee=3000):
    """A map whose cars slow smoothly as commuters are added.

    50 km/h empty, half that at `knee` commuters — so at a target of 20 km/h
    the crossing is at exactly 4 500.
    """

    def speed_at(commuters):
        return free_kmh * knee / (knee + commuters)

    return speed_at


class FindCommutersTests(SimpleTestCase):
    def test_finds_the_population_at_the_target_speed(self):
        found, _ = calibration.find_commuters(
            slowing(), target_kmh=20, start=6400, smallest=64
        )
        self.assertEqual(found, 4500)

    def test_the_answer_does_not_depend_on_where_it_starts(self):
        for start in (500, 4500, 6400, 40_000):
            with self.subTest(start=start):
                found, _ = calibration.find_commuters(
                    slowing(), target_kmh=20, start=start, smallest=64
                )
                self.assertEqual(found, 4500)

    def test_says_what_it_measured(self):
        _, searched = calibration.find_commuters(
            slowing(), target_kmh=20, start=6400, smallest=64
        )
        self.assertIn(6400, searched)
        self.assertAlmostEqual(searched[6400], slowing()(6400))

    def test_refuses_a_target_faster_than_the_empty_map(self):
        with self.assertRaises(calibration.CalibrationRefused) as caught:
            calibration.find_commuters(
                slowing(free_kmh=30), target_kmh=35, start=6400, smallest=64
            )
        self.assertIn("35", str(caught.exception))

    def test_refuses_a_map_that_never_gets_that_slow(self):
        with self.assertRaises(calibration.CalibrationRefused):
            calibration.find_commuters(
                lambda commuters: 40.0, target_kmh=24, start=6400, smallest=64
            )

    def test_a_round_where_somebody_never_got_home_is_too_slow(self):
        """A pass that hit the guard has no speed; more commuters only make it worse."""

        def speed_at(commuters):
            return None if commuters > 5000 else slowing()(commuters)

        found, _ = calibration.find_commuters(
            speed_at, target_kmh=10, start=6400, smallest=64
        )
        self.assertEqual(found, 5000)


@dataclass(frozen=True)
class FakeRound:
    """Just what the rule reads off a round."""

    total_kg: float
    car_km: float = 10.0
    car_hours: float = 0.5
    not_home: int = 0


class FakeMap:
    """Rounds whose cost depends on the share only, and a speed on commuters."""

    def __init__(self):
        self.calls = []

    def play(self, *, commuters, share, seed, way_home=True):
        self.calls.append((commuters, share, seed, way_home))
        hours = 0.5 if commuters <= 4000 else 1.0
        # 10 000 kg at all car, 6 000 at none, and one kg per seed of noise.
        return FakeRound(total_kg=6000 + 4000 * share + seed, car_hours=hours)


class CalibrateTests(SimpleTestCase):
    def test_the_budget_is_the_half_driving_round_rounded(self):
        fake = FakeMap()
        result = calibration.calibrate(
            fake.play, commuters=4000, start=4000, smallest=64, seeds=(1, 2, 3)
        )
        self.assertEqual(result.commuters, 4000)
        self.assertAlmostEqual(result.budget_measured_kg, 8002)
        self.assertEqual(result.budget_kg, 8000)

    def test_the_share_is_the_difficulty_dial(self):
        fake = FakeMap()
        result = calibration.calibrate(
            fake.play, commuters=4000, start=4000, smallest=64, share=0.6, seeds=(1,)
        )
        self.assertEqual(result.budget_kg, 8400)
        self.assertIn(0.6, result.rows)

    def test_given_commuters_are_not_searched(self):
        fake = FakeMap()
        calibration.calibrate(
            fake.play, commuters=4000, start=4000, smallest=64, seeds=(1,)
        )
        self.assertTrue(all(way_home for *_, way_home in fake.calls))
        self.assertEqual({c for c, *_ in fake.calls}, {4000})

    def test_a_target_speed_is_searched_on_mornings_where_everybody_drives(self):
        fake = FakeMap()
        result = calibration.calibrate(
            fake.play, target_kmh=20, start=6400, smallest=64, seeds=(1,)
        )
        # 20 km/h up to 4 000 commuters, 10 above: the largest population
        # still at the target, rounded.
        self.assertEqual(result.commuters, 4000)
        searched = [call for call in fake.calls if not call[3]]
        self.assertTrue(searched)
        self.assertTrue(all(share == 1.0 for _, share, _, _ in searched))

    def test_every_share_of_the_table_is_measured_at_the_answer(self):
        fake = FakeMap()
        result = calibration.calibrate(
            fake.play, commuters=4000, start=4000, smallest=64, seeds=(1, 2)
        )
        self.assertEqual(sorted(result.rows), [0.0, 0.25, 0.5, 0.75, 1.0])
        self.assertTrue(all(len(rounds) == 2 for rounds in result.rows.values()))
        self.assertAlmostEqual(result.speed_kmh, 20.0)


def map_file():
    """The six-node map, with its one home and one workplace an hour's queue apart."""
    graph = small_map()
    graph["map"].update(district_commuters=640, co2_budget_kg_per_round=100)
    return graph


@override_settings(**TEST_BACKENDS)
class MapRoundsTests(TempMediaRootMixin, TestCase):
    """Rounds played for real on a small map, through the move endpoint's writer."""

    def setUp(self):
        self.host = create_host(is_staff=True)
        graph = map_file()
        with muted():
            self.game_map = MapImporter(self.host).run(
                {
                    "map_name": "Klein",
                    "json_file": ContentFile(json.dumps(graph).encode(), name="k.json"),
                    "image_file": None,
                    "description": "",
                    "max_players": 4,
                }
            )
        self.base = MapVersion.objects.get(game_map=self.game_map, base_version=True)
        self.node = {n.name: n.pk for n in self.game_map.node_set.all()}
        self.bus = BusLine.objects.get(game_map=self.game_map, name="1")
        self.bus_back = BusLine.objects.get(game_map=self.game_map, name="1 reverse")

    def leg(self, *steps):
        """A leg along named nodes: ("Wohnort", "A", "car"), ("A", "B", "bus") …"""
        segments, metres = [], 0.0
        for start, end, mode in steps:
            edge = Edge.objects.get(
                game_map=self.game_map,
                start_node_id=self.node[start],
                end_node_id=self.node[end],
                map_versions=self.base,
            )
            segment = {
                "edge_id": edge.pk,
                "start_node": self.node[start],
                "end_node": self.node[end],
                "mode": mode,
            }
            if mode == "bus":
                segment["pt_line_id"] = (self.bus if start == "A" else self.bus_back).pk
            segments.append(segment)
            metres += 1000
        return {
            "total_distance_m": metres,
            "estimated_time_min": 5.0,
            "segments": segments,
        }

    def routes(self, public=True):
        there = {
            "car": self.leg(
                ("Wohnort", "A", "car"), ("A", "B", "car"), ("B", "Arbeit", "car")
            ),
        }
        back = {
            "car": self.leg(
                ("Arbeit", "B", "car"), ("B", "A", "car"), ("A", "Wohnort", "car")
            ),
        }
        if public:
            there["public"] = self.leg(
                ("Wohnort", "A", "walk"), ("A", "B", "bus"), ("B", "Arbeit", "walk")
            )
            back["public"] = self.leg(
                ("Arbeit", "B", "walk"), ("B", "A", "bus"), ("A", "Wohnort", "walk")
            )
        else:
            there["public"] = back["public"] = {"error": "keine Linie"}
        return {
            "choice": {"carOptimization": "time", "ptOptimization": "fastest"},
            "commutes": [
                {
                    "home": self.node["Wohnort"],
                    "workplace": self.node["Arbeit"],
                    "there": there,
                    "back": back,
                }
            ],
        }

    def rounds(self, **routes):
        return MapRounds(self.game_map, self.base, self.routes(**routes), self.host)

    def play(self, rounds, **kwargs):
        kwargs.setdefault("commuters", 640)
        kwargs.setdefault("seed", 1)
        with muted():
            return rounds.play(**kwargs)

    def test_one_pair_carries_a_full_class_of_gruppen(self):
        rounds = self.rounds()
        self.assertEqual(rounds.gruppen, 64)
        self.assertEqual(rounds.people_per_gruppe(640), 10)

    def test_everybody_driving_is_cars_and_the_empty_timetable(self):
        measure = self.play(self.rounds(), share=1.0)
        self.assertEqual(measure.people, 640)
        self.assertGreater(measure.car_kg, 0)
        self.assertGreater(measure.timetable_kg, 0)
        self.assertIsNone(measure.pt_trip_min)
        self.assertAlmostEqual(measure.car_km, 64 * 3.0)
        self.assertGreater(measure.car_trip_min, 0)
        self.assertIsNotNone(measure.car_return_min)
        self.assertEqual(measure.not_home, 0)

    def test_nobody_driving_is_the_timetable_alone(self):
        measure = self.play(self.rounds(), share=0.0)
        self.assertEqual(measure.car_kg, 0)
        self.assertIsNone(measure.car_trip_min)
        self.assertGreater(measure.pt_trip_min, 0)
        self.assertAlmostEqual(measure.timetable_kg, measure.total_kg)

    def test_half_the_gruppen_drive_at_half(self):
        rounds = self.rounds()
        self.assertEqual(len(rounds.drivers(0.5, seed=1)), 32)
        measure = self.play(rounds, share=0.5)
        self.assertAlmostEqual(measure.car_km, 32 * 3.0)

    def test_a_morning_alone_has_no_way_home(self):
        rounds = self.rounds()
        both = self.play(rounds, share=1.0)
        morning = self.play(rounds, share=1.0, way_home=False)
        self.assertIsNone(morning.car_return_min)
        self.assertEqual(morning.car_trip_min, both.car_trip_min)
        self.assertLess(morning.total_kg, both.total_kg * 0.75)

    def test_more_commuters_are_a_slower_morning(self):
        rounds = self.rounds()
        light = self.play(rounds, share=1.0, commuters=64, way_home=False)
        heavy = self.play(rounds, share=1.0, commuters=1600, way_home=False)
        self.assertLess(heavy.car_km / heavy.car_hours, light.car_km / light.car_hours)

    def test_nothing_played_is_kept(self):
        self.play(self.rounds(), share=0.5)
        self.assertFalse(GameSession.objects.exists())
        self.assertFalse(Player.objects.exists())

    def test_a_pair_with_no_line_drives(self):
        measure = self.play(self.rounds(public=False), share=0.0)
        self.assertEqual(measure.switched, 64)
        self.assertAlmostEqual(measure.car_km, 64 * 3.0)

    def test_a_route_the_move_endpoint_refuses_is_not_measured(self):
        routes = self.routes()
        # The way there, ending one street short of work.
        routes["commutes"][0]["there"]["car"]["segments"].pop()
        rounds = MapRounds(self.game_map, self.base, routes, self.host)
        with self.assertRaises(RoutesRefused) as caught:
            self.play(rounds, share=1.0)
        self.assertIn("destination", str(caught.exception))
