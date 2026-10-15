"""Where the homes and the workplaces go.

A home stands for an equal share of the people, a workplace for an equal share of the jobs —
the calibration sends every home to its workplaces evenly. So:

- homes: the Zensus 2022 grid (people per 100 m cell), cut in halves of equal people along the
  longer side, again and again, to k parts (`halves`); a home sits on the part's cell its people
  live closest to on average, among its 40 most populous (`where`) — a centroid would put a
  village's home in the fields between two villages.
- workplaces: the same on GHSL's non-residential building volume (m³ per ~100 m cell).
- how many: the fewest parts that put 90 % of the people (the jobs) within two of the map's
  median streets of their own home (workplace). No cap: a bigger city gets more.
- names: the nearest OSM place (suburb … hamlet) no other home (workplace) took.

Sources: © Statistisches Bundesamt (Destatis), Zensus 2022, "Bevölkerungszahl in Gitterzellen"
(Germany only — an area outside has no homes yet, the build stops and says so). European
Commission, JRC, GHS-BUILT-V R2023A, NRES, epoch 2020, 3″ (Pesaresi, Politis 2023,
doi:10.2905/AB2F107A-03CD-47A3-85E5-139D8EC63283), CC BY 4.0.
"""

import io
import json
import math
import struct
import zipfile

from . import download, geo

REACH = 2.0  # median streets: 90 % of the people within this many of their home
SHARE = 0.9
TOP = 40  # a part's home: among its this many most populous cells
KINDS = ("suburb", "quarter", "neighbourhood", "village", "town", "hamlet")

# --- the Zensus grid: ETRS89-LAEA (EPSG:3035) cell centres, EPSG guidance note 7-2, method 9820

A, F = 6378137.0, 1 / 298.257222101  # GRS80
E2 = 2 * F - F * F
E = math.sqrt(E2)
LAT0, LON0, FE, FN = math.radians(52), math.radians(10), 4321000.0, 3210000.0


def _q(phi):
    s = math.sin(phi)
    return (1 - E2) * (
        s / (1 - E2 * s * s) - 1 / (2 * E) * math.log((1 - E * s) / (1 + E * s))
    )


QP = _q(math.pi / 2)
B0 = math.asin(_q(LAT0) / QP)
RQ = A * math.sqrt(QP / 2)
D = A * (math.cos(LAT0) / math.sqrt(1 - E2 * math.sin(LAT0) ** 2)) / (RQ * math.cos(B0))


def to_laea(lat, lon):
    phi, lam = math.radians(lat), math.radians(lon)
    b = math.asin(_q(phi) / QP)
    bb = RQ * math.sqrt(
        2
        / (
            1
            + math.sin(B0) * math.sin(b)
            + math.cos(B0) * math.cos(b) * math.cos(lam - LON0)
        )
    )
    x = FE + bb * D * math.cos(b) * math.sin(lam - LON0)
    y = FN + (bb / D) * (
        math.cos(B0) * math.sin(b) - math.sin(B0) * math.cos(b) * math.cos(lam - LON0)
    )
    return x, y


def from_laea(x, y):
    dx, dy = x - FE, y - FN
    rho = math.hypot(dx / D, D * dy)
    c = 2 * math.asin(rho / (2 * RQ))
    b = math.asin(
        math.cos(c) * math.sin(B0) + D * dy * math.sin(c) * math.cos(B0) / rho
    )
    phi = (
        b
        + (E2 / 3 + 31 * E2**2 / 180 + 517 * E2**3 / 5040) * math.sin(2 * b)
        + (23 * E2**2 / 360 + 251 * E2**3 / 3780) * math.sin(4 * b)
        + (761 * E2**3 / 45360) * math.sin(6 * b)
    )
    lam = LON0 + math.atan2(
        dx * math.sin(c),
        D * rho * math.cos(B0) * math.cos(c) - D * D * dy * math.sin(B0) * math.sin(c),
    )
    return math.degrees(phi), math.degrees(lam)


def zensus_cut(lines, bbox):
    """the grid's cells whose centre lies in bbox (s, w, n, e): [(lat, lon, people)]. `lines`: the
    CSV's lines, header first."""
    s, w, n, e = bbox
    corners = [to_laea(la, lo) for la in (s, n) for lo in (w, e)]
    x0, x1 = min(c[0] for c in corners) - 100, max(c[0] for c in corners) + 100
    y0, y1 = min(c[1] for c in corners) - 100, max(c[1] for c in corners) + 100
    out = []
    it = iter(lines)
    next(it)
    for line in it:
        _, x, y, p = line.rstrip("\n").split(";")
        x, y = int(x), int(y)
        if x0 <= x <= x1 and y0 <= y <= y1:
            la, lo = from_laea(x, y)
            if s <= la <= n and w <= lo <= e:
                out.append((round(la, 6), round(lo, 6), int(p)))
    return out


# --- GHSL: 10° tiles, BigTIFF, 256 px LZW blocks of uint32 m³ per cell, read by hand

GHSL_LON0, GHSL_LAT0 = (
    -180.0079166,
    89.0995833,
)  # the tile grid's north-west corner (tile R1_C1)


def lzw(data):
    """TIFF LZW (MSB first, early change)."""
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    width, buf, nbits, prev = 9, 0, 0, None
    for byte in data:
        buf = (buf << 8) | byte
        nbits += 8
        while nbits >= width:
            nbits -= width
            code = (buf >> nbits) & ((1 << width) - 1)
            if code == 256:
                table = table[:258]
                width, prev = 9, None
                continue
            if code == 257:
                return bytes(out)
            if prev is None:
                entry = table[code]
            elif code < len(table):
                entry = table[code]
                table.append(prev + entry[:1])
            else:
                entry = prev + prev[:1]
                table.append(entry)
            out += entry
            prev = entry
            if len(table) + 1 >= (1 << width) and width < 12:
                width += 1
    return bytes(out)


class Tile:
    def __init__(self, path):
        self.f = open(path, "rb")
        b = self.f.read(16)
        assert (
            b[:2] == b"II" and struct.unpack("<H", b[2:4])[0] == 43
        ), "BigTIFF, little-endian"
        off = struct.unpack("<Q", b[8:16])[0]
        self.f.seek(off)
        n = struct.unpack("<Q", self.f.read(8))[0]
        ent = self.f.read(20 * n)
        tags = {}
        size = {3: 2, 4: 4, 12: 8, 16: 8}
        fmt = {3: "H", 4: "I", 12: "d", 16: "Q"}
        for i in range(n):
            tag, typ, cnt = struct.unpack("<HHQ", ent[20 * i : 20 * i + 12])
            if typ not in size:
                continue
            sz = size[typ] * cnt
            raw = ent[20 * i + 12 : 20 * i + 12 + sz] if sz <= 8 else None
            if raw is None:
                self.f.seek(struct.unpack("<Q", ent[20 * i + 12 : 20 * i + 20])[0])
                raw = self.f.read(sz)
            tags[tag] = struct.unpack("<" + fmt[typ] * cnt, raw)
        assert tags[259] == (5,) and tags[258] == (32,) and tags[317] == (1,)
        self.W, self.H = tags[256][0], tags[257][0]
        self.tw = tags[322][0]
        self.offs, self.counts = tags[324], tags[325]
        self.dx, self.dy = tags[33550][0], tags[33550][1]
        self.lon0, self.lat0 = tags[33922][3], tags[33922][4]
        self.across = math.ceil(self.W / self.tw)

    def block(self, i, j):
        k = j * self.across + i
        self.f.seek(self.offs[k])
        raw = lzw(self.f.read(self.counts[k]))
        return struct.unpack(f"<{self.tw * self.tw}I", raw[: 4 * self.tw * self.tw])

    def cut(self, s, w, n, e):
        """cells whose centre lies in (s, w, n, e): [(lat, lon, m³)], zeros left out."""
        c0, c1 = max(0, int((w - self.lon0) / self.dx)), min(
            self.W - 1, int((e - self.lon0) / self.dx)
        )
        r0, r1 = max(0, int((self.lat0 - n) / self.dy)), min(
            self.H - 1, int((self.lat0 - s) / self.dy)
        )
        out = []
        for j in range(r0 // self.tw, r1 // self.tw + 1):
            for i in range(c0 // self.tw, c1 // self.tw + 1):
                if not self.counts[j * self.across + i]:
                    continue
                v = self.block(i, j)
                for y in range(self.tw):
                    r = j * self.tw + y
                    if not r0 <= r <= r1:
                        continue
                    for x in range(self.tw):
                        c = i * self.tw + x
                        if c0 <= c <= c1 and v[y * self.tw + x]:
                            lat = self.lat0 - (r + 0.5) * self.dy
                            lon = self.lon0 + (c + 0.5) * self.dx
                            if s <= lat <= n and w <= lon <= e:
                                out.append(
                                    (round(lat, 6), round(lon, 6), v[y * self.tw + x])
                                )
        return out


def ghsl_tiles(bbox):
    """the (row, column) of every GHSL tile the box touches, north-west first."""
    s, w, n, e = bbox
    rows = range(int((GHSL_LAT0 - n) // 10) + 1, int((GHSL_LAT0 - s) // 10) + 2)
    cols = range(int((w - GHSL_LON0) // 10) + 1, int((e - GHSL_LON0) // 10) + 2)
    return [(r, c) for r in rows for c in cols]


# --- the cells of an area


def _cached(area, name, cut):
    path = area.cache / name
    if not path.exists():
        path.write_text(json.dumps(cut(area.fetch_bbox)))
    return json.loads(path.read_text())


def _zensus(bbox):
    with zipfile.ZipFile(download.zensus()) as z, z.open(download.ZENSUS_CSV) as f:
        return zensus_cut(io.TextIOWrapper(f, "utf-8"), bbox)


def _ghsl(bbox):
    out = []
    for r, c in ghsl_tiles(bbox):
        tif = download.ghsl(r, c)
        if tif is not None:
            out += Tile(tif).cut(*bbox)
    return out


def cells(area, kind, inside):
    """the area's people ("zensus") or non-residential m³ ("ghsl") per cell, in the current
    projection, inside: [(x, y, amount)]."""
    raw = _cached(area, f"{kind}.json", _zensus if kind == "zensus" else _ghsl)
    pts = [(geo.xy(la, lo), v) for la, lo, v in raw]
    return [(q[0], q[1], v) for q, v in pts if inside(q)]


# --- equal shares


def where(pts, top=TOP):
    """a part's home: the cell, among its `top` most populous, from which its people live closest
    on average."""
    cand = sorted(pts, key=lambda c: -c[2])[:top]
    best = min(cand, key=lambda c: sum(p * math.dist(c[:2], (x, y)) for x, y, p in pts))
    return best[:2]


def halves(pts, k):
    """k parts with the same people: cut the part along its longer side where its people split
    k1 : k2 (k1 = k // 2), and cut each side again. [(centre, people, cells)]."""
    if k == 1:
        return [(where(pts), sum(p for *_, p in pts), pts)]
    xs, ys = [x for x, *_ in pts], [y for _, y, _ in pts]
    axis = 0 if max(xs) - min(xs) >= max(ys) - min(ys) else 1
    pts = sorted(pts, key=lambda c: c[axis])
    k1 = k // 2
    want = sum(p for *_, p in pts) * k1 / k
    acc, cut = 0, 0
    for i, (*_, p) in enumerate(pts):
        if acc + p / 2 > want:
            cut = i
            break
        acc += p
    cut = min(max(cut, k1), len(pts) - (k - k1))  # each side keeps a cell per part
    return halves(pts[:cut], k1) + halves(pts[cut:], k - k1)


def own(parts):
    """each person to their own part's centre: (median m, 90th percentile m)."""
    near = sorted(
        (math.dist((x, y), c), p) for c, _, cells in parts for x, y, p in cells
    )
    tot, acc, out = sum(p for _, p in near), 0, []
    for d, p in near:
        acc += p
        while len(out) < 2 and acc >= (0.5, SHARE)[len(out)] * tot:
            out.append(d)
    return out[0], out[1]


def count(cells, target):
    """the fewest parts with 90 % within `target` of their own part's centre (bisection)."""
    fits = lambda k: own(halves(cells, k))[1] <= target
    hi = 1
    while not fits(hi) and hi < len(cells):
        hi *= 2
    lo = hi // 2  # fails (or 0); the smallest k that fits lies in (lo, hi]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if fits(mid) else (mid, hi)
    return hi


def nearest_place(places, p, avoid=(), kinds=KINDS):
    best = None
    for e in places:
        t = e["tags"]
        if t.get("place") not in kinds or not t.get("name") or t["name"] in avoid:
            continue
        d = math.dist(p, geo.xy(e["lat"], e["lon"]))
        if best is None or d < best[0]:
            best = (d, t["name"])
    return best[1] if best else None


def rule(cells, mesh_m, places):
    """equal shares: ({name: (lat, lon)}, (k, median m, p90 m)), the largest share first."""
    k = count(cells, REACH * mesh_m)
    parts = halves(cells, k)
    md, p90 = own(parts)
    out = {}
    for c, _, _ in sorted(parts, key=lambda t: -t[1]):
        name = nearest_place(places, c, set(out)) or f"Ort {len(out) + 1}"
        out[name] = geo.to_latlon(c)
    return out, (k, md, p90)


def places_of(area, mesh_m, inside):
    """the area's homes and workplaces: ({"home <name>" | "work <name>": (lat, lon)}, report lines)."""
    people = cells(area, "zensus", inside)
    if not people:
        raise download.Missing(
            "Keine Zensus-Zellen in diesem Gebiet: die Wohnorte kommen aus dem Zensus 2022, und der "
            "deckt nur Deutschland ab."
        )
    jobs = cells(area, "ghsl", inside)
    if not jobs:
        raise download.Missing(
            "Keine GHSL-Zellen in diesem Gebiet: ohne Gebäude keine Arbeitsorte."
        )
    places = download.osm(area, "places")
    homes, (k, md, p90) = rule(people, mesh_m, places)
    say = [
        f"Wohnorte: {k}, gleich viele Menschen je Wohnort; 90 % wohnen höchstens {p90:.0f} m von ihrem "
        f"(zwei mittlere Straßen = {REACH * mesh_m:.0f} m), die Hälfte {md:.0f} m"
    ]
    work, (k, md, p90) = rule(jobs, mesh_m, places)
    say.append(
        f"Arbeitsorte: {k}, gleich viel Arbeit je Arbeitsort; 90 % höchstens {p90:.0f} m von ihrem, "
        f"die Hälfte {md:.0f} m"
    )
    return {
        **{f"home {n}": ll for n, ll in homes.items()},
        **{f"work {n}": ll for n, ll in work.items()},
    }, say
