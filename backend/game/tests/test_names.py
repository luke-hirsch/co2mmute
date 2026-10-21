from django.test import SimpleTestCase

from game.names import looks_like_the_host


class HostNameLookalikeTests(SimpleTestCase):
    """No one but the host may carry a name that reads as Spielleitung."""

    def test_the_name_and_its_spellings_are_refused(self):
        for name in (
            "Spielleitung",
            "spielleitung",
            "SPIELLEITUNG",
            " Spielleitung ",
            "Spiel leitung",
            "Spiel-Leitung",
            "Spiel_Leitung!",
            "Spiel·Leitung",
        ):
            with self.subTest(name=name):
                self.assertTrue(looks_like_the_host(name))

    def test_typos_are_refused(self):
        for name in (
            "Spieleitung",  # a letter short
            "Speilleitung",  # two letters swapped
            "Spielleitungg",  # a letter too many
            "Spielleitnug",  # two letters swapped
            "Spilleitung",
            "Spielleitun",
        ):
            with self.subTest(name=name):
                self.assertTrue(looks_like_the_host(name))

    def test_look_alike_digits_are_refused(self):
        for name in (
            "Sp1elle1tung",
            "Spi3lleitung",
            "Sp1elleitung",
            "Spielleitung".replace("e", "3"),
        ):
            with self.subTest(name=name):
                self.assertTrue(looks_like_the_host(name))

    def test_ordinary_names_get_through(self):
        for name in (
            "Spieler",
            "Spieler 1",
            "Leitung",
            "Spiel",
            "Lea",
            "Leo",
            "Alex",
            "Müller",
            "Spielleitung-Fan",
            "Die Spielleitungsfans",
            "SS",
            "",
        ):
            with self.subTest(name=name):
                self.assertFalse(looks_like_the_host(name))
