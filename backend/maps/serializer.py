from rest_framework import serializers
import maps.models as mm


class MapVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.MapVersion
        fields = (
            "id",
            "game_map",
            "name",
            "description",
            "base_version",
            "poll_text",
            "revert_poll_text",
            "source_version",
        )
        read_only_fields = ("id",)


class MapVersionsMixin:
    map_versions = serializers.PrimaryKeyRelatedField(
        queryset=mm.MapVersion.objects.all(),
        many=True,
        required=False,
    )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["map_versions"] = MapVersionSerializer(
            instance.map_versions.all(),
            many=True,
        ).data
        return data


class GameMapSerializer(serializers.ModelSerializer):
    background_image_url = serializers.SerializerMethodField()

    class Meta:
        model = mm.GameMap
        fields = (
            "id",
            "name",
            "x_dim",
            "y_dim",
            "scale",
            "created",
            "author",
            "updated",
            "updated_by",
            "background_image_url",
            "image_offset_x",
            "image_offset_y",
            "image_scale",
            "image_crop_top",
            "image_crop_right",
            "image_crop_bottom",
            "image_crop_left",
        )
        read_only_fields = ("id", "created", "updated", "background_image_url")

    def get_background_image_url(self, obj):
        if obj.background_image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.background_image.url)
            return obj.background_image.url
        return None

    def validate_scale(self, value):
        if value <= 0:
            raise serializers.ValidationError("Scale must be greater than 0")
        return value


class NodeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.NodeType
        fields = ("id", "name", "short")
        read_only_fields = ("id",)


class NodeSerializer(MapVersionsMixin, serializers.ModelSerializer):
    node_type = serializers.PrimaryKeyRelatedField(
        queryset=mm.NodeType.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = mm.Node
        fields = [
            "id",
            "game_map",
            "name",
            "x_position",
            "y_position",
            "node_type",
            "map_versions",
        ]
        read_only_fields = ("id",)
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):  # pragma: no cover - exercised via integration tests
        game_map = attrs.get("game_map") or getattr(self.instance, "game_map", None)
        if game_map is None:
            raise serializers.ValidationError({"game_map": "game_map is required"})

        x_position = attrs.get(
            "x_position",
            getattr(self.instance, "x_position", None),
        )
        y_position = attrs.get(
            "y_position",
            getattr(self.instance, "y_position", None),
        )

        if x_position is not None and not 0 <= x_position <= game_map.x_dim:
            raise serializers.ValidationError("x_position out of bounds")
        if y_position is not None and not 0 <= y_position <= game_map.y_dim:
            raise serializers.ValidationError("y_position out of bounds")

        map_versions = attrs.get("map_versions")
        if map_versions is not None:
            invalid_map_versions = [
                mv.pk for mv in map_versions if mv.game_map_id != game_map.id
            ]
            if invalid_map_versions:
                raise serializers.ValidationError(
                    {
                        "map_versions": (
                            "All map versions must belong to the same game_map as "
                            "the node. "
                            f"Invalid map version IDs: {invalid_map_versions}"
                        )
                    }
                )
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["node_type"] = NodeTypeSerializer(
            instance.node_type.all(),
            many=True,
        ).data
        return data


class EdgeSerializer(MapVersionsMixin, serializers.ModelSerializer):
    street_edge = serializers.SerializerMethodField()
    train_edge = serializers.SerializerMethodField()
    distance_m = serializers.SerializerMethodField()

    class Meta:
        model = mm.Edge
        fields = [
            "id",
            "game_map",
            "name",
            "start_node",
            "end_node",
            "biking",
            "walking",
            "max_lanes",
            "map_versions",
            "street_edge",
            "train_edge",
            "distance_m",
        ]
        read_only_fields = ("id", "street_edge", "train_edge", "distance_m")
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
        }

    def get_street_edge(self, obj):
        """Get street edge data if it exists for this edge."""
        try:
            # StreetEdge has ForeignKey to Edge, access via reverse relation
            street_edge = obj.streetedge_set.first()
            if street_edge:
                return {
                    "id": street_edge.id,
                    "speed_limit": street_edge.speed_limit,
                    "lanes": street_edge.lanes,
                    "dedicated_bus_lane": street_edge.dedicated_bus_lane,
                }
            return None
        except Exception:
            return None

    def get_train_edge(self, obj):
        """Get train edge data if it exists for this edge."""
        try:
            # TrainEdge has ForeignKey to Edge, access via reverse relation
            train_edge = obj.trainedge_set.first()
            if train_edge:
                return {
                    "id": train_edge.id,
                }
            return None
        except Exception:
            return None

    def get_distance_m(self, obj):
        """Calculate distance in meters using euclidean_2d_distance * scale."""
        return obj.euclidean_2d_distance() * obj.game_map.scale

    def validate(self, attrs):
        game_map = attrs.get("game_map") or getattr(self.instance, "game_map", None)
        start_node = attrs.get("start_node") or getattr(
            self.instance, "start_node", None
        )
        end_node = attrs.get("end_node") or getattr(self.instance, "end_node", None)

        errors = {}

        if game_map is None:
            errors["game_map"] = "game_map is required."

        if start_node and end_node and start_node == end_node:
            errors["end_node"] = "start_node and end_node must be different."

        if start_node and end_node and start_node.game_map_id != end_node.game_map_id:
            errors["end_node"] = "start_node and end_node must belong to the same map."

        if game_map and start_node and start_node.game_map_id != game_map.id:
            errors["start_node"] = "start_node must belong to game_map."

        if game_map and end_node and end_node.game_map_id != game_map.id:
            errors["end_node"] = "end_node must belong to game_map."

        map_versions = attrs.get("map_versions")
        if map_versions is not None and game_map:
            mismatched_version_ids = [
                mv.pk for mv in map_versions if mv.game_map_id != game_map.id
            ]
            if mismatched_version_ids:
                errors["map_versions"] = (
                    "All map versions must belong to the same game_map as the edge. "
                    f"Invalid map version IDs: {mismatched_version_ids}"
                )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class StreetEdgeSerializer(MapVersionsMixin, serializers.ModelSerializer):
    class Meta:
        model = mm.StreetEdge
        fields = (
            "id",
            "edge",
            "speed_limit",
            "lanes",
            "dedicated_bus_lane",
            "map_versions",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        edge = attrs.get("edge") or getattr(self.instance, "edge", None)
        if edge is None:
            raise serializers.ValidationError({"edge": "edge is required."})

        map_versions = attrs.get("map_versions")
        if map_versions is not None:
            invalid_map_versions = [
                mv.pk for mv in map_versions if mv.game_map_id != edge.game_map_id
            ]
            if invalid_map_versions:
                raise serializers.ValidationError(
                    {
                        "map_versions": (
                            "All map versions must belong to the same game_map as "
                            "the edge. "
                            f"Invalid map version IDs: {invalid_map_versions}"
                        )
                    }
                )

        return attrs


class BusLineSerializer(MapVersionsMixin, serializers.ModelSerializer):
    edges = serializers.PrimaryKeyRelatedField(
        queryset=mm.StreetEdge.objects.all(),
        many=True,
    )

    class Meta:
        model = mm.BusLine
        fields = (
            "id",
            "game_map",
            "name",
            "intervall",
            "bus_capacity",
            "edges",
            "map_versions",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        game_map = attrs.get("game_map") or getattr(self.instance, "game_map", None)
        edges = attrs.get("edges", None)
        if edges is None and self.instance is not None:
            edges = list(self.instance.edges.all())

        if game_map is None:
            raise serializers.ValidationError({"game_map": "game_map is required."})

        mismatched_edges = [
            edge.pk for edge in edges or [] if edge.edge.game_map_id != game_map.id
        ]

        if mismatched_edges:
            raise serializers.ValidationError(
                {
                    "edges": (
                        "All edges must belong to the same game_map as the bus line. "
                        f"Invalid edge IDs: {mismatched_edges}"
                    )
                }
            )

        map_versions = attrs.get("map_versions")
        if map_versions is not None:
            invalid_map_versions = [
                mv.pk for mv in map_versions if mv.game_map_id != game_map.id
            ]
            if invalid_map_versions:
                raise serializers.ValidationError(
                    {
                        "map_versions": (
                            "All map versions must belong to the same game_map as "
                            "the bus line. "
                            f"Invalid map version IDs: {invalid_map_versions}"
                        )
                    }
                )

        return attrs

    def validate_intervall(self, value):
        if value <= 0:
            raise serializers.ValidationError("intervall must be greater than 0.")
        return value


class TrainEdgeSerializer(MapVersionsMixin, serializers.ModelSerializer):
    class Meta:
        model = mm.TrainEdge
        fields = ("id", "edge", "map_versions")
        read_only_fields = ("id",)

    def validate(self, attrs):
        edge = attrs.get("edge") or getattr(self.instance, "edge", None)
        if edge is None:
            raise serializers.ValidationError({"edge": "edge is required."})

        map_versions = attrs.get("map_versions")
        if map_versions is not None:
            invalid_map_versions = [
                mv.pk for mv in map_versions if mv.game_map_id != edge.game_map_id
            ]
            if invalid_map_versions:
                raise serializers.ValidationError(
                    {
                        "map_versions": (
                            "All map versions must belong to the same game_map as "
                            "the edge. "
                            f"Invalid map version IDs: {invalid_map_versions}"
                        )
                    }
                )

        return attrs


class TrainLineSerializer(MapVersionsMixin, serializers.ModelSerializer):
    edges = serializers.PrimaryKeyRelatedField(
        queryset=mm.TrainEdge.objects.all(),
        many=True,
    )

    class Meta:
        model = mm.TrainLine
        fields = (
            "id",
            "game_map",
            "name",
            "intervall",
            "train_capacity",
            "edges",
            "map_versions",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        game_map = attrs.get("game_map") or getattr(self.instance, "game_map", None)
        edges = attrs.get("edges", None)
        if edges is None and self.instance is not None:
            edges = list(self.instance.edges.all())

        if game_map is None:
            raise serializers.ValidationError({"game_map": "game_map is required."})

        mismatched_edges = [
            edge.pk for edge in edges or [] if edge.edge.game_map_id != game_map.id
        ]

        if mismatched_edges:
            raise serializers.ValidationError(
                {
                    "edges": (
                        "All edges must belong to the same game_map as the train line. "
                        f"Invalid edge IDs: {mismatched_edges}"
                    )
                }
            )

        map_versions = attrs.get("map_versions")
        if map_versions is not None:
            invalid_map_versions = [
                mv.pk for mv in map_versions if mv.game_map_id != game_map.id
            ]
            if invalid_map_versions:
                raise serializers.ValidationError(
                    {
                        "map_versions": (
                            "All map versions must belong to the same game_map as "
                            "the train line. "
                            f"Invalid map version IDs: {invalid_map_versions}"
                        )
                    }
                )

        return attrs

    def validate_intervall(self, value):
        if value <= 0:
            raise serializers.ValidationError("intervall must be greater than 0.")
        return value


# Graph-specific serializers for pathfinding/routing
class PTLineGraphSerializer(serializers.Serializer):
    """Serializer for PT lines in graph context (for frontend routing)."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField()  # "bus" or "train"
    interval = serializers.IntegerField()
    capacity = serializers.IntegerField()
    edges = serializers.ListField(child=serializers.IntegerField())
    stops = serializers.ListField(child=serializers.IntegerField())


def serialize_bus_line_for_graph(bus_line, version):
    """Serialize a bus line for graph/routing purposes."""
    # Get edges in order and extract underlying edge IDs
    street_edges = bus_line.edges.filter(map_versions=version).select_related("edge")
    edge_ids = [se.edge_id for se in street_edges]

    # Extract stops (unique nodes from edges in order)
    stops = []
    for se in street_edges:
        edge = se.edge
        if edge.start_node_id not in stops:
            stops.append(edge.start_node_id)
        if edge.end_node_id not in stops:
            stops.append(edge.end_node_id)

    return {
        "id": bus_line.id,
        "name": bus_line.name,
        "type": "bus",
        "interval": bus_line.intervall,
        "capacity": bus_line.bus_capacity,
        "edges": edge_ids,
        "stops": stops,
    }


def serialize_train_line_for_graph(train_line, version):
    """Serialize a train line for graph/routing purposes."""
    # Get edges in order and extract underlying edge IDs
    train_edges = train_line.edges.filter(map_versions=version).select_related("edge")
    edge_ids = [te.edge_id for te in train_edges]

    # Extract stops (unique nodes from edges in order)
    stops = []
    for te in train_edges:
        edge = te.edge
        if edge.start_node_id not in stops:
            stops.append(edge.start_node_id)
        if edge.end_node_id not in stops:
            stops.append(edge.end_node_id)

    return {
        "id": train_line.id,
        "name": train_line.name,
        "type": "train",
        "interval": train_line.intervall,
        "capacity": train_line.train_capacity,
        "edges": edge_ids,
        "stops": stops,
    }


# --- Version Diff serializers ---


class EdgeChangeSerializer(serializers.Serializer):
    """A single edge modification in a version diff changeset."""

    edge_id = serializers.IntegerField()
    biking = serializers.BooleanField(required=False)
    walking = serializers.BooleanField(required=False)
    max_lanes = serializers.IntegerField(required=False)
    speed_limit = serializers.IntegerField(required=False)
    lanes = serializers.IntegerField(required=False)
    dedicated_bus_lane = serializers.BooleanField(required=False)


class PTLineChangeSerializer(serializers.Serializer):
    """A PT line addition, modification, or removal in a version diff."""

    id = serializers.IntegerField(required=False)
    action = serializers.ChoiceField(choices=["add", "modify", "remove"])
    line_type = serializers.ChoiceField(choices=["bus", "train"])
    name = serializers.CharField(required=False)
    interval = serializers.IntegerField(required=False)
    capacity = serializers.IntegerField(required=False)
    speed_kmh = serializers.IntegerField(required=False)
    edge_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=[]
    )


class VersionDiffInputSerializer(serializers.Serializer):
    """Input for creating a new map version from a source version + changeset."""

    source_version_id = serializers.IntegerField()
    version_name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    poll_text = serializers.CharField(
        required=False, allow_blank=True, default="Die Karte soll ... "
    )
    revert_poll_text = serializers.CharField(
        required=False, allow_blank=True, default="Die Karte soll ... "
    )
    is_base_version = serializers.BooleanField(required=False, default=False)
    edge_changes = EdgeChangeSerializer(many=True, required=False, default=[])
    pt_line_changes = PTLineChangeSerializer(many=True, required=False, default=[])