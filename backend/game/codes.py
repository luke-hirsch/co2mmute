"""The one place that knows what a code opens, by its length.

A game id is six characters, a seat code seven. Another app can register a
kind of its own (a longer code) from its `AppConfig.ready()`; `game` never
imports such an app, and with it off the length is simply unknown.

`api/game/code/<code>/` is the only door: GET says what the code opens, POST
takes it (`views_join.CodeView`). A kind's `look` and `take` get the request
and the code, return a `Response`, and raise `UnknownCode` when nothing is
behind it.
"""

from dataclasses import dataclass
from typing import Callable

from rest_framework.request import Request
from rest_framework.response import Response

#: `GameSession.game_id` is generated at this length.
GAME_ID_LENGTH = 6
#: `game.seats.issue_code` draws this many characters.
SEAT_CODE_LENGTH = 7


class UnknownCode(Exception):
    """Nothing is behind the code (any more)."""


@dataclass(frozen=True)
class CodeKind:
    look: Callable[[Request, str], Response]
    take: Callable[[Request, str], Response]
    #: Misses are counted and limited per address. A bearer token is, a game
    #: id is not: it stands on the projector and a class mistypes it.
    counted: bool


_kinds: dict[int, CodeKind] = {}


def register_code_kind(
    length: int,
    *,
    look: Callable[[Request, str], Response],
    take: Callable[[Request, str], Response],
    counted: bool = True,
) -> None:
    """Make codes of this length open something. One kind per length."""
    if length in _kinds:
        raise ValueError(f"a code of {length} characters already has a kind")
    _kinds[length] = CodeKind(look=look, take=take, counted=counted)


def kind_for(code: str) -> CodeKind | None:
    """The kind of a normalised code, or None for a length nobody owns."""
    return _kinds.get(len(code))
