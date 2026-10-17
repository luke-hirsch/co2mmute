"""The research export: a sqlite file of ended, anonymised games.

What matters is what does not leave: the player rows here keep their real
names (anonymisation is stamped by hand, not run), so a name in the file is the
export's doing.
"""

import sqlite3
import tempfile
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
    SimulationResult,
    StalemateVote,
)
from maps.models import MapVersion, Node

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
        self.out = Path(self.dir.name) / "research.sqlite"
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
            )
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
        GameSession.objects.filter(pk=game.pk).update(
            ended_at=timezone.now() - timezone.timedelta(hours=hours_ago),
            end_reason="max_rounds",
            anonymised_at=timezone.now() if anonymised else None,
        )
        return game

    def export(self):
        with muted():
            call_command("export_research_data", str(self.out), stdout=StringIO())
        return sqlite3.connect(self.out)

    def count(self, db, table):
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_an_ended_anonymised_game_is_exported_with_its_counts(self):
        game = self.play()
        db = self.export()

        self.assertEqual(self.count(db, "game"), 1)
        self.assertEqual(self.count(db, "player"), 2)
        self.assertEqual(self.count(db, "round"), 1)
        self.assertEqual(self.count(db, "gruppe_round"), 2)
        self.assertEqual(self.count(db, "vote"), 2)
        self.assertEqual(self.count(db, "stichwahl_vote"), 2)
        self.assertEqual(self.count(db, "ballot_option"), 1)
        self.assertEqual(self.count(db, "map_version"), 2)
        self.assertEqual(self.count(db, "node"), 2)
        row = db.execute(
            "SELECT id, map_name, max_rounds, rounds_played, seats, people_per_agent,"
            " co2_kg_per_person, balanced_deal, end_reason FROM game"
        ).fetchone()
        self.assertEqual(row, (game.pk, "Testkarte", 3, 1, 2, 10, 2.4, 1, "max_rounds"))

    def test_whether_the_co2_was_hidden_leaves(self):
        hidden = self.play(hide_co2=True)
        shown = self.play()

        rows = dict(self.export().execute("SELECT id, co2_hidden FROM game"))

        self.assertEqual(rows, {hidden.pk: 1, shown.pk: 0})

    def test_a_study_leaves_as_a_number_its_games_share_never_as_its_label(self):
        """The label is free text the host wrote, so it stays on the instance."""
        hidden = self.play(hide_co2=True, study="verdeckt-offen-1")
        shown = self.play(study="verdeckt-offen-1")
        other = self.play(study="ausbalanciert")
        alone = self.play()

        rows = dict(self.export().execute("SELECT id, study FROM game"))

        self.assertIsNotNone(rows[hidden.pk])
        self.assertEqual(rows[shown.pk], rows[hidden.pk])
        self.assertIsNotNone(rows[other.pk])
        self.assertNotEqual(rows[other.pk], rows[hidden.pk])
        self.assertIsNone(rows[alone.pk])
        raw = self.out.read_bytes()
        self.assertNotIn(b"verdeckt-offen-1", raw)
        self.assertNotIn(b"ausbalanciert", raw)

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
        db = self.export_after_play()
        rows = db.execute(
            "SELECT mode, trip_min, return_min, cost_eur, paid_eur, co2_g_per_person"
            " FROM gruppe_round ORDER BY mode"
        ).fetchall()

        self.assertEqual(
            rows,
            [("bike", 14.0, 16.0, 1.5, 1.0, 25.0), ("car", 14.0, 16.0, 1.5, 1.0, 25.0)],
        )

    def test_a_pendlertyp_the_host_wrote_leaves_as_eigener_typ(self):
        db = self.export_after_play()
        types = sorted(r[0] for r in db.execute("SELECT pendlertyp FROM gruppe_round"))

        self.assertEqual(types, sorted([self.standard.name, "eigener Typ"]))

    def test_the_ballot_and_the_votes_are_there(self):
        db = self.export_after_play()

        self.assertEqual(
            db.execute("SELECT version_id, votes FROM ballot_option").fetchall(),
            [(self.bus_lane.pk, 1)],
        )
        self.assertEqual(
            sorted(r[0] or 0 for r in db.execute("SELECT version_id FROM vote")),
            [0, self.bus_lane.pk],
        )
        self.assertEqual(
            db.execute(
                "SELECT poll_text FROM map_version WHERE name = 'Busspur'"
            ).fetchone()[0],
            "Die Karte soll eine Busspur bekommen.",
        )

    def test_nothing_that_identifies_anyone_is_in_the_file(self):
        self.export_after_play()
        raw = self.out.read_bytes()

        for forbidden in (GAME_NAME, USERNAME, EMAIL, *NAMES, "Mias Lieblingstyp"):
            self.assertNotIn(forbidden.encode(), raw, forbidden)

    def test_no_column_is_one_that_must_not_leave(self):
        db = self.export_after_play()
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
        for (table,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall():
            columns = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
            if table in ("map_version", "node"):
                columns -= {"name"}  # the map's own words, not a person's
            if table == "game":
                columns -= {"map_name"}
            self.assertFalse(columns & banned, table)

    def test_the_game_date_is_a_day_not_a_moment(self):
        db = self.export_after_play()
        (ended_on,) = db.execute("SELECT ended_on FROM game").fetchone()

        self.assertRegex(ended_on, r"^\d{4}-\d{2}-\d{2}$")

    def test_a_second_export_replaces_the_file(self):
        self.play()
        self.export()
        db = self.export()

        self.assertEqual(self.count(db, "game"), 1)

    def export_after_play(self):
        self.play()
        return self.export()
