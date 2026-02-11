import json
import logging
from django.views.generic import FormView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.shortcuts import redirect
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
    BusLineEdge,
    TrainLine,
    TrainLineEdge,
)

logger = logging.getLogger(__name__)


class MapUploadView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = "maps/map_upload.html"
    form_class = MapUploadForm
    login_url = "login"

    def get_success_url(self):
        latest_map = GameMap.objects.latest("created")
        return reverse("map-detail", kwargs={"pk": latest_map.pk})

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(
            self.request,
            "You do not have permission to upload maps. Staff access required.",
        )
        return super().handle_no_permission()

    def form_valid(self, form):
        try:
            # Extract form data
            json_file = form.cleaned_data.get("json_file")
            image_file = form.cleaned_data.get("image_file")
            map_name = form.cleaned_data["map_name"]
            description = form.cleaned_data.get("description", "")
            max_players = form.cleaned_data["max_players"]

            # Parse JSON if provided
            graph_data = None
            if json_file:
                json_file.seek(0)
                graph_data = json.loads(json_file.read().decode("utf-8"))

                # Run validation checks first (dry run)
                validation_errors = self._validate_graph_data(graph_data)
                if validation_errors:
                    error_message = "JSON validation errors found:\n" + "\n".join(
                        [f"• {error}" for error in validation_errors]
                    )
                    logger.warning(
                        f"Validation errors for map '{map_name}': {validation_errors}"
                    )
                    messages.error(self.request, error_message)
                    return self.form_invalid(form)

            logger.info(f"Starting map creation for '{map_name}'")

            # Create map in a transaction
            with transaction.atomic():
                scale = graph_data.get("scale", 1.0) if graph_data else 1.0
                game_map = self._create_game_map(
                    name=map_name, max_players=max_players, author=self.request.user, scale=scale
                )
                logger.info(f"Created GameMap with pk {game_map.pk}")

                # Save background image if provided
                if image_file:
                    game_map.background_image = image_file
                    game_map.save()

                # Create base version
                base_version = MapVersion.objects.create(
                    game_map=game_map,
                    name=f"{map_name} - Base",
                    description=description,
                    base_version=True,
                )
                logger.info(f"Created MapVersion with pk {base_version.pk}")

                if graph_data:
                    # Create nodes and edges from JSON
                    node_mapping = self._create_nodes(
                        game_map=game_map,
                        base_version=base_version,
                        nodes_data=graph_data.get("nodes", []),
                    )
                    logger.info(f"Created {len(node_mapping)} nodes")

                    edge_mapping = self._create_edges(
                        game_map=game_map,
                        base_version=base_version,
                        edges_data=graph_data.get("edges", []),
                        node_mapping=node_mapping,
                    )
                    logger.info(f"Created {len(edge_mapping)} edges")

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
                else:
                    messages.success(
                        self.request,
                        f"Blank map '{map_name}' created successfully!",
                    )
                    logger.info(
                        f"User {self.request.user.username} created blank map '{map_name}'"
                    )

        except Exception as e:
            logger.error(f"Error processing map upload: {str(e)}", exc_info=True)
            messages.error(self.request, f"Error creating map: {str(e)}")
            return self.form_invalid(form)

        logger.info(f"Redirecting to success_url: {self.success_url}")
        return super().form_valid(form)

    def _validate_graph_data(self, graph_data):
        errors = []

        # Check basic structure
        if not isinstance(graph_data, dict):
            errors.append("JSON root must be an object/dictionary")
            return errors

        nodes_data = graph_data.get("nodes", [])
        edges_data = graph_data.get("edges", [])
        bus_lines_data = graph_data.get("bus_lines", [])
        train_lines_data = graph_data.get("train_lines", [])

        # Validate nodes
        if not nodes_data:
            errors.append("At least one node is required")
        else:
            node_ids = set()
            for idx, node in enumerate(nodes_data):
                node_id = str(node.get("id", ""))
                if not node_id:
                    errors.append(f"Node {idx}: missing or empty 'id' field")
                if node_id in node_ids:
                    errors.append(f"Node {idx}: duplicate id '{node_id}'")
                node_ids.add(node_id)

                if "x" not in node:
                    errors.append(f"Node '{node_id}': missing 'x' coordinate")
                if "y" not in node:
                    errors.append(f"Node '{node_id}': missing 'y' coordinate")

        # Validate edges
        if not edges_data:
            errors.append("At least one edge is required")
        else:
            for idx, edge in enumerate(edges_data):
                start = str(edge.get("start_node", ""))
                end = str(edge.get("end_node", ""))

                if not start:
                    errors.append(f"Edge {idx}: missing or empty 'start_node' field")
                elif start not in node_ids:
                    errors.append(
                        f"Edge {idx}: start_node '{start}' not found in nodes"
                    )

                if not end:
                    errors.append(f"Edge {idx}: missing or empty 'end_node' field")
                elif end not in node_ids:
                    errors.append(f"Edge {idx}: end_node '{end}' not found in nodes")

                # Validate edge type
                edge_type = edge.get("type", "both")
                if edge_type not in ("street", "train", "both"):
                    errors.append(
                        f"Edge {idx}: invalid type '{edge_type}'. "
                        f"Must be 'street', 'train', or 'both'"
                    )

                # Validate that train-only edges don't have biking/walking
                if edge_type == "train":
                    if edge.get("biking", False) or edge.get("walking", False):
                        errors.append(
                            f"Edge {idx}: train-only edges should not have "
                            f"biking=true or walking=true"
                        )

        # Validate bus lines
        for bus_line_idx, bus_line in enumerate(bus_lines_data):
            bus_name = bus_line.get("name", f"BusLine {bus_line_idx}")
            edges = bus_line.get("edges", [])

            if not edges:
                errors.append(f"Bus line '{bus_name}': no edges specified")
            else:
                for edge_idx in edges:
                    if not isinstance(edge_idx, int) or edge_idx < 0:
                        errors.append(
                            f"Bus line '{bus_name}': invalid edge index {edge_idx}"
                        )
                    elif edge_idx >= len(edges_data):
                        errors.append(
                            f"Bus line '{bus_name}': edge index {edge_idx} not found "
                            f"(only {len(edges_data)} edges available)"
                        )

        # Validate train lines
        for train_line_idx, train_line in enumerate(train_lines_data):
            train_name = train_line.get("name", f"TrainLine {train_line_idx}")
            edges = train_line.get("edges", [])

            if not edges:
                errors.append(f"Train line '{train_name}': no edges specified")
            else:
                for edge_idx in edges:
                    if not isinstance(edge_idx, int) or edge_idx < 0:
                        errors.append(
                            f"Train line '{train_name}': invalid edge index {edge_idx}"
                        )
                    elif edge_idx >= len(edges_data):
                        errors.append(
                            f"Train line '{train_name}': edge index {edge_idx} not found "
                            f"(only {len(edges_data)} edges available)"
                        )

        return errors

    def _create_game_map(self, name, max_players, author, scale=1.0):
        game_map = GameMap.objects.create(
            name=name,
            max_player=max_players,
            author=author,
            updated_by=author,
            x_dim=100,  # Default, can be adjusted
            y_dim=100,  # Default, can be adjusted
            scale=scale,
        )
        return game_map

    def _create_nodes(self, game_map, base_version, nodes_data):
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
        edge_mapping = {}

        for edge_idx, edge_data in enumerate(edges_data):
            start_node_id = str(edge_data["start_node"])
            end_node_id = str(edge_data["end_node"])

            # Validate nodes exist
            if start_node_id not in node_mapping:
                available_nodes = ", ".join(sorted(node_mapping.keys()))
                raise ValueError(
                    f"Start node '{start_node_id}' from edge not found in nodes. "
                    f"Available nodes: {available_nodes}"
                )
            if end_node_id not in node_mapping:
                available_nodes = ", ".join(sorted(node_mapping.keys()))
                raise ValueError(
                    f"End node '{end_node_id}' from edge not found in nodes. "
                    f"Available nodes: {available_nodes}"
                )

            start_node = node_mapping[start_node_id]
            end_node = node_mapping[end_node_id]

            edge_type = edge_data.get("type", "both")
            default_biking = False if edge_type == "train" else True
            default_walking = False if edge_type == "train" else True

            edge = Edge.objects.create(
                game_map=game_map,
                name=edge_data.get("name", f"{start_node_id}-{end_node_id}"),
                start_node=start_node,
                end_node=end_node,
                biking=edge_data.get("biking", default_biking),
                walking=edge_data.get("walking", default_walking),
                max_lanes=edge_data.get("max_lanes", 2),
            )

            # Add to base version
            edge.map_versions.add(base_version)

            # Store mapping by index
            edge_mapping[edge_idx] = edge

        return edge_mapping

    def _create_specialized_edges(self, base_version, edges_data, edge_mapping):
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
        for bus_line_data in bus_lines_data:
            bus_line = BusLine.objects.create(
                game_map=game_map,
                name=bus_line_data["name"],
                intervall=bus_line_data.get("interval", 5),
                bus_capacity=bus_line_data.get("capacity", 60),
            )
            bus_line.map_versions.add(base_version)

            # Add street edges to bus line (ordered)
            for order, edge_idx in enumerate(bus_line_data.get("edges", [])):
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

                BusLineEdge.objects.create(
                    bus_line=bus_line, street_edge=street_edge, order=order
                )

    def _create_train_lines(
        self, game_map, base_version, train_lines_data, edges_data, edge_mapping
    ):
        for train_line_data in train_lines_data:
            train_line = TrainLine.objects.create(
                game_map=game_map,
                name=train_line_data["name"],
                intervall=train_line_data.get("interval", 10),
                train_capacity=train_line_data.get("capacity", 500),
            )
            train_line.map_versions.add(base_version)

            # Add train edges to train line (ordered)
            for order, edge_idx in enumerate(train_line_data.get("edges", [])):
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

                TrainLineEdge.objects.create(
                    train_line=train_line, train_edge=train_edge, order=order
                )


class MapListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = GameMap
    template_name = "maps/map_list.html"
    login_url = "login"

    def test_func(self):
        """Only allow staff users to upload maps."""
        return self.request.user.is_staff


class MapEditorView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Interactive map editor using Cytoscape.js for graph manipulation."""

    model = GameMap
    template_name = "maps/map_editor.html"
    login_url = "login"

    def test_func(self):
        """Only allow staff users to edit maps."""
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        """Prepare map data in Cytoscape.js compatible format."""
        context = super().get_context_data(**kwargs)
        game_map = self.get_object()

        # Get the base version
        base_version = MapVersion.objects.filter(
            game_map=game_map, base_version=True
        ).first()

        # Get all node types for the template
        all_node_types = NodeType.objects.all()
        context["node_types"] = all_node_types

        if base_version:
            context["node_types_json"] = json.dumps(
                [
                    {"id": nt.pk, "name": nt.name, "short": nt.short}
                    for nt in all_node_types
                ]
            )

            # Get nodes and edges for the base version
            nodes = Node.objects.filter(
                game_map=game_map, map_versions=base_version
            ).prefetch_related("node_type")

            edges = Edge.objects.filter(
                game_map=game_map, map_versions=base_version
            ).select_related("start_node", "end_node")

            # Pre-fetch street edges and train edges
            edge_pks = [edge.pk for edge in edges]
            street_edges_map = {
                se.edge.pk: se for se in StreetEdge.objects.filter(edge_id__in=edge_pks)
            }
            train_edges_map = {
                te.edge.pk: te for te in TrainEdge.objects.filter(edge_id__in=edge_pks)
            }

            # Format nodes for Cytoscape.js
            cytoscape_nodes = []
            for node in nodes:
                cytoscape_nodes.append(
                    {
                        "data": {
                            "id": str(node.pk),
                            "name": node.name,
                            "nodeTypes": [nt.id for nt in node.node_type.all()],
                        },
                        "position": {
                            "x": float(node.x_position),
                            "y": float(node.y_position),
                        },
                    }
                )

            # Format edges for Cytoscape.js
            cytoscape_edges = []
            for edge in edges:
                street_edge = street_edges_map.get(edge.pk)
                train_edge = train_edges_map.get(edge.pk)

                # Determine edge type
                edge_type = "path"
                if street_edge and train_edge:
                    edge_type = "both"
                elif street_edge:
                    edge_type = "street"
                elif train_edge:
                    edge_type = "train"

                edge_data = {
                    "data": {
                        "id": str(edge.pk),
                        "source": str(edge.start_node.pk),
                        "target": str(edge.end_node.pk),
                        "name": edge.name,
                        "biking": edge.biking,
                        "walking": edge.walking,
                        "maxLanes": edge.max_lanes,
                        "edgeType": edge_type,
                    }
                }

                # Add street edge properties if present
                if street_edge:
                    edge_data["data"]["speedLimit"] = street_edge.speed_limit
                    edge_data["data"]["lanes"] = street_edge.lanes
                    edge_data["data"]["dedicatedBusLane"] = (
                        street_edge.dedicated_bus_lane
                    )

                cytoscape_edges.append(edge_data)

            context["nodes_json"] = json.dumps(cytoscape_nodes)
            context["edges_json"] = json.dumps(cytoscape_edges)
            context["base_version"] = base_version
        else:
            # No base version - provide empty data
            context["nodes_json"] = json.dumps([])
            context["edges_json"] = json.dumps([])
            context["base_version"] = None

        return context

    def post(self, request, *args, **kwargs):
        """Handle saving the edited map as a new version."""
        game_map = self.get_object()
        if not isinstance(game_map, GameMap):
            messages.error(request, "Map not found")
            return self.get(request, *args, **kwargs)

        try:
            # Get form data
            version_name = request.POST.get("version_name", "").strip()
            description = request.POST.get("description", "").strip()
            is_base_version = request.POST.get("base_version") == "on"
            graph_data_str = request.POST.get("graph_data", "{}")

            if not version_name:
                messages.error(request, "Version name is required.")
                return self.get(request, *args, **kwargs)

            # Parse graph data from JSON
            graph_data = json.loads(graph_data_str)
            nodes_data = graph_data.get("nodes", [])
            edges_data = graph_data.get("edges", [])

            logger.info(
                f"Saving new version '{version_name}' for map '{game_map.name}' "
                f"with {len(nodes_data)} nodes and {len(edges_data)} edges"
            )

            with transaction.atomic():
                # If this is set as base version, unset other base versions
                if is_base_version:
                    MapVersion.objects.filter(
                        game_map=game_map, base_version=True
                    ).update(base_version=False)

                # Create new version
                new_version = MapVersion.objects.create(
                    game_map=game_map,
                    name=version_name,
                    description=description,
                    base_version=is_base_version,
                )

                # Build mapping from cytoscape IDs to new/existing nodes
                cy_id_to_node = {}

                # Process nodes
                for node_data in nodes_data:
                    cy_id = node_data.get("cyId")
                    original_id = node_data.get("id")
                    is_new = node_data.get("isNew", False)

                    if is_new or original_id is None:
                        # Create new node
                        node = Node.objects.create(
                            game_map=game_map,
                            name=node_data.get("name", "New Node"),
                            x_position=node_data.get("x_position", 0),
                            y_position=node_data.get("y_position", 0),
                        )
                    else:
                        # Get existing node
                        node = Node.objects.get(pk=original_id)
                        # Update position if changed
                        node.x_position = node_data.get("x_position", node.x_position)
                        node.y_position = node_data.get("y_position", node.y_position)
                        node.name = node_data.get("name", node.name)
                        node.save()

                    # Add to new version
                    node.map_versions.add(new_version)

                    # Update node types
                    node_type_ids = node_data.get("node_types", [])
                    if node_type_ids:
                        node.node_type.set(
                            NodeType.objects.filter(pk__in=node_type_ids)
                        )

                    cy_id_to_node[cy_id] = node

                # Process edges
                for edge_data in edges_data:
                    original_id = edge_data.get("id")
                    is_new = edge_data.get("isNew", False)
                    source_cy_id = edge_data.get("source_cyId")
                    target_cy_id = edge_data.get("target_cyId")

                    # Get source and target nodes
                    start_node = cy_id_to_node.get(source_cy_id)
                    end_node = cy_id_to_node.get(target_cy_id)

                    if not start_node or not end_node:
                        logger.warning(
                            f"Skipping edge: source={source_cy_id}, target={target_cy_id} "
                            f"- nodes not found"
                        )
                        continue

                    if is_new or original_id is None:
                        # Create new edge
                        edge = Edge.objects.create(
                            game_map=game_map,
                            name=edge_data.get(
                                "name", f"{start_node.name}-{end_node.name}"
                            ),
                            start_node=start_node,
                            end_node=end_node,
                            biking=edge_data.get("biking", True),
                            walking=edge_data.get("walking", True),
                            max_lanes=edge_data.get("max_lanes", 2),
                        )
                    else:
                        # Get existing edge
                        edge = Edge.objects.get(pk=original_id)
                        # Update properties
                        edge.name = edge_data.get("name", edge.name)
                        edge.biking = edge_data.get("biking", edge.biking)
                        edge.walking = edge_data.get("walking", edge.walking)
                        edge.max_lanes = edge_data.get("max_lanes", edge.max_lanes)
                        edge.save()

                    # Add to new version
                    edge.map_versions.add(new_version)

                    # Handle street/train edge types
                    edge_type = edge_data.get("edge_type", "path")

                    # Create or update StreetEdge
                    if edge_type in ("street", "both"):
                        street_edge, created = StreetEdge.objects.get_or_create(
                            edge=edge,
                            defaults={
                                "speed_limit": edge_data.get("speed_limit", 50),
                                "lanes": edge_data.get("lanes", 1),
                                "dedicated_bus_lane": edge_data.get(
                                    "dedicated_bus_lane", False
                                ),
                            },
                        )
                        if not created:
                            street_edge.speed_limit = edge_data.get(
                                "speed_limit", street_edge.speed_limit
                            )
                            street_edge.lanes = edge_data.get(
                                "lanes", street_edge.lanes
                            )
                            street_edge.dedicated_bus_lane = edge_data.get(
                                "dedicated_bus_lane", street_edge.dedicated_bus_lane
                            )
                            street_edge.save()
                        street_edge.map_versions.add(new_version)
                    else:
                        # Remove from street edges if it was one
                        StreetEdge.objects.filter(edge=edge).exclude(
                            map_versions=new_version
                        ).delete()

                    # Create or update TrainEdge
                    if edge_type in ("train", "both"):
                        train_edge, created = TrainEdge.objects.get_or_create(edge=edge)
                        train_edge.map_versions.add(new_version)
                    else:
                        # Remove from train edges if it was one
                        TrainEdge.objects.filter(edge=edge).exclude(
                            map_versions=new_version
                        ).delete()

            messages.success(
                request,
                f"Map version '{version_name}' saved successfully with "
                f"{len(nodes_data)} nodes and {len(edges_data)} edges!",
            )
            logger.info(
                f"User {request.user.username} saved version '{version_name}' "
                f"for map '{game_map.name}'"
            )

            return redirect("map-detail", pk=game_map.pk)

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            messages.error(request, f"Invalid graph data format: {e}")
            return self.get(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error saving map version: {e}", exc_info=True)
            messages.error(request, f"Error saving map version: {e}")
            return self.get(request, *args, **kwargs)


class MapDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = GameMap
    template_name = "maps/map_detail.html"
    login_url = "login"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        game_map = self.get_object()

        all_versions = list(MapVersion.objects.filter(game_map=game_map).order_by("pk"))
        context["all_versions"] = all_versions
        context["version_count"] = len(all_versions)

        version_pk = self.request.GET.get("version")
        if version_pk:
            try:
                current_version = MapVersion.objects.get(
                    pk=version_pk, game_map=game_map
                )
            except MapVersion.DoesNotExist:
                current_version = None
        else:
            # Default to base version
            current_version = MapVersion.objects.filter(
                game_map=game_map, base_version=True
            ).first()

        if not current_version and all_versions:
            current_version = all_versions[0]

        if current_version:
            try:
                current_index = all_versions.index(current_version)
            except ValueError:
                current_index = 0

            context["current_version"] = current_version
            context["current_index"] = current_index + 1  # 1-based for display
            context["prev_version"] = (
                all_versions[current_index - 1] if current_index > 0 else None
            )
            context["next_version"] = (
                all_versions[current_index + 1]
                if current_index < len(all_versions) - 1
                else None
            )

            nodes = Node.objects.filter(
                game_map=game_map, map_versions=current_version
            ).prefetch_related("node_type")

            edges = Edge.objects.filter(
                game_map=game_map, map_versions=current_version
            ).select_related("start_node", "end_node")

            bus_lines = BusLine.objects.filter(
                game_map=game_map, map_versions=current_version
            )
            train_lines = TrainLine.objects.filter(
                game_map=game_map, map_versions=current_version
            )

            nodes_json = json.dumps(
                [
                    {
                        "id": node.pk,
                        "name": node.name,
                        "x_position": float(node.x_position),
                        "y_position": float(node.y_position),
                        "node_type": [
                            {"id": nt.id, "name": nt.name, "short": nt.short}
                            for nt in node.node_type.all()
                        ],
                    }
                    for node in nodes
                ]
            )

            edge_pks = [edge.pk for edge in edges]
            street_edges_map = {
                se.edge.pk: se for se in StreetEdge.objects.filter(edge_id__in=edge_pks)
            }
            train_edges_map = {
                te.edge.pk: te for te in TrainEdge.objects.filter(edge_id__in=edge_pks)
            }

            edges_json = json.dumps(
                [
                    {
                        "id": edge.pk,
                        "name": edge.name,
                        "start_node": edge.start_node.pk,
                        "end_node": edge.end_node.pk,
                        "biking": edge.biking,
                        "walking": edge.walking,
                        "max_lanes": edge.max_lanes,
                        "street_edge": {
                            "id": street_edges_map[edge.pk].pk,
                            "speed_limit": street_edges_map[edge.pk].speed_limit,
                            "lanes": street_edges_map[edge.pk].lanes,
                            "dedicated_bus_lane": street_edges_map[
                                edge.pk
                            ].dedicated_bus_lane,
                        }
                        if edge.pk in street_edges_map
                        else None,
                        "train_edge": {"id": train_edges_map[edge.pk].pk}
                        if edge.pk in train_edges_map
                        else None,
                    }
                    for edge in edges
                ]
            )

            context["base_version"] = current_version
            context["nodes"] = nodes
            context["edges"] = edges
            context["bus_lines"] = bus_lines
            context["train_lines"] = train_lines
            context["node_count"] = nodes.count()
            context["edge_count"] = edges.count()
            context["bus_line_count"] = bus_lines.count()
            context["train_line_count"] = train_lines.count()
            context["nodes_json"] = nodes_json
            context["edges_json"] = edges_json

        return context
