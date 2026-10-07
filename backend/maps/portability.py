"""The JSON a map travels in — the whole map, every version of it.

A map only ever moves between boxes as a file, and until S14 that file was a
snapshot of **one** version, flattened: the export picked a `MapVersion`,
filtered nodes, edges and lines to it and wrote no version information at all,
and the importer answered with exactly one `base_version`. A map with four
versions therefore exported as four files that re-imported as four separate
maps, and each move lost the other versions, `compatible_versions` — which *is*
the vote, since `_get_voteable_map_versions()` offers what the active version's
m2m reaches — `source_version`, both poll texts, `change_img`, and which element
belongs where. Measured on the live box's own map: a base-only export drops 19
edges, a whole bus line pair and all 24 `compatible_versions` pairs.

So there are two files, and the two urls already read like it:

* ``GET api/maps/<pk>/export/`` — the whole map. Carries a ``versions`` block
  and per-element membership, and is the only thing worth calling a backup.
* ``GET api/maps/<pk>/export/version/<version_pk>/`` — one version, flattened,
  the shape this project has always written. Every file in ``map_examples/``
  is one.

The rules of the format, in one place because the writer and the reader both
have to agree about them:

* **An element's ``versions`` is a list of indices into the top-level
  ``versions`` block.** Absent means *the base version* — which is exactly what
  a file without a ``versions`` block has always meant, so a legacy file is
  simply a file with one implicit base version and the importer has one code
  path. ``"versions": []`` means *no version at all*, and the two are
  deliberately different: the box has three `Bus 147` leftovers that belong
  nowhere, and a backup that quietly promoted them to the base version would be
  inventing a line the map never had.
* **A street's or a railway's own membership rides on its edge** unless it
  differs, in which case the edge carries ``street_versions`` /
  ``train_versions``. Written only when it differs, because on a 140-edge map
  with eight versions the common case would otherwise be a thousand redundant
  index lists.
* **A line's route is per version, so it is written per route, not per
  version**: ``chains`` is a list of ``{"versions": [...], "edges": [...]}``
  groups, and four versions that run the same three links produce one entry.
  A version the line belongs to but runs no link in gets ``"edges": []`` rather
  than being left out — that is the damaged state S15 recorded and S16 repairs,
  and it has to be legible in the file.
* **A flat file's ``edges`` on a line still works** and means "this route, in
  every version the line belongs to".
* **``"type": "path"`` is a link with neither a street nor a railway under
  it** — a way for bikes and pedestrians and nothing else. The map the group
  plays has twelve of them: three homes reaching the S-Bahn at Bellevue, the
  Justizministerium reaching Checkpoint Charlie, and since F11 eight through
  the Tiergarten and round Potsdamer Platz. It needs its own name because the
  export used to write such links as ``"street"`` (the ``else`` branch of a
  three-way choice) and the importer then gave each one a ``StreetEdge`` at the
  default 50 km/h and one lane — so the map could not survive its own round
  trip, and every front door gained a fast car shortcut. A legacy file saying
  ``"street"`` while stating no ``speed_limit``, ``lanes`` or
  ``dedicated_bus_lane`` means the same thing and is read the same way.

The version's own name wins over the form's. A copy imported under a new map
name keeps the base version called after the map it was drawn on, which is what
makes the round trip a fixed point: export, import, export again and the second
file says the same thing as the first.
"""

import base64
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_POLL_TEXT = "Die Karte soll ... "


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------


def ordered_versions(game_map):
    """Every version of the map, base first and then by age.

    A stable order is what makes the indices in the file mean anything, and
    putting the base first means a hand-edited file's `"versions": [0]` is the
    obvious thing. `MapVersion.Meta.ordering` sorts by descending pk for the
    admin, which would put the newest version second.
    """
    from maps.models import MapVersion

    return sorted(
        MapVersion.objects.filter(game_map=game_map),
        key=lambda version: (not version.base_version, version.pk),
    )


def build_export(game_map, version=None):
    """The file. `version=None` is the whole map, otherwise that one flattened."""
    from maps.models import BusLine, Edge, Node, StreetEdge, TrainEdge, TrainLine

    whole = version is None
    versions = ordered_versions(game_map) if whole else []
    index_of = {v.pk: i for i, v in enumerate(versions)}

    nodes = _rows(Node.objects.filter(game_map=game_map), version).prefetch_related(
        "node_type", "map_versions"
    )
    edges = list(
        _rows(Edge.objects.filter(game_map=game_map), version)
        .select_related("start_node", "end_node")
        .prefetch_related("map_versions")
    )
    edge_index = {edge.pk: idx for idx, edge in enumerate(edges)}
    edge_pks = list(edge_index)

    streets = _one_per_edge(
        _rows(StreetEdge.objects.filter(edge_id__in=edge_pks), version), "street"
    )
    trains = _one_per_edge(
        _rows(TrainEdge.objects.filter(edge_id__in=edge_pks), version), "railway"
    )

    nodes_data = []
    for node in nodes:
        entry = {
            "id": str(node.pk),
            "name": node.name,
            "x": float(node.x_position),
            "y": float(node.y_position),
        }
        types = [nt.name for nt in node.node_type.all()]
        if types:
            entry["types"] = types
        if whole:
            entry["versions"] = _indices(node.map_versions.all(), index_of)
        nodes_data.append(entry)

    edges_data = []
    for edge in edges:
        street = streets.get(edge.pk)
        train = trains.get(edge.pk)
        if street and train:
            edge_type = "both"
        elif train:
            edge_type = "train"
        elif street:
            edge_type = "street"
        else:
            edge_type = "path"

        entry = {
            "start_node": str(edge.start_node_id),
            "end_node": str(edge.end_node_id),
            "name": edge.name,
            "type": edge_type,
            "biking": edge.biking,
            "bike_lane": edge.bike_lane,
            "walking": edge.walking,
            "max_lanes": edge.max_lanes,
        }
        if street:
            entry["speed_limit"] = street.speed_limit
            entry["lanes"] = street.lanes
            entry["dedicated_bus_lane"] = street.dedicated_bus_lane
        if whole:
            own = _indices(edge.map_versions.all(), index_of)
            entry["versions"] = own
            if street:
                street_versions = _indices(street.map_versions.all(), index_of)
                if street_versions != own:
                    entry["street_versions"] = street_versions
            if train:
                train_versions = _indices(train.map_versions.all(), index_of)
                if train_versions != own:
                    entry["train_versions"] = train_versions
        edges_data.append(entry)

    export = {
        "scale": float(game_map.scale),
        "map": {
            "name": game_map.name,
            "x_dim": game_map.x_dim,
            "y_dim": game_map.y_dim,
            "max_player": game_map.max_player,
            "walk_speed_kmh": game_map.walk_speed_kmh,
            "bike_speed_kmh": game_map.bike_speed_kmh,
            "default_car_speed_kmh": game_map.default_car_speed_kmh,
            "district_commuters": game_map.district_commuters,
            "calibrated": game_map.calibrated,
        },
    }
    if whole:
        export["versions"] = [_version_entry(v, index_of) for v in versions]
    export["nodes"] = nodes_data
    export["edges"] = edges_data
    export["bus_lines"] = [
        _line_entry(line, "bus", version, versions, index_of, edge_index)
        for line in _rows(BusLine.objects.filter(game_map=game_map), version)
    ]
    export["train_lines"] = [
        _line_entry(line, "train", version, versions, index_of, edge_index)
        for line in _rows(TrainLine.objects.filter(game_map=game_map), version)
    ]

    background = _background_block(game_map)
    if background:
        export["background_image"] = background
    return export


def _rows(queryset, version):
    return queryset if version is None else queryset.filter(map_versions=version)


def _indices(versions, index_of):
    return sorted(index_of[v.pk] for v in versions if v.pk in index_of)


def _one_per_edge(queryset, what):
    """The street (or railway) of each edge, keyed by edge.

    One per edge is what every reader in the project assumes — the importer
    looks it up with `.first()`, the diff builder clones the *edge* when it
    changes the street — and the format has no way to say anything else. A
    second row would be data the file cannot carry, so it is named rather than
    dropped in silence.
    """
    found = {}
    for row in queryset.prefetch_related("map_versions"):
        if row.edge_id in found:
            logger.warning(
                "[maps] edge %s has more than one %s row (%s and %s); "
                "the export can only carry the first",
                row.edge_id,
                what,
                found[row.edge_id].pk,
                row.pk,
            )
            continue
        found[row.edge_id] = row
    return found


def _version_entry(version, index_of):
    entry = {
        "name": version.name,
        "description": version.description or "",
        "base_version": version.base_version,
        "poll_text": version.poll_text,
        "revert_poll_text": version.revert_poll_text,
        "source_version": index_of.get(version.source_version_id),
        "compatible_versions": _indices(version.compatible_versions.all(), index_of),
    }
    if version.change_img:
        block = {"filename": os.path.basename(version.change_img.name)}
        try:
            with version.change_img.open("rb") as fh:
                block["data"] = base64.b64encode(fh.read()).decode("ascii")
        except (FileNotFoundError, OSError) as exc:
            logger.warning(
                "[maps] version %s: change image %s could not be read (%s), "
                "exporting the name only",
                version.pk,
                version.change_img.name,
                exc,
            )
        entry["change_img"] = block
    return entry


def _line_entry(line, kind, version, versions, index_of, edge_index):
    from maps.versions import bus_chain_rows, train_chain_rows

    if kind == "bus":
        entry = {
            "name": line.name,
            "interval": line.intervall,
            "capacity": line.bus_capacity,
            "speed_kmh": line.bus_speed_kmh,
        }
        rows_of = bus_chain_rows
        element = "street_edge"
    else:
        entry = {
            "name": line.name,
            "interval": line.intervall,
            "capacity": line.train_capacity,
            "speed_kmh": line.train_speed_kmh,
        }
        rows_of = train_chain_rows
        element = "train_edge"

    if version is not None:
        entry["edges"] = _chain_indices(line, rows_of, element, version, edge_index)
        return entry

    own_pks = set(line.map_versions.values_list("pk", flat=True))
    own = [v for v in versions if v.pk in own_pks]
    entry["versions"] = sorted(index_of[v.pk] for v in own)
    if not own:
        logger.warning(
            "[maps] %s line %s (%s) belongs to no version — nothing plays it, "
            "and it travels with an empty version list",
            kind,
            line.name,
            line.pk,
        )
    grouped: dict = {}
    for candidate in own:
        route = tuple(_chain_indices(line, rows_of, element, candidate, edge_index))
        grouped.setdefault(route, []).append(index_of[candidate.pk])
    entry["chains"] = [
        {"versions": sorted(indices), "edges": list(route)}
        for route, indices in grouped.items()
    ]
    return entry


def _chain_indices(line, rows_of, element, version, edge_index):
    indices = []
    for row in rows_of(line, version).select_related(f"{element}__edge"):
        edge_pk = getattr(row, element).edge_id
        idx = edge_index.get(edge_pk)
        if idx is None:
            logger.warning(
                "[maps] version %s (%s) does not hold edge %s, so line %s "
                "loses that link in the export",
                version.pk,
                version.name,
                edge_pk,
                line.name,
            )
            continue
        indices.append(idx)
    return indices


def _background_block(game_map):
    if not game_map.background_image:
        return None
    block = {
        "scale": game_map.image_scale,
        "offset_x": game_map.image_offset_x,
        "offset_y": game_map.image_offset_y,
        "crop_top": game_map.image_crop_top,
        "crop_right": game_map.image_crop_right,
        "crop_bottom": game_map.image_crop_bottom,
        "crop_left": game_map.image_crop_left,
        "filename": os.path.basename(game_map.background_image.name),
    }
    try:
        with game_map.background_image.open("rb") as fh:
            block["data"] = base64.b64encode(fh.read()).decode("ascii")
    except (FileNotFoundError, OSError) as exc:
        # The placement is worth something anyway: if the image is added by
        # hand later, at least it sits in the right place.
        logger.warning(
            "[maps] map %s: background image %s could not be read (%s), "
            "exporting placement only",
            game_map.pk,
            game_map.background_image.name,
            exc,
        )
    return block


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------


STREET_FIELDS = ("speed_limit", "lanes", "dedicated_bus_lane")


def states_a_street(edge_data):
    """Whether an edge entry actually describes a street under it.

    `"type": "path"` says outright that there is none. A file written before
    that type existed says `"street"` and simply states no street field, which
    means the same thing — the alternative reading, "a street whose numbers
    were left out", is what gave the four bike-and-foot links on the shipped
    map a 50 km/h car lane on the way back in.
    """
    return any(field in edge_data for field in STREET_FIELDS)


def version_block(graph_data):
    """The file's `versions` list, or None for a flat file."""
    block = (graph_data or {}).get("versions")
    if isinstance(block, list) and block:
        return block
    return None


def base_index(block):
    """Which entry is the base version. Validation has already pinned it to one."""
    for idx, entry in enumerate(block):
        if isinstance(entry, dict) and entry.get("base_version"):
            return idx
    return 0


def version_indices(entry, count, base_idx):
    """The versions an element names.

    Base when it names none, nowhere when it says `[]`.
    """
    return element_versions(entry, "versions", [base_idx], count)


def element_versions(entry, key, fallback, count):
    """`entry[key]` as version indices, or `fallback` when the key is absent.

    What `street_versions` and `train_versions` are read with: a street belongs
    where its edge belongs unless the file says otherwise, so the fallback is
    the edge's own list rather than the base version.
    """
    raw = (entry or {}).get(key)
    if raw is None:
        return list(fallback)
    return [idx for idx in raw if isinstance(idx, int) and 0 <= idx < count]


def chain_groups(line_data, line_indices):
    """`[(version indices, edge indices)]` for one line.

    A file that says nothing about `chains` means the one route it wrote under
    `edges`, in every version the line belongs to — which is what a flat file
    has always meant and what a hand-written multi-version file should be able
    to say in one line.
    """
    chains = (line_data or {}).get("chains")
    if chains is None:
        return [(list(line_indices), list(line_data.get("edges", []) or []))]
    groups = []
    for chain in chains:
        if not isinstance(chain, dict):
            continue
        groups.append(
            (list(chain.get("versions", []) or []), list(chain.get("edges", []) or []))
        )
    return groups


def validate_versions(graph_data):
    """Everything about versioning a file can get wrong, as upload errors.

    A hand-edited file is how S16 repairs the map the group plays, so an index
    that points nowhere has to come back as a sentence on the upload page rather
    than as a map with a hole in it.
    """
    block = (graph_data or {}).get("versions")
    if block is None:
        return []
    if not isinstance(block, list) or not block:
        return ["'versions' muss eine nicht leere Liste von Versionen sein."]

    errors = []
    count = len(block)
    for idx, entry in enumerate(block):
        if not isinstance(entry, dict):
            errors.append(f"Version {idx}: muss ein Objekt sein.")
            continue
        if not str(entry.get("name", "")).strip():
            errors.append(f"Version {idx}: 'name' fehlt oder ist leer.")
        errors += _index_errors(
            entry.get("compatible_versions"),
            count,
            f"Version {idx}: compatible_versions",
        )
        source = entry.get("source_version")
        if source is not None:
            errors += _index_errors([source], count, f"Version {idx}: source_version")
    if errors:
        # Every check below indexes into the block, so a broken block first.
        return errors

    bases = [i for i, entry in enumerate(block) if entry.get("base_version")]
    if len(bases) != 1:
        errors.append(
            f"Genau eine Version braucht base_version, in der Datei sind es "
            f"{len(bases)}."
        )

    edge_count = len(graph_data.get("edges") or [])
    for label, items in (
        ("Knoten", graph_data.get("nodes") or []),
        ("Kante", graph_data.get("edges") or []),
    ):
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            errors += _index_errors(item.get("versions"), count, f"{label} {idx}")
            for key in ("street_versions", "train_versions"):
                errors += _index_errors(item.get(key), count, f"{label} {idx}: {key}")

    for label, key in (("Buslinie", "bus_lines"), ("Bahnlinie", "train_lines")):
        for idx, line in enumerate(graph_data.get(key) or []):
            if not isinstance(line, dict):
                continue
            errors += _index_errors(line.get("versions"), count, f"{label} {idx}")
            chains = line.get("chains")
            if chains is None:
                continue
            if not isinstance(chains, list):
                errors.append(f"{label} {idx}: 'chains' muss eine Liste sein.")
                continue
            for chain_idx, chain in enumerate(chains):
                where = f"{label} {idx}: Strecke {chain_idx}"
                if not isinstance(chain, dict):
                    errors.append(f"{where}: muss ein Objekt sein.")
                    continue
                errors += _index_errors(chain.get("versions"), count, where)
                for edge_idx in chain.get("edges") or []:
                    if not isinstance(edge_idx, int) or not (
                        0 <= edge_idx < edge_count
                    ):
                        errors.append(
                            f"{where}: Kante {edge_idx} gibt es nicht "
                            f"(die Datei hat {edge_count} Kanten)."
                        )
    return errors


def _index_errors(raw, count, where):
    if raw is None:
        return []
    if not isinstance(raw, list):
        return [f"{where}: muss eine Liste von Versionsnummern sein."]
    out = []
    for value in raw:
        if not isinstance(value, int) or not (0 <= value < count):
            out.append(
                f"{where}: Version {value} gibt es nicht "
                f"(die Datei hat {count} Versionen)."
            )
    return out
