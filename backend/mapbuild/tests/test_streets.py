"""The fold and the merge, on streets drawn by hand (x east, y south, in m)."""

import collections
import math

from django.test import SimpleTestCase

from mapbuild import streets


def way(wid, nodes, name, oneway, cls="secondary", junction=""):
    tags = {"highway": cls, "name": name}
    if oneway:
        tags["oneway"] = "yes"
    if junction:
        tags["junction"] = junction
        oneway = True
    return dict(
        id=str(wid),
        key=name,
        aliases={name},
        cls=cls,
        base=cls.replace("_link", ""),
        link=cls.endswith("_link"),
        ring=bool(junction),
        junction=junction,
        oneway=oneway,
        lanes=(1, 0) if oneway else (1, 1),
        tags=tags,
        nodes=nodes,
    )


def d(length, name="", slip=False, lanes=1, speed=50.0, rank=1.0, junction=""):
    return dict(
        len=length,
        speed=speed,
        lanes=lanes,
        rank=rank,
        names=collections.Counter({name: length} if name else {}),
        slip=slip,
        junction=junction,
    )


class FoldTests(SimpleTestCase):
    """A dual carriageway, 30 m apart, crossed in the middle by a two-way street: OSM draws two
    one-way ways and four junction corners; the game wants one two-way street and one crossing.
    """

    pos = {
        1: (0, 0),
        2: (500, 0),
        3: (1000, 0),
        6: (1000, 30),
        5: (500, 30),
        4: (0, 30),
        7: (500, -300),
        8: (500, 330),
    }
    ways = [
        way(10, [1, 2, 3], "Hauptstraße", True),  # eastbound
        way(11, [6, 5, 4], "Hauptstraße", True),  # westbound
        way(12, [7, 2, 5, 8], "Querstraße", False),
    ]

    def folded(self):
        uf, p1, w1 = streets.fold(
            self.pos, self.ways, streets.twins(self.pos, self.ways)
        )
        return uf, streets.graph(p1, w1, uf)

    def test_the_two_carriageways_twin(self):
        tw = streets.twins(self.pos, self.ways)
        self.assertEqual(set(tw), {0, 1})
        self.assertEqual(set(tw[0]), {1})

    def test_the_four_corners_are_one_crossing_in_their_middle(self):
        uf, (p2, _, links) = self.folded()
        self.assertEqual(uf.find(2), uf.find(5))
        self.assertEqual(p2[uf.find(2)], (500.0, 15.0))

    def test_the_street_is_one_link_each_way_between_crossings(self):
        uf, (_, _, links) = self.folded()
        haupt = [t for t in links if streets.top_name(t) == "Hauptstraße"]
        self.assertEqual(len(haupt), 2)
        for t in haupt:
            self.assertIsNotNone(t[2])
            self.assertIsNotNone(t[3])

    def test_a_one_way_street_without_a_twin_stays_one_way(self):
        ways = [way(10, [1, 2, 3], "Einbahnstraße", True)]
        self.assertEqual(streets.twins(self.pos, ways), {})


class MergeTests(SimpleTestCase):
    """The merge's stages one at a time."""

    def test_a_link_shorter_than_s_is_one_node_at_the_centroid(self):
        pos = {"b": (1000, 0), "b2": (1000, 20), "a": (0, 0), "c": (1000, 1000)}
        links = [
            ("a", "b", d(1000, "Nord"), d(1000, "Nord"), [pos["a"], pos["b"]]),
            ("b", "b2", d(20, "Ost"), d(20, "Ost"), [pos["b"], pos["b2"]]),
            ("b2", "c", d(980, "Ost"), d(980, "Ost"), [pos["b2"], pos["c"]]),
        ]
        p, out, _ = streets.merge_ends(
            pos, links, lambda t: math.dist(pos[t[0]], pos[t[1]]) < streets.S
        )
        self.assertEqual({n for t in out for n in t[:2]}, {"a", "b", "c"})
        self.assertEqual(p["b"], (1000.0, 10.0))

    def test_a_slip_road_is_one_node(self):
        pos = {"x": (0, 0), "y": (300, 0), "z": (2000, 0)}
        links = [
            ("x", "y", d(300, slip=True), None, [(0, 0), (300, 0)]),
            ("y", "z", d(1700, "B 1"), d(1700, "B 1"), [(300, 0), (2000, 0)]),
        ]
        _, out, _ = streets.merge_ends(
            pos, links, lambda t: streets.is_slip(t[2]) and streets.is_slip(t[3])
        )
        self.assertEqual(len(out), 1)

    def test_two_kept_nodes_never_merge_into_one(self):
        pos = {"b": (1000, 0), "b2": (1000, 20)}
        links = [("b", "b2", d(20, "Ost"), d(20, "Ost"), [pos["b"], pos["b2"]])]
        _, out, keep = streets.merge_ends(pos, links, lambda t: True, keep={"b", "b2"})
        self.assertEqual(keep, {"b", "b2"})
        self.assertEqual(len(out), 1)

    def hub(self, m_speed=30):
        """x and y are crossings (two side streets each), m only carries the street on."""
        pos = {
            "x": (0, 0),
            "m": (500, 0),
            "y": (1000, 0),
            "p": (0, -300),
            "q": (0, 300),
            "r": (1000, -300),
            "s": (1000, 300),
        }
        line = lambda a, b, n, L: (a, b, d(L, n), d(L, n), [pos[a], pos[b]])
        return pos, [
            (
                "x",
                "m",
                d(500, "Allee", speed=m_speed),
                d(500, "Allee", speed=m_speed),
                [pos["x"], pos["m"]],
            ),
            ("m", "y", d(500, "Allee"), d(500, "Allee"), [pos["m"], pos["y"]]),
            line("x", "p", "Nord 1", 300),
            line("x", "q", "Süd 1", 300),
            line("y", "r", "Nord 2", 300),
            line("y", "s", "Süd 2", 300),
        ]

    def test_a_pass_through_goes_and_keeps_the_time_to_drive_both(self):
        _, links = self.hub()
        out = streets.pass_throughs(links)
        allee = [t for t in out if streets.top_name(t) == "Allee"]
        self.assertEqual(len(allee), 1)
        self.assertEqual(allee[0][2]["len"], 1000)
        self.assertAlmostEqual(allee[0][2]["speed"], 1000 / (500 / 30 + 500 / 50))

    def test_a_kept_pass_through_stays(self):
        _, links = self.hub()
        self.assertIn(
            "m", {n for t in streets.pass_throughs(links, keep={"m"}) for n in t[:2]}
        )

    def test_a_dead_end_goes_back_to_its_junction_unless_kept(self):
        _, links = self.hub()
        self.assertEqual(
            streets.drop_ends(links), []
        )  # every street here ends somewhere
        kept = streets.drop_ends(links, keep={"p", "s"})
        self.assertEqual({n for t in kept for n in t[:2]}, {"p", "x", "m", "y", "s"})

    def test_two_streets_on_one_node_pair_get_a_node_on_the_lesser(self):
        pos = {"a": (0, 0), "z": (1000, 0)}
        big = (
            "a",
            "z",
            d(1000, "Allee", rank=2),
            d(1000, "Allee", rank=2),
            [(0, 0), (1000, 0)],
        )
        small = (
            "a",
            "z",
            d(1400, "Weg", rank=1),
            d(1400, "Weg", rank=1),
            [(0, 0), (500, 300), (1000, 0)],
        )
        pos2, links = streets.unbundle(pos, [big, small])
        self.assertEqual(len(links), 3)
        mid = next(n for t in links for n in t[:2] if n not in ("a", "z"))
        self.assertEqual(pos2[mid], (500, 300))

    def test_the_same_street_split_round_an_island_adds_its_lanes(self):
        pos = {"a": (0, 0), "z": (1000, 0)}
        one = ("a", "z", d(1000, "Allee", lanes=1), None, [(0, 0), (1000, 10)])
        two = ("a", "z", d(1010, "Allee", lanes=2), None, [(0, 0), (1000, -10)])
        _, links = streets.unbundle(pos, [one, two])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][2]["lanes"], 3)


class RingTests(SimpleTestCase):
    """A ring keeps OSM's word for it, on the links made only of the ring.

    Ernst-Reuter-Platz is `junction=circular`, a roundabout `roundabout`; on
    both the ring has right of way in the game, so the word has to reach the
    file. A link that leaves the ring is a street like any other.
    """

    pos = {
        1: (0, 0),
        2: (100, 0),
        3: (100, 100),
        4: (0, 100),
        11: (-300, 0),
        13: (400, 100),
        14: (700, 100),
    }

    def links(self, ways):
        """Each direction of each link by its two ends."""
        _, _, links = streets.graph(self.pos, ways)
        out = {}
        for u, v, f, b, _ in links:
            if f:
                out[(u, v)] = f
            if b:
                out[(v, u)] = b
        return out

    def test_a_link_made_only_of_the_ring_keeps_its_junction(self):
        links = self.links(
            [
                way(1, [1, 2, 3], "Ernst-Reuter-Platz", True, junction="circular"),
                way(2, [3, 4, 1], "Ernst-Reuter-Platz", True, junction="circular"),
                way(3, [11, 1], "Hardenbergstraße", False),
                way(4, [3, 13], "Otto-Suhr-Allee", False),
            ]
        )

        self.assertEqual(links[(1, 3)].get("junction"), "circular")
        self.assertEqual(links[(3, 1)].get("junction"), "circular")
        self.assertEqual(links[(11, 1)].get("junction"), "")

    def test_a_link_that_leaves_the_ring_is_no_ring(self):
        """Half a roundabout with nothing else joining it: in, round and out
        is one link, and a street."""
        links = self.links(
            [
                way(1, [11, 1], "Zufahrt", True),
                way(2, [1, 2, 3], "Kreisel", True, junction="roundabout"),
                way(3, [3, 13], "Ausfahrt", True),
                way(4, [13, 14], "Weiter", False),
                way(5, [4, 13], "Quer", False),
            ]
        )

        self.assertEqual(links[(11, 13)].get("junction"), "")

    def test_two_ring_links_joined_stay_a_ring_and_a_ring_and_a_street_do_not(self):
        ring = d(50, "Kreisel", junction="roundabout")

        self.assertEqual(streets.join(ring, ring).get("junction"), "roundabout")
        self.assertEqual(streets.join(ring, d(50, "Straße")).get("junction"), "")
        self.assertEqual(streets.add_dir(ring, ring).get("junction"), "roundabout")
        self.assertEqual(streets.add_dir(ring, d(50, "Kreisel")).get("junction"), "")

