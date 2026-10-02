"""What a map version actually holds, in one place.

A `MapVersion` is a filter over one shared graph: every element carries a
`map_versions` m2m and a version is the set of rows naming it. Since a PT line's
chain rows carry it too, four callers ask the same question — "which links does
this line run on *this* version" — and they used to answer it four different
ways, or not at all:

* `serialize_bus_line_for_graph` / `serialize_train_line_for_graph`, the payload
  the client routes on,
* `MapExportView`, which used to infer the chain from the edges it had already
  written and silently drop the rest,
* the simulator's line loader (`game/simulation.py:_read_lines` today), which
  took the whole chain and let `_register_pt_line` trim it to whatever happened to be on the network.

One question, one function. The same argument as `game/auth.py`: one resolver,
three callers.
"""

import logging

logger = logging.getLogger(__name__)


def bus_chain_rows(bus_line, version):
    """`BusLineEdge` rows of `bus_line` on `version`, in travel order.

    `version=None` means the map has no versions at all — a round built by hand
    or in a test — and then every row counts, which is the fallback
    the simulator's line loader has always documented.
    """
    from maps.models import BusLineEdge

    rows = BusLineEdge.objects.filter(bus_line=bus_line)
    if version is not None:
        rows = rows.filter(map_versions=version)
    return rows.order_by("order")


def train_chain_rows(train_line, version):
    """`TrainLineEdge` rows of `train_line` on `version`, in travel order."""
    from maps.models import TrainLineEdge

    rows = TrainLineEdge.objects.filter(train_line=train_line)
    if version is not None:
        rows = rows.filter(map_versions=version)
    return rows.order_by("order")


def put_rows_in(rows, versions):
    """Every chain row into every one of `versions`.

    The writers' half of the chain m2m, and the reason it is a named function:
    a row created without it belongs to no version and its line silently loses a
    link. Every path that makes a chain row goes through here — the importer, the
    two line endpoints, the two chain endpoints and the version builders.
    """
    versions = list(versions)
    if not versions:
        return
    for row in rows:
        row.map_versions.add(*versions)


def drop_rows_from(rows, version):
    """Take `version` off every one of `rows`, and only that version.

    The counterpart, and the whole shape of the fix: a version that stops running
    a line over a street removes *itself* from the row. Deleting the row took the
    line off that street in every other version too.
    """
    for row in rows:
        row.map_versions.remove(version)


def combination_members(model, base_version, member_versions):
    """The pks of `model` a combination of `member_versions` holds.

    A combination version means "apply both changes", so it is

        base − everything a member removed + everything a member added

    and *not* the union of the members. The union looks right only because every
    version derived from base contains all of base; it loses every removal. That
    is how `Busspuren + Umgehungsstraßen` on the live box came to carry 155 edges
    where the whole map has 140: the fifteen streets `Busspuren` replaced stayed
    in beside their fifteen bus-lane clones, so the router saw two parallel roads
    on fifteen corridors and the bus chain had two candidates per link.

    Two members that change the *same* element still land both clones — composing
    two diffs over one street has no single right answer, and neither did the
    union. The box's three atomics do not overlap.

    Without a base version there is nothing to diff against and the union is all
    this can mean.
    """
    if base_version is None:
        members: set = set()
        for version in member_versions:
            members |= _pks(model, version)
        return members

    base_pks = _pks(model, base_version)
    added: set = set()
    removed: set = set()
    for version in member_versions:
        version_pks = _pks(model, version)
        added |= version_pks - base_pks
        removed |= base_pks - version_pks
    return (base_pks - removed) | added


def _pks(model, version):
    return set(model.objects.filter(map_versions=version).values_list("pk", flat=True))


def german_list(names):
    """`»A« und »B«`, `»A«, »B« und »C«` — a list a class can read aloud."""
    quoted = [f"»{name}«" for name in names]
    if len(quoted) == 1:
        return quoted[0]
    return ", ".join(quoted[:-1]) + " und " + quoted[-1]


def combination_poll_texts(names):
    """The two ballot questions for a generated combination version.

    The hand-drawn versions carry poll text somebody wrote for them; a
    combination gets a template, because there are 2^n − n − 1 of them and
    nobody is going to write prose for eleven. It was English ("Apply changes:
    Buslinie, Umgehungsstraßen") and the class votes on it, so on the live box
    four of eight ballot options read English to a room of school students.

    Phrased as the atomics are — a question starting `Soll`/`Sollen` — so the
    combination does not look like a different kind of object on the screen.
    """
    listed = german_list(list(names))
    return (
        f"Sollen die Änderungen {listed} zusammen umgesetzt werden?",
        f"Sollen die Änderungen {listed} zurückgenommen werden?",
    )


def backfill_chain_versions(BusLine, BusLineEdge, TrainLine, TrainLineEdge):
    """Put every existing chain row in the versions that can actually run it.

    Faithful, not corrective: a row lands in the versions where **both** its line
    and its street or train edge are already present. On the live box that
    records the damage rather than repairing it — buslinie 100 keeps reaching 0
    of its 7 edges in the base version — because a migration guessing at what a
    hand-drawn version meant is worse than the explicit repair S16 does with the
    test suite watching. A row whose line belongs to no version at all (the box
    has three such `Bus 147` leftovers) stays in no version, which is what it
    already meant.

    Takes its models as arguments so `maps/0009` can hand it the historical ones
    and a test can hand it the real ones.
    """
    added = 0
    for line_model, row_model, line_field, element_field in (
        (BusLine, BusLineEdge, "bus_line", "street_edge"),
        (TrainLine, TrainLineEdge, "train_line", "train_edge"),
    ):
        for line in line_model.objects.all():
            line_versions = set(line.map_versions.values_list("pk", flat=True))
            if not line_versions:
                continue
            rows = row_model.objects.filter(**{line_field: line}).select_related(
                element_field
            )
            for row in rows:
                element = getattr(row, element_field)
                shared = line_versions & set(
                    element.map_versions.values_list("pk", flat=True)
                )
                if shared:
                    row.map_versions.add(*shared)
                    added += len(shared)
    logger.info("[maps] chain rows placed in %s version slots", added)
    return added
