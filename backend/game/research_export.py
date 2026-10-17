"""The research data of finished games, as one sqlite file.

Only games that are over and anonymised leave: a game inside its grace period
is still being debriefed and still carries its players' names. Players are
numbers (their pk), never names. What a host or a player wrote as free text
(the game's name, the chat, a Pendlertyp the host made up, the study's label)
does not leave, and neither does anything of the host's account. A study leaves
as a number its games share.

One reader of the models, one schema: `SCHEMA` below is the file's contract, and
`.agents/skills/extract-data/SKILL.md` describes it in words.
"""

import sqlite3
from pathlib import Path

from game.models import (
    AgentSimulationResult,
    GameRound,
    GameSession,
    MapVersionVote,
    Persona,
    Player,
    StalemateVote,
)
from maps.models import MapVersion, Node

OWN_PERSONA = "eigener Typ"

SCHEMA = """
CREATE TABLE game (
    id INTEGER PRIMARY KEY,
    map_id INTEGER,
    map_name TEXT,
    ended_on TEXT NOT NULL,
    end_reason TEXT,
    max_rounds INTEGER NOT NULL,
    rounds_played INTEGER NOT NULL,
    seats INTEGER NOT NULL,
    gruppen_per_seat INTEGER NOT NULL,
    people_per_agent INTEGER NOT NULL,
    co2_kg_per_person REAL,
    max_co2_kg INTEGER NOT NULL,
    timetable_factor REAL NOT NULL,
    balanced_deal INTEGER NOT NULL,
    map_updates INTEGER NOT NULL,
    co2_hidden INTEGER NOT NULL,
    study INTEGER
);
CREATE TABLE player (
    id INTEGER PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES game(id),
    left_early INTEGER NOT NULL
);
CREATE TABLE map_version (
    id INTEGER PRIMARY KEY,
    map_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    is_base INTEGER NOT NULL,
    poll_text TEXT NOT NULL,
    revert_poll_text TEXT NOT NULL,
    source_version_id INTEGER
);
CREATE TABLE node (
    id INTEGER PRIMARY KEY,
    map_id INTEGER NOT NULL,
    name TEXT,
    x REAL NOT NULL,
    y REAL NOT NULL
);
CREATE TABLE round (
    id INTEGER PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES game(id),
    round_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    total_co2_g REAL,
    total_cost_eur REAL,
    network_co2_g REAL,
    network_cost_eur REAL,
    stalemate_count INTEGER NOT NULL,
    winning_version_id INTEGER,
    tie INTEGER,
    forced INTEGER
);
CREATE TABLE ballot_option (
    round_id INTEGER NOT NULL REFERENCES round(id),
    version_id INTEGER NOT NULL,
    votes INTEGER
);
CREATE TABLE vote (
    round_id INTEGER NOT NULL REFERENCES round(id),
    player_id INTEGER NOT NULL REFERENCES player(id),
    version_id INTEGER
);
CREATE TABLE stichwahl_vote (
    round_id INTEGER NOT NULL REFERENCES round(id),
    player_id INTEGER NOT NULL REFERENCES player(id),
    want_revote INTEGER NOT NULL
);
CREATE TABLE gruppe_round (
    round_id INTEGER NOT NULL REFERENCES round(id),
    player_id INTEGER NOT NULL REFERENCES player(id),
    gruppe INTEGER NOT NULL,
    pendlertyp TEXT,
    home_node_id INTEGER,
    destination_node_id INTEGER,
    mode TEXT NOT NULL,
    optimization TEXT,
    distance_m REAL,
    trip_min REAL NOT NULL,
    return_min REAL NOT NULL,
    cost_eur REAL NOT NULL,
    paid_eur REAL NOT NULL,
    co2_g_per_person REAL NOT NULL,
    congestion_delay_min REAL NOT NULL,
    wait_time_min REAL NOT NULL
);
"""


def exportable_games():
    """Ended and anonymised: the only games that leave."""
    return GameSession.objects.filter(
        ended_at__isnull=False, anonymised_at__isnull=False
    ).order_by("pk")


def _study_numbers(games: list[GameSession]) -> dict[str, int]:
    """1, 2, … per label, in the order its first game ended up in the file.

    The label is free text the host wrote, so it stays on the instance; the
    number is only good for telling which games of this file belong together.
    """
    numbers: dict[str, int] = {}
    for game in games:
        if game.study and game.study not in numbers:
            numbers[game.study] = len(numbers) + 1
    return numbers


def _persona_names(game: GameSession, standard_names: set[str]) -> dict[int, str]:
    # A Pendlertyp the host wrote is free text; only the standard ones keep
    # their name.
    return {
        p.pk: p.name if p.name in standard_names else OWN_PERSONA
        for p in Persona.objects.filter(game=game)
    }


def export_research_data(path) -> dict[str, int]:
    """Write the file at `path` (replacing one) and return the rows per table."""
    path = Path(path)
    if path.exists():
        path.unlink()
    standard_names = set(
        Persona.objects.filter(game__isnull=True).values_list("name", flat=True)
    )
    games = list(exportable_games().select_related("game_map"))
    studies = _study_numbers(games)
    node_ids: set[int] = set()
    map_ids: set[int] = set()

    db = sqlite3.connect(path)
    try:
        db.executescript(SCHEMA)
        for game in games:
            if game.game_map_id:
                map_ids.add(game.game_map_id)
            players = list(Player.objects.filter(game=game).without_host_rows())
            rounds = list(
                GameRound.objects.filter(game=game).select_related("simulation")
            )
            db.execute(
                "INSERT INTO game VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    game.pk,
                    game.game_map_id,
                    game.game_map.name if game.game_map else None,
                    game.ended_at.date().isoformat(),  # type: ignore
                    game.end_reason,
                    game.max_rounds,
                    sum(1 for r in rounds if r.status == GameRound.Status.COMPLETED),
                    len(players),
                    game.agent_per_player,
                    game.people_per_agent,
                    (
                        float(game.co2_kg_per_person)
                        if game.co2_kg_per_person is not None
                        else None
                    ),
                    game.max_CO2_level,
                    game.timetable_factor,
                    int(game.balanced_deal),
                    int(game.map_updates),
                    int(game.hide_co2),
                    studies.get(game.study),
                ),
            )
            for player in players:
                db.execute(
                    "INSERT INTO player VALUES (?,?,?)",
                    (player.pk, game.pk, int(player.left_at is not None)),
                )
            persona_names = _persona_names(game, standard_names)
            agents = {
                player.pk: {
                    a["id"]: a
                    for a in (player.agent_assignments or {}).get("agents", [])
                }
                for player in players
            }
            for game_round in rounds:
                sim = getattr(game_round, "simulation", None)
                vote = game_round.vote_result or {}
                db.execute(
                    "INSERT INTO round VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        game_round.pk,
                        game.pk,
                        game_round.round_number,
                        game_round.status,
                        sim.total_co2_g if sim else None,
                        sim.total_cost_eur if sim else None,
                        sim.network_co2_g if sim else None,
                        sim.network_cost_eur if sim else None,
                        game_round.stalemate_count,
                        vote.get("winning_version_id"),
                        int(vote["tie"]) if "tie" in vote else None,
                        int(vote["forced"]) if "forced" in vote else None,
                    ),
                )
                counts = {
                    row["version_id"]: row["count"]
                    for row in vote.get("vote_counts", [])
                }
                for option in vote.get("options", []):
                    db.execute(
                        "INSERT INTO ballot_option VALUES (?,?,?)",
                        (
                            game_round.pk,
                            option["version_id"],
                            counts.get(option["version_id"]),
                        ),
                    )
                for v in MapVersionVote.objects.filter(
                    game_round=game_round, player__in=players
                ):
                    db.execute(
                        "INSERT INTO vote VALUES (?,?,?)",
                        (game_round.pk, v.player_id, v.map_version_id),  # type: ignore
                    )
                for s in StalemateVote.objects.filter(
                    game_round=game_round, player__in=players
                ):
                    db.execute(
                        "INSERT INTO stichwahl_vote VALUES (?,?,?)",
                        (game_round.pk, s.player_id, int(s.want_revote)),  # type: ignore
                    )
                if sim is None:
                    continue
                results = AgentSimulationResult.objects.filter(
                    simulation=sim, agent_route__player_move__player__in=players
                ).select_related("agent_route__player_move")
                for result in results:
                    route = result.agent_route
                    player_id = route.player_move.player_id  # type: ignore
                    agent = agents.get(player_id, {}).get(route.agent_id, {})
                    for key in ("home_node", "destination_node"):
                        if agent.get(key):
                            node_ids.add(agent[key])
                    db.execute(
                        "INSERT INTO gruppe_round VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            game_round.pk,
                            player_id,
                            route.agent_id,
                            persona_names.get(agent.get("persona")),
                            agent.get("home_node"),
                            agent.get("destination_node"),
                            route.transport_mode,
                            route.optimization,
                            route.total_distance_m,
                            result.mean_trip_time_min,
                            result.mean_return_time_min,
                            result.mean_cost_eur,
                            result.mean_paid_eur,
                            result.total_co2_g / (game.people_per_agent or 1),
                            result.congestion_delay_min,
                            result.wait_time_min,
                        ),
                    )
        for version in MapVersion.objects.filter(game_map__in=map_ids).order_by("pk"):
            db.execute(
                "INSERT INTO map_version VALUES (?,?,?,?,?,?,?)",
                (
                    version.pk,
                    version.game_map_id,  # type: ignore
                    version.name,
                    int(version.base_version),
                    version.poll_text,
                    version.revert_poll_text,
                    version.source_version_id,  # type: ignore
                ),
            )
        for node in Node.objects.filter(pk__in=node_ids).order_by("pk"):
            db.execute(
                "INSERT INTO node VALUES (?,?,?,?,?)",
                (node.pk, node.game_map_id, node.name, node.x_position, node.y_position),  # type: ignore
            )
        db.commit()
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "game",
                "player",
                "round",
                "ballot_option",
                "vote",
                "stichwahl_vote",
                "gruppe_round",
                "map_version",
                "node",
            )
        }
    finally:
        db.close()
