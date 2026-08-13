import ast
import pathlib

from django.test import SimpleTestCase

# co2mmute/tests/test_sanity.py -> co2mmute/tests -> co2mmute -> backend
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Third-party / generated trees we do not own.
SKIP_PARTS = {"node_modules", "staticfiles", "__pycache__", ".venv"}


class SourceTreeParsesTests(SimpleTestCase):
    """Every Python file we ship must at least parse.

    Catches abandoned stubs that are never imported and therefore never fail
    loudly (game/engine.py was one).
    """

    def test_all_python_sources_parse(self):
        failures = []

        for path in sorted(BACKEND_ROOT.rglob("*.py")):
            if SKIP_PARTS.intersection(path.parts):
                continue
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                rel = path.relative_to(BACKEND_ROOT)
                failures.append(f"{rel}: line {exc.lineno}: {exc.msg}")

        self.assertEqual(
            failures,
            [],
            msg="Python files that do not parse:\n  " + "\n  ".join(failures),
        )
