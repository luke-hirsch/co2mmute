"""The research data of finished games, as CSV files in one zip.

Only games that are over and anonymised leave: a game inside its grace period
is still being debriefed and still carries its players' names. Players are
numbers (their pk), never names. What a host or a player wrote as free text
(the game's name, the chat, a Pendlertyp the host made up) does not leave, and
neither does anything of the host's account. Moments are seconds since a start
(the game's opening, the round's result), never a clock time.

One reader of the models, one schema: `SCHEMA` below is the contract. The
tables are filled into an in-memory sqlite database, one place to keep the
columns and the order, and each leaves as one CSV file beside a `README.txt`
that says what the columns are. `.agents/skills/extract-data/SKILL.md`
describes the tables in words.
"""

import csv
import io
import json
import re
import sqlite3
import zipfile
from collections.abc import Callable
from pathlib import Path

from django.utils import timezone

from game.models import (
    AgentRoute,
    AgentSimulationResult,
    GameRound,
    GameSession,
    MapVersionVote,
    Persona,
    Player,
    RouteSegment,
    StalemateVote,
)
from maps.models import BusLine, Edge, MapVersion, Node, TrainLine

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
    co2_hidden INTEGER NOT NULL
);
CREATE TABLE player (
    id INTEGER PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES game(id),
    joined_s INTEGER,
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
CREATE TABLE edge (
    id INTEGER PRIMARY KEY,
    map_id INTEGER NOT NULL,
    start_node_id INTEGER NOT NULL REFERENCES node(id),
    end_node_id INTEGER NOT NULL REFERENCES node(id),
    name TEXT,
    length_m REAL NOT NULL
);
CREATE TABLE pt_line (
    kind TEXT NOT NULL,
    id INTEGER NOT NULL,
    map_id INTEGER NOT NULL,
    name TEXT NOT NULL
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
    version_id INTEGER,
    voted_s INTEGER
);
CREATE TABLE stichwahl_vote (
    round_id INTEGER NOT NULL REFERENCES round(id),
    player_id INTEGER NOT NULL REFERENCES player(id),
    want_revote INTEGER NOT NULL,
    voted_s INTEGER
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
CREATE TABLE route_segment (
    round_id INTEGER NOT NULL REFERENCES round(id),
    player_id INTEGER NOT NULL REFERENCES player(id),
    gruppe INTEGER NOT NULL,
    direction TEXT NOT NULL,
    step INTEGER NOT NULL,
    mode TEXT NOT NULL,
    edge_id INTEGER NOT NULL REFERENCES edge(id),
    pt_line_id INTEGER
);
CREATE TABLE replay_round (
    round_id INTEGER PRIMARY KEY REFERENCES round(id),
    format_version INTEGER,
    people_per_dot REAL,
    tick_duration_min INTEGER,
    end_min REAL,
    home_start_min REAL,
    not_home_unfinished INTEGER,
    not_home_stranded INTEGER
);
CREATE TABLE replay_dot (
    round_id INTEGER NOT NULL REFERENCES round(id),
    dot_id INTEGER NOT NULL,
    pass TEXT NOT NULL,
    player_id INTEGER REFERENCES player(id),
    gruppe INTEGER,
    line TEXT,
    mode TEXT,
    wants_min REAL,
    ending TEXT,
    legs TEXT NOT NULL
);
"""

# What each table is, for the README inside the zip; `*` names a column worth a
# note. Tables another app registers bring their own (`register_tables`).
NOTES: dict[str, tuple[str, dict[str, str]]] = {
    "game": (
        "one row per exported game",
        {
            "ended_on": "the day the game ended, no time",
            "co2_hidden": "1: the class saw no CO2 figure or budget until the summary",
            "timetable_factor": "the share of the timetable the class paid (CO2 and cost)",
        },
    ),
    "player": (
        "one row per seat, by number only",
        {"joined_s": "seconds from the game being opened to the seat joining"},
    ),
    "round": (
        "one row per round",
        {
            "total_co2_g": "the players' CO2 in grams, there and back",
            "network_co2_g": "the CO2 of the lines nobody rode",
            "winning_version_id": "the map version the vote chose; empty: left as it was",
        },
    ),
    "ballot_option": ("one row per option on a round's ballot", {}),
    "vote": (
        "one row per seat and round",
        {
            "version_id": "the version voted for; empty: leave the map as it is",
            "voted_s": "seconds from the round's result being ready to the vote",
        },
    ),
    "stichwahl_vote": (
        "one row per seat and round: another vote after a tie?",
        {"voted_s": "seconds from the round's result being ready to the vote"},
    ),
    "map_version": (
        "one row per version of an exported game's map",
        {"poll_text": "what the version changes, in the words the ballot used"},
    ),
    "node": (
        "the nodes the games used: homes, workplaces, and the ends of streets travelled",
        {"x": "map units, not metres", "y": "map units, not metres"},
    ),
    "edge": (
        "the streets and rails the games travelled, as the segments and the replay name them",
        {"length_m": "the road's length in metres"},
    ),
    "pt_line": (
        "the bus and train lines the games rode",
        {"kind": "bus or train (a tram is a train line); (kind, id) is the key"},
    ),
    "gruppe_round": (
        "one row per Gruppe and round: what its commuters did and cost",
        {
            "gruppe": "1, 2, ... within the seat",
            "pendlertyp": "a standard type's name, or `eigener Typ` for one a host wrote",
            "cost_eur": "the real cost",
            "paid_eur": "what the commuter paid",
            "co2_g_per_person": "one commuter's day; the Gruppe's is that times people_per_agent",
        },
    ),
    "route_segment": (
        "one row per street or rail a Gruppe used in a round: which, not why",
        {
            "direction": "out (to work) or home",
            "step": "0, 1, ... along the route",
            "mode": "car, bus, train, bike or walk",
            "pt_line_id": "with mode bus or train: the line, in pt_line",
        },
    ),
    "replay_round": (
        "one row per round with a recording: the recording's frame",
        {
            "end_min": "minutes from the start of the departure window",
            "home_start_min": "where the evening starts on that clock",
            "people_per_dot": "how many people one dot stands for",
        },
    ),
    "replay_dot": (
        "one row per dot of the recording: a sampled person or a line vehicle",
        {
            "pass": "out or home",
            "player_id": "empty for a line vehicle",
            "wants_min": "when this person wanted to leave; the gap to the first leg is the queue at the door",
            "ending": "arrived, stranded or unfinished",
            "legs": (
                "JSON, a list of [kind, ref, from_min, to_min, from_node]: e = crossing "
                "edge ref (see edge), s = waiting at node ref, r = riding the dot "
                "with id ref"
            ),
        },
    ),
}


# Tables other apps add, as (schema, writer). `game` never imports them: an
# optional app registers itself from its AppConfig, and with it switched off
# the zip has no such files at all.
_EXTRA_TABLES: list[tuple[str, Callable]] = []
_EXTRA_NOTES: dict[str, tuple[str, dict[str, str]]] = {}


def register_tables(schema_sql: str, writer: Callable, notes=None) -> None:
    """Add tables to the export: `writer(db, games)` runs after the game tables.

    `games` are the exported ones (ended and anonymised); the writer must leave
    out anything that is not about them. `notes` is `{table: (what it is,
    {column: note})}` for the README. Registering the same writer twice is a
    no-op.
    """
    if all(existing is not writer for _, existing in _EXTRA_TABLES):
        _EXTRA_TABLES.append((schema_sql, writer))
        _EXTRA_NOTES.update(notes or {})


def exportable_games():
    """Ended and anonymised: the only games that leave."""
    return GameSession.objects.filter(
        ended_at__isnull=False, anonymised_at__isnull=False
    ).order_by("pk")


def _persona_names(game: GameSession, standard_names: set[str]) -> dict[int, str]:
    # A Pendlertyp the host wrote is free text; only the standard ones keep
    # their name.
    return {
        p.pk: p.name if p.name in standard_names else OWN_PERSONA
        for p in Persona.objects.filter(game=game)
    }


def _seconds(later, earlier) -> int | None:
    """Whole seconds from `earlier` to `later`, never negative; None if either is."""
    if later is None or earlier is None:
        return None
    return max(0, int((later - earlier).total_seconds()))


def _tables(db) -> list[str]:
    return [
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid"
        )
    ]


def _csv_text(db, table: str) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    cursor = db.execute(f"SELECT * FROM {table} ORDER BY rowid")
    writer.writerow([column[0] for column in cursor.description])
    for row in cursor:
        writer.writerow(["" if value is None else value for value in row])
    return out.getvalue()


_COLUMN = re.compile(r"^\s+(\w+) (INTEGER|REAL|TEXT)\b", re.MULTILINE)


def _readme(db, counts: dict[str, int]) -> str:
    notes = {**NOTES, **_EXTRA_NOTES}
    schemas = {
        row[0]: row[1]
        for row in db.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    }
    lines = [
        "co2mmute: research data of finished games",
        "",
        "One CSV file per table. Only games that are over and anonymised are in it.",
        "Players are numbers, never names. There is no host account, no game name, no",
        "chat, no free text a host or a player wrote. Moments are seconds since a start",
        "(named in the column), never a clock time.",
        "",
        "Format: UTF-8 with a byte-order mark (so Excel on Windows shows the umlauts;",
        "pandas: encoding='utf-8-sig', R: fileEncoding='UTF-8-BOM'), comma-separated,",
        "a point as decimal mark, an empty field is no value (null), 1 and 0 for yes",
        "and no, days as YYYY-MM-DD. The first row is the column names.",
        "",
        "The recording of a round (replay_dot) is one row per dot with its legs as JSON",
        "in one field: a row per leg would be some hundred thousand rows a round, and",
        "one field per round more than a spreadsheet cell holds.",
        "",
    ]
    for table in _tables(db):
        what, columns = notes.get(table, ("", {}))
        lines.append(
            f"{table}.csv  ({counts[table]} rows)" + (f": {what}" if what else "")
        )
        for name, kind in _COLUMN.findall(schemas[table]):
            note = columns.get(name)
            lines.append(f"    {name} ({kind.lower()})" + (f": {note}" if note else ""))
        lines.append("")
    return "\n".join(lines)


def export_research_data(path) -> dict[str, int]:
    """Write the zip at `path` (replacing one) and return the rows per table.

    A directory as `path` gets `research-<date>.zip` inside it.
    """
    path = Path(path)
    if path.is_dir():
        path = path / f"research-{timezone.localdate().isoformat()}.zip"
    if path.exists():
        path.unlink()
    standard_names = set(
        Persona.objects.filter(game__isnull=True).values_list("name", flat=True)
    )
    games = list(exportable_games().select_related("game_map"))
    node_ids: set[int] = set()
    edge_ids: set[int] = set()
    lines: set[tuple[str, int]] = set()
    map_ids: set[int] = set()

    db = sqlite3.connect(":memory:")
    try:
        db.executescript(SCHEMA)
        for schema_sql, _ in _EXTRA_TABLES:
            db.executescript(schema_sql)
        for game in games:
            if game.game_map_id:
                map_ids.add(game.game_map_id)
            players = list(Player.objects.filter(game=game).without_host_rows())
            rounds = list(
                GameRound.objects.filter(game=game).select_related("simulation")
            )
            db.execute(
                "INSERT INTO game VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                ),
            )
            for player in players:
                db.execute(
                    "INSERT INTO player VALUES (?,?,?,?)",
                    (
                        player.pk,
                        game.pk,
                        _seconds(player.joined_at, game.created_at),
                        int(player.left_at is not None),
                    ),
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
                result_ready = sim.completed_at if sim else None
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
                        "INSERT INTO vote VALUES (?,?,?,?)",
                        (
                            game_round.pk,
                            v.player_id,  # type: ignore
                            v.map_version_id,  # type: ignore
                            _seconds(v.voted_at, result_ready),
                        ),
                    )
                for s in StalemateVote.objects.filter(
                    game_round=game_round, player__in=players
                ):
                    db.execute(
                        "INSERT INTO stichwahl_vote VALUES (?,?,?,?)",
                        (
                            game_round.pk,
                            s.player_id,  # type: ignore
                            int(s.want_revote),
                            _seconds(s.voted_at, result_ready),
                        ),
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
                routes = {
                    route.pk: route
                    for route in AgentRoute.objects.filter(
                        player_move__session_round=game_round,
                        player_move__player__in=players,
                    ).select_related("player_move")
                }
                _write_segments(db, game_round, routes, edge_ids, lines)
                _write_replay(db, game_round, sim, routes, edge_ids, node_ids)
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
        for edge in (
            Edge.objects.filter(pk__in=edge_ids)
            .select_related("game_map")
            .order_by("pk")
        ):
            node_ids.update((edge.start_node_id, edge.end_node_id))  # type: ignore
            db.execute(
                "INSERT INTO edge VALUES (?,?,?,?,?,?)",
                (
                    edge.pk,
                    edge.game_map_id,  # type: ignore
                    edge.start_node_id,  # type: ignore
                    edge.end_node_id,  # type: ignore
                    edge.name,
                    edge.length_m(edge.game_map.scale),
                ),
            )
        for kind, model in (("bus", BusLine), ("train", TrainLine)):
            ids = {line_id for k, line_id in lines if k == kind}
            for line in model.objects.filter(pk__in=ids).order_by("pk"):
                db.execute(
                    "INSERT INTO pt_line VALUES (?,?,?,?)",
                    (kind, line.pk, line.game_map_id, line.name),  # type: ignore
                )
        for node in Node.objects.filter(pk__in=node_ids).order_by("pk"):
            db.execute(
                "INSERT INTO node VALUES (?,?,?,?,?)",
                (node.pk, node.game_map_id, node.name, node.x_position, node.y_position),  # type: ignore
            )
        for _, writer in _EXTRA_TABLES:
            writer(db, games)
        db.commit()

        counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in _tables(db)
        }
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.txt", _readme(db, counts).encode("utf-8"))
            for table in _tables(db):
                # The byte-order mark: Excel on Windows reads umlauts only with it.
                archive.writestr(
                    f"{table}.csv", _csv_text(db, table).encode("utf-8-sig")
                )
        return counts
    finally:
        db.close()


def _write_segments(db, game_round, routes, edge_ids, lines) -> None:
    """Which streets and lines each Gruppe used, in order, there and back."""
    segments = RouteSegment.objects.filter(agent_route__in=routes).order_by(
        "agent_route_id", "order"
    )
    for segment in segments:
        route = routes[segment.agent_route_id]  # type: ignore
        edge_ids.add(segment.edge_id)  # type: ignore
        if segment.pt_line_id and segment.mode in ("bus", "train"):
            lines.add((segment.mode, segment.pt_line_id))
        db.execute(
            "INSERT INTO route_segment VALUES (?,?,?,?,?,?,?,?)",
            (
                game_round.pk,
                route.player_move.player_id,
                route.agent_id,
                route.direction,
                segment.order,
                segment.mode,
                segment.edge_id,  # type: ignore
                segment.pt_line_id,
            ),
        )


def _write_replay(db, game_round, sim, routes, edge_ids, node_ids) -> None:
    """The round's recording: its frame, and one row per dot."""
    replay = sim.replay
    if not replay:
        return
    endings = replay.get("endings") or {}
    db.execute(
        "INSERT INTO replay_round VALUES (?,?,?,?,?,?,?,?)",
        (
            game_round.pk,
            replay.get("version"),
            replay.get("people_per_dot"),
            replay.get("tick_duration_min"),
            replay.get("end_min"),
            replay.get("home_start_min"),
            endings.get("unfinished"),
            endings.get("stranded"),
        ),
    )
    for dot in replay.get("dots", []):
        route = routes.get(dot.get("route"))
        if dot.get("route") is not None and route is None:
            # A dot of a seat that is not exported (the host's own row).
            continue
        for kind, ref, _start, _end, from_node in dot["legs"]:
            if kind == "e" and ref is not None:
                edge_ids.add(ref)
            elif kind == "s" and ref is not None:
                node_ids.add(ref)
            if from_node is not None:
                node_ids.add(from_node)
        db.execute(
            "INSERT INTO replay_dot VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                game_round.pk,
                dot["id"],
                dot.get("pass"),
                route.player_move.player_id if route else None,
                route.agent_id if route else None,
                dot.get("line"),
                dot.get("mode"),
                dot.get("wants"),
                dot.get("end"),
                json.dumps(dot["legs"], separators=(",", ":")),
            ),
        )
