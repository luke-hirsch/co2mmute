"""The Django pages the map area used to have, as doorways into the SPA.

All three were templates once — the list (S18), a map's page (S18) and the
upload form (S19). The URLs stay because `base.html` names them in its menus
and a bookmark might; nothing is looked up, and the SPA does the staff gating.
The import itself is `maps/importer.py`, behind `api/maps/import/`.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import RedirectView


class MapUploadView(LoginRequiredMixin, RedirectView):
    """`/map/upload/` — the upload screen, which `/app/maps/upload` is now. S19.

    `RedirectView` answers every method with the redirect, so a POST here no
    longer imports anything: the endpoint is the one door, and a second one
    would be a second place to forget a rule.
    """

    pattern_name = None
    url = "/app/maps/upload"
    permanent = False


class MapListView(LoginRequiredMixin, RedirectView):
    """`/map/list/` — the staff map list, which `/app/maps` is now. S18.

    The template was English and printed a `description` `GameMap` has no
    column for. The URL stays because both menus in `base.html` name
    `map-list`. Staff gating is the SPA's, as it is for the detail page.
    """

    pattern_name = None
    url = "/app/maps/"
    permanent = False


class MapDetailView(LoginRequiredMixin, RedirectView):
    """`/map/<pk>/` — a map's page, which `/app/maps/<pk>/` is now. S18.

    Nothing linked here any more: the old list already pointed at the SPA. Its
    version browser is the editor's version panel. Nothing is looked up, so an
    unknown pk is the SPA's to refuse.
    """

    pattern_name = None
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return f"/app/maps/{kwargs['pk']}/"
