"""Which lines a map carries, and their intervals."""

from django.test import SimpleTestCase

from mapbuild import lines, timetable


def rel(rid, ref, route="bus", **tags):
    return {"id": rid, "tags": {"route": route, "ref": ref, **tags}, "members": []}


def stops(*names, y=0):
    return [(n, (1000 * i, y)) for i, n in enumerate(names)]


class ModeTests(SimpleTestCase):
    def test_modes(self):
        self.assertEqual(lines.mode({"route": "subway"}), "U-Bahn")
        self.assertEqual(lines.mode({"route": "light_rail"}), "S-Bahn (light_rail)")
        self.assertEqual(
            lines.mode({"route": "train", "ref": "RE 1"}), "train: regional / S"
        )
        self.assertEqual(
            lines.mode({"route": "train", "ref": "ICE 5"}), "train: long distance"
        )
        self.assertEqual(lines.mode({"route": "bus", "ref": "N7"}), "night")
        self.assertEqual(lines.mode({"route": "trolleybus"}), "bus")

    def test_osm_intervals(self):
        self.assertEqual(lines.minutes("10"), 10)
        self.assertEqual(lines.minutes("00:10"), 10)
        self.assertEqual(lines.minutes("01:00"), 60)
        self.assertEqual(lines.minutes("5-10"), 5)
        self.assertIsNone(lines.minutes("on demand"))


class RouteTests(SimpleTestCase):
    def test_one_route_per_direction_the_longest_variant(self):
        stops_of = {
            1: stops("A", "B", "C", "D"),
            2: stops("A", "B", "C"),
            3: stops("D", "C", "B", "A"),
            4: stops("C", "B"),
        }
        rs = [rel(1, "7"), rel(2, "7"), rel(3, "7"), rel(4, "7")]
        self.assertEqual([r["id"] for r in lines.routes(rs, stops_of)], [1, 3])

    def test_a_loop_has_one(self):
        stops_of = {1: stops("A", "B", "C", "D", "A")}
        self.assertEqual([r["id"] for r in lines.routes([rel(1, "58")], stops_of)], [1])

    def test_a_ring_filed_as_two_lines_is_one_line_each_way(self):
        ring = ("Südkreuz", "Tempelhof", "Neukölln", "Treptower Park")
        stops_of = {1: stops(*ring), 2: stops(*reversed(ring))}
        ls = {
            ("S-Bahn (light_rail)", "S41"): [rel(1, "S41")],
            ("S-Bahn (light_rail)", "S42"): [rel(2, "S42")],
        }
        self.assertEqual(
            lines.way_back(ls, stops_of)[("S-Bahn (light_rail)", "S41")],
            ("S-Bahn (light_rail)", "S42"),
        )


class CoverTests(SimpleTestCase):
    places = {"home": [(0, 0), (5000, 0)], "workplace": [(10000, 0)]}

    def test_rail_first_then_only_what_brings_a_new_place_within_reach(self):
        ls = {
            ("bus", "100"): [rel(1, "100")],
            ("U-Bahn", "U2"): [rel(2, "U2", route="subway")],
            ("tram", "M10"): [rel(3, "M10", route="tram")],
        }
        stops_of = {
            1: [("a", (0, 0)), ("b", (5000, 0)), ("c", (10000, 0))],
            2: [("a", (0, 100)), ("c", (10000, 100))],
            3: [("b", (5000, 100)), ("x", (6000, 100))],
        }
        self.assertEqual(
            lines.cover(ls, stops_of, self.places), [("U-Bahn", "U2"), ("tram", "M10")]
        )

    def test_night_and_long_distance_lines_are_never_kept(self):
        ls = {
            ("night", "N1"): [rel(1, "N1")],
            ("train: long distance", "ICE"): [rel(2, "ICE", route="train")],
        }
        stops_of = {
            1: [("a", (0, 0)), ("b", (5000, 0))],
            2: [("c", (10000, 0)), ("a", (0, 0))],
        }
        self.assertEqual(lines.cover(ls, stops_of, self.places), [])

    def test_the_timetables_line_only_where_osm_has_none(self):
        ls = {
            ("bus", "1"): [rel(1, "1")],
            ("bus", "2"): [rel(2, "2", source="timetable")],
        }
        stops_of = {
            1: [("a", (0, 0)), ("b", (5000, 0))],
            2: [("a", (0, 0)), ("b", (5000, 0)), ("c", (10000, 0))],
        }
        self.assertEqual(
            lines.cover(ls, stops_of, self.places), [("bus", "1"), ("bus", "2")]
        )


class IntervalTests(SimpleTestCase):
    def test_departures_in_two_hours_to_the_games_minutes(self):
        self.assertEqual(timetable.game_interval(6), 20)
        self.assertEqual(timetable.game_interval(12), 10)
        self.assertEqual(timetable.game_interval(24), 5)

    def test_no_run_in_the_window_plays_one_a_pass(self):
        self.assertEqual(timetable.game_interval(0), 120)

    def test_the_timetable_else_osm_else_the_default(self):
        d = {
            "lines": {
                ("bus", "1"): [rel(1, "1", interval="15")],
                ("bus", "2"): [rel(2, "2")],
            }
        }
        self.assertEqual(
            timetable.rule(None, d, [("bus", "1"), ("bus", "2")]),
            {("bus", "1"): (15, "OSM"), ("bus", "2"): (20, "default")},
        )

    def test_a_station_counts_a_trip_once_and_a_trips_last_stop_is_no_departure(self):
        stops = {
            "s1": ["A", 0, 0, "A"],
            "s2": ["B", 0, 0.01, "B"],
            "s3": ["C", 0, 0.02, "C"],
        }
        at = lambda h, m: h * 3600 + m * 60  # noqa: E731
        trips = {
            "t1": [[1, "s1", at(8, 0)], [2, "s2", at(8, 5)], [3, "s3", at(8, 10)]],
            "t2": [[1, "s1", at(8, 30)], [2, "s2", at(8, 35)], [3, "s3", at(8, 40)]],
            "t3": [[1, "s1", at(10, 30)], [2, "s2", at(10, 35)], [3, "s3", at(10, 40)]],
        }
        timetable.geo.use((-0.1, -0.1, 0.1, 0.1))
        c = timetable.counts(trips, stops, lambda p: True)
        self.assertEqual(dict(c[0]), {"A": 2, "B": 2})
