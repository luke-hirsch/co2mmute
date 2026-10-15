"""The streets and places as a game map file (the format `maps/portability.py` reads).

The largest strongly connected part is kept (a car gets back from wherever it goes); every place
takes its nearest free node, the closest pair first. A node is (x, y) in km, an edge one direction
of a street with the road's length over the straight line as `circuity`.
"""

import collections
import json
import math

from . import geo, streets

COMMUTERS = 6800  # a placeholder until `calibrate_map --out` writes the map's own count


def snap_all(net, groups):
    """every place to its nearest free node, the closest pair first, so no place is pushed off
    its node by one that merely came earlier in a list."""
    pairs = sorted(
        (math.dist(net.pos[n], geo.xy(*ll)), g, name, n)
        for g, places in enumerate(groups)
        for name, ll in places.items()
        for n in net.pos
    )
    outs = [{} for _ in groups]
    placed, taken = set(), set()
    for d, g, name, n in pairs:
        if (g, name) in placed or n in taken:
            continue
        placed.add((g, name))
        taken.add(n)
        outs[g][n] = (name, d)
    return outs


def emit(net, name, homes_at, work_at):
    homes, work = snap_all(net, [homes_at, work_at])
    ids = {n: str(i + 1) for i, n in enumerate(sorted(net.pos))}
    nodes = []
    for n, (x, y) in net.pos.items():
        types = ["intersection"]
        label = ""
        if n in homes:
            types.append("home")
            label = "Wohnort " + homes[n][0]
        if n in work:
            types.append("workplace")
            label = "Arbeit " + work[n][0]
        nodes.append(
            dict(
                id=ids[n], name=label, x=x / 1000, y=y / 1000, types=types, versions=[0]
            )
        )
    edges = []
    for u in net.adj:
        for v, r in net.adj[u].items():
            d = r["uv"]
            if not d:
                continue
            motorway = d["rank"] >= 3.5
            lanes = max(1, min(int(d["lanes"]), 6))
            street = d["names"].most_common(1)[0][0] if d["names"] else ""
            # the road over the straight line; a merged junction at its centroid can put the
            # line past the road, and the line is the floor (check_map: road-length)
            straight = math.dist(net.pos[u], net.pos[v])
            circuity = max(1.0, round(d["len"] / straight, 3)) if straight else 1.0
            edges.append(
                dict(
                    start_node=ids[u],
                    end_node=ids[v],
                    name=street[:100],
                    type="street",
                    biking=not motorway,
                    bike_lane=False,
                    walking=not motorway,
                    max_lanes=lanes,
                    speed_limit=int(round(d["speed"] / 10) * 10) or 30,
                    lanes=lanes,
                    dedicated_bus_lane=False,
                    circuity=circuity,
                    versions=[0],
                )
            )
    xs = [p[0] for p in net.pos.values()]
    ys = [p[1] for p in net.pos.values()]
    return (
        {
            "scale": 1000.0,
            "map": {
                "name": name,
                "x_dim": math.ceil(max(xs) / 1000) + 1,
                "y_dim": math.ceil(max(ys) / 1000) + 1,
                "max_player": len(homes),
                "walk_speed_kmh": 5,
                "bike_speed_kmh": 20,
                "default_car_speed_kmh": 50,
                "district_commuters": COMMUTERS,
                "calibrated": False,
            },
            "versions": [
                {
                    "name": name + " - Base",
                    "description": "",
                    "base_version": True,
                    "poll_text": "Die Karte soll ...",
                    "revert_poll_text": "Die Karte soll ...",
                    "source_version": None,
                    "compatible_versions": [],
                }
            ],
            "nodes": nodes,
            "edges": edges,
            "bus_lines": [],
            "train_lines": [],
        },
        homes,
        work,
    )


def to_map(pos, links, name, places):
    """(map file data, report lines). places: {"home <name>" | "work <name>": (lat, lon)}."""
    home_at = {
        k.removeprefix("home "): v for k, v in places.items() if k.startswith("home ")
    }
    work_at = {
        k.removeprefix("work "): v for k, v in places.items() if k.startswith("work ")
    }
    nodes = sorted({n for t in links for n in t[:2]}, key=str)
    ix = {n: i + 1 for i, n in enumerate(nodes)}
    net = geo.Graph(
        {ix[n]: pos[n] for n in nodes},
        set(ix.values()),
        [(ix[u], ix[v], f, b, g) for u, v, f, b, g in links],
    )
    before = dict(net.pos)
    names = {
        n: {streets.top_name(t) for t in links if n in (ix[t[0]], ix[t[1]])} - {""}
        for n in net.pos
    }
    net.strongly_connected()
    dropped = [n for n in before if n not in net.pos]
    data, homes, work = emit(net, name, home_at, work_at)
    say = [
        f"Knoten {len(net.pos)}, Kanten {len(data['edges'])}, Wohnorte {len(homes)} von {len(home_at)}, "
        f"Arbeitsorte {len(work)} von {len(work_at)}"
    ]
    far = sorted(((d, nm) for nm, d in {**homes, **work}.values()), reverse=True)[:5]
    say.append(
        "am weitesten von ihrem Knoten: "
        + ", ".join(f"{nm} {d:.0f} m" for d, nm in far)
    )
    if dropped:  # a one-way piece the network can't get back from, or into
        street_names = collections.Counter(nm for n in dropped for nm in names[n])
        say.append(
            f"{len(dropped)} Knoten nicht stark verbunden, weggelassen"
            + (
                f" ({', '.join(nm for nm, _ in street_names.most_common(3))})"
                if street_names
                else ""
            )
        )
    return data, say


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def street_shapes(pos, links):
    """every kept street link with its road's shape, for the lines that ride it: [{u, v, pts,
    name, fwd, bwd}] in the plane, in m."""
    return [
        dict(
            u=list(pos[u]),
            v=list(pos[v]),
            pts=[list(p) for p in g],
            name=streets.top_name(t),
            fwd=f is not None,
            bwd=b is not None,
        )
        for t in links
        for u, v, f, b, g in [t]
    ]
