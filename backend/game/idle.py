"""Games nobody plays any more end by themselves. Roadmap.md 1.6.

A paused game can wait a long time for a class that never comes back, and a
lobby nobody starts waits forever. Each game ends after its own idle_end_days
without activity; the host sets that in the create form (default 30). Once
ended, the normal anonymisation (game/anon.py) takes the names after its grace
period.
"""

import logging
from datetime import datetime, timedelta

from django.db.models import Max
from django.utils import timezone

from game.models import GameRound, GameSession, Player, PlayerMove

logger = logging.getLogger(__name__)


def last_activity(game: GameSession) -> datetime:
    """The latest thing that happened in this game.

    updated_at covers creation, settings, start, pause and resume. Rounds,
    moves and joins are rows of their own.
    """
    candidates = [
        game.updated_at,
        GameRound.objects.filter(game=game).aggregate(at=Max("updated_at"))["at"],
        PlayerMove.objects.filter(player__game=game).aggregate(at=Max("moved_at"))[
            "at"
        ],
        Player.objects.filter(game=game).aggregate(at=Max("joined_at"))["at"],
    ]
    return max(at for at in candidates if at is not None)


def games_due_for_idle_end(now: datetime | None = None) -> list[GameSession]:
    """Games not ended yet whose last activity is older than their own limit.

    A loop, not one query: there are only ever a few unended games, and each
    one has its own limit.
    """
    now = now or timezone.now()
    return [
        game
        for game in GameSession.objects.filter(ended_at__isnull=True)
        if last_activity(game) < now - timedelta(days=game.idle_end_days)
    ]


def end_idle_game(game: GameSession) -> None:
    """End the game the way the host's stop does. post_save (game_start)
    sends game.ended."""
    game.end(GameSession.EndReason.IDLE)
    logger.info(f"Game {game.game_id} ended after {game.idle_end_days} idle days")
