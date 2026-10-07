"""What `maps/checks.py` says about a map file, on a map small enough to read.

The shipped map passes every check (`test_example_map.py` runs them over
`map_examples/`), which proves only that the checks do not cry wolf. These are
the other half: each test breaks one rule on a six-node map and expects that
rule, by name, to say so.
"""

import copy
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from maps.checks import check_map


def street(start, end, versions=(0, 1), **fields):
    edge = {
        "start_node": start,
        "end_node": end,
        "name": f"{start}-{end}",
        "type": "street",
        "biking": True,
        "bike_lane": False,
        "walking": True,
        "speed_limit": 50,
        "lanes": 1,
        "dedicated_bus_lane": False,
        "versions": list(versions),
    }
    edge.update(fields)
    return edge


def small_map():
    """Home, two stops, a workplace and a station; a bypass in version 1.

    Edges by index:
      0/1 h-a, 2/3 a-b, 4/5 b-w (streets) · 6/7 h-w (path)
      8/9 a-c, 10/11 c-b (streets, bypass only) · 12/13 b-s (rail)
    Bus 1 runs a→b, its reverse b→a; S1 runs b→s and back.
    """
    rail = {
        "type": "train",
        "biking": False,
        "bike_lane": False,
        "walking": False,
        "versions": [0, 1],
    }
    path = {
        "type": "path",
        "biking": True,
        "bike_lane": False,
        "walking": True,
        "versions": [0, 1],
    }
    return {
        "scale": 1000.0,
        "map": {"name": "Klein", "x_dim": 4, "y_dim": 2},
        "versions": [
            {
                "name": "Klein",
                "base_version": True,
                "compatible_versions": [1],
            },
            {
                "name": "Umgehung",
                "base_version": False,
                "source_version": 0,
                "compatible_versions": [0],
            },
        ],
        "nodes": [
            {
                "id": "h",
                "name": "Wohnort",
                "x": 0,
                "y": 0,
                "types": ["home"],
                "versions": [0, 1],
            },
            {
                "id": "a",
                "name": "A",
                "x": 1,
                "y": 0,
                "types": ["bus_stop"],
                "versions": [0, 1],
            },
            {
                "id": "b",
                "name": "B",
                "x": 2,
                "y": 0,
                "types": ["bus_stop", "station"],
                "versions": [0, 1],
            },
            {
                "id": "w",
                "name": "Arbeit",
                "x": 3,
                "y": 0,
                "types": ["workplace"],
                "versions": [0, 1],
            },
            {
                "id": "c",
                "name": "C",
                "x": 1.5,
                "y": 1,
                "types": ["intersection"],
                "versions": [1],
            },
            {
                "id": "s",
                "name": "S",
                "x": 2,
                "y": 1,
                "types": ["station"],
                "versions": [0, 1],
            },
        ],
        "edges": [
            street("h", "a"),
            street("a", "h"),
            street("a", "b"),
            street("b", "a"),
            street("b", "w"),
            street("w", "b"),
            {"start_node": "h", "end_node": "w", "name": "Pfad", **path},
            {"start_node": "w", "end_node": "h", "name": "Pfad", **path},
            street("a", "c", versions=[1]),
            street("c", "a", versions=[1]),
            street("c", "b", versions=[1]),
            street("b", "c", versions=[1]),
            {"start_node": "b", "end_node": "s", "name": "Gleis", **rail},
            {"start_node": "s", "end_node": "b", "name": "Gleis", **rail},
        ],
        "bus_lines": [
            {
                "name": "1",
                "interval": 10,
                "capacity": 85,
                "speed_kmh": 30,
                "versions": [0, 1],
                "edges": [2],
            },
            {
                "name": "1 reverse",
                "interval": 10,
                "capacity": 85,
                "speed_kmh": 30,
                "versions": [0, 1],
                "edges": [3],
            },
        ],
        "train_lines": [
            {
                "name": "S1",
                "interval": 5,
                "capacity": 1000,
                "speed_kmh": 50,
                "versions": [0, 1],
                "edges": [12],
            },
            {
                "name": "S1 reverse",
                "interval": 5,
                "capacity": 1000,
                "speed_kmh": 50,
                "versions": [0, 1],
                "edges": [13],
            },
        ],
    }


class CheckMapTests(SimpleTestCase):
    def setUp(self):
        self.graph = small_map()

    def found(self, graph=None):
        return check_map(self.graph if graph is None else graph)

    def assertReports(self, check, graph=None):
        problems = self.found(graph)
        self.assertIn(check, {p.check for p in problems}, problems)
        return problems

    def test_a_sound_map_has_no_problems(self):
        self.assertEqual(self.found(), [])

    def test_a_file_the_upload_refuses_is_reported_and_nothing_else(self):
        """The later checks index into the file; on a broken one they would crash."""
        self.graph["edges"][0]["end_node"] = "nirgends"
        problems = self.found()
        self.assertEqual({p.check for p in problems}, {"upload"})
        self.assertIn("nirgends", problems[0].message)

    def test_a_ballot_offered_one_way(self):
        self.graph["versions"][1]["compatible_versions"] = []
        self.assertReports("ballot-one-way")

    def test_a_version_no_vote_leads_to(self):
        self.graph["versions"].append({"name": "Insel", "base_version": False})
        self.assertReports("version-unreachable")

    def test_an_element_in_no_version(self):
        self.graph["edges"][6]["versions"] = []
        problems = self.assertReports("in-no-version")
        self.assertTrue(any("Pfad" in p.message for p in problems))

    def test_two_links_between_the_same_nodes_in_one_version(self):
        self.graph["edges"].append(street("h", "a"))
        self.assertReports("link-twice")

    def test_the_same_pair_in_two_versions_is_not_twice(self):
        """The clone pattern: original in one version, clone in the other."""
        self.graph["edges"][0]["versions"] = [0]
        self.graph["edges"].append(
            street("h", "a", versions=[1], dedicated_bus_lane=True, lanes=2)
        )
        self.assertEqual(self.found(), [])

    def test_an_edge_in_a_version_its_node_is_not_in(self):
        self.graph["edges"][8]["versions"] = [0, 1]
        self.assertReports("edge-without-node")

    def test_a_line_that_runs_nothing_in_one_of_its_versions(self):
        line = self.graph["bus_lines"][0]
        del line["edges"]
        line["chains"] = [
            {"versions": [0], "edges": [2]},
            {"versions": [1], "edges": []},
        ]
        self.assertReports("line-runs-nothing")

    def test_a_line_that_runs_where_it_does_not_belong(self):
        line = self.graph["bus_lines"][0]
        line["versions"] = [0]
        del line["edges"]
        line["chains"] = [{"versions": [0, 1], "edges": [2]}]
        self.assertReports("line-outside-its-versions")

    def test_a_line_that_breaks(self):
        self.graph["bus_lines"][0]["edges"] = [0, 4]
        problems = self.assertReports("line-broken")
        self.assertTrue(any("nach 1 von 2" in p.message for p in problems))

    def test_a_line_over_a_street_its_version_does_not_have(self):
        self.graph["bus_lines"][0]["edges"] = [8, 10]
        problems = [p for p in self.found() if p.check == "line-off-version"]
        self.assertEqual(len(problems), 2, problems)
        for problem in problems:
            self.assertIn("Klein", problem.message)
            self.assertNotIn("Umgehung", problem.message)

    def test_a_line_on_the_other_side_of_the_street(self):
        """a→h then a→b travels h, a, b — so the first link is the wrong way.

        One problem per line, naming every version it happens in.
        """
        self.graph["nodes"][0]["types"].append("bus_stop")
        self.graph["bus_lines"][0]["edges"] = [1, 2]
        self.graph["bus_lines"][1]["edges"] = [3, 0]
        problems = [p for p in self.found() if p.check == "line-wrong-side"]
        self.assertEqual(len(problems), 2, problems)
        for problem in problems:
            self.assertIn("Klein", problem.message)
            self.assertIn("Umgehung", problem.message)

    def test_a_line_with_no_way_its_own_side_is_left_alone(self):
        """A line on a one-way street names the only link there is.

        h→a exists only in the bypass version; in the base, running a→h
        backwards is all a bus from h can do, and that is no defect.
        """
        self.graph["nodes"][0]["types"].append("bus_stop")
        self.graph["edges"][0]["versions"] = [1]
        self.graph["bus_lines"][0]["edges"] = [1, 2]
        self.graph["bus_lines"][1]["edges"] = [3, 1]
        problems = [p for p in self.found() if p.check == "line-wrong-side"]
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("Umgehung", problems[0].message)
        self.assertNotIn("Klein", problems[0].message)

    def test_a_train_line_on_the_other_track(self):
        rail = dict(self.graph["edges"][12], name="Gleis 2")
        self.graph["nodes"].append(
            {
                "id": "t",
                "name": "T",
                "x": 3,
                "y": 1,
                "types": ["station"],
                "versions": [0, 1],
            }
        )
        self.graph["edges"] += [
            dict(rail, start_node="s", end_node="t"),  # 14
            dict(rail, start_node="t", end_node="s"),  # 15
        ]
        self.graph["train_lines"][0]["edges"] = [12, 15]
        self.graph["train_lines"][1]["edges"] = [15, 13]
        problems = [p for p in self.found() if p.check == "line-wrong-side"]
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("S1", problems[0].message)
        self.assertNotIn("S1 reverse", problems[0].message)

    def test_a_line_that_ends_where_nobody_can_board(self):
        self.graph["bus_lines"][0]["edges"] = [0]
        problems = self.assertReports("line-end-not-a-stop")
        self.assertTrue(any("Wohnort" in p.message for p in problems))

    def test_a_line_without_seats_or_speed(self):
        self.graph["bus_lines"][0]["capacity"] = 0
        del self.graph["train_lines"][1]["speed_kmh"]
        problems = [p for p in self.found() if p.check == "line-figures"]
        self.assertEqual(len(problems), 2, problems)

    def test_a_line_that_never_comes(self):
        self.graph["bus_lines"][0]["interval"] = 0
        self.assertReports("line-figures")

    def test_an_edge_that_does_not_state_its_bike_lane(self):
        del self.graph["edges"][4]["bike_lane"]
        self.assertReports("bike-lane-unstated")

    def test_a_street_missing_one_of_its_numbers(self):
        del self.graph["edges"][2]["lanes"]
        self.assertReports("street-numbers")

    def test_a_street_stating_none_of_its_numbers(self):
        """Read as a path by the importer — say so rather than let it pass."""
        for field in ("speed_limit", "lanes", "dedicated_bus_lane"):
            del self.graph["edges"][2][field]
        self.assertReports("street-numbers")

    def test_a_path_with_a_street_on_it(self):
        self.graph["edges"][6]["speed_limit"] = 30
        self.assertReports("path-numbers")

    def test_a_path_nobody_may_use(self):
        self.graph["edges"][7]["walking"] = False
        self.graph["edges"][7]["biking"] = False
        self.assertReports("path-closed")

    def test_a_speed_limit_of_zero(self):
        self.graph["edges"][0]["speed_limit"] = 0
        self.assertReports("street-figures")

    def test_a_street_with_no_lanes(self):
        self.graph["edges"][0]["lanes"] = 0
        self.assertReports("street-figures")

    def test_a_map_with_nowhere_to_live(self):
        self.graph["nodes"][0]["types"] = ["intersection"]
        self.assertReports("no-home-or-work")

    def test_a_map_with_nowhere_to_work(self):
        self.graph["nodes"][3]["types"] = ["intersection"]
        self.assertReports("no-home-or-work")

    def test_a_commute_with_no_way_back(self):
        """There and back is a round: no way home is no commute."""
        self.graph["edges"][5]["versions"] = [1]
        self.graph["edges"][7]["versions"] = [1]
        problems = self.assertReports("no-way")
        message = next(p.message for p in problems if p.check == "no-way")
        self.assertIn("Arbeit", message)
        self.assertIn("Wohnort", message)
        self.assertIn("Klein", message)

    def test_a_line_counts_as_a_way(self):
        """Riding the train is a way even where nobody may walk the track."""
        self.graph["nodes"][5]["types"].append("workplace")
        self.assertEqual(self.found(), [])

    def test_a_railway_with_no_line_is_no_way(self):
        self.graph["nodes"][5]["types"].append("workplace")
        self.graph["train_lines"] = []
        self.assertReports("no-way")

    def test_a_flat_file_is_one_base_version(self):
        """No `versions` block: every element is in the one implicit base."""
        flat = copy.deepcopy(self.graph)
        del flat["versions"]
        for kind in ("nodes", "edges", "bus_lines", "train_lines"):
            for element in flat[kind]:
                element.pop("versions", None)
        flat["nodes"] = [n for n in flat["nodes"] if n["id"] != "c"]
        flat["edges"] = flat["edges"][:8] + flat["edges"][12:]
        flat["train_lines"][0]["edges"] = [8]
        flat["train_lines"][1]["edges"] = [9]
        self.assertEqual(self.found(flat), [])


class TramCheckTests(SimpleTestCase):
    """A→B becomes a tram street: the M1's rails in the car lane, both ways."""

    def setUp(self):
        self.graph = small_map()
        for idx in (2, 3):
            self.graph["edges"][idx]["type"] = "tram"
            self.graph["edges"][idx]["tram_track"] = "lane"
        tram = {"interval": 10, "capacity": 248, "speed_kmh": 20, "kind": "tram"}
        self.graph["train_lines"] += [
            {"name": "M1", "versions": [0, 1], "edges": [2], **tram},
            {"name": "M1 reverse", "versions": [0, 1], "edges": [3], **tram},
        ]

    def checks(self):
        return {problem.check for problem in check_map(self.graph)}

    def test_a_tram_on_rails_in_the_car_lane_is_sound(self):
        self.assertEqual(check_map(self.graph), [])

    def test_an_s_or_u_bahn_on_rails_in_the_car_lane_is_reported(self):
        self.graph["train_lines"][2]["kind"] = "train"

        problems = [p for p in check_map(self.graph) if p.check == "train-in-car-lane"]

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("M1", problems[0].message)
        self.assertIn("Kante 2", problems[0].message)

    def test_a_line_that_does_not_say_its_kind_is_a_train(self):
        del self.graph["train_lines"][3]["kind"]

        self.assertIn("train-in-car-lane", self.checks())

    def test_its_own_track_takes_any_train(self):
        """The rule is the car lane: on its own track nothing waits with cars."""
        for idx in (2, 3):
            self.graph["edges"][idx]["tram_track"] = "own"
            self.graph["edges"][idx]["lanes"] = 2
        self.graph["train_lines"][2]["kind"] = "train"

        self.assertNotIn("train-in-car-lane", self.checks())

    def test_a_tram_street_without_its_rails_in_a_version_is_reported(self):
        self.graph["edges"][2]["train_versions"] = [0]

        problems = [p for p in check_map(self.graph) if p.check == "tram-without-rails"]

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("Umgehung", problems[0].message)
        self.assertNotIn("Klein", problems[0].message)

    def test_a_tram_street_states_its_numbers_like_a_street(self):
        del self.graph["edges"][2]["lanes"]

        self.assertIn("street-numbers", self.checks())


class CheckMapCommandTests(SimpleTestCase):
    def run_command(self, *paths):
        out = StringIO()
        call_command("check_map", *map(str, paths), stdout=out)
        return out.getvalue()

    def write(self, graph):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        with handle:
            json.dump(graph, handle)
        self.addCleanup(Path(handle.name).unlink)
        return Path(handle.name)

    def test_a_sound_file_says_so(self):
        path = self.write(small_map())
        output = self.run_command(path)
        self.assertIn(path.name, output)
        self.assertIn("in Ordnung", output)

    def test_a_broken_file_names_every_problem_and_fails(self):
        graph = small_map()
        graph["edges"][0]["speed_limit"] = 0
        graph["bus_lines"][0]["capacity"] = 0
        path = self.write(graph)

        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("check_map", str(path), stdout=out)
        output = out.getvalue()
        self.assertIn("street-figures", output)
        self.assertIn("line-figures", output)

    def test_every_file_is_checked_before_it_fails(self):
        broken = small_map()
        broken["bus_lines"][0]["capacity"] = 0
        sound = self.write(small_map())
        bad = self.write(broken)

        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("check_map", str(bad), str(sound), stdout=out)
        self.assertIn(sound.name, out.getvalue())

    def test_a_file_that_is_not_json(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        with handle:
            handle.write("{ kaputt")
        self.addCleanup(Path(handle.name).unlink)

        with self.assertRaises(CommandError):
            self.run_command(handle.name)
