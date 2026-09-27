"""The 60-seat U-Bahn, out of the databases as well as out of the file.

`0005` moved the model defaults to bus 85 / train 1000 and stopped there,
because a default only decides what a *new* line gets. Every line on every map
already imported still says 60 — not from the old default but from
`map_examples/Berlin_Mitte-West.json`, which stated `"capacity": 60` outright
for both modes, so the importer's own numbers never got a look in. That is the
60-seat U-Bahn: it is in the shipped file (fixed with S5), and it is in the dev
and the live database, where no re-import reaches it.

Only rows that still say exactly 60 are touched. 60 is what that one file said
and is not a number any part of this project would choose for either mode — a
line a map author has since given a capacity of its own is left alone.

Safe to change under a running game, which it would not have been before the
timetable landed: nothing on the emissions path reads capacity any more
(`_calculate_emissions_and_cost` charges society per vehicle-km), so capacity
decides only who fits on board, and a full bus is a wait rather than an ending.

There is no reverse. Putting 60 back would have to hit every row that says 85
or 1000 today, including the ones that mean it, so undoing this is a restore,
not a migration.
"""

from django.db import migrations

WRONG_CAPACITY = 60
BUS_CAPACITY = 85
TRAIN_CAPACITY = 1000


def fix_capacities(apps, schema_editor):
    BusLine = apps.get_model("maps", "BusLine")
    TrainLine = apps.get_model("maps", "TrainLine")

    BusLine.objects.filter(bus_capacity=WRONG_CAPACITY).update(
        bus_capacity=BUS_CAPACITY
    )
    TrainLine.objects.filter(train_capacity=WRONG_CAPACITY).update(
        train_capacity=TRAIN_CAPACITY
    )


class Migration(migrations.Migration):
    dependencies = [("maps", "0007_karten_kalibrierung")]

    operations = [migrations.RunPython(fix_capacities, migrations.RunPython.noop)]
