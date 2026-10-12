"""The graph endpoint after a write: what the editor reads back.

`GET graph/…` is cached for an hour under map + version, and the map editor
reads its own writes back through it. Until F10 only a `Node` or `Edge` save
cleared that cache, so every other write the editor makes — a street or a
railway under an edge, a change to a street — was saved and then not shown:
"+ Straße anlegen" answered 201 twice and the panel still offered "+ Straße
anlegen", for up to an hour or until some unrelated node was dragged. Clicking
it again wrote a second street row under the same edge.

The second half is a race the first fix alone would leave open. The editor
refetches the graph after every write, and building it takes long enough (about
1.7 s on the shipped map) for the next write to land in the middle. A read that
began before a write and stores its graph after it put the old graph back into
the cache — for an hour. So the cache key carries a generation that every write
moves, and a read stores under the generation it started with.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from game.tests._helpers import TEST_BACKENDS
from maps import views_rest
from maps.models import Edge, Node, StreetEdge, TrainEdge, TrainLine
from maps.tests.test_versions import VersionFixtureMixin


@override_settings(**TEST_BACKENDS)
class GraphAfterAWriteTests(VersionFixtureMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        self.build_map()
        # A path: neither a street nor a railway under it yet.
        self.path = self._edge("P", 0, 2, street=False, rail=False)

    def graph(self):
        response = self.client.get(
            reverse("maps:mapversion-graph", kwargs={"pk": self.game_map.pk})
        )
        self.assertEqual(response.status_code, 200)
        return {edge["id"]: edge for edge in response.json()["edges"]}

    def post(self, name, data):
        response = self.client.post(
            reverse(name, kwargs={"pk": self.game_map.pk}),
            data=data,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_a_street_laid_under_an_edge_shows_on_the_next_read(self):
        """`+ Straße anlegen`, as the editor sends it."""
        self.assertIsNone(self.graph()[self.path.pk]["street_edge"])

        self.post(
            "maps:streetedge-list",
            {
                "edge": self.path.pk,
                "speed_limit": 50,
                "lanes": 1,
                "dedicated_bus_lane": False,
                "map_versions": [self.base.pk],
            },
        )

        self.assertIsNotNone(self.graph()[self.path.pk]["street_edge"])

    def test_a_railway_laid_under_an_edge_shows_on_the_next_read(self):
        self.assertIsNone(self.graph()[self.path.pk]["train_edge"])

        self.post(
            "maps:trainedge-list",
            {"edge": self.path.pk, "map_versions": [self.base.pk]},
        )

        self.assertIsNotNone(self.graph()[self.path.pk]["train_edge"])

    def test_a_changed_street_shows_on_the_next_read(self):
        """The panel's Speichern sends the street's half as its own PATCH."""
        street = StreetEdge.objects.get(edge=self.edge_a)
        self.assertEqual(self.graph()[self.edge_a.pk]["street_edge"]["speed_limit"], 50)

        response = self.client.patch(
            reverse(
                "maps:streetedge-detail",
                kwargs={"pk": self.game_map.pk, "streetedge_pk": street.pk},
            ),
            data={"speed_limit": 30},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        self.assertEqual(self.graph()[self.edge_a.pk]["street_edge"]["speed_limit"], 30)

    def test_a_removed_railway_is_gone_on_the_next_read(self):
        train = TrainEdge.objects.get(edge=self.edge_b)
        self.assertIsNotNone(self.graph()[self.edge_b.pk]["train_edge"])

        response = self.client.delete(
            reverse(
                "maps:trainedge-detail",
                kwargs={"pk": self.game_map.pk, "trainedge_pk": train.pk},
            )
        )
        self.assertEqual(response.status_code, 204)

        self.assertIsNone(self.graph()[self.edge_b.pk]["train_edge"])

    def test_a_row_joining_the_version_shows_on_the_next_read(self):
        """Membership is an m2m, and an m2m add saves no row at all.

        Every version write — the diff endpoint, the combinations, the importer —
        is a `map_versions.add`, so a cache cleared only on `post_save` would
        miss all of them.
        """
        edge = Edge.objects.create(
            game_map=self.game_map,
            start_node=self.nodes[3],
            end_node=self.nodes[0],
            walking=True,
        )
        self.assertNotIn(edge.pk, self.graph())

        edge.map_versions.add(self.base)

        self.assertIn(edge.pk, self.graph())

    def test_a_read_that_began_before_a_write_cannot_keep_the_old_graph(self):
        """The race, reproduced in one thread.

        The write lands while the read is building the graph — after the edges
        have been read, before the result is stored. The read itself answers
        with what it read, which is fine: the editor refetches after the write
        anyway. What must not happen is that its answer is what the *next* read
        gets from the cache. Nothing has read the graph since `setUp` drew the
        path, so this read builds it rather than finding it stored.
        """
        real = views_rest.serialize_bus_line_for_graph
        wrote = []

        def write_in_the_middle(*args, **kwargs):
            if not wrote:
                street = StreetEdge.objects.create(edge=self.path, speed_limit=50)
                street.map_versions.add(self.base)
                wrote.append(street)
            return real(*args, **kwargs)

        with mock.patch.object(
            views_rest, "serialize_bus_line_for_graph", write_in_the_middle
        ):
            first = self.graph()

        self.assertTrue(wrote, "the patch must have run inside the read")
        self.assertIsNone(first[self.path.pk]["street_edge"])
        self.assertIsNotNone(self.graph()[self.path.pk]["street_edge"])

    def test_the_graph_does_not_cost_a_query_per_row(self):
        """1 832 queries for one graph of the shipped map, 1 811 of them a version.

        Every node and edge serialises its whole version list, and each version
        its ballot neighbours. Harmless while the graph was read once an hour;
        since F10 the editor waits for a fresh one after every write. Counted
        twice rather than pinned to a number: what must not happen is that the
        count grows with the map.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def queries_for_a_fresh_graph():
            self.edge_c.save()  # any write: the next read rebuilds
            with CaptureQueriesContext(connection) as ctx:
                self.graph()
            return len(ctx.captured_queries)

        small = queries_for_a_fresh_graph()
        for i in range(6):
            node = Node.objects.create(
                game_map=self.game_map, name=f"X{i}", x_position=i, y_position=5
            )
            node.map_versions.add(self.base)
            self.nodes.append(node)
            self._edge(f"X{i}", len(self.nodes) - 1, 0, street=True, rail=True)

        self.assertEqual(queries_for_a_fresh_graph(), small)


@override_settings(**TEST_BACKENDS)
class TramWritesTests(VersionFixtureMixin, TestCase):
    """What the editor writes for a tram: the street's track, the line's kind.

    Edge B is street and rail; edge A is a street with no rails under it.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        self.build_map()

    def patch_street(self, edge, data):
        street = StreetEdge.objects.get(edge=edge)
        return self.client.patch(
            reverse(
                "maps:streetedge-detail",
                kwargs={"pk": self.game_map.pk, "streetedge_pk": street.pk},
            ),
            data=data,
            content_type="application/json",
        )

    def graph_street(self, edge):
        response = self.client.get(
            reverse("maps:mapversion-graph", kwargs={"pk": self.game_map.pk})
        )
        edges = {e["id"]: e for e in response.json()["edges"]}
        return edges[edge.pk]["street_edge"]

    def test_rails_in_the_car_lane_are_set_on_the_street(self):
        response = self.patch_street(self.edge_b, {"tram_track": "lane"})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.graph_street(self.edge_b)["tram_track"], "lane")

    def test_a_street_with_no_rails_under_it_refuses_a_track(self):
        response = self.patch_street(self.edge_a, {"tram_track": "own"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("tram_track", response.json())
        self.assertEqual(StreetEdge.objects.get(edge=self.edge_a).tram_track, "")

    def test_taking_the_rails_away_takes_the_track_with_them(self):
        """Or the street would keep a lane reserved for a tram that has no rails."""
        self.patch_street(self.edge_b, {"tram_track": "own"})
        rails = TrainEdge.objects.get(edge=self.edge_b)

        response = self.client.delete(
            reverse(
                "maps:trainedge-detail",
                kwargs={"pk": self.game_map.pk, "trainedge_pk": rails.pk},
            )
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(StreetEdge.objects.get(edge=self.edge_b).tram_track, "")
        self.assertEqual(self.graph_street(self.edge_b)["tram_track"], "")

    def test_a_train_line_is_written_with_its_kind(self):
        response = self.client.post(
            reverse("maps:trainline-list", kwargs={"pk": self.game_map.pk}),
            data={
                "game_map": self.game_map.pk,
                "name": "M1",
                "kind": "tram",
                "intervall": 10,
                "train_capacity": 248,
                "train_speed_kmh": 30,
                "map_versions": [self.base.pk],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(TrainLine.objects.get(name="M1").kind, "tram")
        self.assertEqual(response.json()["kind"], "tram")


@override_settings(**TEST_BACKENDS)
class RoadLengthTests(VersionFixtureMixin, TestCase):
    """What the router reads as an edge's length: the road, not the line.

    `circuity` is the road's length over the straight line between its two
    nodes. Stored as that ratio, the road moves with its nodes: drag one and
    the bends come along (Lukas, 2026-10-12: the length scales).

    Edge A runs N0 → N1, one unit on a map of 500 m per unit.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        self.build_map()
        self.game_map.scale = 500.0
        self.game_map.save()

    def graph(self):
        response = self.client.get(
            reverse("maps:mapversion-graph", kwargs={"pk": self.game_map.pk})
        )
        self.assertEqual(response.status_code, 200)
        return {edge["id"]: edge for edge in response.json()["edges"]}

    def draw_edge(self, start, end, **fields):
        return self.client.post(
            reverse("maps:edge-list", kwargs={"pk": self.game_map.pk}),
            data={
                "game_map": self.game_map.pk,
                "start_node": self.nodes[start].pk,
                "end_node": self.nodes[end].pk,
                "map_versions": [self.base.pk],
                **fields,
            },
            content_type="application/json",
        )

    def patch_edge(self, edge, data):
        return self.client.patch(
            reverse(
                "maps:edge-detail",
                kwargs={"pk": self.game_map.pk, "edge_pk": edge.pk},
            ),
            data=data,
            content_type="application/json",
        )

    def test_an_edge_that_says_nothing_is_its_straight_line(self):
        self.assertAlmostEqual(self.graph()[self.edge_a.pk]["distance_m"], 500.0)

    def test_the_graph_gives_the_road_its_length(self):
        Edge.objects.filter(pk=self.edge_a.pk).update(circuity=1.3)

        self.assertAlmostEqual(self.graph()[self.edge_a.pk]["distance_m"], 650.0)

    def test_dragging_a_node_scales_the_road_with_it(self):
        Edge.objects.filter(pk=self.edge_a.pk).update(circuity=1.3)

        response = self.client.patch(
            reverse(
                "maps:node-detail",
                kwargs={"pk": self.game_map.pk, "node_pk": self.nodes[1].pk},
            ),
            data={"x_position": 2.0},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertAlmostEqual(self.graph()[self.edge_a.pk]["distance_m"], 1300.0)

    def test_an_edge_is_drawn_with_its_road(self):
        """What "+ Gegenrichtung anlegen" sends: the other way down the same road."""
        response = self.draw_edge(1, 0, circuity=1.3)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Edge.objects.get(pk=response.json()["id"]).circuity, 1.3)

    def test_both_directions_drawn_at_once_run_down_one_road(self):
        response = self.draw_edge(0, 2, circuity=1.3, bidirectional=True)

        self.assertEqual(response.status_code, 201, response.content)
        back = Edge.objects.get(start_node=self.nodes[2], end_node=self.nodes[0])
        self.assertEqual(back.circuity, 1.3)

    def test_a_road_shorter_than_its_straight_line_is_refused(self):
        response = self.patch_edge(self.edge_a, {"circuity": 0.9})

        self.assertEqual(response.status_code, 400)
        self.assertIn("circuity", response.json())
        self.assertEqual(Edge.objects.get(pk=self.edge_a.pk).circuity, 1.0)
