from django.urls import path

from studies import views

app_name = "studies"

urlpatterns = [
    path("", views.StudyListView.as_view(), name="study-list"),
    path("<int:pk>/", views.StudyDetailView.as_view(), name="study-detail"),
    path("<int:pk>/codes/", views.CodeListView.as_view(), name="code-list"),
    path(
        "<int:pk>/codes/<int:code_pk>/",
        views.CodeDetailView.as_view(),
        name="code-detail",
    ),
    path("<int:pk>/cards/", views.CardListView.as_view(), name="card-list"),
    path("<int:pk>/games/", views.StudyGameListView.as_view(), name="game-list"),
    path(
        "<int:pk>/games/<str:game_id>/",
        views.StudyGameDetailView.as_view(),
        name="game-detail",
    ),
    path("<int:pk>/notes/", views.NoteListView.as_view(), name="note-list"),
    path(
        "<int:pk>/notes/<int:note_pk>/",
        views.NoteDetailView.as_view(),
        name="note-detail",
    ),
]
