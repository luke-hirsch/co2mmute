"""The landing page, and the two background documents behind /hintergrund/.

/hintergrund/ itself is not tested here on purpose: it is edited often, and an
edit to its copy must not be able to stop a deploy (Lukas, 2026-10-01). So the
page and `docs/de-hintergrund.md` are no longer held together by a test; what
stays is the English document mirroring the German one. Every template, this
one included, is still compiled and read for retired words and third-party
loads by `test_sanity`.

The doc tests read `docs/` from the repository root, the way `maps/tests/
test_example_map.py` reads `map_examples/`: CI checks out the whole repo.
"""

import re
from html import unescape
from pathlib import Path

from django.test import TestCase

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
        """The public-transport line's detour is the way to /hintergrund/."""
        self.assertEqual(self.response.status_code, 200)
        detour = re.search(r'<section class="metro-detour">(.*?)</section>', self.html, flags=re.S)
        self.assertIsNotNone(detour)
        self.assertIn('href="/hintergrund/"', detour.group(1))

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
