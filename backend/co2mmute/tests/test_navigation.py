"""The header and footer, for both halves of the site. S20.

`co2mmute/navigation.py` builds one list; `base.html` renders it and
`api/navigation/` serves it to the SPA. Before, each half kept its own list and
they disagreed — the SPA had no map menu and no way to sign out, and
`base.html` called the same two links "Hochladen"/"Karten" on a desktop and
"Upload"/"Liste" in the phone menu. These tests pin the list, and then that
both doors hand out exactly that list.
"""

import re

from content.models import NavigationItem, Page
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from game.tests._helpers import create_host

from co2mmute import navigation

NAVIGATION_URL = "/api/navigation/"


def _labels(items):
    return [item["label"] for item in items]


def _hrefs(items):
    out = []
    for item in items:
        if item.get("href"):
            out.append(item["href"])
        out.extend(_hrefs(item.get("children", [])))
    return out


def _build(user=None):
    request = RequestFactory().get("/")
    request.user = user or AnonymousUser()
    return navigation.build(request)


class NavigationListTests(TestCase):
    def test_an_anonymous_visitor_gets_the_game_menu_and_a_way_to_sign_in(self):
        nav = _build()

        self.assertEqual(_labels(nav["header"]), ["Spielen", "Hintergrund"])
        spielen = nav["header"][0]
        self.assertEqual(
            [(child["label"], child["href"]) for child in spielen["children"]],
            [("Erstellen", "/app/game/create"), ("Beitreten", "/join/")],
        )
        self.assertIsNone(nav["account"])
        self.assertEqual(nav["session"]["label"], "Anmelden")
        self.assertEqual(nav["session"]["href"], "/accounts/login/")

    def test_a_player_sees_neither_the_map_menu_nor_a_sign_out(self):
        # A player is anonymous to Django — two signed cookies, no session —
        # so this is the anonymous list, and it must not offer either.
        nav = _build()

        self.assertNotIn("Karten", _labels(nav["header"]))
        self.assertNotIn("/app/maps", _hrefs(nav["header"]))
        self.assertNotEqual(nav["session"]["label"], "Abmelden")

    def test_a_host_gets_their_profile_and_a_sign_out_but_no_map_menu(self):
        nav = _build(create_host(username="lehrkraft"))

        self.assertEqual(_labels(nav["header"]), ["Spielen", "Hintergrund"])
        self.assertEqual(nav["account"]["label"], "lehrkraft")
        # Straight into the SPA: `/accounts/profile/` only redirects there.
        self.assertEqual(nav["account"]["href"], "/app/host")
        self.assertEqual(nav["session"]["label"], "Abmelden")
        self.assertEqual(nav["session"]["href"], "/accounts/logout/")

    def test_staff_get_the_map_menu(self):
        nav = _build(create_host(username="staff", is_staff=True))

        self.assertEqual(_labels(nav["header"]), ["Spielen", "Karten", "Hintergrund"])
        karten = nav["header"][1]
        self.assertEqual(
            [(child["label"], child["href"]) for child in karten["children"]],
            [("Alle Karten", "/app/maps"), ("Hochladen", "/app/maps/upload")],
        )

    def test_the_footer_is_the_legal_pages_then_the_repository(self):
        nav = _build()

        self.assertEqual(
            [(item["label"], item["href"]) for item in nav["footer"]],
            [
                ("Impressum", "/legal/impressum/"),
                ("Datenschutz", "/legal/dsgvo/"),
                ("Cookies", "/legal/cookies/"),
                ("Quellcode", navigation.REPOSITORY_URL),
            ],
        )

    def test_every_item_has_an_id_that_is_unique_in_its_list(self):
        # The ids name the popovers in both halves (`nav-<id>`) and key the
        # React lists; a repeat would open the wrong menu.
        nav = _build(create_host(username="staff", is_staff=True))

        def ids(items):
            for item in items:
                yield item["id"]
                yield from ids(item.get("children", []))

        for key in ("header", "footer"):
            found = list(ids(nav[key]))
            self.assertEqual(len(found), len(set(found)), key)


class CmsItemsTests(TestCase):
    """The CMS's own entries join the fixed ones, on both halves."""

    def setUp(self):
        self.page = Page.objects.create(key="projekt", title="Projekt")

    def test_a_header_entry_follows_the_fixed_items(self):
        NavigationItem.objects.create(location="header", label="Projekt", page=self.page)

        nav = _build()

        self.assertEqual(_labels(nav["header"]), ["Spielen", "Hintergrund", "Projekt"])
        self.assertEqual(nav["header"][-1]["href"], "/content/projekt/")

    def test_a_container_becomes_a_menu_of_its_children_in_order(self):
        other = Page.objects.create(key="team", title="Team")
        menu = NavigationItem.objects.create(location="header", label="Über uns")
        NavigationItem.objects.create(
            location="header", label="Team", page=other, parent=menu, order=2
        )
        NavigationItem.objects.create(
            location="header", label="Projekt", page=self.page, parent=menu, order=1
        )

        nav = _build()

        entry = nav["header"][-1]
        self.assertEqual(entry["label"], "Über uns")
        self.assertNotIn("href", entry)
        self.assertEqual(_labels(entry["children"]), ["Projekt", "Team"])

    def test_a_footer_entry_sits_between_the_legal_pages_and_the_repository(self):
        NavigationItem.objects.create(location="footer", label="Projekt", page=self.page)

        nav = _build()

        self.assertEqual(
            _labels(nav["footer"]),
            ["Impressum", "Datenschutz", "Cookies", "Projekt", "Quellcode"],
        )

    def test_an_entry_without_a_page_has_nowhere_to_go(self):
        NavigationItem.objects.create(location="footer", label="Bald mehr")

        nav = _build()

        self.assertIsNone(nav["footer"][3]["href"])


class NavigationEndpointTests(TestCase):
    """`api/navigation/` is the same list, for the SPA."""

    def test_anyone_may_ask_and_gets_the_anonymous_list(self):
        response = self.client.get(NAVIGATION_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), _build())

    def test_staff_get_the_map_menu_from_the_endpoint_too(self):
        staff = create_host(username="staff", is_staff=True)
        self.client.force_login(staff)

        body = self.client.get(NAVIGATION_URL).json()

        self.assertEqual(body, _build(staff))
        self.assertIn("Karten", _labels(body["header"]))


class BaseTemplateTests(TestCase):
    """`base.html` renders the list, and nothing else.

    `/hintergrund/` stands in for every Django page: it extends `base.html` and
    needs nobody signed in.
    """

    PAGE = "/hintergrund/"

    def _page(self):
        response = self.client.get(self.PAGE)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_the_desktop_bar_and_the_phone_menu_offer_the_same_links(self):
        # The bug this replaces: the same two links, labelled differently in
        # the two menus of one template. Each link must appear in both.
        staff = create_host(username="staff", is_staff=True)
        self.client.force_login(staff)
        header = self._page().split("</header>")[0]

        for href in _hrefs(_build(staff)["header"]):
            self.assertEqual(
                header.count(f'href="{href}"'), 2, f"{href} is not in both menus"
            )
        self.assertNotIn(">Upload<", header)
        self.assertNotIn(">Liste<", header)

    def test_a_visitor_is_offered_no_map_menu(self):
        html = self._page()

        self.assertNotIn('href="/app/maps"', html)
        self.assertNotIn("Abmelden", html)
        self.assertIn('href="/accounts/login/"', html)

    def test_a_host_can_sign_out_and_reach_their_page(self):
        self.client.force_login(create_host(username="lehrkraft"))
        html = self._page()

        self.assertIn('href="/accounts/logout/"', html)
        self.assertIn('href="/app/host"', html)
        self.assertNotIn('href="/app/maps"', html)

    def test_the_footer_links_the_legal_pages_and_the_repository(self):
        footer = self._page().split("<footer")[1]

        for href in (
            "/legal/impressum/",
            "/legal/dsgvo/",
            "/legal/cookies/",
            navigation.REPOSITORY_URL,
        ):
            self.assertIn(f'href="{href}"', footer)

    def test_the_lockup_is_the_shared_mark_and_the_name_as_text(self):
        html = self._page()

        # Header and phone menu, both from the one drawing.
        uses = re.findall(r'<use href="([^"]+)"', html)
        self.assertEqual(uses, ["/static/img/mark.svg#mark"] * 2)
        self.assertNotIn("logo.svg", html)
        # The rest of the name is text in the page's font, not paths.
        self.assertEqual(html.count("O<sub>2</sub>mmute</span>"), 2)
