from django.urls import path

from .views import (
    SessionCreateView,
    SessionDeleteView,
    SessionDetailView,
    SessionListView,
    SessionUpdateView,
)

urlpatterns = [
    path("sessions/", SessionListView.as_view(), name="session_list"),
    path("sessions/create/", SessionCreateView.as_view(), name="session_create"),
    path("sessions/<int:pk>/", SessionDetailView.as_view(), name="session_detail"),
    path("sessions/<int:pk>/edit/", SessionUpdateView.as_view(), name="session_update"),
    path(
        "sessions/<int:pk>/delete/", SessionDeleteView.as_view(), name="session_delete"
    ),
]
