from rest_framework import serializers
import maps.models as models


class GameMapSerialzer(serializers.ModelSerializer):
    class Meta:
        model = models.GameMap
        fields = ["name", "x_dim", "y_dim", "scale"]
