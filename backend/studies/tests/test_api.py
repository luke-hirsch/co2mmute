import base64

from django.test import TestCase
from django.utils import timezone
from game.models import Player
from game.seats import CODE_ALPHABET
from game.tests._helpers import create_game_map, create_game_session, create_host

from studies.models import (
    PARTICIPANT_CODE_LENGTH,
    Participant,
    ResearchNote,
    Study,
    StudyGame,
    StudySeat,
)

URL = "/api/studies/"


class StudyApiCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = create_host("staff", is_staff=True)
        cls.host = create_host("host")
        cls.study = Study.objects.create(name="Sommer", created_by=cls.staff)

    def as_staff(self):
        self.client.force_login(self.staff)

    def game(self, **extra):
        return create_game_session(
            self.host, game_map=create_game_map(), game_name="Dienstag", **extra
        )


class PermissionTests(StudyApiCase):
    def test_anonymous_and_a_normal_host_are_refused_everywhere(self):
        paths = [
            URL,
            f"{URL}{self.study.pk}/",
            f"{URL}{self.study.pk}/codes/",
            f"{URL}{self.study.pk}/cards/",
            f"{URL}{self.study.pk}/games/",
            f"{URL}{self.study.pk}/notes/",
        ]
        for who in (None, self.host):
            self.client.logout()
            if who:
                self.client.force_login(who)
            for path in paths:
                self.assertEqual(self.client.get(path).status_code, 403, path)

    def test_a_normal_host_cannot_write(self):
        self.client.force_login(self.host)
        response = self.client.post(URL, {"name": "x"}, content_type="application/json")
        self.assertEqual(response.status_code, 403)


class StudyCrudTests(StudyApiCase):
    def test_create_list_patch(self):
        self.as_staff()
        response = self.client.post(
            URL,
            {"name": "Herbst", "description": "Zwei Klassen"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Study.objects.get(pk=response.json()["id"]).created_by, self.staff
        )

        listing = self.client.get(URL).json()
        self.assertEqual({row["name"] for row in listing}, {"Sommer", "Herbst"})

        patch = self.client.patch(
            f"{URL}{self.study.pk}/",
            {"name": "Winter"},
            content_type="application/json",
        )
        self.assertEqual(patch.status_code, 200)
        self.study.refresh_from_db()
        self.assertEqual(self.study.name, "Winter")

    def test_a_study_needs_a_name(self):
        self.as_staff()
        response = self.client.post(URL, {"name": " "}, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_delete_works_until_a_game_started(self):
        self.as_staff()
        game = self.game()
        StudyGame.objects.create(study=self.study, game=game)
        self.assertEqual(self.client.delete(f"{URL}{self.study.pk}/").status_code, 204)
        self.assertFalse(Study.objects.filter(pk=self.study.pk).exists())
        game.refresh_from_db()  # the game itself stays

    def test_delete_is_refused_once_a_game_started(self):
        self.as_staff()
        StudyGame.objects.create(
            study=self.study, game=self.game(started_at=timezone.now())
        )
        response = self.client.delete(f"{URL}{self.study.pk}/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("gestartet", response.json()["detail"])
        self.assertTrue(Study.objects.filter(pk=self.study.pk).exists())

    def test_delete_is_refused_while_a_code_sits_on_a_seat(self):
        self.as_staff()
        game = self.game()
        player = Player.objects.create(game=game, name="A")
        code = Participant.objects.create(study=self.study, code="ABCDEFGH")
        StudySeat.objects.create(participant=code, player=player, game=game)
        response = self.client.delete(f"{URL}{self.study.pk}/")
        self.assertEqual(response.status_code, 409)


class CodeTests(StudyApiCase):
    def test_a_batch_makes_that_many_unique_codes_of_the_right_shape(self):
        self.as_staff()
        response = self.client.post(
            f"{URL}{self.study.pk}/codes/",
            {"count": 12},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        codes = [row["code"] for row in response.json()]
        self.assertEqual(len(set(codes)), 12)
        for code in codes:
            self.assertEqual(len(code), PARTICIPANT_CODE_LENGTH)
            self.assertTrue(set(code) <= set(CODE_ALPHABET))
        self.assertEqual(
            self.client.get(f"{URL}{self.study.pk}/codes/").json().__len__(), 12
        )

    def test_the_count_has_a_sane_range(self):
        self.as_staff()
        for count in (0, -1, 501, "x", None):
            response = self.client.post(
                f"{URL}{self.study.pk}/codes/",
                {"count": count},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400, count)
        self.assertEqual(Participant.objects.count(), 0)

    def test_a_code_is_unique_across_studies(self):
        other = Study.objects.create(name="Andere")
        Participant.objects.create(study=other, code="ABCDEFGH")
        with self.assertRaises(Exception):
            Participant.objects.create(study=self.study, code="ABCDEFGH")

    def test_an_unused_code_can_be_deleted_a_seated_one_cannot(self):
        self.as_staff()
        free = Participant.objects.create(study=self.study, code="AAAAAAAA")
        taken = Participant.objects.create(study=self.study, code="BBBBBBBB")
        game = self.game()
        StudySeat.objects.create(
            participant=taken,
            player=Player.objects.create(game=game, name="A"),
            game=game,
        )
        self.assertEqual(
            self.client.delete(f"{URL}{self.study.pk}/codes/{free.pk}/").status_code,
            204,
        )
        response = self.client.delete(f"{URL}{self.study.pk}/codes/{taken.pk}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Participant.objects.filter(pk=taken.pk).exists())

    def test_a_code_of_another_study_is_a_404(self):
        self.as_staff()
        other = Study.objects.create(name="Andere")
        code = Participant.objects.create(study=other, code="CCCCCCCC")
        response = self.client.delete(f"{URL}{self.study.pk}/codes/{code.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_a_code_plays_once_per_game(self):
        game = self.game()
        code = Participant.objects.create(study=self.study, code="DDDDDDDD")
        StudySeat.objects.create(
            participant=code,
            player=Player.objects.create(game=game, name="A"),
            game=game,
        )
        with self.assertRaises(Exception):
            StudySeat.objects.create(
                participant=code,
                player=Player.objects.create(game=game, name="B"),
                game=game,
            )


class CardTests(StudyApiCase):
    def test_a_card_has_its_code_and_a_qr_to_the_one_way_in(self):
        self.as_staff()
        Participant.objects.create(study=self.study, code="EEEEEEEE")
        rows = self.client.get(f"{URL}{self.study.pk}/cards/").json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "EEEEEEEE")
        self.assertTrue(rows[0]["url"].endswith("/app/join/EEEEEEEE"))
        prefix = "data:image/svg+xml;base64,"
        self.assertTrue(rows[0]["qr"].startswith(prefix))
        svg = base64.b64decode(rows[0]["qr"][len(prefix) :]).decode()
        self.assertIn("<svg", svg)


class GameLinkTests(StudyApiCase):
    def test_link_list_and_unlink_a_lobby_game(self):
        self.as_staff()
        game = self.game()
        response = self.client.post(
            f"{URL}{self.study.pk}/games/",
            {"game_id": game.game_id.lower()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        rows = self.client.get(f"{URL}{self.study.pk}/games/").json()
        self.assertEqual(rows[0]["game_id"], game.game_id)
        self.assertEqual(rows[0]["name"], "Dienstag")
        self.assertEqual(rows[0]["map"], game.game_map.name)
        self.assertIsNone(rows[0]["started_at"])
        self.assertIs(rows[0]["hide_co2"], False)
        self.assertEqual(
            self.client.delete(
                f"{URL}{self.study.pk}/games/{game.game_id}/"
            ).status_code,
            204,
        )
        self.assertFalse(StudyGame.objects.exists())

    def test_a_started_game_cannot_be_linked_or_unlinked(self):
        self.as_staff()
        started = self.game(started_at=timezone.now())
        response = self.client.post(
            f"{URL}{self.study.pk}/games/",
            {"game_id": started.game_id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        StudyGame.objects.create(study=self.study, game=started)
        response = self.client.delete(f"{URL}{self.study.pk}/games/{started.game_id}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(StudyGame.objects.exists())

    def test_a_game_is_in_one_study_only(self):
        self.as_staff()
        game = self.game()
        other = Study.objects.create(name="Andere")
        StudyGame.objects.create(study=other, game=game)
        response = self.client.post(
            f"{URL}{self.study.pk}/games/",
            {"game_id": game.game_id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_an_unknown_game_is_a_404(self):
        self.as_staff()
        response = self.client.post(
            f"{URL}{self.study.pk}/games/",
            {"game_id": "ZZZZZZ"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


class NoteTests(StudyApiCase):
    def post_note(self, **body):
        return self.client.post(
            f"{URL}{self.study.pk}/notes/", body, content_type="application/json"
        )

    def test_crud_with_games_date_and_flat_meta(self):
        self.as_staff()
        game = self.game()
        StudyGame.objects.create(study=self.study, game=game)
        response = self.post_note(
            text="Klasse 9b, laut.",
            about_date="2026-10-12",
            games=[game.game_id],
            meta={"Klasse": "9b", "Schüler": 24, "Beamer": True},
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["author"], "staff")
        self.assertEqual(body["games"], [game.game_id])
        self.assertEqual(body["meta"], {"Klasse": "9b", "Schüler": 24, "Beamer": True})

        patch = self.client.patch(
            f"{URL}{self.study.pk}/notes/{body['id']}/",
            {"text": "geändert"},
            content_type="application/json",
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(ResearchNote.objects.get().text, "geändert")
        self.assertEqual(len(self.client.get(f"{URL}{self.study.pk}/notes/").json()), 1)
        self.assertEqual(
            self.client.delete(f"{URL}{self.study.pk}/notes/{body['id']}/").status_code,
            204,
        )

    def test_meta_must_be_flat(self):
        self.as_staff()
        for meta in ({"a": [1]}, {"a": {"b": 1}}, {"a": None}, ["a"], {"": "x"}):
            self.assertEqual(self.post_note(text="x", meta=meta).status_code, 400, meta)

    def test_the_author_is_kept_empty_when_the_account_goes(self):
        self.as_staff()
        self.post_note(text="x")
        self.staff.delete()
        self.assertIsNone(ResearchNote.objects.get().author)

    def test_a_game_of_another_study_cannot_be_named(self):
        self.as_staff()
        other = Study.objects.create(name="Andere")
        game = self.game()
        StudyGame.objects.create(study=other, game=game)
        self.assertEqual(
            self.post_note(text="x", games=[game.game_id]).status_code, 400
        )


class HiddenCo2Tests(StudyApiCase):
    def test_the_list_marks_a_game_with_hidden_co2(self):
        self.as_staff()
        StudyGame.objects.create(study=self.study, game=self.game(hide_co2=True))
        rows = self.client.get(f"{URL}{self.study.pk}/games/").json()
        self.assertIs(rows[0]["hide_co2"], True)
