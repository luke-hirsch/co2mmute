"""Signals for maps app."""

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from maps import graph_cache
from maps.models import (
    BusLine,
    BusLineEdge,
    Edge,
    MapVersion,
    Node,
    StreetEdge,
    TrainEdge,
    TrainLine,
    TrainLineEdge,
)


@receiver(pre_save, sender=MapVersion)
def ensure_single_base_version(sender, instance, **kwargs):
    """
    Ensure only one base version per map.

    If setting this version as base, unset all other base versions for this map.
    If unsetting the only base version, force this one to stay as base.
    """
    if instance.pk:  # Only on update, not on create
        # Get current state from database
        try:
            current = MapVersion.objects.get(pk=instance.pk)
            was_base = current.base_version
        except MapVersion.DoesNotExist:
            was_base = False
    else:
        was_base = False

    # Case 1: Setting this version as base when one already exists
    if instance.base_version:
        # Unset all other base versions for this map using bulk_update
        # This is more efficient than individual saves
        other_bases = MapVersion.objects.filter(
            game_map=instance.game_map, base_version=True
        )
        if instance.pk:
            other_bases = other_bases.exclude(pk=instance.pk)

        if other_bases.exists():
            other_bases.update(base_version=False)

    # Case 2: Trying to unset base when it's the only base version
    elif not instance.base_version and was_base:
        other_bases = MapVersion.objects.filter(
            game_map=instance.game_map, base_version=True
        ).exclude(pk=instance.pk)

        if not other_bases.exists():
            # This is the only base version, force it to stay as base
            instance.base_version = True


@receiver(post_delete, sender=MapVersion)
def ensure_base_version_on_delete(sender, instance, **kwargs):
    """If deleted version was base, make another one base."""
    if instance.base_version:
        remaining = MapVersion.objects.filter(game_map=instance.game_map).first()

        if remaining:
            remaining.base_version = True
            remaining.save()


@receiver(post_delete, sender=MapVersion)
def delete_change_image_file(sender, instance, **kwargs):
    """Django deletes the row, not the picture it points at — the same as a
    game's QR code. On commit, so a delete that rolls back keeps its picture,
    and only if no other version names the same file."""
    name = instance.change_img.name if instance.change_img else None
    if not name:
        return
    storage = instance.change_img.storage

    def delete_file():
        if not MapVersion.objects.filter(change_img=name).exists():
            storage.delete(name)

    transaction.on_commit(delete_file)


# ── the cached graph ───────────────────────────────────────────────────────
#
# Every model a graph is built from, and every one's version membership. Until
# F10 only `Node` and `Edge` were here, so a street or a railway laid under an
# edge — the editor's "+ Straße anlegen" — was saved and not drawn for up to an
# hour. Membership is an m2m, and an m2m add saves no row, so it needs its own
# receiver: every version write in this app is a `map_versions.add`.

GRAPH_MODELS = (
    Node,
    Edge,
    StreetEdge,
    TrainEdge,
    BusLine,
    TrainLine,
    BusLineEdge,
    TrainLineEdge,
    MapVersion,
)


def _map_of(instance):
    """The map a row belongs to, however far up it sits.

    `None` if a parent is already gone — a cascade deletes children after
    their parent row has left the database, and the parent's own signal has
    cleared the map then.
    """
    try:
        if isinstance(instance, (StreetEdge, TrainEdge)):
            return instance.edge.game_map_id
        if isinstance(instance, BusLineEdge):
            return instance.bus_line.game_map_id
        if isinstance(instance, TrainLineEdge):
            return instance.train_line.game_map_id
        return instance.game_map_id
    except ObjectDoesNotExist:
        return None


def _graph_row_changed(sender, instance, **kwargs):
    graph_cache.invalidate(_map_of(instance))


def _graph_membership_changed(sender, instance, action, reverse, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    # Reverse is `version.node_set.add(...)`: the instance is the version.
    graph_cache.invalidate(instance.game_map_id if reverse else _map_of(instance))


for _model in GRAPH_MODELS:
    post_save.connect(
        _graph_row_changed, sender=_model, dispatch_uid=f"graph-save-{_model.__name__}"
    )
    post_delete.connect(
        _graph_row_changed, sender=_model, dispatch_uid=f"graph-delete-{_model.__name__}"
    )
    # A version's own m2m is its ballot, which the graph carries too: every
    # node and edge lists its versions with their `compatible_versions`.
    through = (
        MapVersion.compatible_versions.through
        if _model is MapVersion
        else _model.map_versions.through
    )
    m2m_changed.connect(
        _graph_membership_changed,
        sender=through,
        dispatch_uid=f"graph-membership-{_model.__name__}",
    )
