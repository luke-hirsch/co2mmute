from django.db import migrations, models


def _rail_only_pks(Edge):
    return list(
        Edge.objects.filter(trainedge__isnull=False, streetedge__isnull=True)
        .values_list("pk", flat=True)
        .distinct()
    )


def close_railways_to_bikes(apps, schema_editor):
    Edge = apps.get_model("maps", "Edge")
    Edge.objects.filter(pk__in=_rail_only_pks(Edge)).update(biking=False, walking=False)


def reopen_railways(apps, schema_editor):
    Edge = apps.get_model("maps", "Edge")
    Edge.objects.filter(pk__in=_rail_only_pks(Edge)).update(biking=True, walking=True)


class Migration(migrations.Migration):
    dependencies = [("maps", "0005_alter_busline_bus_capacity_and_more")]

    operations = [
        migrations.AddField(
            model_name="edge",
            name="bike_lane",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(close_railways_to_bikes, reopen_railways),
    ]
