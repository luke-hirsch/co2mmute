import json
import logging
from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db import transaction
from django.urls import reverse_lazy
from maps.forms import MapUploadForm
from maps.models import (
    GameMap,
    MapVersion,
    Node,
    NodeType,
    Edge,
    StreetEdge,
    TrainEdge,
    BusLine,
    TrainLine,
)

logger = logging.getLogger(__name__)


class MapUploadView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """
    View for uploading a JSON file containing a graph structure and converting it to map models.

    Restricted to staff users only.

    Expected JSON format:
    {
        "nodes": [
            {"id": "A", "x": 0.0, "y": 0.0, "types": ["city"], "name": "Node A"},
            ...
        ],
        "edges": [
            {
                "start_node": "A",
                "end_node": "B",
                "biking": true,
                "walking": true,
                "name": "Main Street"
            },
            ...
        ]
    }
    """

    template_name = "maps/map_upload.html"
    form_class = MapUploadForm
    success_url = reverse_lazy("maps:gamemap-list")
    login_url = "login"

    def test_func(self):
        """Only allow staff users to upload maps."""
        return self.request.user.is_staff

    def handle_no_permission(self):
        """Redirect non-staff users with an error message."""
        messages.error(
            self.request,
            "You do not have permission to upload maps. Staff access required.",
        )
        return super().handle_no_permission()

    def form_valid(self, form):
        """Process the uploaded JSON file and create map models."""
        try:
            # Parse JSON from file
            json_file = form.cleaned_data["json_file"]
            json_file.seek(0)
            graph_data = json.loads(json_file.read().decode("utf-8"))

            # Extract form data
            map_name = form.cleaned_data["map_name"]
            description = form.cleaned_data.get("description", "")
            max_players = form.cleaned_data["max_players"]

            # Create map in a transaction
            with transaction.atomic():
                game_map = self._create_game_map(
                    name=map_name, max_players=max_players, author=self.request.user
                )

                # Create base version
                base_version = MapVersion.objects.create(
                    game_map=game_map,
                    name=f"{map_name} - Base",
                    description=description,
                    base_version=True,
                )

                # Create nodes and edges from JSON
                node_mapping = self._create_nodes(
                    game_map=game_map,
                    base_version=base_version,
                    nodes_data=graph_data.get("nodes", []),
                )

                edge_mapping = self._create_edges(
                    game_map=game_map,
                    base_version=base_version,
                    edges_data=graph_data.get("edges", []),
                    node_mapping=node_mapping,
                )

                # Create street and train edges
                self._create_specialized_edges(
                    base_version=base_version,
                    edges_data=graph_data.get("edges", []),
                    edge_mapping=edge_mapping,
                )

                # Create bus lines
                self._create_bus_lines(
                    game_map=game_map,
                    base_version=base_version,
                    bus_lines_data=graph_data.get("bus_lines", []),
                    edge_mapping=edge_mapping,
                )

                # Create train lines
                self._create_train_lines(
                    game_map=game_map,
                    base_version=base_version,
                    train_lines_data=graph_data.get("train_lines", []),
                    edges_data=graph_data.get("edges", []),
                    edge_mapping=edge_mapping,
                )

                messages.success(
                    self.request,
                    f"Map '{map_name}' created successfully with "
                    f"{len(node_mapping)} nodes and {len(graph_data.get('edges', []))} edges!",
                )
                logger.info(
                    f"User {self.request.user.username} created map '{map_name}' "
                    f"with {len(node_mapping)} nodes"
                )

        except Exception as e:
            logger.error(f"Error processing map upload: {str(e)}", exc_info=True)
            messages.error(self.request, f"Error creating map: {str(e)}")
            return self.form_invalid(form)

        return super().form_valid(form)

    def _create_game_map(self, name, max_players, author):
        """Create a GameMap instance."""
        # Calculate dimensions from nodes (will be updated after nodes are created)
        game_map = GameMap.objects.create(
            name=name,
            max_player=max_players,
            author=author,
            updated_by=author,
            x_dim=100,  # Default, can be adjusted
            y_dim=100,  # Default, can be adjusted
        )
        return game_map

    def _create_nodes(self, game_map, base_version, nodes_data):
        """
        Create Node instances from JSON data.

        Returns a mapping of node IDs to Node instances.
        """
        node_mapping = {}
        max_x = 0
        max_y = 0

        # Get or create node types
        node_types_cache = {}
        for node_data in nodes_data:
            for type_name in node_data.get("types", []):
                if type_name not in node_types_cache:
                    node_type, _ = NodeType.objects.get_or_create(
                        name=type_name, defaults={"short": type_name[:2].upper()}
                    )
                    node_types_cache[type_name] = node_type

        # Create nodes
        for node_data in nodes_data:
            node_id = str(node_data["id"])
            x_pos = float(node_data["x"])
            y_pos = float(node_data["y"])
            name = node_data.get("name", node_id)

            # Track max dimensions
            max_x = max(max_x, x_pos)
            max_y = max(max_y, y_pos)

            node = Node.objects.create(
                game_map=game_map, name=name, x_position=x_pos, y_position=y_pos
            )

            # Add to base version
            node.map_versions.add(base_version)

            # Add node types
            for type_name in node_data.get("types", []):
                node.node_type.add(node_types_cache[type_name])

            node_mapping[node_id] = node

        # Update map dimensions
        game_map.x_dim = int(max_x) + 1
        game_map.y_dim = int(max_y) + 1
        game_map.save()

        return node_mapping

    def _create_edges(self, game_map, base_version, edges_data, node_mapping):
        """
        Create Edge instances from JSON data.

        Returns a mapping of edge indices to Edge instances.
        """
        edge_mapping = {}

        for edge_idx, edge_data in enumerate(edges_data):
            start_node_id = str(edge_data["start_node"])
            end_node_id = str(edge_data["end_node"])

            # Validate nodes exist
            if start_node_id not in node_mapping:
                raise ValueError(
                    f"Start node '{start_node_id}' from edge not found in nodes"
                )
            if end_node_id not in node_mapping:
                raise ValueError(
                    f"End node '{end_node_id}' from edge not found in nodes"
                )

            start_node = node_mapping[start_node_id]
            end_node = node_mapping[end_node_id]

            edge = Edge.objects.create(
                game_map=game_map,
                name=edge_data.get("name", f"{start_node_id}-{end_node_id}"),
                start_node=start_node,
                end_node=end_node,
                biking=edge_data.get("biking", True),
                walking=edge_data.get("walking", True),
                max_lanes=edge_data.get("max_lanes", 2),
            )

            # Add to base version
            edge.map_versions.add(base_version)

            # Store mapping by index
            edge_mapping[edge_idx] = edge

        return edge_mapping

    def _create_specialized_edges(self, base_version, edges_data, edge_mapping):
        """
        Create StreetEdge and TrainEdge instances based on edge type specification.

        Edge type can be 'street', 'train', or 'both' (default: 'both')
        """
        for edge_idx, edge_data in enumerate(edges_data):
            edge = edge_mapping[edge_idx]
            edge_type = edge_data.get("type", "both")

            # Create StreetEdge if type is 'street' or 'both'
            if edge_type in ("street", "both"):
                street_edge = StreetEdge.objects.create(
                    edge=edge,
                    speed_limit=edge_data.get("speed_limit", 50),
                    lanes=edge_data.get("lanes", 1),
                    dedicated_bus_lane=edge_data.get("dedicated_bus_lane", False),
                )
                street_edge.map_versions.add(base_version)

            # Create TrainEdge if type is 'train' or 'both'
            if edge_type in ("train", "both"):
                train_edge = TrainEdge.objects.create(edge=edge)
                train_edge.map_versions.add(base_version)

    def _create_bus_lines(self, game_map, base_version, bus_lines_data, edge_mapping):
        """
        Create BusLine instances with their associated StreetEdges.

        bus_lines format:
        [
            {
                "name": "M1",
                "edges": [0, 1, 2],  # indices into edges array
                "interval": 5,
                "capacity": 60
            }
        ]
        """
        for bus_line_data in bus_lines_data:
            bus_line = BusLine.objects.create(
                game_map=game_map,
                name=bus_line_data["name"],
                intervall=bus_line_data.get("interval", 5),
                bus_capacity=bus_line_data.get("capacity", 60),
            )
            bus_line.map_versions.add(base_version)

            # Add street edges to bus line
            for edge_idx in bus_line_data.get("edges", []):
                if edge_idx not in edge_mapping:
                    raise ValueError(
                        f"Bus line '{bus_line_data['name']}': "
                        f"edge index {edge_idx} not found"
                    )
                edge = edge_mapping[edge_idx]

                # Get or create StreetEdge for this edge
                street_edge = StreetEdge.objects.filter(edge=edge).first()
                if not street_edge:
                    street_edge = StreetEdge.objects.create(edge=edge)
                    street_edge.map_versions.add(base_version)

                bus_line.edges.add(street_edge)

    def _create_train_lines(
        self, game_map, base_version, train_lines_data, edges_data, edge_mapping
    ):
        """
        Create TrainLine instances with their associated TrainEdges.

        train_lines format:
        [
            {
                "name": "S1",
                "edges": [0, 1, 2],  # indices into edges array
                "interval": 10,
                "capacity": 500
            }
        ]
        """
        for train_line_data in train_lines_data:
            train_line = TrainLine.objects.create(
                game_map=game_map,
                name=train_line_data["name"],
                intervall=train_line_data.get("interval", 10),
                train_capacity=train_line_data.get("capacity", 500),
            )
            train_line.map_versions.add(base_version)

            # Add train edges to train line
            for edge_idx in train_line_data.get("edges", []):
                if edge_idx not in edge_mapping:
                    raise ValueError(
                        f"Train line '{train_line_data['name']}': "
                        f"edge index {edge_idx} not found"
                    )
                edge = edge_mapping[edge_idx]

                # Get or create TrainEdge for this edge
                train_edge = TrainEdge.objects.filter(edge=edge).first()
                if not train_edge:
                    train_edge = TrainEdge.objects.create(edge=edge)
                    train_edge.map_versions.add(base_version)

                train_line.edges.add(train_edge)
