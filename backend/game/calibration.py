"""The numbers a game is played against, and where they come from.

S2. Two settings decide whether a round means anything: how many real people
one Fahrgast stands for, and how much CO2 the class may spend. Neither had ever
been calibrated — the shipped pair was 1000 people per Fahrgast against a
500 kg budget, on a map whose public transport timetable alone emits 2 449 kg
a round before anybody plays. Every game ended in round 1.

**The two inputs live on `GameMap`, not here.** `district_commuters` and
`co2_budget_kg_per_round` are properties of a particular graph: how much
traffic its corridors carry, and what a playable round costs on its distances
and its timetable. Another city is another pair, so a module constant would
have made one neighbourhood's measurements a property of the software. This
module is only the arithmetic on top, plus the record of where the shipped
defaults came from.

Measured on `map_examples/Berlin_Mitte-West.json` (55 nodes, 90 street edges,
6 homes, 6 workplaces, 13 x 10 km at scale 1000), mean home-to-work distance
7.66 km:

**The scale follows the class size, because the district does not.**
A map depicts a place, and a place has a commuter population. The class divides
that population between its Fahrgäste — it does not summon a new population
when more students turn up. Holding `district_commuters` fixed while the seats
vary keeps a round the same round:

    seats  agents  ppa   car CO2    mean trip   mean delay
       16      64  100   8 691 kg     20.4 min     11.3 min
        8      32  200   8 630 kg     20.2 min     11.0 min
        4      16  400   8 904 kg     20.8 min     11.4 min
        2       8  800   8 652 kg     20.7 min     11.5 min

Pin `people_per_agent` to a number instead and the same map gives a half-full
class 0.4 min of delay against 11.3, and 44 % of the CO2 — a different game
depending on who came to the lesson. The route concentration that might have
broken this does not: the class's shortest paths only ever use 29 of the 90
street edges, which is a property of having six homes and six workplaces, not
of how many Fahrgäste share them.

**6 400 is what the graph can carry, not what the district holds.**
Far below Berlin Mitte-West's real commuter count, and deliberately so: the
graph abstracts a district to its main corridors, so the population it can
carry is the population those corridors carry. At 6 400, everybody driving puts
the busiest links (Hansaplatz — Großer Stern — Brandenburger Tor) at about
115 % of their flow capacity and gives a 7.66 km commute 20.4 min against
9.5 min free flow. Inner Berlin's morning peak runs at roughly 24 km/h, which
is the same 11 minutes of delay. Raise it and the model reports commutes no
city has: 1 000 people per Fahrgast at 64 Fahrgäste is 298 min, with no
deadlock and no forced release — the model is fine, the demand is not, and
64 000 cars would need about five times the lanes the map has.

**The budget is per round, and carries no Fahrgast term.**
Because the district's population is constant, a round costs what it costs
however many students play. On the shipped map, with the corrected train
emission factor, measured before the S5 map data pass (see below):

    car share   round total
         100 %    11 140 kg   (8 691 car + 2 449 timetable)
          75 %     8 616 kg
          50 %     6 236 kg
          25 %     4 385 kg
           0 %     2 449 kg   the timetable's own floor

So over six rounds a class that never gets out of the car spends 66 840 kg, and
one that works its way down spends about 41 000. 8 000 kg a round — 48 000 over
six — sits between them: the all-car class runs out in round 5, and a class
that improves finishes with room to spare. It is not the tightest budget that
works; it is the roundest number inside the range, because the class has to be
able to hold it in its head.

**S5 fixed the map the calibration was measured on, and the floor moved.**
`map_examples/Berlin_Mitte-West.json` carried a bus line with no edges, a `101`
that broke mid-chain, a `U2` that served two stations in one direction only, and
60 seats in every vehicle of both modes. With all ten lines connected and
mirrored the timetable drives 98.0 line-km instead of 72.7, so its own floor is
**2 864 kg a round, not 2 449** — 35.8 % of an 8 000 kg round rather than 30.6 %.

Nothing else on the car side moved: at 100 % car the class emits 10 103 kg
before and 10 150 after, inside the 1.4 % spread of six seeds, with the same
22.5 min trip and 12.4 min delay. The eight streets that now state Tempo 30
rather than inheriting 50 are on no car route the class ever takes.

What did move is the reward for getting out of the car. Re-measured over six
seeds with the routes the real client router returns:

    car share   round total, before -> after
         100 %    12 552 -> 13 015 kg
          75 %    10 368 -> 10 003 kg
          50 %     7 544 ->  7 315 kg
          25 %     6 681 ->  5 071 kg
           0 %     5 936 ->  3 191 kg

The 0 % row is the point: 60-seat vehicles forced enough extra runs to put the
timetable at 4 623 kg, and six of the 36 commutes had no PT route at all, so
eleven of 64 Fahrgäste had to drive whatever the class decided. A round with
nobody in a car is 46 % cheaper than it was. The budget still sits in the range
— all-car busts it, an improving class finishes — but by less than it did, which
is worth a look at the next play-test.

Those five rows come from a harness of their own (64 Fahrgäste spread evenly
over all 36 home/workplace pairs) and are **not** comparable with the tables
above, whose Fahrgast-to-pair assignment was a different one and whose network
therefore jams a little less. Compare before against after within a row.

Re-deriving these after a model change means replaying rounds on the map in
question, not adjusting them until a play-test feels right. What each number is
FOR is asserted in `game/tests/test_join.py`.
"""

# What the create form offers, and what the GameSession model defaults agree
# with. The class size, not the calibration — that comes off the map.
DEFAULT_MAX_PLAYERS = 16
DEFAULT_AGENT_PER_PLAYER = 4
DEFAULT_MAX_ROUNDS = 6


def _map_value(game_map, field_name: str) -> int:
    """This map's value for a calibration field, or the field's own default.

    The create form renders before a map is chosen, so there has to be an
    answer without one — and the field default is a better answer than a
    second constant that can drift away from it.
    """
    from maps.models import GameMap

    if game_map is not None:
        return int(getattr(game_map, field_name))
    return int(GameMap._meta.get_field(field_name).default)


def people_per_agent(
    max_players: int, agent_per_player: int, game_map=None
) -> int:
    """How many real people one Fahrgast stands for, for this class size.

    Floored at 1: a game with more Fahrgäste than the district has commuters is
    nonsense, but it must not be a game where each one stands for nobody.

    Args:
        max_players: Seats the game has in total.
        agent_per_player: Fahrgäste each seat starts with.
        game_map: The map being played, for its `district_commuters`. Omitted
            before a map is chosen, which falls back to the field default.

    Returns:
        People per Fahrgast, so that max_players * agent_per_player * this is
        about the map's commuter population.
    """
    commuters = _map_value(game_map, "district_commuters")
    agents = max(1, int(max_players or 0)) * max(1, int(agent_per_player or 0))
    return max(1, round(commuters / agents))


def co2_budget_kg(max_rounds: int, game_map=None) -> int:
    """The CO2 budget in kg for a game of this many rounds on this map.

    Args:
        max_rounds: Rounds the game is played over.
        game_map: The map being played, for its `co2_budget_kg_per_round`.

    Returns:
        Kilograms of CO2 for the whole game.
    """
    per_round = _map_value(game_map, "co2_budget_kg_per_round")
    return per_round * max(1, int(max_rounds or 0))


def per_person(total: float, agent_count: int, people_per_agent_value: int) -> float:
    """Turn a class-scale sum back into what one commuter did once.

    The inverse of the scaling above, and the reason it belongs here: the same
    factor that decides how much demand a class puts on the map decides how a
    figure on the screen has to be read back.

    CO2 and euro are extensive: they add up over agents and over the people each
    agent stands for, so dividing by both gives one person's single commute
    back. Travel time is not — it is passed through here with
    `people_per_agent_value=1`, which makes this a mean over agent-trips rather
    than a per-person figure, because a sum of travel times is not a quantity
    anybody has.

    Zero agent-trips is a round the player sat out; there is nothing to divide
    and nothing to say about it.
    """
    people = agent_count * (people_per_agent_value or 1)
    return total / people if people else 0.0
