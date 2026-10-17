"""The study tables of the research export.

Registered with `game.research_export` from the AppConfig, so with the app off
the file has none of them. Only studies that have an exported game leave, and
within them only what is about exported games. Nothing of the author's account.
The study's name and description and a note's text are the researchers' own
words, which is why they may leave where a classroom host's free text may not.
"""

import json

from game.models import Player

from studies.models import ResearchNote, Study, StudyGame, StudySeat

SCHEMA = """
CREATE TABLE study (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE study_game (
    study_id INTEGER NOT NULL REFERENCES study(id),
    game_id INTEGER NOT NULL REFERENCES game(id)
);
CREATE TABLE study_seat (
    code TEXT NOT NULL,
    game_id INTEGER NOT NULL REFERENCES game(id),
    player_id INTEGER NOT NULL REFERENCES player(id)
);
CREATE TABLE study_note (
    id INTEGER PRIMARY KEY,
    study_id INTEGER NOT NULL REFERENCES study(id),
    about_date TEXT,
    created_on TEXT NOT NULL,
    text TEXT NOT NULL,
    meta TEXT NOT NULL
);
CREATE TABLE study_note_game (
    note_id INTEGER NOT NULL REFERENCES study_note(id),
    game_id INTEGER NOT NULL REFERENCES game(id)
);
"""


def write_tables(db, games) -> None:
    game_ids = {game.pk for game in games}
    links = list(
        StudyGame.objects.filter(game_id__in=game_ids).order_by("study_id", "game_id")
    )
    studies = Study.objects.filter(pk__in={link.study_id for link in links}).order_by(
        "pk"
    )  # type: ignore

    for study in studies:
        db.execute(
            "INSERT INTO study VALUES (?,?,?)",
            (study.pk, study.name, study.description),
        )
    for link in links:
        db.execute("INSERT INTO study_game VALUES (?,?)", (link.study_id, link.game_id))  # type: ignore

    # The seats the player table has: the host's own row never leaves.
    players = set(
        Player.objects.filter(game_id__in=game_ids)
        .without_host_rows()
        .values_list("pk", flat=True)
    )
    seats = StudySeat.objects.filter(game_id__in=game_ids, player_id__in=players)
    for seat in seats.select_related("participant").order_by("pk"):
        db.execute(
            "INSERT INTO study_seat VALUES (?,?,?)",
            (seat.participant.code, seat.game_id, seat.player_id),  # type: ignore
        )

    for note in ResearchNote.objects.filter(study__in=studies).order_by("pk"):
        db.execute(
            "INSERT INTO study_note VALUES (?,?,?,?,?,?)",
            (
                note.pk,
                note.study_id,  # type: ignore
                note.about_date.isoformat() if note.about_date else None,
                note.created_at.date().isoformat(),
                note.text,
                json.dumps(note.meta, ensure_ascii=False, sort_keys=True),
            ),
        )
        for game_id in sorted(
            note.games.filter(pk__in=game_ids).values_list("pk", flat=True)
        ):
            db.execute("INSERT INTO study_note_game VALUES (?,?)", (note.pk, game_id))
