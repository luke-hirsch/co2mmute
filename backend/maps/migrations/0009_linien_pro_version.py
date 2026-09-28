"""A PT line's chain belongs to versions too, like every other element.

`BusLineEdge` and `TrainLineEdge` were the only parts of the graph without a
`map_versions` m2m, so there was exactly one chain per line for a whole map. That
is the bug behind the damage on the live box: `VersionDiffCreateView` clones a
changed street for the new version and then *moved* the line's through-row onto
the clone, and with no membership on the row the move landed in every version
sharing the line. Buslinie 100 reaches 0 of its 7 street edges in the base
version of the map the research group plays; `U2` was caught too, through a
`"type": "both"` edge.

`unique_together` on (line, order) goes with it. Two rows of one line now
legitimately share an order — one per version, one pointing at the original
street and one at the clone — and a reader filters by version before it reads the
order. Nothing else relied on the constraint: every writer either replaces a
line's whole chain or enumerates a fresh one.

The backfill is faithful, not corrective. Each row goes into the versions where
**both** its line and its street or train edge are already present, which records
the damage rather than repairing it; the repair is S16, explicit and under the
test suite. Reverse drops the field, so the backfill has no reverse of its own.

Evidence: `.claude/plans/diagnostics/[findings]-kartenversionen-2026-09-27.md`.
"""

from django.db import migrations, models

from maps.versions import backfill_chain_versions


def place_existing_chains(apps, schema_editor):
    backfill_chain_versions(
        apps.get_model("maps", "BusLine"),
        apps.get_model("maps", "BusLineEdge"),
        apps.get_model("maps", "TrainLine"),
        apps.get_model("maps", "TrainLineEdge"),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0008_pt_kapazitaeten"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="buslineedge",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="trainlineedge",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="buslineedge",
            name="map_versions",
            field=models.ManyToManyField(to="maps.mapversion"),
        ),
        migrations.AddField(
            model_name="trainlineedge",
            name="map_versions",
            field=models.ManyToManyField(to="maps.mapversion"),
        ),
        migrations.RunPython(place_existing_chains, migrations.RunPython.noop),
    ]
