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

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from game.tests._helpers import TEST_BACKENDS
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

    def _diff(self, name, **changes):
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
