"""The Django doors into the SPA.

Every page that used to live here is a React screen now, and what is left are
the old URLs, kept as redirects because something still links them. The join
funnel (`/join/`, `/join/<id>/`, `game/<id>/player/create/`) was the last page
and went in S22 — deleted rather than redirected, see
`game/tests/test_join.py:OneJoinFunnelTests`.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import RedirectView


class GameSessionCreateView(LoginRequiredMixin, RedirectView):
    """`/game/create/` is now a doorway into the SPA. S13.

    The form itself is `frontend/src/routes/game/create.tsx`, because the two
    calibrated numbers it offers have to follow the class size as the host
    types it — `people_per_agent` divides the map's commuters between the
    Gruppen, so changing the seats changes it. Server-rendered, that
    derivation happened once per GET and a host who changed the Platzzahl had
    to pull both numbers across by hand (`docs/testfaelle.md` H-13).

    The URL stays because everything points at it: the landing page twice, the
    footer, the profile page, the end-of-game screen and six e2e specs. A
    redirect keeps every one of them working and leaves exactly one screen.

    `LoginRequiredMixin` stays too, and it is the reason this is a Django view
    rather than an nginx rule: an anonymous visitor belongs on the login page,
    not on a React screen that would bounce them there a second later.
    """

    pattern_name = None
    url = "/app/game/create"
    permanent = False


class ShareSessionView(LoginRequiredMixin, RedirectView):
    """`/game/<id>/share/` — the join QR, which the host lobby already shows.

    Not a port: a deletion. `HostLobbyScreen` puts the game id in a departure
    board with the QR under it, sized for a projector, and has done since F4 —
    so this page was a second screen answering one question, which is the thing
    this project keeps having to undo. It redirects into the lobby.

    A started game has no QR worth showing anyway: joining answers `started`.

    The URL stays because the host's game list links to it and so might a
    bookmark. Nothing is looked up here on purpose — whether a game id exists is
    not a stranger's business, and the game screen refuses what it must.
    """

    pattern_name = None
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return f"/app/game/{kwargs['game_id']}/"


class GameDeleteView(LoginRequiredMixin, RedirectView):
    """`/game/<id>/delete/` — deleting a game, which `/app/host` now does.

    The confirm page it replaces existed because an `<a href>` cannot send
    DELETE and the REST endpoint was the only thing that could delete a game.
    The React list can send DELETE, asks in a dialog that names what goes with
    it, and does not leave the page.

    **The rule the page carried moved with it**: a running game is refused, so
    `end_reason` gets written while it is still known. That refusal now lives in
    `GameSessionDetailView.destroy` (409 `running`) — on the endpoint, where
    both doors have to pass through it, rather than on one of them.
    """

    pattern_name = None
    url = "/app/host"
    permanent = False
