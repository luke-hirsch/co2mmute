"""`api/studies/…` — staff only, reading too: a participant code is a bearer token."""

import base64
import logging
from io import BytesIO

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from game.models import GameSession
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from studies.models import (
    Participant,
    ResearchNote,
    Study,
    StudyGame,
    new_participant_code,
)
from studies.serializers import (
    NoteSerializer,
    ParticipantSerializer,
    StudySerializer,
)

logger = logging.getLogger(__name__)

MAX_CODES_PER_BATCH = 500


def refuse(detail: str, reason: str) -> Response:
    return Response(
        {"detail": detail, "reason": reason}, status=status.HTTP_409_CONFLICT
    )


class StaffOnly:
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)


class StudyScoped(StaffOnly):
    def get_study(self) -> Study:
        return get_object_or_404(Study, pk=self.kwargs["pk"])


class StudyListView(StaffOnly, ListCreateAPIView):
    queryset = Study.objects.all()
    serializer_class = StudySerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


def study_deletion_refusal(study: Study) -> Response | None:
    """A 409 if a game of the study started or a code sits on a seat, else None.

    Like a map: what was played is the data, and the study ties it together.
    """
    started = study.games.filter(game__started_at__isnull=False)
    if started.exists():
        return refuse(
            "In dieser Studie wurde schon ein Spiel gestartet. Eine Studie mit "
            "gespielten Spielen lässt sich nicht löschen.",
            "played",
        )
    if study.codes.filter(seats__isnull=False).exists():
        return refuse(
            "Mit Teilnahmecodes dieser Studie sitzen schon Leute in Spielen. "
            "Lösch erst diese Spiele.",
            "seated",
        )
    return None


class StudyDetailView(StaffOnly, RetrieveUpdateDestroyAPIView):
    queryset = Study.objects.all()
    serializer_class = StudySerializer

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            study = Study.objects.select_for_update().get(pk=self.get_object().pk)
            refusal = study_deletion_refusal(study)
            if refusal is not None:
                return refusal
            study.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CodeListView(StudyScoped, GenericAPIView):
    serializer_class = ParticipantSerializer

    def get(self, request, pk):
        codes = self.get_study().codes.all()
        return Response(self.get_serializer(codes, many=True).data)

    def post(self, request, pk):
        """`{count}` new codes, unique across every study."""
        study = self.get_study()
        count = request.data.get("count")
        if (
            not isinstance(count, int)
            or isinstance(count, bool)
            or not 1 <= count <= MAX_CODES_PER_BATCH
        ):
            return Response(
                {"count": f"Wähle zwischen 1 und {MAX_CODES_PER_BATCH} Codes."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        made = []
        with transaction.atomic():
            taken = set(Participant.objects.values_list("code", flat=True))
            while len(made) < count:
                code = new_participant_code()
                if code in taken:
                    continue
                taken.add(code)
                made.append(Participant(study=study, code=code))
            try:
                Participant.objects.bulk_create(made)
            except IntegrityError:  # another batch took one in between
                return Response(
                    {"detail": "Versuch es noch einmal."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        rows = study.codes.filter(code__in=[p.code for p in made])
        return Response(
            self.get_serializer(rows, many=True).data, status=status.HTTP_201_CREATED
        )


class CodeDetailView(StudyScoped, GenericAPIView):
    def delete(self, request, pk, code_pk):
        participant = get_object_or_404(Participant, pk=code_pk, study_id=pk)
        if participant.seats.exists():
            return refuse(
                "Dieser Code sitzt schon in einem Spiel und bleibt.", "seated"
            )
        participant.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def card_qr(url: str) -> str:
    """The code's address as an SVG data URI: crisp on paper at any size."""
    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=1)
    buffer = BytesIO()
    image.save(buffer)
    return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()


class CardListView(StudyScoped, GenericAPIView):
    def get(self, request, pk):
        rows = []
        for participant in self.get_study().codes.all():
            url = f"{settings.BASE_URL}/app/join/{participant.code}"
            rows.append({"code": participant.code, "url": url, "qr": card_qr(url)})
        return Response(rows)


def game_row(link: StudyGame) -> dict:
    game = link.game
    return {
        "game_id": game.game_id,
        "name": game.game_name,
        "map": game.game_map.name if game.game_map else None,
        "started_at": game.started_at,
        "ended_at": game.ended_at,
        "hide_co2": game.hide_co2,
    }


class StudyGameListView(StudyScoped, GenericAPIView):
    def get(self, request, pk):
        links = self.get_study().games.select_related("game", "game__game_map")
        return Response([game_row(link) for link in links])

    def post(self, request, pk):
        study = self.get_study()
        game_id = str(request.data.get("game_id") or "").strip().upper()
        with transaction.atomic():
            game = get_object_or_404(
                GameSession.objects.select_for_update(), game_id=game_id
            )
            if game.started_at is not None:
                return refuse(
                    "Dieses Spiel ist schon gestartet. Nur ein Spiel in der Lobby "
                    "kommt in eine Studie.",
                    "started",
                )
            if StudyGame.objects.filter(game=game).exists():
                return refuse("Dieses Spiel gehört schon zu einer Studie.", "linked")
            link = StudyGame.objects.create(study=study, game=game)
        return Response(game_row(link), status=status.HTTP_201_CREATED)


class StudyGameDetailView(StudyScoped, GenericAPIView):
    def delete(self, request, pk, game_id):
        link = get_object_or_404(
            StudyGame.objects.select_related("game"),
            study_id=pk,
            game__game_id=game_id.upper(),
        )
        if link.game.started_at is not None:
            return refuse(
                "Dieses Spiel ist schon gestartet und bleibt in der Studie.",
                "started",
            )
        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NoteListView(StudyScoped, ListCreateAPIView):
    serializer_class = NoteSerializer

    def get_queryset(self):
        return self.get_study().notes.select_related("author")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "study": self.get_study()}

    def perform_create(self, serializer):
        serializer.save(study=self.get_study(), author=self.request.user)


class NoteDetailView(StudyScoped, RetrieveUpdateDestroyAPIView):
    serializer_class = NoteSerializer
    lookup_url_kwarg = "note_pk"

    def get_queryset(self):
        return ResearchNote.objects.filter(study_id=self.kwargs["pk"])

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "study": self.get_study()}
