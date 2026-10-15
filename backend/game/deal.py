"""Where a seat's Gruppen live and work: dealt at join.

Two deals, the host's pick when the game is made (`GameSession.balanced_deal`):

- **Off**, the default: a seat draws one free home and all its Gruppen live
  there; once every home is taken, homes are reused at random. Workplaces are
  shuffled per seat and cycled. A class plays as districts.
- **"ausbalanciert"**: every home and every workplace carries the same number
  of Gruppen, give or take one, over the seats still playing. A seat's Gruppen
  live at different homes spread over the map, and a class with fewer Gruppen
  than the map has homes plays homes spread over it: a home is taken least
  loaded first, then in the game's `halves` order. The workplace is drawn among
  the least loaded, so who works where is still the luck of the game.

The calibration plays every home with every workplace either way, the
expectation of both deals. Both doors that make a seat hold the game row
(`select_for_update`) while they do, so two seats never count the same loads.
"""

from __future__ import annotations

import logging
import random
from collections import Counter

from game.personas import deal as deal_personas

logger = logging.getLogger(__name__)


def halves(points: list[tuple[int, float, float]], rng) -> list[int]:
    """Node ids in an order whose every beginning is spread over the map.

    `points` are `(id, x, y)`. Cut them at the median along the longer side of
    their box, put the two halves in a random order and alternate between
    them, and each half the same way: the first two lie in different halves,
    the first four in different quarters, and so on. The builder places homes
    by the same cut, so a half holds about as many people as the other.

    Farthest-first, the other way to spread, runs to the edge of the map: on
    all of Berlin a class of four seats commuted 27 % farther than the
    calibration's mean over every home and workplace. This order keeps to it.
    """
    if len(points) <= 1:
        return [pk for pk, _, _ in points]
    xs = [x for _, x, _ in points]
    ys = [y for _, _, y in points]
    axis = 1 if max(xs) - min(xs) >= max(ys) - min(ys) else 2
    # The id breaks ties, so the order is the game's, not the database's.
    ordered = sorted(points, key=lambda point: (point[axis], point[0]))
    middle = len(ordered) // 2
    first, second = ordered[:middle], ordered[middle:]
    if rng.random() < 0.5:
        first, second = second, first
    a, b = halves(first, rng), halves(second, rng)
    order = []
    for i in range(max(len(a), len(b))):
        order.extend(part[i] for part in (a, b) if i < len(part))
    return order


def balanced(
    order: list[int],
    home_load: Counter,
    workplaces: list[int],
    work_load: Counter,
    count: int,
    rng,
) -> list[tuple[int, int]]:
    """One seat's Gruppen as `(home, workplace)`, given the loads before it.

    A home: one this seat holds fewest Gruppen at, then the least loaded, then
    the first in `order` — so the seat's Gruppen live at different homes while
    the map has enough, and a class fills the map in the order's spread. A
    workplace: drawn among the least loaded. The loads passed in stay as they
    are.
    """
    home_load, work_load = Counter(home_load), Counter(work_load)
    rank = {pk: i for i, pk in enumerate(order)}
    mine: Counter = Counter()
    pairs = []
    for _ in range(count):
        home = min(order, key=lambda pk: (mine[pk], home_load[pk], rank[pk]))
        least = min(work_load[pk] for pk in workplaces)
        work = rng.choice([pk for pk in workplaces if work_load[pk] == least])
        mine[home] += 1
        home_load[home] += 1
        work_load[work] += 1
        pairs.append((home, work))
    return pairs


def assign_agent_nodes(game_session, player, rng=random) -> dict | None:
    """A home and a workplace for each of the seat's Gruppen, and a Pendlertyp
    when the game deals them.

    `{"agents": [{"id": 1, "home_node": …, "destination_node": …}, …]}`, or
    None when the map has no base version, no homes or no workplaces.
    """
    from game.models import Player
    from maps.models import MapVersion, Node

    game_map = game_session.game_map
    if not game_map:
        return None

    base_version = MapVersion.objects.filter(
        game_map=game_map, base_version=True
    ).first()
    if not base_version:
        logger.warning(f"No base version found for map {game_map.pk}")
        return None

    in_base = Node.objects.filter(game_map=game_map, map_versions=base_version)
    homes = sorted(
        in_base.filter(node_type__name="home")
        .values_list("id", "x_position", "y_position")
        .distinct()
    )
    destination_nodes = sorted(
        in_base.filter(node_type__name="workplace")
        .values_list("id", flat=True)
        .distinct()
    )

    if not homes:
        logger.warning(f"No home nodes found for map {game_map.pk}")
        return None

    if not destination_nodes:
        logger.warning(f"No destination nodes found for map {game_map.pk}")
        return None

    agent_count = game_session.agent_per_player

    if game_session.balanced_deal:
        # The Gruppen that play: a seat that left plays no more, and the
        # host's own row never does.
        home_load, work_load = Counter(), Counter()
        for agent in _agents_of(
            Player.objects.filter(game=game_session).playing().exclude(pk=player.pk)
        ):
            home_load[agent.get("home_node")] += 1
            work_load[agent.get("destination_node")] += 1
        # One order per game, the same at every join.
        order = halves(list(homes), random.Random(game_session.pk))
        pairs = balanced(
            order, home_load, destination_nodes, work_load, agent_count, rng
        )
    else:
        home_nodes = {pk for pk, _, _ in homes}
        used_home_nodes = {
            agent.get("home_node")
            for agent in _agents_of(
                Player.objects.filter(game=game_session).exclude(pk=player.pk)
            )
        }
        available_home_nodes = sorted(home_nodes - used_home_nodes)
        if not available_home_nodes:
            # More players than homes: reuse.
            logger.warning(
                f"All home nodes taken for game {game_session.game_id}, reusing"
            )
            available_home_nodes = sorted(home_nodes)
        home_node_id = rng.choice(available_home_nodes)

        # Shuffled per seat and cycled when there are fewer than Gruppen.
        shuffled_destinations = list(destination_nodes)
        rng.shuffle(shuffled_destinations)
        pairs = [
            (home_node_id, shuffled_destinations[i % len(shuffled_destinations)])
            for i in range(agent_count)
        ]

    # One Pendlertyp per Gruppe, when the game has them; none, and it plays free.
    personas = deal_personas(
        list(game_session.personas.values_list("pk", flat=True)), agent_count, rng
    )

    agents = []
    for i, (home, destination) in enumerate(pairs):
        agent = {"id": i + 1, "home_node": home, "destination_node": destination}
        if personas:
            agent["persona"] = personas[i]
        agents.append(agent)
    return {"agents": agents}


def _agents_of(players):
    for assignments in players.values_list("agent_assignments", flat=True):
        if isinstance(assignments, dict):
            yield from assignments.get("agents", [])
