"""A participant code in the one way in: the card's 8 characters.

`game` knows nothing of this; `StudiesConfig.ready()` registers it
(`game.codes.register_code_kind`, `register_look_extra`).

GET says which study the card belongs to and which of its games wait in their
lobby, each with what a game id's look gives. A game the card already plays in
is left out, so a card that has played everything says so instead of offering
a game it would be refused. POST joins one of them exactly as a game id does
(`game.views_join.take_game`) and writes the `StudySeat` inside the same
transaction and lock.
"""

from game.codes import CodeRefused, UnknownCode
from game.models import GameSession
from game.views_join import game_look, take_game
from rest_framework.response import Response

from studies.models import Participant, StudyGame, StudySeat


def _card(code: str) -> Participant:
    card = Participant.objects.select_related("study").filter(code=code).first()
    if card is None:
        raise UnknownCode
    return card


def _waiting(card: Participant) -> tuple[list[GameSession], bool]:
    """The study's games a person can still sit down in, and whether the card
    has already played some of the ones that wait."""
    games = [
        link.game
        for link in StudyGame.objects.filter(
            study=card.study, game__started_at__isnull=True, game__ended_at__isnull=True
        ).select_related("game")
    ]
    played = set(
        StudySeat.objects.filter(participant=card).values_list("game_id", flat=True)
    )
    open_games = [g for g in games if g.pk not in played]
    return open_games, len(open_games) < len(games)


def look(request, code):
    card = _card(code)
    games, played = _waiting(card)
    reason = None
    if not games:
        reason = "played" if played else "none_waiting"
    return Response(
        {
            "kind": "participant",
            "study_name": card.study.name,
            "games": [game_look(game) for game in games],
            "reason": reason,
        }
    )


def take(request, code):
    card = _card(code)
    games, _ = _waiting(card)
    wanted = str(request.data.get("game_id") or "").strip().upper()
    if wanted:
        game = next((g for g in games if g.game_id == wanted), None)
        if game is None:
            # Not one of this card's study, or not waiting any more.
            if StudyGame.objects.filter(
                study=card.study, game__game_id=wanted
            ).exists() and StudySeat.objects.filter(
                participant=card, game__game_id=wanted
            ).exists():
                raise CodeRefused("used", USED)
            raise UnknownCode
    elif len(games) == 1:
        game = games[0]
    elif not games:
        raise UnknownCode
    else:
        raise CodeRefused("choose", "Dieser Code passt zu mehreren Spielen. Wähle eins.")

    def seat(player):
        # Inside the join's transaction and under the game's row lock, so two
        # phones with one card cannot both sit down.
        if StudySeat.objects.filter(participant=card, game=player.game).exists():
            raise CodeRefused("used", USED)
        StudySeat.objects.create(participant=card, player=player, game=player.game)

    return take_game(request, game.game_id, on_joined=seat)


USED = "Mit diesem Code hat schon jemand in diesem Spiel mitgespielt."


def coded_study(game) -> dict:
    """Added to a game id's look: the game's study has cards, so a card is the
    better way in."""
    return {
        "coded_study": Participant.objects.filter(
            study__games__game=game
        ).exists()
    }
