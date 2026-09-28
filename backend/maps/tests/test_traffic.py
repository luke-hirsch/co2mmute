"""Last round's observed speeds, on their way to the route preview.

`StreetPerRound.speed_under_load` has been written since the beginning and read
by nobody; on the other side `PathfindingOptions.trafficData` was threaded all
the way through the frontend with nothing ever supplying a value. So
"schnellste" was computed on a graph that had never seen a jam — the loop the
README describes as routing "unter der Auslastung der letzten Runde" did not
exist end to end.

`serialize_previous_round_traffic` is the join between the two halves, and
until S6 **nothing tested it on either side**. These pin the contract the
frontend now reads: the shape of a row, which round it comes from, and the three
ways it is legitimately empty — because an empty list is what round one looks
like, and a bug that empties it looks exactly the same on screen.
"""

from django.test import TestCase

from game.models import GameRound, SimulationResult
from game.tests._helpers import create_game_session, create_host
from maps.models import Edge, GameMap, MapVersion, Node, StreetEdge, StreetPerRound
from maps.serializer import serialize_previous_round_traffic


class PreviousRoundTrafficTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.game_map = GameMap.objects.create(name="Traffic map", x_dim=10, y_dim=10)
        cls.version = MapVersion.objects.create(
            game_map=cls.game_map, name="base", base_version=True
        )
        cls.a = Node.objects.create(
            game_map=cls.game_map, name="A", x_position=0, y_position=0
        )
        cls.b = Node.objects.create(
            game_map=cls.game_map, name="B", x_position=1, y_position=0
        )
        # Padding, so `Edge.pk` and `StreetEdge.pk` cannot coincide. Both tables
        # start at 1, so a fixture with one row of each makes the two ids equal
        # and the join below passes whichever field it reads — which is exactly
        # how a test comes to assert nothing. Verified by mutation.
        for i in range(3):
            Edge.objects.create(
                game_map=cls.game_map, name=f"pad{i}", start_node=cls.a, end_node=cls.b
            )

        cls.edge = Edge.objects.create(
            game_map=cls.game_map, name="A-B", start_node=cls.a, end_node=cls.b
        )
        cls.street = StreetEdge.objects.create(edge=cls.edge, speed_limit=50, lanes=2)
        assert cls.street.pk != cls.edge.pk, "fixture no longer separates the two pks"

        cls.host = create_host()
        cls.game = create_game_session(cls.host, game_map=cls.game_map)

    def _round(self, number, *, completed=True):
        game_round = GameRound.objects.create(game=self.game, round_number=number)
        SimulationResult.objects.create(
            game_round=game_round,
            status=(
                SimulationResult.Status.COMPLETED
                if completed
                else SimulationResult.Status.RUNNING
            ),
        )
        return game_round

    def test_a_row_carries_the_three_fields_the_router_reads(self):
        game_round = self._round(1)
        StreetPerRound.objects.create(
            edge=self.street, game_round=game_round, speed_under_load=25
        )

        rows = serialize_previous_round_traffic(self.game.game_id)

        # The keys are camelCase because `EdgeTrafficData` in the frontend is,
        # and `calculateEdgeWeight` reads `edgeId` and `avgSpeedKmh` by name.
        self.assertEqual(
            rows,
            [{"edgeId": self.edge.pk, "avgSpeedKmh": 25, "congestionLevel": "medium"}],
        )

    def test_the_edge_is_the_graph_edge_not_the_street_row(self):
        """The frontend joins on `Edge.id`, which is what the graph ships.

        `StreetPerRound.edge` is a `StreetEdge`, a different table with its own
        pks. Serialising that one would produce a list that joins against
        nothing and silently routes on free flow everywhere.
        """
        game_round = self._round(1)
        StreetPerRound.objects.create(
            edge=self.street, game_round=game_round, speed_under_load=30
        )

        (row,) = serialize_previous_round_traffic(self.game.game_id)

        self.assertEqual(row["edgeId"], self.edge.pk)

    def test_it_serves_the_last_completed_round(self):
        first = self._round(1)
        second = self._round(2)
        StreetPerRound.objects.create(
            edge=self.street, game_round=first, speed_under_load=10
        )
        StreetPerRound.objects.create(
            edge=self.street, game_round=second, speed_under_load=40
        )

        (row,) = serialize_previous_round_traffic(self.game.game_id)

        self.assertEqual(row["avgSpeedKmh"], 40)

    def test_a_round_still_running_is_not_the_one_reported(self):
        done = self._round(1)
        running = self._round(2, completed=False)
        StreetPerRound.objects.create(
            edge=self.street, game_round=done, speed_under_load=10
        )
        StreetPerRound.objects.create(
            edge=self.street, game_round=running, speed_under_load=40
        )

        (row,) = serialize_previous_round_traffic(self.game.game_id)

        self.assertEqual(row["avgSpeedKmh"], 10)

    def test_the_congestion_level_is_measured_against_this_street_s_own_limit(self):
        """A Tempo-30 street at 30 is empty, not jammed.

        `berlin_base_v2` has 36 edges at 30. Scored against a network-wide 50
        every one of them would report congestion while free-flowing.
        """
        slow = Edge.objects.create(
            game_map=self.game_map, name="slow", start_node=self.b, end_node=self.a
        )
        slow_street = StreetEdge.objects.create(edge=slow, speed_limit=30, lanes=1)
        game_round = self._round(1)
        StreetPerRound.objects.create(
            edge=slow_street, game_round=game_round, speed_under_load=30
        )

        (row,) = serialize_previous_round_traffic(self.game.game_id)

        self.assertEqual(row["congestionLevel"], "low")

    def test_round_one_has_nothing_to_report(self):
        self.assertEqual(serialize_previous_round_traffic(self.game.game_id), [])

    def test_no_game_is_an_empty_list_rather_than_an_error(self):
        # The graph endpoint serves the same payload with or without `?game=`,
        # so the map editor and the detail page must not blow up on it.
        self.assertEqual(serialize_previous_round_traffic(None), [])
        self.assertEqual(serialize_previous_round_traffic("nope"), [])

    def test_one_game_never_sees_another_game_s_traffic(self):
        """The graph is shared between games; the traffic never is.

        Both games sit on the same map version, whose graph the backend caches
        for an hour under map + version. If the traffic were inside that cache
        the second game would route on the first one's jams — and keep routing
        on them after its own round had run.
        """
        other = create_game_session(self.host, game_map=self.game_map)
        mine = self._round(1)
        StreetPerRound.objects.create(
            edge=self.street, game_round=mine, speed_under_load=12
        )

        self.assertEqual(serialize_previous_round_traffic(other.game_id), [])
        self.assertEqual(len(serialize_previous_round_traffic(self.game.game_id)), 1)


class GraphEndpointTrafficTests(TestCase):
    """The same thing through the endpoint the SPA actually calls."""

    @classmethod
    def setUpTestData(cls):
        cls.game_map = GameMap.objects.create(name="Endpoint map", x_dim=10, y_dim=10)
        cls.version = MapVersion.objects.create(
            game_map=cls.game_map, name="base", base_version=True
        )
        a = Node.objects.create(
            game_map=cls.game_map, name="A", x_position=0, y_position=0
        )
        b = Node.objects.create(
            game_map=cls.game_map, name="B", x_position=1, y_position=0
        )
        a.map_versions.add(cls.version)
        b.map_versions.add(cls.version)
        # Same padding as above: the two pks must not line up.
        for i in range(3):
            Edge.objects.create(
                game_map=cls.game_map, name=f"pad{i}", start_node=a, end_node=b
            )
        cls.edge = Edge.objects.create(
            game_map=cls.game_map, name="A-B", start_node=a, end_node=b
        )
        cls.edge.map_versions.add(cls.version)
        cls.street = StreetEdge.objects.create(edge=cls.edge, speed_limit=50, lanes=2)

        cls.host = create_host()
        cls.game = create_game_session(cls.host, game_map=cls.game_map)
        game_round = GameRound.objects.create(game=cls.game, round_number=1)
        SimulationResult.objects.create(
            game_round=game_round, status=SimulationResult.Status.COMPLETED
        )
        StreetPerRound.objects.create(
            edge=cls.street, game_round=game_round, speed_under_load=18
        )

    def setUp(self):
        # The graph is cached for an hour under map + version, and these two
        # tests ask for the same one.
        from django.core.cache import cache

        cache.clear()

    def _url(self, query=""):
        return (
            f"/api/maps/{self.game_map.pk}/graph/version/{self.version.pk}/{query}"
        )

    def test_without_a_game_the_traffic_is_empty(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["previous_round_traffic"], [])

    def test_with_a_game_it_carries_that_game_s_last_round(self):
        response = self.client.get(self._url(f"?game={self.game.game_id}"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["previous_round_traffic"],
            [{"edgeId": self.edge.pk, "avgSpeedKmh": 18, "congestionLevel": "high"}],
        )

    def test_the_cached_graph_does_not_freeze_the_traffic_into_it(self):
        """The traffic is attached outside the cache, so it must survive a hit.

        The first call populates `map_graph:<map>:<version>`; the second is
        served from it. If the traffic had been cached with the graph, the
        second call would carry whatever the first one was asked for — here,
        nothing.
        """
        self.client.get(self._url())

        response = self.client.get(self._url(f"?game={self.game.game_id}"))

        self.assertEqual(len(response.json()["previous_round_traffic"]), 1)
