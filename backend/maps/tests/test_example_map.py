"""The one map anybody plays.

`map_examples/Berlin_Mitte-West.json` is not a fixture. It is the file the live
box was seeded from, the file `frontend/e2e/seed.mjs` uploads to make an
instance playable, and — since `f66b52e` — the only backup a map has. Every
other test in this suite builds its own two-node graph, so nothing read this
file, and it quietly carried real defects: a bus line with no edges at all, a
60-seat U-Bahn, a `101` that breaks mid-chain and drives 4,04 of its 6,33 km.

It gets a module of its own rather than a class in `test_portability.py`
because the subject is the data, not the code: what is pinned here is what the
shipped map says. The round trip that has to carry it lives next door.

These tests read the file directly, so they fail on the file rather than on a
database — which is what you want from a data test: the same run tells you
whether the *file* is broken, wherever it is about to be imported.
"""

import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from maps.models import BusLine, Edge, TrainLine
from maps.serializer import serialize_bus_line_for_graph, serialize_train_line_for_graph
from maps.tests.test_portability import MapUploadMixin
from sim import node_chain

SHIPPED_MAP = (
    Path(__file__).resolve().parents[3] / "map_examples" / "Berlin_Mitte-West.json"
)

# What a line of each mode carries and how fast it drives. The seats are the
# project-wide pair (`maps/models.py`, both view defaults, `_get_pt_capacity`'s
# fallback, `frontend/src/lib/map/pt-defaults.ts`); the speeds are the model
# defaults for a bus in mixed traffic and a U-Bahn, plus 50 for the Stadtbahn,
# which is an S-Bahn on an alignment of its own and the only line here that is
# not sharing the road or stopping every 700 m.
BUS_CAPACITY = 85
TRAIN_CAPACITY = 1000
BUS_SPEED_KMH = 30
TRAIN_SPEEDS_KMH = {40, 50}


def load_shipped_map():
    with SHIPPED_MAP.open(encoding="utf-8") as fh:
        return json.load(fh)


def edge_ends(graph, indices):
    return [
        (graph["edges"][i]["start_node"], graph["edges"][i]["end_node"])
        for i in indices
    ]


def base_name(line_name):
    """`101 reverse` and `U2 Reverse` both belong to the pair they mirror."""
    return line_name.rsplit(" ", 1)[0] if " " in line_name else line_name


class ShippedMapLineTests(SimpleTestCase):
    """The lines: connected, mirrored, and carrying the right numbers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = load_shipped_map()
        cls.lines = [
            ("bus", line) for line in cls.graph["bus_lines"]
        ] + [("train", line) for line in cls.graph["train_lines"]]

    def test_no_line_is_empty(self):
        """A line with no edges is a line that cannot be ridden or drawn.

        `100` shipped with zero edges: `_register_pt_line` measures it at 0 km,
        logs twice and returns before it gets a run to drive, so the map showed
        a bus line nobody could board.
        """
        for mode, line in self.lines:
            with self.subTest(line=line["name"]):
                self.assertGreater(len(line["edges"]), 0, f"{mode} {line['name']}")

    def test_every_line_is_one_connected_walk(self):
        """`node_chain` has to reach the end of the edge list.

        This is the check `_register_pt_line` makes at runtime, where the answer
        is a truncated line and a warning in the log nobody reads. A chain that
        is whole has exactly one more node than it has edges.
        """
        for mode, line in self.lines:
            with self.subTest(line=line["name"]):
                chain = node_chain(edge_ends(self.graph, line["edges"]))
                self.assertEqual(
                    len(chain),
                    len(line["edges"]) + 1,
                    f"{mode} {line['name']} breaks after {max(0, len(chain) - 1)} "
                    f"of {len(line['edges'])} edges",
                )

    def test_a_line_and_its_reverse_serve_the_same_stops(self):
        """Both directions of a line, or a stop served one way only.

        `101` ran nine stops one way and three the other; `U2` stopped at
        Ernst-Reuter Platz westbound while `U2 Reverse` carried on to
        Kaiserdamm. A rider going to work can get there and not back.
        """
        chains = {}
        for _, line in self.lines:
            chains[line["name"]] = node_chain(edge_ends(self.graph, line["edges"]))

        pairs = [
            (name, other)
            for name in chains
            for other in chains
            if name != other and base_name(other) == name
        ]
        self.assertEqual(len(pairs), 5, f"expected five line pairs, got {pairs}")

        for forward, reverse in pairs:
            with self.subTest(pair=forward):
                self.assertEqual(
                    chains[forward],
                    list(reversed(chains[reverse])),
                    f"{forward} and {reverse} do not mirror each other",
                )

    def test_every_line_carries_the_seats_of_its_mode(self):
        """The 60-seat U-Bahn came from this file, not from a default.

        Both modes said `"capacity": 60` outright, so the importer's own
        defaults never got a chance — which is why fixing the five disagreeing
        code paths left the shipped map broken anyway.
        """
        for mode, line in self.lines:
            with self.subTest(line=line["name"]):
                expected = BUS_CAPACITY if mode == "bus" else TRAIN_CAPACITY
                self.assertEqual(line["capacity"], expected)

    def test_every_line_says_how_fast_it_drives(self):
        """Read by the simulator and by the client's route preview.

        Both sides take it from the line (`bus_line_speeds` in
        `game/simulation.py`, `line.speed_kmh` in `ptRouting.ts`), so a bus at
        50 km/h is a bus that never stops. The two directions of one line have
        to agree, or the trip home is not the trip out.
        """
        speeds = {}
        for mode, line in self.lines:
            with self.subTest(line=line["name"]):
                if mode == "bus":
                    self.assertEqual(line["speed_kmh"], BUS_SPEED_KMH)
                else:
                    self.assertIn(line["speed_kmh"], TRAIN_SPEEDS_KMH)
            speeds.setdefault(base_name(line["name"]), set()).add(line["speed_kmh"])

        for name, values in speeds.items():
            with self.subTest(pair=name):
                self.assertEqual(len(values), 1, f"{name}: {sorted(values)}")

    def test_every_stop_is_a_stop_a_player_can_board_at(self):
        """`buildDesignatedStopSet` boards only at `station` or `bus_stop`.

        A line may run past an ordinary junction — that is what a bus does —
        but then nobody gets on there, and a line whose *ends* are not stops is
        a line that goes nowhere. Every node on every line here is typed, which
        is also how the intended network can be read off the map at all.
        """
        types = {node["id"]: set(node.get("types", [])) for node in self.graph["nodes"]}

        for mode, line in self.lines:
            chain = node_chain(edge_ends(self.graph, line["edges"]))
            for node_id in chain:
                with self.subTest(line=line["name"], node=node_id):
                    self.assertTrue(
                        types[node_id] & {"station", "bus_stop"},
                        f"{mode} {line['name']} stops at {node_id} "
                        f"({sorted(types[node_id])})",
                    )


class ShippedMapEdgeTests(SimpleTestCase):
    """The edges: every field stated, nothing left to a default."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = load_shipped_map()

    def test_every_edge_states_its_bike_lane(self):
        """The file has to describe the map, not a diff against a default.

        Same argument as the export's (`test_the_export_carries_a_missing_bike_
        lane_too`): a key that only appears when it is True re-imports to the
        same value, but the next reader cannot tell "no bike lane here" from
        "this file is older than the field". `maps/0006` added it; the shipped
        map never mentioned it.
        """
        for idx, edge in enumerate(self.graph["edges"]):
            with self.subTest(edge=idx):
                self.assertIn("bike_lane", edge)

    def test_every_street_states_its_speed_limit_and_lanes(self):
        """Eight edges said neither and took 50 km/h and one lane by default.

        They are the three home links to Bellevue and the one to Checkpoint
        Charlie, all drawn in the editor after the file was first written. The
        speed limit is what the free-flow time and the CO2 curve are computed
        from, so leaving it out is not a formality.
        """
        for idx, edge in enumerate(self.graph["edges"]):
            if edge.get("type", "both") not in ("street", "both"):
                continue
            with self.subTest(edge=idx):
                self.assertIn("speed_limit", edge)
                self.assertIn("lanes", edge)
                self.assertIn("dedicated_bus_lane", edge)

    def test_no_edge_has_a_speed_limit_of_zero(self):
        """Fixed once already — a zero divides into the free-flow time.

        The simulator now warns and falls back to the map default, which means
        a new zero would cost nothing but a log line. Pinned so it stays fixed.
        """
        for idx, edge in enumerate(self.graph["edges"]):
            with self.subTest(edge=idx):
                self.assertNotEqual(edge.get("speed_limit", 50), 0)

    def test_a_railway_is_not_a_bike_route(self):
        """`"type": "train"` says false outright since 2026-09-24.

        The importer still honours `"biking": true` on a rail edge, because
        under the post-`bike_lane` semantics that is a legitimate statement — a
        way alongside. This map does not make it: its 46 rail edges are rail.
        The six `"type": "both"` edges are street-and-rail and stay open, which
        is why this test names the type instead of the TrainEdge.
        """
        rail = [e for e in self.graph["edges"] if e.get("type") == "train"]
        self.assertEqual(len(rail), 46)
        for edge in rail:
            with self.subTest(edge=edge["name"]):
                self.assertFalse(edge["biking"])
                self.assertFalse(edge["walking"])


class ShippedMapImportsTests(MapUploadMixin, TestCase):
    """The file through `/map/upload/`, which is how it reaches a box.

    `MapUploadMixin` comes from `test_portability` rather than being copied:
    the upload form has two required fields and a rejected form answers 200
    with the form re-rendered, so the mixin's `uploaded_map` failure message is
    the difference between a readable red and a bare DoesNotExist.
    """

    def upload_shipped_map(self):
        graph = load_shipped_map()
        # The background image is 970 KB of base64 in this file and the import
        # writes it to disk. TempMediaRootMixin would clean it up, but the
        # picture is not what these tests are about — `test_portability` pins
        # the image round trip on a 2x2 PNG.
        graph.pop("background_image", None)
        return self.upload(graph, name="Berlin Mitte-West", max_players=6)

    def test_the_shipped_map_imports_whole(self):
        game_map = self.upload_shipped_map()

        self.assertEqual(Edge.objects.filter(game_map=game_map).count(), 136)
        self.assertEqual(game_map.max_player, 6)
        self.assertEqual(game_map.district_commuters, 6400)
        self.assertEqual(game_map.co2_budget_kg_per_round, 8000)

    def test_the_lines_arrive_with_their_seats_and_their_speed(self):
        game_map = self.upload_shipped_map()

        buses = BusLine.objects.filter(game_map=game_map)
        trains = TrainLine.objects.filter(game_map=game_map)
        self.assertEqual(buses.count(), 4)
        self.assertEqual(trains.count(), 6)
        for bus in buses:
            with self.subTest(line=bus.name):
                self.assertEqual(bus.bus_capacity, BUS_CAPACITY)
                self.assertEqual(bus.bus_speed_kmh, BUS_SPEED_KMH)
        for train in trains:
            with self.subTest(line=train.name):
                self.assertEqual(train.train_capacity, TRAIN_CAPACITY)
                self.assertIn(train.train_speed_kmh, TRAIN_SPEEDS_KMH)

    def test_every_line_reports_a_whole_stop_list_to_the_client(self):
        """The serializer is what `ptRouting.ts` boards people with.

        Same walk as `node_chain`, one layer up and after a real import — so
        this is the check the pure-JSON test above cannot make: that the edges
        arrived in the order the file gave them and the M2M kept it.
        """
        game_map = self.upload_shipped_map()
        version = game_map.mapversion_set.get(base_version=True)

        for line in BusLine.objects.filter(game_map=game_map):
            with self.subTest(line=line.name):
                data = serialize_bus_line_for_graph(line, version)
                self.assertEqual(len(data["stops"]), len(data["edges"]) + 1)
        for line in TrainLine.objects.filter(game_map=game_map):
            with self.subTest(line=line.name):
                data = serialize_train_line_for_graph(line, version)
                self.assertEqual(len(data["stops"]), len(data["edges"]) + 1)
