"""Which names a player may not take.

The chat and the roster call the host Spielleitung. A player who joins under a
name that reads as that could pass for the host in the chat, so the join and the
seat refuse it: the name itself, however it is written, and its near misses.
"""

from game.models import HOST_NAME

# The digits that stand in for a letter at a glance.
_LOOK_ALIKES = str.maketrans({"1": "i", "0": "o", "3": "e"})
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

# How many edits away from the host's name still counts as it.
MAX_DISTANCE = 2


def _squash(name: str) -> str:
    """Letters only, lower case, umlauts and look-alike digits folded."""
    folded = name.lower().translate(_UMLAUTS).translate(_LOOK_ALIKES)
    return "".join(ch for ch in folded if ch.isalpha())


def _distance(a: str, b: str) -> int:
    """Edits between two strings: an insert, a delete, a substitution, or two
    neighbouring letters swapped, each one edit (Damerau–Levenshtein, restricted)."""
    previous2: list[int] = []
    previous = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        row = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            row[j] = min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                row[j] = min(row[j], previous2[j - 2] + 1)
        previous2, previous = previous, row
    return previous[len(b)]


def looks_like_the_host(name: str) -> bool:
    """Whether a player's name reads as the host's, within `MAX_DISTANCE` edits."""
    squashed = _squash(name)
    if not squashed:
        return False
    return _distance(squashed, _squash(HOST_NAME)) <= MAX_DISTANCE
