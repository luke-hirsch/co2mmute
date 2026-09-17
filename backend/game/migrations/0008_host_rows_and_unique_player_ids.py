"""Two data fixes before 0009 adds the unique constraint on player_id.

Roadmap.md 1.6. Written by hand (makemigrations --empty); the historical
Player model has neither host_rows() nor generate_unique_player_id(), so both
are spelled out here.
"""

import uuid

from django.db import migrations
from django.db.models import Count, F


def give_duplicate_player_ids_a_new_one(apps, schema_editor):
    """The old generator never saw a collision, so a game can hold one
    player_id twice. The later row gets a fresh id; its cookie stops working,
    which only matters in a running game."""
    Player = apps.get_model("game", "Player")
    duplicates = list(
        Player.objects.exclude(player_id=None)
        .values("game_id", "player_id")
        .annotate(rows=Count("pk"))
        .filter(rows__gt=1)
    )
    for duplicate in duplicates:
        rows = Player.objects.filter(
            game_id=duplicate["game_id"], player_id=duplicate["player_id"]
        ).order_by("joined_at", "pk")
        for player in list(rows)[1:]:
            while True:
                new_id = f"P-{uuid.uuid4().hex[:4].upper()}"
                taken = Player.objects.filter(
                    game_id=player.game_id, player_id=new_id
                ).exists()
                if not taken:
                    break
            Player.objects.filter(pk=player.pk).update(player_id=new_id)


def host_rows_are_not_host_controlled(apps, schema_editor):
    """From here on controlled_by_host means "played at the host machine".
    The host's own row is recognised by its account (host_rows())."""
    Player = apps.get_model("game", "Player")
    Player.objects.filter(user=F("game__game_host")).update(controlled_by_host=False)


def host_rows_are_host_controlled(apps, schema_editor):
    Player = apps.get_model("game", "Player")
    Player.objects.filter(user=F("game__game_host")).update(controlled_by_host=True)


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0007_gameround_vote_option_ids_statsack"),
    ]

    operations = [
        migrations.RunPython(
            give_duplicate_player_ids_a_new_one, migrations.RunPython.noop
        ),
        migrations.RunPython(
            host_rows_are_not_host_controlled, host_rows_are_host_controlled
        ),
    ]
