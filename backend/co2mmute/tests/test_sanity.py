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


class NoShadowedMethodsTests(SimpleTestCase):
    """A class must not define the same method twice.

    Python keeps the last one and says nothing. `EdgeSerializer` carried two
    `validate` methods for four days: the first held "a bike lane implies bike
    access", the second the node and map-version rules, and only the second ever
    ran — so the bike rule was silently off on the one path the map editor
    writes through. `Edge.clean()` carries the same rule and is tested, but DRF
    never calls `full_clean()`, so every test of it was passing against a code
    path the editor does not use.

    Nothing catches this: the file parses, the class imports, the suite is
    green, and the only symptom is a rule that quietly does not apply. Linting
    would find it too, but eslint does not read Python and this repo runs no
    Python linter in CI.
    """

    def test_no_class_defines_a_method_twice(self):
        failures = []

        for path in sorted(BACKEND_ROOT.rglob("*.py")):
            if SKIP_PARTS.intersection(path.parts):
                continue
            # Migrations are generated and legitimately repetitive.
            if "migrations" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:
                continue  # test_all_python_sources_parse owns that failure

            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                seen = {}
                for body in node.body:
                    if not isinstance(body, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    # A property and its setter share a name on purpose.
                    decorators = {
                        d.attr if isinstance(d, ast.Attribute) else getattr(d, "id", "")
                        for d in body.decorator_list
                    }
                    if {"setter", "deleter", "overload"} & decorators:
                        continue
                    if body.name in seen:
                        rel = path.relative_to(BACKEND_ROOT)
                        failures.append(
                            f"{rel}: {node.name}.{body.name} defined twice "
                            f"(lines {seen[body.name]} and {body.lineno}) — "
                            f"the first one never runs"
                        )
                    seen[body.name] = body.lineno

        self.assertEqual(
            failures,
            [],
            msg="Methods shadowed by a later definition:\n  " + "\n  ".join(failures),
        )
