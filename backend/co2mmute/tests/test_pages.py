"""The landing page and /hintergrund/ — the two public pages that are not a form.

S23 put the whole of `docs/de-hintergrund.md` on /hintergrund/. The page cannot
read the file — the backend image copies `backend/`, never `docs/` — so the two
are two copies of one text, and two copies of one thing is the class of bug
this project has had most. These tests are what keeps them one text: the same
chapters in the same order, the same numbers both ways, the same figures, and
the figures drawing the tables' numbers rather than numbers of their own.

They read `docs/` from the repository root, the way `maps/tests/
test_example_map.py` reads `map_examples/`: CI checks out the whole repo.
"""

import re
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

from django.test import TestCase

from co2mmute.navigation import REPOSITORY_URL
from game.tests._helpers import english_in, visible_text

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_DE = REPO_ROOT / "docs" / "de-hintergrund.md"
DOC_EN = REPO_ROOT / "docs" / "en-background.md"
FIGURES = REPO_ROOT / "backend" / "template" / "hintergrund"

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
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


def doc_numbers(markdown):
    """Every number the document states, link targets and figure paths aside."""
    prose = re.sub(r"\]\([^)]*\)", "]", markdown)
    return set(NUMBER.findall(normalise(prose)))


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


class HintergrundIsTheWholeDocumentTests(TestCase):
    """/hintergrund/ carries docs/de-hintergrund.md, and nothing drifts apart."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc = DOC_DE.read_text(encoding="utf-8")

    def setUp(self):
        self.response = self.client.get("/hintergrund/")
        self.html = self.response.content.decode("utf-8")
        match = re.search(r"<article\b[^>]*>(.*)</article>", self.html, flags=re.S)
        self.article = match.group(1) if match else ""

    def test_the_page_answers(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertTrue(self.article, "the page has no <article> to hold the document")

    def test_every_chapter_and_section_of_the_document_is_on_the_page_in_order(self):
        """A chapter is a station on the page's line, a section a stop."""
        self.assertEqual(self.response.status_code, 200)
        on_page = [
            (int(level), normalise(text))
            for level, text in re.findall(r"<h([23])\b[^>]*>(.*?)</h\1>", self.article, flags=re.S)
        ]
        self.assertEqual(on_page, doc_headings(self.doc))

    def test_every_number_in_the_document_is_on_the_page(self):
        """The drift this exists for: a re-measurement written into one copy.

        Read against the whole page, figures included, because the lead
        paragraph carries the doc's introduction and the figures its curve.
        """
        self.assertEqual(self.response.status_code, 200)
        on_page = set(NUMBER.findall(normalise(self.html)))
        self.assertEqual(sorted(doc_numbers(self.doc) - on_page), [])

    def test_every_number_in_the_page_text_is_in_the_document(self):
        """The other direction: an edit made to the page alone.

        The figures are left out — an axis tick is not a claim the document
        makes — and are held to the tables by the test below instead.
        """
        self.assertEqual(self.response.status_code, 200)
        prose = re.sub(r"<figure\b.*?</figure>", " ", self.article, flags=re.S)
        on_page = set(NUMBER.findall(normalise(prose)))
        self.assertEqual(sorted(on_page - doc_numbers(self.doc)), [])

    def test_the_page_shows_the_figures_the_document_shows(self):
        self.assertEqual(self.response.status_code, 200)
        in_doc = FIGURE_LINK.findall(self.doc)
        on_page = re.findall(r'aria-labelledby="fig-([\w-]+)-title', self.article)
        self.assertEqual(on_page, in_doc)
        for name in in_doc:
            with self.subTest(figure=name):
                self.assertTrue((FIGURES / f"{name}.svg").is_file())

    def test_the_figures_draw_the_numbers_the_tables_state(self):
        """A figure is a drawing of a table; it must not keep numbers of its own.

        The page's number check cannot see this: after a re-measurement the
        page's table would carry the new numbers and a stale figure would still
        pass, because the doc→page direction only asks that each number appear
        somewhere.
        """
        round_cost = (FIGURES / "runde.svg").read_text(encoding="utf-8")
        for row in doc_table(self.doc, "Autoanteil"):
            with self.subTest(share=row[0]):
                self.assertIn(f">{row[0]}<", round_cost.replace("\xa0", " "))
                self.assertIn(f">{row[1]}<", round_cost)

        scale = (FIGURES / "massstab.svg").read_text(encoding="utf-8")
        for seats, groups, people, *_ in doc_table(self.doc, "Plätze"):
            with self.subTest(seats=seats):
                self.assertIn(f">{seats} Plätze · {groups} Gruppen zu je {people}<", scale)

        curve = (FIGURES / "co2-kurve.svg").read_text(encoding="utf-8")
        speeds = doc_table(self.doc, "km/h")
        grams_at_50 = speeds[0][5]
        self.assertIn(f"Anker: {grams_at_50} g", curve)

    def test_every_figure_stands_on_its_own(self):
        """The docs show these files directly, so each must be a whole SVG.

        And on the page all four are inline in one document, so their ids
        must not collide — `aria-labelledby` would name the wrong title.
        """
        for path in sorted(FIGURES.glob("*.svg")):
            with self.subTest(figure=path.name):
                root = ET.fromstring(path.read_text(encoding="utf-8"))
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(self.response.status_code, 200)
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        self.assertEqual(len(ids), len(set(ids)), f"duplicate ids: {sorted(ids)}")

    def test_the_sources_are_linked_into_the_repository(self):
        """The thesis and the calibration code, through the footer's constant."""
        self.assertEqual(self.response.status_code, 200)
        self.assertIn(f'href="{REPOSITORY_URL}/blob/main/master_thesis.pdf"', self.html)
        self.assertNotIn("{{", self.html)

    def test_the_page_is_german(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertEqual(english_in(visible_text(self.html)), [])


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
        """The public-transport line's detour is the way to /hintergrund/."""
        self.assertEqual(self.response.status_code, 200)
        detour = re.search(r'<section class="metro-detour">(.*?)</section>', self.html, flags=re.S)
        self.assertIsNotNone(detour)
        self.assertIn('href="/hintergrund/"', detour.group(1))

    def test_the_thesis_is_credited_to_the_university_it_was_written_at(self):
        """`master_thesis.pdf` was submitted at the Freie Universität Berlin.

        Both pages and the README had it at the TU Berlin, where the game is
        developed now — the thesis's own title page says otherwise.
        """
        self.assertEqual(self.response.status_code, 200)
        background = self.client.get("/hintergrund/").content.decode("utf-8")
        for name, html in (("landing", self.html), ("hintergrund", background)):
            with self.subTest(page=name):
                self.assertIn("Freien Universität Berlin", normalise(html))
                self.assertNotIn("Masterarbeit an der TU Berlin", normalise(html))

    def test_the_page_is_german(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertEqual(english_in(visible_text(self.html)), [])
