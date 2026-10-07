"""Map versions: what a new version does to the map the others still see.

A `MapVersion` is a filter over one shared graph, not a copy — every node, edge
and line carries a `map_versions` m2m and a version is the set of rows that name
it. A PT line's *chain* was the one exception: `BusLineEdge` and `TrainLineEdge`
carried no membership at all, so there was exactly one chain per line for the
whole map. `VersionDiffCreateView` clones a changed edge for the new version and
then **moved** the line's through-row onto the clone — and that move landed in
every version sharing the line.

On the live box that broke the base version of the map the research group plays:
buslinie 100 reaches 0 of its 7 street edges there, 101 reverse 2 of 8, and even
`U2` was caught through a `"type": "both"` edge. It is also where the shipped
`map_examples/Berlin_Mitte-West.json` got its empty bus 100 from — the export
silently drops a chain row whose street edge is missing from the version, so the
file was exported incomplete rather than authored incomplete.

Second defect measured in the same pass: `GenerateCombinationsView` copies nodes,
edges, street edges, train edges and `BusLine` onto a combination version and
never `TrainLine`, so all four combinations on the box hold no rail at all — and
it unions the member versions instead of composing their diffs, so a street a
member *replaced* stays in the combination beside its replacement. Measured:
`Busspuren + Umgehungsstraßen` carries 155 edges where 140 is the whole map,
i.e. 15 streets twice over.

Evidence and the per-version counts: `.claude/plans/diagnostics/[findings]-\
kartenversionen-2026-09-27.md`. Neither version endpoint had a single test
before this file, which is why the topic gets one of its own.
"""

import os

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from game.models import (
    AgentRoute,
    GameRound,
    MapVersionVote,
    Player,
    PlayerMove,
    RouteSegment,
)
from game.tests._helpers import TEST_BACKENDS, TempMediaRootMixin, create_game_session
from maps.models import (
    BusLine,
    BusLineEdge,
    Edge,
    GameMap,
    MapVersion,
    Node,
    StreetEdge,
    TrainEdge,
    TrainLine,
    TrainLineEdge,
)
from maps.serializer import serialize_bus_line_for_graph, serialize_train_line_for_graph
from maps.versions import backfill_chain_versions


class VersionFixtureMixin:
    """The box's shape in miniature: one line over a street a version changes.

    Four nodes in a row, three edges between them. The middle and the last edge
    are `"type": "both"` — street *and* rail, which is how `Busspuren` came to
    damage `U2` as well as the two bus lines. Bus `100` runs the whole row; train
    `U2` runs the rail half of the last two.
    """

    def build_map(self, name="Mitte-West mini"):
        self.game_map = GameMap.objects.create(name=name, x_dim=10, y_dim=10)
        self.base = MapVersion.objects.create(
            game_map=self.game_map, name=f"{name} - Base", base_version=True
        )
        self.nodes = []
        for i in range(4):
            node = Node.objects.create(
                game_map=self.game_map, name=f"N{i}", x_position=i, y_position=0
            )
            node.map_versions.add(self.base)
            self.nodes.append(node)

        # A: street only. B, C: street and rail.
        self.edge_a = self._edge("A", 0, 1, street=True, rail=False)
        self.edge_b = self._edge("B", 1, 2, street=True, rail=True)
        self.edge_c = self._edge("C", 2, 3, street=True, rail=True)

        self.bus = BusLine.objects.create(
            game_map=self.game_map, name="100", bus_capacity=85
        )
        self.bus.map_versions.add(self.base)
        for order, edge in enumerate((self.edge_a, self.edge_b, self.edge_c)):
            row = BusLineEdge.objects.create(
                bus_line=self.bus,
                street_edge=StreetEdge.objects.get(edge=edge),
                order=order,
            )
            row.map_versions.add(self.base)

        self.train = TrainLine.objects.create(
            game_map=self.game_map, name="U2", train_capacity=1000
        )
        self.train.map_versions.add(self.base)
        for order, edge in enumerate((self.edge_b, self.edge_c)):
            row = TrainLineEdge.objects.create(
                train_line=self.train,
                train_edge=TrainEdge.objects.get(edge=edge),
                order=order,
            )
            row.map_versions.add(self.base)

    def _edge(self, label, start, end, *, street, rail):
        edge = Edge.objects.create(
            game_map=self.game_map,
            name=label,
            start_node=self.nodes[start],
            end_node=self.nodes[end],
            walking=True,
            max_lanes=2,
        )
        edge.map_versions.add(self.base)
        if street:
            se = StreetEdge.objects.create(edge=edge, speed_limit=50, lanes=2)
            se.map_versions.add(self.base)
        if rail:
            te = TrainEdge.objects.create(edge=edge)
            te.map_versions.add(self.base)
        return edge

    # --- building versions the way the editor does ------------------------

    def _diff(self, name, **changes):
        """A version from base plus `changes`, through the editor's endpoint."""
        response = self.client.post(
            reverse("maps:version-diff-create", kwargs={"pk": self.game_map.pk}),
            data={
                "source_version_id": self.base.pk,
                "version_name": name,
                "poll_text": f"Soll {name} kommen?",
                **changes,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return MapVersion.objects.get(pk=response.json()["id"])

    def _combine(self, *versions):
        response = self.client.post(
            reverse(
                "maps:version-generate-combinations", kwargs={"pk": self.game_map.pk}
            ),
            data={"version_ids": [v.pk for v in versions]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return MapVersion.objects.exclude(
            pk__in=[self.base.pk, *[v.pk for v in versions]]
        ).get(game_map=self.game_map)

    # --- reading a version back ------------------------------------------

    def bus_chain(self, version):
        """The underlying edge ids bus 100 reports on `version`, in order.

        Read through the graph serializer on purpose: that is the payload the
        client routes on and the shape the export and the simulator both walk.
        """
        return serialize_bus_line_for_graph(self.bus, version)["edges"]

    def train_chain(self, version):
        return serialize_train_line_for_graph(self.train, version)["edges"]

    def edges_in(self, version):
        return set(
            Edge.objects.filter(
                game_map=self.game_map, map_versions=version
            ).values_list("pk", flat=True)
        )


@override_settings(**TEST_BACKENDS)
class VersionDiffChainTests(VersionFixtureMixin, TestCase):
    """`POST versions/create-from-diff/` must not touch the source version."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        self.build_map()

    def create_version(self, name, **changes):
        payload = {
            "source_version_id": self.base.pk,
            "version_name": name,
            "poll_text": f"Soll {name} kommen?",
            **changes,
        }
        response = self.client.post(
            reverse("maps:version-diff-create", kwargs={"pk": self.game_map.pk}),
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return MapVersion.objects.get(pk=response.json()["id"])

    def busspuren(self):
        """A car lane becomes a bus lane on edge B — the box's own change."""
        return self.create_version(
            "Busspuren",
            edge_changes=[
                {"edge_id": self.edge_b.pk, "dedicated_bus_lane": True, "lanes": 2}
            ],
        )

    def test_its_own_track_for_the_tram_is_a_version_change(self):
        """„Die Tram bekommt ein eigenes Gleis“, drawn like Busspuren.

        Edge B carries a tram's rails in its car lane; the version clones the
        street with a track of its own, and the tram runs over the clone there
        while the base keeps the rails in the lane.
        """
        StreetEdge.objects.filter(edge=self.edge_b).update(tram_track="lane")
        TrainLine.objects.filter(pk=self.train.pk).update(kind="tram")

        own_track = self.create_version(
            "Eigenes Gleis",
            edge_changes=[{"edge_id": self.edge_b.pk, "tram_track": "own"}],
        )

        chain = self.train_chain(own_track)
        self.assertNotEqual(chain[0], self.edge_b.pk)
        clone = Edge.objects.get(pk=chain[0])
        self.assertEqual(StreetEdge.objects.get(edge=clone).tram_track, "own")
        self.assertEqual(StreetEdge.objects.get(edge=self.edge_b).tram_track, "lane")
        self.assertEqual(self.train_chain(self.base)[0], self.edge_b.pk)

    def test_a_new_tram_line_in_a_version_starts_with_a_trams_defaults(self):
        rails = [TrainEdge.objects.get(edge=e).pk for e in (self.edge_b, self.edge_c)]

        version = self.create_version(
            "Neue Tram",
            pt_line_changes=[
                {
                    "action": "add",
                    "line_type": "train",
                    "kind": "tram",
                    "name": "M1",
                    "edge_ids": rails,
                }
            ],
        )

        line = TrainLine.objects.get(game_map=self.game_map, name="M1")
        self.assertEqual(line.kind, "tram")
        self.assertEqual(
            (line.train_capacity, line.train_speed_kmh),
            (
                TrainLine.DEFAULTS["tram"]["capacity"],
                TrainLine.DEFAULTS["tram"]["speed_kmh"],
            ),
        )
        self.assertIn(version, line.map_versions.all())

    def test_a_tram_changed_in_a_version_stays_a_tram(self):
        """A modified line is a clone; the clone keeps what it was."""
        TrainLine.objects.filter(pk=self.train.pk).update(kind="tram")

        self.create_version(
            "Takt",
            pt_line_changes=[
                {
                    "action": "modify",
                    "line_type": "train",
                    "id": self.train.pk,
                    "interval": 5,
                }
            ],
        )

        clone = TrainLine.objects.exclude(pk=self.train.pk).get(name="U2")
        self.assertEqual((clone.kind, clone.intervall), ("tram", 5))

    def test_the_base_version_keeps_the_whole_bus_chain(self):
        """The bug, exactly as measured: 100 reaches 0 of 7 edges in base."""
        self.busspuren()

        self.assertEqual(
            self.bus_chain(self.base),
            [self.edge_a.pk, self.edge_b.pk, self.edge_c.pk],
        )

    def test_the_new_version_runs_the_line_over_the_clone(self):
        """Same three stops, but the middle edge is the bus-lane copy."""
        busspuren = self.busspuren()

        chain = self.bus_chain(busspuren)
        self.assertEqual(len(chain), 3)
        self.assertEqual([chain[0], chain[2]], [self.edge_a.pk, self.edge_c.pk])
        self.assertNotEqual(chain[1], self.edge_b.pk)
        clone = Edge.objects.get(pk=chain[1])
        self.assertTrue(
            StreetEdge.objects.get(edge=clone).dedicated_bus_lane,
            "the cloned street is the one carrying the bus lane",
        )

    def test_a_rail_line_over_the_same_street_survives_in_base(self):
        """`U2` was caught through a `"type": "both"` edge, not a bus lane."""
        self.busspuren()

        self.assertEqual(
            self.train_chain(self.base), [self.edge_b.pk, self.edge_c.pk]
        )

    def test_the_new_version_runs_the_train_over_the_clone(self):
        busspuren = self.busspuren()

        chain = self.train_chain(busspuren)
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[1], self.edge_c.pk)
        self.assertNotEqual(chain[0], self.edge_b.pk)

    def test_both_versions_report_every_stop(self):
        """A chain with a hole in it truncates, and the stop list says so."""
        busspuren = self.busspuren()

        for version in (self.base, busspuren):
            with self.subTest(version=version.name):
                self.assertEqual(
                    len(serialize_bus_line_for_graph(self.bus, version)["stops"]),
                    4,
                    "four stops for three connected edges",
                )

    def test_a_line_added_in_a_version_is_not_on_the_source(self):
        """The other direction: `Buslinie` 147 must not appear in base."""
        street_ids = list(
            StreetEdge.objects.filter(
                edge__in=[self.edge_a, self.edge_b], map_versions=self.base
            ).values_list("pk", flat=True)
        )
        new_version = self.create_version(
            "Buslinie",
            pt_line_changes=[
                {
                    "action": "add",
                    "line_type": "bus",
                    "name": "147",
                    "edge_ids": street_ids,
                }
            ],
        )

        line = BusLine.objects.get(game_map=self.game_map, name="147")
        self.assertEqual(
            len(serialize_bus_line_for_graph(line, new_version)["edges"]), 2
        )
        self.assertEqual(serialize_bus_line_for_graph(line, self.base)["edges"], [])

    def test_a_line_removed_in_a_version_keeps_its_chain_elsewhere(self):
        new_version = self.create_version(
            "Ohne 100",
            pt_line_changes=[
                {"action": "remove", "line_type": "bus", "id": self.bus.pk}
            ],
        )

        self.assertEqual(len(self.bus_chain(self.base)), 3)
        self.assertEqual(self.bus_chain(new_version), [])

    def test_deleting_an_edge_takes_the_chain_row_with_it(self):
        """A version without the street cannot have the line running over it.

        Otherwise the row survives in a version whose graph does not hold its
        edge, which is precisely the state the export drops silently and the
        simulator turns into stranded riders paying society CO2 all round.

        The control version is the half that matters: without it the count below
        is zero because no row names any version at all, and the test passes for
        the wrong reason.
        """
        untouched = self.create_version("Mit B")
        without_b = self.create_version("Ohne B", deleted_edge_ids=[self.edge_b.pk])

        rows = BusLineEdge.objects.filter(
            bus_line=self.bus, street_edge__edge=self.edge_b
        )
        self.assertEqual(rows.filter(map_versions=untouched).count(), 1)
        self.assertEqual(rows.filter(map_versions=without_b).count(), 0)
        self.assertEqual(len(self.bus_chain(self.base)), 3)

    def test_a_chain_row_never_claims_a_version_its_line_has_left(self):
        """The invariant the file format depends on, after four operations.

        S14 writes chain membership into the export, so a row naming a version
        whose line or whose street is not in it would be written out as a link of
        a line that is not there — the same silent nonsense the flattened export
        produces today, only harder to see.
        """
        self.busspuren()
        self.create_version("Ohne B", deleted_edge_ids=[self.edge_b.pk])
        self.create_version(
            "Ohne 100",
            pt_line_changes=[
                {"action": "remove", "line_type": "bus", "id": self.bus.pk}
            ],
        )

        for row in BusLineEdge.objects.prefetch_related("map_versions"):
            claimed = set(row.map_versions.values_list("pk", flat=True))
            with self.subTest(row=row.pk):
                self.assertTrue(
                    claimed
                    <= set(row.bus_line.map_versions.values_list("pk", flat=True)),
                    "a row may only name versions its line runs in",
                )
                self.assertTrue(
                    claimed
                    <= set(row.street_edge.map_versions.values_list("pk", flat=True)),
                    "a row may only name versions its street is in",
                )
        for row in TrainLineEdge.objects.prefetch_related("map_versions"):
            claimed = set(row.map_versions.values_list("pk", flat=True))
            with self.subTest(row=row.pk):
                self.assertTrue(
                    claimed
                    <= set(row.train_line.map_versions.values_list("pk", flat=True))
                )
                self.assertTrue(
                    claimed
                    <= set(row.train_edge.map_versions.values_list("pk", flat=True))
                )


@override_settings(**TEST_BACKENDS)
class GeneratedCombinationTests(VersionFixtureMixin, TestCase):
    """`POST versions/generate-combinations/` composes diffs, it does not union.

    A combination is "apply both changes", so it is base plus what each member
    added minus what each member removed. Unioning the members instead keeps a
    street a member replaced *beside* its replacement, and on the box that is 15
    duplicated corridors in every combination containing `Busspuren`.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        self.build_map()
        self.busspuren = self._diff(
            "Busspuren",
            edge_changes=[
                {"edge_id": self.edge_b.pk, "dedicated_bus_lane": True, "lanes": 2}
            ],
        )
        self.umweg = self._diff(
            "Umgehungsstraße",
            new_edges=[
                {
                    "temp_start_node": str(self.nodes[0].pk),
                    "temp_end_node": str(self.nodes[3].pk),
                    "walking": True,
                    "max_lanes": 1,
                    "speed_limit": 50,
                    "lanes": 1,
                }
            ],
        )
        self.combination = self._combine(self.busspuren, self.umweg)

    def test_the_combination_carries_the_rail_lines(self):
        """Measured on the box: all four combinations hold no train line."""
        self.assertEqual(
            TrainLine.objects.filter(
                game_map=self.game_map, map_versions=self.combination
            ).count(),
            1,
        )

    def test_the_rail_line_still_has_its_chain_there(self):
        chain = self.train_chain(self.combination)
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[1], self.edge_c.pk)

    def test_a_replaced_street_does_not_stay_beside_its_replacement(self):
        """Three edges in base, one added, one replaced: four, not five."""
        self.assertEqual(len(self.edges_in(self.combination)), 4)
        self.assertNotIn(self.edge_b.pk, self.edges_in(self.combination))

    def test_the_replacement_street_is_the_one_with_the_bus_lane(self):
        streets = StreetEdge.objects.filter(
            edge__game_map=self.game_map, map_versions=self.combination
        )
        self.assertEqual(streets.count(), 4)
        self.assertEqual(
            streets.filter(dedicated_bus_lane=True).count(),
            1,
            "the bus lane arrives once, on the clone",
        )

    def test_the_bus_line_runs_the_replacement_and_not_the_original(self):
        chain = self.bus_chain(self.combination)

        self.assertEqual(len(chain), 3)
        self.assertEqual([chain[0], chain[2]], [self.edge_a.pk, self.edge_c.pk])
        self.assertNotEqual(chain[1], self.edge_b.pk)

    def test_the_added_street_is_there_too(self):
        added = self.edges_in(self.umweg) - self.edges_in(self.base)

        self.assertEqual(len(added), 1)
        self.assertTrue(added <= self.edges_in(self.combination))

    def test_the_combination_asks_its_question_in_german(self):
        """The class reads this text on the ballot.

        It was `"Apply changes: Busspuren, Umgehungsstraße"` — English, on the
        vote, in a room of school students, and four of the eight versions on
        the live box carried it. A template rather than prose because a map with
        n interventions has 2^n - n - 1 combinations and nobody writes prose for
        eleven; phrased as a question so it does not read as a different kind of
        thing beside the hand-written ones.
        """
        self.assertEqual(
            self.combination.poll_text,
            "Sollen die Änderungen »Busspuren« und »Umgehungsstraße« zusammen "
            "umgesetzt werden?",
        )
        self.assertEqual(
            self.combination.revert_poll_text,
            "Sollen die Änderungen »Busspuren« und »Umgehungsstraße« "
            "zurückgenommen werden?",
        )

    def test_the_atomic_versions_are_untouched_by_combining(self):
        self.assertEqual(len(self.edges_in(self.busspuren)), 3)
        self.assertEqual(len(self.edges_in(self.umweg)), 4)
        self.assertEqual(len(self.bus_chain(self.base)), 3)


class ChainBackfillTests(VersionFixtureMixin, TestCase):
    """What `maps/0009` does to the chains already in a database.

    Faithful, not corrective: a row lands in the versions where **both** its line
    and its street or train edge are present. On the live box that reproduces the
    damage rather than repairing it — buslinie 100 keeps reaching 0 of its 7
    edges in the base version — and that is the point. A migration that guessed
    at what a hand-drawn version had meant would be a repair nobody could review;
    the repair is S16, in a file, under this suite.
    """

    def setUp(self):
        self.build_map()

    def run_backfill(self):
        return backfill_chain_versions(BusLine, BusLineEdge, TrainLine, TrainLineEdge)

    def strip_membership(self):
        for row in BusLineEdge.objects.all():
            row.map_versions.clear()
        for row in TrainLineEdge.objects.all():
            row.map_versions.clear()

    def test_an_intact_map_comes_back_whole(self):
        self.strip_membership()
        self.assertEqual(self.bus_chain(self.base), [])

        self.run_backfill()

        self.assertEqual(
            self.bus_chain(self.base),
            [self.edge_a.pk, self.edge_b.pk, self.edge_c.pk],
        )
        self.assertEqual(
            self.train_chain(self.base), [self.edge_b.pk, self.edge_c.pk]
        )

    def test_a_street_the_version_does_not_hold_stays_out(self):
        """The box's damage, recorded rather than repaired."""
        self.strip_membership()
        StreetEdge.objects.get(edge=self.edge_b).map_versions.remove(self.base)

        self.run_backfill()

        self.assertEqual(
            self.bus_chain(self.base), [self.edge_a.pk, self.edge_c.pk]
        )

    def test_a_line_belonging_to_no_version_gets_nothing(self):
        """The box has three such `Bus 147` leftovers. S16 drops them."""
        self.strip_membership()
        self.bus.map_versions.clear()

        self.run_backfill()

        self.assertEqual(
            BusLineEdge.objects.filter(bus_line=self.bus, map_versions__isnull=False)
            .distinct()
            .count(),
            0,
        )

    def test_a_row_lands_in_every_version_that_can_run_it(self):
        """Two versions sharing a street share the link over it."""
        second = MapVersion.objects.create(game_map=self.game_map, name="Zweite")
        for edge in (self.edge_a, self.edge_b, self.edge_c):
            edge.map_versions.add(second)
            StreetEdge.objects.get(edge=edge).map_versions.add(second)
        for node in self.nodes:
            node.map_versions.add(second)
        self.bus.map_versions.add(second)
        self.strip_membership()

        self.run_backfill()

        self.assertEqual(len(self.bus_chain(self.base)), 3)
        self.assertEqual(len(self.bus_chain(second)), 3)

    def test_it_is_safe_to_run_twice(self):
        """`./manage.py` may want it again as a backfill, and adding is idempotent."""
        self.strip_membership()
        self.run_backfill()
        self.run_backfill()

        self.assertEqual(
            BusLineEdge.objects.filter(map_versions=self.base).count(), 3
        )


@override_settings(**TEST_BACKENDS)
class DrawnInAVersionTests(VersionFixtureMixin, TestCase):
    """What the editor draws in a version is in every version built on it (F10).

    Before F10 a node or an edge drawn in a version was in that version only, so
    every other version lacked it unless it was drawn there again — and the box's
    map shows exactly that: Lukas's footpaths of 2026-10-02 in base and nowhere
    else. Drawn in base, a row is in every version; drawn in a change, it is in
    that change and in the combinations holding it. Otherwise a class that votes
    in two changes plays a combination that silently lacks part of one.

    "Built on" is read off what the versions hold, the way `combination_members`
    composes them: a version is built on X when it holds everything X added over
    the version X was made from and nothing X removed. Combinations record no
    members, so this is the only answer the map can give.

    The fixture is the box's lattice in miniature: base, `Busspuren` (edge B
    replaced by a clone with a bus lane), `Umgehungsstraße` (a new street
    N0→N3) and their combination.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        self.build_map()
        self.busspuren = self._diff(
            "Busspuren",
            edge_changes=[
                {"edge_id": self.edge_b.pk, "dedicated_bus_lane": True, "lanes": 2}
            ],
        )
        self.umweg = self._diff(
            "Umgehungsstraße",
            new_edges=[
                {
                    "temp_start_node": str(self.nodes[0].pk),
                    "temp_end_node": str(self.nodes[3].pk),
                    "walking": True,
                    "max_lanes": 1,
                    "speed_limit": 50,
                    "lanes": 1,
                }
            ],
        )
        self.combination = self._combine(self.busspuren, self.umweg)
        self.everywhere = {
            self.base.name,
            self.busspuren.name,
            self.umweg.name,
            self.combination.name,
        }

    # --- drawing, as the editor sends it -----------------------------------

    def post(self, name, data):
        return self.client.post(
            reverse(name, kwargs={"pk": self.game_map.pk}),
            data=data,
            content_type="application/json",
        )

    def draw_node(self, version):
        response = self.post(
            "maps:node-list",
            {
                "game_map": self.game_map.pk,
                "x_position": 5,
                "y_position": 5,
                "map_versions": [version.pk],
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        return Node.objects.get(pk=response.json()["id"])

    def draw_edge(self, version, start, end, *, bidirectional=False):
        return self.post(
            "maps:edge-list",
            {
                "game_map": self.game_map.pk,
                "start_node": self.nodes[start].pk,
                "end_node": self.nodes[end].pk,
                "map_versions": [version.pk],
                "bidirectional": bidirectional,
            },
        )

    def lay_street(self, version, edge):
        return self.post(
            "maps:streetedge-list",
            {
                "edge": edge.pk,
                "speed_limit": 50,
                "lanes": 1,
                "dedicated_bus_lane": False,
                "map_versions": [version.pk],
            },
        )

    def edge_between(self, start, end):
        return Edge.objects.get(
            game_map=self.game_map,
            start_node=self.nodes[start],
            end_node=self.nodes[end],
        )

    @staticmethod
    def versions_of(row):
        return set(row.map_versions.values_list("name", flat=True))

    # --- the rule ------------------------------------------------------------

    def test_a_node_drawn_in_base_is_in_every_version(self):
        node = self.draw_node(self.base)

        self.assertEqual(self.versions_of(node), self.everywhere)

    def test_a_node_drawn_in_a_change_is_in_the_combinations_holding_it(self):
        node = self.draw_node(self.busspuren)

        self.assertEqual(
            self.versions_of(node), {self.busspuren.name, self.combination.name}
        )

    def test_an_edge_drawn_in_base_is_in_every_version(self):
        response = self.draw_edge(self.base, 1, 3)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.versions_of(self.edge_between(1, 3)), self.everywhere)

    def test_an_edge_drawn_in_a_change_is_in_the_combinations_holding_it(self):
        response = self.draw_edge(self.umweg, 3, 1)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            self.versions_of(self.edge_between(3, 1)),
            {self.umweg.name, self.combination.name},
        )

    def test_both_directions_follow_the_rule(self):
        response = self.draw_edge(self.base, 1, 3, bidirectional=True)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.versions_of(self.edge_between(1, 3)), self.everywhere)
        self.assertEqual(self.versions_of(self.edge_between(3, 1)), self.everywhere)

    def test_a_street_laid_in_base_follows_its_edge(self):
        """"+ Straße anlegen" on a path drawn in base: a street in all four."""
        self.draw_edge(self.base, 1, 3)
        edge = self.edge_between(1, 3)

        response = self.lay_street(self.base, edge)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            self.versions_of(StreetEdge.objects.get(edge=edge)), self.everywhere
        )

    def test_a_version_with_its_own_copy_keeps_it(self):
        """`Umgehungsstraße` has its own N0→N3; base drawing one adds no second.

        The same holds for the `Busspuren` clones on the real map: a version
        that replaced a street with its own copy keeps the copy, because that
        copy *is* the version's change.
        """
        response = self.draw_edge(self.base, 0, 3)

        self.assertEqual(response.status_code, 201, response.content)
        drawn = Edge.objects.get(pk=response.json()["id"])
        self.assertEqual(
            self.versions_of(drawn), {self.base.name, self.busspuren.name}
        )
        for version in (self.umweg, self.combination):
            self.assertEqual(
                Edge.objects.filter(
                    map_versions=version,
                    start_node=self.nodes[0],
                    end_node=self.nodes[3],
                ).count(),
                1,
                version.name,
            )

    def test_an_edge_stays_out_of_a_version_without_its_node(self):
        """A change that took N3 away cannot hold a street ending there."""
        without = MapVersion.objects.create(
            game_map=self.game_map, name="Ohne N3", source_version=self.base
        )
        for model in (Node, Edge, StreetEdge, TrainEdge):
            for row in model.objects.filter(map_versions=self.base):
                row.map_versions.add(without)
        self.nodes[3].map_versions.remove(without)
        self.edge_c.map_versions.remove(without)

        self.draw_edge(self.base, 1, 3)

        self.assertNotIn(without.name, self.versions_of(self.edge_between(1, 3)))
        self.assertIn(without.name, self.versions_of(self.draw_node(self.base)))

    def test_a_change_with_nothing_in_it_has_nothing_built_on_it(self):
        """A copy of base adds and removes nothing, so every version "holds" it.

        Read literally that would put a row drawn there into base and all the
        rest; it stays where it was drawn.
        """
        copy = MapVersion.objects.create(
            game_map=self.game_map, name="Kopie", source_version=self.base
        )
        for model in (Node, Edge, StreetEdge, TrainEdge, BusLine, TrainLine):
            for row in model.objects.filter(map_versions=self.base):
                row.map_versions.add(copy)

        self.assertEqual(self.versions_of(self.draw_node(copy)), {"Kopie"})

    # --- what the editor may not write --------------------------------------

    def test_a_row_drawn_in_no_version_is_refused(self):
        """It would be in no version, and so on no map anybody can open.

        That is where two of the box's streets and Lukas's U Potsdamer Platz –
        Urania path sit. Not through these endpoints: an empty list was already
        refused, and so was leaving the field out — both in English, by the
        field DRF builds from the model. How they got there is not reproduced;
        the refusal now says why, in German.
        """
        before = Edge.objects.count()
        for versions in ([], None):
            data = {
                "game_map": self.game_map.pk,
                "start_node": self.nodes[1].pk,
                "end_node": self.nodes[3].pk,
            }
            if versions is not None:
                data["map_versions"] = versions
            response = self.post("maps:edge-list", data)

            self.assertEqual(response.status_code, 400, response.content)
            self.assertIn("Ohne Version", str(response.json()), versions)
        self.assertEqual(Edge.objects.count(), before)

    def test_an_edge_already_drawn_in_the_version_is_refused(self):
        """Bellevue – Großer Stern sits twice in the box's base version."""
        before = Edge.objects.count()

        response = self.draw_edge(self.base, 0, 1)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["reason"], "edge-exists")
        self.assertEqual(Edge.objects.count(), before)

    def test_both_ways_where_one_way_exists_adds_the_other(self):
        """Drawing A–B both ways over an A→B is drawing B→A."""
        before = Edge.objects.count()

        response = self.draw_edge(self.base, 1, 0, bidirectional=True)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Edge.objects.count(), before + 1)
        self.assertEqual(self.versions_of(self.edge_between(1, 0)), self.everywhere)

    def test_a_second_street_under_an_edge_is_refused(self):
        """A second click on "+ Straße anlegen" wrote a second street row."""
        response = self.lay_street(self.base, self.edge_a)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["reason"], "street-exists")
        self.assertEqual(StreetEdge.objects.filter(edge=self.edge_a).count(), 1)

    def test_a_second_railway_under_an_edge_is_refused(self):
        response = self.post(
            "maps:trainedge-list",
            {"edge": self.edge_c.pk, "map_versions": [self.base.pk]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["reason"], "rail-exists")
        self.assertEqual(TrainEdge.objects.filter(edge=self.edge_c).count(), 1)


# What a version holds, per model — every row with a `map_versions` m2m.
VERSIONED = (
    Node,
    Edge,
    StreetEdge,
    TrainEdge,
    BusLine,
    TrainLine,
    BusLineEdge,
    TrainLineEdge,
)


class DeletingAVersionMixin(TempMediaRootMixin, VersionFixtureMixin):
    """The DrawnInAVersionTests lattice plus a change nothing is built on.

    `Neubaugebiet` adds a node, a street to it both ways, bus `200` over two
    base streets and a train line `U9` over the rail — five kinds of row that
    no other version holds, and so the five that have to go with it.
    `Busspuren` is the other case: a change whose every row the combination
    holds as well, so deleting it takes nothing but itself and its ballot.
    """

    def build_lattice(self):
        self.build_map()
        self.busspuren = self._diff(
            "Busspuren",
            edge_changes=[
                {"edge_id": self.edge_b.pk, "dedicated_bus_lane": True, "lanes": 2}
            ],
        )
        self.umweg = self._diff(
            "Umgehungsstraße",
            new_edges=[
                {
                    "temp_start_node": str(self.nodes[0].pk),
                    "temp_end_node": str(self.nodes[3].pk),
                    "walking": True,
                    "max_lanes": 1,
                    "speed_limit": 50,
                    "lanes": 1,
                }
            ],
        )
        self.combination = self._combine(self.busspuren, self.umweg)
        street = StreetEdge.objects.filter(map_versions=self.base)
        rail = TrainEdge.objects.filter(map_versions=self.base)
        self.neubau = self._diff(
            "Neubaugebiet",
            new_nodes=[{"temp_id": "neu", "x_position": 5, "y_position": 2}],
            new_edges=[
                {
                    "temp_start_node": str(self.nodes[3].pk),
                    "temp_end_node": "neu",
                    "bidirectional": True,
                    "walking": True,
                    "speed_limit": 30,
                    "lanes": 1,
                }
            ],
            pt_line_changes=[
                {
                    "action": "add",
                    "line_type": "bus",
                    "name": "200",
                    "edge_ids": [
                        street.get(edge=self.edge_a).pk,
                        street.get(edge=self.edge_b).pk,
                    ],
                },
                {
                    "action": "add",
                    "line_type": "train",
                    "name": "U9",
                    "edge_ids": [
                        rail.get(edge=self.edge_b).pk,
                        rail.get(edge=self.edge_c).pk,
                    ],
                },
            ],
        )

    def held_by(self, version):
        return {
            model.__name__: set(
                model.objects.filter(map_versions=version).values_list("pk", flat=True)
            )
            for model in VERSIONED
        }

    def only_in(self, version):
        """What `version` holds and no other version of the map does."""
        own = self.held_by(version)
        for other in MapVersion.objects.filter(game_map=self.game_map).exclude(
            pk=version.pk
        ):
            for name, pks in self.held_by(other).items():
                own[name] -= pks
        return own

    def still_there(self, rows):
        return {
            model.__name__: set(
                model.objects.filter(pk__in=rows[model.__name__]).values_list(
                    "pk", flat=True
                )
            )
            for model in VERSIONED
        }

    def in_no_version(self):
        return {
            model.__name__: model.objects.filter(map_versions__isnull=True).count()
            for model in VERSIONED
        }

    def game(self, name="Dienstag", **fields):
        host = get_user_model().objects.get_or_create(username="gastgeber")[0]
        return create_game_session(
            host, game_name=name, game_map=self.game_map, **fields
        )

    def ended_game(self, name="Dienstag", **fields):
        return self.game(
            name, is_active=True, ended_at=timezone.now(), **fields
        )


@override_settings(**TEST_BACKENDS)
class DeletingAVersionTests(DeletingAVersionMixin, TestCase):
    """Deleting a version in the editor (F14).

    The website could not delete one. The admin could, and left every row that
    was only in that version in no version — invisible in the editor, still in
    the export: the two stray rows in the box's 2026-10-02 export came from a
    version made in a click-through and deleted there. `DELETE` on the version
    endpoint did the same thing, it was only that nothing called it.

    The rule: what only that version holds goes with it, what another version
    holds stays, the ballot pairs go. Refused for the base version, while a
    game is running on the map, and for a version a game has already seen —
    its routes' segments (`RouteSegment.edge` is CASCADE) and every vote cast
    for it (`MapVersionVote.map_version` is CASCADE) would go with it, and
    every move, route and result stays intact for research.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        self.build_lattice()

    def delete(self, version, map_pk=None):
        return self.client.delete(
            reverse(
                "maps:mapversion-detail",
                kwargs={"pk": map_pk or self.game_map.pk, "version_pk": version.pk},
            )
        )

    def preview(self, version):
        return self.client.get(
            reverse(
                "maps:mapversion-deletion",
                kwargs={"pk": self.game_map.pk, "version_pk": version.pk},
            )
        )

    def assertRefused(self, response, reason, *words):
        self.assertEqual(response.status_code, 409, response.content)
        body = response.json()
        self.assertEqual(body["reason"], reason)
        for word in words:
            self.assertIn(word, body["detail"])
        self.assertTrue(MapVersion.objects.filter(pk=self.neubau.pk).exists())

    # --- what goes ----------------------------------------------------------

    def test_it_takes_the_rows_only_that_version_holds(self):
        only = self.only_in(self.neubau)
        self.assertEqual(
            {name: len(pks) for name, pks in only.items()},
            {
                "Node": 1,
                "Edge": 2,
                "StreetEdge": 2,
                "TrainEdge": 0,
                "BusLine": 1,
                "TrainLine": 1,
                "BusLineEdge": 2,
                "TrainLineEdge": 2,
            },
            "the fixture has something of its own to delete",
        )

        response = self.delete(self.neubau)

        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(MapVersion.objects.filter(pk=self.neubau.pk).exists())
        self.assertEqual(
            self.still_there(only), {model.__name__: set() for model in VERSIONED}
        )

    def test_it_leaves_no_row_in_no_version(self):
        """The admin's old delete did exactly this, and the editor hid it."""
        self.assertEqual(set(self.in_no_version().values()), {0})

        self.delete(self.neubau)

        self.assertEqual(set(self.in_no_version().values()), {0})

    def test_every_other_version_keeps_what_it_held(self):
        others = MapVersion.objects.filter(game_map=self.game_map).exclude(
            pk=self.busspuren.pk
        )
        before = {version.name: self.held_by(version) for version in others}

        response = self.delete(self.busspuren)

        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(
            {version.name: self.held_by(version) for version in others}, before
        )

    def test_a_change_its_combination_holds_takes_no_row_with_it(self):
        """`Busspuren`'s clone is the combination's bus lane too."""
        before = {model.__name__: model.objects.count() for model in VERSIONED}

        self.delete(self.busspuren)

        self.assertEqual(
            {model.__name__: model.objects.count() for model in VERSIONED}, before
        )
        self.assertTrue(
            StreetEdge.objects.filter(
                map_versions=self.combination, dedicated_bus_lane=True
            ).exists()
        )

    def test_its_ballot_pairs_go_with_it(self):
        self.assertIn(self.busspuren, self.base.compatible_versions.all())

        self.delete(self.busspuren)

        for version in (self.base, self.combination):
            with self.subTest(version=version.name):
                self.assertNotIn(
                    "Busspuren",
                    set(version.compatible_versions.values_list("name", flat=True)),
                )

    def test_its_picture_goes_with_it(self):
        self.neubau.change_img.save("neubau.png", ContentFile(b"png"), save=True)
        path = self.neubau.change_img.path
        self.assertTrue(os.path.exists(path))

        with self.captureOnCommitCallbacks(execute=True):
            self.delete(self.neubau)

        self.assertFalse(os.path.exists(path))

    def test_the_graph_is_read_again_afterwards(self):
        """A pin, green before F14 as well: every node lists its versions and
        their ballot, and the graph is cached for an hour."""
        url = reverse(
            "maps:mapversion-graph",
            kwargs={"pk": self.game_map.pk, "version_pk": self.base.pk},
        )

        def named_versions():
            named = set()
            for node in self.client.get(url).json()["nodes"]:
                for version in node["map_versions"]:
                    named |= {version["id"], *version["compatible_versions"]}
            return named

        self.assertIn(self.busspuren.pk, named_versions())

        self.delete(self.busspuren)

        self.assertNotIn(self.busspuren.pk, named_versions())

    # --- what refuses it ----------------------------------------------------

    def test_the_base_version_is_refused(self):
        before = {model.__name__: model.objects.count() for model in VERSIONED}

        response = self.delete(self.base)

        self.assertRefused(response, "base", "Grundversion")
        self.assertTrue(MapVersion.objects.filter(pk=self.base.pk).exists())
        self.assertEqual(
            {model.__name__: model.objects.count() for model in VERSIONED}, before
        )

    def test_a_running_game_on_the_map_refuses_it(self):
        """Even on base: the class may vote for any version after the round."""
        self.game(is_active=True, active_map_version=self.base)

        self.assertRefused(self.delete(self.neubau), "running", "»Dienstag«")

    def test_a_paused_game_is_still_running(self):
        self.game(
            is_active=True, active_map_version=self.base, paused_at=timezone.now()
        )

        self.assertRefused(self.delete(self.neubau), "running")

    def test_a_game_in_the_lobby_does_not_refuse_it(self):
        self.game()

        self.assertEqual(self.delete(self.neubau).status_code, 204)

    def test_an_ended_game_played_on_it_refuses_it(self):
        self.ended_game(active_map_version=self.neubau)

        self.assertRefused(self.delete(self.neubau), "played", "»Dienstag«")

    def test_an_ended_game_that_had_it_on_the_ballot_refuses_it(self):
        game = self.ended_game(active_map_version=self.base)
        GameRound.objects.create(
            game=game, round_number=1, vote_option_ids=[self.neubau.pk]
        )

        self.assertRefused(self.delete(self.neubau), "played")

    def test_a_vote_cast_for_it_refuses_it(self):
        game = self.ended_game(active_map_version=self.base)
        game_round = GameRound.objects.create(game=game, round_number=1)
        player = Player.objects.create(game=game, name="Ada")
        MapVersionVote.objects.create(
            game_round=game_round, player=player, map_version=self.neubau
        )

        self.assertRefused(self.delete(self.neubau), "played")

    def test_a_route_over_its_streets_refuses_it(self):
        """The data that would go: `RouteSegment.edge` is CASCADE."""
        game = self.ended_game(active_map_version=self.base)
        game_round = GameRound.objects.create(game=game, round_number=1)
        player = Player.objects.create(game=game, name="Ada")
        move = PlayerMove.objects.create(
            session_round=game_round, player=player, action="submit"
        )
        route = AgentRoute.objects.create(
            player_move=move,
            agent_id=1,
            transport_mode="car",
            total_distance_m=100,
            estimated_time_min=1,
        )
        edge = Edge.objects.get(pk=min(self.only_in(self.neubau)["Edge"]))
        segment = RouteSegment.objects.create(
            agent_route=route, order=0, edge=edge, mode="car"
        )

        self.assertRefused(self.delete(self.neubau), "played")
        self.assertTrue(RouteSegment.objects.filter(pk=segment.pk).exists())

    def test_a_game_that_never_saw_it_does_not_refuse_it(self):
        game = self.ended_game(active_map_version=self.base)
        game_round = GameRound.objects.create(
            game=game, round_number=1, vote_option_ids=[self.busspuren.pk]
        )
        player = Player.objects.create(game=game, name="Ada")
        MapVersionVote.objects.create(
            game_round=game_round, player=player, map_version=self.busspuren
        )

        self.assertEqual(self.delete(self.neubau).status_code, 204)

    # --- the question before it ---------------------------------------------

    def test_the_preview_names_what_goes(self):
        before = {model.__name__: model.objects.count() for model in VERSIONED}

        response = self.preview(self.neubau)

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertIsNone(body["refusal"])
        self.assertEqual(
            body["goes"],
            {
                "nodes": 1,
                "edges": 2,
                "streets": 2,
                "rails": 0,
                "bus_lines": ["200"],
                "train_lines": ["U9"],
                "line_links": 4,
            },
        )
        self.assertEqual(body["keeps"], [])
        self.assertEqual(
            {model.__name__: model.objects.count() for model in VERSIONED},
            before,
            "asking deletes nothing",
        )

    def test_the_preview_of_a_change_names_the_combination_that_keeps_it(self):
        body = self.preview(self.busspuren).json()

        self.assertEqual(
            body["goes"],
            {
                "nodes": 0,
                "edges": 0,
                "streets": 0,
                "rails": 0,
                "bus_lines": [],
                "train_lines": [],
                "line_links": 0,
            },
        )
        self.assertEqual(body["keeps"], [self.combination.name])
        self.assertEqual(
            sorted(body["ballot"]), sorted([self.base.name, self.combination.name])
        )

    def test_the_preview_carries_the_refusal(self):
        self.ended_game(active_map_version=self.neubau)

        refusal = self.preview(self.neubau).json()["refusal"]

        self.assertEqual(refusal["reason"], "played")
        self.assertIn("»Dienstag«", refusal["detail"])

    # --- who may ------------------------------------------------------------

    def test_only_staff_may_delete_or_ask(self):
        get_user_model().objects.create_user(username="gast", password="pw12345!X")
        for login in ("gast", None):
            self.client.logout()
            if login:
                self.client.force_login(get_user_model().objects.get(username=login))
            with self.subTest(user=login):
                self.assertEqual(self.delete(self.neubau).status_code, 403)
                self.assertEqual(self.preview(self.neubau).status_code, 403)
        self.assertTrue(MapVersion.objects.filter(pk=self.neubau.pk).exists())

    def test_a_version_is_deleted_only_under_its_own_map(self):
        other = GameMap.objects.create(name="Andere Karte")

        response = self.delete(self.neubau, map_pk=other.pk)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(MapVersion.objects.filter(pk=self.neubau.pk).exists())


@override_settings(**TEST_BACKENDS)
class DeletingAVersionInTheAdminTests(DeletingAVersionMixin, TestCase):
    """The admin's delete runs the same cleanup — or it would not be a rule.

    Both its doors: the delete page of one version and the list's bulk
    "delete selected". A refusal shows as Django's "protected" list, which
    re-renders the page and deletes nothing on POST.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin", password="password123"
        )
        self.client.force_login(self.user)
        self.build_lattice()

    def delete_page(self, version):
        return reverse("admin:maps_mapversion_delete", args=[version.pk])

    def test_its_delete_takes_the_same_rows(self):
        only = self.only_in(self.neubau)

        response = self.client.post(self.delete_page(self.neubau), {"post": "yes"})

        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(MapVersion.objects.filter(pk=self.neubau.pk).exists())
        self.assertEqual(
            self.still_there(only), {model.__name__: set() for model in VERSIONED}
        )
        self.assertEqual(set(self.in_no_version().values()), {0})

    def test_its_confirmation_names_what_goes(self):
        page = self.client.get(self.delete_page(self.neubau)).content.decode()

        self.assertIn("»200«", page)
        self.assertIn("»U9«", page)

    def test_it_refuses_the_base_version(self):
        page = self.client.get(self.delete_page(self.base)).content.decode()
        self.assertIn("Grundversion", page)

        self.client.post(self.delete_page(self.base), {"post": "yes"})

        self.assertTrue(MapVersion.objects.filter(pk=self.base.pk).exists())

    def test_it_refuses_a_version_a_game_was_played_on(self):
        self.ended_game(active_map_version=self.neubau)

        self.client.post(self.delete_page(self.neubau), {"post": "yes"})

        self.assertTrue(MapVersion.objects.filter(pk=self.neubau.pk).exists())
        self.assertTrue(Node.objects.filter(pk__in=self.only_in(self.neubau)["Node"]))

    def test_its_bulk_delete_takes_the_same_rows(self):
        only = self.only_in(self.neubau)

        response = self.client.post(
            reverse("admin:maps_mapversion_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [self.neubau.pk],
                "post": "yes",
            },
        )

        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(MapVersion.objects.filter(pk=self.neubau.pk).exists())
        self.assertEqual(
            self.still_there(only), {model.__name__: set() for model in VERSIONED}
        )

    def test_its_bulk_delete_refuses_too(self):
        self.client.post(
            reverse("admin:maps_mapversion_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [self.neubau.pk, self.base.pk],
                "post": "yes",
            },
        )

        self.assertTrue(MapVersion.objects.filter(pk=self.base.pk).exists())
        self.assertTrue(MapVersion.objects.filter(pk=self.neubau.pk).exists())
