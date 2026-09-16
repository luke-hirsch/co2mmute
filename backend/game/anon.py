"""Anonymisation at game end.

Roadmap.md 1.3, decided 2026-08-13. Players are school students, some of them
minors, and the screen name is the only identifying thing this project collects.
So the name goes and everything else stays: moves, routes, per-agent results all
keep their foreign keys and stay linkable for the thesis.

Deliberately not deletion. Deleting the game would take the research data with
it, and the data is the point.
"""

import logging

from django.db import transaction
from django.utils import timezone

from game.models import GameSession, Player

logger = logging.getLogger(__name__)

ANONYMOUS_NAME_TEMPLATE = "Spieler {n}"
HOST_NAME = "Host"


def anonymise_game(game: GameSession) -> int:
    """Strip identifying data from a finished game. Returns rows renamed.

    The host's own row becomes "Host" and takes no number; everyone else,
    including players at the host machine, becomes "Spieler N" in join order.

    Idempotent: run it twice and the second run renames nothing new, because the
    numbering is by join order rather than by a counter, and the QR file is
    already gone.
    """
    renamed = 0

    with transaction.atomic():
        players = (
            Player.objects.select_for_update()
            .filter(game=game)
            .order_by("joined_at", "pk")
        )
        host_row_ids = set(
            Player.objects.filter(game=game).host_rows().values_list("pk", flat=True)  # type: ignore
        )

        number = 0
        for player in players:
            if player.pk in host_row_ids:
                new_name = HOST_NAME
            else:
                number += 1
                new_name = ANONYMOUS_NAME_TEMPLATE.format(n=number)
            if player.name == new_name:
                continue
            # update() rather than save() — the post_save receiver on Player
            # broadcasts a chat message and re-runs agent assignment, neither of
            # which belongs in a cleanup job.
            Player.objects.filter(pk=player.pk).update(name=new_name)
            renamed += 1

        if game.game_qr_code:
            # The QR encodes the join URL, which carries the game id. Harmless on
            # its own, but the game is over and nothing needs it.
            game.game_qr_code.delete(save=False)
            GameSession.objects.filter(pk=game.pk).update(game_qr_code="")

        GameSession.objects.filter(pk=game.pk).update(anonymised_at=timezone.now())

    # game_id, never a name.
    logger.info(f"Anonymised game {game.game_id}: {renamed} players renamed")
    return renamed


def games_due_for_anonymisation(grace_hours: int):
    """Ended long enough ago, not done yet."""
    cutoff = timezone.now() - timezone.timedelta(hours=grace_hours)
    return GameSession.objects.filter(
        ended_at__isnull=False,
        ended_at__lt=cutoff,
        anonymised_at__isnull=True,
    )
