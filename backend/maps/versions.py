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

from django.db.models import Q

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


def versions_built_on(version, ignoring=None):
    """`version` and every version built on it — where a row drawn there goes.

    The editor's rule since F10 (decided 2026-10-02): what is drawn in a version
    is in every version built on it. Drawn in base, that is every version of the
    map. Drawn in a change, it is that change and every combination holding it —
    otherwise a class that votes in two changes plays a combination that
    silently lacks part of one.

    Nothing records which versions a combination was made of (its
    `source_version` is empty), so "built on" is read off what the versions
    hold, the same way `combination_members` composes them: V is built on X
    when V holds everything X added over the version X was made from, and
    nothing X removed. For a combination that is exactly true of its members
    and false of every other change.

    A version that adds and removes nothing would by that reading be held by
    every version, base included; nothing is built on it but itself.

    `ignoring` is the row being placed: it is already in `version` when this is
    asked, and counted as part of the change no combination would hold it yet.
    """
    from maps.models import MapVersion

    versions = list(MapVersion.objects.filter(game_map_id=version.game_map_id))
    if version.base_version:
        return versions

    source = version.source_version
    if source is None:
        source = next((v for v in versions if v.base_version and v != version), None)
    if source is None:
        return [version]

    models = _versioned_models()
    added, removed = {}, {}
    for model in models:
        own, theirs = _pks(model, version), _pks(model, source)
        if ignoring is not None and isinstance(ignoring, model):
            own.discard(ignoring.pk)
        added[model], removed[model] = own - theirs, theirs - own
    if not any(added.values()) and not any(removed.values()):
        return [version]

    built_on = [version]
    for other in versions:
        if other == version:
            continue
        holds = {model: _pks(model, other) for model in models}
        if all(
            added[model] <= holds[model] and not (removed[model] & holds[model])
            for model in models
        ):
            built_on.append(other)
    return built_on


def spread_to_built_on(row, drawn_in):
    """Put a row drawn in `drawn_in` into every version built on them.

    The writers' half of `versions_built_on`, for the four rows the editor
    draws — a node, an edge, and the street or railway under an edge. A version
    gets the row only if it can hold it:

    * an edge needs both its nodes there, and no edge of its own between them
      in the same direction. That second half is the `Busspuren` case: a
      version that replaced a street with its own copy keeps the copy, because
      the copy *is* the version's change.
    * a street or a railway needs its edge there, and no other street (or
      railway) under that edge in that version.

    Everything goes into `map_versions` explicitly. "A row naming no version is
    in no version" stays; this is the editor writing the full list, not a
    fallback at read time.
    """
    from maps.models import Edge, Node, StreetEdge, TrainEdge

    drawn = list(drawn_in)
    targets = {}
    for version in drawn:
        for other in versions_built_on(version, ignoring=row):
            targets.setdefault(other.pk, other)
    for version in drawn:
        targets.pop(version.pk, None)

    room = []
    for version in targets.values():
        if isinstance(row, Node):
            fits = True
        elif isinstance(row, Edge):
            fits = (
                Node.objects.filter(
                    pk__in=[row.start_node_id, row.end_node_id], map_versions=version
                ).count()
                == 2
                and not Edge.objects.filter(
                    start_node_id=row.start_node_id,
                    end_node_id=row.end_node_id,
                    map_versions=version,
                )
                .exclude(pk=row.pk)
                .exists()
            )
        elif isinstance(row, (StreetEdge, TrainEdge)):
            fits = (
                row.edge.map_versions.filter(pk=version.pk).exists()
                and not type(row)
                .objects.filter(edge_id=row.edge_id, map_versions=version)
                .exclude(pk=row.pk)
                .exists()
            )
        else:
            raise TypeError(f"the editor draws no {type(row).__name__}")
        if fits:
            room.append(version)
    if room:
        row.map_versions.add(*room)
    return room


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


# ── deleting a version (F14) ──────────────────────────────────────────────


class VersionDeleteRefused(Exception):
    """Why a version may not go: `reason` for the screen, `detail` for people."""

    def __init__(self, reason, detail):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def only_in(version):
    """`{model: [pk, …]}` — the rows `version` holds and no other version does.

    What goes with it. Everything another version still holds stays, whatever
    the version it was drawn in, and so does a row in no version at all: it was
    nowhere before the delete, and guessing where it belongs is not a delete's
    job. On the shipped map this is empty for every version — the triple
    combination holds every change — and it is a version drawn and never
    combined, the click-through case, that has rows of its own.
    """
    from maps.models import MapVersion

    others = MapVersion.objects.filter(game_map_id=version.game_map_id).exclude(
        pk=version.pk
    )
    rows = {}
    for model in _versioned_models():
        elsewhere = set(
            model.objects.filter(map_versions__in=others).values_list("pk", flat=True)
        )
        rows[model] = sorted(_pks(model, version) - elsewhere)
    return rows


def deletion_refusal(version, goes=None):
    """A `VersionDeleteRefused` if `version` may not go, else `None`.

    Three refusals, checked in this order:

    * **base** — every game starts on it, and `ensure_base_version_on_delete`
      would quietly promote some other version to take its place.
    * **running** — a game is running on the map, on any version: after every
      round the class may vote for this one. The same 409 as deleting a running
      game, and for the same reason.
    * **played** — a game has seen it: played on it, had it on a ballot, voted
      for it, or driven over a street that would go with it. Every one of those
      is research data that would go too, silently — `MapVersionVote.map_version`
      and `RouteSegment.edge` are CASCADE, `active_map_version` is SET_NULL.
      Anonymisation keeps every move, route and result linkable; a version
      delete must not be the back door. The way out is to delete those games
      first, or to take the version off the ballot, which keeps it out of every
      new game and loses nothing.
    """
    from game.models import (
        EdgeTrafficSnapshot,
        GameRound,
        GameSession,
        MapVersionVote,
        RouteSegment,
    )
    from maps.models import Edge, Node, StreetEdge, StreetPerRound

    if version.base_version:
        return VersionDeleteRefused(
            "base",
            "Die Grundversion lässt sich nicht löschen: auf ihr fängt jedes Spiel an.",
        )

    on_map = GameSession.objects.filter(game_map_id=version.game_map_id)
    running = on_map.filter(is_active=True, ended_at__isnull=True)
    if running.exists():
        one = running.count() == 1
        return VersionDeleteRefused(
            "running",
            f"Auf dieser Karte {'läuft' if one else 'laufen'} gerade "
            f"{_named_games(running)}. Beende {'es' if one else 'sie'} erst – nach "
            "jeder Runde kann über diese Version abgestimmt werden.",
        )

    seen = set(
        GameSession.objects.filter(active_map_version=version).values_list(
            "pk", flat=True
        )
    )
    seen |= set(
        MapVersionVote.objects.filter(map_version=version).values_list(
            "game_round__game_id", flat=True
        )
    )
    for game_pk, options in GameRound.objects.filter(game__in=on_map).values_list(
        "game_id", "vote_option_ids"
    ):
        if version.pk in (options or []):
            seen.add(game_pk)

    goes = goes if goes is not None else only_in(version)
    # An edge goes with its version, and so does every edge touching a node
    # that goes — the cascade does not ask which version that edge is in.
    edges = set(goes[Edge]) | set(
        Edge.objects.filter(
            Q(start_node_id__in=goes[Node]) | Q(end_node_id__in=goes[Node])
        ).values_list("pk", flat=True)
    )
    streets = set(goes[StreetEdge]) | set(
        StreetEdge.objects.filter(edge_id__in=edges).values_list("pk", flat=True)
    )
    if edges:
        seen |= set(
            RouteSegment.objects.filter(edge_id__in=edges).values_list(
                "agent_route__player_move__session_round__game_id", flat=True
            )
        )
        seen |= set(
            EdgeTrafficSnapshot.objects.filter(edge_id__in=edges).values_list(
                "simulation__game_round__game_id", flat=True
            )
        )
    if streets:
        seen |= set(
            StreetPerRound.objects.filter(edge_id__in=streets).values_list(
                "game_round__game_id", flat=True
            )
        )
    if seen:
        games = GameSession.objects.filter(pk__in=seen)
        one = len(seen) == 1
        return VersionDeleteRefused(
            "played",
            f"Diese Version kommt schon {'im Spiel' if one else 'in den Spielen'} "
            f"{_named_games(games, article=False)} vor. Mit ihr ginge dort verloren, "
            f"was gefahren und abgestimmt wurde. Lösch erst "
            f"{'das Spiel' if one else 'die Spiele'} – oder nimm die Version aus der "
            "Abstimmung (»Verträglich mit«), dann kommt sie in keinem neuen Spiel "
            "mehr vor.",
        )
    return None


def deletion_preview(version):
    """What the editor's dialog asks before a delete — nothing is written.

    `goes` is what only this version holds, `ballot` the versions it is paired
    with (those pairs go too), `keeps` the versions built on it, which keep its
    change: deleting `Busspuren` leaves `Busspuren + Buslinie` with its bus
    lanes.
    """
    from maps.models import (
        BusLine,
        BusLineEdge,
        Edge,
        Node,
        StreetEdge,
        TrainEdge,
        TrainLine,
        TrainLineEdge,
    )

    goes = only_in(version)
    refusal = deletion_refusal(version, goes)
    return {
        "version": {"id": version.pk, "name": version.name},
        "refusal": (
            {"reason": refusal.reason, "detail": refusal.detail} if refusal else None
        ),
        "goes": {
            "nodes": len(goes[Node]),
            "edges": len(goes[Edge]),
            "streets": len(goes[StreetEdge]),
            "rails": len(goes[TrainEdge]),
            "bus_lines": sorted(
                BusLine.objects.filter(pk__in=goes[BusLine]).values_list(
                    "name", flat=True
                )
            ),
            "train_lines": sorted(
                TrainLine.objects.filter(pk__in=goes[TrainLine]).values_list(
                    "name", flat=True
                )
            ),
            "line_links": len(goes[BusLineEdge]) + len(goes[TrainLineEdge]),
        },
        "ballot": list(version.compatible_versions.values_list("name", flat=True)),
        "keeps": (
            []
            if version.base_version
            else [v.name for v in versions_built_on(version) if v.pk != version.pk]
        ),
    }


def describe_goes(goes):
    """`preview["goes"]` as one German line — the admin's confirmation page."""
    parts = []
    for count, one, many in (
        (goes["nodes"], "Knoten", "Knoten"),
        (goes["edges"], "Kante", "Kanten"),
        (goes["streets"], "Straße", "Straßen"),
        (goes["rails"], "Gleis", "Gleise"),
        (goes["line_links"], "Linienabschnitt", "Linienabschnitte"),
    ):
        if count:
            parts.append(f"{count} {one if count == 1 else many}")
    for names, one, many in (
        (goes["bus_lines"], "Buslinie", "Buslinien"),
        (goes["train_lines"], "Bahnlinie", "Bahnlinien"),
    ):
        if names:
            parts.append(f"{one if len(names) == 1 else many} {german_list(names)}")
    if not parts:
        return "nur die Version selbst – alles in ihr steht auch in anderen Versionen"
    return "nur in dieser Version, geht mit: " + ", ".join(parts)


def delete_version(version):
    """Delete `version` and what only it holds, or raise `VersionDeleteRefused`.

    The one cleanup, for both doors — the editor's `DELETE` and the admin's
    delete (single and bulk). The admin used to delete the bare row and leave
    every node, edge and line that was only in it in no version: invisible in
    the editor, still in the export. A rule only one of two doors enforces is
    not a rule.

    Rows go chain rows first and nodes last, each through `.delete()`, so the
    graph cache's signals hear every one; the ballot pairs and the m2m rows go
    with the version itself. Checked again under the transaction, so a game
    that started between the dialog and the click still refuses it.
    """
    from django.db import transaction

    from maps.models import MapVersion

    with transaction.atomic():
        version = MapVersion.objects.select_for_update().get(pk=version.pk)
        goes = only_in(version)
        refusal = deletion_refusal(version, goes)
        if refusal is not None:
            raise refusal
        for model in reversed(_versioned_models()):
            model.objects.filter(pk__in=goes[model]).delete()
        version.delete()
    logger.info(
        "[maps] version %s of map %s deleted with %s rows of its own",
        version.pk,
        version.game_map_id,
        sum(len(pks) for pks in goes.values()),
    )
    return goes


def _named_games(games, article=True):
    """`das Spiel »Dienstag« (A1B2C3)`, or a list of them, five at most."""
    named = [f"»{g.game_name}« ({g.game_id})" for g in games.order_by("pk")[:6]]
    if len(named) > 5:
        rest = games.count() - 5
        named = named[:5] + [f"{rest} weitere"]
    listed = named[0] if len(named) == 1 else ", ".join(named[:-1]) + " und " + named[-1]
    if not article:
        return listed
    return ("das Spiel " if len(named) == 1 else "die Spiele ") + listed


def _versioned_models():
    from maps.models import (
        BusLine,
        BusLineEdge,
        Edge,
        Node,
        StreetEdge,
        TrainEdge,
        TrainLine,
        TrainLineEdge,
    )

    return (
        Node,
        Edge,
        StreetEdge,
        TrainEdge,
        BusLine,
        TrainLine,
        BusLineEdge,
        TrainLineEdge,
    )


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
