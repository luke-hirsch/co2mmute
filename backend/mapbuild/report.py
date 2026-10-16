"""The heads-up lines of the build report: what the rules could not fix, each with a version to
suggest. A line is one finding; nothing here changes the map.

Places are `[(name, (x, y))]` in metres, stops `[(x, y)]`. A line is told by its key (mode, ref).

- no transport: a place with no kept line's stop within the reach — OSM has no line there and the
  timetable had none to stand in (or there is no timetable).
- snapped away: a place a kept line's stop served until the stop took its node, up to 100 m off.
- far on foot: a place a stop reaches as the crow flies, but the walk along the map's links is
  longer than the reach (cover measures the crow, the walker follows the graph).
- no morning trip: a kept line the timetable has no trip for between 8 and 10; the game plays it
  as one run a pass.
- one bus: workplaces whose only line is one bus.
- numbers: the commuter count and the stops, the counts a first look wants.
"""

import heapq
import math


def _name_list(items):
    return ", ".join(f"{name} {d:.0f} m" for name, d in items)


def nearest(point, stops):
    return min((math.dist(point, s) for s in stops), default=math.inf)


def no_transport(places, raw_stops, reach, has_feed):
    far = [
        (name, nearest(p, raw_stops))
        for name, p in places
        if nearest(p, raw_stops) > reach
    ]
    if not far:
        return None
    why = (
        "in OSM keine Linie und im Fahrplan keine, die einspringen könnte"
        if has_feed
        else "in OSM keine Linie, und es gibt keinen Fahrplan, der einspringen könnte"
    )
    return (
        f"{len(far)} Orte ohne Halt im Umkreis von {reach} m ({why}): {_name_list(far)}. "
        "Vorschlag: eine Version mit einer Linie dorthin"
    )


def snapped_away(places, raw_stops, final_stops, reach):
    out = [
        (name, nearest(p, final_stops))
        for name, p in places
        if nearest(p, raw_stops) <= reach < nearest(p, final_stops)
    ]
    if not out:
        return None
    return (
        f"{len(out)} Orte, die der Halt erst bediente, bevor er auf seinen Knoten rückte, "
        f"jetzt weiter als {reach} m: {_name_list(out)}. "
        "Vorschlag: eine Version mit einem Halt näher dran"
    )


def far_on_foot(nodes, edges, stop_ids, places, reach):
    """places: [(name, node id)]. The walk is along the walkable links, in their direction."""
    xy = {n["id"]: (n["x"] * 1000, n["y"] * 1000) for n in nodes}
    back = {}
    for e in edges:
        if e.get("walking") is False:
            continue
        a, b = e["start_node"], e["end_node"]
        length = math.dist(xy[a], xy[b]) * e.get("circuity", 1.0)
        back.setdefault(b, []).append((a, length))
    dist = {s: 0.0 for s in stop_ids}
    heap = [(0.0, s) for s in sorted(stop_ids, key=str)]
    heapq.heapify(heap)
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist.get(n, math.inf):
            continue
        for m, length in back.get(n, ()):
            nd = d + length
            if nd <= reach and nd < dist.get(m, math.inf):
                dist[m] = nd
                heapq.heappush(heap, (nd, m))
    out = [(name, n) for name, n in places if n not in dist]
    if not out:
        return None
    return (
        f"{len(out)} Orte, deren Halt zu Fuß weiter als {reach} m entfernt ist, obwohl er in "
        f"der Luftlinie näher liegt: {', '.join(name for name, _ in out)}. "
        "Vorschlag: eine Version mit einem Fußweg oder einem Halt dort"
    )


def no_morning_trip(found):
    """found: {line key: dict(n, matched)} from `timetable.match`."""
    bare = sorted(ref for (_, ref), f in found.items() if f["matched"] and not f["n"])
    if not bare:
        return None
    return (
        f"{len(bare)} Linien ohne Fahrt zwischen 8 und 10 Uhr im Fahrplan (im Spiel eine Fahrt je "
        f"Durchgang): {', '.join(bare)}. Vorschlag: eine Version mit einem eigenen Takt für sie"
    )


def one_bus(workplaces, stops_of, found, reach):
    """workplaces: [(name, (x, y))]; stops_of: {line key: [(x, y)]}, kept lines, within reach."""
    only = {}
    for _, p in workplaces:
        lines = [k for k, st in stops_of.items() if nearest(p, st) <= reach]
        if len(lines) == 1 and lines[0][0] == "bus":
            only[lines[0]] = only.get(lines[0], 0) + 1
    if not only:
        return None
    parts = []
    for k, n in sorted(only.items(), key=lambda kv: (-kv[1], kv[0])):
        f = found.get(k)
        bare = f and f["matched"] and not f["n"]
        parts.append(
            f"{k[1]} für {n} von {len(workplaces)}"
            + (" (ohne Fahrt 8–10)" if bare else "")
        )
    return (
        "Arbeitsorte, zu denen nur ein Bus fährt: "
        + ", ".join(parts)
        + ". Vorschlag: eine Version mit einer zweiten Linie oder einem dichteren Takt"
    )


def numbers(data):
    types = [set(n["types"]) for n in data["nodes"]]
    stops = sum("bus_stop" in t for t in types)
    stations = sum("station" in t for t in types)
    return (
        f"Pendler {data['map']['district_commuters']} (ein Platzhalter bis zur Kalibrierung), "
        f"Haltestellen {stops}, Bahnhöfe {stations}"
    )
