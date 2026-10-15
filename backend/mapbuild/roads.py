"""OSM's ways of the street classes a map is built from: clipped, with speed and lanes.

- classes: secondary and up (motorway, trunk, primary, secondary) — a city's big streets and
  famous axes. A place that ends up far from them gets one class down (`connect`).
- speed: the sign where OSM has one (`maxspeed`, or a tag naming the sign's type); unsigned, 50
  inside a built-up area and 100 outside it (StVO §3). Built-up is built-up land (residential and
  work land) at the road or within a margin of it; the margin is the one that errs alike on the
  area's own signed 50 and 100 roads (`fit_builtup`), so it needs no number per city.
- lanes: the tags, else 2 a direction on motorways and trunks, 1 elsewhere.
"""

import math

from . import download, geo

CLASSES = {
    "secondary": {"motorway", "trunk", "primary", "secondary"},
}
# one class down at a time, in this order
LADDER = ["secondary", "tertiary", "unclassified", "residential"]
for _a, _b in zip(LADDER, LADDER[1:]):
    CLASSES[_b] = CLASSES[_a] | {_b}
LINKS = {
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}
DEFAULT_LANES = {
    "motorway": 2,
    "trunk": 2,
    "primary": 2,
    "secondary": 1,
    "tertiary": 1,
    "unclassified": 1,
    "residential": 1,
}
DEFAULT_SPEED = {
    "motorway": 100,
    "trunk": 70,
    "primary": 50,
    "secondary": 50,
    "tertiary": 50,
    "unclassified": 50,
    "residential": 50,
}
RANK = {
    "motorway": 4,
    "trunk": 3,
    "primary": 2,
    "secondary": 1,
    "tertiary": 0.75,
    "unclassified": 0.5,
    "residential": 0.25,
}
URBAN, RURAL = 50, 100  # StVO §3, cars
MARGINS = (
    0,
    10,
    20,
    30,
    40,
    50,
    75,
    100,
)  # m: built-up land this far from a road makes it built-up


def parse_int(v, default):
    try:
        return int(str(v).split(";")[0].split()[0])
    except (ValueError, IndexError):
        return default


def implicit(tags):
    """the limit a German sign implies, from maxspeed or the tags that name its type."""
    for k in (
        "maxspeed",
        "maxspeed:type",
        "source:maxspeed",
        "zone:maxspeed",
        "zone:traffic",
    ):
        v = tags.get(k, "")
        if v in ("none", "DE:motorway"):
            return 100
        if v.endswith("DE:urban"):
            return URBAN
        if v.endswith("DE:rural"):
            return RURAL
        if v.endswith("DE:zone30") or v == "DE:30":
            return 30
    return None


def speed(tags, cls, mid=None, builtup=None):
    """km/h: the sign, else built-up or not at the segment's middle, else the class's."""
    v = parse_int(tags.get("maxspeed"), None)
    if v:
        return min(v, 100)
    v = implicit(tags)
    if v:
        return v
    if builtup is not None and mid is not None and cls != "motorway":
        return URBAN if builtup(mid) else RURAL
    return DEFAULT_SPEED[cls]


def direction_lanes(tags, cls, oneway):
    lanes = parse_int(tags.get("lanes"), None)
    if oneway:
        return (lanes or DEFAULT_LANES[cls], 0)
    fwd = parse_int(tags.get("lanes:forward"), None)
    bwd = parse_int(tags.get("lanes:backward"), None)
    if fwd and bwd:
        return (fwd, bwd)
    if lanes:
        half = max(1, lanes // 2)
        return (half, max(1, lanes - half))
    d = max(1, DEFAULT_LANES[cls] // 2) if cls != "secondary" else 1
    return (d, d)


def _raw(area, class_set):
    raw = list(download.osm(area, "roads"))
    if class_set - CLASSES["secondary"]:
        raw += download.osm(area, "local")
    return raw


def load(area, class_set):
    """the ways of these classes clipped to the area: (pos, ways). A way that leaves the area and
    comes back is two."""
    raw = _raw(area, class_set)
    inside = area.clip()
    pos, ways = {}, []
    for w in raw:
        t = w["tags"]
        h = t["highway"]
        base = h.replace("_link", "")
        if (
            base not in class_set
            or t.get("access") in ("no", "private")
            or t.get("area") == "yes"
        ):
            continue
        ow = t.get("oneway")
        ring = t.get("junction") in ("roundabout", "circular")
        oneway = ow in ("yes", "1", "true", "-1") or h.startswith("motorway") or ring
        nodes = list(w["nodes"])
        geom = [geo.xy(p["lat"], p["lon"]) for p in w["geometry"]]
        if ow == "-1":
            nodes, geom = nodes[::-1], geom[::-1]
        lf, lb = direction_lanes(t, base, oneway)
        runs, cur = [], []
        for n, p in zip(nodes, geom):
            if inside(p):
                cur.append((n, p))
            else:
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
        if len(cur) > 1:
            runs.append(cur)
        for k, run in enumerate(runs):
            for n, p in run:
                pos[n] = p
            ways.append(
                dict(
                    id=f"{w['id']}" + (f".{k}" if len(runs) > 1 else ""),
                    key=t.get("name") or t.get("ref") or "",
                    aliases=({t["name"]} if t.get("name") else set())
                    | {r.strip() for r in t.get("ref", "").split(";") if r.strip()},
                    cls=h,
                    base=base,
                    link=h in LINKS,
                    ring=ring,
                    oneway=oneway,
                    lanes=(lf, lb),
                    tags=t,
                    nodes=[n for n, _ in run],
                )
            )
    return pos, ways


def _land_segments(elements):
    segs = []
    for e in elements:
        rings = (
            [e["geometry"]]
            if e["type"] == "way"
            else [m["geometry"] for m in e["members"] if m.get("geometry")]
        )
        for g in rings:
            pts = [geo.xy(p["lat"], p["lon"]) for p in g]
            if pts and pts[0] != pts[-1]:
                pts.append(pts[0])
            segs += list(zip(pts, pts[1:]))
    return segs


def fit_builtup(area):
    """the built-up test: (test, margin m, share of 50 signs right, of 100 signs right)."""
    W, H = geo.size()
    land = geo.Inside(
        _land_segments(
            download.osm(area, "residential") + download.osm(area, "workland")
        ),
        bucket=200.0,
    )

    def near_land(margin):
        """built-up land at the point or within `margin` of it (land stops at the kerb)."""
        ring8 = [
            (margin * math.cos(k * math.pi / 4), margin * math.sin(k * math.pi / 4))
            for k in range(8)
        ]
        return lambda p: land(p) or (
            margin > 0 and any(land((p[0] + dx, p[1] + dy)) for dx, dy in ring8)
        )

    clip = geo.Inside(area.outline())
    signed = (
        []
    )  # (the sign says built-up, segment middle, km) for every signed 50/100 segment in the area
    for w in _raw(area, CLASSES["tertiary"]):
        t = w["tags"]
        v = parse_int(t.get("maxspeed"), None) or implicit(t)
        if v not in (50, 100) or t["highway"].startswith("motorway"):
            continue
        g = [geo.xy(p["lat"], p["lon"]) for p in w["geometry"]]
        for a, b in zip(g, g[1:]):
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if 0 <= mid[0] <= W and 0 <= mid[1] <= H and clip(mid):
                signed.append((v == 50, mid, math.dist(a, b) / 1000))
    km = {u: sum(L for s, _, L in signed if s == u) for u in (True, False)}
    if not km[True] or not km[False]:
        return None, None, None, None
    ladder = []
    for margin in MARGINS:
        test = near_land(margin)
        ok = {
            u: sum(L for s, p, L in signed if s == u and test(p) == u) / km[u]
            for u in (True, False)
        }
        ladder.append((abs(ok[True] - ok[False]), margin, ok[True], ok[False]))
    _, margin, ok50, ok100 = min(ladder)
    return near_land(margin), margin, ok50, ok100


def lower_ways(area, cls, rung):
    """the ways of the classes below `cls`, down to `rung`, clipped like the base: (pos, ways)."""
    pos_all, ways_all = load(area, CLASSES[rung])
    return pos_all, [w for w in ways_all if w["base"] not in CLASSES[cls]]
