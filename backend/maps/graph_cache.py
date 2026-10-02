"""The cached map graph, and the one way to throw it away.

`GET graph/…` builds the payload the client routes and draws on and keeps it an
hour under map + version: a class of thirty phones asks for the same graph at
the start of every round. The map editor reads its own writes back through the
same endpoint, so every write to a map row has to make the next read rebuild.

Two things went wrong with "delete the key on save", and both are why this is a
module of its own:

* **Only `Node` and `Edge` cleared it.** A street or a railway under an edge, a
  line, a chain row and every `map_versions.add` saved without a word, so the
  editor's "+ Straße anlegen" answered 201 and drew nothing — for up to an
  hour, or until some unrelated node was dragged. The signals in
  `maps/signals.py` now cover every model a graph is built from.
* **Deleting a key does not stop a read already under way from putting it
  back.** Building the graph takes long enough (1.7 s on the shipped map, local
  sqlite) for the editor's next write to land in the middle, and the read then
  stored the graph it had read *before* that write. So the key carries a
  generation: every write moves it, and a read stores under the generation it
  started with — a key nobody will ask for again.

The generation is moved twice, now and when the transaction commits. Now, so a
read in the same transaction (every `TestCase`) sees the change; on commit,
because a read that starts between the write and the commit cannot see the
uncommitted row and would otherwise store the old graph under the new
generation.
"""

from django.core.cache import cache
from django.db import transaction

# An hour: the graph changes only when someone edits the map.
GRAPH_TIMEOUT_S = 3600


def _generation_key(map_pk) -> str:
    return f"map_graph_generation:{map_pk}"


def generation(map_pk) -> int:
    """The map's current generation — read once, at the start of a read."""
    return cache.get(_generation_key(map_pk), 0)


def graph_key(map_pk, version_pk, at_generation) -> str:
    """Where a graph built at `at_generation` is stored.

    `version_pk` is `None` for `graph/baseversion/`, which is its own entry.
    """
    return f"map_graph:{map_pk}:{version_pk}:{at_generation}"


def _bump(map_pk) -> None:
    key = _generation_key(map_pk)
    # `incr` refuses a missing key, and `add` is a no-op on an existing one, so
    # the two together are race-free on Redis and on locmem alike. No timeout:
    # a generation that expired would start again at 0 and could meet a stored
    # graph from the last time it was 0.
    cache.add(key, 0, timeout=None)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=None)


def invalidate(map_pk) -> None:
    """Every stored graph of the map is stale from here on."""
    if map_pk is None:
        return
    _bump(map_pk)
    transaction.on_commit(lambda: _bump(map_pk))
