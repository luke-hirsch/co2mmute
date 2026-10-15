"""Speed and lanes from OSM's tags."""

from django.test import SimpleTestCase

from mapbuild import roads

BUILT_UP = lambda p: p[0] < 1000  # noqa: E731 — west of x = 1 km is built-up land


class SpeedTests(SimpleTestCase):
    def test_the_sign_wins(self):
        self.assertEqual(
            roads.speed({"maxspeed": "30"}, "primary", (5000, 0), BUILT_UP), 30
        )

    def test_no_sign_faster_than_100(self):
        self.assertEqual(roads.speed({"maxspeed": "130"}, "motorway"), 100)

    def test_a_tag_naming_the_sign_type(self):
        self.assertEqual(
            roads.speed({"maxspeed": "DE:urban"}, "secondary", (5000, 0), BUILT_UP), 50
        )
        self.assertEqual(roads.speed({"zone:maxspeed": "DE:30"}, "secondary"), 30)
        self.assertEqual(
            roads.speed({"maxspeed:type": "DE:rural"}, "secondary", (0, 0), BUILT_UP),
            100,
        )

    def test_unsigned_50_inside_built_up_land_and_100_outside(self):
        self.assertEqual(roads.speed({}, "trunk", (500, 0), BUILT_UP), 50)
        self.assertEqual(roads.speed({}, "secondary", (5000, 0), BUILT_UP), 100)

    def test_an_unsigned_motorway_is_the_class_default_anywhere(self):
        self.assertEqual(roads.speed({}, "motorway", (500, 0), BUILT_UP), 100)

    def test_without_a_built_up_test_the_class_default(self):
        self.assertEqual(roads.speed({}, "trunk"), 70)


class LaneTests(SimpleTestCase):
    def test_a_one_way_street_has_all_its_lanes_one_way(self):
        self.assertEqual(roads.direction_lanes({"lanes": "3"}, "primary", True), (3, 0))

    def test_a_two_way_street_splits_its_lanes(self):
        self.assertEqual(
            roads.direction_lanes({"lanes": "3"}, "primary", False), (1, 2)
        )
        self.assertEqual(
            roads.direction_lanes(
                {"lanes:forward": "2", "lanes:backward": "1"}, "primary", False
            ),
            (2, 1),
        )

    def test_untagged_a_motorway_has_two_a_side_a_secondary_one(self):
        self.assertEqual(roads.direction_lanes({}, "motorway", True), (2, 0))
        self.assertEqual(roads.direction_lanes({}, "primary", False), (1, 1))
        self.assertEqual(roads.direction_lanes({}, "secondary", False), (1, 1))

    def test_a_messy_tag_reads_its_first_number(self):
        self.assertEqual(roads.parse_int("2;3", None), 2)
        self.assertIsNone(roads.parse_int("none", None))


class ClassTests(SimpleTestCase):
    def test_each_rung_adds_one_class(self):
        self.assertEqual(
            roads.CLASSES["tertiary"] - roads.CLASSES["secondary"], {"tertiary"}
        )
        self.assertEqual(roads.LADDER[roads.LADDER.index("secondary") + 1], "tertiary")
