# Manual migration for adding simulation parameters to GameSession

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0005_add_route_and_simulation_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesession',
            name='people_per_agent',
            field=models.PositiveIntegerField(default=1000),
        ),
        migrations.AddField(
            model_name='gamesession',
            name='tick_duration_min',
            field=models.PositiveSmallIntegerField(default=5),
        ),
        migrations.AddField(
            model_name='gamesession',
            name='morning_departure_hour',
            field=models.PositiveSmallIntegerField(default=9),
        ),
        migrations.AddField(
            model_name='gamesession',
            name='evening_departure_hour',
            field=models.PositiveSmallIntegerField(default=17),
        ),
        migrations.AddField(
            model_name='gamesession',
            name='departure_std_dev_min',
            field=models.PositiveSmallIntegerField(default=10),
        ),
    ]
