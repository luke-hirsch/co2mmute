"""Rail lines (U, S, regional) onto the map: their stations and the hops between them.

- a station: one name within 400 m, U and S together. Within `SNAP` of a node it is that node,
  else its own node and a path edge to the nearest node.
- a hop: two consecutive stations of a relation inside the area (a stop outside breaks the run),
  one link per direction on its node pair. Its length is the track between the points of it
  nearest the two placed nodes, each looked for within 400 m of track of its own stop (a ring
  closes on itself), so the circuity is the track's over the straight line.
"""

import collections
import math
import statistics

from . import geo, lines as L

SNAP = 100.0  # m: a station this close to a node is that node
APART = 400.0  # m: stops of one name closer than this are one station


def stations(kept, lines, stops_of):
    """(group, name, i) -> {"p": centre, "lines": {...}}."""
    out = {}
    clusters = collections.defaultdict(list)  # (group, name) -> [{"pts", "lines"}]
    for key in kept:
        group = "rail" if key[0] in L.RAIL else key[0]
        for r in lines[key]:
            for name, p in stops_of[r["id"]]:
                cs = clusters[(group, name)]
                for c in cs:
                    if math.dist(c["pts"][0], p) < APART:
                        c["pts"].append(p)
                        c["lines"].add(key)
                        break
                else:
                    cs.append({"pts": [p], "lines": {key}})
    for (group, name), cs in clusters.items():
        for i, c in enumerate(cs):
            x = statistics.fmean(q[0] for q in c["pts"])
            y = statistics.fmean(q[1] for q in c["pts"])
            out[(group, name, i)] = {"p": (x, y), "lines": c["lines"]}
    return out


def polyline(rel, ways):
    """the relation's track: [(node id, (x, y))], its ways in member order, each turned to meet
    the last; and the gaps where the next way meets neither end."""
    parts = []
    for m in rel["members"]:
        if (
            m["type"] == "way"
            and m["role"] in ("", "forward", "backward")
            and m["ref"] in ways
        ):
            w = ways[m["ref"]]
            if "nodes" in w and len(w["nodes"]) == len(w["geometry"]) >= 2:
                parts.append(
                    list(
                        zip(
                            w["nodes"],
                            (geo.xy(g["lat"], g["lon"]) for g in w["geometry"]),
                        )
                    )
                )
    if not parts:
        return [], 0
    line = list(parts[0])
    if len(parts) > 1:
        ends = {parts[1][0][0], parts[1][-1][0]}
        if line[-1][0] not in ends and line[0][0] in ends:
            line.reverse()
    gaps = 0
    for s in parts[1:]:
        if s[0][0] == line[-1][0]:
            line += s[1:]
        elif s[-1][0] == line[-1][0]:
            line += s[::-1][1:]
        else:
            gaps += 1
            if math.dist(s[-1][1], line[-1][1]) < math.dist(s[0][1], line[-1][1]):
                s = s[::-1]
            line += s
    return line, gaps


def project(line, cum, p, start=0):
    """(distance, arc length, segment) of the point of line[start:] nearest p."""
    best = (math.inf, 0.0, start)
    for i in range(start, len(line) - 1):
        a, b = line[i][1], line[i + 1][1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = (
            0
            if L2 == 0
            else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        )
        d = math.dist(p, (a[0] + t * dx, a[1] + t * dy))
        if d < best[0]:
            best = (d, cum[i] + t * math.sqrt(L2), i)
    return best


def near_arc(line, cum, p, s0, window=APART):
    """arc length of the point nearest p on the stretch of track within `window` of arc s0."""
    lo = (
        next(i for i in range(len(cum)) if cum[i] >= s0 - window)
        if cum[-1] >= s0 - window
        else 0
    )
    best = (math.inf, s0)
    for i in range(max(0, lo - 1), len(line) - 1):
        if cum[i] > s0 + window:
            break
        a, b = line[i][1], line[i + 1][1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = (
            0
            if L2 == 0
            else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        )
        d = math.dist(p, (a[0] + t * dx, a[1] + t * dy))
        if d < best[0]:
            best = (d, cum[i] + t * math.sqrt(L2))
    return best[1]


def stop_seq(rel, nodes, inside):
    """the relation's stops in order: (name, (x, y), inside)."""
    roles = (
        L.STOP_ROLES
        if any(
            m["role"] in L.STOP_ROLES and m["type"] == "node" for m in rel["members"]
        )
        else L.PLATFORM_ROLES
    )
    out = []
    for m in rel["members"]:
        if m["type"] == "node" and m["role"] in roles and m["ref"] in nodes:
            n = nodes[m["ref"]]
            p = geo.xy(n["lat"], n["lon"])
            out.append((n.get("tags", {}).get("name", "?"), p, inside(p)))
    return out


def build(data, kept):
    """the stations and every relation's hops between them, the hops grouped by node pair.
    seqs: per relation its runs of placed stations in order [(line, rid, [station, …])].
    """
    inside = data["inside"]
    osm_nodes = data["nodes"]  # OSM's, and the timetable's stand-ins
    graph, ways, lines = data["graph"], data["ways"], data["lines"]
    rail_kept = [k for k in kept if k[0] in L.RAIL]
    st = stations(rail_kept, lines, data["stops_of"])
    pos = {n["id"]: (n["x"] * 1000, n["y"] * 1000) for n in graph["nodes"]}
    gnodes = list(pos.items())

    placed, path_to = {}, {}
    for k, s in st.items():
        nid, p = min(gnodes, key=lambda kv: math.dist(s["p"], kv[1]))
        if math.dist(s["p"], p) <= SNAP:
            placed[k] = nid
        else:
            placed[k] = ("own", k)
            path_to[("own", k)] = nid
    at = lambda n: pos[n] if not isinstance(n, tuple) else st[n[1]]["p"]

    def station_of(name, p):
        cands = [k for k in st if k[0] == "rail" and k[1] == name]
        k = min(cands, key=lambda k: math.dist(st[k]["p"], p), default=None)
        return k if k is not None and math.dist(st[k]["p"], p) < APART else None

    hops = (
        []
    )  # (line, a, b, track m or None, track between the placed nodes' projections)
    seqs = []
    for key in rail_kept:
        for r in lines[key]:
            runs = [[]]
            line, _ = polyline(r, ways)
            cum = [0.0]
            for (_, a), (_, b) in zip(line, line[1:]):
                cum.append(cum[-1] + math.dist(a, b))
            seq = stop_seq(r, osm_nodes, inside)
            if len(line) >= 2 and len(seq) >= 2:
                first, last = project(line, cum, seq[0][1]), project(
                    line, cum, seq[-1][1]
                )
                if first[1] > last[1]:
                    line = line[::-1]
                    cum = [cum[-1] - c for c in cum[::-1]]
            prev, start = None, 0
            for name, p, ins in seq:
                if len(line) >= 2:
                    d, s, start = project(line, cum, p, start)
                else:
                    s = None
                k = station_of(name, p) if ins else None
                if k is None:
                    prev = None
                    if runs[-1]:
                        runs.append([])
                    continue
                if not runs[-1] or runs[-1][-1] != k:
                    runs[-1].append(k)
                if prev is not None and prev[0] != k:
                    track = (
                        s - prev[1]
                        if s is not None and prev[1] is not None and s > prev[1]
                        else None
                    )
                    snapped = None
                    if track:
                        sa = near_arc(line, cum, at(placed[prev[0]]), prev[1])
                        sb = near_arc(line, cum, at(placed[k]), s)
                        snapped = sb - sa if sb > sa else None
                    hops.append((key, prev[0], k, track, snapped))
                if prev is None or prev[0] != k:
                    prev = (k, s, start)
            seqs += [(key, r["id"], run) for run in runs if len(run) >= 2]

    # one link per direction per node pair: the hops grouped by their placed pair
    pairs = collections.defaultdict(list)
    for key, a, b, track, snapped in hops:
        na, nb = placed[a], placed[b]
        if na == nb:
            continue
        pairs[frozenset((na, nb))].append((key, (na, nb), a, b, track, snapped))
    return dict(st=st, placed=placed, path_to=path_to, pairs=pairs, seqs=seqs)
