"""CO₂ hidden until the summary, and the study a game belongs to.

Both for research, both off on every game before.
"""

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
        migrations.AddField(
            model_name="gamesession",
            name="study",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
    ]
