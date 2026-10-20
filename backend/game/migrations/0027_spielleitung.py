from django.db import migrations, models

HOST_NAME = "Spielleitung"


def host_rows_are_spielleitung(apps, schema_editor):
    """The host's own row used to carry "<full name> (Host)", and the roster
    sends every row of a game to every player in it. The account link stays: it
    is what marks the row."""
    Player = apps.get_model("game", "Player")
    Player.objects.filter(user=models.F("game__game_host")).exclude(
        name=HOST_NAME
    ).update(name=HOST_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0026_zahlen_aus_den_konstanten"),
    ]

    operations = [
        migrations.RunPython(host_rows_are_spielleitung, migrations.RunPython.noop),
    ]
