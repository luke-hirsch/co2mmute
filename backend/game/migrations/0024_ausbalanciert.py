"""The balanced deal, and a home per Gruppe.

In a balanced game a seat's Gruppen live at different homes, so the home moves
from the seat onto each Gruppe in `Player.agent_assignments`. Seats dealt
before keep theirs: every one of their Gruppen gets the seat's home.
"""

from django.db import migrations, models


def homes_onto_gruppen(apps, schema_editor):
    Player = apps.get_model("game", "Player")
    for player in Player.objects.filter(agent_assignments__isnull=False):
        assignments = player.agent_assignments
        if not isinstance(assignments, dict) or "home_node" not in assignments:
            continue
        home = assignments.pop("home_node")
        assignments["agents"] = [
            {"id": agent["id"], "home_node": home, **agent}
            for agent in assignments.get("agents", [])
        ]
        Player.objects.filter(pk=player.pk).update(agent_assignments=assignments)


def homes_onto_seats(apps, schema_editor):
    """Back to one home a seat: the first Gruppe's, since there was only one."""
    Player = apps.get_model("game", "Player")
    for player in Player.objects.filter(agent_assignments__isnull=False):
        assignments = player.agent_assignments
        if not isinstance(assignments, dict) or not assignments.get("agents"):
            continue
        agents = assignments["agents"]
        assignments["home_node"] = agents[0].get("home_node")
        assignments["agents"] = [
            {key: value for key, value in agent.items() if key != "home_node"}
            for agent in agents
        ]
        Player.objects.filter(pk=player.pk).update(agent_assignments=assignments)


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0023_pendlertypen_standard"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="balanced_deal",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(homes_onto_gruppen, homes_onto_seats),
    ]
