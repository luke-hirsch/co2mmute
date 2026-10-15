"""`mapbuild/` builds a map without Django, like `sim/`: checked in a subprocess, because by the
time the test runner has started, Django is imported."""

import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parents[2]

PROBE = """
import sys
import mapbuild
import mapbuild.area, mapbuild.build, mapbuild.buses, mapbuild.connect, mapbuild.download
import mapbuild.geo, mapbuild.lines, mapbuild.mapfile, mapbuild.people, mapbuild.rail
import mapbuild.roads, mapbuild.streets, mapbuild.timetable, mapbuild.transit
leaked = sorted(m for m in sys.modules if m == "django" or m.startswith("django."))
if leaked:
    print("DJANGO:" + ",".join(leaked[:5]))
    sys.exit(1)
print("CLEAN")
"""


class MapbuildIsDjangoFreeTests(SimpleTestCase):
    def test_importing_mapbuild_does_not_import_django(self):
        proc = subprocess.run(
            [sys.executable, "-c", PROBE], cwd=BACKEND, capture_output=True, text=True
        )

        self.assertEqual(
            proc.returncode, 0, f"stdout={proc.stdout!r} stderr={proc.stderr[-800:]!r}"
        )
        self.assertIn("CLEAN", proc.stdout)
