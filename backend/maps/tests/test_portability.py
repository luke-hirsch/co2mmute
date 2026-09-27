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
from maps.models import BusLine, Edge, GameMap, MapVersion, Node, TrainLine

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


class MapUploadMixin(TempMediaRootMixin):
    """Posting `/map/upload/` the way the page does.

    Extracted so the bike and rail tests below can upload a map without
    inheriting a test class and re-running its assertions under a second name.
    """

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


class MapImportPortabilityTests(MapUploadMixin, TestCase):
    """What `/map/upload/` has to read back out of that file."""

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


# ---------------------------------------------------------------------------
# The bike lane — see `.claude/plans/to-do/[backend]-bike-lane-and-traffic.md`.
#
# `Edge.biking` was carrying two meanings at once: *a bike may use this link*
# and *a bike is unimpeded on this link*. The first is access, the second is
# infrastructure, and a map could not tell them apart. `Edge.bike_lane` is the
# second one, and it has to survive the JSON round trip like every other field
# — export is the only way a map moves between boxes.
# ---------------------------------------------------------------------------


class BikeLaneTravelsTests(MapUploadMixin, TestCase):
    """`bike_lane` has to go into the file and come back out of it."""

    def street_payload(self, **edge_extra):
        payload = self.graph_payload()
        payload["edges"] = [
            {
                "start_node": "1",
                "end_node": "2",
                "name": "Hauptstraße",
                "type": "street",
                "lanes": 2,
                **edge_extra,
            }
        ]
        return payload

    def test_a_bike_lane_survives_the_import(self):
        game_map = self.upload(
            self.street_payload(bike_lane=True), name="Mit Radweg"
        )

        self.assertTrue(Edge.objects.get(game_map=game_map).bike_lane)

    def test_an_edge_that_does_not_mention_it_has_none(self):
        """The default is False everywhere, including on a path.

        Unlike `biking`, which is True by default because a bike may ride on
        an ordinary street, infrastructure is absent until a map says it is
        there. So no default needs flipping and no existing map changes
        meaning.
        """
        game_map = self.upload(self.street_payload(), name="Ohne Radweg")

        self.assertFalse(Edge.objects.get(game_map=game_map).bike_lane)

    def test_the_export_carries_the_bike_lane_back_out(self):
        game_map = self.upload(
            self.street_payload(bike_lane=True), name="Radweg Export"
        )

        response = self.client.get(
            reverse("maps:map-export", kwargs={"pk": game_map.pk})
        )

        self.assertEqual(response.json()["edges"][0]["bike_lane"], True)

    def test_the_export_carries_a_missing_bike_lane_too(self):
        """False has to be written out, not left out.

        A key that only appears when it is True re-imports as False anyway,
        which is the same value — but the file then stops describing the map
        and starts describing a diff against a default, and the next reader
        cannot tell "no bike lane" from "this exporter is older than the
        field".
        """
        game_map = self.upload(self.street_payload(), name="Radweg Export leer")

        response = self.client.get(
            reverse("maps:map-export", kwargs={"pk": game_map.pk})
        )

        self.assertEqual(response.json()["edges"][0]["bike_lane"], False)

    def test_the_graph_the_client_reads_carries_it(self):
        """`canUseEdge` and the map legend are on the other end of this.

        The editor checkbox and the game's own renderer both read the edge out
        of EdgeSerializer, so a field missing from that list exists in the
        database and nowhere a player can see it.
        """
        from maps.serializer import EdgeSerializer

        game_map = self.upload(
            self.street_payload(bike_lane=True), name="Radweg Graph"
        )
        edge = Edge.objects.get(game_map=game_map)

        self.assertEqual(EdgeSerializer(edge).data["bike_lane"], True)

    def test_a_bike_lane_without_access_is_refused(self):
        """The two contradict each other, so the file is wrong, not the reader.

        Lukas: "obviously we can't have a bike lane and not accessible by bike
        on the edge." Silently correcting it would let a map say one thing and
        play another; the import says no and names the edge.
        """
        from game.tests._helpers import muted

        payload = self.street_payload(bike_lane=True, biking=False)

        with muted():
            response = self.client.post(
                reverse("map-upload"),
                {
                    "map_name": "Widerspruch",
                    "max_players": 4,
                    "description": "",
                    "json_file": ContentFile(
                        json.dumps(payload).encode("utf-8"), name="map.json"
                    ),
                },
                follow=True,
            )
        notes = " ".join(
            str(m) for m in (getattr(response, "context", None) or {}).get(
                "messages", []
            )
        )

        self.assertFalse(GameMap.objects.filter(name="Widerspruch").exists())
        self.assertIn("bike_lane", notes)


class RailIsNotACycleTrackTests(MapUploadMixin, TestCase):
    """A railway is not a shortcut for bikes — unless it says it has a path.

    All 92 rail-only edges across the two maps in the dev database carry
    `biking=True` and `walking=True`, so the bike graph is the street network
    *plus* the rail alignment: the straightest, longest links on the map, with
    no junctions. Same origin and destination: car 8.4 km, bike 4.7 km.

    The first fix proposed was to force `biking=False` on every rail edge at
    import. The bike-lane split makes that wrong: a cycle path alongside a
    rail alignment is real and common — Lukas named the S-Bahn in the south of
    Berlin — and `bike_lane` is how a map says so. So the importer honours
    what the file says and the existing default does the work: an edge of type
    `train` that mentions neither flag arrives closed to both. The 92 edges
    that are wrong today are a data problem, fixed by the migration's pass and
    pinned in `test_models.py`.
    """

    def rail_payload(self, **edge_extra):
        payload = self.graph_payload()
        payload["edges"] = [
            {
                "start_node": "1",
                "end_node": "2",
                "name": "Stadtbahn",
                "type": "train",
                **edge_extra,
            }
        ]
        return payload

    def test_a_rail_edge_that_says_nothing_arrives_closed_to_bikes(self):
        game_map = self.upload(self.rail_payload(), name="Schiene")

        self.assertFalse(Edge.objects.get(game_map=game_map).biking)

    def test_a_rail_edge_that_says_nothing_arrives_closed_to_walkers(self):
        game_map = self.upload(self.rail_payload(), name="Schiene zu Fuss")

        self.assertFalse(Edge.objects.get(game_map=game_map).walking)

    def test_a_rail_alignment_may_carry_a_path_alongside(self):
        """The U-Bahn is closed to both; parts of the S-Bahn are not.

        This is the case that killed `StreetEdge.dedicated_bike_lane`: there
        is no street here at all, so the flag has to live on `Edge`.
        """
        payload = self.rail_payload(biking=True, walking=True, bike_lane=True)

        game_map = self.upload(payload, name="Schiene mit Weg")
        edge = Edge.objects.get(game_map=game_map)

        self.assertTrue(edge.biking)
        self.assertTrue(edge.walking)
        self.assertTrue(edge.bike_lane)

    def test_a_street_that_also_carries_rail_keeps_its_flags(self):
        """`type: "both"` is a real case — six edges on each shipped map.

        A tram alignment down a street is still a street: you can cycle on it,
        and blanket-clearing every edge that touches a TrainEdge would take
        those twelve off the bike network for no reason.
        """
        payload = self.rail_payload(type="both", speed_limit=30, lanes=2)

        game_map = self.upload(payload, name="Strasse mit Gleis")
        edge = Edge.objects.get(game_map=game_map)

        self.assertTrue(edge.biking)
        self.assertTrue(edge.walking)

    def test_an_ordinary_street_is_untouched(self):
        payload = self.rail_payload(type="street", lanes=1)

        game_map = self.upload(payload, name="Nur Strasse")
        edge = Edge.objects.get(game_map=game_map)

        self.assertTrue(edge.biking)
        self.assertTrue(edge.walking)


# ---------------------------------------------------------------------------
# The rest of the map block, and the lines.
#
# S2 read `district_commuters` and `co2_budget_kg_per_round` on the way in and
# named what it left behind: `_create_game_map` takes a `map_meta` argument that
# no caller passes, so `max_player` and the three speeds are written into every
# export and dropped by every import. A PT line's `speed_kmh` is the same story
# one level down — `_create_bus_lines` and `_create_train_lines` never read it,
# which is why every line on every imported map has run at the model default
# whatever its file said.
# ---------------------------------------------------------------------------


class MapBlockPortabilityTests(MapUploadMixin, TestCase):
    """Everything under `map` that is not the picture or the calibration pair."""

    def test_import_reads_max_player_from_the_file(self):
        """The file wins over the form field.

        `max_players` is a required field on the upload form with no default, so
        the host types *something* on every import — which means the form can
        never be "absent" and the file would never win if the form took
        precedence. What the map was drawn for is a property of the map.
        """
        payload = self.graph_payload(
            map={"name": "Berlin 3", "x_dim": 7, "y_dim": 5, "max_player": 6}
        )

        game_map = self.upload(payload, max_players=4)

        self.assertEqual(game_map.max_player, 6)

    def test_import_reads_the_three_speeds_from_the_file(self):
        """walk, bike and the car default: what the graph is measured with.

        A map whose walking speed is 4 km/h and whose streets default to 45
        arrives as 5 and 50, so every travel time on the new box differs from
        the box the map was drawn on.
        """
        payload = self.graph_payload(
            map={
                "name": "Berlin 3",
                "x_dim": 7,
                "y_dim": 5,
                "walk_speed_kmh": 4,
                "bike_speed_kmh": 18,
                "default_car_speed_kmh": 45,
            }
        )

        game_map = self.upload(payload)

        self.assertEqual(game_map.walk_speed_kmh, 4)
        self.assertEqual(game_map.bike_speed_kmh, 18)
        self.assertEqual(game_map.default_car_speed_kmh, 45)

    def test_a_file_without_them_keeps_the_form_and_the_defaults(self):
        """An older export, and every handwritten file, says none of this."""
        game_map = self.upload(self.graph_payload(), max_players=4)

        self.assertEqual(game_map.max_player, 4)
        self.assertEqual(game_map.walk_speed_kmh, 5)
        self.assertEqual(game_map.bike_speed_kmh, 20)
        self.assertEqual(game_map.default_car_speed_kmh, 50)

    def test_the_whole_block_survives_export_and_import(self):
        original = self.upload(
            self.graph_payload(
                map={
                    "name": "Berlin 3",
                    "x_dim": 7,
                    "y_dim": 5,
                    "max_player": 6,
                    "walk_speed_kmh": 4,
                    "bike_speed_kmh": 18,
                    "default_car_speed_kmh": 45,
                    "district_commuters": 4200,
                    "co2_budget_kg_per_round": 5500,
                }
            ),
            name="Vorher",
        )

        exported = self.client.get(
            reverse("maps:map-export", kwargs={"pk": original.pk})
        ).json()
        copy = self.upload(exported, name="Nachher", max_players=2)

        self.assertEqual(copy.max_player, 6)
        self.assertEqual(copy.walk_speed_kmh, 4)
        self.assertEqual(copy.bike_speed_kmh, 18)
        self.assertEqual(copy.default_car_speed_kmh, 45)
        self.assertEqual(copy.district_commuters, 4200)
        self.assertEqual(copy.co2_budget_kg_per_round, 5500)
        self.assertEqual(copy.x_dim, 7)
        self.assertEqual(copy.y_dim, 5)


class PTLinePortabilityTests(MapUploadMixin, TestCase):
    """A line's own numbers: seats, interval, and how fast it drives.

    The speed is not decoration — `game/simulation.py` loads it into
    `bus_line_speeds` / `train_line_speeds` to run the line's vehicles, and
    `ptRouting.ts` costs every boarding with it. A line that arrives at the
    default drives at the default on both sides.
    """

    def line_payload(self, *, bus=None, train=None):
        payload = self.graph_payload()
        if bus is not None:
            payload["bus_lines"] = [{"name": "100", "edges": [0], **bus}]
        if train is not None:
            payload["train_lines"] = [{"name": "U2", "edges": [0], **train}]
        return payload

    def test_import_reads_the_bus_line_speed(self):
        game_map = self.upload(
            self.line_payload(bus={"speed_kmh": 22}), name="Bus mit Tempo"
        )

        self.assertEqual(BusLine.objects.get(game_map=game_map).bus_speed_kmh, 22)

    def test_import_reads_the_train_line_speed(self):
        game_map = self.upload(
            self.line_payload(train={"speed_kmh": 55}), name="Bahn mit Tempo"
        )

        self.assertEqual(TrainLine.objects.get(game_map=game_map).train_speed_kmh, 55)

    def test_a_bus_line_without_a_speed_drives_at_the_model_default(self):
        game_map = self.upload(self.line_payload(bus={}), name="Bus ohne Tempo")

        self.assertEqual(BusLine.objects.get(game_map=game_map).bus_speed_kmh, 30)

    def test_a_train_line_without_a_speed_drives_at_the_model_default(self):
        game_map = self.upload(self.line_payload(train={}), name="Bahn ohne Tempo")

        self.assertEqual(TrainLine.objects.get(game_map=game_map).train_speed_kmh, 40)

    def test_a_train_line_without_an_interval_keeps_the_model_default(self):
        """Five, like the model and like a bus — not ten.

        The importer answered this question with 10 while `TrainLine.intervall`
        says 5 and `_create_bus_lines` says 5, so a handwritten file got twice
        the service it asked for on the bus and half of it on the train. Same
        shape as the 60-seat U-Bahn: three places, two answers.
        """
        game_map = self.upload(self.line_payload(train={}), name="Bahn ohne Takt")

        self.assertEqual(TrainLine.objects.get(game_map=game_map).intervall, 5)

    def test_a_line_survives_export_and_import(self):
        original = self.upload(
            self.line_payload(
                bus={"interval": 8, "capacity": 85, "speed_kmh": 22},
                train={"interval": 4, "capacity": 1000, "speed_kmh": 55},
            ),
            name="Linien vorher",
        )

        exported = self.client.get(
            reverse("maps:map-export", kwargs={"pk": original.pk})
        ).json()
        copy = self.upload(exported, name="Linien nachher")

        bus = BusLine.objects.get(game_map=copy)
        train = TrainLine.objects.get(game_map=copy)
        self.assertEqual(
            (bus.intervall, bus.bus_capacity, bus.bus_speed_kmh), (8, 85, 22)
        )
        self.assertEqual(
            (train.intervall, train.train_capacity, train.train_speed_kmh),
            (4, 1000, 55),
        )
        self.assertEqual(bus.edges.count(), 1)
        self.assertEqual(train.edges.count(), 1)
