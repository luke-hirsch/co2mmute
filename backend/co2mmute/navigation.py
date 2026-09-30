"""
What the header and the footer offer, for one request.

The site has two halves and used to have two headers: `base.html` for the
Django pages and `app-header.tsx` for the SPA, each with its own list. They
disagreed about nearly everything — which items, which labels, who sees the
map menu — and `base.html` disagreed with itself, calling the same two links
"Hochladen"/"Karten" on a desktop and "Upload"/"Liste" in the phone menu.

So there is one list, built here. `context_processor` hands it to every
template and `NavigationView` (`api/navigation/`) hands the same thing to the
SPA, which renders it and decides nothing. Who may see the map menu is
therefore answered once, in Python, for both halves.

An item is `{"id", "label", "href"}` or `{"id", "label", "children"}`. An
`href` under `/app/` is a screen the SPA already has and it follows it without
a reload; anything else is a Django page. A CMS item with neither a page nor
children has `href` None and renders as plain text, as it always did.
"""

from django.urls import reverse

from content.models import NavigationItem

# Where the code lives. The project is handed over to the research group, so
# this is the one line to change if the repository moves.
REPOSITORY_URL = "https://github.com/luke-hirsch/co2mmute"


def _link(id_, label, href):
    return {"id": id_, "label": label, "href": href}


def _cms_items():
    """
    The CMS's header and footer entries, one level of children deep.

    The admin only offers the locations in `NavigationItem.LOCATION_CHOICES`,
    so `header` and `footer` are the two this reads. The `game_menu` and
    `map_menu` blocks `base.html` used to loop over were never among them and
    rendered nothing.
    """
    items = NavigationItem.objects.select_related("page").order_by("order", "pk")
    tops = {}
    by_location = {"header": [], "footer": []}

    for item in items:
        if item.parent_id is None and item.location in by_location:
            entry = {
                "id": f"cms-{item.pk}",
                "label": item.label,
                "href": _page_href(item),
            }
            tops[item.pk] = entry
            by_location[item.location].append(entry)

    for item in items:
        parent = tops.get(item.parent_id) if item.parent_id else None
        if parent is not None:
            parent.setdefault("children", []).append(
                _link(f"cms-{item.pk}", item.label, _page_href(item))
            )

    # A container with children is a menu, not a link; the model refuses a
    # page on it, but a row saved before that rule would still carry one.
    for entry in tops.values():
        if entry.get("children"):
            entry.pop("href", None)

    return by_location


def _page_href(item):
    if item.page is None:
        return None
    return reverse("content:static-page", kwargs={"key": item.page.key})


def build(request):
    user = request.user
    signed_in = bool(user and user.is_authenticated)
    cms = _cms_items()

    header = [
        {
            "id": "spielen",
            "label": "Spielen",
            "children": [
                _link("erstellen", "Erstellen", "/app/game/create"),
                _link("beitreten", "Beitreten", reverse("session-join")),
            ],
        },
    ]
    if signed_in and user.is_staff:
        header.append(
            {
                "id": "karten",
                "label": "Karten",
                "children": [
                    _link("alle-karten", "Alle Karten", "/app/maps"),
                    _link("hochladen", "Hochladen", "/app/maps/upload"),
                ],
            }
        )
    header.append(_link("hintergrund", "Hintergrund", reverse("hintergrund")))
    header.extend(cms["header"])

    # The legal pages are fixed and first: they must be reachable whatever the
    # CMS holds.
    footer = [
        _link("impressum", "Impressum", reverse("impressum")),
        _link("datenschutz", "Datenschutz", reverse("dsgvo")),
        _link("cookies", "Cookies", reverse("cookies")),
        *cms["footer"],
        _link("quellcode", "Quellcode", REPOSITORY_URL),
    ]

    if signed_in:
        account = _link("konto", user.get_username(), "/app/host")
        session = _link("abmelden", "Abmelden", reverse("logout"))
    else:
        account = None
        session = _link("anmelden", "Anmelden", reverse("login"))

    return {"header": header, "footer": footer, "account": account, "session": session}


def context_processor(request):
    return {"navigation": build(request)}
