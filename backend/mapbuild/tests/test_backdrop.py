"""The background: a drawing in the plane the nodes lie in, from what the build holds."""

import base64
import re
from unittest import mock

from django.test import SimpleTestCase

from mapbuild import backdrop, download, geo

BOX = (52.0, 13.0, 52.03, 13.04)  # about 2.7 km by 3.3 km


def way(wid, pts, **tags):
    return dict(
        type="way",
        id=wid,
        tags=tags,
        geometry=[dict(lat=a, lon=b) for a, b in pts],
    )


def square(lat, lon, d):
    """a closed square of side d degrees, its north-west corner at lat, lon."""
    return [(lat, lon), (lat, lon + d), (lat - d, lon + d), (lat - d, lon), (lat, lon)]


def drawn(layers, x_dim=3, y_dim=4):
    """backdrop.draw on hand-made layers {"residential": [...], …}; the rest are empty."""
    geo.use(BOX)
    empty = {
        k: [] for k in ("residential", "workland", "local", "water", "green", "pt_ways")
    }
    with mock.patch(
        "mapbuild.download.osm", lambda area, name: {**empty, **layers}[name]
    ):
        return backdrop.draw(None, x_dim, y_dim)


class PlacedWhereTheNodesAre(SimpleTestCase):
    def test_a_corner_is_where_a_node_at_that_point_would_be(self):
        lat, lon = 52.01, 13.01
        svg, _ = drawn({"residential": [way(1, square(lat, lon, 0.004))]})
        x, y = geo.xy(
            lat, lon
        )  # a node is written as x / 1000 km, the viewers draw it at km × 100
        self.assertIn(f"M{round(x)} {round(y)}l", svg)

    def test_the_view_box_is_the_maps_box_in_metres(self):
        svg, _ = drawn({}, x_dim=3, y_dim=4)
        self.assertIn('viewBox="0 0 3000 4000"', svg)
        self.assertIn('width="3000" height="4000"', svg)


class WhatIsLeftOut(SimpleTestCase):
    def test_a_polygon_of_a_few_pixels_is_dropped(self):
        small = way(1, square(52.01, 13.01, 0.0001))  # about 7 m by 11 m
        big = way(2, square(52.02, 13.02, 0.004))
        svg, _ = drawn({"residential": [small, big]})
        self.assertEqual(svg.count("<path d="), 1)

    def test_a_polygon_outside_the_box_is_dropped(self):
        far = way(1, square(53.5, 13.01, 0.004))
        svg, _ = drawn({"residential": [far]})
        self.assertNotIn("<path d=", svg)

    def test_a_short_street_is_dropped_and_a_long_one_is_drawn(self):
        stub = way(1, [(52.01, 13.01), (52.01, 13.0102)], highway="residential")
        road = way(2, [(52.01, 13.01), (52.01, 13.02)], highway="residential")
        svg, _ = drawn({"local": [stub, road]})
        d = re.search(r'id="strassen" d="([^"]+)"', svg).group(1)
        self.assertEqual(d.count("M"), 1)

    def test_a_bend_inside_the_tolerance_is_simplified_away(self):
        pts = [(52.01, 13.01), (52.01002, 13.015), (52.01, 13.02)]  # 2 m off the line
        svg, _ = drawn({"local": [way(1, pts, highway="residential")]})
        d = re.search(r'id="strassen" d="([^"]+)"', svg).group(1)
        self.assertEqual(len(d.split("l")[1].split()), 2)


class Shapes(SimpleTestCase):
    def test_an_island_is_a_hole_and_opens_no_other_shape(self):
        outer = square(52.02, 13.01, 0.01)
        hole = square(52.018, 13.012, 0.004)
        other = square(52.01, 13.03, 0.004)
        lake = dict(
            type="relation",
            id=1,
            tags={"natural": "water"},
            members=[
                dict(type="way", role="outer", geometry=way(0, outer)["geometry"]),
                dict(type="way", role="inner", geometry=way(0, hole)["geometry"]),
            ],
        )
        svg, _ = drawn({"water": [lake, way(2, other, natural="water")]})
        paths = re.findall(r'<path d="[^"]+"[^>]*>', svg)
        self.assertEqual(len(paths), 2)
        self.assertIn('fill-rule="evenodd"', paths[0])
        self.assertNotIn("fill-rule", paths[1])

    def test_a_river_is_a_line_and_a_riverbank_a_shape(self):
        river = way(1, [(52.01, 13.0), (52.01, 13.03)], waterway="river")
        bank = way(2, square(52.02, 13.01, 0.004), waterway="riverbank")
        svg, _ = drawn({"water": [river, bank]})
        self.assertIn('stroke-width="24"', svg)
        self.assertEqual(svg.count("fill-rule"), 0)
        self.assertEqual(len(re.findall(r'<path d="M[^"]+z"/>', svg)), 1)

    def test_a_railway_is_drawn_and_a_bus_way_is_not(self):
        rail = way(1, [(52.01, 13.0), (52.01, 13.03)], railway="rail")
        bus = way(2, [(52.02, 13.0), (52.02, 13.03)], highway="residential")
        svg, _ = drawn({"pt_ways": [rail, bus, rail]})
        d = re.search(r'id="schiene" d="([^"]+)"', svg).group(1)
        self.assertEqual(d.count("M"), 1)


class OptionalLayers(SimpleTestCase):
    def test_without_water_and_parks_it_is_drawn_and_the_report_says_so(self):
        geo.use(BOX)

        def osm(area, name):
            if name in ("water", "green"):
                raise download.Missing("nicht erreichbar")
            return []

        with mock.patch("mapbuild.download.osm", osm):
            svg, report = backdrop.draw(None, 3, 4)
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(any(line.startswith("water fehlt") for line in report))
        self.assertTrue(any(line.startswith("green fehlt") for line in report))


class TheFile(SimpleTestCase):
    def test_the_block_is_the_drawing_placed_at_the_origin_at_scale_one(self):
        block = backdrop.block("<svg/>")
        self.assertEqual(base64.b64decode(block["data"]), b"<svg/>")
        self.assertTrue(block["filename"].endswith(".svg"))
        self.assertEqual(
            (block["scale"], block["offset_x"], block["offset_y"]), (1.0, 0.0, 0.0)
        )

    def test_the_same_inputs_the_same_bytes(self):
        land = [way(i, square(52.02 - i * 0.005, 13.01, 0.004)) for i in (3, 1, 2)]
        a, _ = drawn({"residential": land})
        b, _ = drawn({"residential": list(reversed(land))})
        self.assertEqual(a, b)
