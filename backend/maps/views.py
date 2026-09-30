import base64
import binascii
import json
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.files.base import ContentFile
from django.db import transaction
from django.views.generic import FormView, RedirectView

from maps.forms import MapUploadForm
from maps.models import (
    BusLine,
    BusLineEdge,
    Edge,
    GameMap,
    MapVersion,
    Node,
    NodeType,
    StreetEdge,
    TrainEdge,
    TrainLine,
    TrainLineEdge,
)
from maps.portability import (
    DEFAULT_POLL_TEXT,
    base_index,
    chain_groups,
    element_versions,
    states_a_street,
    validate_versions,
    version_block,
    version_indices,
)
from maps.versions import put_rows_in

logger = logging.getLogger(__name__)


class MapUploadView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = "maps/map_upload.html"
    form_class = MapUploadForm
    login_url = "login"

    def get_success_url(self):
        latest_map = GameMap.objects.latest("created")
        return f"/app/maps/{latest_map.pk}/"

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

            logger.info(
                f"Map upload started: name='{map_name}', "
                f"has_json={json_file is not None}, has_image={image_file is not None}"
            )

            # Parse JSON if provided
            graph_data = None
            if json_file:
                json_file.seek(0)
                raw = json_file.read().decode("utf-8")
                logger.info(f"JSON file size: {len(raw)} bytes")
                graph_data = json.loads(raw)

                node_count = len(graph_data.get("nodes", []))
                edge_count = len(graph_data.get("edges", []))
                bus_line_count = len(graph_data.get("bus_lines", []))
                train_line_count = len(graph_data.get("train_lines", []))
                logger.info(
                    f"Parsed JSON: {node_count} nodes, {edge_count} edges, "
                    f"{bus_line_count} bus lines, {train_line_count} train lines, "
                    f"scale={graph_data.get('scale')}"
                )

                # Run validation checks first (dry run)
                validation_errors = self._validate_graph_data(graph_data)
                if validation_errors:
                    error_message = "JSON validation errors found:\n" + "\n".join(
                        [f"• {error}" for error in validation_errors]
                    )
                    logger.warning(
                        f"Validation failed for map '{map_name}' "
                        f"({len(validation_errors)} errors):"
                    )
                    for i, err in enumerate(validation_errors, 1):
                        logger.warning(f"  [{i}] {err}")
                    messages.error(self.request, error_message)
                    return self.form_invalid(form)

                logger.info(f"JSON validation passed for map '{map_name}'")

            logger.info(f"Starting map creation for '{map_name}'")

            # Create map in a transaction
            with transaction.atomic():
                scale = graph_data.get("scale", 1.0) if graph_data else 1.0
                game_map = self._create_game_map(
                    name=map_name,
                    max_players=max_players,
                    author=self.request.user,
                    scale=scale,
                    map_meta=(graph_data or {}).get("map", {}),
                )
                logger.info(f"Created GameMap with pk {game_map.pk}")

                # Save background image if provided
                if image_file:
                    game_map.background_image = image_file
                    game_map.save()
                elif graph_data and graph_data.get("background_image"):
                    self._apply_background_from_json(
                        game_map, graph_data["background_image"]
                    )

                # Every version the file describes — one implicit base version
                # when it describes none, which is every file written before
                # S14 and every file in `map_examples/`.
                versions, base_idx = self._create_map_versions(
                    game_map, graph_data, map_name, description
                )
                logger.info(f"Created {len(versions)} map version(s)")

                if graph_data:
                    # Create nodes and edges from JSON
                    node_mapping = self._create_nodes(
                        game_map=game_map,
                        versions=versions,
                        base_idx=base_idx,
                        nodes_data=graph_data.get("nodes", []),
                    )
                    map_meta = (graph_data or {}).get("map", {})
                    changed = []
                    if "x_dim" in map_meta and "y_dim" in map_meta:
                        game_map.x_dim = int(map_meta["x_dim"])
                        game_map.y_dim = int(map_meta["y_dim"])
                        changed += ["x_dim", "y_dim"]
                    # What the map is played against travels with it: the
                    # export is the only way a map moves between boxes, so a
                    # key read on the way out and ignored on the way back in is
                    # a field that does not exist off this machine. Absent on
                    # every map exported before S2, which is why each is
                    # guarded rather than defaulted — the field default then
                    # stands, and that is the right answer for an old file.
                    # (`max_player` and the three speeds are still dropped on
                    # import; that half of the round trip is S5's.)
                    for key in ("district_commuters", "co2_budget_kg_per_round"):
                        if key in map_meta:
                            try:
                                value = int(map_meta[key])
                            except (TypeError, ValueError):
                                logger.warning(
                                    "Map %s: %s is not a number (%r), keeping "
                                    "the default",
                                    game_map.pk,
                                    key,
                                    map_meta[key],
                                )
                                continue
                            if value > 0:
                                setattr(game_map, key, value)
                                changed.append(key)
                    if changed:
                        game_map.save(update_fields=changed)
                    logger.info(f"Created {len(node_mapping)} nodes")

                    edge_mapping = self._create_edges(
                        game_map=game_map,
                        versions=versions,
                        base_idx=base_idx,
                        edges_data=graph_data.get("edges", []),
                        node_mapping=node_mapping,
                    )
                    logger.info(f"Created {len(edge_mapping)} edges")

                    # Create street and train edges
                    self._create_specialized_edges(
                        versions=versions,
                        base_idx=base_idx,
                        edges_data=graph_data.get("edges", []),
                        edge_mapping=edge_mapping,
                    )

                    # Create bus lines
                    self._create_bus_lines(
                        game_map=game_map,
                        versions=versions,
                        base_idx=base_idx,
                        bus_lines_data=graph_data.get("bus_lines", []),
                        edge_mapping=edge_mapping,
                    )

                    # Create train lines
                    self._create_train_lines(
                        game_map=game_map,
                        versions=versions,
                        base_idx=base_idx,
                        train_lines_data=graph_data.get("train_lines", []),
                        edge_mapping=edge_mapping,
                    )

                    logger.info(
                        f"User {self.request.user.username} created map '{map_name}' "
                        f"with {len(node_mapping)} nodes"
                    )
                else:
                    logger.info(
                        f"User {self.request.user.username} created blank map '{map_name}'"
                    )

        except Exception as e:
            logger.error(
                f"Error processing map upload for '{map_name}': {e!s}", exc_info=True
            )
            messages.error(self.request, f"Error creating map: {e!s}")
            return self.form_invalid(form)

        logger.info(f"Map upload complete for '{map_name}', redirecting to success_url")
        return super().form_valid(form)

    def _apply_background_from_json(self, game_map, block):
        """Take image and placement from the JSON.

        The placement is set even when no image data comes with it — the image can
        then be added by hand and still sits in the right place.
        """
        game_map.image_scale = block.get("scale", 1.0)
        game_map.image_offset_x = block.get("offset_x", 0.0)
        game_map.image_offset_y = block.get("offset_y", 0.0)
        game_map.image_crop_top = block.get("crop_top", 0.0)
        game_map.image_crop_right = block.get("crop_right", 0.0)
        game_map.image_crop_bottom = block.get("crop_bottom", 0.0)
        game_map.image_crop_left = block.get("crop_left", 0.0)

        data = block.get("data")
        if data:
            try:
                raw = base64.b64decode(data)
            except (binascii.Error, ValueError) as exc:
                # A broken image file must not kill the map import — the graph is
                # the valuable part, the image can be added afterwards.
                logger.warning(
                    "Map %s: background image not decodable (%s)", game_map.pk, exc
                )
            else:
                filename = block.get("filename") or "background.png"
                game_map.background_image.save(filename, ContentFile(raw), save=False)

        game_map.save()

    def _validate_graph_data(self, graph_data):
        errors = []

        # Check basic structure
        if not isinstance(graph_data, dict):
            errors.append("JSON root must be an object/dictionary")
            return errors

        # Everything about versioning the file can get wrong, including every
        # index that points into the `versions` block. A hand-edited file is
        # how S16 repairs the map the group plays, so a wrong index has to come
        # back as a sentence on the upload page rather than as a map with a
        # hole in it. `maps/portability.py` owns those rules.
        errors += validate_versions(graph_data)

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
                if edge_type not in ("street", "train", "both", "path"):
                    errors.append(
                        f"Edge {idx}: invalid type '{edge_type}'. "
                        f"Must be 'street', 'train', 'both', or 'path'"
                    )
                # A bike lane implies bike access. Read against the same
                # default _create_edges uses, so a train edge that asks for a
                # bike lane has to say `biking` too rather than inherit a
                # False it did not mean.
                default_biking = edge_type != "train"
                if edge.get("bike_lane", False) and not edge.get(
                    "biking", default_biking
                ):
                    errors.append(
                        f"Edge {idx}: bike_lane is set but biking is not — "
                        f"a bike lane has to be open to bikes"
                    )

        # Validate bus lines
        for bus_line_idx, bus_line in enumerate(bus_lines_data):
            bus_name = bus_line.get("name", f"BusLine {bus_line_idx}")
            errors += self._line_edge_errors(
                f"Bus line '{bus_name}'", bus_line, edges_data
            )

        # Validate train lines
        for train_line_idx, train_line in enumerate(train_lines_data):
            train_name = train_line.get("name", f"TrainLine {train_line_idx}")
            errors += self._line_edge_errors(
                f"Train line '{train_name}'", train_line, edges_data
            )

        return errors

    def _line_edge_errors(self, label, line_data, edges_data):
        """The links a line claims, whether it writes one route or several.

        `edges` is the flat route every file used to carry; `chains` is the
        per-version form, and the bounds are the same either way. The indices
        *inside* `chains` are checked here too rather than only in
        `validate_versions`, so a flat-looking file with one bad index is
        refused with the line's name on it.
        """
        errors = []
        routes = [line_data.get("edges", []) or []]
        for chain in line_data.get("chains", []) or []:
            if isinstance(chain, dict):
                routes.append(chain.get("edges", []) or [])
        for route in routes:
            for edge_idx in route:
                if not isinstance(edge_idx, int) or edge_idx < 0:
                    errors.append(f"{label}: invalid edge index {edge_idx}")
                elif edge_idx >= len(edges_data):
                    errors.append(
                        f"{label}: edge index {edge_idx} not found "
                        f"(only {len(edges_data)} edges available)"
                    )
        return errors

    def _create_game_map(self, name, max_players, author, scale=1.0, map_meta=None):
        """The map row itself, from the file's `map` block where it has one.

        `map_meta` was accepted here and passed by nobody, so every key in the
        block except the dimensions and (since S2) the calibration pair was
        written into the export and dropped on the way back in: the copy arrived
        with the form's Platzzahl and the three speed defaults, whatever the
        file said. A map whose walking speed is 4 km/h is a different map on the
        next box, which is the whole thing the round trip exists to prevent.

        Every value is guarded rather than defaulted, so a file that does not
        mention a key — every export older than the field — keeps the field
        default instead of a None. `max_player` takes the form's number as its
        fallback, because that field is required and the host always types
        something; when the file states one, the file wins. What the map was
        drawn for is a property of the map, not of the upload.
        """
        meta = map_meta or {}

        def from_meta(key, fallback):
            if key not in meta:
                return fallback
            try:
                value = int(meta[key])
            except (TypeError, ValueError):
                value = 0
            if value <= 0:
                logger.warning(
                    "Map %r: %s is not a usable number (%r), keeping %s",
                    name,
                    key,
                    meta[key],
                    fallback,
                )
                return fallback
            return value

        game_map = GameMap.objects.create(
            name=name,
            max_player=from_meta("max_player", max_players),
            author=author,
            updated_by=author,
            x_dim=100,
            y_dim=100,
            scale=scale,
            walk_speed_kmh=from_meta("walk_speed_kmh", 5),
            bike_speed_kmh=from_meta("bike_speed_kmh", 20),
            default_car_speed_kmh=from_meta("default_car_speed_kmh", 50),
        )
        return game_map

    def _create_map_versions(self, game_map, graph_data, map_name, description):
        """Every `MapVersion` the file describes, in the file's own order.

        A file without a `versions` block gets the single base version this
        importer has always made, and everything downstream keeps one code
        path: an element that names no versions means the base one either way.

        The version's own name wins over the form's. A copy uploaded under a
        new map name therefore keeps its base version called after the map it
        was drawn on, which is what makes the round trip a fixed point — export,
        import, export again, and the second file says the same as the first.
        """
        block = version_block(graph_data)
        if block is None:
            base = MapVersion.objects.create(
                game_map=game_map,
                name=f"{map_name} - Base",
                description=description,
                base_version=True,
            )
            return [base], 0

        base_idx = base_index(block)
        created = []
        for idx, entry in enumerate(block):
            version = MapVersion.objects.create(
                game_map=game_map,
                name=entry.get("name") or f"{map_name} - Version {idx + 1}",
                description=entry.get("description")
                or (description if idx == base_idx else ""),
                base_version=idx == base_idx,
                poll_text=entry.get("poll_text") or DEFAULT_POLL_TEXT,
                revert_poll_text=entry.get("revert_poll_text") or DEFAULT_POLL_TEXT,
            )
            self._apply_change_image(version, entry.get("change_img"))
            created.append(version)

        # Second pass: both links point at other versions, so they need all of
        # them to exist first. `compatible_versions` is symmetric, so writing
        # each side is idempotent rather than double.
        for idx, entry in enumerate(block):
            source = entry.get("source_version")
            if isinstance(source, int) and 0 <= source < len(created):
                created[idx].source_version = created[source]
                created[idx].save(update_fields=["source_version"])
            compatible = [
                created[other]
                for other in entry.get("compatible_versions", []) or []
                if isinstance(other, int) and 0 <= other < len(created)
            ]
            if compatible:
                created[idx].compatible_versions.add(*compatible)
        return created, base_idx

    def _apply_change_image(self, version, block):
        """The picture the ballot shows for this change.

        Base64 in the file like the background image, and a broken one must not
        cost the map: the graph is the valuable part and the picture can be
        added afterwards.
        """
        if not isinstance(block, dict):
            return
        data = block.get("data")
        if not data:
            return
        try:
            raw = base64.b64decode(data)
        except (binascii.Error, ValueError) as exc:
            logger.warning(
                "Version %s: change image not decodable (%s)", version.pk, exc
            )
            return
        version.change_img.save(
            block.get("filename") or "change.png", ContentFile(raw), save=True
        )

    def _versions_for(self, entry, versions, base_idx):
        """The `MapVersion` rows an entry in the file names.

        Absent means the base version, `[]` means nowhere — see
        `maps/portability.py`, which owns the rule and states why the two are
        different.
        """
        return [
            versions[idx]
            for idx in version_indices(entry, len(versions), base_idx)
        ]

    def _create_nodes(self, game_map, versions, base_idx, nodes_data):
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

            node.map_versions.add(
                *self._versions_for(node_data, versions, base_idx)
            )

            # Add node types
            for type_name in node_data.get("types", []):
                node.node_type.add(node_types_cache[type_name])

            node_mapping[node_id] = node

        # Update map dimensions
        game_map.x_dim = int(max_x) + 1
        game_map.y_dim = int(max_y) + 1
        game_map.save()

        return node_mapping

    def _create_edges(
        self, game_map, versions, base_idx, edges_data, node_mapping
    ):
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
            default_biking = edge_type != "train"
            default_walking = edge_type != "train"

            edge = Edge.objects.create(
                bike_lane=edge_data.get("bike_lane", False),
                game_map=game_map,
                name=edge_data.get("name", f"{start_node_id}-{end_node_id}"),
                start_node=start_node,
                end_node=end_node,
                biking=edge_data.get("biking", default_biking),
                walking=edge_data.get("walking", default_walking),
                max_lanes=edge_data.get("max_lanes", 2),
            )

            edge.map_versions.add(
                *self._versions_for(edge_data, versions, base_idx)
            )

            # Store mapping by index
            edge_mapping[edge_idx] = edge

        return edge_mapping

    def _create_specialized_edges(self, versions, base_idx, edges_data, edge_mapping):
        """The street and the railway under an edge, each with its own membership.

        Both ride on the edge's `versions` unless the file overrides them with
        `street_versions` / `train_versions` — a version that keeps an edge but
        drops the street over it is a real state (`_drop_edge_from_version`
        makes one), and a file that cannot say it would repair the map by
        accident on the way back in.
        """
        for edge_idx, edge_data in enumerate(edges_data):
            edge = edge_mapping[edge_idx]
            edge_type = edge_data.get("type", "both")
            own = element_versions(edge_data, "versions", [base_idx], len(versions))

            # Create StreetEdge if type is 'street' or 'both' — but only when
            # the file actually states a street. `"type": "path"` says there is
            # none, and a legacy file saying `"street"` without a single street
            # field means the same: that is how the four bike-and-foot links on
            # the shipped map were written before the type existed. Creating one
            # anyway handed each of them 50 km/h and a lane, which is a car
            # shortcut past three front doors that nobody drew.
            if edge_type in ("street", "both") and states_a_street(edge_data):
                street_edge = StreetEdge.objects.create(
                    edge=edge,
                    speed_limit=edge_data.get("speed_limit", 50),
                    lanes=edge_data.get("lanes", 1),
                    dedicated_bus_lane=edge_data.get("dedicated_bus_lane", False),
                )
                street_edge.map_versions.add(
                    *self._sub_versions(edge_data, "street_versions", own, versions)
                )

            # Create TrainEdge if type is 'train' or 'both'
            if edge_type in ("train", "both"):
                train_edge = TrainEdge.objects.create(edge=edge)
                train_edge.map_versions.add(
                    *self._sub_versions(edge_data, "train_versions", own, versions)
                )

    def _sub_versions(self, edge_data, key, own, versions):
        """A street's or a railway's own membership, defaulting to its edge's.

        Absent means "wherever the edge is", and an explicit `[]` means nowhere
        — the same two-way distinction the top-level `versions` key has, and the
        reason this is not written as `... or own`.
        """
        return [
            versions[idx]
            for idx in element_versions(edge_data, key, own, len(versions))
        ]

    def _create_bus_lines(
        self, game_map, versions, base_idx, bus_lines_data, edge_mapping
    ):
        for bus_line_data in bus_lines_data:
            # Every default here is the model's own (`maps/models.py`), so a
            # handwritten file that mentions none of them gets the same line the
            # editor's "new line" button makes. `speed_kmh` used to be exported
            # and then dropped, which is why every line on every imported map has
            # run at 30 whatever its file said — the simulator takes a line
            # vehicle's speed from it (`bus_line_speeds`) and so does the
            # client's route preview (`ptRouting.ts`).
            bus_line = BusLine.objects.create(
                game_map=game_map,
                name=bus_line_data["name"],
                intervall=bus_line_data.get("interval", 5),
                bus_capacity=bus_line_data.get("capacity", 85),
                bus_speed_kmh=bus_line_data.get("speed_kmh", 30),
            )
            line_indices = version_indices(bus_line_data, len(versions), base_idx)
            bus_line.map_versions.add(*[versions[i] for i in line_indices])
            self._create_chain(
                bus_line, bus_line_data, line_indices, versions, edge_mapping, "bus"
            )

    def _create_train_lines(
        self, game_map, versions, base_idx, train_lines_data, edge_mapping
    ):
        for train_line_data in train_lines_data:
            # `intervall` defaulted to 10 here while the model, the editor and
            # the bus above all say 5: three places, two answers, the same shape
            # as the 60-seat U-Bahn. A file without an interval asked for a
            # timetable and got half of one.
            train_line = TrainLine.objects.create(
                game_map=game_map,
                name=train_line_data["name"],
                intervall=train_line_data.get("interval", 5),
                train_capacity=train_line_data.get("capacity", 1000),
                train_speed_kmh=train_line_data.get("speed_kmh", 40),
            )
            line_indices = version_indices(train_line_data, len(versions), base_idx)
            train_line.map_versions.add(*[versions[i] for i in line_indices])
            self._create_chain(
                train_line,
                train_line_data,
                line_indices,
                versions,
                edge_mapping,
                "train",
            )

    def _create_chain(
        self, line, line_data, line_indices, versions, edge_mapping, kind
    ):
        """A line's links, one set of rows per route rather than per version.

        Since S15 the chain is version-scoped: a version that clones a street
        runs the line over the clone while the others keep the original, so one
        line legitimately has two rows of the same `order`. The file writes that
        as one `chains` entry per distinct route, and each entry becomes its own
        rows named into the versions that share it. A file that says only
        `edges` means one route in every version the line runs — which is what a
        flat file has always meant.
        """
        for chain_indices, edge_indices in chain_groups(line_data, line_indices):
            group = [
                versions[i]
                for i in chain_indices
                if isinstance(i, int) and 0 <= i < len(versions)
            ]
            rows = []
            for order, edge_idx in enumerate(edge_indices):
                if edge_idx not in edge_mapping:
                    raise ValueError(
                        f"{kind} line '{line.name}': edge index {edge_idx} not found"
                    )
                edge = edge_mapping[edge_idx]
                if kind == "bus":
                    element = StreetEdge.objects.filter(edge=edge).first()
                    if not element:
                        element = StreetEdge.objects.create(edge=edge)
                        element.map_versions.add(*group)
                    rows.append(
                        BusLineEdge.objects.create(
                            bus_line=line, street_edge=element, order=order
                        )
                    )
                else:
                    element = TrainEdge.objects.filter(edge=edge).first()
                    if not element:
                        element = TrainEdge.objects.create(edge=edge)
                        element.map_versions.add(*group)
                    rows.append(
                        TrainLineEdge.objects.create(
                            train_line=line, train_edge=element, order=order
                        )
                    )
            # A row that names no version is a link no reader ever finds, so
            # the writer is the named one (`maps/versions.py`) here too.
            put_rows_in(rows, group)


class MapListView(LoginRequiredMixin, RedirectView):
    """`/map/list/` — the staff map list, which `/app/maps` is now. S18.

    The template was English and printed a `description` `GameMap` has no
    column for. The URL stays because both menus in `base.html` name
    `map-list`. Staff gating is the SPA's, as it is for the detail page.
    """

    pattern_name = None
    url = "/app/maps/"
    permanent = False


class MapDetailView(LoginRequiredMixin, RedirectView):
    """`/map/<pk>/` — a map's page, which `/app/maps/<pk>/` is now. S18.

    Nothing linked here any more: the old list already pointed at the SPA. Its
    version browser is the editor's version panel. Nothing is looked up, so an
    unknown pk is the SPA's to refuse.
    """

    pattern_name = None
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return f"/app/maps/{kwargs['pk']}/"
