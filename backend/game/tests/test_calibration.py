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

import datetime
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from game import calibration
from game.management.commands.calibrate_map import Command, calibrated_file
from game.measure import MapRounds, RoutesRefused, every_pair, version_graph
from game.measure_workers import Workers
from game.models import GameSession, Player
from game.tests._helpers import TEST_BACKENDS, TempMediaRootMixin, create_host, muted
from maps.importer import MapImporter
from maps.models import BusLine, Edge, MapVersion
from maps.tests.test_checks import small_map
from maps.tests.test_example_map import SHIPPED_MAP

MEASURED_AT = datetime.datetime(2026, 10, 20, 9, 0, tzinfo=datetime.timezone.utc)


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
    car_kg: float = 0.0
    base_kg: float = 0.0
    average_kg: float = 0.0
    cost_eur: float = 0.0
    car_cost_eur: float = 0.0

    @property
    def timetable_kg(self):
        return self.total_kg - self.car_kg

    @property
    def timetable_cost_eur(self):
        return self.cost_eur - self.car_cost_eur


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
# back, the class paying its share of the timetable (docs/kalibrierung.md §16).
BERLIN = {1.0: 3.62, 0.75: 2.65, 0.5: 1.86, 0.25: 1.28, 0.0: 0.73}


class NormalTests(SimpleTestCase):
    """What a game is played against: kg per person per round, one dial."""

    def test_normal_is_a_commute_inside_germanys_2030_target(self):
        """A commute trip emitted 2.42 kg in 2017 (UBA, Texte 224/2020,
        Tab. 4), so 4.84 there and back. The climate law gives transport 85 Mt
        in 2030 (KSG, Anlage 2a) against 168 in 2017 (UBA). Cut by as much, a
        commuter's day is 2.45 kg; on the dial's step, 2.4."""
        day = Decimal("2.42") * 2 * Decimal(85) / Decimal(168)
        step = calibration.CO2_KG_PER_PERSON_STEP

        self.assertEqual(
            calibration.CO2_KG_PER_PERSON_NORMAL,
            (day / step).quantize(Decimal(1)) * step,
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

    def test_normal_buys_two_thirds_of_the_cars_on_berlin(self):
        share = calibration.car_share_at(Decimal("2.4"), BERLIN)
        # Between 50 % (1.86) and 75 % (2.65).
        self.assertAlmostEqual(share, 0.5 + 0.25 * (2.4 - 1.86) / (2.65 - 1.86))
        self.assertAlmostEqual(share, 0.671, places=3)

    def test_a_row_of_the_table_is_its_share(self):
        self.assertAlmostEqual(calibration.car_share_at(Decimal("2.65"), BERLIN), 0.75)

    def test_more_than_everybody_driving_is_everybody(self):
        self.assertEqual(calibration.car_share_at(Decimal("5.0"), BERLIN), 1.0)

    def test_less_than_nobody_driving_buys_nothing(self):
        """The timetable runs whether anybody rides or not."""
        self.assertIsNone(calibration.car_share_at(Decimal("0.6"), BERLIN))


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

    def test_the_rounds_of_a_step_are_played_together(self):
        """Every seed of a count the search tries, every share and seed of the
        table: nothing in a step waits for another of its rounds."""
        fake = FakeMap()
        steps = []

        def play_many(jobs):
            steps.append(jobs)
            return [fake.play(**job) for job in jobs]

        result = calibration.calibrate(
            fake.play,
            play_many=play_many,
            target_kmh=20,
            start=6400,
            smallest=64,
            seeds=(1, 2, 3),
        )
        *search, table = steps
        self.assertTrue(search)
        for jobs in search:
            self.assertEqual([job["seed"] for job in jobs], [1, 2, 3])
            self.assertEqual(len({job["commuters"] for job in jobs}), 1)
        self.assertEqual(len(table), 15)
        alone = calibration.calibrate(
            FakeMap().play, target_kmh=20, start=6400, smallest=64, seeds=(1, 2, 3)
        )
        self.assertEqual(result, alone)


class TimetableMap:
    """Rounds with a timetable: the base one emits 1 000 kg, the riders' km
    at Germany's occupancy 400 kg when half drive, the cars 2 kg a head."""

    def play(self, *, commuters, share, seed, way_home=True):
        car = 2.0 * commuters * share
        return FakeRound(
            total_kg=car + 1200.0,
            car_kg=car,
            base_kg=1000.0,
            average_kg=400.0 + seed if share == 0.5 else 0.0,
        )


class TimetableFactorTests(SimpleTestCase):
    """The share of the timetable the class pays (`GameMap.timetable_factor`).

    What the class's riders would emit at the occupancy Germany's buses and
    trains really run at, over what the map's base timetable emits, on the
    map's round where half the Gruppen drive. The riders the game does not
    have fill the seats it does.
    """

    def test_it_is_the_riders_at_germanys_occupancy_over_the_base_timetable(self):
        rounds = [FakeRound(total_kg=0, base_kg=5729.0, average_kg=2725.0)]

        self.assertEqual(calibration.timetable_factor(rounds), 0.48)

    def test_over_seeds_it_is_the_sums(self):
        rounds = [
            FakeRound(total_kg=0, base_kg=1000.0, average_kg=300.0),
            FakeRound(total_kg=0, base_kg=1000.0, average_kg=500.0),
        ]

        self.assertEqual(calibration.timetable_factor(rounds), 0.4)

    def test_two_figures_like_the_commuters(self):
        rounds = [FakeRound(total_kg=0, base_kg=76729.0, average_kg=1565.0)]

        self.assertEqual(calibration.timetable_factor(rounds), 0.02)

    def test_never_more_than_the_whole_timetable(self):
        """Buses fuller than Germany's would charge more than they emit."""
        rounds = [FakeRound(total_kg=0, base_kg=100.0, average_kg=150.0)]

        self.assertEqual(calibration.timetable_factor(rounds), 1.0)

    def test_nothing_to_measure_says_so(self):
        """No timetable, or nobody on it: there is no share to read off."""
        for base, average in ((0.0, 0.0), (100.0, 0.0)):
            with self.subTest(base=base, average=average):
                rounds = [FakeRound(total_kg=0, base_kg=base, average_kg=average)]
                self.assertIsNone(calibration.timetable_factor(rounds))

    def test_calibrate_measures_it_where_half_the_gruppen_drive(self):
        result = calibration.calibrate(
            TimetableMap().play, commuters=1000, start=1000, smallest=64, seeds=(1, 2)
        )

        # (401 + 402) / (1 000 + 1 000)
        self.assertEqual(result.timetable_factor, 0.4)

    def test_the_table_is_what_the_class_pays(self):
        """The cars, and the factor's share of the timetable as it ran."""
        result = calibration.calibrate(
            TimetableMap().play, commuters=1000, start=1000, smallest=64, seeds=(1,)
        )

        self.assertEqual(result.timetable_factor, 0.4)
        self.assertAlmostEqual(result.per_person[1.0], (2000 + 0.4 * 1200) / 1000)
        self.assertAlmostEqual(result.per_person[0.0], 0.4 * 1200 / 1000)

    def test_the_cost_a_head_is_paid_the_same_way_as_the_kg(self):
        """The cars' cost, and the share's part of the timetable's."""
        rows = {
            share: [
                FakeRound(
                    total_kg=0,
                    base_kg=1000,
                    average_kg=400,
                    cost_eur=500,
                    car_cost_eur=200,
                )
            ]
            for share in calibration.TABLE_SHARES
        }
        result = calibration.Calibration(
            commuters=1000, target_kmh=None, speed_kmh=None, rows=rows
        )

        self.assertEqual(result.timetable_factor, 0.4)
        self.assertAlmostEqual(result.cost_per_person[0.5], (200 + 0.4 * 300) / 1000)

    def test_without_a_share_the_cost_is_the_rounds_as_played(self):
        rows = {0.5: [FakeRound(total_kg=0, cost_eur=500, car_cost_eur=200)]}
        result = calibration.Calibration(
            commuters=1000, target_kmh=None, speed_kmh=None, rows=rows
        )

        self.assertIsNone(result.timetable_factor)
        self.assertAlmostEqual(result.cost_per_person[0.5], 0.5)

    def test_without_a_share_the_table_is_the_rounds_as_played(self):
        result = calibration.calibrate(
            FakeMap().play, commuters=4000, start=4000, smallest=64, seeds=(1,)
        )

        self.assertIsNone(result.timetable_factor)
        self.assertAlmostEqual(result.per_person[1.0], 2.5 + 1 / 4000)


class CalibratedFileTests(SimpleTestCase):
    """What `calibrate_map --out` writes into its copy of the file."""

    def result(self, factor_kg):
        return calibration.Calibration(
            commuters=6800,
            target_kmh=19.0,
            speed_kmh=19.1,
            rows={0.5: [FakeRound(total_kg=0, base_kg=5729.0, average_kg=factor_kg)]},
        )

    def test_the_count_the_flag_and_the_share(self):
        graph = {"map": {"name": "Karte", "co2_budget_kg_per_round": 16000}}

        written = calibrated_file(graph, self.result(2725.0), MEASURED_AT)

        self.assertEqual(written["map"]["district_commuters"], 6800)
        self.assertEqual(written["map"]["calibrated_at"], MEASURED_AT.isoformat())
        self.assertNotIn("calibrated", written["map"])
        self.assertEqual(written["map"]["timetable_factor"], 0.48)
        self.assertNotIn("co2_budget_kg_per_round", written["map"])

    def test_a_share_it_could_not_measure_leaves_the_files_own(self):
        graph = {"map": {"name": "Karte", "timetable_factor": 0.3}}

        written = calibrated_file(graph, self.result(0.0), MEASURED_AT)

        self.assertEqual(written["map"]["timetable_factor"], 0.3)


class Co2TableTests(SimpleTestCase):
    """The table on the map: share in whole percent → kg a head, two decimals."""

    def test_keys_are_whole_percent_values_are_rounded_kg(self):
        table = calibration.co2_table({1.0: 3.6249, 0.75: 2.651, 0.0: 0.7349})

        self.assertEqual(table, {"100": 3.62, "75": 2.65, "0": 0.73})

    def test_a_clean_table_stays_as_it_is(self):
        table = {"100": 3.62, "50": 1.86, "0": 0.73}

        self.assertEqual(calibration.clean_co2_table(table), table)

    def test_anything_that_is_no_table_is_none(self):
        for value in (None, [], "viel", {}, {"101": 1.0}, {"-5": 1.0}, {"a": 1.0}):
            with self.subTest(value=value):
                self.assertIsNone(calibration.clean_co2_table(value))

    def test_a_row_that_is_no_number_spoils_the_table(self):
        for kg in (-0.1, "3", None, True, float("nan")):
            with self.subTest(kg=kg):
                self.assertIsNone(calibration.clean_co2_table({"50": kg}))


class CalibratedTableTests(SimpleTestCase):
    def test_the_file_gets_the_table(self):
        result = calibration.Calibration(
            commuters=1000,
            target_kmh=19.0,
            speed_kmh=19.1,
            rows={
                1.0: [FakeRound(total_kg=3000.0, car_kg=2000.0)],
                0.0: [FakeRound(total_kg=1000.0, car_kg=0.0)],
            },
        )

        written = calibrated_file({"map": {}}, result, MEASURED_AT)

        self.assertEqual(written["map"]["co2_table"], {"100": 3.0, "0": 1.0})


@dataclass(frozen=True)
class ReportedRound(FakeRound):
    """A round with everything the command's table prints."""

    car_trip_min: float | None = 20.0
    car_return_min: float | None = 20.0
    pt_trip_min: float | None = None
    pt_wait_min: float | None = None
    switched: int = 0


class ReportTests(SimpleTestCase):
    """What `calibrate_map` prints once the rounds are played."""

    class Rounds:
        gruppen = 72

        def people_per_gruppe(self, commuters):
            return commuters // 72

    def _report(self, rows, speed_kmh):
        from io import StringIO

        result = calibration.Calibration(
            commuters=7200,
            target_kmh=19.0,
            speed_kmh=speed_kmh,
            searched={7200: 19.4, 14400: None},
            rows=rows,
        )
        command = Command(stdout=StringIO())
        command._report({"map": {}}, self.Rounds(), result)
        return command.stdout.getvalue()

    def test_a_table_where_someone_never_got_home_is_reported_not_a_crash(self):
        """The search measures mornings; the table plays there and back. A way
        home that ran into the tick guard leaves the round without a speed,
        and the report said so by raising on the missing number — after an
        hour of Berlin, with nothing written."""
        rows = {
            share: [ReportedRound(total_kg=7200 * (1 + share), not_home=0)]
            for share in calibration.TABLE_SHARES
        }
        rows[1.0] = [ReportedRound(total_kg=14400, not_home=368)]

        out = self._report(rows, speed_kmh=None)

        self.assertIn("Pendler: 7.200 — alle im Auto: nicht alle angekommen", out)
        self.assertIn("Nicht alle sind angekommen", out)

    def test_the_table_prints_what_a_head_pays(self):
        rows = {
            share: [ReportedRound(total_kg=7200, cost_eur=3600, car_cost_eur=1800)]
            for share in calibration.TABLE_SHARES
        }

        out = self._report(rows, speed_kmh=19.0)

        self.assertIn("€ pro Person", out)
        self.assertIn("0,50 €", out)


class NotPlayableTests(SimpleTestCase):
    def test_a_budget_below_the_empty_round_cannot_be_won(self):
        table = {1.0: 3.0, 0.0: 1.0}

        self.assertEqual(calibration.playable(0.6, table), "unwinnable")
        self.assertEqual(calibration.playable(6.0, table), "unlosable")
        self.assertIsNone(calibration.playable(2.4, table))


def map_file():
    """The six-node map, with its one home and one workplace an hour's queue apart."""
    graph = small_map()
    graph["map"].update(district_commuters=640)
    return graph


@override_settings(**TEST_BACKENDS)
def commutes(homes, workplaces):
    """Every home to every workplace, as the router lists them; no legs."""
    return {
        "choice": {"carOptimization": "time", "ptOptimization": "fastest"},
        "commutes": [
            {"home": home, "workplace": workplace, "there": {}, "back": {}}
            for home in range(1, homes + 1)
            for workplace in range(101, 101 + workplaces)
        ],
    }


class DealTests(SimpleTestCase):
    """Which Gruppen a round plays: every pair, or the workplaces dealt to each
    home for its seed, when a map has more of them than a home plays."""

    def rounds(self, homes, workplaces, per_home):
        return MapRounds(None, None, commutes(homes, workplaces), None, per_home)

    def dealt(self, rounds, seed=1, share=1.0):
        return {
            home: [rounds.commutes[index]["workplace"] for index, _ in gruppen]
            for home, gruppen in rounds.gruppen_at(share, seed).items()
        }

    def test_a_home_plays_every_workplace_while_it_can(self):
        rounds = self.rounds(3, 5, per_home=5)
        # 15 pairs, five Gruppen each: a full class
        self.assertEqual(rounds.gruppen, 75)
        for workplaces in self.dealt(rounds).values():
            self.assertEqual(Counter(workplaces), {w: 5 for w in range(101, 106)})

    def test_with_more_workplaces_each_home_is_dealt_its_own(self):
        rounds = self.rounds(32, 5, per_home=2)
        self.assertEqual(rounds.gruppen, 64)
        dealt = self.dealt(rounds)
        self.assertEqual(sorted(dealt), list(range(1, 33)))
        for workplaces in dealt.values():
            self.assertEqual(len(set(workplaces)), 2)

    def test_a_few_homes_still_play_a_full_class(self):
        rounds = self.rounds(5, 46, per_home=4)
        self.assertEqual(rounds.gruppen, 65)
        for workplaces in self.dealt(rounds).values():
            self.assertEqual(len(set(workplaces)), 13)

    def test_every_workplace_is_dealt_as_often_as_the_others(self):
        # 96 Gruppen on five workplaces: 19 or 20 each
        rounds = self.rounds(32, 5, per_home=3)
        for seed in range(1, 21):
            counts = Counter(w for ws in self.dealt(rounds, seed).values() for w in ws)
            self.assertEqual(set(counts), set(range(101, 106)))
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_each_seed_deals_anew_and_the_same_seed_alike(self):
        rounds = self.rounds(32, 9, per_home=2)
        self.assertEqual(self.dealt(rounds, 1), self.dealt(rounds, 1))
        self.assertNotEqual(self.dealt(rounds, 1), self.dealt(rounds, 2))

    def test_over_many_seeds_every_pair_is_played_alike(self):
        rounds = self.rounds(32, 5, per_home=2)
        played = Counter(
            (home, w)
            for seed in range(600)
            for home, ws in self.dealt(rounds, seed).items()
            for w in ws
        )
        # 600 rounds, two of five workplaces each: 240 a pair
        self.assertEqual(len(played), 160)
        for count in played.values():
            self.assertAlmostEqual(count, 240, delta=40)

    def test_only_the_pairs_the_seeds_deal_are_routed(self):
        rounds = self.rounds(32, 9, per_home=2)
        dealt = {
            (home, workplace)
            for seed in (1, 2)
            for home, workplaces in self.dealt(rounds, seed).items()
            for workplace in workplaces
        }
        played = rounds.played((1, 2))
        self.assertEqual({tuple(pair) for pair in played}, dealt)
        self.assertEqual(played, sorted(played))
        self.assertLess(len(played), 32 * 9)

    def test_a_map_played_pair_by_pair_routes_every_pair(self):
        rounds = self.rounds(3, 5, per_home=5)
        self.assertEqual(len(rounds.played((1, 2, 3))), 15)

    def test_the_commuters_are_spread_over_the_dealt_gruppen(self):
        rounds = self.rounds(32, 5, per_home=2)
        self.assertEqual(rounds.people_per_gruppe(6400), 100)

    def test_every_home_drives_its_share(self):
        rounds = self.rounds(16, 9, per_home=4)
        for seed in range(1, 6):
            for gruppen in rounds.gruppen_at(0.5, seed).values():
                self.assertEqual(sum(mode == "car" for _, mode in gruppen), 2)


class EveryPairTests(SimpleTestCase):
    def test_in_the_routers_order_homes_outer_both_by_id(self):
        """As `routeCommutes` lists them, so a deal drawn over this list is the
        deal drawn over the router's."""

        def node(pk, *types):
            return {"id": pk, "node_type": [{"id": 1, "name": t} for t in types]}

        graph = {
            "nodes": [
                node(9, "workplace"),
                node(4, "home"),
                node(7),
                node(2, "home"),
                node(5, "workplace"),
            ]
        }
        commutes = every_pair(graph)["commutes"]
        self.assertEqual(
            [(c["home"], c["workplace"]) for c in commutes],
            [(2, 5), (2, 9), (4, 5), (4, 9)],
        )
        self.assertTrue(all(c["there"] == c["back"] == {} for c in commutes))


class DealtUnlessToldTests(SimpleTestCase):
    """`calibrate_map` without `--per-home`: four workplaces a home, the
    cheapest deal measured and no noisier than seven or fourteen
    (docs/kalibrierung.md, section 15)."""

    def per_home(self, *argv):
        parser = Command().create_parser("manage.py", "calibrate_map")
        return parser.parse_args(["karte.json", "--speed", "19", *argv]).per_home

    def test_a_home_is_dealt_four_workplaces(self):
        self.assertEqual(self.per_home(), 4)
        self.assertEqual(self.per_home("--per-home", "7"), 7)

    def test_the_shipped_map_still_plays_every_pair(self):
        graph = json.loads(SHIPPED_MAP.read_text(encoding="utf-8"))
        homes, workplaces = (
            sum(kind in node["types"] for node in graph["nodes"])
            for kind in ("home", "workplace")
        )
        rounds = MapRounds(
            None, None, commutes(homes, workplaces), None, self.per_home()
        )
        self.assertFalse(rounds.dealt)


class SmallMapRounds:
    """The six-node map imported, and its one commute written by hand."""

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


class MapRoundsTests(SmallMapRounds, TempMediaRootMixin, TestCase):
    """Rounds played for real on a small map, through the move endpoint's writer."""

    def test_routed_after_the_deal_it_plays_as_routed_whole(self):
        rounds = MapRounds(
            self.game_map,
            self.base,
            every_pair(version_graph(self.game_map, self.base)),
            self.host,
        )
        pair = [self.node["Wohnort"], self.node["Arbeit"]]
        self.assertEqual(rounds.played(calibration.SEEDS), [pair])
        rounds.route(self.routes())
        self.assertEqual(
            self.play(rounds, share=0.5), self.play(self.rounds(), share=0.5)
        )

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

    def test_a_round_says_what_its_riders_emit_at_germanys_occupancy(self):
        """Read off the lines as they ran, there and back: the riders'
        person-km at UBA's g per person-km, and the base timetable, whole."""
        nobody = self.play(self.rounds(), share=0.0)
        everybody = self.play(self.rounds(), share=1.0)

        there = Edge.objects.get(
            game_map=self.game_map,
            start_node_id=self.node["A"],
            end_node_id=self.node["B"],
            map_versions=self.base,
        )
        back = Edge.objects.get(
            game_map=self.game_map,
            start_node_id=self.node["B"],
            end_node_id=self.node["A"],
            map_versions=self.base,
        )
        scale = self.game_map.scale
        person_km = 640 * (there.length_m(scale) + back.length_m(scale)) / 1000
        self.assertAlmostEqual(nobody.average_kg, 90.0 * person_km / 1000)
        self.assertEqual(everybody.average_kg, 0)
        self.assertGreater(nobody.base_kg, 0)
        self.assertAlmostEqual(everybody.base_kg, nobody.base_kg)
        self.assertLessEqual(nobody.base_kg, nobody.timetable_kg)

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


class SideBySideTests(SmallMapRounds, TempMediaRootMixin, TransactionTestCase):
    """Rounds played by worker processes, as `calibrate_map --workers` does."""

    def test_workers_play_the_rounds_one_process_plays(self):
        rounds = self.rounds()
        jobs = [
            dict(commuters=640, share=0.5, seed=1),
            dict(commuters=640, share=1.0, seed=2, way_home=False),
        ]
        with muted(), Workers(rounds, 2) as workers:
            together = workers.play(jobs)
        self.assertEqual(together, [self.play(rounds, **job) for job in jobs])
