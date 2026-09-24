"""PT lines: the stop list a line reports for routing.

`ptRouting.ts` boards and alights only at the node ids a line lists in `stops`,
so a line that under-reports its stops is a line nobody can take. The shipped
example maps store every edge of every line reversed relative to the direction
of travel, which is the case the serializer used to give up on — see
`.claude/plans/to-do/[backend]-pt-stops.md`.
"""

from django.test import TestCase

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
from maps.serializer import (
    _stops_in_travel_order,
    serialize_bus_line_for_graph,
    serialize_train_line_for_graph,
)


class PTFixtureMixin:
    """A map with a row of nodes and the edges between them.

    Nodes are laid out left to right so an edge chain is easy to read: node i
    sits at x=i. `self.nodes[i]` is the i-th node, `self.edge(a, b)` an edge
    from node a to node b — stored in exactly that direction, which is the
    whole point of these tests.
    """

    @classmethod
    def setUpTestData(cls):
        cls.game_map = GameMap.objects.create(name="PT test map", x_dim=50, y_dim=50)
        cls.version = MapVersion.objects.create(
            game_map=cls.game_map, name="base", base_version=True
        )
        cls.nodes = []
        for i in range(6):
            node = Node.objects.create(
                game_map=cls.game_map, name=f"N{i}", x_position=i, y_position=0
            )
            node.map_versions.add(cls.version)
            cls.nodes.append(node)

    @classmethod
    def edge(cls, start_index, end_index):
        edge = Edge.objects.create(
            game_map=cls.game_map,
            name=f"E{start_index}-{end_index}",
            start_node=cls.nodes[start_index],
            end_node=cls.nodes[end_index],
        )
        edge.map_versions.add(cls.version)
        return edge

    @classmethod
    def node_id(cls, index):
        return cls.nodes[index].pk


class StopsInTravelOrderTests(PTFixtureMixin, TestCase):
    """The chain builder itself."""

    def test_forward_chain_lists_every_node(self):
        edges = [self.edge(0, 1), self.edge(1, 2), self.edge(2, 3)]

        stops = _stops_in_travel_order(edges, "line under test")

        self.assertEqual(
            stops, [self.node_id(0), self.node_id(1), self.node_id(2), self.node_id(3)]
        )

    def test_fully_reversed_chain_lists_every_node(self):
        """The shipped-map case: every edge stored against the travel direction.

        Each edge's start_node is the *next* stop, not the previous one. Seeding
        the chain from the first edge in stored order makes the second edge look
        disconnected, which is how a nine-edge line came to report two stops.
        """
        edges = [self.edge(1, 0), self.edge(2, 1), self.edge(3, 2)]

        stops = _stops_in_travel_order(edges, "line under test")

        self.assertEqual(
            stops, [self.node_id(0), self.node_id(1), self.node_id(2), self.node_id(3)]
        )

    def test_mixed_directions_list_every_node(self):
        edges = [self.edge(0, 1), self.edge(2, 1), self.edge(2, 3), self.edge(4, 3)]

        stops = _stops_in_travel_order(edges, "line under test")

        self.assertEqual(
            stops,
            [
                self.node_id(0),
                self.node_id(1),
                self.node_id(2),
                self.node_id(3),
                self.node_id(4),
            ],
        )

    def test_single_edge_gives_both_of_its_nodes(self):
        stops = _stops_in_travel_order([self.edge(2, 3)], "line under test")

        self.assertEqual(stops, [self.node_id(2), self.node_id(3)])

    def test_no_edges_gives_no_stops(self):
        self.assertEqual(_stops_in_travel_order([], "line under test"), [])

    def test_disconnected_edge_truncates_and_warns(self):
        """A line whose edges do not touch is a broken map: say so, don't guess."""
        edges = [self.edge(0, 1), self.edge(1, 2), self.edge(4, 5)]

        with self.assertLogs("maps.serializer", level="WARNING") as captured:
            stops = _stops_in_travel_order(edges, "line under test")

        self.assertEqual(
            stops, [self.node_id(0), self.node_id(1), self.node_id(2)]
        )
        self.assertIn("disconnected", " ".join(captured.output).lower())


class GraphSerializerPTTests(PTFixtureMixin, TestCase):
    """The payload the client actually routes on."""

    def test_train_line_reports_every_stop_when_edges_are_reversed(self):
        edges = [self.edge(1, 0), self.edge(2, 1), self.edge(3, 2)]
        line = TrainLine.objects.create(
            game_map=self.game_map, name="U-Test", train_capacity=400
        )
        line.map_versions.add(self.version)
        for order, edge in enumerate(edges):
            train_edge = TrainEdge.objects.create(edge=edge)
            train_edge.map_versions.add(self.version)
            TrainLineEdge.objects.create(
                train_line=line, train_edge=train_edge, order=order
            )

        payload = serialize_train_line_for_graph(line, self.version)

        self.assertEqual(payload["type"], "train")
        self.assertEqual(len(payload["edges"]), 3)
        # A connected line always has one more stop than it has edges.
        self.assertEqual(len(payload["stops"]), 4)
        self.assertEqual(
            payload["stops"],
            [self.node_id(0), self.node_id(1), self.node_id(2), self.node_id(3)],
        )

    def test_bus_line_reports_every_stop_when_edges_are_reversed(self):
        edges = [self.edge(1, 0), self.edge(2, 1)]
        line = BusLine.objects.create(
            game_map=self.game_map, name="B-Test", bus_capacity=80
        )
        line.map_versions.add(self.version)
        for order, edge in enumerate(edges):
            street_edge = StreetEdge.objects.create(edge=edge)
            street_edge.map_versions.add(self.version)
            BusLineEdge.objects.create(
                bus_line=line, street_edge=street_edge, order=order
            )

        payload = serialize_bus_line_for_graph(line, self.version)

        self.assertEqual(payload["type"], "bus")
        self.assertEqual(len(payload["edges"]), 2)
        self.assertEqual(
            payload["stops"],
            [self.node_id(0), self.node_id(1), self.node_id(2)],
        )

    def test_line_without_edges_reports_no_stops(self):
        """The shipped example's two bus lines. Empty is correct, not a crash."""
        line = BusLine.objects.create(
            game_map=self.game_map, name="B-Leer", bus_capacity=80
        )
        line.map_versions.add(self.version)

        payload = serialize_bus_line_for_graph(line, self.version)

        self.assertEqual(payload["edges"], [])
        self.assertEqual(payload["stops"], [])


class PTCapacityDefaultTests(PTFixtureMixin, TestCase):
    """A line drawn without a capacity gets a plausible vehicle, not 60 seats.

    `[backend]-pt-timetable-and-society.md` §2.5. Five places disagreed about
    what an unspecified PT vehicle holds, and the one a map author actually
    meets — the editor's new-line panel — did not branch on mode at all. That
    is how the shipped map came to carry a 60-seat U-Bahn.

    The numbers are game parameters with a real order of magnitude behind them:
    a 12 m city bus carries 70-100 including standing room, a Großprofil
    U-Bahn train and a full S-Bahn are both around a thousand. After the
    timetable change nothing in the emissions path reads them, so they can be
    corrected without moving a reported number.
    """

    def test_a_bus_line_without_a_capacity_seats_a_city_bus(self):
        line = BusLine.objects.create(game_map=self.game_map, name="M99")

        self.assertEqual(line.bus_capacity, 85)

    def test_a_train_line_without_a_capacity_seats_a_full_train(self):
        line = TrainLine.objects.create(game_map=self.game_map, name="U99")

        self.assertEqual(line.train_capacity, 1000)

    def test_an_explicit_capacity_still_wins(self):
        """The default is a default — a map author's own number is data."""
        bus = BusLine.objects.create(
            game_map=self.game_map, name="M98", bus_capacity=40
        )
        train = TrainLine.objects.create(
            game_map=self.game_map, name="U98", train_capacity=200
        )

        self.assertEqual(bus.bus_capacity, 40)
        self.assertEqual(train.train_capacity, 200)
