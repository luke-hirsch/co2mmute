"""Between-round phases: stats → discussion → voting → stalemate → next round.

Everything that decides when a phase is over lives
here, synchronous and testable without a socket. GameConsumer turns websocket
messages into these calls and does nothing else. handle_round_completed (in the
Celery worker) uses vote_options() for the same ballot.

Every transition is a claim on GameRound.between_round_phase, the pattern
rounds.complete_round_if_ready uses for the round itself: two sockets that
finish a phase at the same instant both get here, and exactly one of them gets
a 1 back from update().

Writes go inside transaction.atomic(), broadcasts after it.
"""

import logging
import random
from collections import Counter

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from co2mmute.utils import sanitize_group_name, send_game_state_message
from django.db import transaction
from django.utils import timezone
from maps.models import MapVersion

from game.models import (
    GameRound,
    GameSession,
    MapVersionVote,
    Player,
    StalemateVote,
    StatsAck,
)
from game.roster import broadcast

logger = logging.getLogger(__name__)

Phase = GameRound.BetweenRoundPhase

MAX_VOTE_OPTIONS = 2
# The first tie in a round asks whether to vote again, the second one leaves
# the map as it is.
MAX_STALEMATES = 2
LEAVE_AS_IS = "Leave as it is"


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────


def _load(game_id: str) -> tuple[GameSession | None, GameRound | None]:
    """The game and its latest round. Between rounds, that is the finished one.

    (None, None) while the game is paused, so every phase function refuses and
    no phase ends. pause.resume_game runs recheck() afterwards.
    """
    game = GameSession.objects.filter(game_id=game_id, paused_at__isnull=True).first()
    if game is None:
        return None, None
    game_round = GameRound.objects.filter(game=game).order_by("-round_number").first()
    return game, game_round


def _playing(game: GameSession):
    return Player.objects.filter(game=game).playing()  # type:ignore


def _seat(game: GameSession, player_id: str, by_host: bool = False) -> Player | None:
    """The playing seat behind a player_id.

    None for the host's own row, for someone who left and for an id from another
    game. None of them take part in a phase. by_host: the host is asking, which
    is only allowed for a seat played at the host machine (Roadmap.md 1.6).
    """
    seats = _playing(game).filter(player_id=player_id)
    if by_host:
        seats = seats.filter(controlled_by_host=True)
    return seats.first()


def _progress(model, game: GameSession, game_round: GameRound) -> tuple[int, int]:
    """(cast, needed) for StatsAck, MapVersionVote or StalemateVote.

    The counting rule on both sides, as in rounds.py: playing seats only. A
    player who left is not waited for, and what they cast no longer counts.
    """
    playing = _playing(game)
    cast = model.objects.filter(game_round=game_round, player__in=playing).count()
    return cast, playing.count()


def _complete(model, game: GameSession, game_round: GameRound) -> bool:
    cast, needed = _progress(model, game, game_round)
    return needed > 0 and cast >= needed


def _claim(game_round: GameRound, from_phase: str, to_phase: str, **extra) -> bool:
    """Move the round from one phase to the next, for exactly one caller.

    update() skips auto_now, so updated_at is set by hand.
    """
    claimed = GameRound.objects.filter(
        pk=game_round.pk, between_round_phase=from_phase
    ).update(between_round_phase=to_phase, updated_at=timezone.now(), **extra)
    return claimed == 1


def _broadcast(game_id: str, event: str, data: dict) -> None:
    """Send a between-round event to every socket in the game.

    GameConsumer.between_round_event forwards it as {"type": event, ...}.
    Sync on purpose: async_to_sync only works outside the event loop, which is
    why the consumer could never send round.started itself.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("No channel layer configured, cannot send between-round event")
        return
    async_to_sync(channel_layer.group_send)(
        f"gamestate_{sanitize_group_name(game_id)}",
        {"type": "between_round_event", "event": event, "data": data},
    )


def _announce_round(game_id: str, started: dict) -> None:
    """round.started, then the roster: every seat is choosing again."""
    send_game_state_message(game_id, "round.started", started)
    broadcast(game_id)


def _start_next_round(
    game: GameSession,
    game_round: GameRound,
    from_phase: str,
    winner_id: int | None = None,
    **extra,
) -> dict | None:
    """Close the between-round phase, apply the vote, open the next round.

    Returns the round.started payload to the caller that claimed the
    transition, None to everyone else.
    """
    with transaction.atomic():
        if not _claim(game_round, from_phase, Phase.NONE, **extra):
            return None
        if winner_id is not None:
            game.active_map_version_id = winner_id  # type: ignore
            game.save(update_fields=["active_map_version", "updated_at"])
        new_round = GameRound.objects.create(
            game=game,
            status=GameRound.Status.ACTIVE,
            started_at=timezone.now(),
        )

    total_game_emissions = sum(
        r.total_emissions_g
        for r in GameRound.objects.filter(game=game, status=GameRound.Status.COMPLETED)
    )
    logger.info(f"Round {new_round.round_number} started for game {game.game_id}")
    return {
        "round_number": new_round.round_number,
        "max_rounds": game.max_rounds,
        "total_game_emissions_g": total_game_emissions,
        "max_co2_level_g": game.max_CO2_level * 1000,
    }


# ─────────────────────────────────────────────────────────────────────────────
# The ballot
# ─────────────────────────────────────────────────────────────────────────────


def _is_rollback_target(active_version, target_version):
    """Return True if target_version is an ancestor of active_version (i.e., a rollback)."""
    if target_version.base_version:
        return True
    current = active_version.source_version
    while current is not None:
        if current.pk == target_version.pk:
            return True
        current = current.source_version
    return False


def _get_delta_img_url(active_version, target_version):
    """
    Return the relative URL of the 'change preview' image for a voting option.

    For rollbacks: the active version's image (showing what will be reverted).
    For forward moves to an atomic version: the target's own image.
    For forward moves to a combo version (e.g. A→AB): find the 'new' component B
    by looking at target's compatible_versions that are not an ancestor of active.
    """
    if _is_rollback_target(active_version, target_version):
        if active_version.change_img:
            return active_version.change_img.url
        return None

    # Collect active's ancestry (source_version chain)
    active_ancestor_pks = set()
    cur = active_version
    while cur:
        active_ancestor_pks.add(cur.pk)
        cur = cur.source_version

    # Only do delta lookup if active is a direct predecessor of target
    # (active appears in target's compatible_versions)
    active_is_predecessor = target_version.compatible_versions.filter(
        pk=active_version.pk
    ).exists()

    if active_is_predecessor:
        # Find the delta: a compat of target that is not an ancestor of active and has an image
        for compat in target_version.compatible_versions.all():
            if compat.pk in active_ancestor_pks:
                continue
            if compat.base_version:
                continue
            if compat.change_img:
                return compat.change_img.url

    # Fallback: target's own image
    if target_version.change_img:
        return target_version.change_img.url
    return None


def _build_version_dict(active_version, target_version):
    """Build the voting option dict for a candidate version."""
    is_rollback = _is_rollback_target(active_version, target_version)
    return {
        "id": target_version.id,
        "name": target_version.name,
        "poll_text": active_version.revert_poll_text
        if is_rollback
        else target_version.poll_text,
        "is_rollback": is_rollback,
        "change_img_url": _get_delta_img_url(active_version, target_version),
    }


def vote_options(game_round: GameRound) -> list[dict]:
    """The ballot for the vote after this round: at most two map versions.

    Drawn once and stored on the round, so round.completed, a reconnect and a
    revote after a stalemate all show the same options, however long the break.
    A new round starts with an empty list and draws again.
    """
    game = game_round.game
    active_version = game.active_map_version
    if not game.game_map or not game.map_updates or active_version is None:
        return []

    if not game_round.vote_option_ids:
        candidate_ids = list(
            active_version.compatible_versions.values_list("pk", flat=True)
        )
        if len(candidate_ids) > MAX_VOTE_OPTIONS:
            candidate_ids = random.sample(candidate_ids, MAX_VOTE_OPTIONS)
        # The first draw wins. A concurrent caller's update matches no row,
        # and it reads the winning draw back below.
        GameRound.objects.filter(pk=game_round.pk, vote_option_ids=[]).update(
            vote_option_ids=candidate_ids
        )
        game_round.refresh_from_db(fields=["vote_option_ids"])  # type: ignore

    versions = MapVersion.objects.filter(pk__in=game_round.vote_option_ids).order_by(
        "pk"
    )
    return [_build_version_dict(active_version, version) for version in versions]


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────


def ack_stats(game_id: str, player_id: str) -> bool:
    """A player has read the round's stats. False if the ack was not taken.

    Stored as a row on the Player, not under the player_id: the Redis set this
    replaces expired after an hour, and would count a player twice once 1.7
    gives them a new id.
    """
    return _ack(game_id, player_id=player_id)


def ack_host_seats(game_id: str) -> bool:
    """The host has read the stats, for every seat played at the host machine.
    They all look at the same screen. False if there is no such seat."""
    return _ack(game_id, controlled_by_host=True)


def _ack(game_id: str, **seat_filter) -> bool:
    """Store an ack for every playing seat matching seat_filter, then try to
    move on."""
    game, game_round = _load(game_id)
    if not game or game_round is None or game_round.between_round_phase != Phase.STATS:
        return False
    seats = list(_playing(game).filter(**seat_filter))
    if not seats:
        return False

    for seat in seats:
        StatsAck.objects.get_or_create(game_round=game_round, player=seat)
    _advance_from_stats(game, game_round)
    return True


def _advance_from_stats(game: GameSession, game_round: GameRound) -> None:
    """Everyone has read the stats: discussion if there is a ballot, else the next round."""
    if not _complete(StatsAck, game, game_round):
        return

    options = vote_options(game_round)
    if options:
        if _claim(game_round, Phase.STATS, Phase.DISCUSSION):
            _broadcast(
                game.game_id,
                "stats.all_acked",
                {"next_phase": "discussion", "map_versions": options},
            )
        return

    started = _start_next_round(game, game_round, Phase.STATS)
    if started:
        _broadcast(game.game_id, "stats.all_acked", {"next_phase": "next_round"})
        _announce_round(game.game_id, started)


# ─────────────────────────────────────────────────────────────────────────────
# Voting
# ─────────────────────────────────────────────────────────────────────────────


def open_vote(game_id: str) -> bool:
    """The host ends the discussion. Only from the discussion phase."""
    _game, game_round = _load(game_id)
    if game_round is None:
        return False
    if not _claim(game_round, Phase.DISCUSSION, Phase.VOTING):
        return False

    _broadcast(game_id, "vote.opened", {"versions": vote_options(game_round)})
    return True


def submit_vote(
    game_id: str, player_id: str, version_id: int | None, by_host: bool = False
) -> bool:
    """One vote per seat per round. None means "leave as it is".

    Only versions on this round's ballot are accepted. by_host: the host votes
    for a seat played at the host machine.
    """
    game, game_round = _load(game_id)
    if not game or game_round is None or game_round.between_round_phase != Phase.VOTING:
        return False
    player = _seat(game, player_id, by_host)
    if player is None:
        return False
    if version_id is not None:
        ballot = {option["id"] for option in vote_options(game_round)}
        if version_id not in ballot:
            return False

    _, created = MapVersionVote.objects.get_or_create(
        game_round=game_round,
        player=player,
        defaults={"map_version_id": version_id},
    )
    if not created:
        return False

    cast, needed = _progress(MapVersionVote, game, game_round)
    _broadcast(
        game_id,
        "vote.recorded",
        {"player_id": player.player_id, "votes_cast": cast, "votes_needed": needed},
    )
    _tally_if_complete(game, game_round)
    return True


def _tally_if_complete(game: GameSession, game_round: GameRound) -> None:
    """Everyone has voted: apply the winner, or ask again after a tie."""
    if not _complete(MapVersionVote, game, game_round):
        return

    votes = list(
        MapVersionVote.objects.filter(
            game_round=game_round, player__in=_playing(game)
        ).select_related("map_version")
    )
    if not votes:
        logger.warning(
            f"Round {game_round.round_number} of game {game.game_id} completed with no votes"
        )
        return
    counter = Counter(vote.map_version_id for vote in votes)  # type:ignore
    names = {
        vote.map_version_id: vote.map_version.name  # type:ignore
        for vote in votes
        if vote.map_version  # type:ignore
    }
    vote_counts = [
        {
            "version_id": version_id,
            "version_name": names.get(version_id, LEAVE_AS_IS),
            "count": count,
        }
        for version_id, count in counter.items()
    ]

    top = max(counter.values())
    leaders = [version_id for version_id, count in counter.items() if count == top]
    tie = len(leaders) > 1
    stalemate_count = game_round.stalemate_count + (1 if tie else 0)

    if tie and stalemate_count < MAX_STALEMATES:
        if _claim(
            game_round, Phase.VOTING, Phase.STALEMATE, stalemate_count=stalemate_count
        ):
            _broadcast(
                game.game_id,
                "vote.stalemate",
                {
                    "stalemate": True,
                    "stalemate_count": stalemate_count,
                    "vote_counts": vote_counts,
                    "winning_version_id": None,
                    "winning_version_name": LEAVE_AS_IS,
                },
            )
        return

    # One winner, or the second tie, which leaves the map as it is.
    winner_id = None if tie else leaders[0]
    started = _start_next_round(
        game,
        game_round,
        Phase.VOTING,
        winner_id=winner_id,
        stalemate_count=stalemate_count,
    )
    if started:
        _broadcast(
            game.game_id,
            "vote.result",
            {
                "stalemate": False,
                "stalemate_count": stalemate_count,
                "winning_version_id": winner_id,
                "winning_version_name": names.get(winner_id, LEAVE_AS_IS),
                "vote_counts": vote_counts,
            },
        )
        _announce_round(game.game_id, started)


# ─────────────────────────────────────────────────────────────────────────────
# Stalemate
# ─────────────────────────────────────────────────────────────────────────────


def submit_stalemate_vote(
    game_id: str, player_id: str, want_revote: bool, by_host: bool = False
) -> bool:
    """After a tie: vote again (True) or leave the map as it is (False).
    by_host as in submit_vote."""

    game, game_round = _load(game_id)
    if (
        not game
        or game_round is None
        or game_round.between_round_phase != Phase.STALEMATE
    ):
        return False
    player = _seat(game, player_id, by_host)
    if player is None:
        return False

    _, created = StalemateVote.objects.get_or_create(
        game_round=game_round,
        player=player,
        defaults={"want_revote": want_revote},
    )
    if not created:
        return False

    cast, needed = _progress(StalemateVote, game, game_round)
    _broadcast(game_id, "stalemate.progress", {"cast": cast, "needed": needed})
    _resolve_stalemate_if_complete(game, game_round)
    return True


def _resolve_stalemate_if_complete(game: GameSession, game_round: GameRound) -> None:
    """Everyone has answered: vote again on a majority for it, else leave the map."""
    if not _complete(StalemateVote, game, game_round):
        return

    answers = StalemateVote.objects.filter(
        game_round=game_round, player__in=_playing(game)
    )
    revote = answers.filter(want_revote=True).count()
    if revote > answers.count() - revote:
        _reopen_vote(game, game_round)
    else:
        _leave_as_is(game, game_round)


def _reopen_vote(game: GameSession, game_round: GameRound) -> None:
    """Same ballot, votes wiped."""
    with transaction.atomic():
        if not _claim(game_round, Phase.STALEMATE, Phase.VOTING):
            return
        MapVersionVote.objects.filter(game_round=game_round).delete()

    _broadcast(game.game_id, "vote.opened", {"versions": vote_options(game_round)})


def force_leave_as_is(game_id: str) -> bool:
    """The host cuts a stalemate short. Only from the stalemate phase."""
    game, game_round = _load(game_id)
    if not game or game_round is None:
        return False
    return _leave_as_is(game, game_round)


def _leave_as_is(game: GameSession, game_round: GameRound) -> bool:
    started = _start_next_round(game, game_round, Phase.STALEMATE)
    if not started:
        return False

    _broadcast(
        game.game_id,
        "vote.result",
        {
            "stalemate": False,
            "winning_version_id": None,
            "winning_version_name": LEAVE_AS_IS,
            "vote_counts": [],
            "forced": True,
        },
    )
    _announce_round(game.game_id, started)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# After someone leaves
# ─────────────────────────────────────────────────────────────────────────────


def recheck(game_id: str) -> None:
    """Finish whatever phase the remaining players have already finished.

    A player leaving lowers the count every phase waits for, so the leave
    itself can complete one. The claims make this safe to call at any time.
    """
    game, game_round = _load(game_id)
    if not game or not game_round:
        return

    phase = game_round.between_round_phase
    if phase == Phase.STATS:
        _advance_from_stats(game, game_round)
    elif phase == Phase.VOTING:
        _tally_if_complete(game, game_round)
    elif phase == Phase.STALEMATE:
        _resolve_stalemate_if_complete(game, game_round)


def schedule_recheck(game_id: str) -> None:
    """recheck() once the surrounding transaction has committed.

    Same idea as rounds.schedule_round_completion_check.
    """
    transaction.on_commit(lambda: recheck(game_id))
