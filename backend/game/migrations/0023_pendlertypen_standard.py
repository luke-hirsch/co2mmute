"""The standard Pendlertypen, the ones every create form offers.

A migration rather than a command, because every instance runs `migrate` on
its way up (the box on every deploy) and nobody has to remember a second step.
From here on they are data: the admin edits them, and a game keeps its own
copies, so changing one here later changes no game already played.
"""

from django.db import migrations

STANDARD = [
    (
        "Auf den letzten Drücker",
        "Deine Gruppe ist immer spät dran. Jede Minute zählt.",
    ),
    ("Sparfuchs", "Ende des Monats, Konto leer. Jeder Euro zählt."),
    (
        "Öko aus Überzeugung",
        "So wenig CO₂ wie möglich, koste es, was es wolle.",
    ),
    ("Sportskanone", "Wozu ins Fitnessstudio? Rad und Füße sind Training."),
    ("Bloß kein Stress", "Kein Umsteigen, keine Umwege. Einfach ankommen."),
    ("Benzin im Blut", "Ohne Auto geht gar nichts. Lieber im Stau als im Bus."),
    (
        "Einfach du",
        "Keine Mission. Fahr so, wie du selbst fahren würdest.",
    ),
]


def seed(apps, schema_editor):
    Persona = apps.get_model("game", "Persona")
    for order, (name, description) in enumerate(STANDARD):
        Persona.objects.get_or_create(
            game=None,
            name=name,
            defaults={"description": description, "order": order},
        )


def unseed(apps, schema_editor):
    Persona = apps.get_model("game", "Persona")
    Persona.objects.filter(game=None, name__in=[name for name, _ in STANDARD]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0022_pendlertyp"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
