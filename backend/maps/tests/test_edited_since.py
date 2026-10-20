"""A map knows it was edited after it was measured.

`GameMap.calibrated_at` says when the count was measured, `graph_edited_at`
when anything a measurement reads last changed: a node, an edge, a line (every
editor write ends in `graph_cache.invalidate`) or one of the map-row values in
`GameMap.STALES_CALIBRATION`. What a calibration writes back is no edit.
"""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from game.tests._helpers import TEST_BACKENDS

from maps.models import GameMap, StreetEdge
from maps.tests.test_versions import VersionFixtureMixin


@override_settings(**TEST_BACKENDS)
class EditedSinceCalibrationTests(VersionFixtureMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        self.build_map()
        GameMap.objects.filter(pk=self.game_map.pk).update(graph_edited_at=None)

    def row(self):
        return GameMap.objects.get(pk=self.game_map.pk)

    def patch_map(self, data):
        return self.client.patch(
            reverse("maps:gamemap-detail", kwargs={"pk": self.game_map.pk}),
            data=data,
            content_type="application/json",
        )

    def test_a_street_changed_in_the_editor_is_an_edit(self):
        street = StreetEdge.objects.get(edge=self.edge_a)

        response = self.client.patch(
            reverse(
                "maps:streetedge-detail",
                kwargs={"pk": self.game_map.pk, "streetedge_pk": street.pk},
            ),
            data={"speed_limit": 30},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNotNone(self.row().graph_edited_at)

    def test_a_node_dragged_in_the_editor_is_an_edit(self):
        node = self.nodes[0]

        response = self.client.patch(
            reverse(
                "maps:node-detail", kwargs={"pk": self.game_map.pk, "node_pk": node.pk}
            ),
            data={"x_position": 0.5},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNotNone(self.row().graph_edited_at)

    def test_a_line_chain_written_in_one_go_is_an_edit(self):
        """`bulk_create` fires no signal; the view drops the cache itself."""
        edges = [StreetEdge.objects.get(edge=e).pk for e in (self.edge_a, self.edge_b)]

        response = self.client.put(
            reverse(
                "maps:busline-edges",
                kwargs={"pk": self.game_map.pk, "busline_pk": self.bus.pk},
            ),
            data={"edges": edges},
            content_type="application/json",
        )

        self.assertIn(response.status_code, (200, 201), response.content)
        self.assertIsNotNone(self.row().graph_edited_at)

    def test_a_speed_changed_on_the_map_row_is_an_edit(self):
        for field, value in (
            ("walk_speed_kmh", 4),
            ("bike_speed_kmh", 18),
            ("default_car_speed_kmh", 40),
            ("scale", 2.0),
        ):
            with self.subTest(field=field):
                GameMap.objects.filter(pk=self.game_map.pk).update(graph_edited_at=None)

                response = self.patch_map({field: value})

                self.assertEqual(response.status_code, 200, response.content)
                self.assertIsNotNone(self.row().graph_edited_at)

    def test_a_calibration_written_back_is_no_edit(self):
        response = self.patch_map(
            {
                "district_commuters": 1_800,
                "timetable_factor": 0.4,
                "co2_table": {"100": 3.5, "0": 0.7},
                "calibrated_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
            }
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(self.row().graph_edited_at)
        self.assertEqual(self.row().district_commuters, 1_800)
        self.assertEqual(self.row().timetable_factor, 0.4)

    def test_a_rename_is_no_edit(self):
        response = self.patch_map({"name": "Ein anderer Name"})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(self.row().graph_edited_at)

    def test_a_form_sending_every_value_again_is_no_edit(self):
        """What counts is a changed value, not a field in the payload."""
        game_map = self.row()

        response = self.patch_map(
            {
                "walk_speed_kmh": game_map.walk_speed_kmh,
                "bike_speed_kmh": game_map.bike_speed_kmh,
                "default_car_speed_kmh": game_map.default_car_speed_kmh,
                "scale": game_map.scale,
            }
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(self.row().graph_edited_at)

    def test_it_is_due_when_the_edit_came_after_the_measurement(self):
        now = timezone.now()
        GameMap.objects.filter(pk=self.game_map.pk).update(
            calibrated_at=now - timedelta(hours=2),
            graph_edited_at=now - timedelta(hours=1),
        )
        self.assertTrue(self.row().edited_since_calibration)

        GameMap.objects.filter(pk=self.game_map.pk).update(
            calibrated_at=now - timedelta(minutes=5)
        )
        self.assertFalse(self.row().edited_since_calibration)

    def test_a_map_never_measured_or_never_edited_is_not_due(self):
        self.assertFalse(self.row().edited_since_calibration)
        GameMap.objects.filter(pk=self.game_map.pk).update(
            graph_edited_at=timezone.now()
        )
        self.assertFalse(self.row().edited_since_calibration)

    def test_the_api_says_it_and_staff_cannot_write_the_edit_date(self):
        response = self.patch_map({"graph_edited_at": timezone.now().isoformat()})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(self.row().graph_edited_at)
        body = self.client.get(
            reverse("maps:gamemap-detail", kwargs={"pk": self.game_map.pk})
        ).json()
        self.assertIs(body["edited_since_calibration"], False)
        self.assertIn("timetable_factor", body)

    def test_a_share_outside_0_and_1_is_refused(self):
        self.assertEqual(self.patch_map({"timetable_factor": 1.5}).status_code, 400)
        self.assertEqual(self.patch_map({"timetable_factor": -0.1}).status_code, 400)

    def test_a_measurement_in_the_future_is_refused(self):
        future = (timezone.now() + timedelta(days=1)).isoformat()

        self.assertEqual(self.patch_map({"calibrated_at": future}).status_code, 400)

    def test_an_import_is_no_edit(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        graph = {
            "scale": 1000.0,
            "map": {"name": "Kiez", "x_dim": 13, "y_dim": 10},
            "nodes": [
                {"id": "a", "name": "A", "x": 0, "y": 0, "types": []},
                {"id": "b", "name": "B", "x": 1, "y": 0, "types": []},
            ],
            "edges": [{"start_node": "a", "end_node": "b", "type": "street"}],
            "bus_lines": [],
            "train_lines": [],
        }
        upload = SimpleUploadedFile(
            "kiez.json", json.dumps(graph).encode(), content_type="application/json"
        )

        response = self.client.post(
            "/api/maps/import/",
            {
                "map_name": "Kiez",
                "description": "",
                "max_players": 16,
                "json_file": upload,
            },
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(GameMap.objects.get(pk=response.json()["id"]).graph_edited_at)
