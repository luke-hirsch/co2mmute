import json
import tempfile
import zipfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from game.models import Player
from game.tests._helpers import create_game_map, create_game_session, create_host, muted
from game.tests.test_research_export import Export

from studies.models import (
    Participant,
    ResearchNote,
    Study,
    StudyGame,
    StudySeat,
)


class StudyExportTests(TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.out = Path(self.dir.name) / "research.zip"
        self.staff = create_host("staff-konto", is_staff=True)
        self.map = create_game_map()

    def finished_game(self, anonymised=True):
        game = create_game_session(self.staff, game_map=self.map, game_name="Geheim")
        type(game).objects.filter(pk=game.pk).update(
            ended_at=timezone.now(),
            anonymised_at=timezone.now() if anonymised else None,
        )
        return game

    def seat(self, study, code, game):
        participant, _ = Participant.objects.get_or_create(study=study, code=code)
        player = Player.objects.create(game=game, name="Spieler 1")
        StudySeat.objects.create(participant=participant, player=player, game=game)
        return player

    def export(self):
        with muted():
            call_command("export_research_data", str(self.out), stdout=StringIO())
        return Export(self.out)

    def test_a_study_with_an_exported_game_leaves_with_its_seats_and_notes(self):
        study = Study.objects.create(
            name="Sommer", description="Zwei Klassen.", created_by=self.staff
        )
        done = self.finished_game()
        grace = self.finished_game(anonymised=False)
        for game in (done, grace):
            StudyGame.objects.create(study=study, game=game)
        player = self.seat(study, "ABCDEFGH", done)
        self.seat(study, "ABCDEFGH", grace)
        note = ResearchNote.objects.create(
            study=study,
            author=self.staff,
            text="Laut.",
            about_date="2026-10-12",
            meta={"Ort": "Aula", "Schüler": 24},
        )
        note.games.set([done, grace])

        data = self.export()

        self.assertEqual(
            [(r["name"], r["description"]) for r in data.rows("study")],
            [("Sommer", "Zwei Klassen.")],
        )
        self.assertEqual(
            [r["game_id"] for r in data.rows("study_game")], [str(done.pk)]
        )
        self.assertEqual(
            [(r["code"], r["game_id"], r["player_id"]) for r in data.rows("study_seat")],
            [("ABCDEFGH", str(done.pk), str(player.pk))],
        )
        (row,) = data.rows("study_note")
        self.assertEqual((row["about_date"], row["text"]), ("2026-10-12", "Laut."))
        self.assertRegex(row["created_on"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(json.loads(row["meta"]), {"Ort": "Aula", "Schüler": 24})
        self.assertEqual(
            [r["game_id"] for r in data.rows("study_note_game")], [str(done.pk)]
        )

    def test_nothing_of_the_author_or_the_games_names_leaves(self):
        study = Study.objects.create(name="Sommer", created_by=self.staff)
        game = self.finished_game()
        StudyGame.objects.create(study=study, game=game)
        ResearchNote.objects.create(study=study, author=self.staff, text="x")
        self.export()

        with zipfile.ZipFile(self.out) as archive:
            raw = b"".join(archive.read(n) for n in archive.namelist())
        self.assertNotIn(b"staff-konto", raw)
        self.assertNotIn(b"Geheim", raw)
        data = Export(self.out)
        for table in ("study", "study_note", "study_seat"):
            columns = set(data.columns(table))
            self.assertFalse(columns & {"author", "author_id", "user", "created_by"})

    def test_a_study_without_an_exported_game_stays_home(self):
        study = Study.objects.create(name="Leer")
        StudyGame.objects.create(study=study, game=self.finished_game(anonymised=False))
        ResearchNote.objects.create(study=study, text="x")

        data = self.export()

        for table in ("study", "study_game", "study_seat", "study_note"):
            self.assertEqual(data.rows(table), [])

    def test_the_tables_exist_even_with_no_study(self):
        names = set(self.export().tables())
        self.assertTrue({"study", "study_game", "study_seat", "study_note"} <= names)

    def test_the_readme_knows_the_study_tables(self):
        self.export()
        with zipfile.ZipFile(self.out) as archive:
            readme = archive.read("README.txt").decode("utf-8")
        self.assertIn("study_seat.csv", readme)
        self.assertIn("never whose it is", readme)
