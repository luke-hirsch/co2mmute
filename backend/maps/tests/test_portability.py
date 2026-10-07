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

from game.tests._helpers import TempMediaRootMixin, english_in, muted
from maps.forms import MapUploadForm
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


def refusal_of(response):
    """Everything the import said no with, as one string."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}, no JSON"
    fields = [str(m) for msgs in body.get("fields", {}).values() for m in msgs]
    return " ".join(fields + [str(m) for m in body.get("graph", [])])


class MapUploadMixin(TempMediaRootMixin):
    """Posting `api/maps/import/` the way the upload screen does.

    It was `/map/upload/` until S19 moved the page into the SPA; the endpoint
    reads the same form, so every test here moved with it unchanged.

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
            reverse("maps:map-import"),
            {"map_name": name, "max_players": max_players, "description": "", **files},
        )
        self.assertIn(response.status_code, (201, 400))
        return self.uploaded_map(name, response)

    def uploaded_map(self, name, response):
        """The map the upload made — or why the import refused it.

        A bare DoesNotExist here says nothing; the endpoint answers 400 with
        the form's field errors and the file's graph errors, so both are worth
        printing when the map is missing.
        """
        game_map = GameMap.objects.filter(name=name).order_by("-created").first()
        if game_map is not None:
            return game_map

        raise AssertionError(
            f"upload created no map named {name!r}: {refusal_of(response)}"
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
            reverse("maps:map-import"),
            {
                "map_name": "Berlin 3 (Kopie)",
                "max_players": 4,
                "description": "",
                "json_file": ContentFile(
                    json.dumps(exported).encode("utf-8"), name="map.json"
                ),
            },
        )

        copy = GameMap.objects.filter(name="Berlin 3 (Kopie)").order_by("-created").first()
        if copy is None:
            raise AssertionError(
                f"the exported file did not import: {refusal_of(response)}"
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
                reverse("maps:map-import"),
                {
                    "map_name": "Widerspruch",
                    "max_players": 4,
                    "description": "",
                    "json_file": ContentFile(
                        json.dumps(payload).encode("utf-8"), name="map.json"
                    ),
                },
            )
        notes = refusal_of(response)

        self.assertFalse(GameMap.objects.filter(name="Widerspruch").exists())
        self.assertIn("bike_lane", notes)


class PathHasNoStreetUnderItTests(MapUploadMixin, TestCase):
    """A way for bikes and pedestrians, and no car lane at all.

    The map the group plays has twelve: three homes reaching the S-Bahn at
    Bellevue, the Justizministerium reaching Checkpoint Charlie, and since F11
    eight through the Tiergarten and round Potsdamer Platz. A car goes round.

    `type` used to have three values, so the export wrote such a link as
    `"street"` — the `else` branch of the three-way choice — and the importer
    answered by creating a `StreetEdge` at the default 50 km/h and one lane. The
    map therefore could not survive its own round trip: every front door gained
    a fast car shortcut that nobody drew, and S5 "corrected" the shipped file by
    writing those invented numbers out.
    """

    def path_payload(self, **edge_extra):
        payload = self.graph_payload()
        payload["edges"] = [
            {
                "start_node": "1",
                "end_node": "2",
                "name": None,
                "type": "path",
                "walking": True,
                "biking": True,
                "max_lanes": 1,
                **edge_extra,
            }
        ]
        return payload

    def test_a_path_arrives_without_a_street(self):
        game_map = self.upload(self.path_payload(), name="Mit Weg")
        edge = Edge.objects.get(game_map=game_map)

        self.assertFalse(edge.streetedge_set.exists())
        self.assertFalse(edge.trainedge_set.exists())
        self.assertTrue(edge.walking)
        self.assertTrue(edge.biking)

    def test_a_path_comes_back_out_as_a_path(self):
        game_map = self.upload(self.path_payload(), name="Weg hin und zurück")

        response = self.client.get(
            reverse("maps:map-export", kwargs={"pk": game_map.pk})
        )
        self.assertEqual(response.status_code, 200)
        entry = response.json()["edges"][0]
        self.assertEqual(entry["type"], "path")
        self.assertNotIn("speed_limit", entry)
        self.assertNotIn("lanes", entry)
        self.assertNotIn("dedicated_bus_lane", entry)

    def test_an_old_file_calling_it_a_street_means_the_same_thing(self):
        """Backwards compatibility, and the bug's own history.

        A file written before `"path"` existed says `"street"` and simply states
        no street field. Reading that as "a street whose numbers were left out"
        is what invented the car lane, so it is read as a path — which is what
        the four links on the shipped map were, all along.
        """
        game_map = self.upload(
            self.path_payload(type="street"), name="Alte Datei"
        )

        self.assertFalse(Edge.objects.get(game_map=game_map).streetedge_set.exists())

    def test_a_street_that_states_one_number_is_still_a_street(self):
        """The line is "says nothing about a street", not "says everything"."""
        game_map = self.upload(
            self.path_payload(type="street", lanes=2), name="Halb beschrieben"
        )

        street = Edge.objects.get(game_map=game_map).streetedge_set.get()
        self.assertEqual(street.lanes, 2)


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
# S2 read `district_commuters` (and a per-map budget, gone since F8 step 2b) on
# the way in and named what it left behind: `_create_game_map` takes a `map_meta` argument that
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
        self.assertNotIn("co2_budget_kg_per_round", exported["map"])
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


class TramTravelsTests(MapUploadMixin, TestCase):
    """Where a tram's rails lie, and that a line is a tram, through the file.

    `"type": "tram"` is a street with rails in it, the M1's on Friedrichstraße
    north; `tram_track` says whether they lie in the car lane or on a lane of
    their own. A train line says its `kind`.
    """

    def tram_payload(self, *, edges=None, train=None):
        payload = self.graph_payload()
        payload["edges"] = edges or [
            {
                "start_node": "1",
                "end_node": "2",
                "name": "Friedrichstraße",
                "type": "tram",
                "speed_limit": 30,
                "lanes": 1,
            },
            {
                "start_node": "2",
                "end_node": "1",
                "name": "Friedrichstraße",
                "type": "tram",
                "tram_track": "own",
                "speed_limit": 30,
                "lanes": 2,
            },
        ]
        if train is not None:
            payload["train_lines"] = [{"name": "M1", "edges": [0], **train}]
        return payload

    def refused(self, payload, name):
        with muted():
            response = self.client.post(
                reverse("maps:map-import"),
                {
                    "map_name": name,
                    "max_players": 4,
                    "description": "",
                    "json_file": ContentFile(
                        json.dumps(payload).encode("utf-8"), name="map.json"
                    ),
                },
            )
        self.assertFalse(GameMap.objects.filter(name=name).exists())
        return refusal_of(response)

    def streets(self, game_map):
        from maps.models import StreetEdge

        return {
            street.lanes: street
            for street in StreetEdge.objects.filter(edge__game_map=game_map)
        }

    def test_a_tram_street_arrives_with_rails_in_the_car_lane(self):
        game_map = self.upload(self.tram_payload(), name="Tram in der Spur")

        street = self.streets(game_map)[1]
        self.assertEqual(street.tram_track, "lane")
        self.assertTrue(street.edge.trainedge_set.exists())

    def test_its_own_track_arrives_as_its_own_track(self):
        game_map = self.upload(self.tram_payload(), name="Tram eigenes Gleis")

        street = self.streets(game_map)[2]
        self.assertEqual(street.tram_track, "own")
        self.assertTrue(street.edge.trainedge_set.exists())

    def test_a_tram_line_arrives_as_a_tram_with_a_trams_defaults(self):
        game_map = self.upload(
            self.tram_payload(train={"kind": "tram"}), name="Tramlinie"
        )

        line = TrainLine.objects.get(game_map=game_map)
        self.assertEqual(line.kind, "tram")
        self.assertEqual(
            (line.train_capacity, line.train_speed_kmh),
            (
                TrainLine.DEFAULTS["tram"]["capacity"],
                TrainLine.DEFAULTS["tram"]["speed_kmh"],
            ),
        )
        self.assertEqual((line.train_capacity, line.train_speed_kmh), (248, 30))

    def test_a_train_line_that_says_nothing_is_a_train(self):
        game_map = self.upload(self.tram_payload(train={}), name="Bahnlinie")

        line = TrainLine.objects.get(game_map=game_map)
        self.assertEqual(line.kind, "train")
        self.assertEqual((line.train_capacity, line.train_speed_kmh), (1000, 40))

    def test_the_export_writes_them_back_out(self):
        game_map = self.upload(
            self.tram_payload(train={"kind": "tram"}), name="Tram Export"
        )

        exported = self.client.get(
            reverse("maps:map-export", kwargs={"pk": game_map.pk})
        ).json()

        by_lanes = {edge["lanes"]: edge for edge in exported["edges"]}
        self.assertEqual(by_lanes[1]["type"], "tram")
        self.assertEqual(by_lanes[1]["tram_track"], "lane")
        self.assertEqual(by_lanes[2]["type"], "tram")
        self.assertEqual(by_lanes[2]["tram_track"], "own")
        self.assertEqual(exported["train_lines"][0]["kind"], "tram")

    def test_a_train_line_is_written_as_a_train(self):
        """Written out, not left out — the file describes the map."""
        game_map = self.upload(self.tram_payload(train={}), name="Bahn Export")

        exported = self.client.get(
            reverse("maps:map-export", kwargs={"pk": game_map.pk})
        ).json()

        self.assertEqual(exported["train_lines"][0]["kind"], "train")

    def test_rails_beside_a_street_stay_both(self):
        """The U2 under Bismarckstraße: a street and a railway, no tram track."""
        payload = self.tram_payload(
            edges=[
                {
                    "start_node": "1",
                    "end_node": "2",
                    "name": "Bismarckstraße",
                    "type": "both",
                    "speed_limit": 50,
                    "lanes": 2,
                }
            ]
        )
        game_map = self.upload(payload, name="U2 darunter")

        exported = self.client.get(
            reverse("maps:map-export", kwargs={"pk": game_map.pk})
        ).json()

        self.assertEqual(self.streets(game_map)[2].tram_track, "")
        self.assertEqual(exported["edges"][0]["type"], "both")
        self.assertNotIn("tram_track", exported["edges"][0])

    def test_the_graph_the_client_reads_carries_the_track_and_the_kind(self):
        """`carLanes` counts its own track like a bus lane; the screen says Tram."""
        from maps.serializer import EdgeSerializer, serialize_train_line_for_graph

        game_map = self.upload(
            self.tram_payload(train={"kind": "tram"}), name="Tram Graph"
        )
        streets = self.streets(game_map)
        line = TrainLine.objects.get(game_map=game_map)
        version = MapVersion.objects.get(game_map=game_map)

        self.assertEqual(
            EdgeSerializer(streets[1].edge).data["street_edge"]["tram_track"], "lane"
        )
        self.assertEqual(
            EdgeSerializer(streets[2].edge).data["street_edge"]["tram_track"], "own"
        )
        self.assertEqual(serialize_train_line_for_graph(line, version)["kind"], "tram")

    def test_a_tram_survives_export_and_import(self):
        original = self.upload(
            self.tram_payload(train={"kind": "tram", "speed_kmh": 18}),
            name="Tram vorher",
        )
        exported = self.client.get(
            reverse("maps:map-export", kwargs={"pk": original.pk})
        ).json()

        copy = self.upload(exported, name="Tram nachher")

        self.assertEqual(map_summary(copy), map_summary(original))
        line = TrainLine.objects.get(game_map=copy)
        self.assertEqual((line.kind, line.train_speed_kmh), ("tram", 18))

    def test_a_track_on_anything_but_a_tram_street_is_refused(self):
        payload = self.tram_payload(
            edges=[
                {
                    "start_node": "1",
                    "end_node": "2",
                    "type": "both",
                    "tram_track": "own",
                    "lanes": 2,
                }
            ]
        )

        notes = self.refused(payload, "Gleis ohne Tram")

        self.assertIn("tram_track", notes)

    def test_a_track_that_is_neither_lane_nor_own_is_refused(self):
        payload = self.tram_payload()
        payload["edges"][0]["tram_track"] = "median"

        notes = self.refused(payload, "Gleis unbekannt")

        self.assertIn("median", notes)

    def test_a_kind_that_is_neither_train_nor_tram_is_refused(self):
        notes = self.refused(self.tram_payload(train={"kind": "metro"}), "Unbekannt")

        self.assertIn("metro", notes)


class PTChainExportTests(MapUploadMixin, TestCase):
    """The export writes the chain of the version it is exporting, and says so.

    This is where `map_examples/Berlin_Mitte-West.json` got its bus `100` with no
    edges at all. The export writes a line's links as indices into the edge list
    it has just built for one version, and a link whose street is missing from
    that version has no index — so it was skipped without a word. Ten silent
    drops read as a map author who never finished drawing the line, and S5 fixed
    the file on that reading. The file was right about what it had been given.

    So: the chain comes from the version's own through rows, and a link the file
    cannot carry is a warning naming the line and the edge.
    """

    def upload_with_a_line(self, name):
        payload = self.graph_payload()
        payload["edges"].append(
            {
                "start_node": "2",
                "end_node": "1",
                "name": "Hauptstraße zurück",
                "walking": True,
            }
        )
        payload["bus_lines"] = [{"name": "100", "edges": [0, 1]}]
        return self.upload(payload, name=name)

    def export(self, game_map, version=None):
        """Always the single-version file: dropping a link is its branch alone.

        The whole-map export writes every edge, so a chain row always has an
        index there and this warning cannot fire. `None` means the base
        version, which is what this url used to mean.
        """
        if version is None:
            version = MapVersion.objects.get(game_map=game_map, base_version=True)
        url = reverse(
            "maps:map-export-version",
            kwargs={"pk": game_map.pk, "version_pk": version.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_a_healthy_line_exports_every_link_without_complaining(self):
        game_map = self.upload_with_a_line("Linie ganz")

        with self.assertNoLogs("maps.portability", level="WARNING"):
            exported = self.export(game_map)

        self.assertEqual(exported["bus_lines"][0]["edges"], [0, 1])

    def test_a_link_the_version_cannot_hold_is_named_in_the_log(self):
        """The damaged shape, built the only way it can now arise: by hand."""
        game_map = self.upload_with_a_line("Linie mit Loch")
        version = MapVersion.objects.get(game_map=game_map, base_version=True)
        second = Edge.objects.get(game_map=game_map, name="Hauptstraße zurück")
        second.map_versions.remove(version)

        with self.assertLogs("maps.portability", level="WARNING") as captured:
            exported = self.export(game_map)

        self.assertEqual(exported["bus_lines"][0]["edges"], [0])
        logged = " ".join(captured.output)
        self.assertIn("100", logged)
        self.assertIn(str(second.pk), logged)

    def test_a_link_outside_the_version_is_not_exported_into_it(self):
        """A row belonging to another version is not this version's chain.

        Filtering the chain by the street edges the version happens to share
        with the line gave the right answer only while every line had exactly one
        chain for the whole map.
        """
        game_map = self.upload_with_a_line("Linie pro Version")
        base = MapVersion.objects.get(game_map=game_map, base_version=True)
        other = MapVersion.objects.create(game_map=game_map, name="Andere")
        line = BusLine.objects.get(game_map=game_map)
        line.map_versions.add(other)
        for node in Node.objects.filter(game_map=game_map):
            node.map_versions.add(other)
        for edge in Edge.objects.filter(game_map=game_map):
            edge.map_versions.add(other)
        for row in line.buslineedge_set.all():
            row.street_edge.map_versions.add(other)
            row.map_versions.add(other)
        # The second link runs on the other version only.
        line.buslineedge_set.get(order=1).map_versions.remove(base)

        self.assertEqual(self.export(game_map, base)["bus_lines"][0]["edges"], [0])
        self.assertEqual(self.export(game_map, other)["bus_lines"][0]["edges"], [0, 1])


# ---------------------------------------------------------------------------
# S14 — the whole map in one file.
#
# Until now the export was a snapshot of one version, flattened: it picked a
# `MapVersion`, filtered nodes, edges and lines to it and wrote no version
# information at all, and the importer answered with exactly one base version.
# So a map with four versions exported as four files that re-imported as four
# separate maps, and what was lost on every move between boxes was the other
# versions, `compatible_versions` — which *is* the vote — `source_version`, both
# poll texts, `change_img`, and which element belongs where. Measured on the
# box's own map: a base-only export drops 19 edges, a whole bus line pair and
# all 24 `compatible_versions` pairs.
#
# `/export/` is now the whole map and `/export/version/<pk>/` stays the single
# flattened version, which is what the two urls already read like. A file
# *without* a `versions` block keeps importing exactly as it does today — every
# file in `map_examples/` is one.
# ---------------------------------------------------------------------------


def edge_key(edge):
    """An edge identified by what it *is*, so two maps can be compared.

    Primary keys differ between the original and its copy, and a version that
    changes a street clones the row — so the clone shares name and endpoints
    with its original and is told apart only by the street it carries. That is
    the whole point of the comparison: the copy has to end up with both.
    """
    from maps.models import StreetEdge, TrainEdge

    se = StreetEdge.objects.filter(edge=edge).first()
    te = TrainEdge.objects.filter(edge=edge).first()
    return (
        edge.name or "",
        edge.start_node.name or "",
        edge.end_node.name or "",
        round(edge.start_node.x_position, 3),
        round(edge.end_node.x_position, 3),
        edge.biking,
        edge.bike_lane,
        edge.walking,
        edge.max_lanes,
        (se.speed_limit, se.lanes, se.dedicated_bus_lane, se.tram_track)
        if se
        else None,
        te is not None,
    )


def map_summary(game_map):
    """Everything about a map that has to survive the file, by version name.

    Version names are unique within these fixtures, which is what makes the
    original and the copy comparable at all — nothing else about a version is
    stable across two databases.
    """
    from maps.models import BusLine, Edge, MapVersion, Node, TrainLine
    from maps.versions import bus_chain_rows, train_chain_rows

    summary = {}
    for version in MapVersion.objects.filter(game_map=game_map):
        summary[version.name] = {
            "base": version.base_version,
            "poll_text": version.poll_text,
            "revert_poll_text": version.revert_poll_text,
            "description": version.description or "",
            "source": version.source_version.name if version.source_version else None,
            "compatible": sorted(
                other.name for other in version.compatible_versions.all()
            ),
            "nodes": sorted(
                (n.name or "", round(n.x_position, 3), round(n.y_position, 3))
                for n in Node.objects.filter(game_map=game_map, map_versions=version)
            ),
            "edges": sorted(
                edge_key(e)
                for e in Edge.objects.filter(game_map=game_map, map_versions=version)
            ),
            "bus": {
                line.name: [
                    edge_key(row.street_edge.edge)
                    for row in bus_chain_rows(line, version).select_related(
                        "street_edge__edge"
                    )
                ]
                for line in BusLine.objects.filter(
                    game_map=game_map, map_versions=version
                )
            },
            "train": {
                (line.name, line.kind): [
                    edge_key(row.train_edge.edge)
                    for row in train_chain_rows(line, version).select_related(
                        "train_edge__edge"
                    )
                ]
                for line in TrainLine.objects.filter(
                    game_map=game_map, map_versions=version
                )
            },
        }
    return summary


class VersionedMapMixin(MapUploadMixin):
    """A map shaped like the box's: base, two hand-drawn atomics, one combination.

    Built through the real endpoints rather than by hand, because the thing
    under test is whether a file can carry what `create-from-diff` and
    `generate-combinations` actually produce — cloned streets, chains that
    differ per version, and a `compatible_versions` graph nobody typed.

    Four nodes in a row, three edges. `B` and `C` are `"type": "both"`, street
    and rail at once, which is how drawing bus lanes on the box also moved
    `U2`'s chain. Bus `100` runs A-B-C, train `U2` runs the rail half of B-C.
    """

    def seed_payload(self):
        nodes = [
            {"id": str(i), "name": f"N{i}", "x": float(i), "y": 0.0} for i in range(4)
        ]
        edges = [
            {
                "start_node": "0",
                "end_node": "1",
                "name": "A",
                "type": "street",
                "speed_limit": 50,
                "lanes": 2,
            },
            {
                "start_node": "1",
                "end_node": "2",
                "name": "B",
                "type": "both",
                "speed_limit": 50,
                "lanes": 2,
            },
            {
                "start_node": "2",
                "end_node": "3",
                "name": "C",
                "type": "both",
                "speed_limit": 30,
                "lanes": 2,
            },
        ]
        return {
            "scale": 120.0,
            "nodes": nodes,
            "edges": edges,
            "bus_lines": [
                {"name": "100", "interval": 7, "capacity": 85, "speed_kmh": 30,
                 "edges": [0, 1, 2]}
            ],
            "train_lines": [
                {"name": "U2", "interval": 4, "capacity": 1000, "speed_kmh": 40,
                 "edges": [1, 2]}
            ],
        }

    def build_versioned_map(self, name="Mitte-West"):
        from maps.models import Edge, MapVersion

        game_map = self.upload(self.seed_payload(), name=name)
        base = MapVersion.objects.get(game_map=game_map, base_version=True)
        edge_b = Edge.objects.get(game_map=game_map, name="B")

        def node_pk(name):
            return Node.objects.get(game_map=game_map, name=name).pk

        busspuren = self.create_version(
            game_map,
            base,
            "Busspuren",
            edge_changes=[
                {"edge_id": edge_b.pk, "dedicated_bus_lane": True, "lanes": 2}
            ],
        )
        umgehung = self.create_version(
            game_map,
            base,
            "Umgehung",
            new_edges=[
                {
                    "temp_start_node": str(node_pk("N0")),
                    "temp_end_node": str(node_pk("N3")),
                    "speed_limit": 50,
                    "lanes": 1,
                    "max_lanes": 1,
                    "biking": True,
                    "walking": True,
                }
            ],
        )
        response = self.client.post(
            reverse(
                "maps:version-generate-combinations", kwargs={"pk": game_map.pk}
            ),
            data={"version_ids": [busspuren.pk, umgehung.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return game_map, base

    def create_version(self, game_map, source, version_name, **changes):
        from maps.models import MapVersion

        response = self.client.post(
            reverse("maps:version-diff-create", kwargs={"pk": game_map.pk}),
            data={
                "source_version_id": source.pk,
                "version_name": version_name,
                "description": f"Was {version_name} ändert",
                "poll_text": f"Die Karte soll {version_name} bekommen.",
                "revert_poll_text": f"Die Karte soll {version_name} wieder los.",
                **changes,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return MapVersion.objects.get(pk=response.json()["id"])

    def export_whole(self, game_map):
        response = self.client.get(
            reverse("maps:map-export", kwargs={"pk": game_map.pk})
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def export_version(self, game_map, version):
        response = self.client.get(
            reverse(
                "maps:map-export-version",
                kwargs={"pk": game_map.pk, "version_pk": version.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        return response.json()


class WholeMapExportTests(VersionedMapMixin, TestCase):
    """What `GET api/maps/<pk>/export/` has to write down about versions."""

    def setUp(self):
        super().setUp()
        self.game_map, self.base = self.build_versioned_map()
        self.exported = self.export_whole(self.game_map)
        self.names = [v["name"] for v in self.exported["versions"]]

    def index(self, name):
        return self.names.index(name)

    def test_every_version_of_the_map_is_in_the_file(self):
        self.assertEqual(
            sorted(self.names),
            sorted(["Mitte-West - Base", "Busspuren", "Umgehung",
                    "Busspuren + Umgehung"]),
        )

    def test_the_base_version_is_the_first_entry_and_says_so(self):
        self.assertEqual(self.exported["versions"][0]["name"], "Mitte-West - Base")
        self.assertTrue(self.exported["versions"][0]["base_version"])
        self.assertEqual(
            [v["base_version"] for v in self.exported["versions"]].count(True), 1
        )

    def test_a_version_carries_both_poll_texts_and_its_description(self):
        entry = self.exported["versions"][self.index("Busspuren")]
        self.assertEqual(entry["poll_text"], "Die Karte soll Busspuren bekommen.")
        self.assertEqual(
            entry["revert_poll_text"], "Die Karte soll Busspuren wieder los."
        )
        self.assertEqual(entry["description"], "Was Busspuren ändert")

    def test_source_version_is_written_as_an_index(self):
        entry = self.exported["versions"][self.index("Busspuren")]
        self.assertEqual(entry["source_version"], self.index("Mitte-West - Base"))
        self.assertIsNone(
            self.exported["versions"][self.index("Mitte-West - Base")][
                "source_version"
            ]
        )

    def test_compatible_versions_are_written_as_indices(self):
        """The ballot: what `_get_voteable_map_versions()` reads.

        Base reaches both atomics, each atomic reaches base and the
        combination. Nothing else in the file says a vote exists.
        """
        entry = self.exported["versions"][self.index("Mitte-West - Base")]
        self.assertEqual(
            sorted(self.names[i] for i in entry["compatible_versions"]),
            ["Busspuren", "Umgehung"],
        )
        entry = self.exported["versions"][self.index("Busspuren")]
        self.assertEqual(
            sorted(self.names[i] for i in entry["compatible_versions"]),
            ["Busspuren + Umgehung", "Mitte-West - Base"],
        )

    def test_every_node_and_edge_says_which_versions_hold_it(self):
        for node in self.exported["nodes"]:
            self.assertIn("versions", node)
            self.assertTrue(node["versions"])
        # The bypass `Umgehung` draws is in that version and in the
        # combination, and in neither of the other two.
        added = [e for e in self.exported["edges"] if e["name"] is None]
        self.assertEqual(len(added), 1, self.exported["edges"])
        self.assertEqual(
            sorted(self.names[i] for i in added[0]["versions"]),
            ["Busspuren + Umgehung", "Umgehung"],
        )

    def test_the_street_a_version_replaced_is_in_the_file_twice(self):
        """Once as the original and once as the bus-lane clone.

        A one-version export writes whichever of the two that version holds and
        the other is simply gone — which is how the same street ends up with
        different tempo in two versions on the box for a reason nobody chose.
        """
        b_edges = [e for e in self.exported["edges"] if e["name"] == "B"]
        self.assertEqual(len(b_edges), 2)
        self.assertEqual(
            sorted(e["dedicated_bus_lane"] for e in b_edges), [False, True]
        )
        clone = next(e for e in b_edges if e["dedicated_bus_lane"])
        self.assertEqual(
            sorted(self.names[i] for i in clone["versions"]),
            ["Busspuren", "Busspuren + Umgehung"],
        )

    def test_a_line_writes_one_chain_per_route_and_not_one_per_version(self):
        """Four versions, two routes: the file says it twice, not four times."""
        line = next(b for b in self.exported["bus_lines"] if b["name"] == "100")
        self.assertNotIn("edges", line)
        self.assertEqual(len(line["chains"]), 2)
        by_versions = {
            tuple(sorted(self.names[i] for i in c["versions"])): c["edges"]
            for c in line["chains"]
        }
        self.assertEqual(
            sorted(by_versions),
            [
                ("Busspuren", "Busspuren + Umgehung"),
                ("Mitte-West - Base", "Umgehung"),
            ],
        )
        plain = by_versions[("Mitte-West - Base", "Umgehung")]
        with_lane = by_versions[("Busspuren", "Busspuren + Umgehung")]
        self.assertEqual(len(plain), 3)
        self.assertEqual(len(with_lane), 3)
        self.assertNotEqual(plain[1], with_lane[1])
        self.assertFalse(self.exported["edges"][plain[1]]["dedicated_bus_lane"])
        self.assertTrue(self.exported["edges"][with_lane[1]]["dedicated_bus_lane"])

    def test_a_version_that_runs_no_link_of_a_line_is_written_as_an_empty_chain(self):
        """The damaged state has to be legible, because S16 repairs it here.

        On the box buslinie 100 reaches 0 of its 7 street edges in the base
        version. A file that simply omitted that version would read as a line
        with one route rather than a line that is broken in one of them.
        """
        from maps.models import BusLine

        line = BusLine.objects.get(game_map=self.game_map, name="100")
        for row in line.buslineedge_set.filter(map_versions=self.base):
            row.map_versions.remove(self.base)

        exported = self.export_whole(self.game_map)
        names = [v["name"] for v in exported["versions"]]
        entry = next(b for b in exported["bus_lines"] if b["name"] == "100")
        empty = [
            c
            for c in entry["chains"]
            if names[c["versions"][0]] == "Mitte-West - Base"
        ]
        self.assertEqual(len(empty), 1)
        self.assertEqual(empty[0]["edges"], [])

    def test_a_line_that_belongs_to_no_version_is_named_in_the_log(self):
        """The box has three `Bus 147` leftovers that no version ever runs.

        Invisible in play, so a backup that dropped them silently would be a
        backup nobody could check. They travel with an empty version list — and
        the export says so out loud, since a line in no version is a defect.
        """
        from maps.models import BusLine

        orphan = BusLine.objects.create(game_map=self.game_map, name="147")

        with self.assertLogs("maps.portability", level="WARNING") as captured:
            exported = self.export_whole(self.game_map)

        entry = next(b for b in exported["bus_lines"] if b["name"] == "147")
        self.assertEqual(entry["versions"], [])
        self.assertEqual(entry["chains"], [])
        self.assertIn("147", " ".join(captured.output))
        self.assertIn(str(orphan.pk), " ".join(captured.output))

    def test_the_change_image_travels_with_its_version(self):
        from maps.models import MapVersion

        version = MapVersion.objects.get(game_map=self.game_map, name="Busspuren")
        version.change_img.save("busspuren.png", ContentFile(PNG_BYTES), save=True)

        exported = self.export_whole(self.game_map)
        names = [v["name"] for v in exported["versions"]]
        entry = exported["versions"][names.index("Busspuren")]

        self.assertEqual(entry["change_img"]["filename"], "busspuren.png")
        self.assertEqual(
            base64.b64decode(entry["change_img"]["data"]), PNG_BYTES
        )
        self.assertNotIn(
            "change_img", exported["versions"][names.index("Umgehung")]
        )


class SingleVersionExportStaysFlatTests(VersionedMapMixin, TestCase):
    """`/export/version/<pk>/` is still the one-version snapshot it was.

    Two urls, two jobs — and the flat one is what every file in
    `map_examples/` looks like, so it has to keep being producible.
    """

    def setUp(self):
        super().setUp()
        self.game_map, self.base = self.build_versioned_map()

    def test_a_version_export_writes_no_version_block(self):
        exported = self.export_version(self.game_map, self.base)

        self.assertNotIn("versions", exported)
        for node in exported["nodes"]:
            self.assertNotIn("versions", node)
        for edge in exported["edges"]:
            self.assertNotIn("versions", edge)

    def test_a_version_export_writes_a_line_as_a_flat_edge_list(self):
        exported = self.export_version(self.game_map, self.base)
        line = next(b for b in exported["bus_lines"] if b["name"] == "100")

        self.assertEqual(line["edges"], [0, 1, 2])
        self.assertNotIn("chains", line)

    def test_a_version_export_holds_only_that_version_s_edges(self):
        from maps.models import MapVersion

        umgehung = MapVersion.objects.get(game_map=self.game_map, name="Umgehung")

        self.assertEqual(len(self.export_version(self.game_map, self.base)["edges"]), 3)
        self.assertEqual(len(self.export_version(self.game_map, umgehung)["edges"]), 4)


class WholeMapImportTests(VersionedMapMixin, TestCase):
    """What `/map/upload/` has to read back out of a versioned file."""

    def versioned_payload(self, **extra):
        """Two versions by hand: a base and one that closes the second street."""
        payload = self.seed_payload()
        payload["versions"] = [
            {
                "name": "Basis",
                "description": "wie gezeichnet",
                "base_version": True,
                "poll_text": "Die Karte soll bleiben.",
                "revert_poll_text": "Die Karte soll zurück.",
                "source_version": None,
                "compatible_versions": [1],
            },
            {
                "name": "Ohne C",
                "base_version": False,
                "poll_text": "Die Karte soll C verlieren.",
                "revert_poll_text": "Die Karte soll C behalten.",
                "source_version": 0,
                "compatible_versions": [0],
            },
        ]
        for node in payload["nodes"]:
            node["versions"] = [0, 1]
        payload["edges"][0]["versions"] = [0, 1]
        payload["edges"][1]["versions"] = [0, 1]
        payload["edges"][2]["versions"] = [0]
        payload["bus_lines"][0]["versions"] = [0, 1]
        payload["bus_lines"][0].pop("edges")
        payload["bus_lines"][0]["chains"] = [
            {"versions": [0], "edges": [0, 1, 2]},
            {"versions": [1], "edges": [0, 1]},
        ]
        payload["train_lines"][0]["versions"] = [0]
        payload.update(extra)
        return payload

    def test_a_file_with_versions_creates_all_of_them(self):
        from maps.models import MapVersion

        game_map = self.upload(self.versioned_payload(), name="Zwei Versionen")

        versions = MapVersion.objects.filter(game_map=game_map)
        self.assertEqual(sorted(v.name for v in versions), ["Basis", "Ohne C"])
        self.assertEqual([v.name for v in versions if v.base_version], ["Basis"])

    def test_the_vote_comes_back_with_the_map(self):
        """`compatible_versions` is the ballot and nothing else carries it."""
        from maps.models import MapVersion

        game_map = self.upload(self.versioned_payload(), name="Mit Abstimmung")

        base = MapVersion.objects.get(game_map=game_map, base_version=True)
        self.assertEqual(
            [v.name for v in base.compatible_versions.all()], ["Ohne C"]
        )
        self.assertTrue(game_map.offers_map_changes())

    def test_source_version_and_the_poll_texts_arrive(self):
        from maps.models import MapVersion

        game_map = self.upload(self.versioned_payload(), name="Mit Herkunft")

        other = MapVersion.objects.get(game_map=game_map, name="Ohne C")
        self.assertEqual(other.source_version.name, "Basis")
        self.assertEqual(other.poll_text, "Die Karte soll C verlieren.")
        self.assertEqual(other.revert_poll_text, "Die Karte soll C behalten.")

    def test_membership_lands_per_version(self):
        from maps.models import Edge, MapVersion

        game_map = self.upload(self.versioned_payload(), name="Pro Version")

        base = MapVersion.objects.get(game_map=game_map, name="Basis")
        other = MapVersion.objects.get(game_map=game_map, name="Ohne C")
        self.assertEqual(Edge.objects.filter(map_versions=base).count(), 3)
        self.assertEqual(Edge.objects.filter(map_versions=other).count(), 2)

    def test_a_line_gets_a_chain_of_its_own_in_each_version(self):
        from maps.models import BusLine, MapVersion
        from maps.versions import bus_chain_rows

        game_map = self.upload(self.versioned_payload(), name="Kette pro Version")

        line = BusLine.objects.get(game_map=game_map)
        base = MapVersion.objects.get(game_map=game_map, name="Basis")
        other = MapVersion.objects.get(game_map=game_map, name="Ohne C")
        self.assertEqual(
            [r.street_edge.edge.name for r in bus_chain_rows(line, base)],
            ["A", "B", "C"],
        )
        self.assertEqual(
            [r.street_edge.edge.name for r in bus_chain_rows(line, other)],
            ["A", "B"],
        )

    def test_a_line_only_one_version_runs_is_in_only_that_one(self):
        from maps.models import MapVersion, TrainLine

        game_map = self.upload(self.versioned_payload(), name="Bahn nur in Basis")

        train = TrainLine.objects.get(game_map=game_map)
        self.assertEqual(
            [v.name for v in train.map_versions.all()], ["Basis"]
        )

    def test_an_element_that_names_no_versions_lands_in_the_base_version(self):
        """The rule a handwritten file relies on, and the legacy one too.

        `versions` absent means the base version — which is exactly what a file
        without a `versions` block has always meant. `"versions": []` is how a
        file says *nowhere*, and the two are deliberately different.
        """
        from maps.models import Edge, MapVersion

        payload = self.versioned_payload()
        del payload["edges"][0]["versions"]

        game_map = self.upload(payload, name="Ohne Angabe")

        base = MapVersion.objects.get(game_map=game_map, name="Basis")
        other = MapVersion.objects.get(game_map=game_map, name="Ohne C")
        edge_a = Edge.objects.get(game_map=game_map, name="A")
        self.assertEqual([v.name for v in edge_a.map_versions.all()], [base.name])
        self.assertEqual(Edge.objects.filter(map_versions=other).count(), 1)

    def test_an_element_with_an_empty_version_list_lands_nowhere(self):
        from maps.models import BusLine

        payload = self.versioned_payload()
        payload["bus_lines"][0]["versions"] = []
        payload["bus_lines"][0]["chains"] = []

        game_map = self.upload(payload, name="Linie ohne Version")

        line = BusLine.objects.get(game_map=game_map)
        self.assertEqual(line.map_versions.count(), 0)

    def test_the_change_image_arrives_with_its_version(self):
        from maps.models import MapVersion

        payload = self.versioned_payload()
        payload["versions"][1]["change_img"] = {
            "filename": "ohne-c.png",
            "data": base64.b64encode(PNG_BYTES).decode("ascii"),
        }

        game_map = self.upload(payload, name="Mit Bild")

        other = MapVersion.objects.get(game_map=game_map, name="Ohne C")
        with other.change_img.open("rb") as fh:
            self.assertEqual(fh.read(), PNG_BYTES)

    def test_a_file_without_a_versions_block_still_makes_one_base_version(self):
        from maps.models import Edge, MapVersion

        game_map = self.upload(self.seed_payload(), name="Alt und flach")

        versions = list(MapVersion.objects.filter(game_map=game_map))
        self.assertEqual(len(versions), 1)
        self.assertTrue(versions[0].base_version)
        self.assertEqual(Edge.objects.filter(map_versions=versions[0]).count(), 3)


class VersionedFileValidationTests(VersionedMapMixin, TestCase):
    """A hand-edited file is how S16 repairs the box's map.

    So every way of getting one wrong is refused loudly, on the upload page.
    """

    def refuse(self, payload, name):
        from maps.models import GameMap

        response = self.client.post(
            reverse("maps:map-import"),
            {
                "map_name": name,
                "max_players": 4,
                "description": "",
                "json_file": ContentFile(
                    json.dumps(payload).encode("utf-8"), name="map.json"
                ),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(GameMap.objects.filter(name=name).exists())
        return refusal_of(response)

    def base_payload(self):
        payload = self.seed_payload()
        payload["versions"] = [
            {"name": "Basis", "base_version": True},
            {"name": "Zweite", "base_version": False},
        ]
        return payload

    def test_a_file_with_no_base_version_is_refused(self):
        payload = self.base_payload()
        payload["versions"][0]["base_version"] = False

        self.assertIn("base_version", self.refuse(payload, "Ohne Basis"))

    def test_a_file_with_two_base_versions_is_refused(self):
        payload = self.base_payload()
        payload["versions"][1]["base_version"] = True

        self.assertIn("base_version", self.refuse(payload, "Zwei Basen"))

    def test_a_version_index_out_of_range_is_refused(self):
        payload = self.base_payload()
        payload["nodes"][0]["versions"] = [0, 7]

        self.assertIn("7", self.refuse(payload, "Index daneben"))

    def test_a_compatible_version_pointing_nowhere_is_refused(self):
        payload = self.base_payload()
        payload["versions"][0]["compatible_versions"] = [4]

        self.assertIn("compatible_versions", self.refuse(payload, "Ballot kaputt"))

    def test_a_chain_pointing_at_an_edge_that_is_not_there_is_refused(self):
        payload = self.base_payload()
        payload["bus_lines"][0].pop("edges")
        payload["bus_lines"][0]["chains"] = [{"versions": [0], "edges": [9]}]

        self.assertIn("9", self.refuse(payload, "Kette daneben"))

    def test_a_version_without_a_name_is_refused(self):
        payload = self.base_payload()
        payload["versions"][1]["name"] = ""

        self.assertIn("name", self.refuse(payload, "Namenlos"))


class WholeMapRoundTripTests(VersionedMapMixin, TestCase):
    """Out of one box and into the next, with the ballot intact.

    This is the test S16 rehearses: export the map the group plays, repair the
    file, import it as a new map. Everything below is compared through
    `map_summary`, which reads a map the way the game does — per version.
    """

    def setUp(self):
        super().setUp()
        self.original, self.base = self.build_versioned_map("Mitte-West")
        exported = self.export_whole(self.original)
        self.copy = self.upload(exported, name="Mitte-West (Kopie)", max_players=4)

    def test_the_copy_has_the_same_versions(self):
        self.assertEqual(
            sorted(map_summary(self.copy)),
            sorted(map_summary(self.original)),
        )

    def test_every_version_holds_the_same_graph(self):
        before = map_summary(self.original)
        after = map_summary(self.copy)
        for name in sorted(before):
            with self.subTest(version=name):
                self.assertEqual(after[name]["nodes"], before[name]["nodes"])
                self.assertEqual(after[name]["edges"], before[name]["edges"])

    def test_every_version_runs_the_same_lines_over_the_same_links(self):
        before = map_summary(self.original)
        after = map_summary(self.copy)
        # Guard against a vacuous pass: the fixture only says anything if the
        # line really does run two different routes across the four versions.
        routes = {tuple(v["bus"]["100"]) for v in before.values()}
        self.assertEqual(len(routes), 2, before)
        for name in sorted(before):
            with self.subTest(version=name):
                self.assertEqual(after[name]["bus"], before[name]["bus"])
                self.assertEqual(after[name]["train"], before[name]["train"])

    def test_the_ballot_survives(self):
        before = map_summary(self.original)
        after = map_summary(self.copy)
        for name in sorted(before):
            with self.subTest(version=name):
                self.assertEqual(
                    after[name]["compatible"], before[name]["compatible"]
                )
        self.assertTrue(self.copy.offers_map_changes())

    def test_the_poll_texts_and_the_lineage_survive(self):
        before = map_summary(self.original)
        after = map_summary(self.copy)
        for name in sorted(before):
            with self.subTest(version=name):
                for key in ("base", "poll_text", "revert_poll_text",
                            "description", "source"):
                    self.assertEqual(after[name][key], before[name][key], key)

    def test_the_bus_lane_clone_is_a_second_street_in_the_copy_too(self):
        """Not a detail: unioning the two would give the router two roads.

        The copy has to hold both `B`s — the plain one the base runs on and the
        bus-lane one `Busspuren` runs on — and no version may hold both.
        """
        from maps.models import Edge, MapVersion

        b_edges = Edge.objects.filter(game_map=self.copy, name="B")
        self.assertEqual(b_edges.count(), 2)
        for version in MapVersion.objects.filter(game_map=self.copy):
            with self.subTest(version=version.name):
                self.assertEqual(
                    Edge.objects.filter(
                        game_map=self.copy, name="B", map_versions=version
                    ).count(),
                    1,
                )

    def test_a_second_round_trip_changes_nothing(self):
        """The file is a fixed point, which is what makes it a backup."""
        again = self.upload(
            self.export_whole(self.copy), name="Mitte-West (Kopie 2)"
        )

        self.assertEqual(map_summary(again), map_summary(self.copy))


# ---------------------------------------------------------------------------
# The upload page is German (S17)
# ---------------------------------------------------------------------------


class MapUploadIsGermanTests(TempMediaRootMixin, TestCase):
    """The map import speaks German, labels and refusals alike.

    The detector is the join funnel's (`game/tests/_helpers.py`), and until S17
    it ran over `/join/` and `player/create/` and nowhere else. This page had
    English labels ("Map JSON File", "Background Image"), English help text and
    English validation errors, live on the site, and nothing was watching — two
    of nine German pages covered is how that survives.

    It is the import door, which is why the check lives in this module: a map
    moves between boxes through this form, and a staff member reading it is
    reading the only German the file round trip has.

    Nothing here asserts a sentence. The test is "this page is not English",
    so the wording stays free to improve.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)

    def test_the_import_refuses_in_german(self):
        """What the file got wrong, read out on the upload screen.

        S17 translated the form and missed these: they are
        `_validate_graph_data`'s and `validate_versions`'s, and they only
        appear after a failed upload, so a check of the rendered page never
        saw one. Since S19 the SPA prints them as they come, which makes them
        copy. Key names stay English (`start_node`, `base_version`): they are
        the file's field names, the same rule as the form's help text.
        """
        node = {"id": "a", "x": 0, "y": 0}
        broken = {
            "no edges": {"nodes": [node], "edges": []},
            "unknown node": {
                "nodes": [node],
                "edges": [{"start_node": "a", "end_node": "z"}],
            },
            "duplicate node": {
                "nodes": [node, dict(node)],
                "edges": [{"start_node": "a", "end_node": "a"}],
            },
            "bike lane without bikes": {
                "nodes": [node, {"id": "b", "x": 1, "y": 0}],
                "edges": [
                    {
                        "start_node": "a",
                        "end_node": "b",
                        "type": "street",
                        "bike_lane": True,
                        "biking": False,
                    }
                ],
            },
            "line off the map": {
                "nodes": [node, {"id": "b", "x": 1, "y": 0}],
                "edges": [{"start_node": "a", "end_node": "b"}],
                "bus_lines": [{"name": "100", "edges": [5]}],
            },
            "two base versions": {
                "nodes": [node, {"id": "b", "x": 1, "y": 0}],
                "edges": [{"start_node": "a", "end_node": "b"}],
                "versions": [
                    {"name": "A", "base_version": True},
                    {"name": "B", "base_version": True, "compatible_versions": [7]},
                ],
            },
        }
        for label, payload in broken.items():
            with self.subTest(label):
                with muted():
                    response = self.client.post(
                        reverse("maps:map-import"),
                        {
                            "map_name": f"Kaputt {label}",
                            "max_players": 4,
                            "json_file": ContentFile(
                                json.dumps(payload).encode("utf-8"), name="map.json"
                            ),
                        },
                    )

                self.assertEqual(response.status_code, 400)
                said = refusal_of(response)
                self.assertTrue(said, "refused without saying why")
                self.assertEqual(english_in(said), [], said)

    def test_the_form_labels_and_help_are_german(self):
        """The rendered page covers these, but only while they are rendered.

        A label lives in `forms.py`, not in the template, so a grep of
        `maps/templates/` does not see it — the same reason the join form's
        labels get their own assertion.
        """
        form = MapUploadForm()

        offenders = {
            name: (str(field.label), str(field.help_text or ""))
            for name, field in form.fields.items()
            if english_in(str(field.label)) or english_in(str(field.help_text or ""))
        }

        self.assertEqual(offenders, {})

    def test_a_file_that_is_not_json_is_refused_in_german(self):
        form = MapUploadForm(
            data={"map_name": "Kaputt", "max_players": 4},
            files={"json_file": ContentFile(b"nicht json", name="map.json")},
        )

        self.assertFalse(form.is_valid())
        errors = " ".join(str(m) for m in form.errors["json_file"])
        self.assertEqual(english_in(errors), [], errors)

    def test_a_graph_without_nodes_is_refused_in_german(self):
        payload = json.dumps({"nodes": [], "edges": []}).encode("utf-8")
        form = MapUploadForm(
            data={"map_name": "Leer", "max_players": 4},
            files={"json_file": ContentFile(payload, name="map.json")},
        )

        self.assertFalse(form.is_valid())
        errors = " ".join(str(m) for m in form.errors["json_file"])
        self.assertEqual(english_in(errors), [], errors)

    def test_a_duplicate_name_is_refused_in_german(self):
        GameMap.objects.create(name="Schon da", max_player=4)

        form = MapUploadForm(data={"map_name": "Schon da", "max_players": 4})

        self.assertFalse(form.is_valid())
        errors = " ".join(str(m) for m in form.errors["map_name"])
        self.assertEqual(english_in(errors), [], errors)


class MapImportEndpointTests(TempMediaRootMixin, TestCase):
    """`POST api/maps/import/`, the one door a map file comes in through. S19.

    `/map/upload/` was a Django form page; the SPA's upload screen replaced it,
    and the page's URL is a redirect now. Two doors taking the same file would
    be two places for a rule to be enforced in one of — so the form, the graph
    validation and the importer are this endpoint's and nobody else's.
    """

    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.host = User.objects.create_user(username="host", password="password123")

    def post(self, payload=None, **fields):
        data = {"map_name": "Neu", "max_players": 6, **fields}
        if payload is not None:
            data["json_file"] = ContentFile(
                json.dumps(payload).encode("utf-8"), name="map.json"
            )
        return self.client.post(reverse("maps:map-import"), data)

    def graph(self):
        return {
            "nodes": [{"id": "a", "x": 0, "y": 0}, {"id": "b", "x": 1, "y": 0}],
            "edges": [{"start_node": "a", "end_node": "b", "type": "street"}],
        }

    def test_a_good_file_answers_with_the_new_map(self):
        self.client.force_login(self.staff)

        response = self.post(self.graph())

        self.assertEqual(response.status_code, 201)
        game_map = GameMap.objects.get(name="Neu")
        self.assertEqual(response.json(), {"id": game_map.pk})
        self.assertEqual(Node.objects.filter(game_map=game_map).count(), 2)
        self.assertEqual(game_map.author, self.staff)

    def test_no_file_makes_an_empty_map(self):
        self.client.force_login(self.staff)

        response = self.post()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(MapVersion.objects.filter(game_map__name="Neu").exists())

    def test_a_bad_field_is_named(self):
        GameMap.objects.create(name="Neu", max_player=4)
        self.client.force_login(self.staff)

        response = self.post(self.graph())

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("map_name", body["fields"])
        self.assertEqual(body["graph"], [])
        self.assertEqual(GameMap.objects.filter(name="Neu").count(), 1)

    def test_a_bad_graph_is_listed_and_nothing_is_made(self):
        self.client.force_login(self.staff)
        payload = self.graph()
        payload["edges"][0]["end_node"] = "z"

        with muted():
            response = self.post(payload)

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["fields"], {})
        self.assertEqual(len(body["graph"]), 1)
        self.assertIn("z", body["graph"][0])
        self.assertFalse(GameMap.objects.filter(name="Neu").exists())

    def test_only_staff_may_import(self):
        self.client.force_login(self.host)

        response = self.post(self.graph())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(GameMap.objects.exists())

    def test_a_visitor_may_not_import(self):
        response = self.post(self.graph())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(GameMap.objects.exists())

    def test_the_old_page_goes_to_the_upload_screen(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("map-upload"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/maps/upload")

    def test_the_old_page_takes_no_file_any_more(self):
        """One door. A POST to the old URL must not still import."""
        self.client.force_login(self.staff)

        self.client.post(
            reverse("map-upload"),
            {
                "map_name": "Neu",
                "max_players": 6,
                "json_file": ContentFile(
                    json.dumps(self.graph()).encode("utf-8"), name="map.json"
                ),
            },
        )

        self.assertFalse(GameMap.objects.filter(name="Neu").exists())
