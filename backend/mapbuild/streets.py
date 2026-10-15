"""The streets: OSM's carriageways and junctions → one edge per street, one node per crossing.

OSM draws a big street as two one-way carriageways, and every crossing of two of them as four
junctions. The game draws a street as one two-way edge and a crossing as one node.

The fold:
1. twins: a one-way way (not a roundabout, not a slip road) twins with the one-way ways of the
   same street that run the other way within `D` of it, if they cover half its length. The same
   street: they share a name or a ref (one carriageway "Oldenburger Straße", its twin only "B 75").
2. mirror: every junction on a twinned way is mirrored onto its twin: it joins a junction of the
   twin within `SNAP` of the foot of its perpendicular, else a node is put into the twin there.
3. crossings: a junction and its mirror are one crossing; so are junctions within `D` of each
   other that share two street keys (the four corners of two dual carriageways crossing). A
   crossing sits at the centroid of its junctions.
4. contract: chains between crossings; one carriageway gives one direction of a street link, its
   twin the other.

Then the merge, after the dead ends are cut back to their last junction:
1. slip roads: a link made only of `_link` ways joins its two ends — an interchange is one node.
2. short links: a link shorter than `S` (straight line) joins its two ends — staggered junctions,
   a side street meeting the two carriageways apart, a small roundabout. A merged node sits at
   the centroid of the junctions it took in.
3. bundles: two chains between the same two nodes in one direction (a map has one link per
   direction per node pair). The same street: lanes add (a carriageway split around an island).
   Two streets: the less important one gets a node at its middle.
4. pass-throughs: a node that only carries one street on (two neighbours, the same directions
   both sides) goes; the two links become one (the narrower lanes, the time to drive both).

A link is (u, v, forward, backward, geometry): each direction a dict (len, speed, lanes, rank,
names, slip) or None where the street is one-way.
"""

import collections
import math

from . import geo, roads

D = 80.0  # m: twins and crossings
SNAP = 25.0  # m along the twin: a mirror this close to a junction of the twin is that junction
S = 30.0  # m: a link this short (straight line) is one node


def twins(pos, ways, D=D):
    """{way index: {partner way index: m of this way it covers}} for the one-way ways that twin."""
    cand = [
        i
        for i, w in enumerate(ways)
        if w["oneway"] and not w["ring"] and not w["link"] and w["key"]
    ]
    grid = collections.defaultdict(list)  # (alias, cell) -> (way index, a, b)
    for i in cand:
        w = ways[i]
        for a, b in zip(w["nodes"], w["nodes"][1:]):
            pa, pb = pos[a], pos[b]
            for cx in range(
                int(min(pa[0], pb[0]) // D) - 1, int(max(pa[0], pb[0]) // D) + 2
            ):
                for cy in range(
                    int(min(pa[1], pb[1]) // D) - 1, int(max(pa[1], pb[1]) // D) + 2
                ):
                    for k in w["aliases"]:
                        grid[(k, cx, cy)].append((i, a, b))
    out = {}
    for i in cand:
        w = ways[i]
        cover = collections.Counter()
        total = 0.0
        for a, b in zip(w["nodes"], w["nodes"][1:]):
            pa, pb = pos[a], pos[b]
            L = math.dist(pa, pb)
            if L == 0:
                continue
            d = ((pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L)
            steps = max(1, int(L // 10))
            for s in range(steps):  # one sample per 10 m, at the middle of its stretch
                f = (s + 0.5) / steps
                p = (pa[0] + f * (pb[0] - pa[0]), pa[1] + f * (pb[1] - pa[1]))
                total += L / steps
                best = None
                near = {
                    t
                    for k in w["aliases"]
                    for t in grid[(k, int(p[0] // D), int(p[1] // D))]
                }
                for j, qa, qb in near:
                    if j == i:
                        continue
                    A, B = pos[qa], pos[qb]
                    M = math.dist(A, B)
                    if M == 0:
                        continue
                    if (
                        (B[0] - A[0]) * d[0] + (B[1] - A[1]) * d[1]
                    ) / M > -0.5:  # not the other way
                        continue
                    dist = geo.point_seg(p, A, B)
                    if dist <= D and (best is None or dist < best[0]):
                        best = (dist, j)
                if best:
                    cover[best[1]] += L / steps
        if total and sum(cover.values()) >= 0.5 * total:
            out[i] = dict(cover)
    return out


def foot(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    t = (
        0.0
        if L2 == 0
        else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    )
    return t, (ax + t * dx, ay + t * dy)


def neighbours(ways):
    nbr = collections.defaultdict(set)
    for w in ways:
        for a, b in zip(w["nodes"], w["nodes"][1:]):
            if a != b:
                nbr[a].add(b)
                nbr[b].add(a)
    return nbr


def fold(pos, ways, tw, D=D, snap=SNAP):
    """mirror the junctions of twinned ways, cluster crossings. returns (uf, pos, ways)."""
    pos = dict(pos)
    ways = [dict(w, nodes=list(w["nodes"])) for w in ways]
    nbr = neighbours(ways)
    junction = {n for n, s in nbr.items() if len(s) != 2}
    uf = geo.UF()
    # mirror: inserts are collected per partner segment and spliced afterwards, in order
    inserts = collections.defaultdict(
        list
    )  # (way index, segment index) -> [(t, new node, point)]
    for i, cover in tw.items():
        w = ways[i]
        for n in w["nodes"]:
            if n not in junction:
                continue
            best = None
            for j in cover:
                pw = ways[j]
                for k, (a, b) in enumerate(zip(pw["nodes"], pw["nodes"][1:])):
                    t, q = foot(pos[n], pos[a], pos[b])
                    dist = math.dist(pos[n], q)
                    if dist <= D and (best is None or dist < best[0]):
                        best = (dist, j, k, t, q)
            if best is None:
                continue
            _, j, k, t, q = best
            near = [
                m
                for m in ways[j]["nodes"]
                if m in junction and math.dist(pos[m], q) <= snap
            ]
            if near:
                uf.union(n, min(near, key=lambda m: math.dist(pos[m], q)))
            else:
                m = f"m{n}@{ways[j]['id']}"
                inserts[(j, k)].append((t, m, q))
                uf.union(n, m)
    for j in sorted({j for j, _ in inserts}):
        nodes = ways[j]["nodes"]
        out = [nodes[0]]
        for k in range(len(nodes) - 1):
            for t, m, q in sorted(inserts.get((j, k), [])):
                if m not in pos:
                    pos[m] = q
                    out.append(m)
            out.append(nodes[k + 1])
        ways[j]["nodes"] = out
    # crossings: junctions within D that share two keys
    keys = collections.defaultdict(set)
    for w in ways:
        if w["key"]:
            for n in w["nodes"]:
                keys[n].add(w["key"])
    nbr = neighbours(ways)
    junction = {n for n, s in nbr.items() if len(s) != 2} | {
        m for (_, _), ins in inserts.items() for _, m, _ in ins
    }
    grid = collections.defaultdict(list)
    for n in junction:
        grid[(int(pos[n][0] // D), int(pos[n][1] // D))].append(n)
    for n in junction:
        if len(keys[n]) < 2:
            continue
        cx, cy = int(pos[n][0] // D), int(pos[n][1] // D)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for m in grid[(cx + i, cy + j)]:
                    if (
                        m != n
                        and len(keys[n] & keys[m]) >= 2
                        and math.dist(pos[n], pos[m]) <= D
                    ):
                        uf.union(n, m)
    return uf, pos, ways


def segments(pos, ways, uf=None, builtup=None):
    """directed segments (u, v) -> dict(len, lanes, speed, rank, name, cls, way, slip), endpoints
    through the crossings."""
    f = uf.find if uf else (lambda n: n)
    seg = {}
    for w in ways:
        t = w["tags"]
        rank = roads.RANK[w["base"]] - (0.5 if w["link"] else 0)
        lf, lb = w["lanes"]
        for a, b in zip(w["nodes"], w["nodes"][1:]):
            pa, pb = pos[a], pos[b]
            a2, b2 = f(a), f(b)
            if a2 == b2:
                continue
            sp = roads.speed(
                t, w["base"], ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2), builtup
            )
            rec = dict(
                len=max(math.dist(pa, pb), 0.1),
                lanes=lf,
                speed=sp,
                rank=rank,
                name=w["key"],
                cls=w["cls"],
                way=w["id"],
                slip=w["link"],
            )
            seg[(a2, b2)] = rec
            if not w["oneway"]:
                seg[(b2, a2)] = dict(rec, lanes=lb)
    return seg


def crossing_pos(pos, uf, nodes):
    groups = collections.defaultdict(list)
    for n in nodes:
        groups[uf.find(n)].append(pos[n])
    return {
        r: (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))
        for r, ps in groups.items()
    }


def contract(pos, seg, extra=()):
    """chains between junctions -> links (u, v, forward, backward, geometry)."""
    nbr = collections.defaultdict(set)
    for a, b in seg:
        nbr[a].add(b)
        nbr[b].add(a)
    junction = {n for n in nbr if len(nbr[n]) != 2} | (set(extra) & set(nbr))
    links = []
    seen = set()
    for j in list(junction):
        for n in nbr[j]:
            if (j, n) in seen:
                continue
            path = [j, n]
            while path[-1] not in junction:
                nxt = [m for m in nbr[path[-1]] if m != path[-2]]
                if not nxt:
                    break
                path.append(nxt[0])
                if path[-1] == j:
                    break
            for a, b in zip(path, path[1:]):
                seen.add((a, b))
                seen.add((b, a))
            u, v = path[0], path[-1]
            if u == v:
                continue

            def agg(p):
                parts = [seg.get((a, b)) for a, b in zip(p, p[1:])]
                if any(s is None for s in parts):
                    return None
                L = sum(s["len"] for s in parts)
                t = sum(s["len"] / s["speed"] for s in parts)
                return dict(
                    len=L,
                    speed=L / t,
                    lanes=min(s["lanes"] for s in parts),
                    rank=max(s["rank"] for s in parts),
                    names=collections.Counter(
                        {s["name"]: s["len"] for s in parts if s["name"]}
                    ),
                    slip=all(s.get("slip") for s in parts),
                )

            links.append((u, v, agg(path), agg(path[::-1]), [pos[p] for p in path]))
    return junction, links


def graph(pos, ways, uf=None, builtup=None):
    """contract to junctions: (pos of junctions, junctions, links)."""
    seg = segments(pos, ways, uf, builtup)
    p2 = dict(pos)
    if uf:
        p2.update(crossing_pos(pos, uf, [n for w in ways for n in w["nodes"]]))
    for a, b in seg:
        p2.setdefault(a, pos.get(a))
        p2.setdefault(b, pos.get(b))
    junction, links = contract(p2, seg)
    return p2, junction, links


def folded(area, builtup, cls=None):
    """the area's streets after the fold: (pos, links, state for the places to pin into)."""
    pos, ways = roads.load(area, roads.CLASSES[cls or area.cls])
    uf, p1, w1 = fold(pos, ways, twins(pos, ways, D), D)
    p2, _, l1 = graph(p1, w1, uf, builtup)
    return (
        p2,
        live(l1),
        dict(pos=pos, uf=uf, p1=p1, w1=w1, cls=cls or area.cls, builtup=builtup),
    )


# --- the merge -----------------------------------------------------------------------------


def live(links):
    return [t for t in links if t[0] != t[1] and (t[2] or t[3])]


def is_slip(d):
    return d is None or d.get("slip", False)


def road(t):
    return min(d["len"] for d in (t[2], t[3]) if d)


def top_name(t):
    names = collections.Counter()
    for d in (t[2], t[3]):
        if d:
            names.update(d["names"])
    return names.most_common(1)[0][0] if names else ""


def drop_ends(links, keep=()):
    """a road that ends, at the clip or in a cul-de-sac, goes back to its last junction."""
    keep = set(keep)
    links = list(links)
    while True:
        deg = collections.Counter()
        for u, v, *_ in links:
            deg[u] += 1
            deg[v] += 1
        ends = {n for n, k in deg.items() if k == 1 and n not in keep}
        if not ends:
            return links
        links = [t for t in links if t[0] not in ends and t[1] not in ends]


def cut_ends(links, keep=()):
    """dead ends by neighbours, not by chains: a stub reached by two one-way chains is one too."""
    while True:
        nb = collections.defaultdict(set)
        for u, v, *_ in links:
            nb[u].add(v)
            nb[v].add(u)
        ends = {n for n, s in nb.items() if len(s) == 1 and n not in keep}
        if not ends:
            return links
        links = [t for t in links if t[0] not in ends and t[1] not in ends]


def rebuild(pos, links, uf):
    """endpoints through uf, a merged node at the centroid of its members, loops dropped."""
    members = collections.defaultdict(set)
    for u, v, *_ in links:
        members[uf.find(u)].add(u)
        members[uf.find(v)].add(v)
    p = {
        r: (sum(pos[m][0] for m in ms) / len(ms), sum(pos[m][1] for m in ms) / len(ms))
        for r, ms in members.items()
    }
    out = [(uf.find(u), uf.find(v), f, b, g) for u, v, f, b, g in links]
    return p, live(out)


def merge_ends(pos, links, pick, keep=()):
    """join the two ends of every link `pick` takes; a node in `keep` (a place's own node) is
    carried to the node it merged into, and two of them never merge into one. returns
    (pos, links, the kept nodes as they are now)."""
    uf = geo.UF()
    pinned = set(keep)  # roots holding a kept node
    for t in links:
        if pick(t):
            ra, rb = uf.find(t[0]), uf.find(t[1])
            if ra == rb or (ra in pinned and rb in pinned):
                continue
            uf.union(ra, rb)
            if ra in pinned or rb in pinned:
                pinned.add(uf.find(ra))
    p, out = rebuild(pos, links, uf)
    return p, out, {uf.find(k) for k in keep}


def add_dir(x, y):
    if x is None:
        return y
    if y is None:
        return x
    lanes = x["lanes"] + y["lanes"]
    return dict(
        len=min(x["len"], y["len"]),
        speed=(x["speed"] * x["lanes"] + y["speed"] * y["lanes"]) / lanes,
        lanes=lanes,
        rank=max(x["rank"], y["rank"]),
        names=x["names"] + y["names"],
        slip=x.get("slip") and y.get("slip"),
    )


def oriented(t, a):
    u, v, f, b, g = t
    return (u, v, f, b, g) if u == a else (v, u, b, f, g[::-1])


def unbundle(pos, links):
    """one chain per direction per node pair: (pos, links)."""
    pos = dict(pos)
    groups = collections.defaultdict(list)
    for t in links:
        a, z = sorted((t[0], t[1]), key=str)
        groups[(a, z)].append(oriented(t, a))
    out = []
    for (a, z), ts in groups.items():
        if len(ts) == 1:
            out.append(ts[0])
            continue
        ts.sort(key=lambda t: (-max(d["rank"] for d in (t[2], t[3]) if d), road(t)))
        keep = list(ts[0])
        for t in ts[1:]:
            clash = (t[2] and keep[2]) or (t[3] and keep[3])
            if not clash:  # the other direction of the same pair: one link
                keep[2], keep[3] = keep[2] or t[2], keep[3] or t[3]
            elif top_name(t) and top_name(t) == top_name(
                keep
            ):  # the same street: lanes add
                keep[2], keep[3] = add_dir(keep[2], t[2]), add_dir(keep[3], t[3])
            else:  # two streets: a node on the less important one
                g = t[4]
                mid = f"b{a}|{z}|{len(out)}"
                pos[mid] = (
                    g[len(g) // 2]
                    if len(g) > 2
                    else ((g[0][0] + g[-1][0]) / 2, (g[0][1] + g[-1][1]) / 2)
                )
                half = lambda d: d and dict(d, len=d["len"] / 2)
                out.append((a, mid, half(t[2]), half(t[3]), g[: len(g) // 2 + 1]))
                out.append((mid, z, half(t[2]), half(t[3]), g[len(g) // 2 :]))
        out.append(tuple(keep))
    return pos, out


def join(x, y):
    if x is None or y is None:
        return None
    L = x["len"] + y["len"]
    return dict(
        len=L,
        speed=L / (x["len"] / x["speed"] + y["len"] / y["speed"]),
        lanes=min(x["lanes"], y["lanes"]),
        rank=min(x["rank"], y["rank"]),
        names=x["names"] + y["names"],
        slip=x.get("slip") and y.get("slip"),
    )


def pass_throughs(links, keep=()):
    """drop the nodes that carry one street on; a node in `keep` stays."""
    links = list(links)
    changed = True
    while changed:
        changed = False
        at = collections.defaultdict(list)
        for i, t in enumerate(links):
            at[t[0]].append(i)
            at[t[1]].append(i)
        pairset = {frozenset(t[:2]) for t in links}
        gone, new = set(), []
        for n, idx in at.items():
            if n in keep or len(idx) != 2 or any(i in gone for i in idx):
                continue
            t1 = (
                links[idx[0]]
                if links[idx[0]][1] == n
                else oriented(links[idx[0]], links[idx[0]][1])
            )
            t2 = links[idx[1]] if links[idx[1]][0] == n else oriented(links[idx[1]], n)
            a, z = t1[0], t2[1]
            if a == z or t1[1] != n or t2[0] != n or frozenset((a, z)) in pairset:
                continue
            if bool(t1[2]) != bool(t2[2]) or bool(t1[3]) != bool(t2[3]):
                continue
            new.append(
                (a, z, join(t1[2], t2[2]), join(t2[3], t1[3]), t1[4] + t2[4][1:])
            )
            gone.update(idx)
            pairset.add(frozenset((a, z)))
            changed = True
        links = [t for i, t in enumerate(links) if i not in gone] + new
    return links


def merged(pos, links, keep=()):
    """the merge on folded links: dead ends cut (but not at a kept node), slip roads and short
    links one node, bundles resolved, pass-throughs dropped: (pos, links)."""
    keep = set(keep)
    le = live(drop_ends(links, keep))
    le = cut_ends(le, keep)
    pB, lB, keep = merge_ends(pos, le, lambda t: is_slip(t[2]) and is_slip(t[3]), keep)
    pC, lC, keep = merge_ends(pB, lB, lambda t: math.dist(pB[t[0]], pB[t[1]]) < S, keep)
    pD, lD = unbundle(pC, lC)
    return pD, pass_throughs(lD, keep)
