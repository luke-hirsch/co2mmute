from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializer import (
    EdgeSerializer,
    GameMapSerializer,
    MapGenerationRequestSerializer,
    NodeSerializer,
)
from .services import MapGenerationError, MapGenerationService


class MapGenerationView(APIView):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = MapGenerationRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = MapGenerationService()
        try:
            result = service.generate_map(
                author=request.user,
                updated_by=request.user,
                **serializer.validated_data,
            )
        except MapGenerationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_data = {
            "map": GameMapSerializer(result.game_map).data,
            "nodes": NodeSerializer(result.nodes, many=True).data,
            "edges": EdgeSerializer(result.edges, many=True).data,
            "summary": result.summary,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
