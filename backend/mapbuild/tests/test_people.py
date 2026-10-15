"""Equal shares of people and jobs, and the grids they come from."""

from django.test import SimpleTestCase

from mapbuild import connect, geo, people


def cluster(x0, y0, n, people_each=10):
    """n cells of 100 m in a row starting at (x0, y0)."""
    return [(x0 + 100 * i, y0, people_each) for i in range(n)]


class HalvesTests(SimpleTestCase):
    def test_each_part_has_the_same_people(self):
        cells = cluster(0, 0, 40)
        parts = people.halves(cells, 4)
        self.assertEqual(len(parts), 4)
        self.assertEqual(sorted(p for _, p, _ in parts), [100, 100, 100, 100])

    def test_a_home_sits_on_a_cell_people_live_in_never_between_two_villages(self):
        cells = cluster(0, 0, 3) + cluster(5000, 0, 3)
        c, _, _ = people.halves(cells, 1)[0]
        self.assertIn(c, [(x, y) for x, y, _ in cells])

    def test_the_count_is_the_fewest_parts_that_put_most_people_close(self):
        two_villages = cluster(0, 0, 3) + cluster(10000, 0, 3)
        self.assertEqual(people.count(two_villages, 500), 2)
        self.assertEqual(people.count(two_villages, 20000), 1)

    def test_a_place_is_named_after_the_nearest_place_no_other_took(self):
        geo.use((52.0, 13.0, 52.1, 13.1))
        places = [
            {"lat": 52.1, "lon": 13.0, "tags": {"place": "suburb", "name": "Nordwest"}},
            {"lat": 52.0, "lon": 13.1, "tags": {"place": "village", "name": "Südost"}},
            {
                "lat": 52.1,
                "lon": 13.0,
                "tags": {"place": "city", "name": "Stadt"},
            },  # not a kind a home is named after
        ]
        self.assertEqual(people.nearest_place(places, (0, 0)), "Nordwest")
        self.assertEqual(
            people.nearest_place(places, (0, 0), avoid={"Nordwest"}), "Südost"
        )
        self.assertIsNone(
            people.nearest_place(places, (0, 0), avoid={"Nordwest", "Südost"})
        )


class GridTests(SimpleTestCase):
    def test_the_zensus_projection_goes_there_and_back(self):
        x, y = people.to_laea(52.5163, 13.3777)  # Brandenburger Tor
        self.assertAlmostEqual(x / 1000, 4550.2, delta=0.1)
        lat, lon = people.from_laea(x, y)
        self.assertAlmostEqual(lat, 52.5163, places=6)
        self.assertAlmostEqual(lon, 13.3777, places=6)

    def test_the_zensus_cut_keeps_the_cells_in_the_box(self):
        x, y = people.to_laea(52.5163, 13.3777)
        lines = [
            "GITTER_ID_100m;x_mp_100m;y_mp_100m;Einwohner\n",
            f"A;{int(x)};{int(y)};7\n",
            "B;4000050;3000050;9\n",
        ]
        cells = people.zensus_cut(lines, (52.5, 13.3, 52.6, 13.4))
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0][2], 7)

    def test_the_ghsl_tile_of_a_place(self):
        self.assertEqual(people.ghsl_tiles((53.0, 8.4, 53.2, 9.0)), [(4, 19)])  # Bremen
        self.assertEqual(
            people.ghsl_tiles((52.3, 13.0, 52.7, 13.8)), [(4, 20)]
        )  # Berlin
        self.assertEqual(people.ghsl_tiles((50.0, 9.9, 50.1, 10.1)), [(4, 19), (4, 20)])


class OwnNodeTests(SimpleTestCase):
    def test_two_places_nearest_one_node_each_get_their_own(self):
        geo.use((52.0, 13.0, 52.1, 13.1))
        pos = {
            "a": geo.xy(52.05, 13.05),
            "b": geo.xy(52.0505, 13.05),
            "c": geo.xy(52.06, 13.06),
        }
        at = {"home Eins": (52.05, 13.05), "work Zwei": (52.05001, 13.05)}
        taken = connect.own_nodes(set(pos), pos, at)
        self.assertEqual(taken, {"a", "b"})
