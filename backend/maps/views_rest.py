import logging

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from maps.forms import MapUploadForm
from maps.importer import ImportRefused, MapImporter
from maps.mixins import MapScopedQuerysetMixin
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
from maps.permissions import IsStaffOrReadOnly
from maps.serializer import (
    BusLineSerializer,
    EdgeSerializer,
    GameMapSerializer,
    MapVersionSerializer,
    NodeSerializer,
    NodeTypeSerializer,
    StreetEdgeSerializer,
    TrainEdgeSerializer,
    TrainLineSerializer,
    VersionDiffInputSerializer,
    serialize_bus_line_for_graph,
    serialize_previous_round_traffic,
    serialize_train_line_for_graph,
)
from maps.portability import build_export
from maps.versions import (
    bus_chain_rows,
    combination_members,
    combination_poll_texts,
    drop_rows_from,
    put_rows_in,
    train_chain_rows,
)

logger = logging.getLogger(__name__)


# GameMap Views
class GameMapListView(ListCreateAPIView):
    """List all game maps or create a new one."""

    queryset = GameMap.objects.all()
    serializer_class = GameMapSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def perform_create(self, serializer):
        """Set the author when creating a new map."""
        serializer.save(author=self.request.user, updated_by=self.request.user)


class GameMapDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific game map."""

    queryset = GameMap.objects.all()
    serializer_class = GameMapSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"

    def perform_update(self, serializer):
        """Set updated_by when updating a map."""
        serializer.save(updated_by=self.request.user)
        _invalidate_map_cache(self.kwargs["pk"])


# MapVersion Views
class MapVersionListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all map versions for a specific map or create a new one."""

    serializer_class = MapVersionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter map versions by the specific map."""
        map_id = self.get_map_id()
        return MapVersion.objects.filter(game_map_id=map_id)


class MapVersionDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific map version."""

    queryset = MapVersion.objects.all()
    serializer_class = MapVersionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    parser_classes = (MultiPartParser, FormParser)
    lookup_field = "pk"
    lookup_url_kwarg = "version_pk"


class GenerateCombinationsView(GenericAPIView):
    """Generate combination MapVersions from a list of atomic version IDs."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    @transaction.atomic
    def post(self, request, pk):
        from itertools import combinations as _combinations

        game_map = get_object_or_404(GameMap, pk=pk)
        version_ids = request.data.get("version_ids", [])
        if len(version_ids) < 2:
            return Response(
                {"error": "Provide at least 2 version IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        atomic_versions = list(
            MapVersion.objects.filter(pk__in=version_ids, game_map=game_map)
        )
        if len(atomic_versions) != len(version_ids):
            return Response(
                {"error": "One or more versions not found for this map."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if any(v.base_version for v in atomic_versions):
            return Response(
                {"error": "Do not include base versions."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_version = MapVersion.objects.filter(
            game_map=game_map, base_version=True
        ).first()

        existing: dict = {}
        for v in atomic_versions:
            existing[frozenset([v.pk])] = v

        n = len(atomic_versions)
        all_subsets = []
        for size in range(2, n + 1):
            for combo in _combinations(atomic_versions, size):
                all_subsets.append(frozenset(v.pk for v in combo))

        created_count = 0
        for subset in all_subsets:
            if subset in existing:
                continue
            members = sorted(
                [v for v in atomic_versions if v.pk in subset], key=lambda v: v.name
            )
            combo_name = " + ".join(v.name for v in members)
            combo_poll_text, combo_revert_text = combination_poll_texts(
                [v.name for v in members]
            )
            combo_version = MapVersion.objects.create(
                game_map=game_map,
                name=combo_name,
                poll_text=combo_poll_text,
                revert_poll_text=combo_revert_text,
                base_version=False,
            )
            existing[subset] = combo_version
            created_count += 1

            member_versions = [existing[frozenset([p])] for p in subset]
            # "Apply both changes" is base minus what each member removed plus
            # what each member added (`maps/versions.py`), not the union of the
            # members. The union kept a street a member had *replaced* beside its
            # replacement: on the live box every combination containing
            # `Busspuren` carries 15 corridors twice over, 155 edges where the
            # whole map has 140, so the router saw two parallel roads and the bus
            # chain had two candidates per link.
            #
            # `TrainLine` and the two chain models were simply missing. That is
            # why all four combinations on the box hold no rail at all, and why
            # three play-tested games ran on a map with no U-Bahn and no S-Bahn.
            for model in (
                Node,
                Edge,
                StreetEdge,
                TrainEdge,
                BusLine,
                TrainLine,
                BusLineEdge,
                TrainLineEdge,
            ):
                members = combination_members(model, base_version, member_versions)
                for element in model.objects.filter(pk__in=members):
                    element.map_versions.add(combo_version)

        all_entries = {**existing}
        for subset, version in all_entries.items():
            neighbours = []
            size = len(subset)
            for other_subset, other_version in all_entries.items():
                if len(other_subset) == size + 1 and subset.issubset(other_subset):
                    neighbours.append(other_version)
            for other_subset, other_version in all_entries.items():
                if len(other_subset) == size - 1 and other_subset.issubset(subset):
                    neighbours.append(other_version)
            if size == 1 and base_version:
                neighbours.append(base_version)
            version.compatible_versions.set(neighbours)

        if base_version:
            existing_base_compat = list(base_version.compatible_versions.all())
            new_atomics = [v for v in atomic_versions if v not in existing_base_compat]
            if new_atomics:
                base_version.compatible_versions.add(*new_atomics)

        return Response({"created": created_count}, status=status.HTTP_201_CREATED)


# NodeType Views
class NodeTypeListView(ListCreateAPIView):
    """List all node types or create a new one."""

    queryset = NodeType.objects.all()
    serializer_class = NodeTypeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)


class NodeTypeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific node type."""

    queryset = NodeType.objects.all()
    serializer_class = NodeTypeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "nodetype_pk"


# Node Views
class NodeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all nodes for a specific map or create a new one."""

    serializer_class = NodeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter nodes by the specific map."""
        map_id = self.get_map_id()
        return Node.objects.filter(game_map_id=map_id)


class NodeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific node."""

    queryset = Node.objects.all()
    serializer_class = NodeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "node_pk"


# Edge Views
class EdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all edges for a specific map or create a new one."""

    serializer_class = EdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter edges by the specific map."""
        map_id = self.get_map_id()
        return Edge.objects.filter(game_map_id=map_id)

    @transaction.atomic
    def perform_create(self, serializer):
        """Create edge, and optionally the reverse edge if bidirectional."""
        bidirectional = serializer.validated_data.pop("bidirectional", False)
        edge = serializer.save()

        if bidirectional:
            reverse_edge = Edge.objects.create(
                game_map=edge.game_map,
                name=edge.name,
                start_node=edge.end_node,
                end_node=edge.start_node,
                biking=edge.biking,
                bike_lane=edge.bike_lane,
                walking=edge.walking,
                max_lanes=edge.max_lanes,
            )
            reverse_edge.map_versions.set(edge.map_versions.all())

        _invalidate_map_cache(self.kwargs["pk"])


class EdgeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific edge."""

    queryset = Edge.objects.all()
    serializer_class = EdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "edge_pk"


# StreetEdge Views
class StreetEdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all street edges for a specific map or create a new one."""

    serializer_class = StreetEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter street edges by the specific map."""
        map_id = self.get_map_id()
        return StreetEdge.objects.filter(edge__game_map_id=map_id).select_related(
            "edge"
        )


class StreetEdgeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific street edge."""

    queryset = StreetEdge.objects.all()
    serializer_class = StreetEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "streetedge_pk"


# BusLine Views
class BusLineListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all bus lines for a specific map or create a new one."""

    serializer_class = BusLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter bus lines by the specific map."""
        map_id = self.get_map_id()
        return BusLine.objects.filter(game_map_id=map_id)

    def perform_create(self, serializer):
        instance = serializer.save()
        edge_ids = self.request.data.get("edges", [])  # type: ignore
        if edge_ids:
            se_by_pk = {se.pk: se for se in StreetEdge.objects.filter(pk__in=edge_ids)}
            rows = BusLineEdge.objects.bulk_create(
                [
                    BusLineEdge(bus_line=instance, street_edge=se_by_pk[eid], order=idx)
                    for idx, eid in enumerate(edge_ids)
                    if eid in se_by_pk
                ]
            )
            # The chain runs wherever the line runs. The editor draws a line on
            # the map, not on one version — versions come from the diff endpoint.
            put_rows_in(rows, instance.map_versions.all())
        _invalidate_map_cache(self.kwargs["pk"])


class BusLineDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific bus line."""

    queryset = BusLine.objects.all()
    serializer_class = BusLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "busline_pk"

    def perform_update(self, serializer):
        serializer.save()
        _invalidate_map_cache(self.kwargs["pk"])

    def perform_destroy(self, instance):
        map_pk = self.kwargs["pk"]
        instance.delete()
        _invalidate_map_cache(map_pk)


class BusLineEdgesView(GenericAPIView):
    """Replace all edges for a bus line."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def put(self, request, pk, busline_pk):
        """Replace the chain — in every version the line runs in.

        The endpoint takes no version, so it cannot do less than that, and the
        editor's line panel has always meant "this is the line's route". A
        per-version chain edit is the diff endpoint's job.
        """
        bus_line = get_object_or_404(BusLine, pk=busline_pk, game_map_id=pk)
        edge_ids = request.data.get("edges", [])
        BusLineEdge.objects.filter(bus_line=bus_line).delete()
        if edge_ids:
            se_by_pk = {se.pk: se for se in StreetEdge.objects.filter(pk__in=edge_ids)}
            rows = BusLineEdge.objects.bulk_create(
                [
                    BusLineEdge(bus_line=bus_line, street_edge=se_by_pk[eid], order=idx)
                    for idx, eid in enumerate(edge_ids)
                    if eid in se_by_pk
                ]
            )
            put_rows_in(rows, bus_line.map_versions.all())
        _invalidate_map_cache(pk)
        return Response(
            BusLineSerializer(bus_line).data,
            status=status.HTTP_200_OK,
        )


# TrainEdge Views
class TrainEdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all train edges for a specific map or create a new one."""

    serializer_class = TrainEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter train edges by the specific map."""
        map_id = self.get_map_id()
        return TrainEdge.objects.filter(edge__game_map_id=map_id).select_related("edge")


class TrainEdgeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific train edge."""

    queryset = TrainEdge.objects.all()
    serializer_class = TrainEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "trainedge_pk"


# TrainLine Views
class TrainLineListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all train lines for a specific map or create a new one."""

    serializer_class = TrainLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter train lines by the specific map."""
        map_id = self.get_map_id()
        return TrainLine.objects.filter(game_map_id=map_id)

    def perform_create(self, serializer):
        instance = serializer.save()
        edge_ids = self.request.data.get("edges", [])  # type: ignore
        if edge_ids:
            te_by_pk = {te.pk: te for te in TrainEdge.objects.filter(pk__in=edge_ids)}
            rows = TrainLineEdge.objects.bulk_create(
                [
                    TrainLineEdge(
                        train_line=instance, train_edge=te_by_pk[eid], order=idx
                    )
                    for idx, eid in enumerate(edge_ids)
                    if eid in te_by_pk
                ]
            )
            put_rows_in(rows, instance.map_versions.all())
        _invalidate_map_cache(self.kwargs["pk"])


class TrainLineDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific train line."""

    queryset = TrainLine.objects.all()
    serializer_class = TrainLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "trainline_pk"

    def perform_update(self, serializer):
        serializer.save()
        _invalidate_map_cache(self.kwargs["pk"])

    def perform_destroy(self, instance):
        map_pk = self.kwargs["pk"]
        instance.delete()
        _invalidate_map_cache(map_pk)


class TrainLineEdgesView(GenericAPIView):
    """Replace all edges for a train line."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def put(self, request, pk, trainline_pk):
        """Replace the chain in every version the line runs in — see the bus."""
        train_line = get_object_or_404(TrainLine, pk=trainline_pk, game_map_id=pk)
        edge_ids = request.data.get("edges", [])
        TrainLineEdge.objects.filter(train_line=train_line).delete()
        if edge_ids:
            te_by_pk = {te.pk: te for te in TrainEdge.objects.filter(pk__in=edge_ids)}
            rows = TrainLineEdge.objects.bulk_create(
                [
                    TrainLineEdge(
                        train_line=train_line, train_edge=te_by_pk[eid], order=idx
                    )
                    for idx, eid in enumerate(edge_ids)
                    if eid in te_by_pk
                ]
            )
            put_rows_in(rows, train_line.map_versions.all())
        _invalidate_map_cache(pk)
        return Response(
            TrainLineSerializer(train_line).data,
            status=status.HTTP_200_OK,
        )


# Custom Graph View
class MapVersionGraphView(MapScopedQuerysetMixin, GenericAPIView):
    serializer_class = MapVersionSerializer
    authentication_classes = (SessionAuthentication,)

    @staticmethod
    def _with_traffic(graph_data, game_id):
        """Attach the last round's observed speeds, outside the cache.

        The graph is the same for every game on that map version and is
        cached for an hour under map + version. The traffic is neither: it
        belongs to one game and changes every round. So it is attached to
        the response on the way out and never stored in the cached payload,
        which would serve one game's jams to another game — and keep serving
        them after the next round had run.
        """
        return {
            **graph_data,
            "previous_round_traffic": serialize_previous_round_traffic(game_id),
        }

    def get(self, request, *args, **kwargs):
        map_pk = self.get_map_id()
        version_pk = kwargs.get("version_pk")
        # Optional: the game whose last round's speeds to attach. Without it
        # the payload is unchanged apart from an empty traffic list.
        game_id = request.query_params.get("game")

        try:
            map_obj = GameMap.objects.get(pk=map_pk)

        except GameMap.DoesNotExist:
            logger.error("map not found")
            return Response(
                {"error": "Map not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build cache key
        cache_key = f"map_graph:{map_pk}:{version_pk}"

        # Try to get from cache first
        cached_graph = cache.get(cache_key)
        if cached_graph:
            return Response(
                self._with_traffic(cached_graph, game_id),
                status=status.HTTP_200_OK,
            )

        # Get or determine version
        if not version_pk:
            version = MapVersion.objects.filter(game_map=map_obj).first()
            if not version:
                return Response(
                    {"error": "No map version found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            try:
                version = MapVersion.objects.get(pk=version_pk, game_map=map_obj)
            except MapVersion.DoesNotExist:
                logger.error(f"version {version_pk} not found for map {map_pk}")
                return Response(
                    {"error": "Map version not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            # Get all nodes for this map version
            nodes = Node.objects.filter(
                game_map=map_obj, map_versions=version
            ).prefetch_related("node_type")

            # Get all edges for this map version with street_edge and train_edge prefetch
            # StreetEdge and TrainEdge have ForeignKey to Edge, so we use prefetch_related
            edges = (
                Edge.objects.filter(game_map=map_obj, map_versions=version)
                .select_related("start_node", "end_node", "game_map")
                .prefetch_related("streetedge_set", "trainedge_set")
            )

            # PT lines of this version. Their chains are not prefetched here:
            # the serializer asks for the through rows *this version* holds
            # (`maps/versions.py`), which a prefetch over `edges` cannot express
            # — and never could, since `.filter()` on a prefetched manager goes
            # back to the database anyway.
            bus_lines = BusLine.objects.filter(game_map=map_obj, map_versions=version)
            train_lines = TrainLine.objects.filter(
                game_map=map_obj, map_versions=version
            )

            # Serialize the data
            nodes_data = NodeSerializer(nodes, many=True).data
            edges_data = EdgeSerializer(edges, many=True).data

            # Serialize PT lines for graph/routing
            bus_lines_data = [
                serialize_bus_line_for_graph(bl, version) for bl in bus_lines
            ]
            train_lines_data = [
                serialize_train_line_for_graph(tl, version) for tl in train_lines
            ]

            graph_data = {
                "map_id": map_pk,
                "version_id": version_pk or version.pk,
                "version_name": version.name,
                "version_description": version.description,
                "nodes": nodes_data,
                "edges": edges_data,
                "node_count": len(nodes_data),
                "edge_count": len(edges_data),
                "bus_lines": bus_lines_data,
                "train_lines": train_lines_data,
                "scale": map_obj.scale,
                "x_dim": map_obj.x_dim,
                "y_dim": map_obj.y_dim,
                "background_image_url": (
                    request.build_absolute_uri(map_obj.background_image.url)
                    if map_obj.background_image
                    else None
                ),
                "image_offset_x": map_obj.image_offset_x,
                "image_offset_y": map_obj.image_offset_y,
                "image_scale": map_obj.image_scale,
                "image_crop_top": map_obj.image_crop_top,
                "image_crop_right": map_obj.image_crop_right,
                "image_crop_bottom": map_obj.image_crop_bottom,
                "image_crop_left": map_obj.image_crop_left,
            }

            # Cache the result for 1 hour (3600 seconds)
            cache.set(cache_key, graph_data, 3600)

            return Response(
                self._with_traffic(graph_data, game_id),
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception(
                f"Error building graph for map {map_pk} version {version_pk}:{e!s}"
            )
            return Response(
                {"error": "Error building graph"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def _drop_edge_from_version(edge, version):
    """Take an edge out of a version, links and all.

    A version that does not hold the street cannot hold a line running over it:
    the row would name a version whose graph has no such edge, which is exactly
    the state the export drops (silently, until now) and the simulator turns into
    riders stranded at a stop the line can never reach — and a stranded rider
    keeps the line dispatching and paying society CO2 to the end of the clock.
    The line itself stays; it is a link short and `_register_pt_line` truncates
    it there, which is the honest reading of a street that is gone.
    """
    for se in StreetEdge.objects.filter(edge=edge, map_versions=version):
        se.map_versions.remove(version)
        drop_rows_from(
            BusLineEdge.objects.filter(street_edge=se, map_versions=version), version
        )
    for te in TrainEdge.objects.filter(edge=edge, map_versions=version):
        te.map_versions.remove(version)
        drop_rows_from(
            TrainLineEdge.objects.filter(train_edge=te, map_versions=version), version
        )


class MapExportView(MapScopedQuerysetMixin, GenericAPIView):
    """The map as a file — the whole thing, or one version flattened.

    Two urls, two jobs. Without a `version_pk` this is the backup: every
    version, `compatible_versions`, the poll texts and per-element membership,
    which is the only shape a multi-version map survives a move between boxes
    in. With one it is the single-version snapshot the project has always
    written, and the shape every file in `map_examples/` has.

    The format itself lives in `maps/portability.py`, because the importer has
    to agree with it.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get(self, request, *args, **kwargs):
        game_map = get_object_or_404(GameMap, pk=self.get_map_id())
        version_pk = kwargs.get("version_pk")

        version = None
        if version_pk:
            version = get_object_or_404(
                MapVersion, pk=version_pk, game_map=game_map
            )
        elif not MapVersion.objects.filter(game_map=game_map).exists():
            return Response(
                {"error": "No map version found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(build_export(game_map, version), status=status.HTTP_200_OK)


class MapImportView(GenericAPIView):
    """`POST api/maps/import/` — a map file in, a new map out. S19.

    The door the SPA's upload screen uses, and the only one: `/map/upload/`
    was a Django form page doing the same job, and it is a redirect now. The
    form (`MapUploadForm`) and the importer (`maps/importer.py`) are unchanged,
    so what a file has to say is exactly what it had to say before.

    **201 `{"id": <pk>}`**, or **400 `{"fields": {...}, "graph": [...]}`**:
    `fields` is the form's own errors per field — a taken name, a file that is
    not JSON — and `graph` is everything wrong inside a file that parsed, all
    at once, because a hand-edited file is fixed in one pass or in twenty
    uploads. Both are German and both are shown as they come.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        form = MapUploadForm(data=request.POST, files=request.FILES)
        if not form.is_valid():
            return Response(
                {
                    "fields": {
                        name: [str(message) for message in messages]
                        for name, messages in form.errors.items()
                    },
                    "graph": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            game_map = MapImporter(request.user).run(form.cleaned_data)
        except ImportRefused as refused:
            return Response(
                {"fields": {}, "graph": refused.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"id": game_map.pk}, status=status.HTTP_201_CREATED)


def _invalidate_map_cache(map_pk):
    """Invalidate graph cache for all versions of a map."""
    for version in MapVersion.objects.filter(game_map_id=map_pk):
        cache.delete(f"map_graph:{map_pk}:{version.pk}")
    cache.delete(f"map_graph:{map_pk}:None")


class GameMapImageUploadView(GenericAPIView):
    """Upload a background image for a game map."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, pk):
        game_map = get_object_or_404(GameMap, pk=pk)
        image = request.FILES.get("image")
        if not image:
            return Response(
                {"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST
            )
        game_map.background_image = image
        game_map.updated_by = request.user
        game_map.save()
        _invalidate_map_cache(pk)
        serializer = GameMapSerializer(game_map, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        game_map = get_object_or_404(GameMap, pk=pk)
        if game_map.background_image:
            game_map.background_image.delete(save=False)
            game_map.background_image = None  # type: ignore
            game_map.updated_by = request.user
            game_map.save()
        _invalidate_map_cache(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VersionDiffCreateView(GenericAPIView):
    """Create a new map version from a source version + changeset."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    @transaction.atomic
    def post(self, request, pk):
        game_map = get_object_or_404(GameMap, pk=pk)
        serializer = VersionDiffInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not isinstance(data, dict):
            return Response(
                {"error": "Cannot create empty version diff."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Get source version
        try:
            source = MapVersion.objects.get(
                pk=data["source_version_id"], game_map=game_map
            )
        except MapVersion.DoesNotExist:
            return Response(
                {"error": "Source version not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Unset other base versions if this will be base
        if data.get("is_base_version"):
            MapVersion.objects.filter(game_map=game_map, base_version=True).update(
                base_version=False
            )

        # 1. Create new MapVersion
        new_version = MapVersion.objects.create(
            game_map=game_map,
            name=data["version_name"],
            description=data.get("description", ""),
            poll_text=data.get("poll_text", "Die Karte soll ... "),
            revert_poll_text=data.get("revert_poll_text", "Die Karte soll ... "),
            base_version=data.get("is_base_version", False),
            source_version=source,
        )

        # 2. Clone all M2M from source version
        for node in Node.objects.filter(map_versions=source):
            node.map_versions.add(new_version)
        for edge in Edge.objects.filter(map_versions=source):
            edge.map_versions.add(new_version)
        for se in StreetEdge.objects.filter(map_versions=source):
            se.map_versions.add(new_version)
        for te in TrainEdge.objects.filter(map_versions=source):
            te.map_versions.add(new_version)
        for bl in BusLine.objects.filter(map_versions=source):
            bl.map_versions.add(new_version)
        for tl in TrainLine.objects.filter(map_versions=source):
            tl.map_versions.add(new_version)
        # The chains too: a line is its links, and the new version starts as a
        # copy of the source before the changeset moves anything.
        for row in BusLineEdge.objects.filter(map_versions=source):
            row.map_versions.add(new_version)
        for row in TrainLineEdge.objects.filter(map_versions=source):
            row.map_versions.add(new_version)

        # 3. Apply edge changes (clone approach)
        for change in data.get("edge_changes", []):
            try:
                original_edge = Edge.objects.get(
                    pk=change["edge_id"], game_map=game_map
                )
            except Edge.DoesNotExist:
                continue

            # Remove original edge from new version
            original_edge.map_versions.remove(new_version)

            # Create cloned edge with modified properties
            cloned_edge = Edge.objects.create(
                game_map=game_map,
                name=original_edge.name,
                start_node=original_edge.start_node,
                end_node=original_edge.end_node,
                biking=change.get("biking", original_edge.biking),
                bike_lane=change.get("bike_lane", original_edge.bike_lane),
                walking=change.get("walking", original_edge.walking),
                max_lanes=change.get("max_lanes", original_edge.max_lanes),
            )
            cloned_edge.map_versions.add(new_version)

            # Clone StreetEdge if original had one
            original_se = StreetEdge.objects.filter(
                edge=original_edge, map_versions=source
            ).first()
            if original_se:
                original_se.map_versions.remove(new_version)
                cloned_se = StreetEdge.objects.create(
                    edge=cloned_edge,
                    speed_limit=change.get("speed_limit", original_se.speed_limit),
                    lanes=change.get("lanes", original_se.lanes),
                    dedicated_bus_lane=change.get(
                        "dedicated_bus_lane", original_se.dedicated_bus_lane
                    ),
                )
                cloned_se.map_versions.add(new_version)

                # Every bus line that runs over the original street *in this
                # version* runs over the clone instead. The original row is
                # kept and merely loses this version — deleting it moved the
                # line onto the clone in every version sharing it, which is the
                # bug that broke buslinie 100 in the base version on the box.
                # Iterating the rows rather than the lines also handles a line
                # that traverses the same street twice, where `.get()` raised.
                for row in BusLineEdge.objects.filter(
                    street_edge=original_se, map_versions=new_version
                ):
                    row.map_versions.remove(new_version)
                    clone_row = BusLineEdge.objects.create(
                        bus_line_id=row.bus_line_id,
                        street_edge=cloned_se,
                        order=row.order,
                    )
                    clone_row.map_versions.add(new_version)

            # Clone TrainEdge if original had one
            original_te = TrainEdge.objects.filter(
                edge=original_edge, map_versions=source
            ).first()
            if original_te:
                original_te.map_versions.remove(new_version)
                cloned_te = TrainEdge.objects.create(edge=cloned_edge)
                cloned_te.map_versions.add(new_version)

                # Same for rail — and it is not a rare case: a `"type": "both"`
                # edge is street and rail at once, which is how drawing bus
                # lanes on the box also took `U2` off two of its nine links.
                for row in TrainLineEdge.objects.filter(
                    train_edge=original_te, map_versions=new_version
                ):
                    row.map_versions.remove(new_version)
                    clone_row = TrainLineEdge.objects.create(
                        train_line_id=row.train_line_id,
                        train_edge=cloned_te,
                        order=row.order,
                    )
                    clone_row.map_versions.add(new_version)

        # 4. Apply PT line changes
        try:
            pt_line_changes = data.get("pt_line_changes", [])
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        for pt_change in pt_line_changes:
            action = pt_change["action"]
            line_type = pt_change["line_type"]

            if action == "add":
                if line_type == "bus":
                    bl = BusLine.objects.create(
                        game_map=game_map,
                        name=pt_change.get("name", "New Bus Line"),
                        intervall=pt_change.get("interval", 5),
                        bus_capacity=pt_change.get("capacity", 85),
                        bus_speed_kmh=pt_change.get("speed_kmh", 30),
                    )
                    bl.map_versions.add(new_version)
                    if pt_change.get("edge_ids"):
                        edge_ids = pt_change["edge_ids"]
                        se_by_pk = {
                            se.pk: se
                            for se in StreetEdge.objects.filter(pk__in=edge_ids)
                        }
                        put_rows_in(
                            BusLineEdge.objects.bulk_create(
                                [
                                    BusLineEdge(
                                        bus_line=bl,
                                        street_edge=se_by_pk[eid],
                                        order=idx,
                                    )
                                    for idx, eid in enumerate(edge_ids)
                                    if eid in se_by_pk
                                ]
                            ),
                            [new_version],
                        )
                else:
                    tl = TrainLine.objects.create(
                        game_map=game_map,
                        name=pt_change.get("name", "New Train Line"),
                        intervall=pt_change.get("interval", 10),
                        train_capacity=pt_change.get("capacity", 1000),
                        train_speed_kmh=pt_change.get("speed_kmh", 40),
                    )
                    tl.map_versions.add(new_version)
                    if pt_change.get("edge_ids"):
                        edge_ids = pt_change["edge_ids"]
                        te_by_pk = {
                            te.pk: te
                            for te in TrainEdge.objects.filter(pk__in=edge_ids)
                        }
                        put_rows_in(
                            TrainLineEdge.objects.bulk_create(
                                [
                                    TrainLineEdge(
                                        train_line=tl,
                                        train_edge=te_by_pk[eid],
                                        order=idx,
                                    )
                                    for idx, eid in enumerate(edge_ids)
                                    if eid in te_by_pk
                                ]
                            ),
                            [new_version],
                        )

            elif action == "remove" and pt_change.get("id"):
                # A row must never name a version its line has left: after S14
                # that would be written into the file as a link of a line that
                # is not there.
                if line_type == "bus":
                    bl = BusLine.objects.filter(pk=pt_change["id"]).first()
                    if bl:
                        bl.map_versions.remove(new_version)
                        drop_rows_from(
                            BusLineEdge.objects.filter(
                                bus_line=bl, map_versions=new_version
                            ),
                            new_version,
                        )
                else:
                    tl = TrainLine.objects.filter(pk=pt_change["id"]).first()
                    if tl:
                        tl.map_versions.remove(new_version)
                        drop_rows_from(
                            TrainLineEdge.objects.filter(
                                train_line=tl, map_versions=new_version
                            ),
                            new_version,
                        )

            elif action == "modify" and pt_change.get("id"):
                # Clone the line for the new version
                if line_type == "bus":
                    original = BusLine.objects.filter(pk=pt_change["id"]).first()
                    if original:
                        original.map_versions.remove(new_version)
                        drop_rows_from(
                            BusLineEdge.objects.filter(
                                bus_line=original, map_versions=new_version
                            ),
                            new_version,
                        )
                        cloned = BusLine.objects.create(
                            game_map=game_map,
                            name=pt_change.get("name", original.name),
                            intervall=pt_change.get("interval", original.intervall),
                            bus_capacity=pt_change.get(
                                "capacity", original.bus_capacity
                            ),
                            bus_speed_kmh=pt_change.get(
                                "speed_kmh", original.bus_speed_kmh
                            ),
                        )
                        cloned.map_versions.add(new_version)
                        if pt_change.get("edge_ids"):
                            edge_ids = pt_change["edge_ids"]
                            se_by_pk = {
                                se.pk: se
                                for se in StreetEdge.objects.filter(pk__in=edge_ids)
                            }
                            put_rows_in(
                                BusLineEdge.objects.bulk_create(
                                    [
                                        BusLineEdge(
                                            bus_line=cloned,
                                            street_edge=se_by_pk[eid],
                                            order=idx,
                                        )
                                        for idx, eid in enumerate(edge_ids)
                                        if eid in se_by_pk
                                    ]
                                ),
                                [new_version],
                            )
                        else:
                            # No edge list: the clone keeps the route the
                            # original runs on the version it was copied from.
                            put_rows_in(
                                BusLineEdge.objects.bulk_create(
                                    [
                                        BusLineEdge(
                                            bus_line=cloned,
                                            street_edge=t.street_edge,
                                            order=t.order,
                                        )
                                        for t in bus_chain_rows(original, source)
                                    ]
                                ),
                                [new_version],
                            )
                else:
                    original = TrainLine.objects.filter(pk=pt_change["id"]).first()
                    if original:
                        original.map_versions.remove(new_version)
                        drop_rows_from(
                            TrainLineEdge.objects.filter(
                                train_line=original, map_versions=new_version
                            ),
                            new_version,
                        )
                        cloned = TrainLine.objects.create(
                            game_map=game_map,
                            name=pt_change.get("name", original.name),
                            intervall=pt_change.get("interval", original.intervall),
                            train_capacity=pt_change.get(
                                "capacity", original.train_capacity
                            ),
                            train_speed_kmh=pt_change.get(
                                "speed_kmh", original.train_speed_kmh
                            ),
                        )
                        cloned.map_versions.add(new_version)
                        if pt_change.get("edge_ids"):
                            edge_ids = pt_change["edge_ids"]
                            te_by_pk = {
                                te.pk: te
                                for te in TrainEdge.objects.filter(pk__in=edge_ids)
                            }
                            put_rows_in(
                                TrainLineEdge.objects.bulk_create(
                                    [
                                        TrainLineEdge(
                                            train_line=cloned,
                                            train_edge=te_by_pk[eid],
                                            order=idx,
                                        )
                                        for idx, eid in enumerate(edge_ids)
                                        if eid in te_by_pk
                                    ]
                                ),
                                [new_version],
                            )
                        else:
                            put_rows_in(
                                TrainLineEdge.objects.bulk_create(
                                    [
                                        TrainLineEdge(
                                            train_line=cloned,
                                            train_edge=t.train_edge,
                                            order=t.order,
                                        )
                                        for t in train_chain_rows(original, source)
                                    ]
                                ),
                                [new_version],
                            )

        # 5. Apply structural deletions
        deleted_node_ids = data.get("deleted_node_ids", [])
        for node_id in deleted_node_ids:
            node = Node.objects.filter(
                pk=node_id, game_map=game_map, map_versions=new_version
            ).first()
            if not node:
                continue
            node.map_versions.remove(new_version)
            # Cascade: remove all edges connected to this node from the version
            for edge in Edge.objects.filter(map_versions=new_version).filter(
                Q(start_node=node) | Q(end_node=node)
            ):
                edge.map_versions.remove(new_version)
                _drop_edge_from_version(edge, new_version)

        deleted_edge_ids = data.get("deleted_edge_ids", [])
        for edge_id in deleted_edge_ids:
            edge = Edge.objects.filter(
                pk=edge_id, game_map=game_map, map_versions=new_version
            ).first()
            if not edge:
                continue
            edge.map_versions.remove(new_version)
            _drop_edge_from_version(edge, new_version)

        # 6. Apply structural additions
        temp_node_map = {}
        for node_data in data.get("new_nodes", []):
            new_node = Node.objects.create(
                game_map=game_map,
                x_position=node_data["x_position"],
                y_position=node_data["y_position"],
            )
            new_node.map_versions.add(new_version)
            temp_node_map[node_data["temp_id"]] = new_node

        for edge_data in data.get("new_edges", []):
            start_raw = edge_data["temp_start_node"]
            end_raw = edge_data["temp_end_node"]

            # Resolve start node: temp ID or real node ID
            if start_raw in temp_node_map:
                start_node = temp_node_map[start_raw]
            else:
                try:
                    start_node = Node.objects.get(pk=int(start_raw), game_map=game_map)
                except (Node.DoesNotExist, ValueError):
                    continue

            # Resolve end node: temp ID or real node ID
            if end_raw in temp_node_map:
                end_node = temp_node_map[end_raw]
            else:
                try:
                    end_node = Node.objects.get(pk=int(end_raw), game_map=game_map)
                except (Node.DoesNotExist, ValueError):
                    continue

            has_street = (
                edge_data.get("speed_limit") is not None
                or edge_data.get("lanes") is not None
            )

            def _create_directed_edge(s_node, e_node):
                new_edge = Edge.objects.create(
                    game_map=game_map,
                    start_node=s_node,
                    end_node=e_node,
                    biking=edge_data.get("biking", False),
                    bike_lane=edge_data.get("bike_lane", False),
                    walking=edge_data.get("walking", False),
                    max_lanes=edge_data.get("max_lanes", 1),
                )
                new_edge.map_versions.add(new_version)
                if has_street:
                    se = StreetEdge.objects.create(
                        edge=new_edge,
                        speed_limit=edge_data.get("speed_limit", 50),
                        lanes=edge_data.get("lanes", 1),
                        dedicated_bus_lane=False,
                    )
                    se.map_versions.add(new_version)

            _create_directed_edge(start_node, end_node)
            if edge_data.get("bidirectional"):
                _create_directed_edge(end_node, start_node)

        # 7. Invalidate cache
        _invalidate_map_cache(pk)

        return Response(
            MapVersionSerializer(new_version).data,
            status=status.HTTP_201_CREATED,
        )
