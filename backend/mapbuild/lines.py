"""Which public transport lines a map carries.

A line is a mode and a ref, every OSM route relation of it together; a relation counts when two
of its stops lie in the area. Night and long-distance lines are left out.

- cover: lines by what the places need — rail (U, S, regional) first, then tram, then bus. A line
  goes on only when it brings a home or workplace within `REACH` of a stop that had none, the line
  that brings the most new places first. OSM's lines first, then the timetable's where OSM has none
  (`timetable.add_stand_ins`).
- one route per direction: a line's longest relation (most stops in the area) is one direction;
  another goes with it when the stops it shares come in the other order. A loop or a one-way ring
  has one.
- a kept line takes its way back along also where OSM files it under another ref — the same stops
  the other way round, the S42 to the S41.
"""

import collections
import math
import re

from . import download, geo, timetable

REACH = 1000  # m from a stop: a place this close is served
STOP_ROLES = ("stop", "stop_entry_only", "stop_exit_only")
PLATFORM_ROLES = ("platform", "platform_entry_only", "platform_exit_only")
RAIL = {"U-Bahn", "S-Bahn (light_rail)", "train: regional / S"}
LEFT_OUT = ("train: long distance", "night")


def mode(tags):
    r = tags.get("route")
    if tags.get("by_night") in ("yes", "only") or re.match(r"N\d", tags.get("ref", "")):
        return "night"
    if r == "train":
        s = tags.get("service", "")
        if s in ("long_distance", "high_speed", "night", "tourism") or re.match(
            r"(ICE|IC|EC|FLX|NJ)\b", tags.get("ref", "")
        ):
            return "train: long distance"
        return "train: regional / S"
    if r == "light_rail":
        return "S-Bahn (light_rail)"
    if r == "trolleybus":
        return "bus"
    return {"subway": "U-Bahn", "tram": "tram", "bus": "bus"}.get(r, r)


def minutes(v):
    """OSM's interval: "10", "00:10", "01:00", "5-10" (the shorter)."""
    v = v.split(";")[0].split("-")[0].strip()
    parts = [int(x) for x in v.split(":") if x.strip().isdigit()]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else parts[0] * 60 + parts[1]


def collect(area, graph, extract):
    """the area's lines, their stops, and the timetable's stand-ins where OSM has none."""
    inside = area.inside()
    rels = download.osm(area, "pt_routes")
    nodes = {n["id"]: n for n in download.osm(area, "pt_nodes") if n["type"] == "node"}
    places = {
        kind: [
            (n["x"] * 1000, n["y"] * 1000) for n in graph["nodes"] if kind in n["types"]
        ]
        for kind in ("home", "workplace")
    }
    lines = collections.defaultdict(list)  # (mode, ref) -> relations
    stops_of = {}
    for r in rels:
        t = r["tags"]
        roles = (
            STOP_ROLES
            if any(
                m["role"] in STOP_ROLES and m["type"] == "node" for m in r["members"]
            )
            else PLATFORM_ROLES
        )
        seq = []
        for m in r["members"]:
            if m["type"] != "node" or m["role"] not in roles or m["ref"] not in nodes:
                continue
            n = nodes[m["ref"]]
            p = geo.xy(n["lat"], n["lon"])
            if inside(p):
                seq.append((n.get("tags", {}).get("name", "?"), p))
        if len(seq) < 2:
            continue
        key = (mode(t), t.get("ref") or t.get("name", "?"))
        lines[key].append(r)
        stops_of[r["id"]] = seq
    ways = {w["id"]: w for w in download.osm(area, "pt_ways") if w["type"] == "way"}
    tt_keys, tt_report = timetable.add_stand_ins(
        area, extract, lines, stops_of, ways, nodes, places, inside
    )
    for k in list(lines):
        lines[k] = routes(lines[k], stops_of)
    return dict(
        lines=lines,
        stops_of=stops_of,
        places=places,
        graph=graph,
        ways=ways,
        inside=inside,
        nodes=nodes,
        timetable_lines=tt_keys,
        timetable_report=tt_report,
    )


def routes(rs, stops_of):
    """a line's routes on the map: one per direction, its longest variant."""
    seqs = {r["id"]: stops_of[r["id"]] for r in rs}
    a = max(rs, key=lambda r: len(seqs[r["id"]]))
    order = {}
    for i, (name, _) in enumerate(seqs[a["id"]]):
        order.setdefault(name, i)
    back = []
    for r in rs:
        if r is a:
            continue
        idx = [order[name] for name, _ in seqs[r["id"]] if name in order]
        up = sum(y > x for x, y in zip(idx, idx[1:]))
        down = sum(y < x for x, y in zip(idx, idx[1:]))
        if down > up:
            back.append(r)
    return [a] + ([max(back, key=lambda r: len(seqs[r["id"]]))] if back else [])


def way_back(lines, stops_of):
    """a line with one route whose way back OSM files as another line of its mode: the same stops
    the other way round."""
    one = {
        k: [n for n, _ in stops_of[rs[0]["id"]]]
        for k, rs in lines.items()
        if len(rs) == 1
    }
    back = {}
    for k, a in one.items():
        order = {}
        for i, n in enumerate(a):
            order.setdefault(n, i)
        for j, b in one.items():
            if j == k or j[0] != k[0] or set(b) != set(a):
                continue
            idx = [order[n] for n in b]
            if sum(y < x for x, y in zip(idx, idx[1:])) > sum(
                y > x for x, y in zip(idx, idx[1:])
            ):
                back[k] = j
                break
    return back


def cover(lines, stops_of, places, reach=REACH):
    """the lines a map carries, in the order they were taken."""
    pts = places["home"] + places["workplace"]
    serves = {}
    for k, rs in lines.items():
        if k[0] in LEFT_OUT:
            continue
        st = [p for r in rs for _, p in stops_of[r["id"]]]
        serves[k] = {
            i for i, q in enumerate(pts) if any(math.dist(q, p) <= reach for p in st)
        }
    tiers = [RAIL, {"tram"}, {"bus"}]
    from_tt = {k for k in serves if lines[k][0]["tags"].get("source") == "timetable"}
    back = way_back(lines, stops_of)
    kept, done = [], set()
    for stand_in in (False, True):
        for tier in tiers:
            while True:
                best = max(
                    (
                        k
                        for k in serves
                        if k[0] in tier and k not in kept and (k in from_tt) == stand_in
                    ),
                    key=lambda k: len(serves[k] - done),
                    default=None,
                )
                if best is None or not serves[best] - done:
                    break
                kept.append(best)
                done |= serves[best]
                if back.get(best) in serves and back[best] not in kept:
                    kept.append(back[best])
                    done |= serves[back[best]]
    return kept
