"""Public transport onto the map: the lines that cover the places, with their stops and edges.

- lines (`lines.cover`): rail → tram → bus at 1 km; OSM's, else the timetable's; one route per
  direction, its longest variant; its whole length in the area.
- rail (`rail.build`): a station within 100 m of a node is that node, else its own node and a path
  edge to the nearest node. A hop is its own `train` edge, its circuity the track's; a pair two
  lines share is one edge at the longest track; a hop on a kept street's pair makes that street
  `both`; a hop on a station's path walks and bikes.
- buses and trams (`buses`): their real route. On the kept streets the street's own edges (a tram
  makes them `both`: rails beside the street, free); a stop or a stretch's end within 100 m of a
  node is that node, else the street is split there. Off the kept streets a chain per stretch, a
  hop from stop to stop its own edge (a bus a bus-only street link, a tram a `train` edge), the
  route's length; a loop back with no stop is dropped; against a one-way street its own edge that
  way; a second edge on one node pair gets a node in its middle. A step between two kept links
  that share no node is bridged over at most `BRIDGE` of street, else it is the line's own link
  along its route. A route that leaves the area and comes back is joined over the stretch outside.
- intervals (`timetable.rule`): the timetable's, else OSM's, else the mode's default.
- a bus-only link walks and bikes both ways (the way no bus rides it is a path); so does every
  walkable link with no way back (a one-way street), where the way back is not a link nobody walks.
  Seats and speed are the kind's defaults (`BusLine`, `TrainLine.DEFAULTS`). A bus-only link's speed
  limit is read by nothing (closed to cars; a bus runs at its line's speed), so 50.
"""

import collections
import heapq
import math

from . import buses, rail, report, timetable
from .lines import RAIL, REACH, collect, cover

BRIDGE = (
    200.0  # m of street: a longer way round between two kept links is not the route
)
BUS = {"capacity": 85, "speed_kmh": 30}  # BusLine's defaults (maps/models.py)
TRAIN = {
    "train": {"capacity": 1000, "speed_kmh": 40},
    "tram": {"capacity": 248, "speed_kmh": 30},
}  # TrainLine.DEFAULTS
STREET_COPY = (
    "name",
    "biking",
    "bike_lane",
    "walking",
    "max_lanes",
    "speed_limit",
    "lanes",
    "dedicated_bus_lane",
    "junction",
)


def along(pts, cum, s):
    """the point at arc s along a polyline."""
    if s <= 0:
        return pts[0]
    for i in range(len(cum) - 1):
        if cum[i + 1] >= s:
            seg = cum[i + 1] - cum[i]
            f = 0 if seg == 0 else (s - cum[i]) / seg
            a, b = pts[i], pts[i + 1]
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
    return pts[-1]


def add(area, graph, shapes, extract):
    """the map file `graph` with its public transport: (map file data, report lines, heads-up
    lines). shapes: `mapfile.street_shapes`; extract: `timetable.of_area` (None: no timetable).
    """
    data = collect(area, graph, extract)
    kept = cover(data["lines"], data["stops_of"], data["places"], REACH)
    R = rail.build(data, kept)
    found = timetable.match(extract, data, kept)
    ruled = timetable.rule(extract, data, kept, found)
    inside = data["inside"]
    lines = data["lines"]
    say, heads_up = [], []

    pos = {n["id"]: (n["x"] * 1000, n["y"] * 1000) for n in graph["nodes"]}
    name_of = {n["id"]: n["name"] for n in graph["nodes"]}
    types = {n["id"]: set(n["types"]) for n in graph["nodes"]}
    sedge = {(e["start_node"], e["end_node"]): e for e in graph["edges"]}
    links = buses.load_links(graph, shapes)
    grid = buses.link_grid(links)
    on_links = {frozenset((l["u"], l["v"])) for l in links}

    # ---- buses and trams: one node set per kept link (stops of both modes, then every stretch's ends)
    got = {
        mode: buses.collect(mode, kept, data, links, grid, inside, data["nodes"])
        for mode in ("bus", "tram")
    }
    kn = buses.KeptNodes(links)
    stop_node = {}
    for mode in got:
        for (name, li), (t, _) in sorted(
            got[mode]["on_stop"].items(), key=lambda kv: (kv[0][1], kv[1][0], kv[0][0])
        ):
            stop_node[mode, name, li] = kn.node(li, t, f"{mode} stop")
    ends = {}
    for mode in got:
        for s in got[mode]["stretches"]:
            for end in ("leave", "rejoin"):
                if s[end]:
                    ends[id(s), end] = kn.node(*s[end], f"{mode} end")
    # the split nodes' places on their links
    on_link = {}  # li -> [(t, node)] sorted
    for li, l in enumerate(links):
        xs = sorted(
            kn.at.get(li, [(0.0, l["u"]), (l["L"], l["v"])]), key=lambda x: x[0]
        )
        on_link[li] = xs
        for t, n in xs:
            if n not in pos:
                pos[n] = along(
                    l["pts"], l["cum"], t * l["cum"][-1] / l["L"] if l["L"] else 0
                )
                types[n] = {"intersection"}
    sub = {}  # (a, b) consecutive on a kept link -> (li, road m, along u→v)
    for li, xs in on_link.items():
        for (ta, a), (tb, b) in zip(xs, xs[1:]):
            sub[a, b] = (li, tb - ta, True)
            sub[b, a] = (li, tb - ta, False)
    split_links = {li for li, xs in on_link.items() if len(xs) > 2}

    # off-street stops: a node each, at the mean of where its routes pass it
    off_pts = collections.defaultdict(list)
    for mode in got:
        for s in got[mode]["stretches"]:
            for o in s["offs"]:
                off_pts[("off", mode) + o["sid"]].append(s["pts"][o["at"]])
    for n, ps in off_pts.items():
        pos[n] = (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))
        name_of[n] = n[2]
        types[n] = {"bus_stop"}

    # ---- the edges the lines need, one per directed node pair
    edges = {}  # (a, b) -> dict(kind="street"|"bus"|"train"|"path", ...)
    mids = 0

    def straight(a, b):
        return math.dist(pos[a], pos[b])

    def circ(length, a, b):
        d = straight(a, b)
        return max(1.0, round(length / d, 3)) if d > 0 and length else 1.0

    def mid_node(a, b, pts, arcs, s_a, s_b, tag):
        nonlocal mids
        m = ("mid", a, b, tag)
        if m not in pos:
            pos[m] = along(pts, [x - arcs[0] for x in arcs], (s_a + s_b) / 2 - arcs[0])
            name_of[m] = ""
            types[m] = {"intersection"}
            mids += 1
        return m

    def own_edge(a, b, kind, length, route=None):
        """a line's own edge a→b (bus-only street link or rails); a pair already taken by another
        kind gets a node in the middle; returns the node list the line runs."""
        cur = edges.get((a, b))
        taken = (a, b) in street_dirs or (cur is not None and cur["kind"] != kind)
        if not taken:
            if cur is None:
                edges[a, b] = dict(kind=kind, length=length)
            else:
                cur["length"] = max(cur["length"], length)
            return [a, b]
        pts, arcs, s_a, s_b = (
            route
            if route
            else ([pos[a], pos[b]], [0.0, straight(a, b)], 0.0, straight(a, b))
        )
        m = mid_node(a, b, pts, arcs, s_a, s_b, kind)
        return own_edge(a, m, kind, length / 2)[:-1] + own_edge(m, b, kind, length / 2)

    # the street's directed sub-links after the splits
    street_dirs = set()
    for (a, b), (li, L, uv) in sub.items():
        l = links[li]
        if (l["u"], l["v"]) in sedge if uv else (l["v"], l["u"]) in sedge:
            street_dirs.add((a, b))
    rails_on_street = set()  # directed street pairs a tram or a train runs on (`both`)
    walk_rail = set()  # directed path pairs a rail hop runs on

    # ---- buses and trams, per route
    def chain_of(mode, Rr):
        """the node sequence a relation runs, first stop to last, and its own hops."""
        stretch_at = {
            round(s["s0"], 3): s
            for s in got[mode]["stretches"]
            if s["rid"] == Rr["rid"]
        }
        stops_in = []
        for idx, (name, p, s, d) in enumerate(Rr["st"]):
            if d > 150:
                continue
            run, k = buses.piece_at(Rr["runs"], s)
            if run is None:
                continue
            li = run[k][3]
            if li is not None:
                n = stop_node.get((mode, name, li))
            else:
                sid = got[mode]["off_id"].get((Rr["rid"], idx))
                n = ("off", mode) + sid if sid else None
            if n is not None:
                stops_in.append((n, s))
        pieces = []  # per run inside the area: (seq, hops, its stops, arc in, arc out)
        all_stops = stops_in
        for run in Rr["runs"]:
            stops_in = []
            for n, s in all_stops:  # this run's stops, in order
                if run[0][0] <= s <= run[-1][1] and (not stops_in or stops_in[-1] != n):
                    stops_in.append(n)
            legs = []
            for piece in run:
                li = piece[3]
                if legs and legs[-1][0] == li:
                    legs[-1][2] = piece
                else:
                    legs.append([li, piece, piece])
            seq, hops = [], {}

            def push(n, hop=None):
                if not seq or seq[-1] != n:
                    if seq and hop:
                        hops[seq[-1], n] = hop
                    seq.append(n)

            for j, (li, first, last) in enumerate(legs):
                if li is None:
                    s = stretch_at.get(round(first[0], 3))
                    if s is None:
                        continue
                    chain = []
                    if s["leave"]:
                        chain.append((ends[id(s), "leave"], s["s0"]))
                    seen = []
                    for o in s["offs"]:
                        n = ("off", mode) + o["sid"]
                        if n not in seen:
                            seen.append(n)
                            chain.append((n, s["arcs"][o["at"]]))
                    if s["rejoin"]:
                        chain.append((ends[id(s), "rejoin"], s["s1"]))
                    if len(chain) == 2 and chain[0][0] == chain[1][0]:
                        continue  # a loop back with no stop: the line rides on
                    for (a, sa), (b, sb) in zip(chain, chain[1:]):
                        push(a)
                        push(b, hop=("off", s, sa, sb))
                    continue
                xs = on_link[li]
                ids = [n for _, n in xs]
                prev = legs[j - 1] if j > 0 else None
                nxt = legs[j + 1] if j + 1 < len(legs) else None

                def nearest(t):
                    return min(xs, key=lambda x: abs(x[0] - t))[1]

                if seq and seq[-1] in ids:
                    entry = seq[-1]
                elif prev is not None and prev[0] is not None:
                    shared = sorted(
                        {links[prev[0]]["u"], links[prev[0]]["v"]}
                        & {links[li]["u"], links[li]["v"]}
                    )
                    entry = (
                        shared[0] if shared else nearest(buses.point(links, first)[1])
                    )
                else:
                    entry = (
                        stops_in[0]
                        if stops_in and stops_in[0] in ids and prev is None
                        else nearest(buses.point(links, first)[1])
                    )
                if nxt is not None and nxt[0] is not None:
                    shared = sorted(
                        {links[nxt[0]]["u"], links[nxt[0]]["v"]}
                        & {links[li]["u"], links[li]["v"]}
                    )
                    exit_ = (
                        shared[0] if shared else nearest(buses.point(links, last)[1])
                    )
                elif nxt is not None:
                    s = stretch_at.get(round(nxt[1][0], 3))
                    exit_ = (
                        ends[id(s), "leave"]
                        if s is not None and s["leave"]
                        else nearest(buses.point(links, last)[1])
                    )
                else:
                    exit_ = (
                        stops_in[-1]
                        if stops_in and stops_in[-1] in ids
                        else nearest(buses.point(links, last)[1])
                    )
                i, k = ids.index(entry), ids.index(exit_)
                for n in (ids[i : k + 1] if k >= i else ids[k : i + 1][::-1]):
                    push(n)
            if seq:
                pieces.append((seq, hops, stops_in, run[0][0], run[-1][1]))
        if not pieces:
            return [], {}
        # a route leaving the area and coming back: its pieces joined over the stretch outside, one
        # hop as long as the route there (a line runs its real route)
        seq, hops, stops_all = (
            list(pieces[0][0]),
            dict(pieces[0][1]),
            list(pieces[0][2]),
        )
        for prev, (sq, hp, stp, s_in, _) in zip(pieces, pieces[1:]):
            if sq[0] != seq[-1]:
                hops[seq[-1], sq[0]] = ("gap", Rr, prev[4], s_in)
                seq.append(sq[0])
            seq += sq[1:]
            hops.update(hp)
            stops_all += stp
        if len(pieces) > 1:
            split_runs.append(f"{Rr['key'][1]} ({len(pieces)} pieces)")
        # first stop to last
        if stops_all and stops_all[0] in seq and stops_all[-1] in seq:
            i = seq.index(stops_all[0])
            k = len(seq) - 1 - seq[::-1].index(stops_all[-1])
            if i < k:
                seq = seq[i : k + 1]
        return seq, hops

    # the street network after the splits, for bridging a step two links make with no node shared
    sadj = collections.defaultdict(list)
    for (a, b), (li, L, uv) in sub.items():
        sadj[a].append((b, L))

    def bridge(a, b):
        dist, prev, h = {a: 0.0}, {}, [(0.0, 0, a)]
        tie = 0
        while h:
            d, _, u = heapq.heappop(h)
            if u == b:
                out = [b]
                while out[-1] != a:
                    out.append(prev[out[-1]])
                return out[::-1], d
            if d > dist.get(u, math.inf):
                continue
            for v, L in sadj[u]:
                if d + L < dist.get(v, math.inf):
                    dist[v] = d + L
                    prev[v] = u
                    tie += 1
                    heapq.heappush(h, (d + L, tie, v))
        return None, math.inf

    # every stop the routes call at is a stop
    for (mode, name, li), n in stop_node.items():
        types.setdefault(n, set()).add("bus_stop")
        if not name_of.get(n):
            name_of[n] = name

    game_lines = []  # (table, name, kind, interval, source, [node chain], key)
    bridged, bridge_m, contraflow, ends_made_stops = 0, [], collections.Counter(), 0
    bridges, jumps, made, split_runs = [], [], [], []
    for key in kept:
        mode = key[0]
        if mode not in ("bus", "tram"):
            continue
        rels = {Rr["rid"]: Rr for Rr in got[mode]["per_rel"] if Rr["key"] == key}
        for di, r in enumerate(lines[key]):
            Rr = rels.get(r["id"])
            if Rr is None:
                continue
            seq, hops = chain_of(mode, Rr)
            if len(seq) < 2:
                continue
            nodes_run = [seq[0]]
            for a, b in zip(seq, seq[1:]):
                hop = hops.get((a, b))
                if hop is not None:
                    kind_of, s, sa, sb = hop
                    route = (
                        (s["pts"], s["arcs"], sa, sb)
                        if kind_of == "off"
                        else ([p for _, p in s["line"]], s["cum"], sa, sb)
                    )
                    run = own_edge(
                        a,
                        b,
                        "bus" if mode == "bus" else "train",
                        max(abs(sb - sa), straight(a, b)),
                        route=route,
                    )
                    nodes_run += run[1:]
                    continue
                path = [a, b] if (a, b) in sub else None
                if path is None:
                    path, d = bridge(a, b)
                    if path is None or d > BRIDGE:
                        sa = rail.project(Rr["line"], Rr["cum"], pos[a])[1]
                        sb = rail.project(Rr["line"], Rr["cum"], pos[b])[1]
                        L = max(abs(sb - sa), straight(a, b))
                        nodes_run += own_edge(
                            a, b, "bus" if mode == "bus" else "train", L
                        )[1:]
                        jumps.append(
                            (
                                L,
                                straight(a, b),
                                d,
                                key[1] + (" reverse" if di else ""),
                                a,
                                b,
                            )
                        )
                        continue
                    bridged += 1
                    bridge_m.append(d)
                    bridges.append(
                        (d, straight(a, b), key[1] + (" reverse" if di else ""), a, b)
                    )
                for x, y in zip(path, path[1:]):
                    if (x, y) in street_dirs:
                        nodes_run.append(y)
                        if mode == "tram":
                            rails_on_street.add((x, y))
                    else:  # against a one-way street: its own edge that way
                        contraflow[mode] += 1
                        nodes_run += own_edge(
                            x, y, "bus" if mode == "bus" else "train", sub[x, y][1]
                        )[1:]
            for n in (seq[0], seq[-1]):
                if not types.get(n, set()) & {"bus_stop", "station"}:
                    ends_made_stops += 1
                    made.append(
                        f"{key[1]}{' reverse' if di else ''} at {name_of.get(n) or n}"
                    )
                types.setdefault(n, set()).add("bus_stop")
            game_lines.append(
                (
                    "bus_lines" if mode == "bus" else "train_lines",
                    key[1] + (" reverse" if di else ""),
                    "tram" if mode == "tram" else None,
                    key,
                    nodes_run,
                )
            )

    # ---- rail: a station a node or its own, a hop its own edge
    st, placed, path_to = R["st"], R["placed"], R["path_to"]
    for k, n in placed.items():
        if isinstance(n, tuple):
            pos[n] = st[k]["p"]
            name_of[n] = k[1]
            types[n] = {"station"}
        else:
            types[n].add("station")
            if not name_of.get(n):
                name_of[n] = k[1]
    paths = {}
    for own, target in path_to.items():
        L = math.dist(pos[own], pos[target])
        paths[own, target] = L
        paths[target, own] = L
    track = collections.defaultdict(float)  # directed placed pair -> the longest track
    for hs in R["pairs"].values():
        for key, d, a, b, tr, snapped in hs:
            if tr:
                track[d] = max(track[d], snapped or tr)
    rail_kinds = collections.Counter()
    for key in kept:
        if key[0] not in RAIL:
            continue
        runs = collections.defaultdict(list)
        for k, rid, run in R["seqs"]:
            if k == key:
                runs[rid].append(run)
        for di, r in enumerate(lines[key]):
            rr = runs.get(r["id"])
            if not rr:
                continue
            # a relation leaving the area and coming back: its runs joined over the track outside
            seq, gaps = [], set()
            for j, run in enumerate(rr):
                for i, k in enumerate(run):
                    n = placed[k]
                    if not seq or seq[-1] != n:
                        if i == 0 and j > 0:
                            gaps.add((seq[-1], n))
                        seq.append(n)
            if len(rr) > 1:
                split_runs.append(f"{key[1]} (rail, {len(rr)} pieces)")
                tline, _ = rail.polyline(r, data["ways"])
                tcum = [0.0]
                for (_, p1), (_, p2) in zip(tline, tline[1:]):
                    tcum.append(tcum[-1] + math.dist(p1, p2))
            if len(seq) < 2:
                continue
            nodes_run = [seq[0]]
            for a, b in zip(seq, seq[1:]):
                tr = track.get((a, b)) or track.get((b, a)) or straight(a, b)
                if (a, b) in gaps and len(tline) >= 2:
                    ta, tb = (
                        rail.project(tline, tcum, pos[a])[1],
                        rail.project(tline, tcum, pos[b])[1],
                    )
                    nodes_run += own_edge(
                        a, b, "train", max(abs(tb - ta), straight(a, b))
                    )[1:]
                    rail_kinds["joined over the track outside the area"] += 1
                    continue
                if (
                    (a, b) in street_dirs
                    and (frozenset((a, b)) in on_links)
                    and sub[a, b][0] not in split_links
                ):
                    rails_on_street.add((a, b))
                    rail_kinds["a kept street's pair: `both`"] += 1
                    nodes_run.append(b)
                elif (a, b) in paths:
                    walk_rail.add((a, b))
                    edges[a, b] = dict(kind="train", length=tr, walks=True)
                    rail_kinds["a station's path: rails that walk"] += 1
                    nodes_run.append(b)
                else:
                    rail_kinds["its own rail edge"] += 1
                    nodes_run += own_edge(a, b, "train", tr)[1:]
            game_lines.append(
                (
                    "train_lines",
                    key[1] + (" reverse" if di else ""),
                    "train",
                    key,
                    nodes_run,
                )
            )

    # ---- the file: every node an edge or a line still uses
    used = {x for pr in list(street_dirs) + list(edges) + list(paths) for x in pr}
    keep_nodes = {
        n for n in pos if n in used or n in set(n0["id"] for n0 in graph["nodes"])
    }
    old_ids = [n["id"] for n in graph["nodes"]]
    new = sorted((n for n in keep_nodes if n not in set(old_ids)), key=repr)
    ids = {n: n for n in old_ids}
    nxt = max(int(i) for i in old_ids) + 1
    for n in new:
        ids[n] = str(nxt)
        nxt += 1
    out_nodes = []
    for n in old_ids + new:
        x, y = pos[n]
        t = types.get(n, {"intersection"})
        order = [
            x
            for x in ("bus_stop", "home", "intersection", "station", "workplace")
            if x in t
        ]
        out_nodes.append(
            dict(
                id=ids[n],
                name=(name_of.get(n) or "")[:100],
                x=x / 1000,
                y=y / 1000,
                types=order,
                versions=[0],
            )
        )

    out_edges, index = [], {}

    def add(a, b, e):
        index[a, b] = len(out_edges)
        e = dict(e, start_node=ids[a], end_node=ids[b], versions=[0])
        out_edges.append(e)

    # streets: unsplit links keep their edges; split ones become their sub-links
    linked = set()
    for li, l in enumerate(links):
        for x, y in ((l["u"], l["v"]), (l["v"], l["u"])):
            linked.add((x, y))
    for (a, b), e in sedge.items():
        if (a, b) in linked:
            continue
        add(
            a,
            b,
            {
                k: v
                for k, v in e.items()
                if k not in ("start_node", "end_node", "versions")
            },
        )
    for (a, b), (li, L, uv) in sorted(
        sub.items(), key=lambda kv: (kv[1][0], repr(kv[0]))
    ):
        if (a, b) not in street_dirs:
            continue
        l = links[li]
        e = sedge[(l["u"], l["v"]) if uv else (l["v"], l["u"])]
        f = {k: e[k] for k in STREET_COPY if k in e}
        f["type"] = "both" if (a, b) in rails_on_street else e.get("type", "street")
        f["circuity"] = (
            e.get("circuity", 1.0) if li not in split_links else circ(L, a, b)
        )
        add(a, b, f)
    for (a, b), L in paths.items():
        if (a, b) in walk_rail:
            continue
        add(
            a,
            b,
            dict(
                name="",
                type="path",
                biking=True,
                bike_lane=False,
                walking=True,
                circuity=1.0,
            ),
        )
    # a bus-only link is a real road one walks both ways: the way no bus rides it is a path
    back_paths = 0
    for (a, b), e in sorted(edges.items(), key=lambda kv: repr(kv[0])):
        if (
            e["kind"] == "bus"
            and (b, a) not in edges
            and (b, a) not in street_dirs
            and (b, a) not in paths
        ):
            add(
                b,
                a,
                dict(
                    name="",
                    type="path",
                    biking=True,
                    bike_lane=False,
                    walking=True,
                    circuity=circ(e["length"], a, b),
                ),
            )
            back_paths += 1
    for (a, b), e in sorted(edges.items(), key=lambda kv: repr(kv[0])):
        if e["kind"] == "bus":
            add(
                a,
                b,
                dict(
                    name="",
                    type="street",
                    biking=True,
                    bike_lane=False,
                    walking=True,
                    max_lanes=1,
                    speed_limit=50,
                    lanes=1,
                    dedicated_bus_lane=True,
                    circuity=circ(e["length"], a, b),
                ),
            )
        else:
            walks = e.get("walks", False)
            add(
                a,
                b,
                dict(
                    name="",
                    type="train",
                    biking=walks,
                    bike_lane=False,
                    walking=walks,
                    max_lanes=1,
                    circuity=circ(e["length"], a, b),
                ),
            )
    # a one-way street is one way for cars: on foot and by bike it goes both ways, so the way
    # back is a path as long as the street. Where a link already runs back that nobody walks
    # (rail), a second one would break one link per direction, and it is counted instead.
    by_pair = {(e["start_node"], e["end_node"]): e for e in out_edges}
    one_way_back, one_way_blocked = 0, 0
    for e in list(out_edges):
        if e.get("walking") is False:
            continue
        back = by_pair.get((e["end_node"], e["start_node"]))
        if back is None:
            out_edges.append(
                dict(
                    name=e.get("name", ""),
                    type="path",
                    biking=True,
                    bike_lane=False,
                    walking=True,
                    circuity=e.get("circuity", 1.0),
                    start_node=e["end_node"],
                    end_node=e["start_node"],
                    versions=[0],
                )
            )
            one_way_back += 1
        elif back.get("walking") is False:
            one_way_blocked += 1

    out_lines = {"bus_lines": [], "train_lines": []}
    sources = collections.Counter()
    defaults = []
    for table, name, kind, key, nodes_run in game_lines:
        iv, source = ruled.get(
            key, (timetable.DEFAULT_INTERVAL.get(key[0], 20), "default")
        )
        sources[source] += 1
        if source != "timetable" and not name.endswith(" reverse"):
            defaults.append(f"{key[1]} {iv} ({source})")
        chain = [index[a, b] for a, b in zip(nodes_run, nodes_run[1:])]
        line = dict(name=name, interval=int(iv))
        line.update(BUS if table == "bus_lines" else TRAIN[kind])
        if table == "train_lines":
            line["kind"] = kind
        line.update(versions=[0], chains=[dict(versions=[0], edges=chain)])
        out_lines[table].append(line)

    data_out = dict(graph)
    data_out["nodes"], data_out["edges"] = out_nodes, out_edges
    data_out.update(out_lines)

    # ---- the report
    n_split = sum(kn.split.values())
    say.append(
        f"Knoten {len(graph['nodes'])} → {len(out_nodes)} (Halte und Enden auf den Straßen {n_split}, Halte abseits "
        f"{len(off_pts)}, eigene Bahnhöfe {len(path_to)}, Mittelknoten {mids}); Kanten {len(graph['edges'])} → {len(out_edges)}"
    )
    say.append(
        "Linien: "
        + "; ".join(
            f"{m} {c}" for m, c in collections.Counter(k[0] for k in kept).items()
        )
        + f" → {len(out_lines['bus_lines'])} Bus- und {len(out_lines['train_lines'])} Bahnlinien in der Datei"
    )
    say.append(
        f"Bahnhöfe {len(st)}: {sum(not isinstance(v, tuple) for v in placed.values())} auf einem Knoten, {len(path_to)} eigene mit Weg; "
        "Abschnitte: " + ", ".join(f"{k} {v}" for k, v in rail_kinds.items())
    )
    kinds = collections.Counter(e["kind"] for e in edges.values())
    say.append(
        f"eigene Kanten: Busstraßen {kinds['bus']} (+ {back_paths} Wege in die Richtung, in die kein Bus fährt), Gleise {kinds['train']}; "
        f"Straßen mit Gleisen (`both`): {len(rails_on_street)}; gegen eine Einbahnstraße: "
        + (", ".join(f"{m} {c}" for m, c in contraflow.items()) or "keine")
    )
    say.append(
        f"Einbahnstraßen zu Fuß zurück: {one_way_back} Wege"
        + (
            f"; {one_way_blocked} nicht, dort fährt schon ein Gleis zurück, auf dem niemand geht"
            if one_way_blocked
            else ""
        )
    )
    if split_runs:
        say.append(
            "Strecken, die das Gebiet verlassen und zurückkommen, über das Stück draußen verbunden: "
            + ", ".join(split_runs)
        )
    if made:
        say.append(
            f"Linienenden ohne Halt, zum Halt gemacht: {ends_made_stops} — "
            + "; ".join(made)
        )
    fin = [d for d in bridge_m if d < math.inf]
    say.append(
        f"Schritte zwischen zwei Straßen ohne gemeinsamen Knoten: {bridged} über ≤ {BRIDGE:.0f} m Straße überbrückt"
        + (f" (längster {max(fin):.0f} m)" if fin else "")
        + f", {len(jumps)} auf eigener Kante entlang der Strecke"
    )
    say.append(
        "Takte: "
        + ", ".join(f"{s} {c}" for s, c in sources.items())
        + (" — aus einem Ersatz: " + ", ".join(defaults) if defaults else "")
    )
    # heads-up
    homes = [(n["name"], (n["x"] * 1000, n["y"] * 1000)) for n in out_nodes if "home" in n["types"]]
    works = [
        (n["name"], (n["x"] * 1000, n["y"] * 1000))
        for n in out_nodes
        if "workplace" in n["types"]
    ]
    places = homes + works
    stop_pts = [
        (n["x"] * 1000, n["y"] * 1000)
        for n in out_nodes
        if set(n["types"]) & {"bus_stop", "station"}
    ]
    line_stops = {
        k: [p for r in lines[k] for _, p in data["stops_of"][r["id"]]] for k in kept
    }
    raw_stops = [p for st in line_stops.values() for p in st]
    if not game_lines:
        heads_up.append("auf dieser Karte fährt kein Bus und keine Bahn")
    if not data["timetable_report"]["feed"]:
        heads_up.append(
            "kein Fahrplan für dieses Gebiet: Takte aus OSM, sonst die Vorgaben"
        )
    stop_ids = {
        n["id"] for n in out_nodes if set(n["types"]) & {"bus_stop", "station"}
    }
    walkers = [
        (n["name"], n["id"])
        for n in out_nodes
        if {"home", "workplace"} & set(n["types"])
        and report.nearest((n["x"] * 1000, n["y"] * 1000), stop_pts) <= REACH
    ]
    for line in (
        report.no_transport(
            places, raw_stops, REACH, bool(data["timetable_report"]["feed"])
        ),
        report.snapped_away(places, raw_stops, stop_pts, REACH),
        report.far_on_foot(out_nodes, out_edges, stop_ids, walkers, REACH),
        report.no_morning_trip(found),
        report.one_bus(works, line_stops, found, REACH),
    ):
        if line:
            heads_up.append(line)
    say.append(report.numbers(data_out))
    return data_out, say, heads_up
