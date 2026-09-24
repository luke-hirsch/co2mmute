"""What the map models themselves have to refuse and to know.

Two rules live here, both from
`.claude/plans/to-do/[backend]-bike-lane-and-traffic.md`:

- **A bike lane implies bike access.** `bike_lane` without `biking` is a
  contradiction, and the model says so instead of quietly fixing it.
- **Validation reaches the edge at all.** `game_map_clean` compares each
  MapVersion to the GameMap instead of to the version's own game_map, so
  `full_clean()` on anything belonging to a version has always raised. It had
  to be fixed before the rule above could be reached.
- **A railway knows it is a railway.** `Edge.objects.rail_only()` is the rule
  the data migration runs on, and it is written as a queryset method rather
  than inline in the migration so that it can be tested without importing a
  module whose name starts with a digit — and so that the next caller that
  needs it (the editor wants to warn about these) has one definition to use.
  Same shape as `Player.objects.playing()` in `game/`.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from maps.models import Edge, GameMap, MapVersion, Node, StreetEdge, TrainEdge


class EdgeFixtureMixin:
    """One map, one version, two nodes, and edges built on demand."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="kartograf", password="password123", is_staff=True
        )
        self.game_map = GameMap.objects.create(
            name="Modellkarte", x_dim=10, y_dim=10, scale=100.0
        )
        self.version = MapVersion.objects.create(
            game_map=self.game_map, name="Base", base_version=True
        )
        self.start = Node.objects.create(
            game_map=self.game_map, x_position=0, y_position=0
        )
        self.end = Node.objects.create(
            game_map=self.game_map, x_position=3, y_position=0
        )
        for node in (self.start, self.end):
            node.map_versions.add(self.version)

    def make_edge(self, street=False, rail=False, **fields):
        edge = Edge.objects.create(
            game_map=self.game_map,
            start_node=self.start,
            end_node=self.end,
            **fields,
        )
        edge.map_versions.add(self.version)
        if street:
            street_edge = StreetEdge.objects.create(
                edge=edge, speed_limit=50, lanes=1
            )
            street_edge.map_versions.add(self.version)
        if rail:
            train_edge = TrainEdge.objects.create(edge=edge)
            train_edge.map_versions.add(self.version)
        return edge


class BikeLaneImpliesAccessTests(EdgeFixtureMixin, TestCase):
    """`bike_lane` without `biking` is refused, not corrected.

    A silent coercion would leave the map saying one thing in the editor and
    playing another in the round. A verification says which edge is wrong and
    lets whoever drew it decide which of the two they meant.
    """

    def test_a_bike_lane_without_access_is_refused(self):
        edge = self.make_edge(street=True, biking=False, bike_lane=True)

        with self.assertRaises(ValidationError):
            edge.full_clean()

    def test_the_refusal_names_the_field(self):
        edge = self.make_edge(street=True, biking=False, bike_lane=True)

        with self.assertRaises(ValidationError) as caught:
            edge.full_clean()

        self.assertIn("bike_lane", str(caught.exception))

    def test_a_bike_lane_with_access_is_fine(self):
        edge = self.make_edge(street=True, biking=True, bike_lane=True)

        edge.full_clean()

    def test_a_street_with_no_bike_lane_is_fine(self):
        edge = self.make_edge(street=True, biking=True, bike_lane=False)

        edge.full_clean()

    def test_a_street_closed_to_bikes_is_fine(self):
        """An Autobahn: no bike access, no bike lane, nothing contradictory."""
        edge = self.make_edge(street=True, biking=False, bike_lane=False)

        edge.full_clean()


class RailOnlyEdgesTests(EdgeFixtureMixin, TestCase):
    """The set the data migration clears `biking` and `walking` on.

    92 edges across the two maps in the dev database are in it, and all 92
    are bikeable and walkable today — not because anybody said so, but because
    both fields default to True and nothing ever cleared them. Before
    `bike_lane` existed, `biking=True` on a railway carried no information;
    after it, it means "there is a path alongside". That is why the pass is a
    one-time migration rather than a rule in the importer: it corrects data
    that was never a statement, and a map author who does mean the path can
    now say so.
    """

    def test_a_railway_is_rail_only(self):
        edge = self.make_edge(rail=True)

        self.assertIn(edge, Edge.objects.rail_only())

    def test_a_street_that_also_carries_rail_is_not(self):
        """The twelve tram-down-a-street edges stay on the bike network."""
        edge = self.make_edge(street=True, rail=True)

        self.assertNotIn(edge, Edge.objects.rail_only())

    def test_an_ordinary_street_is_not(self):
        edge = self.make_edge(street=True)

        self.assertNotIn(edge, Edge.objects.rail_only())

    def test_a_path_with_neither_is_not(self):
        """An edge with no StreetEdge and no TrainEdge is a footpath."""
        edge = self.make_edge()

        self.assertNotIn(edge, Edge.objects.rail_only())

    def test_each_edge_is_listed_once(self):
        """A railway carried by several versions joins several TrainEdge rows.

        Without the distinct() the migration would still be correct — update()
        is idempotent — but any caller counting the result would double-count,
        which is exactly what the editor warning wants to do.
        """
        edge = self.make_edge(rail=True)
        second_version = MapVersion.objects.create(
            game_map=self.game_map, name="Zweite"
        )
        edge.map_versions.add(second_version)
        extra = TrainEdge.objects.create(edge=edge)
        extra.map_versions.add(second_version)

        self.assertEqual(Edge.objects.rail_only().count(), 1)


class EdgeValidationReachesTheEdgeTests(EdgeFixtureMixin, TestCase):
    """`full_clean()` on an edge in a map version raises before it gets there.

    `game_map_clean(self.map_versions.all(), self.game_map)` iterates
    MapVersion rows and compares each one to a GameMap. A MapVersion is never
    equal to a GameMap, so the check fires on every edge that belongs to a
    version — and the message names two things that print identically
    ("MapVersion's GameMap 1 - Modellkarte does not match Node's GameMap
    1 - Modellkarte"), which is why it reads as a fixture mistake.

    Nothing in the REST path calls `full_clean()` — DRF does not — so the
    editor and the importer never hit it. The admin does: it cannot save an
    Edge, Node, StreetEdge or TrainEdge that belongs to a version at all.

    Found while writing the bike-lane contradiction check, which lives in the
    same `clean()` and could not otherwise be reached.
    """

    def test_an_ordinary_edge_validates(self):
        edge = self.make_edge(street=True)

        edge.full_clean()

    def test_a_node_in_its_own_map_validates(self):
        self.start.full_clean()

    def test_a_version_from_another_map_is_still_refused(self):
        """The guard is right, only its comparison was wrong."""
        other_map = GameMap.objects.create(name="Fremde Karte", x_dim=10, y_dim=10)
        other_version = MapVersion.objects.create(
            game_map=other_map, name="Fremd", base_version=True
        )
        edge = self.make_edge(street=True)
        edge.map_versions.add(other_version)

        with self.assertRaises(ValidationError):
            edge.full_clean()
