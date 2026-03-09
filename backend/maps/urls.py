from django.urls import path
from maps import views_rest

app_name = "maps"

urlpatterns = [
    # GameMap endpoints - no pk required in path
    path("", views_rest.GameMapListView.as_view(), name="gamemap-list"),
    path("<int:pk>/", views_rest.GameMapDetailView.as_view(), name="gamemap-detail"),
    # MapVersion endpoints - scoped to specific map
    path(
        "<int:pk>/versions/",
        views_rest.MapVersionListView.as_view(),
        name="mapversion-list",
    ),
    path(
        "<int:pk>/versions/<int:version_pk>/",
        views_rest.MapVersionDetailView.as_view(),
        name="mapversion-detail",
    ),
    # MapVersion Graph endpoint - get complete graph for a specific version
    path(
        "<int:pk>/graph/version/<int:version_pk>/",
        views_rest.MapVersionGraphView.as_view(),
        name="mapversion-graph",
    ),
    path(
        "<int:pk>/graph/baseversion/",
        views_rest.MapVersionGraphView.as_view(),
        name="mapversion-graph",
    ),
    # NodeType endpoints - no scoping (global)
    path("node-types/", views_rest.NodeTypeListView.as_view(), name="nodetype-list"),
    path(
        "node-types/<int:nodetype_pk>/",
        views_rest.NodeTypeDetailView.as_view(),
        name="nodetype-detail",
    ),
    # Node endpoints - scoped to specific map
    path("<int:pk>/nodes/", views_rest.NodeListView.as_view(), name="node-list"),
    path(
        "<int:pk>/nodes/<int:node_pk>/",
        views_rest.NodeDetailView.as_view(),
        name="node-detail",
    ),
    # Edge endpoints - scoped to specific map
    path("<int:pk>/edges/", views_rest.EdgeListView.as_view(), name="edge-list"),
    path(
        "<int:pk>/edges/<int:edge_pk>/",
        views_rest.EdgeDetailView.as_view(),
        name="edge-detail",
    ),
    # StreetEdge endpoints - scoped to specific map
    path(
        "<int:pk>/street-edges/",
        views_rest.StreetEdgeListView.as_view(),
        name="streetedge-list",
    ),
    path(
        "<int:pk>/street-edges/<int:streetedge_pk>/",
        views_rest.StreetEdgeDetailView.as_view(),
        name="streetedge-detail",
    ),
    # BusLine endpoints - scoped to specific map
    path(
        "<int:pk>/bus-lines/",
        views_rest.BusLineListView.as_view(),
        name="busline-list",
    ),
    path(
        "<int:pk>/bus-lines/<int:busline_pk>/",
        views_rest.BusLineDetailView.as_view(),
        name="busline-detail",
    ),
    path(
        "<int:pk>/bus-lines/<int:busline_pk>/edges/",
        views_rest.BusLineEdgesView.as_view(),
        name="busline-edges",
    ),
    # TrainEdge endpoints - scoped to specific map
    path(
        "<int:pk>/train-edges/",
        views_rest.TrainEdgeListView.as_view(),
        name="trainedge-list",
    ),
    path(
        "<int:pk>/train-edges/<int:trainedge_pk>/",
        views_rest.TrainEdgeDetailView.as_view(),
        name="trainedge-detail",
    ),
    # TrainLine endpoints - scoped to specific map
    path(
        "<int:pk>/train-lines/",
        views_rest.TrainLineListView.as_view(),
        name="trainline-list",
    ),
    path(
        "<int:pk>/train-lines/<int:trainline_pk>/",
        views_rest.TrainLineDetailView.as_view(),
        name="trainline-detail",
    ),
    path(
        "<int:pk>/train-lines/<int:trainline_pk>/edges/",
        views_rest.TrainLineEdgesView.as_view(),
        name="trainline-edges",
    ),
    # Background image upload
    path(
        "<int:pk>/background-image/",
        views_rest.GameMapImageUploadView.as_view(),
        name="gamemap-background-image",
    ),
    # Version diff creation
    path(
        "<int:pk>/versions/create-from-diff/",
        views_rest.VersionDiffCreateView.as_view(),
        name="version-diff-create",
    ),
    # Generate combination versions
    path(
        "<int:pk>/versions/generate-combinations/",
        views_rest.GenerateCombinationsView.as_view(),
        name="version-generate-combinations",
    ),
    # Map export (JSON)
    path(
        "<int:pk>/export/",
        views_rest.MapExportView.as_view(),
        name="map-export",
    ),
    path(
        "<int:pk>/export/version/<int:version_pk>/",
        views_rest.MapExportView.as_view(),
        name="map-export-version",
    ),
]
