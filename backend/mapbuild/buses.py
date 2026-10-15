"""Buses and trams onto the map: their real route, on the kept streets and off them.

Each relation's route is chained from its ways and cut into pieces of at most `PIECE`; a piece is
on a kept street link when its middle lies within `NEAR` of one, and it stays on the link it was
on while that link is still within `NEAR` (no flicker at junctions). The links a run of pieces
rides are the line's chain on the kept streets; a run of pieces on none is a stretch off them.

- an on-street stop is one per name and link (both directions, every line; at the mean of their
  places along the link); an off-street stop is one per name within 400 m.
- one node set per kept link: its two ends, then every stop of both modes, then every stretch's
  ends; a point within `SNAP` of a node along the road is that node, else the link is split there.
"""

import bisect
import collections
import math
import statistics

from . import geo, rail

NEAR = 40.0  # m: a piece of route this close to a kept street rides it
PIECE = 25.0  # m
CELL = 100.0  # m: the grid the kept streets are looked up in
SNAP = 100.0  # m along the road: a stop or a stretch's end this close to a node is that node
OFF_TRACK = 150.0  # m: a stop further than this from its own route is not on it


def poly_cum(pts):
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    return cum


def on_poly(pts, cum, p):
    """(distance, arc) of the point of the polyline nearest p."""
    best = (math.inf, 0.0)
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = dx * dx + dy * dy
        t = (
            0
            if L == 0
            else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
        )
        d = math.dist(p, (a[0] + t * dx, a[1] + t * dy))
        if d < best[0]:
            best = (d, cum[i] + t * math.sqrt(L))
    return best


def load_links(graph, shapes):
    """the kept street links with their shapes and ids: [{u, v, pts, cum, L (road length), fwd,
    bwd, name, walk}] — a shape whose ends are not both nodes of the map (the strongly connected
    part dropped one) is left out."""
    at = {
        (round(n["x"] * 1000, 1), round(n["y"] * 1000, 1)): n["id"]
        for n in graph["nodes"]
    }
    pos = {n["id"]: (n["x"] * 1000, n["y"] * 1000) for n in graph["nodes"]}
    edge = {(e["start_node"], e["end_node"]): e for e in graph["edges"]}
    links = []
    for l in shapes:
        u = at.get((round(l["u"][0], 1), round(l["u"][1], 1)))
        v = at.get((round(l["v"][0], 1), round(l["v"][1], 1)))
        e = edge.get((u, v)) or edge.get((v, u))
        if u is None or v is None or e is None:
            continue
        pts = [tuple(p) for p in l["pts"]]
        cum = poly_cum(pts)
        if cum[-1] == 0:
            pts, cum = [pos[u], pos[v]], poly_cum([pos[u], pos[v]])
        L = math.dist(pos[u], pos[v]) * e.get("circuity", 1)
        links.append(
            dict(
                u=u,
                v=v,
                pts=pts,
                cum=cum,
                L=L,
                fwd=(u, v) in edge,
                bwd=(v, u) in edge,
                name=l["name"],
                walk=e.get("walking", True),
            )
        )
    return links


def link_grid(links):
    g = collections.defaultdict(list)
    for li, l in enumerate(links):
        pts = l["pts"]
        for si, (a, b) in enumerate(zip(pts, pts[1:])):
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            for i in range(int((x0 - NEAR) // CELL), int((x1 + NEAR) // CELL) + 1):
                for j in range(int((y0 - NEAR) // CELL), int((y1 + NEAR) // CELL) + 1):
                    g[i, j].append((li, si))
    return g


def piece_at(runs, s):
    for run in runs:
        if run and run[0][0] <= s <= run[-1][1]:
            k = bisect.bisect_right([x[0] for x in run], s) - 1
            return run, max(0, k)
    return None, None


def walk_route(rel, ways, inside, links, grid, osm_nodes):
    """a relation's route in pieces: (runs, stops, line, cum). A run is the pieces inside the area
    in a row, a piece (arc from, arc to, middle, kept link or None, direction on it, segment of
    the line); a stop (name, point, arc, distance from the route)."""
    line, _ = rail.polyline(rel, ways)
    if len(line) < 2:
        return [], [], [], []
    cum = poly_cum([p for _, p in line])
    seq = rail.stop_seq(rel, osm_nodes, inside)
    if len(seq) >= 2:
        first, last = rail.project(line, cum, seq[0][1]), rail.project(
            line, cum, seq[-1][1]
        )
        if first[1] > last[1]:
            line = line[::-1]
            cum = [cum[-1] - c for c in cum[::-1]]
    runs, cur, prev = [], [], None
    for i, ((_, a), (_, b)) in enumerate(zip(line, line[1:])):
        if not (inside(a) and inside(b)):
            if cur:
                runs.append(cur)
                cur = []
            prev = None
            continue
        L = math.dist(a, b)
        n = max(1, math.ceil(L / PIECE))
        for k in range(n):
            m = (
                a[0] + (b[0] - a[0]) * (k + 0.5) / n,
                a[1] + (b[1] - a[1]) * (k + 0.5) / n,
            )
            best = {}
            for li, si in grid.get((int(m[0] // CELL), int(m[1] // CELL)), ()):
                pa, pb = links[li]["pts"][si], links[li]["pts"][si + 1]
                d = geo.point_seg(m, pa, pb)
                if d <= NEAR and d < best.get(li, (math.inf,))[0]:
                    best[li] = (d, si)
            signs = {}
            for x, (_, si) in best.items():
                pa, pb = links[x]["pts"][si], links[x]["pts"][si + 1]
                signs[x] = (
                    1
                    if (b[0] - a[0]) * (pb[0] - pa[0]) + (b[1] - a[1]) * (pb[1] - pa[1])
                    >= 0
                    else -1
                )
            # a link it may ride that way first, then the one it was on, then the nearest
            li = min(
                best,
                key=lambda x: (
                    not (links[x]["fwd"] if signs[x] > 0 else links[x]["bwd"]),
                    x != prev,
                    best[x][0],
                ),
                default=None,
            )
            cur.append(
                (
                    cum[i] + L * k / n,
                    cum[i] + L * (k + 1) / n,
                    m,
                    li,
                    signs.get(li, 0),
                    i,
                )
            )
            prev = li
    if cur:
        runs.append(cur)
    out, start = [], 0
    for name, p, ins in seq:
        if not ins:
            continue
        d, s, start = rail.project(line, cum, p, start)
        out.append((name, p, s, d))
    return runs, out, line, cum


def point(links, piece):
    """where on its kept link a piece lies: (link, m along the road from u)."""
    l = links[piece[3]]
    _, t = on_poly(l["pts"], l["cum"], piece[2])
    return piece[3], t * l["L"] / l["cum"][-1]


def collect(mode, kept, data, links, grid, inside, osm_nodes):
    """per relation its runs; the on-street stops (name, link) -> (m along it, lines); the
    stretches off the kept streets."""
    lines, ways = data["lines"], data["ways"]
    per_rel = []
    for key in (k for k in kept if k[0] == mode):
        for r in lines[key]:
            runs, st, line, cum = walk_route(r, ways, inside, links, grid, osm_nodes)
            if runs:
                per_rel.append(
                    dict(key=key, rid=r["id"], runs=runs, st=st, line=line, cum=cum)
                )
    on_id = collections.defaultdict(list)
    off_at = {}  # (rid, stop idx) -> (name, p, s)
    for R in per_rel:
        for idx, (name, p, s, d) in enumerate(R["st"]):
            if d > OFF_TRACK:
                continue
            run, k = piece_at(R["runs"], s)
            if run is None:
                continue
            li = run[k][3]
            if li is not None:
                l = links[li]
                _, t = on_poly(l["pts"], l["cum"], p)
                on_id[(name, li)].append((t * l["L"] / l["cum"][-1], R["key"]))
            else:
                off_at[(R["rid"], idx)] = (name, p, s)
    on_stop = {
        k: (statistics.fmean(t for t, _ in v), {key for _, key in v})
        for k, v in on_id.items()
    }
    # off-street stops: one per name within 400 m
    clusters = collections.defaultdict(list)
    off_id = {}
    for (rid, idx), (name, p, s) in sorted(off_at.items()):
        cs = clusters[name]
        i = next((i for i, c in enumerate(cs) if math.dist(c, p) < rail.APART), None)
        if i is None:
            cs.append(p)
            i = len(cs) - 1
        off_id[(rid, idx)] = (name, i)
    stretches = []
    for R in per_rel:
        line, cum = R["line"], R["cum"]
        for run in R["runs"]:
            k = 0
            while k < len(run):
                if run[k][3] is not None:
                    k += 1
                    continue
                j = k
                while j < len(run) and run[j][3] is None:
                    j += 1
                s0, s1 = run[k][0], run[j - 1][1]
                i0, i1 = run[k][5], run[j - 1][5]
                path = [line[x][0] for x in range(i0, i1 + 2)]
                arcs = [cum[x] for x in range(i0, i1 + 2)]
                pts = [line[x][1] for x in range(i0, i1 + 2)]
                offs = []
                for idx, (name, p, s, d) in enumerate(R["st"]):
                    if (R["rid"], idx) in off_at and s0 <= s <= s1:
                        x = min(range(len(arcs)), key=lambda x: abs(arcs[x] - s))
                        offs.append(dict(name=name, sid=off_id[(R["rid"], idx)], at=x))
                stretches.append(
                    dict(
                        key=R["key"],
                        rid=R["rid"],
                        L=s1 - s0,
                        s0=s0,
                        s1=s1,
                        path=path,
                        arcs=arcs,
                        pts=pts,
                        offs=offs,
                        leave=point(links, run[k - 1]) if k > 0 else None,
                        rejoin=point(links, run[j]) if j < len(run) else None,
                    )
                )
                k = j
    return dict(on_stop=on_stop, stretches=stretches, per_rel=per_rel, off_id=off_id)


class KeptNodes:
    """one node set per kept link: its two ends, then every split; a point within SNAP of a node
    along the road is that node."""

    def __init__(self, links):
        self.links, self.at, self.split = links, {}, collections.Counter()

    def node(self, li, t, why):
        l = self.links[li]
        xs = self.at.setdefault(li, [(0.0, l["u"]), (l["L"], l["v"])])
        tt, n = min(xs, key=lambda x: abs(t - x[0]))
        if abs(t - tt) <= SNAP:
            return n
        n = ("split", li, round(t))
        xs.append((t, n))
        self.split[why] += 1
        return n
