"""The one map anybody plays — every version of it.

`map_examples/Berlin_Mitte-West.json` is not a fixture. It is the map the
research group plays: eight versions, a 24-row ballot between them, and the
three interventions the thesis is about — `Busspuren` (a car lane given to
100 and 101), `Buslinie` (147) and `Umgehungsstraßen` (four new streets).
Until S16 it lived only in a pg dump of the live box, because the export could
carry one flattened version and nothing else. S14 gave it a file; this module
is what says the file is right.

It gets a module of its own rather than a class in `test_portability.py`
because the subject is the data, not the code: what is pinned here is what the
shipped map says. The round trip that has to carry it lives next door.

**Every assertion is per version.** That is the whole difference from the
flattened file this module used to read. A line's route is not a property of
the line — `100` ran seven links under `Busspuren` and *none at all* in the
base version, because `VersionDiffCreateView` cloned the street it runs on and
moved the chain row onto the clone. One route per line could not even express
the defect, let alone catch it. So a line is checked in each version it belongs
to, and "connected" means connected there.

These tests read the file directly, so they fail on the file rather than on a
database — which is what you want from a data test: the same run tells you
whether the *file* is broken, wherever it is about to be imported. The import
class at the bottom then proves the same map arrives through `/map/upload/`.
"""

import heapq
import json
import math
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from maps.models import BusLine, Edge, MapVersion, Node, TrainLine
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

# The graph, counted. Named because a count that drifts silently is how the
# 60-seat U-Bahn survived two passes: the numbers are the map, not a sanity
# check on the loader.
NODE_COUNT = 55
EDGE_COUNT = 186
VERSION_COUNT = 8
BUS_LINE_COUNT = 6
TRAIN_LINE_COUNT = 6
LINE_PAIR_COUNT = 6
# Each version differs from its neighbours by exactly one intervention, so the
# ballot is the edge set of a cube's worth of choices: 8 versions x 3 changes,
# each pair counted once.
BALLOT_PAIR_COUNT = 12

# The links drawn for bikes and pedestrians only. The first four came with the
# map: three homes to the S-Bahn at Bellevue, and the Justizministerium to
# Checkpoint Charlie. The other eight are F11's (drawn 2026-10-02): paths
# through the Tiergarten and round Potsdamer Platz, without which no commute on
# this map could be walked (see `ShippedMapWalkingTests`). They carry no
# `StreetEdge` row on purpose, which is how both sides already refuse a car on
# them — `canUseEdge` answers `edge.street_edge != null` and `_validate_routes`
# answers "cars not allowed on edge N". Named by their ends rather than by
# index, because an index moves whenever the file is rewritten.
SHORTCUT_ENDS = {
    ("Wohnort 1", "Bellevue"),
    ("Wohnort 2", "Bellevue"),
    ("Wohnort 3", "Bellevue"),
    ("Arbeit Justizministerium", "Checkpoint Charlie"),
    ("Bellevue", "Großer Stern"),
    ("Bellevue", "Brandenburger Tor"),
    ("Unter den Linden", "Arbeit Brandenburger Tor"),
    ("Philarmonie", "Botschaftsviertel"),
    ("Philarmonie", "U Potsdamer Platz"),
    ("U Potsdamer Platz", "Urania Berlin"),
    ("Helper Station 4", "Bundestag"),
    ("Helper Station 4", "Friedrichstadtpalast"),
}
# Every one of them both ways, but Philharmonie-Botschaftsviertel only where
# the Umgehungsstraße Süd is not drawn over it (four versions).
SHORTCUT_EDGE_COUNT = 2 * len(SHORTCUT_ENDS)

# How far anybody walks: `MAX_WALK_M` in `frontend/src/lib/map/trip-limits.ts`.
WALK_LIMIT_M = 5000


def load_shipped_map():
    with SHIPPED_MAP.open(encoding="utf-8") as fh:
        return json.load(fh)


def base_index(graph):
    for idx, version in enumerate(graph["versions"]):
        if version.get("base_version"):
            return idx
    raise AssertionError("the shipped map has no base version")


def element_versions(graph, element):
    """The versions an element belongs to.

    Absent means the base version and `[]` means nowhere — the rule
    `maps/portability.py` owns, restated here because these tests read the file
    without going through the importer.
    """
    if "versions" in element:
        return list(element["versions"])
    return [base_index(graph)]


def routes_by_version(graph, line):
    """What a line runs, in each version it belongs to.

    `chains` is the per-version form: a list of `{"versions": [...],
    "edges": [...]}` groups, so four versions running the same three links are
    one entry. A flat `edges` means "this route, in every version the line
    belongs to" — which is what every file in `map_examples/` said before S14
    and what a legacy file still says.
    """
    chains = line.get("chains")
    if chains is None:
        flat = line.get("edges", [])
        return {idx: list(flat) for idx in element_versions(graph, line)}

    routes = {}
    for group in chains:
        for idx in group.get("versions") or []:
            routes[idx] = list(group.get("edges") or [])
    return routes


def edge_ends(graph, indices):
    return [
        (graph["edges"][i]["start_node"], graph["edges"][i]["end_node"])
        for i in indices
    ]


def base_name(line_name):
    """`101 reverse` and `U2 Reverse` both belong to the pair they mirror."""
    return line_name.rsplit(" ", 1)[0] if " " in line_name else line_name


def has_street_row(edge):
    """A street edge carries its numbers; a shortcut carries none.

    The export writes `speed_limit`, `lanes` and `dedicated_bus_lane` only when
    a `StreetEdge` row exists, so their absence is the file saying "no street
    here" rather than "this file is old".
    """
    return "speed_limit" in edge


class ShippedMapVersionTests(SimpleTestCase):
    """The eight versions and the ballot between them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = load_shipped_map()
        cls.versions = cls.graph["versions"]

    def test_the_map_carries_all_of_its_versions(self):
        """A one-version file is the flattening that lost this map for a year.

        Before S14 the export filtered to a single `MapVersion` and wrote no
        version information at all, so the box's map could only be copied as
        eight unrelated maps with no vote between them.
        """
        self.assertEqual(len(self.versions), VERSION_COUNT)

    def test_exactly_one_version_is_the_base(self):
        flags = [bool(v.get("base_version")) for v in self.versions]
        self.assertEqual(flags.count(True), 1, f"base flags: {flags}")

    def test_every_version_is_named(self):
        for idx, version in enumerate(self.versions):
            with self.subTest(version=idx):
                self.assertTrue((version.get("name") or "").strip())

    def test_the_ballot_is_symmetric_and_complete(self):
        """`compatible_versions` *is* the vote.

        `_get_voteable_map_versions()` offers what the active version's m2m
        reaches, so a missing pair is a change the class can never be asked
        about. The m2m is symmetric, so a file naming one side only would
        re-import as a one-way ballot.
        """
        pairs = set()
        for idx, version in enumerate(self.versions):
            for other in version.get("compatible_versions") or []:
                with self.subTest(version=idx, other=other):
                    self.assertIn(
                        idx,
                        self.versions[other].get("compatible_versions") or [],
                        f"{self.versions[idx]['name']} offers "
                        f"{self.versions[other]['name']} but not the other way",
                    )
                pairs.add(tuple(sorted((idx, other))))
        self.assertEqual(len(pairs), BALLOT_PAIR_COUNT)

    def test_every_version_can_be_reached_from_the_base(self):
        """A version no vote leads to is a version nobody ever plays."""
        base = base_index(self.graph)
        seen = {base}
        frontier = [base]
        while frontier:
            current = frontier.pop()
            for other in self.versions[current].get("compatible_versions") or []:
                if other not in seen:
                    seen.add(other)
                    frontier.append(other)
        unreachable = [
            self.versions[i]["name"] for i in range(len(self.versions)) if i not in seen
        ]
        self.assertEqual(unreachable, [])

    def test_the_hand_drawn_versions_say_what_they_came_from(self):
        """`source_version` is what the revert poll offers to undo.

        The three atomics were drawn off the base version in the editor and
        record it. The four combinations are generated, and
        `GenerateCombinationsView` records no source — asserted as it stands
        rather than tidied, because changing it is a change to the editor.
        """
        base = base_index(self.graph)
        sourced = {
            v["name"]: v.get("source_version")
            for v in self.versions
            if v.get("source_version") is not None
        }
        self.assertEqual(
            sourced, {"Busspuren": base, "Buslinie": base, "Umgehungsstraßen": base}
        )


class ShippedMapMembershipTests(SimpleTestCase):
    """Which version every piece of the graph belongs to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = load_shipped_map()

    def test_nothing_belongs_to_no_version_at_all(self):
        """`"versions": []` is a piece of the map nobody can ever see.

        The box carried 19 such edges, 2 nodes and 3 `Bus 147` lines: third
        copies left behind when a version was drawn and redrawn, each one a
        street that already had a live original *and* a live clone. The format
        keeps `[]` distinct from absent on purpose — a backup that quietly
        promoted them to the base version would invent streets the map never
        had — so the file can say it, and this says the file does not.
        """
        for kind in ("nodes", "edges", "bus_lines", "train_lines"):
            for idx, element in enumerate(self.graph[kind]):
                with self.subTest(kind=kind, index=idx):
                    self.assertNotEqual(
                        element_versions(self.graph, element),
                        [],
                        f"{kind}[{idx}] {element.get('name')!r} belongs nowhere",
                    )

    def test_the_graph_is_counted(self):
        self.assertEqual(len(self.graph["nodes"]), NODE_COUNT)
        self.assertEqual(len(self.graph["edges"]), EDGE_COUNT)
        self.assertEqual(len(self.graph["bus_lines"]), BUS_LINE_COUNT)
        self.assertEqual(len(self.graph["train_lines"]), TRAIN_LINE_COUNT)

    def test_every_version_index_points_at_a_version(self):
        count = len(self.graph["versions"])
        for kind in ("nodes", "edges", "bus_lines", "train_lines"):
            for idx, element in enumerate(self.graph[kind]):
                for other in element_versions(self.graph, element):
                    with self.subTest(kind=kind, index=idx):
                        self.assertIsInstance(other, int)
                        self.assertLess(other, count)
                        self.assertGreaterEqual(other, 0)

    def test_no_version_has_two_links_between_the_same_nodes(self):
        """One link per direction per node pair, in every version.

        The editor refuses a second one (`edge-exists`), whatever its type, so
        a file carrying two is a map the editor cannot make. F11's
        Philharmonie-Botschaftsviertel path is the case that needs it: the
        Umgehungsstraße Süd runs over the same pair in four versions and
        already lets people walk and cycle, so the path stays out of those.
        """
        for version in range(len(self.graph["versions"])):
            seen = set()
            for idx, edge in enumerate(self.graph["edges"]):
                if version not in element_versions(self.graph, edge):
                    continue
                ends = (edge["start_node"], edge["end_node"])
                with self.subTest(version=version, edge=idx):
                    self.assertNotIn(ends, seen)
                seen.add(ends)

    def test_an_edge_lives_wherever_both_its_nodes_live(self):
        """An edge in a version whose node is missing there is a dangling edge.

        The renderer draws from the node coordinates, so this is the difference
        between a line on screen and a crash.
        """
        node_versions = {
            node["id"]: set(element_versions(self.graph, node))
            for node in self.graph["nodes"]
        }
        for idx, edge in enumerate(self.graph["edges"]):
            for version in element_versions(self.graph, edge):
                with self.subTest(edge=idx, version=version):
                    self.assertIn(version, node_versions[edge["start_node"]])
                    self.assertIn(version, node_versions[edge["end_node"]])

    def test_a_bus_lane_version_carries_its_own_copy_of_the_street(self):
        """`Busspuren` is the clone pattern, and it should look like one.

        Changing a street builds the new version by cloning the `Edge` and
        editing the clone, so the original lives in every version *but* that
        one and the clone lives in exactly the versions containing the change.
        Thirty streets — fifteen corridors, both directions — each clone
        sharing its endpoints with its original.
        This is the mechanism that damaged the chains — worth pinning as the
        shape it is supposed to have.

        It is also what the generated combinations got wrong: they held the
        original *beside* its clone, so 100 and 101 had a bus lane and a plain
        two-lane copy of the same street in every combination containing
        `Busspuren`, and the intervention did nothing there.
        """
        with_change = {
            idx
            for idx, v in enumerate(self.graph["versions"])
            if "Busspuren" in v["name"]
        }
        without = set(range(len(self.graph["versions"]))) - with_change

        clones, originals = {}, {}
        for idx, edge in enumerate(self.graph["edges"]):
            versions = set(element_versions(self.graph, edge))
            ends = (edge["start_node"], edge["end_node"])
            if versions == with_change:
                clones[ends] = idx
            elif versions == without:
                originals[ends] = idx

        self.assertEqual(len(clones), 30)
        self.assertEqual(set(clones), set(originals))
        for ends, idx in clones.items():
            with self.subTest(edge=idx):
                self.assertTrue(self.graph["edges"][idx]["dedicated_bus_lane"])
                self.assertFalse(
                    self.graph["edges"][originals[ends]]["dedicated_bus_lane"]
                )


class ShippedMapLineTests(SimpleTestCase):
    """The lines: connected, mirrored, and carrying the right numbers — per version."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = load_shipped_map()
        cls.lines = [("bus", line) for line in cls.graph["bus_lines"]] + [
            ("train", line) for line in cls.graph["train_lines"]
        ]
        cls.names = [v["name"] for v in cls.graph["versions"]]

    def test_a_line_runs_in_every_version_it_belongs_to(self):
        """A line present in a version with no route is the S15 damage itself.

        Bus `100` belonged to all eight versions and ran zero links in four of
        them: `_register_pt_line` measures it at 0 km, logs twice and returns
        before it gets a run to drive, so the map showed a line nobody could
        board and Brandenburger Tor had no bus at all.
        """
        for mode, line in self.lines:
            routes = routes_by_version(self.graph, line)
            for version in element_versions(self.graph, line):
                with self.subTest(line=line["name"], version=self.names[version]):
                    self.assertGreater(
                        len(routes.get(version, [])),
                        0,
                        f"{mode} {line['name']} runs nothing in "
                        f"{self.names[version]}",
                    )

    def test_a_line_runs_nowhere_it_does_not_belong(self):
        """The mirror image: a route in a version the line is not in.

        Cheap to state and it pins the file's own consistency — a chain group
        naming a version the line left is a row the importer would drop.
        """
        for _, line in self.lines:
            belongs = set(element_versions(self.graph, line))
            for version in routes_by_version(self.graph, line):
                with self.subTest(line=line["name"], version=self.names[version]):
                    self.assertIn(version, belongs)

    def test_every_line_is_one_connected_walk_in_every_version(self):
        """`node_chain` has to reach the end of the edge list.

        This is the check `_register_pt_line` makes at runtime, where the answer
        is a truncated line and a warning in the log nobody reads — and a
        truncated line is charged only for what it drives, so it silently
        becomes a different line. A chain that is whole has exactly one more
        node than it has edges.
        """
        for mode, line in self.lines:
            for version, route in routes_by_version(self.graph, line).items():
                with self.subTest(line=line["name"], version=self.names[version]):
                    chain = node_chain(edge_ends(self.graph, route))
                    self.assertEqual(
                        len(chain),
                        len(route) + 1,
                        f"{mode} {line['name']} in {self.names[version]} breaks "
                        f"after {max(0, len(chain) - 1)} of {len(route)} edges",
                    )

    def test_every_line_runs_on_edges_that_exist_in_that_version(self):
        """A route over a street the version does not have is not a route.

        This is the invariant the chain damage broke from the other side: the
        rows moved onto the `Busspuren` clones, and a version without
        `Busspuren` then pointed at streets it does not contain.
        """
        for _, line in self.lines:
            for version, route in routes_by_version(self.graph, line).items():
                for edge_index in route:
                    edge = self.graph["edges"][edge_index]
                    with self.subTest(
                        line=line["name"], version=self.names[version], edge=edge_index
                    ):
                        self.assertIn(
                            version,
                            element_versions(self.graph, edge),
                            f"{line['name']} runs {edge['name']!r} in "
                            f"{self.names[version]}, which does not have it",
                        )

    def test_every_line_names_the_side_of_the_street_it_drives(self):
        """A line names the link going ITS way wherever the version has one.

        Each direction of a street is its own link with its own queue (F2a), and
        `node_chain` reads a line's travel order from the nodes, so a chain row
        naming the other direction passes every test above. Bus `100` eastbound
        named the westbound links from Ernst-Reuter Platz to Arbeit Brandenburger
        Tor, in all eight versions. The simulator now drives the right side
        whatever the file says (`TrafficSimulator._its_own_way`); this keeps the
        file honest, and what the editor and the replay draw with it.
        """
        edges = self.graph["edges"]
        for mode, line in self.lines:
            for version, route in routes_by_version(self.graph, line).items():
                stops = node_chain(edge_ends(self.graph, route))
                for i, edge_index in enumerate(route[: len(stops) - 1]):
                    here, there = stops[i], stops[i + 1]
                    edge = edges[edge_index]
                    if (edge["start_node"], edge["end_node"]) != (there, here):
                        continue
                    own_way = [
                        j
                        for j, other in enumerate(edges)
                        if (other["start_node"], other["end_node"]) == (here, there)
                        and version in element_versions(self.graph, other)
                        and (
                            has_street_row(other)
                            if mode == "bus"
                            else other["type"] in ("train", "both")
                        )
                    ]
                    with self.subTest(
                        line=line["name"], version=self.names[version], edge=edge_index
                    ):
                        self.assertEqual(
                            own_way,
                            [],
                            f"{mode} {line['name']} runs {edge['name']!r} against "
                            f"its direction in {self.names[version]}; edge "
                            f"{own_way} goes its way",
                        )

    def test_rail_runs_in_every_version(self):
        """`GenerateCombinationsView` copies nodes, edges and `BusLine` — not rail.

        So all four generated combinations shipped with no train lines at all,
        and three of the games on the box were played on one of them: a map
        where the U-Bahn simply does not exist, which reads to a class as "the
        bus lane made everyone drive".
        """
        every_version = set(range(len(self.graph["versions"])))
        for line in self.graph["train_lines"]:
            with self.subTest(line=line["name"]):
                self.assertEqual(
                    set(element_versions(self.graph, line)),
                    every_version,
                    f"{line['name']} is missing from "
                    f"{[self.names[i] for i in sorted(every_version - set(element_versions(self.graph, line)))]}",
                )

    def test_the_new_bus_line_runs_only_where_it_was_drawn(self):
        """147 is the `Buslinie` intervention, so it exists nowhere else.

        The counterpart to the rail test: rail belongs everywhere because it is
        part of the city, and 147 belongs to four versions because it is the
        change being voted on.
        """
        drawn = {
            idx
            for idx, v in enumerate(self.graph["versions"])
            if "Buslinie" in v["name"]
        }
        self.assertEqual(len(drawn), 4)
        for line in self.graph["bus_lines"]:
            if base_name(line["name"]) != "147":
                continue
            with self.subTest(line=line["name"]):
                self.assertEqual(set(element_versions(self.graph, line)), drawn)

    def test_a_line_and_its_reverse_serve_the_same_stops(self):
        """Both directions of a line, or a stop served one way only.

        `101` ran nine stops one way and three the other; `U2` stopped at
        Ernst-Reuter Platz westbound while `U2 Reverse` carried on to
        Kaiserdamm. A rider going to work can get there and not back — and
        since the damage was per version, so is the check.
        """
        by_name = {line["name"]: line for _, line in self.lines}
        pairs = [
            (name, other)
            for name in by_name
            for other in by_name
            if name != other and base_name(other) == name
        ]
        self.assertEqual(len(pairs), LINE_PAIR_COUNT, f"line pairs: {sorted(pairs)}")

        for forward, reverse in pairs:
            out = routes_by_version(self.graph, by_name[forward])
            back = routes_by_version(self.graph, by_name[reverse])
            self.assertEqual(
                sorted(out),
                sorted(back),
                f"{forward} and {reverse} do not run in the same versions",
            )
            for version in out:
                with self.subTest(pair=forward, version=self.names[version]):
                    self.assertEqual(
                        node_chain(edge_ends(self.graph, out[version])),
                        list(reversed(node_chain(edge_ends(self.graph, back[version])))),
                        f"{forward} and {reverse} do not mirror each other in "
                        f"{self.names[version]}",
                    )

    def test_every_line_carries_the_seats_of_its_mode(self):
        """The 60-seat U-Bahn came from a file, not from a default.

        `maps/0008` fixed the rows on the box, which is why the export already
        reads 85 and 1000 — pinned so a future hand-drawn line cannot
        reintroduce the number that made a full bus an ending.
        """
        for mode, line in self.lines:
            with self.subTest(line=line["name"]):
                expected = BUS_CAPACITY if mode == "bus" else TRAIN_CAPACITY
                self.assertEqual(line["capacity"], expected)

    def test_every_line_says_how_fast_it_drives(self):
        """Read by the simulator and by the client's route preview.

        Both sides take it from the line (`bus_line_speeds` in
        `game/simulation.py`, `line.speed_kmh` in `ptRouting.ts`), so a bus at
        50 km/h is a bus that never stops — which is what 100 and 101 were on
        the box. The two directions of one line have to agree, or the trip home
        is not the trip out: `U7` ran at 40 and `U7 reverse` at 30.
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
            for version, route in routes_by_version(self.graph, line).items():
                for node_id in node_chain(edge_ends(self.graph, route)):
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
        "this file is older than the field". `maps/0006` added it.
        """
        for idx, edge in enumerate(self.graph["edges"]):
            with self.subTest(edge=idx):
                self.assertIn("bike_lane", edge)

    def test_every_street_a_car_can_use_states_its_speed_limit_and_lanes(self):
        """The speed limit is what the free-flow time and the CO2 curve run on.

        Stated for every street that carries a `StreetEdge` row. The shortcuts
        below are the deliberate exception and are checked by name, so this
        cannot quietly pass because a street lost its row.
        """
        for idx, edge in enumerate(self.graph["edges"]):
            if edge.get("type", "both") not in ("street", "both"):
                continue
            if not has_street_row(edge):
                continue
            with self.subTest(edge=idx):
                self.assertIn("speed_limit", edge)
                self.assertIn("lanes", edge)
                self.assertIn("dedicated_bus_lane", edge)

    def test_the_shortcuts_are_for_bikes_and_pedestrians_only(self):
        """Twelve links with no street under them, and that is the point.

        Three homes reach the S-Bahn at Bellevue and the Justizministerium
        reaches Checkpoint Charlie on foot or by bike; a car has to go round by
        Turmstraße. The Tiergarten paths take the walk to Brandenburger Tor,
        Lützowplatz, TU Berlin and Hegelplatz under an hour. Carrying no
        `StreetEdge` row is how the map says so, and both sides already read
        it: `canUseEdge` answers `edge.street_edge != null` for a car and
        `_validate_routes` refuses the submit with "cars not allowed on edge N".

        Pinned by their ends, in both directions, because these are the only
        edges in the file without a street row or a railway — and an editor
        pass that gave them lanes would silently open a fast shortcut past
        every front door.
        """
        names = {node["id"]: node.get("name") for node in self.graph["nodes"]}
        found = set()
        for idx, edge in enumerate(self.graph["edges"]):
            if edge.get("type", "both") != "path":
                continue
            ends = (names[edge["start_node"]], names[edge["end_node"]])
            with self.subTest(edge=idx):
                self.assertIn(
                    frozenset(ends),
                    {frozenset(pair) for pair in SHORTCUT_ENDS},
                    f"edge {idx} {ends} is a path and is not a known shortcut",
                )
                self.assertTrue(edge["walking"])
                self.assertTrue(edge["biking"])
                self.assertNotIn("speed_limit", edge)
            found.add(frozenset(ends))
        self.assertEqual(found, {frozenset(pair) for pair in SHORTCUT_ENDS})

    def test_no_street_hides_behind_a_missing_speed_limit(self):
        """The other half: a `street` edge always states its numbers.

        Before `"path"` existed the export wrote both cases as `"street"` and
        the importer answered by inventing a 50 km/h lane, so this is the
        assertion that says the file no longer relies on that reading.
        """
        for idx, edge in enumerate(self.graph["edges"]):
            if edge.get("type", "both") not in ("street", "both"):
                continue
            with self.subTest(edge=idx):
                self.assertTrue(has_street_row(edge))

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
        way alongside. This map does not make it: its rail edges are rail. The
        `"type": "both"` edges are street-and-rail and stay open, which is why
        this test names the type instead of the TrainEdge.
        """
        rail = [e for e in self.graph["edges"] if e.get("type") == "train"]
        self.assertEqual(len(rail), 46)
        for edge in rail:
            with self.subTest(edge=edge["name"]):
                self.assertFalse(edge["biking"])
                self.assertFalse(edge["walking"])


class ShippedMapWalkingTests(SimpleTestCase):
    """Whether anybody can walk to work on this map.

    Before F11 three of 36 home/workplace pairs fell inside the 5 km walk cap,
    the shortest at 4.84 km: walking was a mode the game offered and almost
    never allowed. The Tiergarten paths make it 14 in every version, the
    shortest 2.75 km (Wohnort 2 to Arbeit Brandenburger Tor). Measured here the
    way the client router measures it — a link is as long as the straight line
    between its nodes times the map's scale, and anything not saying
    `"walking": false` may be walked — so this is the same number the student
    meets when "zu Fuß" is or is not offered.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = load_shipped_map()
        nodes = {node["id"]: node for node in cls.graph["nodes"]}
        cls.homes = [n["id"] for n in cls.graph["nodes"] if "home" in n["types"]]
        cls.workplaces = [
            n["id"] for n in cls.graph["nodes"] if "workplace" in n["types"]
        ]
        cls.names = {node_id: node["name"] for node_id, node in nodes.items()}
        cls.walks = {}
        for version in range(len(cls.graph["versions"])):
            links = {}
            for edge in cls.graph["edges"]:
                if version not in element_versions(cls.graph, edge):
                    continue
                if edge.get("walking") is False:
                    continue
                a, b = nodes[edge["start_node"]], nodes[edge["end_node"]]
                length = math.hypot(a["x"] - b["x"], a["y"] - b["y"]) * cls.graph["scale"]
                links.setdefault(edge["start_node"], []).append((edge["end_node"], length))
            cls.walks[version] = links

    def shortest_walk_m(self, version, start, end):
        links = self.walks[version]
        best = {start: 0.0}
        queue = [(0.0, start)]
        while queue:
            dist, node = heapq.heappop(queue)
            if node == end:
                return dist
            if dist > best[node]:
                continue
            for other, length in links.get(node, []):
                if dist + length < best.get(other, math.inf):
                    best[other] = dist + length
                    heapq.heappush(queue, (dist + length, other))
        return math.inf

    def walkable(self, version):
        """The pairs inside the cap both ways — a round is there and back."""
        return {
            (home, work)
            for home in self.homes
            for work in self.workplaces
            if self.shortest_walk_m(version, home, work) <= WALK_LIMIT_M
            and self.shortest_walk_m(version, work, home) <= WALK_LIMIT_M
        }

    def test_a_commute_can_be_walked_in_every_version(self):
        self.assertEqual(len(self.homes) * len(self.workplaces), 36)
        for version in range(len(self.graph["versions"])):
            with self.subTest(version=self.graph["versions"][version]["name"]):
                self.assertEqual(len(self.walkable(version)), 14)

    def test_the_shortest_walk_is_through_the_tiergarten(self):
        base = base_index(self.graph)
        shortest = min(
            (self.shortest_walk_m(base, home, work), self.names[home], self.names[work])
            for home in self.homes
            for work in self.workplaces
        )
        self.assertAlmostEqual(shortest[0], 2750, delta=5)
        self.assertEqual(shortest[1:], ("Wohnort 2", "Arbeit Brandenburger Tor"))


class ShippedMapImportsTests(MapUploadMixin, TestCase):
    """The file through `/map/upload/`, which is how it reaches a box.

    `MapUploadMixin` comes from `test_portability` rather than being copied:
    the upload form has two required fields and a rejected form answers 200
    with the form re-rendered, so the mixin's `uploaded_map` failure message is
    the difference between a readable red and a bare DoesNotExist.
    """

    def upload_shipped_map(self):
        graph = load_shipped_map()
        # The background image is ~970 KB of base64 in this file and the import
        # writes it to disk. TempMediaRootMixin would clean it up, but the
        # picture is not what these tests are about — `test_portability` pins
        # the image round trip on a 2x2 PNG.
        graph.pop("background_image", None)
        return self.upload(graph, name="Berlin Mitte-West", max_players=6)

    def test_the_shipped_map_imports_whole(self):
        game_map = self.upload_shipped_map()

        self.assertEqual(Node.objects.filter(game_map=game_map).count(), NODE_COUNT)
        self.assertEqual(Edge.objects.filter(game_map=game_map).count(), EDGE_COUNT)
        self.assertEqual(
            MapVersion.objects.filter(game_map=game_map).count(), VERSION_COUNT
        )
        self.assertEqual(game_map.max_player, 6)
        self.assertEqual(game_map.district_commuters, 6400)
        self.assertEqual(game_map.co2_budget_kg_per_round, 16000)

    def test_the_shipped_map_arrives_measured(self):
        """S2 measured the pair on this map, so the create form must not
        warn about it. Every other map starts unmeasured."""
        game_map = self.upload_shipped_map()

        self.assertTrue(game_map.calibrated)

    def test_the_ballot_survives_the_import(self):
        """`compatible_versions` is the one thing the flattened export lost.

        Twelve pairs, and each one is a question the class gets asked. Counted
        as rows rather than pairs because the m2m is symmetric and writes both
        sides.
        """
        game_map = self.upload_shipped_map()
        versions = MapVersion.objects.filter(game_map=game_map)

        rows = sum(v.compatible_versions.count() for v in versions)
        self.assertEqual(rows, BALLOT_PAIR_COUNT * 2)

        base = versions.get(base_version=True)
        self.assertEqual(
            sorted(v.name for v in base.compatible_versions.all()),
            ["Buslinie", "Busspuren", "Umgehungsstraßen"],
        )

    def test_a_version_is_built_on_by_the_combinations_holding_it(self):
        """F10's rule, read off the real eight versions.

        Combinations record no members, so `versions_built_on` derives them
        from what each version holds. On this map that must come out as the
        names say: base under everything, `Busspuren` under the three
        combinations with `Busspuren` in them, a pair under the triple. If a
        data pass ever leaves a change half-copied into its combinations, the
        derivation stops seeing them — and this is where that shows.
        """
        from maps.versions import versions_built_on

        game_map = self.upload_shipped_map()
        versions = list(MapVersion.objects.filter(game_map=game_map))

        def parts(version):
            return set() if version.base_version else set(version.name.split(" + "))

        for version in versions:
            with self.subTest(version=version.name):
                expected = {v.name for v in versions if parts(v) >= parts(version)}
                self.assertEqual(
                    {v.name for v in versions_built_on(version)}, expected
                )

    def test_deleting_a_version_leaves_the_other_seven_whole(self):
        """F14's rule on the real lattice: `Busspuren`, whose every row its
        three combinations hold as well, takes nothing but itself and its
        three ballot pairs.

        No row of this map is in one version only — the triple combination
        holds every change — so this was green before F14 too. It is here so
        a cleanup that ever reads "only in this version" wrong shows up on the
        map that matters, not on a fixture.
        """
        from django.urls import reverse

        from maps.models import (
            BusLineEdge,
            StreetEdge,
            TrainEdge,
            TrainLineEdge,
        )

        models = (
            Node,
            Edge,
            StreetEdge,
            TrainEdge,
            BusLine,
            TrainLine,
            BusLineEdge,
            TrainLineEdge,
        )
        game_map = self.upload_shipped_map()
        versions = MapVersion.objects.filter(game_map=game_map)
        victim = versions.get(name="Busspuren")

        def held(version):
            return {
                model.__name__: set(
                    model.objects.filter(map_versions=version).values_list(
                        "pk", flat=True
                    )
                )
                for model in models
            }

        def in_no_version():
            return {
                model.__name__: model.objects.filter(map_versions__isnull=True).count()
                for model in models
            }

        others = list(versions.exclude(pk=victim.pk))
        before = {version.name: held(version) for version in others}
        strays = in_no_version()

        response = self.client.delete(
            reverse(
                "maps:mapversion-detail",
                kwargs={"pk": game_map.pk, "version_pk": victim.pk},
            )
        )

        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual({version.name: held(version) for version in others}, before)
        self.assertEqual(in_no_version(), strays)
        self.assertEqual(
            sum(v.compatible_versions.count() for v in versions),
            (BALLOT_PAIR_COUNT - 3) * 2,
        )

    def test_the_lines_arrive_with_their_seats_and_their_speed(self):
        game_map = self.upload_shipped_map()

        buses = BusLine.objects.filter(game_map=game_map)
        trains = TrainLine.objects.filter(game_map=game_map)
        self.assertEqual(buses.count(), BUS_LINE_COUNT)
        self.assertEqual(trains.count(), TRAIN_LINE_COUNT)
        for bus in buses:
            with self.subTest(line=bus.name):
                self.assertEqual(bus.bus_capacity, BUS_CAPACITY)
                self.assertEqual(bus.bus_speed_kmh, BUS_SPEED_KMH)
        for train in trains:
            with self.subTest(line=train.name):
                self.assertEqual(train.train_capacity, TRAIN_CAPACITY)
                self.assertIn(train.train_speed_kmh, TRAIN_SPEEDS_KMH)

    def test_every_line_reports_a_whole_stop_list_in_every_version(self):
        """The serializer is what `ptRouting.ts` boards people with.

        Same walk as `node_chain`, one layer up and after a real import — so
        this is the check the pure-JSON tests cannot make: that the edges
        arrived in the order the file gave them, that the M2M kept it, and that
        it kept it *per version*, which is the whole of S15.
        """
        game_map = self.upload_shipped_map()

        for version in MapVersion.objects.filter(game_map=game_map):
            for line in BusLine.objects.filter(
                game_map=game_map, map_versions=version
            ):
                with self.subTest(line=line.name, version=version.name):
                    data = serialize_bus_line_for_graph(line, version)
                    self.assertGreater(len(data["edges"]), 0)
                    self.assertEqual(len(data["stops"]), len(data["edges"]) + 1)
            for line in TrainLine.objects.filter(
                game_map=game_map, map_versions=version
            ):
                with self.subTest(line=line.name, version=version.name):
                    data = serialize_train_line_for_graph(line, version)
                    self.assertGreater(len(data["edges"]), 0)
                    self.assertEqual(len(data["stops"]), len(data["edges"]) + 1)

    def test_a_shortcut_arrives_without_a_street(self):
        """The carless links have to stay carless through an import.

        `_create_street_edge` is called from the edge loop, so a shortcut that
        arrived with a `StreetEdge` row would open a car route from every home
        to Bellevue — and nothing else in the suite would notice.
        """
        game_map = self.upload_shipped_map()

        # `Edge` has no `type` column — the file's `type` is derived on export
        # from which of the two rows exist, so "neither" is the shortcut.
        carless = [
            edge
            for edge in Edge.objects.filter(game_map=game_map).prefetch_related(
                "streetedge_set", "trainedge_set"
            )
            if not edge.streetedge_set.exists() and not edge.trainedge_set.exists()
        ]
        self.assertEqual(len(carless), SHORTCUT_EDGE_COUNT)
        for edge in carless:
            with self.subTest(edge=edge.pk):
                self.assertTrue(edge.walking)
                self.assertTrue(edge.biking)
