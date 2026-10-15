"""The area: its boundary's rings, its boxes."""

import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from mapbuild import area


def way(*pts):
    return {
        "type": "way",
        "role": "outer",
        "geometry": [{"lat": a, "lon": b} for a, b in pts],
    }


class RingTests(SimpleTestCase):
    def test_outer_ways_join_end_to_end_whichever_way_they_run(self):
        rs = area.rings(
            [way((0, 0), (0, 1)), way((1, 1), (0, 1)), way((1, 1), (1, 0), (0, 0))]
        )
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0][0], rs[0][-1])
        self.assertEqual(len(rs[0]), 5)

    def test_the_largest_ring_is_the_area(self):
        small = [(0, 0), (0, 0.01), (0.01, 0.01), (0, 0)]
        big = [(1, 1), (1, 2), (2, 2), (1, 1)]
        self.assertGreater(area.km2(big), area.km2(small))

    def test_a_name_is_a_directory(self):
        self.assertEqual(area.slug("Frankfurt (Oder)"), "frankfurt--oder")


class BoxTests(SimpleTestCase):
    def test_a_box_is_built_as_it_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = area.box((53.06, 8.775, 53.095, 8.84), name="Ausschnitt", root=tmp)
            self.assertEqual(a.box, (53.06, 8.775, 53.095, 8.84))
            self.assertEqual(a.fetch_bbox, (53.06, 8.775, 53.095, 8.84))
            self.assertIsNone(a.boundary)
            self.assertTrue((Path(tmp) / a.cache.name / "area.json").exists())

    def test_a_named_area_keeps_its_roads_a_kilometre_past_the_boundary(self):
        a = area.Area(
            name="Bremen",
            bbox=(53.01116, 8.48159, 53.22891, 8.99083),
            cache=Path("."),
            boundary=[[]],
            pad=area.PAD,
        )
        s, w, n, e = a.box
        self.assertAlmostEqual((53.01116 - s) * 110574, 1000, places=3)
        self.assertEqual(a.fetch_bbox, (53.00211, 8.46662, 53.23796, 9.0058))

    def test_an_empty_box_is_refused(self):
        with self.assertRaises(ValueError):
            area.box((53.1, 8.8, 53.0, 8.9))
