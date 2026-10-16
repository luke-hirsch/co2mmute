"""One whole build of a cut of real data, offline: Bremen's station and old town."""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

from maps.checks import check_map
from mapbuild import area, build
from mapbuild.tests import fixture_dir, offline

BACKEND = Path(__file__).resolve().parents[2]
BOX = (53.06, 8.775, 53.095, 8.84)


class WholeBuildTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with offline():
            cls.data, cls.report = build.build(area.load(fixture_dir()))

    def test_the_file_passes_check_map(self):
        self.assertEqual(check_map(self.data), [])

    def test_the_map_names_the_data_it_was_built_from(self):
        self.assertEqual(
            [c["text"] for c in self.data["map"]["credits"]],
            [
                "© OpenStreetMap contributors",
                "© Statistisches Bundesamt (Destatis), Zensus 2022",
                "© European Union, CC BY 4.0 (EC JRC, GHS-BUILT-V R2023A)",
                "© DELFI e.V., CC BY 4.0, via gtfs.de",
            ],
        )
        self.assertEqual(
            self.data["map"]["credits"][0]["url"],
            "https://www.openstreetmap.org/copyright",
        )

    def test_a_source_that_was_not_used_is_not_named(self):
        with offline():
            data, _ = build.build(area.load(fixture_dir()), extract=None)

        self.assertNotIn(
            "© DELFI e.V., CC BY 4.0, via gtfs.de",
            [c["text"] for c in data["map"]["credits"]],
        )

    def test_the_report_carries_the_numbers_and_a_version_to_suggest(self):
        lines = [line for _, ls in self.report for line in ls]

        self.assertIn(
            "Pendler 6800 (ein Platzhalter bis zur Kalibrierung), Haltestellen 48, Bahnhöfe 2",
            lines,
        )
        heads_up = dict(self.report)["Achtung"]
        self.assertTrue(heads_up)
        self.assertTrue(all("Vorschlag: eine Version" in h for h in heads_up))

    def test_what_it_holds(self):
        types = [n["types"] for n in self.data["nodes"]]
        self.assertEqual(
            dict(
                nodes=len(self.data["nodes"]),
                edges=len(self.data["edges"]),
                homes=sum("home" in t for t in types),
                workplaces=sum("workplace" in t for t in types),
                stops=sum("bus_stop" in t for t in types),
                stations=sum("station" in t for t in types),
                bus_lines=len(self.data["bus_lines"]),
                train_lines=sorted(line["kind"] for line in self.data["train_lines"]),
            ),
            dict(
                nodes=139,
                edges=377,
                homes=20,
                workplaces=21,
                stops=48,
                stations=2,
                bus_lines=2,
                train_lines=[
                    "train",
                    "train",
                    "tram",
                    "tram",
                    "tram",
                    "tram",
                    "tram",
                    "tram",
                ],
            ),
        )

    def test_every_line_is_its_kinds_seats_and_speed_at_the_timetables_interval(self):
        for line in self.data["bus_lines"]:
            self.assertEqual((line["capacity"], line["speed_kmh"]), (85, 30))
        trams = [line for line in self.data["train_lines"] if line["kind"] == "tram"]
        self.assertEqual(
            {(line["capacity"], line["speed_kmh"]) for line in trams}, {(248, 30)}
        )
        self.assertIn(
            "Takte: timetable 10", [line for head, ls in self.report for line in ls]
        )

    def test_the_file_carries_its_own_background_under_the_nodes(self):
        """The drawing's box is the map's box, at scale 1 from the origin: where the viewers put
        a node (km × 100) it is the same point of the drawing (m)."""
        block = self.data["background_image"]
        svg = base64.b64decode(block["data"]).decode()
        m = self.data["map"]
        self.assertIn(f'viewBox="0 0 {m["x_dim"] * 1000} {m["y_dim"] * 1000}"', svg)
        self.assertEqual(
            (block["scale"], block["offset_x"], block["offset_y"]), (1.0, 0.0, 0.0)
        )
        for layer in ("wohnen", "arbeit", "gruen", "wasser", "strassen", "schiene"):
            self.assertIn(f'id="{layer}"', svg)
        self.assertTrue(
            all(
                0 <= n["x"] <= m["x_dim"] and 0 <= n["y"] <= m["y_dim"]
                for n in self.data["nodes"]
            )
        )

    def test_a_ring_says_so_and_no_other_edge_does(self):
        """The cut ends inside the Rembertikreisel: two ring links, one each way
        round between the two nodes the cut kept."""
        rings = [edge for edge in self.data["edges"] if "junction" in edge]

        self.assertEqual(
            sorted((edge["name"], edge["junction"]) for edge in rings),
            [("Rembertiring", "circular"), ("Rembertiring", "circular")],
        )

    def test_a_one_way_street_walks_back_on_a_path(self):
        pairs = {(e["start_node"], e["end_node"]): e for e in self.data["edges"]}
        for (a, b), e in pairs.items():
            if e.get("walking", True):
                self.assertIn(
                    (b, a), pairs, f"{e['name'] or e['type']} {a} → {b} has no way back"
                )

    def test_the_same_file_under_any_hash_seed(self):
        probe = (
            "import hashlib, json\n"
            "from mapbuild import area, build\n"
            "from mapbuild.tests import fixture_dir\n"
            "d, _ = build.build(area.load(fixture_dir()))\n"
            "print(hashlib.sha256(json.dumps(d, ensure_ascii=False, indent=1).encode()).hexdigest())\n"
        )
        digests = set()
        for seed in ("1", "2"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            proc = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=BACKEND,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
            digests.add(proc.stdout.strip())
        digests.add(
            hashlib.sha256(
                json.dumps(self.data, ensure_ascii=False, indent=1).encode()
            ).hexdigest()
        )
        self.assertEqual(len(digests), 1)


class CommandTests(SimpleTestCase):
    def test_build_map_writes_the_file_and_the_report(self):
        with tempfile.TemporaryDirectory() as root, offline():
            a = area.box(BOX, name="Bremen Mitte", root=root)
            fixture_dir(into=a.cache)
            out = Path(root) / "bremen-mitte.json"
            stdout = StringIO()
            with mock.patch.dict(os.environ, {"CO2MMUTE_MAP_CACHE": root}):
                call_command(
                    "build_map",
                    "--bbox",
                    ",".join(map(str, BOX)),
                    "--name",
                    "Bremen Mitte",
                    "--out",
                    str(out),
                    stdout=stdout,
                )
            data = json.loads(out.read_text())
        self.assertEqual(data["map"]["name"], "Bremen Mitte")
        self.assertEqual(check_map(data), [])
        self.assertIn("Geschrieben:", stdout.getvalue())
        self.assertIn("Bus und Bahn", stdout.getvalue())

    def test_a_place_and_a_box_at_once_is_refused(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("build_map", "Bremen", "--bbox", "1,2,3,4", stdout=StringIO())
