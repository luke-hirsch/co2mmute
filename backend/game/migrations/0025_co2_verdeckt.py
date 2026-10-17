"""CO₂ hidden until the summary, for research; off on every game before."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0024_ausbalanciert"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="hide_co2",
            field=models.BooleanField(default=False),
        ),
    ]
