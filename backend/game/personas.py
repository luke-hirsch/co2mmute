"""Pendlertypen: dealt to the Gruppen at join, read back in the debrief.

A Pendlertyp is a mission a Gruppe is played as. The host picks the game's at
creation (`GameSessionCreateSerializer`); each seat is dealt them at join, one
per Gruppe; the summary lays out how each Gruppe of a seat commuted, so a player
can hold what it did against what it was meant to be.
"""

from __future__ import annotations

import random
from collections import Counter

PT_MODES = ("bus", "train")


def deal(persona_ids: list[int], count: int, rng=random) -> list[int]:
    """One Pendlertyp per Gruppe, from a deck shuffled for this seat.

    Different ones for as long as the deck lasts, so a player's own Gruppen are
    worth comparing; with more Gruppen than Pendlertypen it goes round again.
    Empty when the game has none.
    """
    if not persona_ids:
        return []
    deck = list(persona_ids)
    rng.shuffle(deck)
    return [deck[i % len(deck)] for i in range(count)]


def persona_counts(game) -> list[dict]:
    """The game's Pendlertypen that are in play, with how many Gruppen hold each.

    Read off the seats still playing (the one counting rule), in the order the
    host listed the types. A type nobody was dealt is not in play and is left
    out; a game without types gives an empty list. It names no seat, which is the
    point: the Leitstelle can say what the room is, not who is what.
    """
    from game.models import Player

    held: Counter = Counter()
    for assignments in (
        Player.objects.filter(game=game)
        .playing()  # type: ignore[attr-defined]
        .values_list("agent_assignments", flat=True)
    ):
        for agent in (assignments or {}).get("agents", []):
            if agent.get("persona") is not None:
                held[agent["persona"]] += 1
    return [
        {"id": persona.pk, "name": persona.name, "groups": held[persona.pk]}
        for persona in game.personas.order_by("order", "pk")
        if held[persona.pk]
    ]


def changes(segments) -> int:
    """How often a trip changes from one ride to the next.

    A ride is a run of bus or train segments on one line; a walk between two
    rides of the same line is getting off and on again, and that is a change
    too. Segments come in their `order`.
    """
    rides = 0
    riding = None
    for segment in segments:
        if segment.mode in PT_MODES:
            line = (segment.mode, segment.pt_line_id)
            if line != riding:
                rides += 1
            riding = line
        else:
            riding = None
    return max(rides - 1, 0)


def group_summary(player, completed_rounds, people_per_agent: int) -> list[dict]:
    """Each Gruppe of one seat over the whole game, a day at a time.

    One entry per Gruppe the seat was dealt, with where it lived and worked
    and its Pendlertyp: how often it took each mode, and the mean of a day
    there and back — time, distance, speed door to door, what one commuter
    paid, their CO₂, their changes.
    Only rounds the simulation ran count, since those are the ones with a
    result; a Gruppe with none has zeros and no modes.
    """
    from game.models import AgentRoute
    from maps.models import Node

    agents = (player.agent_assignments or {}).get("agents", [])
    if not agents:
        return []

    personas = {p.pk: p for p in player.game.personas.all()}
    names = dict(
        Node.objects.filter(
            pk__in=[
                a.get(key) for a in agents for key in ("home_node", "destination_node")
            ]
        ).values_list("pk", "name")
    )

    routes = (
        AgentRoute.objects.filter(
            player_move__player=player,
            player_move__session_round__in=completed_rounds,
        )
        .select_related("player_move")
        .prefetch_related("segments", "simulation_results")
    )
    days: dict[tuple[int, int], dict] = {}
    for route in routes:
        key = (route.player_move.session_round_id, route.agent_id)
        days.setdefault(key, {})[route.direction] = route

    people = people_per_agent or 1
    groups = []
    for agent in agents:
        agent_id = agent["id"]
        modes: Counter = Counter()
        n = 0
        time_min = distance_m = paid_eur = co2_g = changes_n = 0.0
        for (_round, route_agent), day in days.items():
            if route_agent != agent_id:
                continue
            out = day.get(AgentRoute.Direction.OUT)
            if out is None:
                continue
            results = list(out.simulation_results.all())
            if not results:
                continue
            result = results[0]
            home = day.get(AgentRoute.Direction.HOME)
            n += 1
            modes[out.transport_mode] += 1
            time_min += result.round_trip_time_min
            paid_eur += result.mean_paid_eur
            co2_g += result.total_co2_g / people
            distance_m += out.total_distance_m
            changes_n += changes(out.segments.all())
            if home is not None:
                distance_m += home.total_distance_m
                changes_n += changes(home.segments.all())

        persona = personas.get(agent.get("persona"))
        groups.append(
            {
                "agent_id": agent_id,
                "home": names.get(agent.get("home_node")),
                "destination": names.get(agent.get("destination_node")),
                "persona": (
                    {"name": persona.name, "description": persona.description}
                    if persona
                    else None
                ),
                "rounds": n,
                "modes": dict(sorted(modes.items())),
                "time_min": round(time_min / n, 1) if n else 0.0,
                "distance_km": round(distance_m / 1000 / n, 1) if n else 0.0,
                "speed_kmh": (
                    round(distance_m / 1000 / (time_min / 60), 1)
                    if time_min > 0
                    else 0.0
                ),
                "paid_eur": round(paid_eur / n, 2) if n else 0.0,
                "co2_g": round(co2_g / n, 1) if n else 0.0,
                "changes": round(changes_n / n, 1) if n else 0.0,
            }
        )
    return groups
