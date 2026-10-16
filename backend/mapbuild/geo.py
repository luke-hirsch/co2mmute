"""The plane a build works in, and the geometry every stage shares.

A point is (x, y) in metres east and south of the north-west corner of the box being built, on a
plane through the box's middle latitude — a map file stores its nodes the same way, in km. One
box at a time: `use` sets it, and every `xy` after it projects into it.
"""

import collections
import math

KY = 110574  # m per degree of latitude
LAT_MAX, LON_MIN = 0.0, 0.0
KX = 111320.0
BBOX = (0.0, 0.0, 0.0, 0.0)  # south, west, north, east


def use(bbox):
    """project into this box (south, west, north, east) from now on."""
    global LAT_MAX, LON_MIN, KX, BBOX
    s, w, n, e = bbox
    BBOX = tuple(bbox)
    LAT_MAX, LON_MIN = n, w
    KX = 111320 * math.cos(math.radians((s + n) / 2))


def xy(lat, lon):
    return ((lon - LON_MIN) * KX, (LAT_MAX - lat) * KY)


def to_latlon(p):
    x, y = p
    return (LAT_MAX - y / KY, LON_MIN + x / KX)


def size():
    """the box's width and height in m."""
    s, w, n, e = BBOX
    return (e - w) * KX, (n - s) * KY


def pad(bbox, m):
    """the box grown by m on every side."""
    s, w, n, e = bbox
    dlat, dlon = m / KY, m / (111320 * math.cos(math.radians((s + n) / 2)))
    return (s - dlat, w - dlon, n + dlat, e + dlon)


def point_seg(p, a, b):
    """the distance from p to the segment a–b."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def near_segments(segs, d):
    """a test: within d of any of the segments (grid of cell d)."""
    grid = collections.defaultdict(list)
    for a, b in segs:
        for i in range(int(min(a[0], b[0]) // d) - 1, int(max(a[0], b[0]) // d) + 2):
            for j in range(
                int(min(a[1], b[1]) // d) - 1, int(max(a[1], b[1]) // d) + 2
            ):
                grid[(i, j)].append((a, b))
    return lambda p: any(
        point_seg(p, a, b) < d for a, b in grid[(int(p[0] // d), int(p[1] // d))]
    )


def polylen(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


class Inside:
    """even-odd test over a soup of outline segments, bucketed by y."""

    def __init__(self, segs, bucket=500.0):
        self.bucket = bucket
        self.rows = collections.defaultdict(list)
        for a, b in segs:
            lo, hi = sorted((a[1], b[1]))
            for k in range(int(lo // bucket), int(hi // bucket) + 1):
                self.rows[k].append((a, b))

    def __call__(self, p):
        x, y = p
        c = False
        for a, b in self.rows[int(y // self.bucket)]:
            if (a[1] > y) != (b[1] > y):
                xi = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if xi > x:
                    c = not c
        return c


class UF:
    """union-find; a set is named by its smallest member (as text), whatever the order of unions."""

    def __init__(self):
        self.p = {}

    def find(self, x):
        p = self.p
        while p.get(x, x) != x:
            p[x] = p.get(p[x], p[x])
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb, key=str)] = min(ra, rb, key=str)


class Graph:
    """links between nodes, both directions of a node pair in one record; for the strongly
    connected part a map keeps."""

    def __init__(self, pos, junction, links):
        self.pos = {j: pos[j] for j in junction}
        # adj[u][v] = {"uv": attrs | None, "vu": attrs | None, "geom": [...]}
        self.adj = collections.defaultdict(dict)
        for u, v, f, b, g in links:
            self._add(u, v, f, b, g)

    @staticmethod
    def _merge_dir(x, y):
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
            junction=(
                x.get("junction", "") if x.get("junction") == y.get("junction") else ""
            ),
        )

    def _add(self, u, v, f, b, g):
        if u == v:
            return
        cur = self.adj[u].get(v)
        if cur is None:
            rec = {"uv": f, "vu": b, "geom": g}
            self.adj[u][v] = rec
            self.adj[v][u] = {"uv": b, "vu": f, "geom": g[::-1], "_twin": rec}
            rec["_twin"] = self.adj[v][u]
        else:
            cur["uv"] = self._merge_dir(cur["uv"], f)
            cur["vu"] = self._merge_dir(cur["vu"], b)
            tw = cur["_twin"]
            tw["uv"], tw["vu"] = cur["vu"], cur["uv"]

    def remove_node(self, n):
        for m in list(self.adj[n]):
            del self.adj[m][n]
        del self.adj[n]
        del self.pos[n]

    def strongly_connected(self):
        """keep the largest strongly connected part: a car must get back from wherever it goes."""
        out = collections.defaultdict(list)
        inn = collections.defaultdict(list)
        for u in self.adj:
            for v, r in self.adj[u].items():
                if r["uv"]:
                    out[u].append(v)
                    inn[v].append(u)
        best = set()
        left = set(self.pos)
        while left:
            s = next(iter(left))
            comp = self._reach(s, out) & self._reach(s, inn)
            left -= comp
            left.discard(s)
            if len(comp) > len(best):
                best = comp
        for n in list(self.pos):
            if n not in best:
                self.remove_node(n) if n in self.adj else self.pos.pop(n)

    @staticmethod
    def _reach(s, edges):
        seen = {s}
        stack = [s]
        while stack:
            x = stack.pop()
            for y in edges[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return seen
