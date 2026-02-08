# Manual migration for adding speed fields to GameMap, BusLine, and TrainLine

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0001_initial'),
    ]

    operations = [
        # Add speed fields to GameMap
        migrations.AddField(
            model_name='gamemap',
            name='walk_speed_kmh',
            field=models.PositiveSmallIntegerField(default=5),
        ),
        migrations.AddField(
            model_name='gamemap',
            name='bike_speed_kmh',
            field=models.PositiveSmallIntegerField(default=20),
        ),
        migrations.AddField(
            model_name='gamemap',
            name='default_car_speed_kmh',
            field=models.PositiveSmallIntegerField(default=50),
        ),
        # Add speed field to BusLine
        migrations.AddField(
            model_name='busline',
            name='bus_speed_kmh',
            field=models.PositiveSmallIntegerField(default=30),
        ),
        # Add speed field to TrainLine
        migrations.AddField(
            model_name='trainline',
            name='train_speed_kmh',
            field=models.PositiveSmallIntegerField(default=40),
        ),
    ]
