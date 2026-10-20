"""Pendlertypen: the standard list, a game's own copies, the deal at join.

The debrief that reads them back is in `test_rounds.py`, beside the rest of the
summary.
"""

import importlib
import random
from collections import Counter
from types import SimpleNamespace

from django.apps import apps
from django.test import TestCase, override_settings
from django.urls import resolve

from game.models import GameSession, Persona, Player
from game.personas import changes, deal

from ._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    log_in_as_player,
    muted,
    post_create,
)


def dealable_map(workplaces=3):
    """A map the join can deal from: one home and a few workplaces in base."""
    from maps.models import GameMap, MapVersion, Node, NodeType

    game_map = GameMap.objects.create(name="Pendeln")
    base = MapVersion.objects.create(game_map=game_map, name="Base", base_version=True)
    home_type = NodeType.objects.create(name="home", short="H")
    work_type = NodeType.objects.create(name="workplace", short="W")
    home = Node.objects.create(
        game_map=game_map, name="Zuhause", x_position=0, y_position=0
    )
    home.map_versions.add(base)
    home.node_type.add(home_type)
    for i in range(workplaces):
        work = Node.objects.create(
            game_map=game_map, name=f"Arbeit {i}", x_position=i + 1, y_position=0
        )
        work.map_versions.add(base)
        work.node_type.add(work_type)
    return game_map


class StandardPendlertypenTests(TestCase):
    """`GET api/game/personas/` — what the create form offers."""

    def test_the_migration_seeds_seven(self):
        names = list(Persona.objects.filter(game=None).values_list("name", flat=True))

        self.assertEqual(len(names), 7)
        self.assertEqual(names[0], "Auf den letzten Drücker")
        self.assertEqual(names[-1], "Einfach du")

    def test_the_route_is_not_taken_for_a_game_id(self):
        self.assertEqual(resolve("/api/game/personas/").url_name, "standard-personas")

    def test_a_host_gets_the_standard_ones_and_no_games_own(self):
        host = create_host()
        with muted():
            game = create_game_session(host)
        Persona.objects.create(game=game, name="Nur in diesem Spiel")
        self.client.force_login(host)

        response = self.client.get("/api/game/personas/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 7)
        self.assertNotIn("Nur in diesem Spiel", [p["name"] for p in body])
        self.assertEqual(set(body[0]), {"id", "name", "description"})

    def test_nobody_logged_out_gets_them(self):
        response = self.client.get("/api/game/personas/")

        self.assertIn(response.status_code, (401, 403))


TEXTS_MIGRATION = "game.migrations.0028_pendlertypen_texte"

NEW_TEXTS = {
    "Auf den letzten Drücker": "Immer zu spät los. Hauptsache schnell da, egal womit.",
    "Sparfuchs": "Ende des Monats, Konto leer. Der billigste Weg gewinnt, auch wenn er dauert.",
    "Öko aus Überzeugung": "So wenig CO₂ wie möglich, auch wenn es länger dauert oder mehr kostet.",
    "Sportskanone": "Wozu ins Fitnessstudio? Wo es geht, mit dem Rad oder zu Fuß.",
    "Bloß kein Stress": "Kein Umsteigen, keine Umwege. Hauptsache entspannt ankommen.",
    "Benzin im Blut": "Ohne Auto geht gar nichts. Lieber im Stau als in Bus und Bahn.",
    "Einfach du": "Keine Rolle. Fahr so, wie du selbst fahren würdest.",
}


class StandardTextsMigrationTests(TestCase):
    """0028 rewrites the seven standard texts, and only where nobody has touched them.

    Its functions are called directly with the app registry, as the other data
    migrations' tests do.
    """

    def migration(self):
        return importlib.import_module(TEXTS_MIGRATION)

    def standard(self):
        return {p.name: p.description for p in Persona.objects.filter(game=None)}

    def test_a_standard_row_with_the_old_draft_gets_the_new_text(self):
        # The test database was migrated up to 0028 already; put the drafts back.
        self.migration().restore_old_texts(apps, None)
        self.assertNotEqual(self.standard()["Sparfuchs"], NEW_TEXTS["Sparfuchs"])

        self.migration().rewrite_standard_texts(apps, None)

        self.assertEqual(self.standard(), NEW_TEXTS)

    def test_the_seven_rows_say_it_after_migrating(self):
        self.assertEqual(self.standard(), NEW_TEXTS)

    def test_an_edit_in_the_admin_stays(self):
        self.migration().restore_old_texts(apps, None)
        Persona.objects.filter(game=None, name="Sparfuchs").update(
            description="Mein eigener Satz."
        )

        self.migration().rewrite_standard_texts(apps, None)

        self.assertEqual(self.standard()["Sparfuchs"], "Mein eigener Satz.")
        self.assertEqual(self.standard()["Sportskanone"], NEW_TEXTS["Sportskanone"])

    def test_a_game_keeps_the_text_it_copied(self):
        host = create_host()
        with muted():
            game = create_game_session(host)
        self.migration().restore_old_texts(apps, None)
        old = Persona.objects.get(game=None, name="Sparfuchs").description
        copy = Persona.objects.create(game=game, name="Sparfuchs", description=old)

        self.migration().rewrite_standard_texts(apps, None)

        copy.refresh_from_db()
        self.assertEqual(copy.description, old)

    def test_it_can_be_taken_back(self):
        self.migration().restore_old_texts(apps, None)

        self.assertEqual(
            self.standard()["Benzin im Blut"],
            "Ohne Auto geht gar nichts. Lieber im Stau als im Bus.",
        )


class CreateWithPendlertypenTests(TempMediaRootMixin, TestCase):
    """`POST api/game/` with the list the host picked."""

    def setUp(self):
        self.host = create_host()
        self.client.force_login(self.host)

    def create(self, **overrides):
        with muted():
            response = post_create(self.client, **overrides)
        return response

    def test_a_game_keeps_its_own_copies_in_the_order_picked(self):
        response = self.create(
            personas=[
                {"name": "Sparfuchs", "description": "Jeder Euro zählt."},
                {"name": "Nachteule", "description": ""},
            ]
        )

        self.assertEqual(response.status_code, 201)
        game = GameSession.objects.get(game_id=response.json()["game_id"])
        self.assertEqual(
            list(game.personas.values_list("name", flat=True)),
            ["Sparfuchs", "Nachteule"],
        )

    def test_a_hosts_own_is_offered_nowhere_else(self):
        self.create(personas=[{"name": "Nachteule", "description": ""}])

        self.assertFalse(Persona.objects.filter(game=None, name="Nachteule").exists())

    def test_without_any_the_game_plays_free(self):
        response = self.create()

        self.assertEqual(response.status_code, 201)
        game = GameSession.objects.get(game_id=response.json()["game_id"])
        self.assertEqual(game.personas.count(), 0)

    def test_editing_a_standard_one_changes_no_game(self):
        standard = Persona.objects.filter(game=None).first()
        assert standard is not None
        response = self.create(
            personas=[{"name": standard.name, "description": standard.description}]
        )
        game = GameSession.objects.get(game_id=response.json()["game_id"])

        standard.description = "Ganz anders."
        standard.save()

        self.assertNotEqual(game.personas.get().description, "Ganz anders.")

    def test_a_pendlertyp_needs_a_name(self):
        response = self.create(personas=[{"name": "   ", "description": "Ohne Namen"}])

        self.assertEqual(response.status_code, 400)
        self.assertIn("personas", response.json())
        self.assertFalse(GameSession.objects.exists())

    def test_switched_on_with_none_picked_is_refused(self):
        """The form sends the key only with the switch on, so an empty list is
        a host who wanted Pendlertypen and unticked every one."""
        response = self.create(personas=[])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["personas"], ["Wähle mindestens einen Pendlertyp."]
        )
        self.assertFalse(GameSession.objects.exists())

    def test_the_hosts_own_row_is_dealt_from_them(self):
        """The host's row is made right after the game, so the game's
        Pendlertypen have to exist by then."""
        response = self.create(
            game_map=dealable_map().pk,
            agent_per_player=2,
            max_players=4,
            personas=[
                {"name": "Sparfuchs", "description": ""},
                {"name": "Sportskanone", "description": ""},
            ],
        )

        game = GameSession.objects.get(game_id=response.json()["game_id"])
        host_row = Player.objects.host_rows().get(game=game)
        dealt = {a["persona"] for a in host_row.agent_assignments["agents"]}
        self.assertEqual(dealt, set(game.personas.values_list("pk", flat=True)))


class DealTests(TestCase):
    def test_a_seats_gruppen_get_different_ones_while_the_deck_lasts(self):
        dealt = deal([1, 2, 3, 4, 5, 6, 7], 4, rng=random.Random(3))

        self.assertEqual(len(dealt), 4)
        self.assertEqual(len(set(dealt)), 4)

    def test_more_gruppen_than_pendlertypen_go_round_again(self):
        dealt = deal([1, 2], 5, rng=random.Random(3))

        self.assertEqual(sorted(Counter(dealt).values()), [2, 3])

    def test_the_deck_is_shuffled_per_seat(self):
        seen = {
            tuple(deal([1, 2, 3], 3, rng=random.Random(seed))) for seed in range(20)
        }

        self.assertGreater(len(seen), 1)

    def test_no_pendlertypen_no_deal(self):
        self.assertEqual(deal([], 3), [])


@override_settings(**TEST_BACKENDS)
class DealtAtJoinTests(TempMediaRootMixin, TestCase):
    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(
                self.host, game_map=dealable_map(), agent_per_player=3
            )

    def join(self, name="Mia"):
        with muted():
            player = Player.objects.create(game=self.game, name=name)
        player.refresh_from_db()
        return player

    def test_each_gruppe_gets_one_of_the_games(self):
        ids = [
            Persona.objects.create(game=self.game, name=name, order=i).pk
            for i, name in enumerate(["A", "B", "C", "D"])
        ]

        agents = self.join().agent_assignments["agents"]

        dealt = [a["persona"] for a in agents]
        self.assertEqual(len(set(dealt)), 3)
        self.assertTrue(set(dealt) <= set(ids))

    def test_a_game_without_any_deals_none(self):
        agents = self.join().agent_assignments["agents"]

        self.assertTrue(all("persona" not in a for a in agents))

    def test_the_seat_payload_carries_the_games_pendlertypen(self):
        persona = Persona.objects.create(
            game=self.game, name="Sparfuchs", description="Jeder Euro zählt."
        )
        player = self.join()
        log_in_as_player(self.client, self.game.game_id, player.player_id)

        with muted():
            response = self.client.get(
                f"/api/game/{self.game.game_id}/{player.player_id}/"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["personas"],
            [
                {
                    "id": persona.pk,
                    "name": "Sparfuchs",
                    "description": "Jeder Euro zählt.",
                }
            ],
        )


def seg(mode, line=None):
    return SimpleNamespace(mode=mode, pt_line_id=line)


class ChangesTests(TestCase):
    """What the "Bloß kein Stress" Gruppe is judged by."""

    def test_one_line_all_the_way_is_no_change(self):
        self.assertEqual(
            changes([seg("walk"), seg("bus", 1), seg("bus", 1), seg("walk")]), 0
        )

    def test_bus_to_train_is_one(self):
        self.assertEqual(
            changes([seg("walk"), seg("bus", 1), seg("train", 1), seg("walk")]), 1
        )

    def test_bus_2_and_train_2_are_different_lines(self):
        self.assertEqual(changes([seg("bus", 2), seg("train", 2)]), 1)

    def test_off_and_on_the_same_line_is_a_change(self):
        self.assertEqual(changes([seg("bus", 1), seg("walk"), seg("bus", 1)]), 1)

    def test_a_car_never_changes(self):
        self.assertEqual(changes([seg("car"), seg("car")]), 0)
