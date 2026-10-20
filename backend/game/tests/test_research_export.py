"""The research export: CSV files in one zip, of ended, anonymised games.

What matters is what does not leave: the player rows here keep their real
names (anonymisation is stamped by hand, not run), so a name in the file is the
export's doing.
"""

import csv
import io
import json
import tempfile
import zipfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from game.models import (
    AgentRoute,
    AgentSimulationResult,
    GameRound,
    GameSession,
    MapVersionVote,
    Persona,
    Player,
    PlayerMove,
    RouteSegment,
    SimulationResult,
    StalemateVote,
)
from maps.models import BusLine, Edge, MapVersion, Node

from ._helpers import (
    TEST_BACKENDS,
    create_game_map,
    create_game_session,
    create_host,
    muted,
)

GAME_NAME = "Klasse 8b, Dienstag"
USERNAME = "frau.beispiel"
EMAIL = "frau.beispiel@schule.example"
NAMES = ("Mia Musterfrau", "Jan Beispiel")


@override_settings(**TEST_BACKENDS)
class ResearchExportTests(TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.out = Path(self.dir.name) / "research.zip"
        self.host = create_host(username=USERNAME, email=EMAIL)
        self.map = create_game_map("Testkarte")
        self.base = MapVersion.objects.create(
            game_map=self.map, name="Basis", base_version=True
        )
        self.bus_lane = MapVersion.objects.create(
            game_map=self.map,
            name="Busspur",
            poll_text="Die Karte soll eine Busspur bekommen.",
        )
        self.home = Node.objects.create(
            game_map=self.map, name="Zuhause", x_position=1, y_position=2
        )
        self.work = Node.objects.create(
            game_map=self.map, name="Arbeit", x_position=3, y_position=4
        )
        self.street = Edge.objects.create(
            game_map=self.map,
            start_node=self.home,
            end_node=self.work,
            name="Hauptstraße",
        )
        self.line = BusLine.objects.create(game_map=self.map, name="M41")
        self.standard = Persona.objects.filter(game=None).first()

    def play(self, anonymised=True, hours_ago=48, **overrides):
        """An ended game of two seats, one round, one Gruppe each, a ballot."""
        with muted():
            game = create_game_session(
                self.host,
                game_name=GAME_NAME,
                game_map=self.map,
                max_rounds=3,
                co2_kg_per_person=2.4,
                people_per_agent=10,
                balanced_deal=True,
                **overrides,
            )
            game_round = GameRound.objects.create(
                game=game,
                round_number=1,
                status=GameRound.Status.COMPLETED,
                stalemate_count=1,
                vote_result={
                    "options": [
                        {"version_id": self.bus_lane.pk, "version_name": "Busspur"}
                    ],
                    "vote_counts": [
                        {
                            "version_id": self.bus_lane.pk,
                            "version_name": "Busspur",
                            "count": 1,
                        }
                    ],
                    "winning_version_id": self.bus_lane.pk,
                    "tie": False,
                    "forced": False,
                },
            )
            sim = SimulationResult.objects.create(
                game_round=game_round,
                status=SimulationResult.Status.COMPLETED,
                total_co2_g=500.0,
                total_cost_eur=12.0,
                network_co2_g=100.0,
                network_cost_eur=2.0,
                completed_at=timezone.now(),
            )
            routes = []
            own = Persona.objects.create(game=game, name="Mias Lieblingstyp")
            copy = Persona.objects.create(game=game, name=self.standard.name)
            for i, name in enumerate(NAMES):
                player = Player.objects.create(
                    game=game,
                    name=name,
                    agent_assignments={
                        "agents": [
                            {
                                "id": 1,
                                "home_node": self.home.pk,
                                "destination_node": self.work.pk,
                                "persona": own.pk if i else copy.pk,
                            }
                        ]
                    },
                )
                move = PlayerMove.objects.create(
                    session_round=game_round, player=player, action="route_submission"
                )
                route = AgentRoute.objects.create(
                    player_move=move,
                    agent_id=1,
                    transport_mode="bike" if i else "car",
                    total_distance_m=1500.0,
                    estimated_time_min=15.0,
                )
                RouteSegment.objects.create(
                    agent_route=route,
                    order=0,
                    edge=self.street,
                    mode="bus" if i else "car",
                    pt_line_id=self.line.pk if i else None,
                )
                routes.append(route)
                AgentSimulationResult.objects.create(
                    simulation=sim,
                    agent_route=route,
                    mean_trip_time_min=14.0,
                    mean_return_time_min=16.0,
                    mean_cost_eur=1.5,
                    mean_paid_eur=1.0,
                    total_co2_g=250.0,
                )
                MapVersionVote.objects.create(
                    game_round=game_round,
                    player=player,
                    map_version=self.bus_lane if i else None,
                )
                StalemateVote.objects.create(
                    game_round=game_round, player=player, want_revote=bool(i)
                )
        sim.replay = {
            "version": 2,
            "people_per_dot": 10.0,
            "tick_duration_min": 5,
            "end_min": 31.5,
            "home_start_min": 1000.0,
            "endings": {"unfinished": 0, "stranded": 1},
            "dots": [
                {
                    "id": 0,
                    "pass": "out",
                    "route": routes[0].pk,
                    "agent": 1,
                    "line": None,
                    "mode": "car",
                    "wants": 4.5,
                    "legs": [["e", self.street.pk, 5.0, 9.0, self.home.pk]],
                    "end": "arrived",
                },
                {
                    "id": 1,
                    "pass": "out",
                    "route": None,
                    "agent": None,
                    "line": "M41",
                    "mode": "bus",
                    "wants": 0.0,
                    "legs": [["s", self.work.pk, 0.0, 3.0, None]],
                    "end": "arrived",
                },
            ],
        }
        sim.save()
        # Moments leave as seconds since a start: joining after the game was
        # opened, a vote after the round's result was ready.
        opened = game.created_at
        ready = sim.completed_at
        Player.objects.filter(game=game).update(
            joined_at=opened + timezone.timedelta(seconds=90)
        )
        MapVersionVote.objects.filter(game_round=game_round).update(
            voted_at=ready + timezone.timedelta(seconds=40)
        )
        StalemateVote.objects.filter(game_round=game_round).update(
            voted_at=ready + timezone.timedelta(seconds=75)
        )
        GameSession.objects.filter(pk=game.pk).update(
            ended_at=timezone.now() - timezone.timedelta(hours=hours_ago),
            end_reason="max_rounds",
            anonymised_at=timezone.now() if anonymised else None,
        )
        return game

    def export(self):
        with muted():
            call_command("export_research_data", str(self.out), stdout=StringIO())
        return Export(self.out)

    def count(self, export, table):
        return len(export.rows(table))

    def export_after_play(self):
        self.play()
        return self.export()

    def test_an_ended_anonymised_game_is_exported_with_its_counts(self):
        game = self.play()
        data = self.export()

        self.assertEqual(self.count(data, "game"), 1)
        self.assertEqual(self.count(data, "player"), 2)
        self.assertEqual(self.count(data, "round"), 1)
        self.assertEqual(self.count(data, "gruppe_round"), 2)
        self.assertEqual(self.count(data, "vote"), 2)
        self.assertEqual(self.count(data, "stichwahl_vote"), 2)
        self.assertEqual(self.count(data, "ballot_option"), 1)
        self.assertEqual(self.count(data, "map_version"), 2)
        # home, workplace: the edge's ends are those two nodes as well.
        self.assertEqual(self.count(data, "node"), 2)
        row = data.rows("game")[0]
        self.assertEqual(
            {
                k: row[k]
                for k in (
                    "id",
                    "map_name",
                    "max_rounds",
                    "rounds_played",
                    "seats",
                    "people_per_agent",
                    "co2_kg_per_person",
                    "balanced_deal",
                    "end_reason",
                )
            },
            {
                "id": str(game.pk),
                "map_name": "Testkarte",
                "max_rounds": "3",
                "rounds_played": "1",
                "seats": "2",
                "people_per_agent": "10",
                "co2_kg_per_person": "2.4",
                "balanced_deal": "1",
                "end_reason": "max_rounds",
            },
        )

    def test_the_zip_is_one_csv_per_table_and_a_readme(self):
        self.play()
        self.export()

        with zipfile.ZipFile(self.out) as archive:
            names = set(archive.namelist())

        self.assertEqual(
            names,
            {"README.txt"}
            | {
                f"{table}.csv"
                for table in (
                    "game",
                    "player",
                    "map_version",
                    "node",
                    "edge",
                    "pt_line",
                    "round",
                    "ballot_option",
                    "vote",
                    "stichwahl_vote",
                    "gruppe_round",
                    "route_segment",
                    "replay_round",
                    "replay_dot",
                )
            }
            | {n for n in names if n.startswith("study")},
        )

    def test_the_csv_is_utf8_with_a_bom_and_a_point_for_decimals(self):
        self.play()
        self.export()

        with zipfile.ZipFile(self.out) as archive:
            raw = archive.read("game.csv")
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        text = raw.decode("utf-8-sig")
        self.assertTrue(text.startswith("id,map_id,map_name,"))
        self.assertIn(",2.4,", text)

    def test_the_readme_names_every_table_and_column_and_the_format(self):
        self.play()
        self.export()

        with zipfile.ZipFile(self.out) as archive:
            readme = archive.read("README.txt").decode("utf-8")
            for name in archive.namelist():
                if not name.endswith(".csv"):
                    continue
                self.assertIn(name, readme)
                columns = (
                    archive.read(name).decode("utf-8-sig").splitlines()[0].split(",")
                )
                for column in columns:
                    self.assertIn(f"    {column} (", readme, f"{name}: {column}")
        self.assertIn("UTF-8 with a byte-order mark", readme)

    def test_whether_the_co2_was_hidden_leaves(self):
        hidden = self.play(hide_co2=True)
        shown = self.play()

        rows = {r["id"]: r["co2_hidden"] for r in self.export().rows("game")}

        self.assertEqual(rows, {str(hidden.pk): "1", str(shown.pk): "0"})

    def test_a_game_inside_the_grace_period_is_left_out(self):
        self.play(anonymised=False, hours_ago=1)

        self.assertEqual(self.count(self.export(), "game"), 0)

    def test_an_ended_game_not_yet_anonymised_is_left_out(self):
        self.play(anonymised=False, hours_ago=48)

        self.assertEqual(self.count(self.export(), "game"), 0)

    def test_a_running_game_is_left_out(self):
        game = self.play()
        GameSession.objects.filter(pk=game.pk).update(ended_at=None)

        self.assertEqual(self.count(self.export(), "game"), 0)

    def test_a_gruppe_keeps_its_mode_cost_time_and_co2_per_person(self):
        rows = self.export_after_play().rows("gruppe_round")
        picked = sorted(
            (
                r["mode"],
                r["trip_min"],
                r["return_min"],
                r["cost_eur"],
                r["paid_eur"],
                r["co2_g_per_person"],
            )
            for r in rows
        )

        self.assertEqual(
            picked,
            [
                ("bike", "14.0", "16.0", "1.5", "1.0", "25.0"),
                ("car", "14.0", "16.0", "1.5", "1.0", "25.0"),
            ],
        )

    def test_a_pendlertyp_the_host_wrote_leaves_as_eigener_typ(self):
        rows = self.export_after_play().rows("gruppe_round")

        self.assertEqual(
            sorted(r["pendlertyp"] for r in rows),
            sorted([self.standard.name, "eigener Typ"]),
        )

    def test_the_ballot_and_the_votes_are_there(self):
        data = self.export_after_play()

        self.assertEqual(
            [(r["version_id"], r["votes"]) for r in data.rows("ballot_option")],
            [(str(self.bus_lane.pk), "1")],
        )
        self.assertEqual(
            sorted(r["version_id"] for r in data.rows("vote")),
            ["", str(self.bus_lane.pk)],
        )
        busspur = [r for r in data.rows("map_version") if r["name"] == "Busspur"]
        self.assertEqual(
            busspur[0]["poll_text"], "Die Karte soll eine Busspur bekommen."
        )

    def test_a_route_leaves_as_one_row_per_segment(self):
        data = self.export_after_play()

        rows = data.rows("route_segment")

        self.assertEqual(len(rows), 2)
        by_mode = {r["mode"]: r for r in rows}
        self.assertEqual(
            {
                "round_id": by_mode["bus"]["round_id"],
                "gruppe": by_mode["bus"]["gruppe"],
                "direction": by_mode["bus"]["direction"],
                "step": by_mode["bus"]["step"],
                "edge_id": by_mode["bus"]["edge_id"],
                "pt_line_id": by_mode["bus"]["pt_line_id"],
            },
            {
                "round_id": data.rows("round")[0]["id"],
                "gruppe": "1",
                "direction": "out",
                "step": "0",
                "edge_id": str(self.street.pk),
                "pt_line_id": str(self.line.pk),
            },
        )
        self.assertEqual(by_mode["car"]["pt_line_id"], "")

    def test_the_streets_and_lines_a_route_names_are_in_the_file(self):
        data = self.export_after_play()

        edge = data.rows("edge")[0]
        self.assertEqual(
            (edge["id"], edge["name"], edge["start_node_id"], edge["end_node_id"]),
            (
                str(self.street.pk),
                "Hauptstraße",
                str(self.home.pk),
                str(self.work.pk),
            ),
        )
        self.assertEqual(
            [(r["kind"], r["id"], r["name"]) for r in data.rows("pt_line")],
            [("bus", str(self.line.pk), "M41")],
        )

    def test_when_a_seat_joined_and_voted_is_seconds_since_a_start(self):
        data = self.export_after_play()

        self.assertEqual({r["joined_s"] for r in data.rows("player")}, {"90"})
        self.assertEqual({r["voted_s"] for r in data.rows("vote")}, {"40"})
        self.assertEqual({r["voted_s"] for r in data.rows("stichwahl_vote")}, {"75"})

    def test_the_replay_is_a_frame_per_round_and_a_row_per_dot(self):
        data = self.export_after_play()

        (frame,) = data.rows("replay_round")
        self.assertEqual(
            (
                frame["round_id"],
                frame["people_per_dot"],
                frame["end_min"],
                frame["home_start_min"],
                frame["not_home_stranded"],
            ),
            (data.rows("round")[0]["id"], "10.0", "31.5", "1000.0", "1"),
        )
        dots = {r["dot_id"]: r for r in data.rows("replay_dot")}
        self.assertEqual(set(dots), {"0", "1"})
        self.assertEqual(
            json.loads(dots["0"]["legs"]),
            [["e", self.street.pk, 5.0, 9.0, self.home.pk]],
        )
        self.assertNotEqual(dots["0"]["player_id"], "")
        self.assertEqual(dots["0"]["gruppe"], "1")
        # A line vehicle belongs to no seat.
        self.assertEqual((dots["1"]["player_id"], dots["1"]["line"]), ("", "M41"))

    def test_a_dot_of_the_hosts_own_seat_stays_home(self):
        game = self.play()
        host = Player.objects.create(game=game, name="Leitstelle", user=self.host)
        move = PlayerMove.objects.create(
            session_round=game.rounds.first(), player=host, action="route_submission"
        )
        route = AgentRoute.objects.create(
            player_move=move,
            agent_id=1,
            transport_mode="car",
            total_distance_m=1.0,
            estimated_time_min=1.0,
        )
        sim = game.rounds.first().simulation
        sim.replay["dots"].append(
            {
                "id": 2,
                "pass": "out",
                "route": route.pk,
                "agent": 1,
                "line": None,
                "mode": "car",
                "wants": 1.0,
                "legs": [["e", self.street.pk, 1.0, 2.0, self.home.pk]],
                "end": "arrived",
            }
        )
        sim.save()

        dots = {r["dot_id"] for r in self.export().rows("replay_dot")}

        self.assertEqual(dots, {"0", "1"})

    def test_a_round_without_a_recording_has_no_replay_rows(self):
        game = self.play()
        SimulationResult.objects.filter(game_round__game=game).update(replay=None)

        data = self.export()

        self.assertEqual(self.count(data, "replay_round"), 0)
        self.assertEqual(self.count(data, "replay_dot"), 0)

    def test_nothing_that_identifies_anyone_is_in_the_file(self):
        self.export_after_play()
        with zipfile.ZipFile(self.out) as archive:
            raw = b"".join(archive.read(n) for n in archive.namelist())

        for forbidden in (GAME_NAME, USERNAME, EMAIL, *NAMES, "Mias Lieblingstyp"):
            self.assertNotIn(forbidden.encode(), raw, forbidden)

    def test_no_column_is_one_that_must_not_leave(self):
        data = self.export_after_play()
        banned = {
            "game_name",
            "name",
            "username",
            "email",
            "user",
            "user_id",
            "game_host",
            "player_id_token",
            "game_id_code",
            "game_qr_code",
            "game_password",
            "message",
        }
        for table in data.tables():
            columns = set(data.columns(table))
            if table in ("map_version", "node", "edge", "pt_line"):
                columns -= {"name"}  # the map's own words, not a person's
            if table == "game":
                columns -= {"map_name"}
            if table == "study":
                columns -= {"name"}  # the researchers' own words
            self.assertFalse(columns & banned, table)

    def test_the_game_date_is_a_day_not_a_moment(self):
        (row,) = self.export_after_play().rows("game")

        self.assertRegex(row["ended_on"], r"^\d{4}-\d{2}-\d{2}$")

    def test_a_second_export_replaces_the_file(self):
        self.play()
        self.export()
        data = self.export()

        self.assertEqual(self.count(data, "game"), 1)

    def test_a_directory_gets_a_zip_named_for_the_day(self):
        self.play()
        with muted():
            call_command("export_research_data", self.dir.name, stdout=StringIO())

        names = [p.name for p in Path(self.dir.name).glob("research-*.zip")]
        self.assertEqual(len(names), 1)
        self.assertRegex(names[0], r"^research-\d{4}-\d{2}-\d{2}\.zip$")


class Export:
    """The zip read back: rows as dicts of strings, as a spreadsheet would show them."""

    def __init__(self, path):
        self.path = path

    def tables(self):
        with zipfile.ZipFile(self.path) as archive:
            return [n[:-4] for n in archive.namelist() if n.endswith(".csv")]

    def _reader(self, table):
        with zipfile.ZipFile(self.path) as archive:
            text = archive.read(f"{table}.csv").decode("utf-8-sig")
        return csv.DictReader(io.StringIO(text))

    def rows(self, table):
        return list(self._reader(table))

    def columns(self, table):
        return list(self._reader(table).fieldnames or [])


class ExportSeamTests(TestCase):
    """Other apps add tables through `register_tables`; none registered, none in the zip."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.out = Path(self.dir.name) / "research.zip"

    def tables(self):
        with muted():
            call_command("export_research_data", str(self.out), stdout=StringIO())
        return set(Export(self.out).tables())

    def test_with_nothing_registered_the_zip_has_only_the_game_tables(self):
        from unittest import mock

        from game import research_export

        with mock.patch.object(research_export, "_EXTRA_TABLES", []):
            self.assertEqual(
                self.tables(),
                {
                    "game",
                    "player",
                    "map_version",
                    "node",
                    "edge",
                    "pt_line",
                    "round",
                    "ballot_option",
                    "vote",
                    "stichwahl_vote",
                    "gruppe_round",
                    "route_segment",
                    "replay_round",
                    "replay_dot",
                },
            )

    def test_a_registered_writer_runs_after_the_game_tables_and_is_counted(self):
        from unittest import mock

        from game import research_export

        seen = []

        def writer(db, games):
            seen.append([g.pk for g in games])
            db.execute("INSERT INTO extra VALUES (1)")

        with mock.patch.object(research_export, "_EXTRA_TABLES", []):
            research_export.register_tables("CREATE TABLE extra (n INTEGER);", writer)
            with muted():
                counts = research_export.export_research_data(self.out)

        self.assertEqual(seen, [[]])
        self.assertEqual(counts["extra"], 1)
        self.assertEqual(Export(self.out).rows("extra"), [{"n": "1"}])
