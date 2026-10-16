"""One test per heads-up line of the build report, on inputs made by hand."""

from django.test import SimpleTestCase

from mapbuild import report

REACH = 1000


class NoTransportTests(SimpleTestCase):
    def test_a_place_with_no_stop_in_reach_is_named_with_a_version_to_suggest(self):
        places = [("Nah", (0, 0)), ("Fern", (5000, 0))]

        line = report.no_transport(places, [(300, 0)], REACH, has_feed=True)

        self.assertIsNotNone(line)
        self.assertIn("1 Orte ohne Halt", line)
        self.assertIn("Fern 4700 m", line)
        self.assertNotIn("Nah", line)
        self.assertIn("im Fahrplan keine, die einspringen könnte", line)
        self.assertIn("Vorschlag: eine Version", line)

    def test_without_a_timetable_it_says_so(self):
        line = report.no_transport([("Fern", (5000, 0))], [], REACH, has_feed=False)

        self.assertIn("keinen Fahrplan", line)

    def test_nothing_to_say_when_everybody_is_served(self):
        self.assertIsNone(
            report.no_transport([("Nah", (0, 0))], [(300, 0)], REACH, True)
        )


class SnappedAwayTests(SimpleTestCase):
    def test_a_stop_that_moved_out_of_reach_names_its_place(self):
        places = [("Rand", (0, 0)), ("Mitte", (0, 2000))]
        raw = [(950, 0), (0, 2000)]
        final = [(1050, 0), (0, 2000)]

        line = report.snapped_away(places, raw, final, REACH)

        self.assertIn("Rand 1050 m", line)
        self.assertNotIn("Mitte", line)
        self.assertIn("Vorschlag: eine Version", line)

    def test_a_place_no_stop_ever_served_is_not_this_lines_business(self):
        self.assertIsNone(
            report.snapped_away([("Fern", (0, 0))], [(5000, 0)], [(5000, 0)], REACH)
        )


class FarOnFootTests(SimpleTestCase):
    def graph(self, circuity):
        nodes = [
            {"id": "stop", "x": 0.0, "y": 0.0},
            {"id": "home", "x": 0.6, "y": 0.0},
        ]
        edges = [
            {"start_node": "home", "end_node": "stop", "circuity": circuity},
            {"start_node": "stop", "end_node": "home", "circuity": circuity},
        ]
        return nodes, edges

    def test_the_walk_follows_the_graph_not_the_crow(self):
        nodes, edges = self.graph(circuity=2.0)

        line = report.far_on_foot(nodes, edges, {"stop"}, [("Zuhause", "home")], REACH)

        self.assertIsNotNone(line)
        self.assertIn("1 Orte", line)
        self.assertIn("Zuhause", line)
        self.assertIn("Vorschlag: eine Version", line)

    def test_a_short_walk_says_nothing(self):
        nodes, edges = self.graph(circuity=1.2)

        self.assertIsNone(
            report.far_on_foot(nodes, edges, {"stop"}, [("Zuhause", "home")], REACH)
        )

    def test_a_link_nobody_walks_is_no_way(self):
        nodes, edges = self.graph(circuity=1.0)
        for e in edges:
            e["walking"] = False

        self.assertIsNotNone(
            report.far_on_foot(nodes, edges, {"stop"}, [("Zuhause", "home")], REACH)
        )

    def test_a_one_way_street_is_walked_the_way_it_goes(self):
        nodes, edges = self.graph(circuity=1.0)
        edges = [e for e in edges if e["start_node"] == "stop"]  # no way to the stop

        self.assertIsNotNone(
            report.far_on_foot(nodes, edges, {"stop"}, [("Zuhause", "home")], REACH)
        )


class NoMorningTripTests(SimpleTestCase):
    def test_a_matched_line_with_no_trip_is_named(self):
        found = {
            ("bus", "80"): dict(n=0, matched=True),
            ("bus", "22"): dict(n=6, matched=True),
            ("bus", "99"): dict(n=0, matched=False),
        }

        line = report.no_morning_trip(found)

        self.assertIn("1 Linien", line)
        self.assertIn("80", line)
        self.assertNotIn("22", line)
        self.assertNotIn("99", line)
        self.assertIn("Vorschlag: eine Version", line)

    def test_nothing_to_say_when_every_line_has_a_trip(self):
        self.assertIsNone(
            report.no_morning_trip({("bus", "22"): dict(n=6, matched=True)})
        )


class OneBusTests(SimpleTestCase):
    stops = {
        ("bus", "80"): [(0, 0)],
        ("bus", "22"): [(5000, 0)],
        ("tram", "1"): [(5000, 0)],
    }

    def test_a_workplace_with_one_bus_and_nothing_else_is_counted_by_line(self):
        works = [("A", (100, 0)), ("B", (200, 0)), ("C", (5000, 0))]
        found = {("bus", "80"): dict(n=0, matched=True)}

        line = report.one_bus(works, self.stops, found, REACH)

        self.assertIn("80 für 2 von 3 (ohne Fahrt 8–10)", line)
        self.assertNotIn("22", line)  # C has the 22 and the tram
        self.assertIn("Vorschlag: eine Version", line)

    def test_a_workplace_whose_only_line_is_a_tram_is_not_this_lines_business(self):
        self.assertIsNone(
            report.one_bus([("T", (0, 0))], {("tram", "1"): [(0, 0)]}, {}, REACH)
        )

    def test_a_workplace_served_by_a_tram_is_fine(self):
        self.assertIsNone(report.one_bus([("C", (5000, 0))], self.stops, {}, REACH))


class NumbersTests(SimpleTestCase):
    def test_commuters_and_stops(self):
        data = {
            "map": {"district_commuters": 6800},
            "nodes": [
                {"types": ["bus_stop"]},
                {"types": ["bus_stop", "home"]},
                {"types": ["station"]},
                {"types": ["intersection"]},
            ],
        }

        self.assertEqual(
            report.numbers(data),
            "Pendler 6800 (ein Platzhalter bis zur Kalibrierung), Haltestellen 2, Bahnhöfe 1",
        )
