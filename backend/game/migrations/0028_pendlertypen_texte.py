"""The seven standard Pendlertypen, in their rewritten words.

0023 seeded the first drafts; it stays as it was. Here each standard row gets its
new text, and only where the description is still exactly the old draft: a text
somebody edited in the admin stays, and a game keeps the copy it made at its
start (a game's rows have a game, these have none).
"""

from django.db import migrations

# name, the draft 0023 seeded, the text it becomes
TEXTS = [
    (
        "Auf den letzten Drücker",
        "Deine Gruppe ist immer spät dran. Jede Minute zählt.",
        "Immer zu spät los. Hauptsache schnell da, egal womit.",
    ),
    (
        "Sparfuchs",
        "Ende des Monats, Konto leer. Jeder Euro zählt.",
        "Ende des Monats, Konto leer. Der billigste Weg gewinnt, auch wenn er dauert.",
    ),
    (
        "Öko aus Überzeugung",
        "So wenig CO₂ wie möglich, koste es, was es wolle.",
        "So wenig CO₂ wie möglich, auch wenn es länger dauert oder mehr kostet.",
    ),
    (
        "Sportskanone",
        "Wozu ins Fitnessstudio? Rad und Füße sind Training.",
        "Wozu ins Fitnessstudio? Wo es geht, mit dem Rad oder zu Fuß.",
    ),
    (
        "Bloß kein Stress",
        "Kein Umsteigen, keine Umwege. Einfach ankommen.",
        "Kein Umsteigen, keine Umwege. Hauptsache entspannt ankommen.",
    ),
    (
        "Benzin im Blut",
        "Ohne Auto geht gar nichts. Lieber im Stau als im Bus.",
        "Ohne Auto geht gar nichts. Lieber im Stau als in Bus und Bahn.",
    ),
    (
        "Einfach du",
        "Keine Mission. Fahr so, wie du selbst fahren würdest.",
        "Keine Rolle. Fahr so, wie du selbst fahren würdest.",
    ),
]


def rewrite_standard_texts(apps, schema_editor):
    Persona = apps.get_model("game", "Persona")
    for name, old, new in TEXTS:
        Persona.objects.filter(game=None, name=name, description=old).update(
            description=new
        )


def restore_old_texts(apps, schema_editor):
    Persona = apps.get_model("game", "Persona")
    for name, old, new in TEXTS:
        Persona.objects.filter(game=None, name=name, description=new).update(
            description=old
        )


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0027_spielleitung"),
    ]

    operations = [
        migrations.RunPython(rewrite_standard_texts, restore_old_texts),
    ]
