from rest_framework import serializers
import maps.models as mm


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


class MapGenerationRequestSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    radius_m = serializers.IntegerField(min_value=50, max_value=10000)
    complexity = serializers.IntegerField(min_value=1, max_value=10)
    name = serializers.CharField(required=False, allow_blank=True, max_length=100)


class NodeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.NodeType
        fields = ("id", "name", "short")
        read_only_fields = ("id",)


class NodeSerializer(serializers.ModelSerializer):
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
        ]
        read_only_fields = ("id",)
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):  # pragma: no cover - exercised via integration tests
        game_map = attrs.get("game_map") or getattr(self.instance, "game_map", None)
        if game_map is None:
            raise serializers.ValidationError("game_map is required")

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
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["node_type"] = NodeTypeSerializer(
            instance.node_type.all(),
            many=True,
        ).data
        return data


class EdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.Edge
        fields = [
            "id",
            "game_map",
            "name",
            "start_node",
            "end_node",
            "bike_speed",
            "walk_speed",
            "max_lanes",
        ]
        read_only_fields = ("id",)
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        game_map = attrs.get("game_map") or getattr(self.instance, "game_map", None)
        start_node = attrs.get("start_node") or getattr(
            self.instance, "start_node", None
        )
        end_node = attrs.get("end_node") or getattr(self.instance, "end_node", None)

        errors = {}

        if start_node and end_node and start_node == end_node:
            errors["end_node"] = "start_node and end_node must be different."

        if start_node and end_node and start_node.game_map_id != end_node.game_map_id:
            errors["end_node"] = "start_node and end_node must belong to the same map."

        if game_map and start_node and start_node.game_map_id != game_map.id:
            errors["start_node"] = "start_node must belong to game_map."

        if game_map and end_node and end_node.game_map_id != game_map.id:
            errors["end_node"] = "end_node must belong to game_map."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class StreetEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.StreetEdge
        fields = ("id", "edge", "speed_limit", "lanes", "dedicated_bus_lane")
        read_only_fields = ("id",)


class BusLineSerializer(serializers.ModelSerializer):
    edges = serializers.PrimaryKeyRelatedField(
        queryset=mm.StreetEdge.objects.all(),
        many=True,
    )

    class Meta:
        model = mm.BusLine
        fields = ("id", "game_map", "name", "frequency", "bus_capacity", "edges")
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

        return attrs

    def validate_frequency(self, value):
        if value <= 0:
            raise serializers.ValidationError("frequency must be greater than 0.")
        return value

class TrainEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.TrainEdge
        fields = ("id", "edge")
        read_only_fields = ("id",)


class TrainLineSerializer(serializers.ModelSerializer):
    edges = serializers.PrimaryKeyRelatedField(
        queryset=mm.TrainEdge.objects.all(),
        many=True,
    )

    class Meta:
        model = mm.TrainLine
        fields = ("id", "game_map", "name", "frequency", "train_capacity", "edges")
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

        return attrs

    def validate_frequency(self, value):
        if value <= 0:
            raise serializers.ValidationError("frequency must be greater than 0.")
        return value
