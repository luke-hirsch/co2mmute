"""The admin's "add" page for the rows a map is made of.

A new row has no primary key, and its `clean()` read the versions it belongs to
before it had one — which a many-to-many refuses. The page answered 500.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from maps.models import BusLine, Edge, GameMap, MapVersion, Node, NodeType, TrainLine


class AdminAddTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="admin", password="password123"
        )
        self.client.force_login(user)
        self.game_map = GameMap.objects.create(name="Karte", x_dim=10, y_dim=10)
        self.version = MapVersion.objects.create(
            game_map=self.game_map, name="Basis", base_version=True
        )
        self.kind = NodeType.objects.create(name="Kreuzung", short="K")
        self.a = Node.objects.create(game_map=self.game_map, x_position=1, y_position=1)
        self.b = Node.objects.create(game_map=self.game_map, x_position=2, y_position=2)

    def add(self, model):
        return reverse(f"admin:maps_{model}_add")

    def test_the_add_page_of_each_opens(self):
        for model in ("node", "edge", "busline", "trainline"):
            with self.subTest(model=model):
                self.assertEqual(self.client.get(self.add(model)).status_code, 200)

    def test_a_node_can_be_added(self):
        response = self.client.post(
            self.add("node"),
            {
                "game_map": self.game_map.pk,
                "map_versions": [self.version.pk],
                "map_versions": [self.version.pk],
                "node_type": [self.kind.pk],
                "x_position": 3,
                "y_position": 4,
            },
        )

        self.assertEqual(response.status_code, 302, response.content[:300])
        self.assertEqual(Node.objects.filter(game_map=self.game_map).count(), 3)

    def test_an_edge_can_be_added(self):
        response = self.client.post(
            self.add("edge"),
            {
                "game_map": self.game_map.pk,
                "map_versions": [self.version.pk],
                "start_node": self.a.pk,
                "end_node": self.b.pk,
                "biking": "on",
                "walking": "on",
                "max_lanes": 1,
                "circuity": 1.0,
            },
        )

        self.assertEqual(response.status_code, 302, response.content[:300])
        self.assertEqual(Edge.objects.filter(game_map=self.game_map).count(), 1)

    def test_a_bus_line_can_be_added(self):
        response = self.client.post(
            self.add("busline"),
            {
                "game_map": self.game_map.pk,
                "map_versions": [self.version.pk],
                "name": "M1",
                "intervall": 5,
                "bus_capacity": 85,
                "bus_speed_kmh": 30,
            },
        )

        self.assertEqual(response.status_code, 302, response.content[:300])
        self.assertEqual(BusLine.objects.filter(game_map=self.game_map).count(), 1)

    def test_a_train_line_can_be_added(self):
        response = self.client.post(
            self.add("trainline"),
            {
                "game_map": self.game_map.pk,
                "map_versions": [self.version.pk],
                "name": "U2",
                "kind": "train",
                "intervall": 5,
                "train_capacity": 1000,
                "train_speed_kmh": 40,
            },
        )

        self.assertEqual(response.status_code, 302, response.content[:300])
        self.assertEqual(TrainLine.objects.filter(game_map=self.game_map).count(), 1)
