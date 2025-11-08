from django.urls import path
from .views import SessionCreateView

urlpatterns = [
    path("sessions/create/", SessionCreateView.as_view(), name="session_create")
]
