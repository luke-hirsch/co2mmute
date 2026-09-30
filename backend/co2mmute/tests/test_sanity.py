import ast
import pathlib
import re

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


class NoThirdPartyLoadsTests(SimpleTestCase):
    """No page may load anything from another origin.

    A script, stylesheet, image or frame fetched from someone else's server
    hands them the visitor's IP address on every page view — and the visitors
    are school students under a data-minimisation design. `base.html` loaded
    `@tailwindplus/elements` from cdn.jsdelivr.net on every Django page for the
    header's two dropdowns and the mobile menu, and the DSGVO page never
    mentioned it. The design rules refuse a webfont for exactly this reason; a
    script is the same leak.

    Links are fine — an `<a href>` to tu.berlin loads nothing until somebody
    clicks it. What this reads is every element that *fetches* on render.

    `frontend/index.html` is the SPA's only HTML and is read when it is there:
    CI checks out the whole repo, but the backend image copies only `backend/`.
    """

    FETCHING_ELEMENT = re.compile(
        r"<(?:script|img|iframe|source|video|audio|embed)\b[^>]*?\bsrc\s*=\s*[\"']?(?:https?:)?//"
        r"|<link\b[^>]*?\bhref\s*=\s*[\"']?(?:https?:)?//",
        re.IGNORECASE,
    )
    REMOTE_CSS_URL = re.compile(r"(?:@import|url\()\s*[\"']?(?:https?:)?//", re.IGNORECASE)

    def _html_sources(self):
        paths = sorted((BACKEND_ROOT / "template").rglob("*.html"))
        spa_index = BACKEND_ROOT.parent / "frontend" / "index.html"
        if spa_index.exists():
            paths.append(spa_index)
        return paths

    def test_no_page_loads_anything_from_another_origin(self):
        failures = []

        for path in self._html_sources():
            text = path.read_text(encoding="utf-8")
            for match in self.FETCHING_ELEMENT.finditer(text):
                lineno = text.count("\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(BACKEND_ROOT.parent)}:{lineno}")

        # The stylesheet sources, not the built bundle: tailwind.css is output.
        for path in sorted((BACKEND_ROOT / "static" / "css").glob("*.css")):
            if path.name == "tailwind.css":
                continue
            text = path.read_text(encoding="utf-8")
            for match in self.REMOTE_CSS_URL.finditer(text):
                lineno = text.count("\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(BACKEND_ROOT.parent)}:{lineno}")

        self.assertEqual(
            failures,
            [],
            msg="loaded from another origin:\n  " + "\n  ".join(failures),
        )

    def test_no_template_uses_an_element_nothing_defines(self):
        """`<el-popover>`, `<el-dialog>` and friends were defined by that CDN
        script. Without it they are inert unknown tags, so Tailwind UI markup
        pasted in later would render and silently do nothing."""
        failures = []

        for path in sorted((BACKEND_ROOT / "template").rglob("*.html")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"<el-[a-z-]+", line):
                    failures.append(f"{path.relative_to(BACKEND_ROOT)}:{lineno}")

        self.assertEqual(
            failures,
            [],
            msg="tailwindplus elements nothing defines:\n  " + "\n  ".join(failures),
        )


class EveryTemplateCompilesTests(SimpleTestCase):
    """Every Django template parses — all of them, not the ones a test renders.

    S22 found three pages of the password-reset flow answering a 500 on every
    request: a formatter had wrapped `{% if not forloop.last %}` across two
    lines, and a template tag cannot span a line break. "Passwort vergessen?"
    on the login page led straight into it. No test had ever requested those
    pages, so the suite was green over a broken door.

    Compiling is what a request would have done first, so this compiles every
    `.html` under `template/` — a page nobody tests is still covered, which is
    the point: a detector scoped to the pages that prompted it misses the next one.
    """

    def test_every_template_compiles(self):
        from django.template import TemplateSyntaxError
        from django.template.loader import get_template

        root = BACKEND_ROOT / "template"
        failures = []

        for path in sorted(root.rglob("*.html")):
            name = path.relative_to(root).as_posix()
            try:
                get_template(name)
            except TemplateSyntaxError as error:
                failures.append(f"template/{name}: {error}")

        self.assertEqual(
            failures,
            [],
            msg="templates that do not compile:\n  " + "\n  ".join(failures),
        )


class TemplatesStayOnThePaletteTests(SimpleTestCase):
    """The Django half paints from the design system, like the SPA does.

    The palette is two colours and ink (`/app/styleguide` renders it), and
    the SPA has `frontend/tests/design/palette.test.ts` to keep it that way.
    The Django half had nothing: `registration/` and the join pages were
    Tailwind UI boilerplate in indigo, gray, red and green, with emoji for
    icons, and nothing noticed. This reads every template and every form
    that sets a widget class, so a page added tomorrow is covered.

    What it refuses is what the rulebook names: Tailwind's stock palettes
    (none of them is a token here), weights above 600, the heavy drop shadows
    that stand in for a line, and emoji standing in for a word.
    """

    STOCK_PALETTE = re.compile(
        r"\b[a-z-]*(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|"
        r"green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)"
        r"-(?:50|[1-9]00|950)\b"
    )
    TOO_HEAVY = re.compile(r"\bfont-(?:bold|extrabold|black)\b|\bshadow-(?:lg|xl|2xl)\b")
    EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐✅]")

    def _sources(self):
        yield from sorted((BACKEND_ROOT / "template").rglob("*.html"))
        for path in sorted(BACKEND_ROOT.rglob("forms.py")):
            if not SKIP_PARTS.intersection(path.parts):
                yield path

    def test_nothing_paints_outside_the_palette(self):
        failures = []

        for path in self._sources():
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for pattern in (self.STOCK_PALETTE, self.TOO_HEAVY, self.EMOJI):
                    for match in pattern.finditer(line):
                        failures.append(
                            f"{path.relative_to(BACKEND_ROOT)}:{lineno}: {match.group(0)}"
                        )

        self.assertEqual(
            failures,
            [],
            msg="off the palette:\n  " + "\n  ".join(failures),
        )
