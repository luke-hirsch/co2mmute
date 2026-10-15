"""Where a seat's Gruppen live and work: the deal at join, both ways."""

import importlib
import json
import random
from collections import Counter

from django.apps import apps
from django.test import TestCase, override_settings
from django.utils import timezone

from game.deal import balanced, halves
from game.models import GameSession, Player

from ._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    muted,
    post_create,
)


def grid(columns, rows):
    """Points on a grid, one id per point, x along the columns."""
    return [
        (column * rows + row + 1, float(column), float(row))
        for column in range(columns)
        for row in range(rows)
    ]


def quarter(point):
    _, x, y = point
    return (x >= 2, y >= 2)


class HalvesTests(TestCase):
    """The order a balanced game takes its homes in."""

    def test_every_home_comes_once(self):
        points = grid(5, 3)

        order = halves(points, random.Random(1))

        self.assertEqual(sorted(order), sorted(pk for pk, _, _ in points))

    def test_the_first_two_lie_in_different_halves_of_the_longer_side(self):
        """Eight wide, two high: the first cut is down the middle of the eight."""
        points = grid(8, 2)
        by_id = {pk: x for pk, x, _ in points}

        for seed in range(20):
            first, second = halves(points, random.Random(seed))[:2]
            self.assertNotEqual(by_id[first] >= 4, by_id[second] >= 4, msg=seed)

    def test_the_first_four_lie_in_four_quarters(self):
        points = grid(4, 4)
        by_id = {point[0]: point for point in points}

        for seed in range(20):
            first_four = halves(points, random.Random(seed))[:4]
            quarters = {quarter(by_id[pk]) for pk in first_four}
            self.assertEqual(len(quarters), 4, msg=seed)

    def test_the_order_of_the_rows_read_does_not_matter(self):
        """A database hands rows back in any order; the deal must not care."""
        points = grid(4, 3)
        shuffled = list(points)
        random.Random(7).shuffle(shuffled)

        self.assertEqual(
            halves(points, random.Random(5)), halves(shuffled, random.Random(5))
        )

    def test_games_get_different_orders(self):
        points = grid(4, 4)

        orders = {tuple(halves(points, random.Random(seed))) for seed in range(10)}

        self.assertGreater(len(orders), 1)


class BalancedTests(TestCase):
    """One seat's Gruppen, given what the seats before it hold."""

    def test_a_seats_gruppen_live_at_different_homes(self):
        pairs = balanced(
            [1, 2, 3, 4, 5, 6], Counter(), [10, 11], Counter(), 4, random.Random(1)
        )

        self.assertEqual(len({home for home, _ in pairs}), 4)

    def test_the_least_loaded_home_goes_first(self):
        pairs = balanced(
            [1, 2, 3], Counter({1: 1, 2: 1}), [10], Counter(), 1, random.Random(1)
        )

        self.assertEqual(pairs[0][0], 3)

    def test_among_the_least_loaded_the_order_decides(self):
        pairs = balanced([3, 1, 2], Counter(), [10], Counter(), 2, random.Random(1))

        self.assertEqual([home for home, _ in pairs], [3, 1])

    def test_more_gruppen_than_homes_go_round_again(self):
        pairs = balanced([1, 2], Counter(), [10], Counter(), 5, random.Random(1))

        self.assertEqual(sorted(Counter(home for home, _ in pairs).values()), [2, 3])

    def test_seat_after_seat_every_home_and_workplace_within_one(self):
        homes, workplaces = [1, 2, 3, 4, 5], [10, 11, 12, 13]
        home_load, work_load = Counter(), Counter()
        rng = random.Random(4)

        for _seat in range(7):
            for home, work in balanced(homes, home_load, workplaces, work_load, 3, rng):
                home_load[home] += 1
                work_load[work] += 1
            self.assertLessEqual(
                max(home_load[h] for h in homes) - min(home_load[h] for h in homes), 1
            )
            self.assertLessEqual(
                max(work_load[w] for w in workplaces)
                - min(work_load[w] for w in workplaces),
                1,
            )

    def test_who_works_where_is_drawn(self):
        seen = {
            tuple(
                balanced(
                    [1, 2, 3], Counter(), [10, 11, 12], Counter(), 3, random.Random(s)
                )
            )
            for s in range(20)
        }

        self.assertGreater(len(seen), 1)

    def test_the_loads_passed_in_are_left_alone(self):
        home_load, work_load = Counter({1: 1}), Counter({10: 1})

        balanced([1, 2], home_load, [10, 11], work_load, 2, random.Random(1))

        self.assertEqual(home_load, Counter({1: 1}))
        self.assertEqual(work_load, Counter({10: 1}))


def two_by_two_map():
    """Four homes in the corners of a square and two workplaces in the middle."""
    from maps.models import GameMap, MapVersion, Node, NodeType

    game_map = GameMap.objects.create(name="Viertel")
    base = MapVersion.objects.create(game_map=game_map, name="Base", base_version=True)
    home_type = NodeType.objects.create(name="home", short="H")
    work_type = NodeType.objects.create(name="workplace", short="W")
    homes = []
    for name, x, y in [
        ("Wohnort Nordwest", 0, 0),
        ("Wohnort Nordost", 10, 0),
        ("Wohnort Südwest", 0, 10),
        ("Wohnort Südost", 10, 10),
    ]:
        node = Node.objects.create(
            game_map=game_map, name=name, x_position=x, y_position=y
        )
        node.map_versions.add(base)
        node.node_type.add(home_type)
        homes.append(node.pk)
    for name, x in [("Arbeit West", 4), ("Arbeit Ost", 6)]:
        node = Node.objects.create(
            game_map=game_map, name=name, x_position=x, y_position=5
        )
        node.map_versions.add(base)
        node.node_type.add(work_type)
    return game_map, homes


def homes_of(player):
    player.refresh_from_db()
    return [a.get("home_node") for a in player.agent_assignments["agents"]]


@override_settings(**TEST_BACKENDS)
class DealtAtJoinTests(TempMediaRootMixin, TestCase):
    def setUp(self):
        self.host = create_host()
        self.game_map, self.homes = two_by_two_map()

    def game(self, balanced_deal, agent_per_player):
        with muted():
            return create_game_session(
                self.host,
                game_map=self.game_map,
                agent_per_player=agent_per_player,
                max_players=8,
                balanced_deal=balanced_deal,
            )

    def join(self, game, name="Mia"):
        with muted():
            return Player.objects.create(game=game, name=name)

    def test_off_a_seats_gruppen_share_one_home(self):
        game = self.game(False, 3)

        homes = homes_of(self.join(game))

        self.assertEqual(len(set(homes)), 1)
        self.assertIn(homes[0], self.homes)

    def test_off_the_next_seat_takes_a_free_home(self):
        game = self.game(False, 2)
        taken = set()

        for name in ["Mia", "Ben", "Ida", "Ole"]:
            taken |= set(homes_of(self.join(game, name)))

        self.assertEqual(taken, set(self.homes))

    def test_on_a_seats_gruppen_live_at_every_corner(self):
        game = self.game(True, 4)

        homes = homes_of(self.join(game))

        self.assertEqual(Counter(homes), Counter(self.homes))

    def test_on_two_gruppen_live_on_opposite_sides(self):
        """The first cut is the longer side; a square cuts along x."""
        from maps.models import Node

        game = self.game(True, 2)

        homes = homes_of(self.join(game))

        x = dict(Node.objects.values_list("pk", "x_position"))
        self.assertEqual({x.get(pk) for pk in homes}, {0, 10})

    def test_on_seat_after_seat_every_home_and_workplace_within_one(self):
        game = self.game(True, 3)

        players = [self.join(game, name) for name in ["Mia", "Ben", "Ida"]]

        home_load, work_load = Counter(), Counter()
        for player in players:
            player.refresh_from_db()
            for agent in player.agent_assignments["agents"]:
                home_load[agent.get("home_node")] += 1
                work_load[agent["destination_node"]] += 1
        self.assertEqual(sorted(home_load.values()), [2, 2, 2, 3])
        self.assertEqual(sorted(work_load.values()), [4, 5])

    def test_on_a_seat_that_left_frees_its_homes(self):
        game = self.game(True, 2)
        first = self.join(game, "Mia")
        Player.objects.filter(pk=first.pk).update(left_at=timezone.now())

        second = self.join(game, "Ben")

        self.assertEqual(homes_of(second), homes_of(first))

    def test_on_the_hosts_own_row_does_not_count(self):
        """It is dealt like any seat and never plays a round."""
        game = self.game(True, 2)
        with muted():
            host_row = Player.objects.create(game=game, name="Leitung", user=self.host)

        player = self.join(game)

        self.assertEqual(homes_of(player), homes_of(host_row))

    def test_on_the_seat_payload_names_each_gruppes_home(self):
        game = self.game(True, 2)

        player = self.join(game)
        player.refresh_from_db()

        self.assertNotIn("home_node", player.agent_assignments)
        for agent in player.agent_assignments["agents"]:
            self.assertEqual(set(agent), {"id", "home_node", "destination_node"})


@override_settings(**TEST_BACKENDS)
class BalancedDealSettingTests(TempMediaRootMixin, TestCase):
    """The host picks the deal when the game is made, and only then."""

    def setUp(self):
        self.host = create_host()
        self.client.force_login(self.host)

    def create(self, **overrides):
        game_map, _ = two_by_two_map()
        with muted():
            response = post_create(self.client, game_map=game_map.pk, **overrides)
        self.assertEqual(response.status_code, 201, response.content)
        return GameSession.objects.get(game_id=response.json()["game_id"])

    def test_off_unless_asked(self):
        self.assertFalse(self.create().balanced_deal)

    def test_the_form_can_ask_for_it(self):
        self.assertTrue(self.create(balanced_deal=True).balanced_deal)

    def test_the_lobby_cannot_change_it(self):
        """Seats already dealt the other way would stay so: a game of two deals."""
        game = self.create()

        with muted():
            self.client.patch(
                f"/api/game/{game.game_id}/",
                json.dumps({"balanced_deal": True}),
                content_type="application/json",
            )

        game.refresh_from_db()
        self.assertFalse(game.balanced_deal)


class HomesOntoGruppenMigrationTests(TempMediaRootMixin, TestCase):
    """Seats dealt before a Gruppe carried its own home."""

    def migrate(self):
        migration = importlib.import_module("game.migrations.0024_ausbalanciert")
        migration.homes_onto_gruppen(apps, None)

    def test_the_seats_home_goes_onto_every_gruppe(self):
        with muted():
            game = create_game_session(create_host())
            player = Player.objects.create(game=game, name="Mia")
        Player.objects.filter(pk=player.pk).update(
            agent_assignments={
                "home_node": 7,
                "agents": [
                    {"id": 1, "destination_node": 8, "persona": 3},
                    {"id": 2, "destination_node": 9},
                ],
            }
        )

        self.migrate()

        player.refresh_from_db()
        self.assertEqual(
            player.agent_assignments,
            {
                "agents": [
                    {"id": 1, "home_node": 7, "destination_node": 8, "persona": 3},
                    {"id": 2, "home_node": 7, "destination_node": 9},
                ]
            },
        )

    def test_a_seat_without_a_deal_stays_without(self):
        with muted():
            game = create_game_session(create_host())
            player = Player.objects.create(game=game, name="Mia")
        Player.objects.filter(pk=player.pk).update(agent_assignments=None)

        self.migrate()

        player.refresh_from_db()
        self.assertIsNone(player.agent_assignments)
