"""What is built: a place's administrative boundary, or a box.

A place name goes to Nominatim. Of the administrative boundaries it returns that are a whole
municipality, the most local one is the area: "Bremen" is a city and a state, the city wins;
"Callenberg" is a Gemeinde and one of its Ortsteile, the Gemeinde wins. The boundary's outer ways
are joined into rings and the largest is kept (Bremen's port in Bremerhaven, 50 km north, goes; the
report says so). Roads are kept `PAD` past the boundary, so a road that leaves the area and comes
back is still one road.

A box (`--bbox`) is built as it is: no boundary, no pad.
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import download, geo

PAD = 1000.0  # m of road kept past a boundary
MUNICIPALITY = {
    "city",
    "town",
    "village",
    "municipality",
}  # Nominatim's addresstype of a Gemeinde


def slug(name):
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


@dataclass
class Area:
    name: str
    bbox: (
        tuple  # south, west, north, east: the boundary's own box, or the box asked for
    )
    cache: Path  # where this area's downloads lie
    boundary: list = (
        None  # the boundary's outer rings [[(lat, lon), …]], none for a box
    )
    pad: float = 0.0
    cls: str = "secondary"  # the street classes the map is built from, and up
    notes: list = field(default_factory=list)  # for the build report

    @property
    def box(self):
        """the box the build projects into: the area and its pad."""
        return geo.pad(self.bbox, self.pad) if self.pad else tuple(self.bbox)

    @property
    def fetch_bbox(self):
        """the box the downloads cover: the projection's, rounded outwards to 1e-5°."""
        s, w, n, e = self.box
        f = 1e5
        return (
            math.floor(s * f) / f,
            math.floor(w * f) / f,
            math.ceil(n * f) / f,
            math.ceil(e * f) / f,
        )

    def outline(self):
        """the area's outline as segments in the current projection: the boundary, else the box."""
        if self.boundary is None:
            W, H = geo.size()
            c = [(0, 0), (W, 0), (W, H), (0, H), (0, 0)]
            return list(zip(c, c[1:]))
        segs = []
        for ring in self.boundary:
            g = [geo.xy(lat, lon) for lat, lon in ring]
            segs += list(zip(g, g[1:]))
        return segs

    def inside(self):
        """the test for homes, workplaces and lines: inside the boundary, else inside the box."""
        if self.boundary is None:
            W, H = geo.size()
            return lambda q: 0 <= q[0] <= W and 0 <= q[1] <= H
        return geo.Inside(self.outline())

    def clip(self):
        """the test for roads: inside the boundary or within the pad of it, else inside the box."""
        if self.boundary is None:
            W, H = geo.size()
            return lambda p: 0 <= p[0] <= W and 0 <= p[1] <= H
        inside = geo.Inside(self.outline())
        if self.pad > 0:
            near = geo.near_segments(self.outline(), self.pad)
            return lambda p: inside(p) or near(p)
        return inside

    def use(self):
        geo.use(self.box)
        return self


def rings(members):
    """outer ways → closed rings of (lat, lon), joined end to end."""
    ways = [
        [(p["lat"], p["lon"]) for p in m["geometry"]]
        for m in members
        if m["type"] == "way" and m.get("role") == "outer"
    ]
    out = []
    while ways:
        ring = ways.pop()
        while ring[0] != ring[-1]:
            for i, w in enumerate(ways):
                if w[0] == ring[-1]:
                    ring += w[1:]
                elif w[-1] == ring[-1]:
                    ring += w[::-1][1:]
                elif w[-1] == ring[0]:
                    ring = w[:-1] + ring
                elif w[0] == ring[0]:
                    ring = w[::-1][:-1] + ring
                else:
                    continue
                ways.pop(i)
                break
            else:
                break  # an open ring: OSM's data is broken there, keep what joined
        out.append(ring)
    return out


def km2(ring):
    lat0 = sum(p[0] for p in ring) / len(ring)
    kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.574
    pts = [(lon * kx, lat * ky) for lat, lon in ring]
    return (
        abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2
    )


def _resolve(name):
    hits = [
        h
        for h in download.nominatim(name)
        if h["osm_type"] == "relation"
        and h["category"] == "boundary"
        and h["type"] == "administrative"
    ]
    if not hits:
        raise download.Missing(
            f"Nominatim kennt keine Verwaltungsgrenze namens {name!r}."
        )
    # a whole municipality, never a part of one
    whole = [h for h in hits if h.get("addresstype") in MUNICIPALITY] or hits
    return max(whole, key=lambda h: h["place_rank"])


def named(name, root=None):
    """the area of a place name, from the cache or, the first time, from Nominatim and Overpass."""
    d = download.cache_root(root) / slug(name)
    if not (d / "area.json").exists():
        hit = _resolve(name)
        rel = download.overpass(
            f"[out:json][timeout:300];relation({hit['osm_id']});out geom;"
        )["elements"][0]
        rs = sorted(rings(rel["members"]), key=km2, reverse=True)
        keep = rs[0]
        dropped = []
        for r in rs[1:]:
            c = (sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r))
            dropped.append(f"{km2(r):.1f} km² bei {c[0]:.3f}, {c[1]:.3f}")
        lats, lons = [p[0] for p in keep], [p[1] for p in keep]
        d.mkdir(parents=True, exist_ok=True)
        rel["members"] = [
            {
                "type": "way",
                "role": "outer",
                "geometry": [{"lat": a, "lon": b} for a, b in keep],
            }
        ]
        (d / "boundary.json").write_text(json.dumps({"elements": [rel]}))
        meta = dict(
            name=name,
            relation=hit["osm_id"],
            display_name=hit["display_name"],
            bbox=[round(v, 5) for v in (min(lats), min(lons), max(lats), max(lons))],
            km2=round(km2(keep), 1),
            dropped=dropped,
        )
        (d / "area.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return load(d, pad=PAD)


def box(bbox, name=None, root=None):
    """a box (south, west, north, east) built as it is."""
    s, w, n, e = (round(v, 5) for v in bbox)
    if not (s < n and w < e):
        raise ValueError("Die Box ist leer: Süden < Norden und Westen < Osten.")
    d = download.cache_root(root) / slug(f"box {s} {w} {n} {e}")
    if not (d / "area.json").exists():
        d.mkdir(parents=True, exist_ok=True)
        (d / "area.json").write_text(
            json.dumps(
                dict(name=name or f"Box {s}, {w}, {n}, {e}", bbox=[s, w, n, e]),
                indent=1,
            )
        )
    a = load(d)
    if name:
        a.name = name
    return a


def load(d, pad=0.0, cls="secondary"):
    """an area from its cache directory: area.json, and boundary.json when it has one."""
    meta = json.loads((d / "area.json").read_text())
    boundary = None
    if (d / "boundary.json").exists():
        rel = json.loads((d / "boundary.json").read_text())["elements"][0]
        boundary = [
            [(p["lat"], p["lon"]) for p in m["geometry"]]
            for m in rel["members"]
            if m["type"] == "way" and m.get("role") == "outer"
        ]
    a = Area(
        name=meta["name"],
        bbox=tuple(meta["bbox"]),
        cache=d,
        boundary=boundary,
        pad=pad if boundary else 0.0,
        cls=cls,
    )
    dropped = meta.get("dropped")
    for part in dropped if isinstance(dropped, list) else ():
        a.notes.append(f"Teil der Grenze weggelassen: {part}")
    return a
