"""The landing page, the docs on the site, and the background documents.

The docs pages under /docs/ (F13) are copies of `docs/de-*.md` and are not held
to them by a test on purpose: they are edited often, and an edit to their copy
must not be able to stop a deploy (Lukas, 2026-10-01). What is tested here is
the frame — that each page is where the menu says, that the English ones are
gone — and that every page is German. What stays of the documents is the
English background mirroring the German one: the English docs live on in
`docs/`, for GitHub, and nowhere on the site. Every template is still compiled
and read for retired words and third-party loads by `test_sanity`.

The doc tests read `docs/` from the repository root, the way `maps/tests/
test_example_map.py` reads `map_examples/`: CI checks out the whole repo.
"""

import re
from html import unescape
from pathlib import Path

from django.test import TestCase
from django.urls import URLResolver, get_resolver, resolve
from django.urls.resolvers import RoutePattern

from game.tests._helpers import english_in, visible_text

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_DE = REPO_ROOT / "docs" / "de-hintergrund.md"
DOC_EN = REPO_ROOT / "docs" / "en-background.md"

FIGURE_LINK = re.compile(r"!\[[^\]]*\]\(\.\./backend/template/hintergrund/([\w-]+)\.svg\)")


def normalise(text):
    """Markup gone, entities resolved, the subscript two written as a two.

    The doc writes CO₂ and the page CO<sub>2</sub>; a non-breaking space keeps
    a number on the page with its unit and is a space in the doc.
    """
    # a cell, a line or a paragraph ends in a space; an inline tag (<sub>,
    # <strong>) does not, or CO<sub>2</sub> would read "CO 2"
    text = re.sub(r"</(?:td|th|tr|li|p|pre|div|figcaption|h[1-6])>|<br\s*/?>", " ", text)
    text = unescape(re.sub(r"<[^>]+>", "", text))
    text = text.replace("₂", "2").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def doc_headings(markdown):
    return [
        (len(match.group(1)), normalise(match.group(2)))
        for match in re.finditer(r"^(#{2,3}) (.+)$", markdown, flags=re.M)
    ]


def doc_table(markdown, first_header):
    """The rows of the table whose first column is headed `first_header`."""
    lines = markdown.splitlines()
    start = next(
        i for i, line in enumerate(lines) if re.match(rf"^\|\s*{first_header}\s*\|", line)
    )
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


class TheEnglishBackgroundMirrorsTheGermanTests(TestCase):
    """`docs/en-background.md` is the German document in English, chapter for chapter."""

    def test_same_chapters_and_sections_in_the_same_order(self):
        german = [level for level, _ in doc_headings(DOC_DE.read_text(encoding="utf-8"))]
        english = [level for level, _ in doc_headings(DOC_EN.read_text(encoding="utf-8"))]
        self.assertEqual(english, german)

    def test_same_figures(self):
        self.assertEqual(
            FIGURE_LINK.findall(DOC_EN.read_text(encoding="utf-8")),
            FIGURE_LINK.findall(DOC_DE.read_text(encoding="utf-8")),
        )

    def test_same_numbers_in_the_tables(self):
        """The tables are where a re-measurement lands; both copies get it."""
        german = DOC_DE.read_text(encoding="utf-8")
        english = DOC_EN.read_text(encoding="utf-8")

        # 13.059 and 22,5 in German, 13 059 and 22.5 in English
        def de_value(cell):
            return re.findall(r"\d+(?:\.\d+)?", cell.replace(".", "").replace(",", "."))

        def en_value(cell):
            return re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?<=\d) (?=\d)", "", cell))

        for de_header, en_header in (("Autoanteil", "car share"), ("Plätze", "seats")):
            with self.subTest(table=de_header):
                self.assertEqual(
                    [[en_value(c) for c in row] for row in doc_table(english, en_header)],
                    [[de_value(c) for c in row] for row in doc_table(german, de_header)],
                )


class LandingPageTests(TestCase):
    def setUp(self):
        self.response = self.client.get("/")
        self.html = self.response.content.decode("utf-8")

    def test_the_detour_leads_to_the_background_page(self):
        """The public-transport line's detour is the way to the background,
        wherever it lives — /docs/hintergrund/ since F13."""
        self.assertEqual(self.response.status_code, 200)
        detour = re.search(r'<section class="metro-detour">(.*?)</section>', self.html, flags=re.S)
        self.assertIsNotNone(detour)
        self.assertIn('href="/docs/hintergrund/"', detour.group(1))

    def test_the_thesis_is_credited_to_the_university_it_was_written_at(self):
        """`master_thesis.pdf` was submitted at the Freie Universität Berlin.

        The landing page and the README had it at the TU Berlin, where the game
        is developed now — the thesis's own title page says otherwise.
        """
        self.assertEqual(self.response.status_code, 200)
        self.assertIn("Freien Universität Berlin", normalise(self.html))
        self.assertNotIn("Masterarbeit an der TU Berlin", normalise(self.html))

    def test_the_page_is_german(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertEqual(english_in(visible_text(self.html)), [])


# path -> url name
DOCS = {
    "/docs/schnellstart/": "docs-schnellstart",
    "/docs/hintergrund/": "docs-hintergrund",
    "/docs/ablaufdiagramme/": "docs-ablaufdiagramme",
}


class DocsPagesTests(TestCase):
    """F13: the docs where the research group can read them — three pages
    under one item in the header, in German like the rest of the site."""

    def test_every_page_is_where_the_menu_says_and_answers(self):
        for path, name in DOCS.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).url_name, name)
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_every_page_is_german_and_offers_no_other_language(self):
        for path in DOCS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn('<html class="" lang="de">', html)
                self.assertNotIn("hreflang", html)
                self.assertNotIn("/docs/en/", html)

    def test_the_english_pages_are_gone(self):
        """A German site with three English pages in its menu read as a
        mistake (Lukas, 2026-10-03). Taken off, not redirected: the English
        text stays in `docs/en-*.md`, where GitHub shows it."""
        for path in ("/docs/en/quick-start/", "/docs/en/background/", "/docs/en/flowcharts/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_the_background_moved_and_its_old_address_is_gone(self):
        """Moved, not redirected — like the old join (S22)."""
        self.assertEqual(self.client.get("/hintergrund/").status_code, 404)


def _plain_paths(patterns, prefix=""):
    """Every route in the URLconf that takes no argument, as a path."""
    for pattern in patterns:
        if not isinstance(pattern.pattern, RoutePattern):
            continue
        route = prefix + str(pattern.pattern)
        if "<" in route:
            continue
        if isinstance(pattern, URLResolver):
            yield from _plain_paths(pattern.url_patterns, route)
        else:
            yield "/" + route


class EveryGermanPageIsGermanTests(TestCase):
    """The English detector over every Django page a visitor can open, not a
    list of the pages that once had English on them — `/map/upload/` was
    English for months behind a green suite because nobody had listed it.

    The admin is Django's own, in English by design, and `api/` answers JSON.
    Nothing else is exempt, so a page added tomorrow is read too.
    """

    NOT_PAGES = ("/admin/", "/api/")

    def test_no_german_page_has_english_on_it(self):
        read, failures = [], []

        for path in sorted(set(_plain_paths(get_resolver().url_patterns))):
            if path.startswith(self.NOT_PAGES):
                continue
            response = self.client.get(path)
            if response.status_code != 200 or "text/html" not in response.get("Content-Type", ""):
                continue
            read.append(path)
            found = english_in(visible_text(response.content.decode()))
            if found:
                failures.append(f"{path}: {found}")

        # A crawler that reads nothing passes; make sure it read the pages.
        for path in ("/", "/docs/schnellstart/", "/docs/hintergrund/", "/docs/ablaufdiagramme/"):
            self.assertIn(path, read)
        self.assertEqual(failures, [], "\n".join(failures))
