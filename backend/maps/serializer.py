from rest_framework import serializers
import maps.models as mm


class MapVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.MapVersion
        fields = ("id", "game_map", "name", "description")
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
        )
        read_only_fields = ("id", "created", "updated")

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
        ]
        read_only_fields = ("id", "street_edge", "train_edge")
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
