"""The numbers a game is played against, and where they come from.

S2. Two settings decide whether a round means anything: how many real people
one Gruppe stands for, and how much CO2 the class may spend. Neither had ever
been calibrated — the shipped pair was 1000 people per Gruppe against a
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
that population between its Gruppen — it does not summon a new population
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
of how many Gruppen share them.

**6 400 is what the graph can carry, not what the district holds.**
Far below Berlin Mitte-West's real commuter count, and deliberately so: the
graph abstracts a district to its main corridors, so the population it can
carry is the population those corridors carry. At 6 400, everybody driving puts
the busiest links (Hansaplatz — Großer Stern — Brandenburger Tor) at about
115 % of their flow capacity and gives a 7.66 km commute 20.4 min against
9.5 min free flow. Inner Berlin's morning peak runs at roughly 24 km/h, which
is the same 11 minutes of delay. Raise it and the model reports commutes no
city has: 1 000 people per Gruppe at 64 Gruppen is 298 min, with no
deadlock and no forced release — the model is fine, the demand is not, and
64 000 cars would need about five times the lanes the map has.

**The budget is per round, and carries no Gruppe term.**
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
eleven of 64 Gruppen had to drive whatever the class decided. A round with
nobody in a car is 46 % cheaper than it was. The budget still sits in the range
— all-car busts it, an improving class finishes — but by less than it did, which
is worth a look at the next play-test.

Those five rows come from a harness of their own (64 Gruppen spread evenly
over all 36 home/workplace pairs) and are **not** comparable with the tables
above, whose assignment of Gruppen to pairs was a different one and whose network
therefore jams a little less. Compare before against after within a row.

**S23 measured the map S16 shipped — the eight-version one the box plays —**
whose base version had never had a round simulated on it. Same harness as the
S5 table above, 2026-10-01:

    car share   round total     car   timetable   car trip / delay
         100 %    13 059 kg  10 194     2 864       22.5 / 12.5 min
          75 %     9 884 kg   6 903     2 981       15.4 /  5.4 min
          50 %     7 184 kg   4 164     3 020       10.6 /  0.7 min
          25 %     5 345 kg   2 207     3 139       10.8 /  0.1 min
           0 %     3 194 kg       0     3 194            —

Within a few per cent of S5's rows, and the floor is the same 2 864 kg. What
changed is the budget's margin: the improving class (100/75/50/50/25/25 %)
spends 48 001 kg against 48 000, and all-car runs out in round 4, not 5.
9 000 kg a round would restore the old story — all-car out in round 5, an
improving class about six tonnes inside. A proposal for the next play-test,
not a change: the number lives in the map file. PT waits grow with riders (9 to
22 min) because vehicles fill; the same pairs at a quarter of the people wait
7.6 min. docs/kalibrierung.md §9 has the full table.

**Everything above is one way: the walk to work.** A round has simulated the
way home as well since 2026-10-01, as a second pass on a fresh network, so what
a round costs doubled and the budget doubled with it — 16 000 kg a round, 96 000
for six, not 8 000 and 48 000. Measured the same way, a round trip is 1.96 to
2.06 times the way there:

    car share   round total     car   timetable
         100 %    25 614 kg  19 885     5 729
          75 %    19 626 kg  13 673     5 953
          50 %    14 470 kg   8 337     6 134
          25 %    10 883 kg   4 415     6 468
           0 %     6 582 kg       0     6 582

The improving class spends 95 946 kg over six rounds against 96 000, all-car is
out in round 4: the same edge as one trip ago. The way-there rows of that run
reproduce the table above to the kilogram. docs/kalibrierung.md §10.

**Since 2026-10-02 every line runs until everybody is home**, ridden or not;
past its timetable a line used to run only for its own riders. Same harness,
routes re-dumped after bus 100, the Stadtbahn and U7 moved to the side of the
street they drive (the same lines, the other side), round trip:

    car share   round total     car   timetable   timetable before
         100 %    26 367 kg  19 631     6 736          5 729
          75 %    20 323 kg  13 530     6 792          5 966
          50 %    16 174 kg   8 318     7 856          6 145
          25 %    14 340 kg   4 415     9 925          6 464
           0 %    10 402 kg       0    10 402          6 585

The car side does not move; the timetable grows most where most people ride,
because a PT trip takes twice a car trip and every line runs while one rider is
out. The improving class spends 107 716 kg against 96 000 (95 541 the moment
before), all-car is out in round 4, so the budget no longer separates the two.
18 000 kg a round would put the improving class 284 kg inside; the map keeps
16 000 (decided 2026-10-02), so finishing all six rounds takes switching sooner.
docs/kalibrierung.md §11.

**Since 2026-10-05 a new map is measured by one rule** (the functions at the
bottom of this module, run by `manage.py calibrate_map`). On Berlin Mitte-West,
on Postgres, its half-driving round trip is 15 854 kg — 16 000, the map's
number — while its 6 400 commuters drive at 20.7 km/h when everybody drives,
not the city's 24; at 24 km/h the rule says 5 700 and 14 000.
docs/kalibrierung.md §12.

Re-deriving these after a model change means replaying rounds on the map in
question (`calibrate_map`), not adjusting them until a play-test feels right.
What each number is FOR is asserted in `game/tests/test_join.py`.
"""

import math
import statistics
from dataclasses import dataclass, field

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
    """How many real people one Gruppe stands for, for this class size.

    Floored at 1: a game with more Gruppen than the district has commuters is
    nonsense, but it must not be a game where each one stands for nobody.

    Args:
        max_players: Seats the game has in total.
        agent_per_player: Gruppen each seat starts with.
        game_map: The map being played, for its `district_commuters`. Omitted
            before a map is chosen, which falls back to the field default.

    Returns:
        People per Gruppe, so that max_players * agent_per_player * this is
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


# ---------------------------------------------------------------------------
# Calibrating a new map: one rule, measured once (`manage.py calibrate_map`).
#
# Budget per round = what a round costs when half the Gruppen drive and the
# rest ride, rounded to a number a class can hold. Commuters = as many as make
# a morning where everybody drives as slow as the city's own rush hour. The
# share is the difficulty: more driving Gruppen is a looser budget. On Berlin
# Mitte-West the half-driving round trip is 16 174 kg (docs/kalibrierung.md
# §11), so its 16 000 is this rule.
#
# The functions below take `play`, a function that plays one round and
# returns what it cost (`game/measure.py:MapRounds.play`), so the rule can be
# read and tested apart from the database.
# ---------------------------------------------------------------------------

BUDGET_SHARE = 0.5
TABLE_SHARES = (1.0, 0.75, 0.5, 0.25, 0.0)

# The seeds every measurement in docs/kalibrierung.md was taken over.
SEEDS = (101, 102, 103, 104, 105, 106)

# How far the search for the commuter count may grow from where it starts —
# 2^5, i.e. 32 times the map's current figure — before it says the map cannot
# get that slow. A round's cost grows with its people, so this also bounds how
# long a calibration can take.
GROWTH_STEPS = 5
BISECTION_STEPS = 12


class CalibrationRefused(Exception):
    """The rule has no answer on this map, and the message says why."""


def round_figure(value: float) -> int:
    """Two significant figures: a number a class can hold in its head.

    16 174 → 16 000, 6 437 → 6 400, 853 → 850. A half rounds up.
    """
    if value <= 0:
        return 0
    step = 10 ** max(0, math.floor(math.log10(value)) - 1)
    return int(math.floor(value / step + 0.5) * step)


def car_speed(rounds) -> float | None:
    """The cars' mean speed over these rounds' mornings, in km/h.

    Kilometres driven over hours taken, pooled over all rounds — the network's
    speed, not a mean of Gruppen speeds, so a long jammed commute weighs as
    much as it costs. None if anybody was still out when a pass hit its guard:
    that round has no speed, and it is slower than any target.
    """
    if any(r.not_home for r in rounds):
        return None
    hours = sum(r.car_hours for r in rounds)
    if hours <= 0:
        return None
    return sum(r.car_km for r in rounds) / hours


def find_commuters(speed_at, *, target_kmh, start, smallest):
    """The most commuters at which everybody driving still reaches `target_kmh`.

    `speed_at(commuters)` is the cars' speed on a morning where everybody
    drives, or None for one that never ended. `smallest` is one person per
    Gruppe; a round has whole people in each, so every population tried is a
    multiple of it — anything between would be rounded to the same round and
    measured twice. Doubles or halves from `start` until the target lies
    between two measurements, then halves the gap (in proportion, since the
    populations span orders of magnitude) until both ends round to the same
    figure or are one person per Gruppe apart.

    Returns the rounded commuter count and every measurement taken, by
    commuters, so the caller can show the search.
    """
    step = int(smallest)
    searched = {}

    def fast_enough(per_gruppe):
        population = per_gruppe * step
        if population not in searched:
            searched[population] = speed_at(population)
        speed = searched[population]
        return speed is not None and speed >= target_kmh

    def shown(per_gruppe):
        speed = searched[per_gruppe * step]
        return "nie fertig" if speed is None else f"{speed:.1f} km/h"

    per_gruppe = max(1, round(start / step))
    if fast_enough(per_gruppe):
        fast, slow = per_gruppe, None
        for _ in range(GROWTH_STEPS):
            per_gruppe *= 2
            if not fast_enough(per_gruppe):
                slow = per_gruppe
                break
            fast = per_gruppe
        if slow is None:
            raise CalibrationRefused(
                f"Auch bei {fast * step} Pendlern fahren alle Autos noch "
                f"{shown(fast)}, schneller als {target_kmh:g} km/h. Die Wege der "
                "Karte verteilen sich auf zu viele Spuren, um so langsam zu werden."
            )
    else:
        fast, slow = None, per_gruppe
        while per_gruppe > 1:
            per_gruppe = max(1, per_gruppe // 2)
            if fast_enough(per_gruppe):
                fast = per_gruppe
                break
            slow = per_gruppe
        if fast is None:
            raise CalibrationRefused(
                f"Schon bei {step} Pendlern, einem Menschen pro Gruppe, fahren "
                f"die Autos nur {shown(1)}, langsamer als {target_kmh:g} km/h. "
                "So schnell ist die Karte auch leer nicht."
            )

    for _ in range(BISECTION_STEPS):
        if slow - fast <= 1 or round_figure(fast * step) == round_figure(slow * step):
            break
        middle = min(slow - 1, max(fast + 1, round(math.sqrt(fast * slow))))
        if fast_enough(middle):
            fast = middle
        else:
            slow = middle
    return round_figure(fast * step), searched


@dataclass
class Calibration:
    """What the rule says about one map, and the rounds it read that off."""

    commuters: int
    budget_kg: int
    budget_measured_kg: float
    share: float
    target_kmh: float | None
    # The cars' morning speed when everybody drives, at `commuters`.
    speed_kmh: float | None
    # Every population the search tried, and the speed it measured.
    searched: dict = field(default_factory=dict)
    # Share → the rounds played at `commuters`, one per seed, there and back.
    rows: dict = field(default_factory=dict)


def calibrate(
    play,
    *,
    start,
    smallest,
    target_kmh=None,
    commuters=None,
    share=BUDGET_SHARE,
    seeds=SEEDS,
):
    """Apply the rule on the map `play` plays.

    Give `target_kmh` to search the commuter count, or `commuters` to keep
    one — the budget is measured at it either way. `start` is where the search
    begins (the map's current figure), `smallest` the fewest commuters a round
    can have (one person per Gruppe).
    """
    searched = {}
    if commuters is None:
        if target_kmh is None:
            raise ValueError("calibrate needs a target speed or a commuter count")

        def speed_at(population):
            return car_speed(
                [
                    play(commuters=population, share=1.0, seed=seed, way_home=False)
                    for seed in seeds
                ]
            )

        commuters, searched = find_commuters(
            speed_at, target_kmh=target_kmh, start=start, smallest=smallest
        )

    rows = {
        level: [play(commuters=commuters, share=level, seed=seed) for seed in seeds]
        for level in sorted(set(TABLE_SHARES) | {share}, reverse=True)
    }
    measured = statistics.mean(r.total_kg for r in rows[share])
    return Calibration(
        commuters=commuters,
        budget_kg=max(1, round_figure(measured)),
        budget_measured_kg=measured,
        share=share,
        target_kmh=target_kmh,
        speed_kmh=car_speed(rows[1.0]),
        searched=searched,
        rows=rows,
    )
