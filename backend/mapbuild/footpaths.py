"""Footpaths to the stop: a place the kept streets walk far from a stop the side streets reach.

The map keeps the streets from secondary up, so a place can sit a few hundred metres from a stop as
the crow flies and more than the reach from it on foot, round a block the map leaves out (Bremen's
Mitte, on the Osterdeich: 207 m to its stop, 1 827 m along the kept streets). The rule walks the
side streets OSM has (`local`: tertiary down to residential, the ones the background draws)
together with the map's walkable links. A place whose walk there reaches a stop within the reach
gets one path to the stop the walk reaches first and one back, as long as that walk: its circuity
is the walk over the straight line, like a street's. A place the side streets don't bring within
the reach stays as it is, and in the report.

A node's door is the nearest point on a side street within `SNAP`, the distance a stop snaps to a
node at; none that near, no door. A stop the place has a link to already is passed over (one link
per direction per node pair), and the walk goes on to the next.
"""

import heapq
import math

from . import download, geo, report

SNAP = 100.0  # m
STOPS = {"bus_stop", "station"}
PLACES = {"home", "workplace"}


def side_streets(area):
    """the area's side streets as `lay` takes them: [(name, [(OSM node id, (x, y))])]."""
    out = []
    for w in download.osm(area, "local"):
        if w.get("type") != "way" or not w.get("geometry"):
            continue
        ids = w.get("nodes") or [None] * len(w["geometry"])
        pts = [
            (i if i is not None else f"{w['id']}:{k}", geo.xy(p["lat"], p["lon"]))
            for k, (i, p) in enumerate(zip(ids, w["geometry"]))
        ]
        out.append((w.get("tags", {}).get("name", ""), pts))
    return out


def lay(nodes, edges, local, reach):
    """(the new path edges, the places still far: [node id]).

    nodes, edges: the map file's. local: `side_streets`. Only places a stop is within the reach of
    as the crow flies are this rule's — the others are a line's, not a path's."""
    xy = {n["id"]: (n["x"] * 1000, n["y"] * 1000) for n in nodes}
    stops = {n["id"] for n in nodes if STOPS & set(n.get("types", ()))}
    stop_pts = [xy[s] for s in sorted(stops, key=str)]
    near = report.walked(nodes, edges, stops, reach)
    far = [
        n["id"]
        for n in nodes
        if PLACES & set(n.get("types", ()))
        and n["id"] not in near
        and report.nearest(xy[n["id"]], stop_pts) <= reach
    ]
    if not far:
        return [], []
    graph = _graph(xy, edges, local)
    pairs = {(e["start_node"], e["end_node"]) for e in edges}
    laid, still_far = [], []
    for place in far:
        # One link per direction per node pair: a stop the place has a link to already (a track
        # nobody walks, a street the long way) is not one to lay a path to; the walk goes on.
        open_stops = {
            st for st in stops if (place, st) not in pairs and (st, place) not in pairs
        }
        found = _walk(graph, place, open_stops, reach)
        if found is None:
            still_far.append(place)
            continue
        stop, length, name = found
        straight = math.dist(xy[place], xy[stop])
        circuity = max(1.0, round(length / straight, 3)) if straight else 1.0
        for a, b in ((place, stop), (stop, place)):
            pairs.add((a, b))
            laid.append(
                dict(
                    name=name,
                    type="path",
                    biking=True,
                    bike_lane=False,
                    walking=True,
                    circuity=circuity,
                    start_node=a,
                    end_node=b,
                    versions=[0],
                )
            )
    return laid, still_far


def say(laid, still_far):
    """the report line."""
    paths = len({frozenset((e["start_node"], e["end_node"])) for e in laid})
    return f"Fußwege zum Halt über die Nebenstraßen: {paths} gelegt" + (
        f", {len(still_far)} Orte bleiben auch so weiter als die Reichweite (unter Achtung)"
        if still_far
        else ""
    )


def _graph(xy, edges, local):
    """{vertex: [(vertex, m, side-street name or None)]}. A map node is ("n", id), a side-street
    point ("o", OSM id): the map's links in their direction, the side streets both ways, a door
    both ways."""
    graph = {}

    def link(a, b, length, name):
        graph.setdefault(a, []).append((b, length, name))

    for e in edges:
        if e.get("walking") is False:
            continue
        a, b = e["start_node"], e["end_node"]
        link(("n", a), ("n", b), math.dist(xy[a], xy[b]) * e.get("circuity", 1.0), None)
    segs = []
    for name, pts in local:
        pts = [(str(i), p) for i, p in pts]
        for (i, p), (j, q) in zip(pts, pts[1:]):
            d = math.dist(p, q)
            link(("o", i), ("o", j), d, name)
            link(("o", j), ("o", i), d, name)
            segs.append((i, p, j, q, d, name))
    cells = {}
    for k, (_, p, _, q, _, _) in enumerate(segs):
        for cx in range(int(min(p[0], q[0]) // SNAP), int(max(p[0], q[0]) // SNAP) + 1):
            for cy in range(
                int(min(p[1], q[1]) // SNAP), int(max(p[1], q[1]) // SNAP) + 1
            ):
                cells.setdefault((cx, cy), []).append(k)
    for n, p in xy.items():
        cx, cy = int(p[0] // SNAP), int(p[1] // SNAP)
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in cells.get((cx + dx, cy + dy), ()):
                    i, a, j, b, _, _ = segs[k]
                    d = geo.point_seg(p, a, b)
                    if d <= SNAP and (best is None or (d, k) < best):
                        best = (d, k)
        if best is None:
            continue
        # The door is the nearest point on that street; from it, both ways along it.
        d, k = best
        i, a, j, b, length, name = segs[k]
        along = math.dist(a, _foot(p, a, b))
        for o, m in ((i, along), (j, length - along)):
            link(("n", n), ("o", o), d + m, name)
            link(("o", o), ("n", n), d + m, name)
    return graph


def _foot(p, a, b):
    """the point of the segment a–b nearest to p."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return a
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return (a[0] + t * dx, a[1] + t * dy)


def _walk(graph, place, stops, reach):
    """(the stop the walk from `place` reaches first, m, the side street walked longest) or None
    within the reach."""
    start = ("n", place)
    dist, prev = {start: 0.0}, {}
    heap = [(0.0, start)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        if v[0] == "n" and v[1] in stops:
            return v[1], d, _longest_street(prev, v)
        for w, length, name in graph.get(v, ()):
            nd = d + length
            if nd <= reach and nd < dist.get(w, math.inf):
                dist[w] = nd
                prev[w] = (v, length, name)
                heapq.heappush(heap, (nd, w))
    return None


def _longest_street(prev, v):
    walked = {}
    while v in prev:
        v, length, name = prev[v]
        if name:
            walked[name] = walked.get(name, 0.0) + length
    if not walked:
        return ""
    return min(walked, key=lambda name: (-walked[name], name))
