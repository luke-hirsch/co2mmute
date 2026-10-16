"""Footpaths to the stop: a place the kept streets walk far from a stop the side streets reach."""

from django.test import SimpleTestCase

from mapbuild import footpaths

REACH = 1000.0


def node(id, x_m, y_m, *types):
    return {"id": id, "x": x_m / 1000, "y": y_m / 1000, "types": list(types)}


def both(a, b, circuity):
    return [
        {"start_node": a, "end_node": b, "circuity": circuity, "type": "street"},
        {"start_node": b, "end_node": a, "circuity": circuity, "type": "street"},
    ]


class LayTests(SimpleTestCase):
    def setUp(self):
        # A stop, and a home 600 m east of it that the map only reaches the long way round.
        self.nodes = [
            node("stop", 0, 0, "bus_stop"),
            node("home", 600, 0, "home"),
            node("round", 300, 700),
        ]
        self.edges = both("home", "round", 1.0) + both("round", "stop", 1.0)
        # A side street from the home's door to the stop's, a little bent.
        self.local = [
            ("Seitenweg", [(1, (600, 10)), (2, (300, 60)), (3, (0, 10))]),
        ]

    def lay(self, **kw):
        args = dict(
            nodes=self.nodes,
            edges=self.edges,
            local=self.local,
            reach=REACH,
        )
        args.update(kw)
        return footpaths.lay(**args)

    def test_a_place_far_on_the_map_gets_a_path_as_long_as_the_side_streets(self):
        laid, still_far = self.lay()

        self.assertEqual(
            sorted((e["start_node"], e["end_node"]) for e in laid),
            [("home", "stop"), ("stop", "home")],
        )
        walk = 10 + ((300**2 + 50**2) ** 0.5) * 2 + 10
        for e in laid:
            self.assertEqual(e["type"], "path")
            self.assertTrue(e["walking"])
            self.assertTrue(e["biking"])
            self.assertEqual(e["versions"], [0])
            self.assertEqual(e["name"], "Seitenweg")
            self.assertAlmostEqual(e["circuity"], round(walk / 600, 3))
        self.assertEqual(still_far, [])

    def test_a_place_the_map_already_walks_gets_nothing(self):
        self.edges = both("home", "round", 1.0) + both("home", "stop", 1.2)

        laid, still_far = self.lay()

        self.assertEqual(laid, [])
        self.assertEqual(still_far, [])

    def test_a_side_street_walk_longer_than_the_reach_leaves_the_place_far(self):
        self.local = [
            ("Umweg", [(1, (600, 10)), (2, (300, 500)), (3, (0, 10))]),
        ]

        laid, still_far = self.lay()

        self.assertEqual(laid, [])
        self.assertEqual(still_far, ["home"])

    def test_a_side_street_more_than_a_snap_from_the_place_is_not_its_door(self):
        self.local = [
            ("Seitenweg", [(1, (600, 150)), (2, (300, 150)), (3, (0, 10))]),
        ]

        laid, still_far = self.lay()

        self.assertEqual(laid, [])
        self.assertEqual(still_far, ["home"])

    def test_the_path_goes_to_the_stop_nearest_on_foot_not_as_the_crow_flies(self):
        # A stop across the river, 200 m off as the crow flies and 900 m over the bridge, and one
        # 450 m along the bank.
        self.nodes = [
            node("home", 0, 0, "home"),
            node("across", 0, 200, "bus_stop"),
            node("bank", 450, 0, "bus_stop"),
        ]
        self.nodes.append(node("round", -1000, -1000))
        self.edges = (
            both("home", "round", 1.0)
            + both("round", "across", 1.0)
            + both("round", "bank", 1.0)
        )
        self.local = [
            ("Brücke", [(1, (0, 0)), (2, (-350, 0)), (3, (-350, 200)), (4, (0, 200))]),
            ("Ufer", [(1, (0, 0)), (5, (450, 0))]),
        ]

        laid, _ = self.lay()

        self.assertEqual(
            sorted((e["start_node"], e["end_node"]) for e in laid),
            [("bank", "home"), ("home", "bank")],
        )

    def test_the_side_streets_and_the_map_are_walked_together(self):
        # The side street ends at a crossing of the map's; the map's street goes on to the stop.
        self.nodes.append(node("crossing", 300, 0))
        self.edges += both("crossing", "stop", 1.0)
        self.local = [("Seitenweg", [(1, (600, 10)), (2, (300, 10))])]

        laid, _ = self.lay()

        self.assertEqual(len(laid), 2)
        self.assertAlmostEqual(
            laid[0]["circuity"], round((10 + 300 + 10 + 300) / 600, 3)
        )

    def test_a_workplace_counts_like_a_home_and_a_station_like_a_stop(self):
        self.nodes[0]["types"] = ["station"]
        self.nodes[1]["types"] = ["workplace"]

        laid, _ = self.lay()

        self.assertEqual(len(laid), 2)

    def test_a_place_with_no_stop_within_reach_as_the_crow_flies_is_not_this_rules(
        self,
    ):
        self.nodes[1]["x"] = 1.5
        self.local = [("Seitenweg", [(1, (1500, 0)), (2, (0, 0))])]

        laid, still_far = self.lay()

        self.assertEqual(laid, [])
        self.assertEqual(still_far, [])

    def test_the_door_is_on_the_street_not_only_at_its_bends(self):
        # A long straight street, its ends 300 and 600 m off, passes 30 m from the home.
        self.local = [("Lange Straße", [(1, (900, 30)), (2, (0, 30))])]

        laid, still_far = self.lay()

        self.assertEqual(len(laid), 2)
        self.assertAlmostEqual(laid[0]["circuity"], round((30 + 600 + 30) / 600, 3))
        self.assertEqual(still_far, [])

    def test_a_stop_the_place_is_linked_to_already_is_passed_over_for_the_next(self):
        # A track nobody walks between the home and the near stop; the side street goes on to
        # another.
        self.nodes.append(node("further", -300, 0, "bus_stop"))
        self.edges.append(
            {
                "start_node": "home",
                "end_node": "stop",
                "type": "train",
                "walking": False,
            }
        )
        self.edges.append(
            {
                "start_node": "stop",
                "end_node": "home",
                "type": "train",
                "walking": False,
            }
        )
        self.local = [("Seitenweg", [(1, (600, 10)), (3, (0, 10)), (4, (-300, 10))])]

        laid, _ = self.lay()

        self.assertEqual(
            sorted((e["start_node"], e["end_node"]) for e in laid),
            [("further", "home"), ("home", "further")],
        )

    def test_a_place_already_linked_to_the_stop_gets_no_second_link(self):
        # One link per direction per node pair: the long street between them stays the only one.
        self.edges = both("home", "stop", 2.0)

        laid, still_far = self.lay()

        self.assertEqual(laid, [])
        self.assertEqual(still_far, ["home"])


class SayTests(SimpleTestCase):
    def test_the_line_counts_paths_not_directions(self):
        laid = [
            {"start_node": "a", "end_node": "s"},
            {"start_node": "s", "end_node": "a"},
        ]

        self.assertEqual(
            footpaths.say(laid, ["b"]),
            "Fußwege zum Halt über die Nebenstraßen: 1 gelegt, 1 Orte bleiben auch so weiter "
            "als die Reichweite (unter Achtung)",
        )
