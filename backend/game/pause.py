"""The bell: the host pauses a running game and resumes it later.

Roadmap.md 1.6. While a game is paused nobody moves, acks or votes, and no
round or phase ends (rounds.py, phases.py and PlayerMoveView check it). The
seats can still be changed: adding, removing, and in 1.7 taking over and
handing on are what the break is for. Resuming runs the checks such a change
may have made due.

Both transitions are a conditional update(), so each one happens once however
many requests arrive together.
"""

import logging
from datetime import datetime

from co2mmute.utils import send_game_state_message
from django.utils import timezone

from game.cache import invalidate_game_session
from game.models import GameSession
from game.phases import schedule_recheck
from game.rounds import schedule_round_completion_check

logger = logging.getLogger(__name__)


class PauseRefused(Exception):
    """reason goes to the client as is."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def pause_game(game_id: str) -> datetime:
    """Pause a running game. Returns the pause's start.

    Raises PauseRefused("paused") if it already is, ("not_running") if it
    hasn't started or has ended.
    """
    now = timezone.now()
    # update() skips auto_now, so updated_at is set by hand. It is what the
    # idle end counts as activity.
    paused = GameSession.objects.filter(
        game_id=game_id, is_active=True, paused_at__isnull=True
    ).update(paused_at=now, updated_at=now)
    if not paused:
        already = GameSession.objects.filter(
            game_id=game_id, is_active=True, paused_at__isnull=False
        ).exists()
        raise PauseRefused("paused" if already else "not_running")

    # update() skips post_save too, which is what refreshes the cached copy.
    invalidate_game_session(game_id)
    send_game_state_message(game_id, "game.paused", {"paused_at": now.isoformat()})
    logger.info(f"Game {game_id} paused")
    return now


def resume_game(game_id: str) -> None:
    """Resume a paused game. Raises PauseRefused("not_paused") otherwise."""
    now = timezone.now()
    resumed = GameSession.objects.filter(
        game_id=game_id, paused_at__isnull=False
    ).update(paused_at=None, updated_at=now)
    if not resumed:
        raise PauseRefused("not_paused")

    invalidate_game_session(game_id)
    send_game_state_message(game_id, "game.resumed", {})
    logger.info(f"Game {game_id} resumed")

    # A seat removed during the pause may have been the last one the round or
    # the between-round phase waited for. Both checks claim before they act.
    schedule_round_completion_check(game_id)
    schedule_recheck(game_id)
