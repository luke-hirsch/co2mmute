from django.urls import path

from .views import MapGenerationView


app_name = "maps"


urlpatterns = [
    path("generate/", MapGenerationView.as_view(), name="generate-map"),
]
