from django.urls import path
from content.views import PageDetailView

app_name = "content"

urlpatterns = [
    path("<slug:key>/", PageDetailView.as_view(), name="static-page"),
]