from rest_framework import serializers
import maps.models as mm


class GameMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.GameMap
        fields = ["id", "name", "x_dim", "y_dim", "scale"]

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    x_dim = serializers.IntegerField(min_value=0, max_value=32767)
    y_dim = serializers.IntegerField(min_value=0, max_value=32767)
    scale = serializers.FloatField()

    def validate_scale(self, value):
        if value <= 0:
            raise serializers.ValidationError("Scale must be greater than 0")
        return value


class NodeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.NodeType
        fields = ["id", "name", "short"]

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    short = serializers.CharField(max_length=2)


class NodeSerializer(serializers.ModelSerializer):
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

    id = serializers.IntegerField(read_only=True)
    game_map = serializers.PrimaryKeyRelatedField(
        queryset=mm.GameMap.objects.all()
    )
    name = serializers.CharField(required=False, allow_blank=True)
    x_position = serializers.FloatField()
    y_position = serializers.FloatField()
    node_type = serializers.PrimaryKeyRelatedField(
        queryset=mm.NodeType.objects.all(),
        many=True,
        required=False,
    )

    def validate(self, attrs):
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

    id = serializers.IntegerField(read_only=True)
    game_map = serializers.PrimaryKeyRelatedField(
        queryset=mm.GameMap.objects.all()
    )
    name = serializers.CharField(required=False, allow_blank=True)
    start_node = serializers.PrimaryKeyRelatedField(
        queryset=mm.Node.objects.all()
    )
    end_node = serializers.PrimaryKeyRelatedField(
        queryset=mm.Node.objects.all()
    )
    bike_speed = serializers.IntegerField(min_value=0)
    walk_speed = serializers.IntegerField(min_value=0)
    max_lanes = serializers.IntegerField(min_value=0)

    def validate(self, attrs):
        game_map = attrs.get("game_map") or getattr(self.instance, "game_map", None)
        start_node = attrs.get("start_node") or getattr(self.instance, "start_node", None)
        end_node = attrs.get("end_node") or getattr(self.instance, "end_node", None)

        if game_map and start_node and start_node.game_map_id != game_map.id:
            raise serializers.ValidationError("start_node must belong to game_map")

        if game_map and end_node and end_node.game_map_id != game_map.id:
            raise serializers.ValidationError("end_node must belong to game_map")

        return attrs


class StreetEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.StreetEdge
        fields = ["id", "edge", "speed_limit", "lanes", "dedicated_bus_lane"]

    id = serializers.IntegerField(read_only=True)
    edge = serializers.PrimaryKeyRelatedField(
        queryset=mm.Edge.objects.all()
    )
    speed_limit = serializers.IntegerField(min_value=0)
    lanes = serializers.IntegerField(min_value=0)
    dedicated_bus_lane = serializers.BooleanField()


class BusLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.BusLine
        fields = ["id", "game_map", "name", "frequency", "bus_capacity", "edges"]

    id = serializers.IntegerField(read_only=True)
    game_map = serializers.PrimaryKeyRelatedField(
        queryset=mm.GameMap.objects.all()
    )
    name = serializers.CharField()
    frequency = serializers.FloatField()
    bus_capacity = serializers.IntegerField(min_value=0)
    edges = serializers.PrimaryKeyRelatedField(
        queryset=mm.StreetEdge.objects.all(),
        many=True,
    )


class TrainEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.TrainEdge
        fields = ["id", "edge"]

    id = serializers.IntegerField(read_only=True)
    edge = serializers.PrimaryKeyRelatedField(
        queryset=mm.Edge.objects.all()
    )


class TrainLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = mm.TrainLine
        fields = ["id", "game_map", "name", "frequency", "train_capacity", "edges"]

    id = serializers.IntegerField(read_only=True)
    game_map = serializers.PrimaryKeyRelatedField(
        queryset=mm.GameMap.objects.all()
    )
    name = serializers.CharField()
    frequency = serializers.FloatField()
    train_capacity = serializers.IntegerField(min_value=0)
    edges = serializers.PrimaryKeyRelatedField(
        queryset=mm.TrainEdge.objects.all(),
        many=True,
    )
