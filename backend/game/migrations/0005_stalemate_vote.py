import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0004_gameround_between_round_phase_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="gameround",
            name="between_round_phase",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("stats", "Stats Review"),
                    ("discussion", "Discussion"),
                    ("voting", "Voting"),
                    ("stalemate", "Stalemate"),
                ],
                default="none",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="gameround",
            name="stalemate_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="StalemateVote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("want_revote", models.BooleanField()),
                ("voted_at", models.DateTimeField(auto_now_add=True)),
                (
                    "game_round",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stalemate_votes",
                        to="game.gameround",
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stalemate_votes",
                        to="game.player",
                    ),
                ),
            ],
            options={
                "ordering": ("game_round", "voted_at"),
                "unique_together": {("game_round", "player")},
            },
        ),
    ]
