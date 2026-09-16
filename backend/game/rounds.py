"""Round completion — the single place that decides a round is over."""

import logging

from django.db import transaction

from game.models import GameRound, GameSession, Player, PlayerMove

logger = logging.getLogger(__name__)


def active_player_count(game: GameSession) -> int:
    """Players whose move the round is waiting for.

    The counting rule, applied identically on both sides of the comparison:
    active (`left_at__isnull=True`) and not host-controlled. The old post_save
    receiver counted every Player row, so a game where anyone had left could
    never complete.
    """
    return Player.objects.filter(
        game=game, left_at__isnull=True, controlled_by_host=False
    ).count()


def submitted_move_count(game_round: GameRound) -> int:
    return PlayerMove.objects.filter(
        session_round=game_round,
        player__controlled_by_host=False,
        player__left_at__isnull=True,
    ).count()


def complete_round_if_ready(game_id: str) -> bool:
    """Complete the current round if every active player has moved.

    Returns True only for the caller that actually claimed the round, so it is
    safe to call from anywhere, as often as you like.

    Must run *after* the move and its routes are committed — call it from
    transaction.on_commit, never from inside the transaction that writes the
    move. Routes are stored after the PlayerMove row, so a caller that fires too
    early makes handle_round_completed see has_routes=False and silently fall
    back to _calculate_hardcoded_stats instead of simulating.
    """
    try:
        game = GameSession.objects.get(game_id=game_id)
    except GameSession.DoesNotExist:
        logger.error(f"Game {game_id} not found while checking round completion")
        return False

    if not game.is_active:
        return False

    game_round = GameRound.objects.filter(game=game).order_by("-round_number").first()
    if not game_round or game_round.status != GameRound.Status.ACTIVE:
        return False

    expected = active_player_count(game)
    submitted = submitted_move_count(game_round)
    if expected == 0 or submitted < expected:
        return False

    # Atomic claim. Two players submitting at the same instant both get here;
    # exactly one of them gets a 1 back and dispatches. Today this is prevented
    # only by the accidental ordering of the two old callers.
    claimed = GameRound.objects.filter(
        pk=game_round.pk, status=GameRound.Status.ACTIVE
    ).update(status=GameRound.Status.COMPLETED)

    if not claimed:
        logger.info(
            f"Round {game_round.round_number} of {game_id} already claimed elsewhere"
        )
        return False

    logger.info(
        f"Round {game_round.round_number} of {game_id} complete "
        f"({submitted}/{expected} moves), dispatching simulation"
    )

    from game.tasks import run_simulation_task

    run_simulation_task.delay(game_round.pk)  # type: ignore
    return True


def schedule_round_completion_check(game_id: str) -> None:
    """Run the check once the surrounding transaction has committed.

    Outside a transaction Django runs the callback immediately, so this is also
    correct for callers that are not in an atomic block (the post_delete
    receiver, for one).
    """
    transaction.on_commit(lambda: complete_round_if_ready(game_id))
