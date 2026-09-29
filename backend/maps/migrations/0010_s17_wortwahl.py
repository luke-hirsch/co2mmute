"""S17: help text only — the agent word changed and "Klasse" went.

Two `AlterField`s carrying nothing but a `help_text`, which is what Django
tracks. No column changes, no data pass, and reversing it restores the old
wording. It is here so `makemigrations --check` stays clean, not because the
database needs anything.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0009_linien_pro_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gamemap',
            name='co2_budget_kg_per_round',
            field=models.PositiveIntegerField(default=8000, help_text='Vorschlag für das CO₂-Budget, pro Runde in kg. Genug, wenn viele umsteigen, zu wenig, wenn alle mit dem Auto fahren.'),
        ),
        migrations.AlterField(
            model_name='gamemap',
            name='district_commuters',
            field=models.PositiveIntegerField(default=6400, help_text='Pendler, die die Straßen dieser Karte im Berufsverkehr verkraften. Wird auf die Gruppen aufgeteilt, damit auf der Karte gleich viel Verkehr ist, egal wie viele mitspielen.'),
        ),
    ]
