"""Play rounds on a map with nobody at a phone, and say what they cost.

A round here is a real round: a `GameSession` with its seats, routes written
by the move endpoint's own validation and writer, run through
`TrafficSimulator` exactly as a finished turn runs — only the class is
replaced by a rule for who drives. Nothing is kept: every round is rolled
back once its numbers are read, so this can run against any database.

The routes come from the game's own router (`frontend/scripts/routes.mjs`),
run on the graph `MapVersionGraphView` serves. There is no Python router: one
router, so the calibration cannot measure a way the class would never be
offered.

Used by `manage.py calibrate_map`, which applies the rule in
`game/calibration.py` to these rounds.
"""

import json
import math
import os
import random
import statistics
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.db import transaction
from rest_framework.test import APIRequestFactory

from game import calibration
from game.models import AgentRoute, GameRound, GameSession, Player, PlayerMove
from game.serializers import PlayerMoveWithRoutesInputSerializer
from game.views_rest import PlayerMoveView

FRONTEND = Path(settings.BASE_DIR).parent / "frontend"

# The seeds every measurement in docs/kalibrierung.md was taken over.
SEEDS = (101, 102, 103, 104, 105, 106)


# What is arbitrary in a class is drawn per seed, so the seeds sample it
# rather than freeze one version of it: the order the seats sit down in (the
# scenario's order, which decides who boards a full bus first — held fixed, one
# arbitrary order moved Berlin's half-driving round by 1.6 %, more than six
# seeds of the simulation's own draws spread), and which pairs drive the one
# Gruppe more when a share does not divide evenly.
def _draw(seed, what):
    return random.Random(f"{seed}:{what}")


# At least as many Gruppen as a full class of the create form's defaults, so a
# share of them is a fine enough step.
MIN_GRUPPEN = calibration.DEFAULT_MAX_PLAYERS * calibration.DEFAULT_AGENT_PER_PLAYER


class RoutesUnavailable(Exception):
    """The game's router could not be run, or answered nothing usable."""


class RoutesRefused(Exception):
    """The move endpoint would refuse a route the router found.

    The map and the router disagree about what is a way — measuring anyway
    would measure a round no class can play.
    """

    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors))


def version_graph(game_map, version):
    """The graph `MapVersionGraphView` serves for this version, as a dict."""
    from maps.views_rest import MapVersionGraphView

    request = APIRequestFactory().get(
        f"/api/maps/{game_map.pk}/graph/version/{version.pk}/"
    )
    response = MapVersionGraphView.as_view()(
        request, pk=game_map.pk, version_pk=version.pk
    )
    if response.status_code != 200:
        raise RoutesUnavailable(f"graph: {response.status_code} {response.data}")
    return json.loads(json.dumps(response.data))


def client_routes(graph):
    """Every commute on `graph`, found by `frontend/scripts/routes.mjs`."""
    script = FRONTEND / "scripts" / "routes.mjs"
    if not (FRONTEND / "node_modules").is_dir():
        raise RoutesUnavailable(
            f"{FRONTEND / 'node_modules'} fehlt — erst `npm ci` in frontend/."
        )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as handle:
        json.dump(graph, handle)
    try:
        done = subprocess.run(
            ["node", str(script), handle.name],
            cwd=FRONTEND,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RoutesUnavailable("node ist nicht installiert.") from exc
    finally:
        os.unlink(handle.name)
    if done.returncode != 0:
        raise RoutesUnavailable(done.stderr.strip() or f"exit {done.returncode}")
    return json.loads(done.stdout)


@dataclass(frozen=True)
class RoundMeasure:
    """What one round cost, read off its result rows.

    Times are means over Gruppen, which all stand for the same number of
    people. `car_km` and `car_hours` sum the way there over driving Gruppen,
    so their ratio is the network's mean car speed in the morning.
    """

    total_kg: float
    car_kg: float
    cost_eur: float
    car_km: float
    car_hours: float
    car_trip_min: float | None
    car_return_min: float | None
    car_delay_min: float | None
    pt_trip_min: float | None
    pt_wait_min: float | None
    not_home: int
    switched: int
    people: int

    @property
    def timetable_kg(self):
        """Everything the cars did not emit: riders' shares and empty runs."""
        return self.total_kg - self.car_kg


def _mean(values):
    return statistics.mean(values) if values else None


class MapRounds:
    """One map version and its commutes, ready to be played at any share.

    Every home goes to every workplace, each pair carrying the same number of
    Gruppen — the class spread evenly over the map, which is what many
    classes on it average to. A seat is a home, as in a game, with its
    Gruppen going to every workplace; the game's own `people_per_agent` rule
    turns the commuter count into people per Gruppe.
    """

    def __init__(self, game_map, version, routes, host):
        self.game_map = game_map
        self.version = version
        self.host = host
        self.commutes = routes["commutes"]
        self.car_optimization = routes["choice"]["carOptimization"]
        if not self.commutes:
            raise RoutesUnavailable(
                "Die Karte hat kein Paar aus Wohnort und Arbeitsplatz."
            )
        self.per_pair = max(1, math.ceil(MIN_GRUPPEN / len(self.commutes)))
        # Commutes by the seat that plays them, in order: index into
        # `self.commutes`, which is also where a Gruppe's number comes from.
        self.seats = {}
        for index, commute in enumerate(self.commutes):
            self.seats.setdefault(commute["home"], []).append(index)
        self.per_seat = max(len(pairs) for pairs in self.seats.values()) * self.per_pair

    @property
    def gruppen(self):
        return len(self.commutes) * self.per_pair

    def people_per_gruppe(self, commuters):
        return calibration.people_per_agent(
            len(self.seats),
            self.per_seat,
            SimpleNamespace(district_commuters=commuters),
        )

    def drivers(self, share, seed):
        """The Gruppen that drive at `share` in the round of `seed`, by index.

        Every pair drives its share: at half, one of each pair's two Gruppen.
        A random half of all Gruppen would put the long commutes in the car
        in one round and the short ones in the next — on Berlin that spread
        the half-driving round by 4 % between seeds, which is the question
        "what does half driving cost" answered with noise. Only a remainder
        is drawn: which pairs drive one Gruppe more.
        """
        pairs = len(self.commutes)
        whole, extra = divmod(round(share * self.gruppen), pairs)
        order = list(range(pairs))
        _draw(seed, "drivers").shuffle(order)
        more = set(order[:extra])
        return {
            pair * self.per_pair + slot
            for pair in range(pairs)
            for slot in range(whole + (pair in more))
        }

    def seat_order(self, seed):
        """The seats in the order they sit down in the round of `seed`."""
        homes = list(self.seats)
        _draw(seed, "seats").shuffle(homes)
        return homes

    def play(self, *, commuters, share, seed, way_home=True):
        """Play one round and read it. Nothing it writes is kept."""
        with transaction.atomic():
            measure = self._play(commuters, share, seed, way_home)
            transaction.set_rollback(True)
        return measure

    def _play(self, commuters, share, seed, way_home):
        from game.simulation import TrafficSimulator

        session = GameSession.objects.create(
            game_host=self.host,
            game_name="Kalibrierung",
            game_map=self.game_map,
            active_map_version=self.version,
            max_players=len(self.seats),
            agent_per_player=self.per_seat,
            people_per_agent=self.people_per_gruppe(commuters),
            max_rounds=calibration.DEFAULT_MAX_ROUNDS,
            max_CO2_level=10**9,
        )
        game_round = GameRound.objects.create(game=session, round_number=1)
        drivers = self.drivers(share, seed)
        view = PlayerMoveView()
        errors = []
        switched = 0

        for number, home in enumerate(self.seat_order(seed), start=1):
            pairs = self.seats[home]
            player = Player.objects.create(game=session, name=f"Wohnort {number}")
            agents = []
            for index in pairs:
                commute = self.commutes[index]
                for slot in range(self.per_pair):
                    wanted = (
                        "car" if index * self.per_pair + slot in drivers else "public"
                    )
                    mode = self._mode(commute, wanted)
                    switched += mode != wanted
                    there, back = commute["there"][mode], commute["back"][mode]
                    who = f"{commute['home']} → {commute['workplace']}, {mode}"
                    view._check_route(
                        who,
                        there["segments"],
                        commute["home"],
                        "home node",
                        commute["workplace"],
                        "destination",
                        errors,
                    )
                    view._check_route(
                        f"{who} (way home)",
                        back["segments"],
                        commute["workplace"],
                        "destination",
                        commute["home"],
                        "home node",
                        errors,
                    )
                    agents.append(
                        {
                            "id": len(agents) + 1,
                            "transport_mode": mode,
                            "optimization": (
                                self.car_optimization if mode == "car" else None
                            ),
                            "route": there,
                            "return_route": back,
                        }
                    )

            serializer = PlayerMoveWithRoutesInputSerializer(data={"agents": agents})
            if not serializer.is_valid():
                raise RoutesRefused([f"Wohnort {number}: {serializer.errors}"])
            validated = serializer.validated_data["agents"]  # type: ignore
            if not way_home:
                validated = [
                    {k: v for k, v in agent.items() if k != "return_route"}
                    for agent in validated
                ]
            move = PlayerMove.objects.create(
                session_round=game_round, player=player, action="route_submission"
            )
            view._store_routes(move, validated)

        if errors:
            raise RoutesRefused(errors)

        simulator = TrafficSimulator(game_round, scale=self.game_map.scale, seed=seed)
        result = simulator.run_simulation()
        result.refresh_from_db()
        rows = list(result.agent_results.select_related("agent_route"))
        car = [
            r
            for r in rows
            if r.agent_route.transport_mode == AgentRoute.TransportMode.CAR
        ]
        pt = [
            r
            for r in rows
            if r.agent_route.transport_mode == AgentRoute.TransportMode.PUBLIC
        ]
        passes = [simulator] + ([simulator.home_pass] if simulator.home_pass else [])

        return RoundMeasure(
            total_kg=result.total_co2_g / 1000,
            car_kg=sum(r.total_co2_g for r in car) / 1000,
            cost_eur=result.total_cost_eur,
            car_km=sum(r.agent_route.total_distance_m for r in car) / 1000,
            car_hours=sum(r.mean_trip_time_min for r in car) / 60,
            car_trip_min=_mean([r.mean_trip_time_min for r in car]),
            # The column defaults to zero, so a morning alone would read as a
            # way home that took no time.
            car_return_min=(
                _mean([r.mean_return_time_min for r in car]) if way_home else None
            ),
            car_delay_min=_mean([r.congestion_delay_min for r in car]),
            pt_trip_min=_mean([r.mean_trip_time_min for r in pt]),
            pt_wait_min=_mean([r.wait_time_min for r in pt]),
            not_home=sum(
                p.non_arrivals["unfinished"] + p.non_arrivals["stranded"]
                for p in passes
            ),
            switched=switched,
            people=self.gruppen * session.people_per_agent,
        )

    @staticmethod
    def _mode(commute, wanted):
        """The mode a Gruppe takes: the one it was given, if that has a way.

        A pair with no car route rides, one with no line drives — a class
        would have no other choice either. A pair with neither cannot be
        played, and `check_map` says why.
        """
        other = "public" if wanted == "car" else "car"
        for mode in (wanted, other):
            leg_there = commute["there"].get(mode) or {}
            leg_back = commute["back"].get(mode) or {}
            if "segments" in leg_there and "segments" in leg_back:
                return mode
        raise RoutesRefused(
            [
                f"Kein Weg mit Auto oder Bus und Bahn von {commute['home']} "
                f"nach {commute['workplace']} und zurück."
            ]
        )
