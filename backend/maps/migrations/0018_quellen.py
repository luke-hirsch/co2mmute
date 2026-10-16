from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0017_kreisverkehr'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamemap',
            name='credits',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
