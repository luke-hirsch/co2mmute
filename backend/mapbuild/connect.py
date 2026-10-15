"""The places onto the streets.

A: every place pins its own node — the nearest node of a road one can stop on (no motorway, no
   slip road) that no nearer place took — and the cut and the merge keep it.
B: a place still more than `FAR` from the network gets the shortest way out over the roads one
   class down, and the shortest way back in (both are searched: some districts reach the network
   only through one-way branches), added as streets. A place whose nearest street one class down
   is far too stays pinned to the main streets around it: no streets inside a Kiez.

No dead end is tied back and an outer district with no place in it stays off the map: the places
decide which districts get their road.
"""

import collections
import heapq
import math

from . import geo, roads, streets

FAR = 500.0  # m from the network: a place this far off gets a street one class down
CANDIDATES = 12  # the nearest nodes a place looks through for one no nearer place took


def mesh_m(pos, links):
    """the map's median street, as the game measures one — the road, never shorter than the
    straight line — on the merged streets before any place pins a node (pins add nodes, and the
    places' count would depend on itself)."""
    rp, merged_links = streets.merged(pos, links)
    lens = sorted(
        max(d["len"], math.dist(rp[t[0]], rp[t[1]]))
        for t in merged_links
        for d in (t[2], t[3])
        if d
    )
    return lens[len(lens) // 2]


def ids_on(links, p2):
    inv = {p: n for n, p in p2.items()}
    return {inv[q] for t in links for q in t[4] if q in inv}


def lower_graph(area, st, rung, P):
    """the directed graph of the roads one class down: (pos, ways, out, inn), adjacency
    {node: [(next, m, way index, segment)]}."""
    f = st["uf"].find
    pos_all, low = roads.lower_ways(area, st["cls"], rung)
    out, inn = collections.defaultdict(list), collections.defaultdict(list)
    for wi, w in enumerate(low):
        ns = [f(n) for n in w["nodes"]]
        for k, (a, b) in enumerate(zip(ns, ns[1:])):
            if a == b:
                continue
            L = math.dist(P.get(a) or pos_all[a], P.get(b) or pos_all[b])
            out[a].append((b, L, wi, k))
            inn[b].append((a, L, wi, k))
            if not w["oneway"]:
                out[b].append((a, L, wi, k))
                inn[a].append((b, L, wi, k))
    return pos_all, low, out, inn


def search(adj, s0, goal, bound=1e18, avoid=()):
    """Dijkstra from s0 to the first node in goal: (m, node, [(way, seg)], [nodes]) or None."""
    dist, prev, heap, c = {s0: 0.0}, {}, [(0.0, 0, s0)], 0
    while heap:
        d, _, x = heapq.heappop(heap)
        if d > dist.get(x, 1e18) or d > bound:
            continue
        if x in goal:
            segs, nodes, y = [], [], x
            while y != s0:
                z, wi, k = prev[y]
                if wi is not None:
                    segs.append((wi, k))
                nodes.append(y)
                y = z
            return d, x, segs, nodes
        for y, L, wi, k in adj[x]:
            if y in avoid and y != s0:
                continue
            if d + L < dist.get(y, 1e18):
                dist[y], prev[y] = d + L, (x, wi, k)
                c += 1
                heapq.heappush(heap, (d + L, c, y))
    return None


def sub_ways(low, used):
    """the pieces of the lower ways a way out or in runs on, as ways of their own."""
    return [
        dict(
            low[wi],
            id=f"{low[wi]['id']}~",
            nodes=low[wi]["nodes"][min(ks) : max(ks) + 2],
        )
        for wi, ks in used.items()
    ]


def nearest(nodes, pos, p):
    return min(nodes, key=lambda n: math.dist(pos[n], p))


def own_nodes(nodes, pos, at, k=CANDIDATES):
    """each place its own node: the nearest one no nearer place took. A home and a workplace on
    one node would be a commute of nothing; on the road's own geometry the next free node is
    metres away."""
    cand = {
        nm: heapq.nsmallest(k, nodes, key=lambda n, p=geo.xy(*ll): math.dist(pos[n], p))
        for nm, ll in at.items()
    }
    taken = set()
    for nm in sorted(at, key=lambda nm: math.dist(pos[cand[nm][0]], geo.xy(*at[nm]))):
        free = [n for n in cand[nm] if n not in taken]
        if not free:
            free = [nearest(set(nodes) - taken, pos, geo.xy(*at[nm]))]
        taken.add(free[0])
    return taken


def graph_pins(P, ways, uf, at, builtup):
    """the folded graph with the road node nearest each place made a junction: (pos, links, pins)."""
    seg = streets.segments(P, ways, uf, builtup)
    p2 = dict(P)
    p2.update(streets.crossing_pos(P, uf, [n for w in ways for n in w["nodes"]]))
    # a place lies on a street one can stop on: no motorway, no slip road
    on_road = {
        n for e, r in seg.items() if not r["slip"] and r["cls"] != "motorway" for n in e
    }
    pins = own_nodes(on_road, p2, at)
    _, links = streets.contract(p2, seg, extra=pins)
    return p2, streets.live(links), pins


def gaps(pos, links, at):
    """each place to the nearest node of the graph: {name: m}."""
    nodes = {n for t in links for n in t[:2]}
    return {
        nm: math.dist(pos[nearest(nodes, pos, geo.xy(*ll))], geo.xy(*ll))
        for nm, ll in at.items()
    }


def reach(area, p2, st, at, keep_from, rung, far=FAR):
    """places still `far` from the network after the pins: the shortest way out over the lower
    roads from the road node nearest the place to the network, and the shortest way back in,
    added as streets. returns (extra ways, positions, report rows)."""
    pos_all, low, out, inn = lower_graph(area, st, rung, p2)
    P = dict(pos_all)
    P.update(p2)
    K = ids_on(keep_from, p2)
    used, rep = collections.defaultdict(set), []
    low_nodes = [n for n in out if n in inn]
    for nm, ll in at.items():
        p = geo.xy(*ll)
        d0 = min(math.dist(P[n], p) for n in K)
        if d0 <= far:
            continue
        src = min(low_nodes, key=lambda n: math.dist(P[n], p))
        way_out, way_in = search(out, src, K), search(inn, src, K)
        if not way_out or not way_in:
            rep.append((nm, d0, None, math.dist(P[src], p)))
            continue
        for _, _, segs, nodes in (way_out, way_in):
            for wi, k in segs:
                used[wi].add(k)
            K.update(nodes)
        K.add(src)
        rep.append((nm, d0, max(way_out[0], way_in[0]), math.dist(P[src], p)))
    return sub_ways(low, used), pos_all, rep


def connected(area, pos, links, st, at, far=FAR):
    """A and B on the folded streets: (pos, links, report lines)."""
    pp, pl, pins = graph_pins(st["p1"], st["w1"], st["uf"], at, st["builtup"])
    pinned = streets.merged(pp, pl, pins)
    rung = roads.LADDER[roads.LADDER.index(st["cls"]) + 1]
    extra, pos_all, rep = reach(area, pos, st, at, pinned[1], rung, far)
    P = dict(pos_all)
    P.update(st["p1"])
    q2, lx, pins2 = graph_pins(P, st["w1"] + extra, st["uf"], at, st["builtup"])
    g = streets.merged(q2, lx, pins2)
    label = (
        lambda nm: ("Wohnort " if nm.startswith("home ") else "Arbeitsort ")
        + nm.split(" ", 1)[1]
    )
    tied = [r for r in rep if r[2] is not None]
    say = [
        f"{len(rep)} Orte weiter als {far:.0f} m vom Netz; {len(tied)} über die Straßen der Klasse {rung} angebunden"
    ]
    no_way = [label(r[0]) for r in rep if r[2] is None]
    if no_way:
        say.append(
            f"auch über {rung} kein Weg hin und zurück, an den Hauptstraßen: "
            + ", ".join(no_way)
        )
    still = sorted(
        ((d, nm) for nm, d in gaps(g[0], g[1], at).items() if d > far), reverse=True
    )
    if still:
        say.append(
            f"danach noch weiter als {far:.0f} m vom Netz: "
            + ", ".join(f"{label(nm)} {d:.0f} m" for d, nm in still)
        )
    return g[0], g[1], say
