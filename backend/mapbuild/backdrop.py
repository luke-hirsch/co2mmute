"""The map's own background, drawn from the OSM data the build already holds.

An SVG in the plane the nodes lie in: metres east and south of the box's north-west corner, the
size of the map's box (`x_dim` × `y_dim` km). The viewers put a background at `x_dim × 100` by
`y_dim × 100` of their units, a node at its km × 100, so a drawing whose view box is the box in
metres sits exactly under the nodes. The file carries it in `background_image`, the block the
export writes.

What is drawn, from the bottom up: residential and commercial / industrial land, parks and woods,
water, the local streets (tertiary, unclassified, residential), railways. The streets the game
keeps are drawn by the viewer on top; the drawing is the quiet ground they lie on. Colours are
mid-tones with some transparency, so they read on the light and on the dark page alike, in the
game's two colours and its grey: the blue of the car line for water, the amber of public transport
for work land, no green. Parks are dotted: pattern, not hue.

Shapes under `MIN_AREA_M2` and streets under `MIN_STREET_M` are left out, lines are simplified to
`SIMPLIFY_M` and coordinates are whole metres, written relative: the file stays small, and the
same inputs give the same bytes.

Water and parks are optional downloads: without them the drawing is made from the rest and the
report says so.
"""

import base64
import math

from . import area as area_mod
from . import download, geo

MIN_AREA_M2 = 1000.0  # a few pixels across at the zoom of a whole city
MIN_STREET_M = 40.0
SIMPLIFY_M = 3.0

# (fill, fill-opacity) per land kind; strokes are (colour, opacity, width in m)
RESIDENTIAL = ("#8b93a1", 0.22)
WORKLAND = ("#ffb300", 0.30)
WATER = ("#1e88e5", 0.40)
PARK = ("#7a9bb5", 0.65)
STREET = ("#8b93a1", 0.55, 9)
LOCAL_MAIN = ("#8b93a1", 0.70, 15)
RAIL = ("#8b93a1", 0.80, 9)
RIVER = 24  # m wide, a canal half of it
RAILWAYS = {"rail", "light_rail", "subway", "tram"}
LOCAL_MAIN_CLASSES = {"tertiary", "tertiary_link"}
LOCAL_CLASSES = LOCAL_MAIN_CLASSES | {"unclassified", "residential"}


def _project(geometry):
    return [geo.xy(p["lat"], p["lon"]) for p in geometry]


def _simplify(pts, tol=SIMPLIFY_M):
    """Douglas-Peucker, iterative (a coastline is long); the ends stay."""
    if len(pts) < 3:
        return list(pts)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        far, at = 0.0, None
        for k in range(i + 1, j):
            d = geo.point_seg(pts[k], pts[i], pts[j])
            if d > far:
                far, at = d, k
        if at is not None and far > tol:
            keep[at] = True
            stack += [(i, at), (at, j)]
    return [p for p, k in zip(pts, keep) if k]


def _area(ring):
    return (
        abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])))
        / 2
    )


def _whole(pts):
    """whole metres, a point not repeated."""
    out = []
    for x, y in pts:
        p = (round(x), round(y))
        if not out or p != out[-1]:
            out.append(p)
    return out


def _sub(pts, closed):
    """one sub-path: an absolute move to the first point, relative lines to the rest."""
    x0, y0 = pts[0]
    d = [f"M{x0} {y0}l"]
    px, py = x0, y0
    steps = []
    for x, y in pts[1:]:
        steps.append(f"{x - px} {y - py}")
        px, py = x, y
    return d[0] + " ".join(steps) + ("z" if closed else "")


def _in_view(pts, W, H):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(xs) >= 0 and min(xs) <= W and max(ys) >= 0 and min(ys) <= H


def _members(el, role):
    return [
        m
        for m in el.get("members", [])
        if m["type"] == "way" and m.get("role") == role and m.get("geometry")
    ]


def _rings(el, W, H):
    """a land element as [(outer ring, [inner rings])], in the plane, simplified, in whole metres."""
    if el["type"] == "way":
        g = el.get("geometry")
        if not g or (g[0] != g[-1] and len(g) < 4):
            return []
        outers, inners = [_project(g)], []
    else:
        outers = [
            _project([{"lat": a, "lon": b} for a, b in r])
            for r in area_mod.rings(_members(el, "outer"))
        ]
        inners = [
            _project([{"lat": a, "lon": b} for a, b in r])
            for r in area_mod.rings(
                [dict(m, role="outer") for m in _members(el, "inner")]
            )
        ]
    shapes = []
    for o in outers:
        o = _whole(_simplify(o))
        if len(o) < 3 or _area(o) < MIN_AREA_M2 or not _in_view(o, W, H):
            continue
        holes = []
        for i in inners:
            i = _whole(_simplify(i))
            if len(i) >= 3 and _area(i) >= MIN_AREA_M2 and _in_view(i, W, H):
                holes.append(i)
        shapes.append((o, holes))
    return shapes


def _land(elements, W, H):
    """the `<path>`s of a land layer, one per shape (a hole in one never opens another)."""
    out = []
    for el in sorted(elements, key=lambda e: (e["type"], e["id"])):
        for outer, holes in _rings(el, W, H):
            d = "".join(_sub(r, True) for r in [outer] + holes)
            rule = ' fill-rule="evenodd"' if holes else ""
            out.append(f'<path d="{d}"{rule}/>')
    return out


def _lines(ways, W, H, keep=lambda w: True):
    """one `d` for all the ways given: each simplified, whole metres, relative."""
    subs = []
    for w in sorted(ways, key=lambda w: w["id"]):
        if not keep(w) or not w.get("geometry"):
            continue
        pts = _project(w["geometry"])
        if geo.polylen(pts) < MIN_STREET_M:
            continue
        pts = _whole(_simplify(pts))
        if len(pts) >= 2 and _in_view(pts, W, H):
            subs.append(_sub(pts, False))
    return "".join(subs)


def _group(label, paths, style, extra=""):
    """paths of one colour, the transparency on the group: where two overlap it does not add up."""
    colour, opacity = style[0], style[1]
    if not paths:
        return ""
    return (
        f'<g id="{label}" opacity="{opacity}" fill="{colour}" stroke="none"{extra}>'
        + "".join(paths)
        + "</g>"
    )


def _stroke(label, d, style, extra=""):
    colour, opacity, width = style
    if not d:
        return ""
    return (
        f'<path id="{label}" d="{d}" fill="none" stroke="{colour}" '
        f'opacity="{opacity}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round"{extra}/>'
    )


LAYERS = {"water": "Gewässer", "green": "Grünflächen"}


def _optional(area, name, report):
    """a layer the map is drawn without when Overpass will not give it. Nothing is cached for it,
    so the next build of the area asks again and gets it."""
    try:
        return download.osm(area, name)
    except download.Missing as e:
        report.append(
            f"{LAYERS[name]} fehlen, ohne gezeichnet ({e}). "
            "Vorschlag: später noch einmal bauen, dann kommen sie dazu"
        )
        return []


def draw(area, x_dim, y_dim):
    """(the SVG as text, build report lines). The area's projection must be in use."""
    W, H = x_dim * 1000, y_dim * 1000
    report = []
    residential = download.osm(area, "residential")
    workland = download.osm(area, "workland")
    local = download.osm(area, "local")
    water = _optional(area, "water", report)
    green = _optional(area, "green", report)
    ways = {}
    for w in download.osm(area, "pt_ways"):
        if w["type"] == "way" and w.get("tags", {}).get("railway") in RAILWAYS:
            ways[w["id"]] = w
    rails = list(ways.values())

    lakes = [
        e for e in water if e.get("tags", {}).get("waterway") not in ("river", "canal")
    ]
    rivers = [
        e
        for e in water
        if e["type"] == "way"
        and e.get("tags", {}).get("waterway") in ("river", "canal")
    ]
    wide = [e for e in rivers if e["tags"]["waterway"] == "river"]
    narrow = [e for e in rivers if e["tags"]["waterway"] == "canal"]
    streets = [e for e in local if e.get("tags", {}).get("highway") in LOCAL_CLASSES]
    main = _lines(streets, W, H, lambda e: e["tags"]["highway"] in LOCAL_MAIN_CLASSES)
    rest = _lines(
        streets, W, H, lambda e: e["tags"]["highway"] not in LOCAL_MAIN_CLASSES
    )

    river = lambda d, w: (  # noqa: E731
        f'<path d="{d}" fill="none" stroke="{WATER[0]}" stroke-width="{w}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        if d
        else ""
    )
    layers = [
        _group("wohnen", _land(residential, W, H), RESIDENTIAL),
        _group("arbeit", _land(workland, W, H), WORKLAND),
        _group("gruen", _land(green, W, H), (f"url(#punkte)", 1.0)),
        _group(
            "wasser",
            _land(lakes, W, H)
            + [
                river(_lines(wide, W, H), RIVER),
                river(_lines(narrow, W, H), RIVER // 2),
            ],
            WATER,
        ),
        _stroke("strassen", rest, STREET),
        _stroke("hauptstrassen", main, LOCAL_MAIN),
        _stroke("schiene", _lines(rails, W, H), RAIL, ' stroke-dasharray="40 24"'),
    ]
    layers = [x for x in layers if x]
    defs = (
        '<defs><pattern id="punkte" width="60" height="60" patternUnits="userSpaceOnUse">'
        f'<circle cx="30" cy="30" r="10" fill="{PARK[0]}" fill-opacity="{PARK[1]}"/>'
        "</pattern></defs>"
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">' + defs + "".join(layers) + "</svg>"
    )
    report.insert(
        0,
        f"Hintergrund: {len(svg) / 1024:.0f} kB, {len(streets)} Nebenstraßen, "
        f"{len(residential)} Wohn- und {len(workland)} Arbeitsflächen, "
        f"{len(water)} Gewässer, {len(green)} Grünflächen, {len(rails)} Gleise",
    )
    return svg, report


def block(svg):
    """the `background_image` block of a map file: the drawing placed at the origin, whole, at
    scale 1 (what the viewers draw at the map's size)."""
    return {
        "scale": 1.0,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "crop_top": 0.0,
        "crop_right": 0.0,
        "crop_bottom": 0.0,
        "crop_left": 0.0,
        "filename": "hintergrund.svg",
        "data": base64.b64encode(svg.encode()).decode("ascii"),
    }
