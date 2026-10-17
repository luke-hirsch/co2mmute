"""The privacy page's section on study codes: only with the study app on, and
its three lengths come from the code, never from the page."""

from unittest import mock

from django.test import TestCase, modify_settings

HEADING = "Studien mit Teilnahmecode"


def page(client):
    response = client.get("/legal/dsgvo/")
    assert response.status_code == 200
    return " ".join(response.content.decode().split())


class StudyCodeSectionTests(TestCase):
    def test_the_section_is_there_with_the_app_on(self):
        html = page(self.client)

        self.assertIn(HEADING, html)
        self.assertIn("Manche Spiele gehören zu einer Studie der Forschungsgruppe", html)
        self.assertIn("Sie speichert nicht, wem ein Code gehört.", html)
        self.assertIn("deine Spiele werden nicht verbunden", html)

    @modify_settings(INSTALLED_APPS={"remove": "studies"})
    def test_the_section_is_gone_with_the_app_off(self):
        html = page(self.client)

        self.assertNotIn(HEADING, html)
        self.assertNotIn("Teilnahmecode", html)

    def test_the_three_lengths_are_the_constants(self):
        from game.models import GameSession

        game_id = GameSession._meta.get_field("game_id").max_length
        html = page(self.client)
        self.assertIn("Sie haben 8 Zeichen", html)
        self.assertIn(f"Spiel-ID ({game_id} Zeichen)", html)
        self.assertIn("Platz-Code (6 Zeichen)", html)

        with (
            mock.patch("studies.models.PARTICIPANT_CODE_LENGTH", 11),
            mock.patch("game.seats.CODE_LENGTH", 9),
        ):
            html = page(self.client)
        self.assertIn("Sie haben 11 Zeichen", html)
        self.assertIn("Platz-Code (9 Zeichen)", html)
