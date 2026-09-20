"""A map has to survive leaving the box it was drawn on.

JSON in and out is the only way a map moves between installations, and today
the round trip drops the background image and the dimensions it is placed
against. Nodes and edges arrive, the picture does not — and the picture is what
makes the graph look like a real place.

These tests pin both halves and, most of all, the round trip: export a map,
import that file, and every field that describes the image has to come back
identical, bytes included.

First real tests in `maps/tests/`; the package was an empty stub until now.
`TempMediaRootMixin` comes from `game/tests/_helpers.py`, which is the shared
fixture module for the whole project — writing image files into the real media
directory during a test run is exactly what it exists to prevent.
"""

import base64
import json

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from game.tests._helpers import TempMediaRootMixin
from maps.models import Edge, GameMap, MapVersion, Node

# Two real 2x2 PNGs, blue and red. `image_file` on the upload form is an
# ImageField, so Pillow opens whatever is posted — a handmade byte string that
# only looks like a PNG fails form validation and the test goes red for the
# wrong reason.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGPkCjjBwMDAxMDAwMDAAAANBAEmTo7dTAAAAABJRU5ErkJggg=="
)
OTHER_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8YCPCwMDAxMDAwMDAAAAQBgFEKHuU0QAAAABJRU5ErkJggg=="
)


def make_map(name="Berlin 3", *, with_image=True, **overrides):
    """A map with two nodes, one edge, and (by default) a placed image."""
    fields = {
        "name": name,
        "x_dim": 7,
        "y_dim": 5,
        "scale": 120.0,
        "max_player": 6,
        "walk_speed_kmh": 4,
        "bike_speed_kmh": 18,
        "default_car_speed_kmh": 45,
    }
    if with_image:
        # The placement of the live "Berlin 3": none of it is a default, so a
        # test that passes cannot be passing on defaults.
        fields.update(
            image_scale=2.11,
            image_offset_x=0.5,
            image_offset_y=-1.4,
            image_crop_top=3.0,
            image_crop_right=4.0,
            image_crop_bottom=5.0,
            image_crop_left=6.0,
        )
    fields.update(overrides)

    game_map = GameMap.objects.create(**fields)
    if with_image:
        game_map.background_image.save("berlin3.png", ContentFile(PNG_BYTES), save=True)

    version = MapVersion.objects.create(
        game_map=game_map, name=f"{name} - Base", base_version=True
    )

    home = Node.objects.create(
        game_map=game_map, name="Zuhause", x_position=1.0, y_position=1.0
    )
    work = Node.objects.create(
        game_map=game_map, name="Arbeit", x_position=3.0, y_position=2.0
    )
    for node in (home, work):
        node.map_versions.add(version)

    edge = Edge.objects.create(
        game_map=game_map,
        name="Hauptstraße",
        start_node=home,
        end_node=work,
        walking=True,
        biking=True,
    )
    edge.map_versions.add(version)

    return game_map, version


class MapExportPortabilityTests(TempMediaRootMixin, TestCase):
    """What `GET api/maps/<pk>/export/` has to put in the file."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)

    def export(self, game_map):
        response = self.client.get(
            reverse("maps:map-export", kwargs={"pk": game_map.pk})
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_export_carries_the_map_itself(self):
        game_map, _ = make_map()

        data = self.export(game_map)

        self.assertIn("map", data)
        self.assertEqual(data["map"]["name"], "Berlin 3")
        self.assertEqual(data["map"]["x_dim"], 7)
        self.assertEqual(data["map"]["y_dim"], 5)
        self.assertEqual(data["map"]["max_player"], 6)
        self.assertEqual(data["map"]["walk_speed_kmh"], 4)
        self.assertEqual(data["map"]["bike_speed_kmh"], 18)
        self.assertEqual(data["map"]["default_car_speed_kmh"], 45)

    def test_export_keeps_the_graph_keys_at_the_top_level(self):
        # The upload path reads these where they have always been. Moving them
        # under "map" would break every JSON already in map_examples/.
        game_map, _ = make_map()

        data = self.export(game_map)

        self.assertEqual(data["scale"], 120.0)
        for key in ("nodes", "edges", "bus_lines", "train_lines"):
            self.assertIn(key, data)
        self.assertEqual(len(data["nodes"]), 2)
        self.assertEqual(len(data["edges"]), 1)

    def test_export_carries_the_image_and_where_it_sits(self):
        game_map, _ = make_map()

        block = self.export(game_map)["background_image"]

        self.assertEqual(base64.b64decode(block["data"]), PNG_BYTES)
        self.assertEqual(block["scale"], 2.11)
        self.assertEqual(block["offset_x"], 0.5)
        self.assertEqual(block["offset_y"], -1.4)
        self.assertEqual(block["crop_top"], 3.0)
        self.assertEqual(block["crop_right"], 4.0)
        self.assertEqual(block["crop_bottom"], 5.0)
        self.assertEqual(block["crop_left"], 6.0)
        self.assertTrue(block["filename"].endswith(".png"))

    def test_export_of_a_map_without_an_image_has_no_image_key(self):
        # Not `null`, not an empty block: the importer decides on presence.
        game_map, _ = make_map("Ohne Bild", with_image=False)

        self.assertNotIn("background_image", self.export(game_map))

    def test_export_survives_an_image_file_that_is_gone(self):
        # A media directory that was reset leaves the field set and the file
        # missing. The placement is still worth having, and a 500 here would
        # make the map unexportable for good.
        game_map, _ = make_map()
        game_map.background_image.storage.delete(game_map.background_image.name)

        block = self.export(game_map)["background_image"]

        self.assertNotIn("data", block)
        self.assertEqual(block["scale"], 2.11)
        self.assertEqual(block["offset_x"], 0.5)


class MapImportPortabilityTests(TempMediaRootMixin, TestCase):
    """What `/map/upload/` has to read back out of that file."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)

    def upload(self, payload, name="Importiert", image=None, max_players=4):
        """Post the upload form the way the page does.

        `map_name` and `max_players` are required fields on MapUploadForm; leave
        either out and the form simply fails validation, which would make every
        test below red for a reason that has nothing to do with portability.
        """
        files = {
            "json_file": ContentFile(
                json.dumps(payload).encode("utf-8"), name="map.json"
            )
        }
        if image is not None:
            files["image_file"] = image
        response = self.client.post(
            reverse("map-upload"),
            {"map_name": name, "max_players": max_players, "description": "", **files},
            follow=True,
        )
        self.assertIn(response.status_code, (200, 302))
        return self.uploaded_map(name, response)

    def uploaded_map(self, name, response):
        """The map the upload made — or why the form refused it.

        A bare DoesNotExist here says nothing; the upload view answers an
        invalid form by re-rendering it and a rejected JSON by adding a message,
        so both are worth printing when the map is missing.
        """
        game_map = GameMap.objects.filter(name=name).order_by("-created").first()
        if game_map is not None:
            return game_map

        context = getattr(response, "context", None) or {}
        form = context.get("form")
        notes = [str(m) for m in context.get("messages", [])]
        raise AssertionError(
            f"upload created no map named {name!r}. "
            f"form errors: {getattr(form, 'errors', None)}; messages: {notes}"
        )

    def graph_payload(self, **extra):
        return {
            "scale": 120.0,
            "nodes": [
                {"id": "1", "name": "Zuhause", "x": 1.0, "y": 1.0},
                {"id": "2", "name": "Arbeit", "x": 3.0, "y": 2.0},
            ],
            "edges": [
                {
                    "start_node": "1",
                    "end_node": "2",
                    "name": "Hauptstraße",
                    "walking": True,
                    "biking": True,
                }
            ],
            "bus_lines": [],
            "train_lines": [],
            **extra,
        }

    def test_import_reads_the_image_and_its_placement(self):
        payload = self.graph_payload(
            background_image={
                "data": base64.b64encode(PNG_BYTES).decode("ascii"),
                "filename": "berlin3.png",
                "scale": 2.11,
                "offset_x": 0.5,
                "offset_y": -1.4,
                "crop_top": 3.0,
                "crop_right": 4.0,
                "crop_bottom": 5.0,
                "crop_left": 6.0,
            }
        )

        game_map = self.upload(payload)

        self.assertTrue(game_map.background_image)
        with game_map.background_image.open("rb") as fh:
            self.assertEqual(fh.read(), PNG_BYTES)
        self.assertAlmostEqual(game_map.image_scale, 2.11)
        self.assertAlmostEqual(game_map.image_offset_x, 0.5)
        self.assertAlmostEqual(game_map.image_offset_y, -1.4)
        self.assertAlmostEqual(game_map.image_crop_top, 3.0)
        self.assertAlmostEqual(game_map.image_crop_left, 6.0)

    def test_import_takes_the_dimensions_from_the_file(self):
        # Without this the importer recomputes x_dim/y_dim from the node
        # coordinates (maps/views.py, _create_nodes), which is the frame the
        # image is placed against — so a recomputed frame misplaces the image.
        payload = self.graph_payload(
            map={"name": "Berlin 3", "x_dim": 7, "y_dim": 5, "max_player": 6}
        )

        game_map = self.upload(payload)

        self.assertEqual(game_map.x_dim, 7)
        self.assertEqual(game_map.y_dim, 5)

    def test_an_uploaded_image_beats_the_one_in_the_file(self):
        payload = self.graph_payload(
            background_image={
                "data": base64.b64encode(PNG_BYTES).decode("ascii"),
                "filename": "from-json.png",
                "scale": 2.11,
            }
        )

        game_map = self.upload(
            payload, image=ContentFile(OTHER_PNG_BYTES, name="explicit.png")
        )

        with game_map.background_image.open("rb") as fh:
            self.assertEqual(fh.read(), OTHER_PNG_BYTES)

    def test_a_file_without_the_new_blocks_still_imports(self):
        # Everything in map_examples/ looks like this.
        game_map = self.upload(self.graph_payload())

        self.assertFalse(game_map.background_image)
        self.assertEqual(Node.objects.filter(game_map=game_map).count(), 2)
        self.assertEqual(Edge.objects.filter(game_map=game_map).count(), 1)

    def test_a_broken_image_does_not_cost_the_graph(self):
        # The graph is the expensive part; an image can be re-attached by hand.
        payload = self.graph_payload(
            background_image={"data": "not base64 at all !!", "scale": 2.11}
        )

        game_map = self.upload(payload)

        self.assertEqual(Node.objects.filter(game_map=game_map).count(), 2)
        self.assertFalse(game_map.background_image)


class MapRoundTripTests(TempMediaRootMixin, TestCase):
    """The thing that actually has to work: out of one box and into the next."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)

    def test_export_then_import_keeps_the_image_and_the_frame(self):
        original, _ = make_map("Berlin 3")

        exported = self.client.get(
            reverse("maps:map-export", kwargs={"pk": original.pk})
        ).json()

        response = self.client.post(
            reverse("map-upload"),
            {
                "map_name": "Berlin 3 (Kopie)",
                "max_players": 4,
                "description": "",
                "json_file": ContentFile(
                    json.dumps(exported).encode("utf-8"), name="map.json"
                ),
            },
            follow=True,
        )
        self.assertIn(response.status_code, (200, 302))

        copy = GameMap.objects.filter(name="Berlin 3 (Kopie)").order_by("-created").first()
        if copy is None:
            context = getattr(response, "context", None) or {}
            raise AssertionError(
                "the exported file did not import. "
                f"form errors: {getattr(context.get('form'), 'errors', None)}; "
                f"messages: {[str(m) for m in context.get('messages', [])]}"
            )

        with copy.background_image.open("rb") as fh:
            self.assertEqual(fh.read(), PNG_BYTES)
        self.assertEqual((copy.x_dim, copy.y_dim), (original.x_dim, original.y_dim))
        self.assertAlmostEqual(copy.image_scale, original.image_scale)
        self.assertAlmostEqual(copy.image_offset_x, original.image_offset_x)
        self.assertAlmostEqual(copy.image_offset_y, original.image_offset_y)
        self.assertAlmostEqual(copy.image_crop_top, original.image_crop_top)
        self.assertAlmostEqual(copy.image_crop_right, original.image_crop_right)
        self.assertAlmostEqual(copy.image_crop_bottom, original.image_crop_bottom)
        self.assertAlmostEqual(copy.image_crop_left, original.image_crop_left)
        self.assertEqual(copy.scale, original.scale)
        self.assertEqual(
            Node.objects.filter(game_map=copy).count(),
            Node.objects.filter(game_map=original).count(),
        )
