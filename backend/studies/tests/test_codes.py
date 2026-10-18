"""The participant code in the one way in (`api/game/code/<CODE>/`, 8 characters)."""

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from game.models import GameSession, Player
from game.seats import issue_code
from game.tests._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_game_map,
    create_game_session,
    create_host,
    muted,
)

from studies.models import Participant, Study, StudyGame, StudySeat


def url(code):
    return f"/api/game/code/{code}/"


@override_settings(**TEST_BACKENDS)
class CardTests(TempMediaRootMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.host = create_host()
        self.study = Study.objects.create(name="Sommer")
        self.card = Participant.objects.create(study=self.study, code="K7P2QX3M")
        self.map = create_game_map()

    def game(self, name="Dienstag", linked=True, **extra):
        with muted():
            game = create_game_session(
                self.host, game_map=self.map, game_name=name, **extra
            )
        if linked:
            StudyGame.objects.create(study=self.study, game=game)
        return game

    def join(self, code, **body):
        body.setdefault("name", "Ana")
        with muted():
            return self.client.post(url(code), body, content_type="application/json")


class LookTests(CardTests):
    def test_it_names_the_study_and_the_waiting_games(self):
        a = self.game("A")
        self.game("B", game_password="geheim")

        body = self.client.get(url(self.card.code)).json()

        self.assertEqual(body["kind"], "participant")
        self.assertEqual(body["study_name"], "Sommer")
        self.assertIsNone(body["reason"])
        self.assertEqual(len(body["games"]), 2)
        first = [g for g in body["games"] if g["game_id"] == a.game_id][0]
        self.assertEqual(first["game_name"], "A")
        self.assertTrue(first["joinable"])
        self.assertFalse(first["requires_password"])
        self.assertTrue(
            [g for g in body["games"] if g["game_name"] == "B"][0]["requires_password"]
        )

    def test_a_started_an_ended_and_an_unlinked_game_do_not_wait(self):
        started = self.game("läuft")
        GameSession.objects.filter(pk=started.pk).update(started_at=timezone.now())
        ended = self.game("vorbei")
        GameSession.objects.filter(pk=ended.pk).update(ended_at=timezone.now())
        self.game("fremd", linked=False)

        body = self.client.get(url(self.card.code)).json()

        self.assertEqual(body["games"], [])
        self.assertEqual(body["reason"], "none_waiting")

    def test_a_game_the_code_already_plays_in_is_left_out(self):
        game = self.game()
        self.assertEqual(self.join(self.card.code, game_id=game.game_id).status_code, 201)

        body = self.client.get(url(self.card.code)).json()

        self.assertEqual(body["games"], [])
        self.assertEqual(body["reason"], "played")

    def test_another_studys_game_is_not_offered(self):
        other = Study.objects.create(name="Winter")
        game = self.game(linked=False)
        StudyGame.objects.create(study=other, game=game)

        self.assertEqual(self.client.get(url(self.card.code)).json()["games"], [])

    def test_an_unknown_code_is_a_404(self):
        self.assertEqual(self.client.get(url("ZZZZZZZZ")).status_code, 404)

    def test_the_game_look_says_it_belongs_to_a_coded_study(self):
        game = self.game()

        body = self.client.get(url(game.game_id)).json()

        self.assertIs(body["coded_study"], True)

    def test_a_game_of_a_study_without_codes_or_none_says_not(self):
        free = Study.objects.create(name="Ohne Karten")
        linked = self.game(linked=False)
        StudyGame.objects.create(study=free, game=linked)
        loose = self.game("lose", linked=False)

        self.assertIs(self.client.get(url(linked.game_id)).json()["coded_study"], False)
        self.assertIs(self.client.get(url(loose.game_id)).json()["coded_study"], False)


class TakeTests(CardTests):
    def test_it_joins_the_game_and_writes_the_seat_together(self):
        game = self.game()

        response = self.join(self.card.code, game_id=game.game_id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["game_id"], game.game_id)
        self.assertIn(f"player_{game.game_id}", response.cookies)
        player = Player.objects.get(game=game, name="Ana")
        seat = StudySeat.objects.get(player=player)
        self.assertEqual(seat.participant, self.card)
        self.assertEqual(seat.game, game)

    def test_one_waiting_game_needs_no_choice(self):
        game = self.game()

        response = self.join(self.card.code)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["game_id"], game.game_id)

    def test_several_waiting_games_need_a_choice(self):
        self.game("A")
        self.game("B")

        response = self.join(self.card.code)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "choose")
        self.assertEqual(StudySeat.objects.count(), 0)

    def test_a_game_outside_the_cards_study_is_unknown(self):
        self.game()
        foreign = self.game("fremd", linked=False)

        self.assertEqual(
            self.join(self.card.code, game_id=foreign.game_id).status_code, 404
        )
        self.assertEqual(Player.objects.filter(game=foreign).count(), 0)

    def test_the_same_code_plays_once_per_game(self):
        game = self.game()
        self.join(self.card.code, game_id=game.game_id)
        second = self.game("zwei", linked=False)
        StudyGame.objects.create(study=self.study, game=second)

        again = self.join(self.card.code, game_id=game.game_id, name="Ben")

        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["reason"], "used")
        self.assertEqual(Player.objects.filter(game=game).count(), 1)
        # …and still opens the other game.
        self.assertEqual(
            self.join(self.card.code, game_id=second.game_id, name="Ben").status_code,
            201,
        )

    def test_a_wrong_password_is_refused_before_anything_else(self):
        game = self.game(game_password="geheim")

        wrong = self.join(self.card.code, game_id=game.game_id, password="falsch")
        right = self.join(self.card.code, game_id=game.game_id, password="geheim")

        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(right.status_code, 201)

    def test_a_full_game_refuses_and_writes_no_seat(self):
        game = self.game(max_players=1)
        with muted():
            Player.objects.create(game=game, name="Zuerst")

        response = self.join(self.card.code, game_id=game.game_id)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "full")
        self.assertEqual(StudySeat.objects.count(), 0)

    def test_a_game_id_still_joins_a_coded_game_without_a_code(self):
        game = self.game()

        response = self.join(game.game_id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(StudySeat.objects.count(), 0)

    def test_a_miss_is_counted_like_a_seat_code(self):
        from co2mmute.throttle import SEAT_CODE_LIMIT

        for _ in range(SEAT_CODE_LIMIT):
            self.client.get(url("ZZZZZZZZ"))

        self.assertEqual(self.client.get(url("ZZZZZZZZ")).status_code, 429)


class SeatFollowsTests(CardTests):
    def test_a_seat_code_takeover_keeps_the_study_seat(self):
        game = self.game()
        self.join(self.card.code, game_id=game.game_id)
        player = Player.objects.get(game=game)
        old = player.player_id
        code = issue_code(player)

        with muted():
            response = self.client.post(url(code), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        player.refresh_from_db()
        self.assertNotEqual(player.player_id, old)
        self.assertEqual(StudySeat.objects.get(player=player).participant, self.card)

    def test_a_host_takeover_keeps_the_study_seat(self):
        from game.seats import take_over

        game = self.game()
        self.join(self.card.code, game_id=game.game_id)
        player = Player.objects.get(game=game)

        with muted():
            take_over(player)

        self.assertEqual(StudySeat.objects.get(player=player).participant, self.card)
