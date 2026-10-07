"""Calibrating a map: the rule, the search, and rounds played on a real map.

The rule: a map's commuters are as many as make a round where everybody
drives as slow as the city's own rush hour. The budget is not the map's: it
is kg of CO2 per person per round, the same on every map, so what a map can
say about it is which car share the normal kg buys there.
`game/calibration.py` holds the rule, `game/measure.py` plays the rounds it
is measured on.

The search and the rule are tested on made-up rounds, where the answer is
known exactly. The rounds themselves are played on the six-node map from
`maps/tests/test_checks.py`, with routes written by hand — the game's router
is TypeScript, and the suite does not run Node.
"""

import json
from dataclasses import dataclass
from decimal import Decimal

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
    """Two significant figures: 6 837 commuters are 6 800."""

    def test_a_commuter_count_is_its_measurement_rounded(self):
        self.assertEqual(calibration.round_figure(6837), 6800)

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
        # 1.5 kg a head when nobody drives, 2.5 when everybody does, and a
        # kilogram per seed of noise over the whole round.
        return FakeRound(total_kg=commuters * (1.5 + share) + seed, car_hours=hours)


# Berlin Mitte-West at 6 800 commuters, kg per person per round, there and
# back (docs/kalibrierung.md §13).
BERLIN = {1.0: 4.17, 0.75: 3.16, 0.5: 2.41, 0.25: 1.96, 0.0: 1.53}


class NormalTests(SimpleTestCase):
    """What a game is played against: kg per person per round, one dial."""

    def test_normal_is_berlins_half_driving_round_rounded_to_the_step(self):
        """2.41 kg a head is what a round costs on Berlin Mitte-West when half
        the Gruppen drive. Rounded to the dial's step, that is normal."""
        half = Decimal(str(BERLIN[0.5]))
        step = calibration.CO2_KG_PER_PERSON_STEP

        self.assertEqual(
            calibration.CO2_KG_PER_PERSON_NORMAL,
            (half / step).quantize(Decimal(1)) * step,
        )
        self.assertEqual(calibration.CO2_KG_PER_PERSON_NORMAL, Decimal("2.4"))

    def test_the_dial_goes_in_steps_of_two_hundred_grams(self):
        choices = calibration.co2_kg_per_person_choices()

        self.assertEqual(choices[0], calibration.CO2_KG_PER_PERSON_MIN)
        self.assertEqual(choices[-1], calibration.CO2_KG_PER_PERSON_MAX)
        self.assertEqual(
            {b - a for a, b in zip(choices, choices[1:])}, {Decimal("0.2")}
        )
        self.assertIn(calibration.CO2_KG_PER_PERSON_NORMAL, choices)

    def test_the_dial_spans_more_than_berlin_does(self):
        """Below what a round costs when nobody drives, above what it costs
        when everybody does: a host can make the game unwinnable or free."""
        self.assertLess(calibration.CO2_KG_PER_PERSON_MIN, Decimal(str(BERLIN[0.0])))
        self.assertGreater(calibration.CO2_KG_PER_PERSON_MAX, Decimal(str(BERLIN[1.0])))


class CarShareTests(SimpleTestCase):
    """Which car share a kg per person buys on a map, read off its table."""

    def test_normal_buys_half_the_cars_on_berlin(self):
        share = calibration.car_share_at(Decimal("2.4"), BERLIN)
        # Between 25 % (1.96) and 50 % (2.41), just short of the half.
        self.assertAlmostEqual(share, 0.25 + 0.25 * (2.4 - 1.96) / (2.41 - 1.96))
        self.assertAlmostEqual(share, 0.494, places=3)

    def test_a_row_of_the_table_is_its_share(self):
        self.assertAlmostEqual(calibration.car_share_at(Decimal("3.16"), BERLIN), 0.75)

    def test_more_than_everybody_driving_is_everybody(self):
        self.assertEqual(calibration.car_share_at(Decimal("5.0"), BERLIN), 1.0)

    def test_less_than_nobody_driving_buys_nothing(self):
        """The timetable runs whether anybody rides or not."""
        self.assertIsNone(calibration.car_share_at(Decimal("1.4"), BERLIN))


class CalibrateTests(SimpleTestCase):
    def test_the_table_is_per_commuter(self):
        """Per head of the map's commuters: the figure the budget is held to."""
        fake = FakeMap()
        result = calibration.calibrate(
            fake.play, commuters=4000, start=4000, smallest=64, seeds=(1, 2, 3)
        )
        self.assertEqual(result.commuters, 4000)
        self.assertAlmostEqual(result.per_person[0.5], 2.0 + 2 / 4000)
        self.assertAlmostEqual(result.per_person[1.0], 2.5 + 2 / 4000)

    def test_it_says_which_car_share_normal_buys(self):
        fake = FakeMap()
        result = calibration.calibrate(
            fake.play, commuters=4000, start=4000, smallest=64, seeds=(1,)
        )
        # 1.5 + share = 2.4, less the noise.
        self.assertAlmostEqual(result.normal_share, 0.9, places=3)

    def test_there_is_no_budget_to_measure(self):
        """The budget is the dial's, not the map's: no `--share`, no figure."""
        fake = FakeMap()
        result = calibration.calibrate(
            fake.play, commuters=4000, start=4000, smallest=64, seeds=(1,)
        )
        self.assertFalse(hasattr(result, "budget_kg"))
        with self.assertRaises(TypeError):
            calibration.calibrate(
                fake.play, commuters=4000, start=4000, smallest=64, share=0.6
            )

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
        self.assertEqual(sorted(result.per_person), [0.0, 0.25, 0.5, 0.75, 1.0])
        self.assertTrue(all(len(rounds) == 2 for rounds in result.rows.values()))
        self.assertAlmostEqual(result.speed_kmh, 20.0)


def map_file():
    """The six-node map, with its one home and one workplace an hour's queue apart."""
    graph = small_map()
    graph["map"].update(district_commuters=640)
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
