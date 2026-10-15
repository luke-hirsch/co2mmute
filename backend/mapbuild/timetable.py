"""The timetable: each kept line's interval, and the timetable's line where OSM has none.

Intervals: the timetable's, else OSM's `interval:peak` / `interval`, else the mode's default
(`DEFAULT_INTERVAL`) — per area (no feed: abroad, no network) and per line (not in the feed).

The feeds are DELFI's timetables for Germany as GTFS (gtfs.de, CC BY 4.0, the next 30 days): `nv`
local transit (U-Bahn, tram, bus), `rv` regional rail (S-Bahn, RB, RE). An area keeps one weekday
of them, at the stops in its box: the weekday in the feed with the most of the area's trips
8:00–10:00 (a school day without a holiday list — Berlin's routes run 3 % fewer in its
Herbstferien, Bremen's 9 %). The game's morning plays a two-hour window from an hour before
`morning_departure_hour` (9), so a line's count is its departures 8:00–10:00 a direction, at the
station in the area where it runs most often.

Stand-ins: a place no OSM line reaches gets the timetable's line that reaches it. The feed has
stops and times, no shapes, so a stand-in is a relation like OSM's, tagged source=timetable, and
the rest of the build takes it unchanged:
  - one relation per stop pattern of the route inside the area (a trip's stops in order); a
    pattern that lies within a longer one of the same route goes;
  - its stops are node members (the feed's name and place);
  - its road is the shortest way between two stops over OSM's roads, from the road node nearest
    each stop (on the largest connected piece), one-way streets one way unless open to buses;
    cut into way members at the OSM ways it runs on, their tags kept. A hop with no way is a
    straight piece (highway "(straight)").
  Only routes that could matter are built: a stop within `REACHES[1]` of a place no OSM line has a
  stop within `REACHES[0]` of.
"""

import collections
import csv
import datetime
import heapq
import io
import json
import math
import zipfile

from . import download, geo

WINDOW = (8 * 3600, 10 * 3600)
# OSM's mode (lines.mode) -> the feed and the GTFS route_type that carry it
FEED_OF = {
    "U-Bahn": ("nv", {"1"}),
    "tram": ("nv", {"0"}),
    "bus": ("nv", {"3"}),
    "S-Bahn (light_rail)": ("rv", {"2"}),
    "train: regional / S": ("rv", {"2"}),
}
# where neither the timetable nor OSM has an interval: a default per mode for all of Germany; no
# source, a compromise the editor corrects for a city that runs more or less often
DEFAULT_INTERVAL = {
    "U-Bahn": 5,
    "S-Bahn (light_rail)": 10,
    "train: regional / S": 60,
    "tram": 15,
    "bus": 20,
}
REACHES = (
    500,
    1000,
)  # m: a place without an OSM stop within the first, a stand-in stop within the second
ROUTE_TAG = {"0": "tram", "1": "subway", "2": "train", "3": "bus", "11": "trolleybus"}
FIRST_ID = -1_000_000_000  # stand-ins' ids count down from here, clear of OSM's


# --- the area's day out of the feeds


def _rows(z, name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))


def _active(z, date):
    """service_ids running on date: calendar's weekday and range, then calendar_dates' exceptions."""
    day = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:]))
    wd = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[
        day.weekday()
    ]
    on = {
        r["service_id"]
        for r in _rows(z, "calendar.txt")
        if r[wd] == "1" and r["start_date"] <= date <= r["end_date"]
    }
    for r in _rows(z, "calendar_dates.txt"):
        if r["date"] == date:
            (on.add if r["exception_type"] == "1" else on.discard)(r["service_id"])
    return on


def _secs(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _stop_times(z):
    """(trip_id, stop_id, stop_sequence, departure) of every stop time, read fast: the first
    columns are never quoted."""
    with z.open("stop_times.txt") as f:
        head = f.readline().decode().strip().split(",")
        it, idep, istop, iseq = (
            head.index(k)
            for k in ("trip_id", "departure_time", "stop_id", "stop_sequence")
        )
        for line in f:
            p = line.decode().split(",", 6)
            yield p[it], p[istop], p[iseq], p[idep]


def extract(feeds, bbox, date=None):
    """one weekday of the feeds at the stops in bbox: {"date", "routes", "stops", "trips"}.
    feeds: {"rv": zip path, "nv": zip path}."""
    s, w, n, e = bbox
    F_all = {}
    for feed in ("rv", "nv"):
        z = zipfile.ZipFile(feeds[feed])
        names = {}
        for r in _rows(z, "stops.txt"):
            if not r["stop_lat"]:
                continue
            lat, lon = float(r["stop_lat"]), float(r["stop_lon"])
            if s <= lat <= n and w <= lon <= e:
                names[r["stop_id"]] = [
                    r["stop_name"],
                    lat,
                    lon,
                    r["parent_station"] or r["stop_name"],
                ]
        F_all[feed] = dict(
            z=z,
            names=names,
            routes={r["route_id"]: r for r in _rows(z, "routes.txt")},
            agency={r["agency_id"]: r["agency_name"] for r in _rows(z, "agency.txt")},
            trips={
                r["trip_id"]: (r["route_id"], r["service_id"])
                for r in _rows(z, "trips.txt")
            },
        )
    if not date:
        # the trips that stop in the box 8-10, any day, then the weekday that runs most of them
        touch = collections.Counter()  # (feed, service) -> trips
        for feed, F in F_all.items():
            seen = set()
            for tid, sid, _, dep in _stop_times(F["z"]):
                if sid not in F["names"] or not WINDOW[0] <= _secs(dep) < WINDOW[1]:
                    continue
                if tid not in seen:
                    seen.add(tid)
                    touch[feed, F["trips"][tid][1]] += 1
        cal = next(iter(F_all.values()))
        days = list(_rows(cal["z"], "calendar.txt"))
        d0 = datetime.datetime.strptime(
            min(r["start_date"] for r in days), "%Y%m%d"
        ).date()
        d1 = datetime.datetime.strptime(
            max(r["end_date"] for r in days), "%Y%m%d"
        ).date()
        weekdays = [d0 + datetime.timedelta(i) for i in range((d1 - d0).days + 1)]
        weekdays = [d.strftime("%Y%m%d") for d in weekdays if d.weekday() < 5]
        on = {
            (feed, dt): _active(F["z"], dt)
            for feed, F in F_all.items()
            for dt in weekdays
        }
        count = {
            dt: sum(c for (feed, sv), c in touch.items() if sv in on[feed, dt])
            for dt in weekdays
        }
        date = max(weekdays, key=lambda dt: (count[dt], -int(dt)))
    out = {"date": date, "routes": {}, "stops": {}, "trips": {}}
    for feed, F in F_all.items():
        on = _active(F["z"], date)
        for tid, sid, seq, dep in _stop_times(F["z"]):
            if sid not in F["names"]:
                continue
            rid, sv = F["trips"][tid]
            if sv not in on:
                continue
            t = out["trips"].setdefault(f"{feed}:{tid}", [f"{feed}:{rid}", []])
            t[1].append([int(seq), f"{feed}:{sid}", _secs(dep)])
            out["stops"][f"{feed}:{sid}"] = F["names"][sid]
            r = F["routes"][rid]
            out["routes"][f"{feed}:{rid}"] = [
                r["route_short_name"],
                r["route_type"],
                F["agency"].get(r["agency_id"], r["agency_id"]),
            ]
    for t in out["trips"].values():
        t[1].sort()
    return out


def of_area(area):
    """the area's day of the feeds, cut once and cached; None when there is none (abroad)."""
    path = area.cache / "timetable.json"
    if not path.exists():
        try:
            feeds = {f: download.gtfs(f) for f in ("rv", "nv")}
        except download.Missing:
            return None
        d = extract(feeds, area.fetch_bbox)
        if not d["trips"]:
            return None
        path.write_text(json.dumps(d))
    return json.loads(path.read_text())


# --- intervals


def game_interval(n):
    """the whole minutes whose round(120 / interval) runs (sim/linkqueue.py) come closest to n
    departures; none in the window plays the engine's least, one run a pass."""
    if not n:
        return 120
    return min(
        range(1, 121), key=lambda iv: (abs(round(120 / iv) - n), abs(iv - 120 / n))
    )


def norm(ref):
    return ref.replace(" ", "").upper()


def counts(trips, stops, inside):
    """departures 8:00-10:00 per station and direction. A station is the stop's parent_station
    (its name where it has none), so both platforms of a place agree; a direction is the order a
    trip passes two stations in. A trip counts once at a station (a loop at its end passes twice).
    """
    seqs = []
    for tid in trips:
        seq = [
            (stops[s][3], t, geo.xy(stops[s][1], stops[s][2])) for _, s, t in trips[tid]
        ]
        seq = [x for x in seq if inside(x[2])]
        if len(seq) >= 2:
            seqs.append(seq)
    if not seqs:
        return {}
    ref = max(seqs, key=len)
    pos = {x[0]: i for i, x in enumerate(ref)}

    def direction(seq):
        idx = [pos[x[0]] for x in seq if x[0] in pos]
        if len(idx) >= 2:
            return 0 if idx[-1] > idx[0] else 1
        return 2  # no two stations shared with the reference trip

    c = collections.defaultdict(lambda: collections.Counter())
    for seq in seqs:
        d = direction(seq)
        seen = set()
        for nm, t, _ in seq[
            :-1
        ]:  # a trip's last stop in the area is not a departure on the line
            if WINDOW[0] <= t < WINDOW[1] and nm not in seen:
                seen.add(nm)
                c[d][nm] += 1
    return c


def osm_interval(rs):
    """OSM's interval:peak, else interval, over a line's relations (the shortest)."""
    from .lines import minutes

    for k in ("interval:peak", "interval"):
        ivs = [
            minutes(r["tags"][k])
            for r in rs
            if k in r["tags"] and minutes(r["tags"][k])
        ]
        if ivs:
            return min(ivs)
    return None


def match(extract, d, kept):
    """each kept line's GTFS routes and its departures 8-10: {line: dict(n, iv, matched)}."""
    if extract is None:
        return {}
    g = extract
    inside = d["inside"]
    stops = g["stops"]
    by_route = collections.defaultdict(list)
    for tid, (rid, _) in g["trips"].items():
        by_route[rid].append(tid)
    trips = {tid: st for tid, (_, st) in g["trips"].items()}
    found = {}
    for k in kept:
        md, ref = k
        feed, types = FEED_OF[md]
        osm_stops = [p for r in d["lines"][k] for _, p in d["stops_of"][r["id"]]]
        cands = []
        for rid, (short, rtype, ag) in g["routes"].items():
            if (
                not rid.startswith(feed + ":")
                or rtype not in types
                or norm(short) != norm(ref)
            ):
                continue
            pts = {
                geo.xy(stops[s][1], stops[s][2])
                for tid in by_route[rid]
                for _, s, _ in trips[tid]
            }
            near = sum(
                any(math.dist(p, q) <= 200 for q in pts) for p in osm_stops
            ) / len(osm_stops)
            if near >= 0.5:
                cands.append((rid, ag, near))
        tids = [t for rid, _, _ in cands for t in by_route[rid]]
        c = counts({t: trips[t] for t in tids}, stops, inside)
        per_dir = [max(c[dn].values()) for dn in (0, 1) if c.get(dn)]
        n = max(per_dir) if per_dir else 0
        found[k] = dict(
            n=n, iv=game_interval(n) if cands else None, matched=bool(cands)
        )
    return found


def rule(extract, d, kept):
    """{(mode, ref): (minutes, source)} for the kept lines: the timetable, else OSM, else default."""
    found = match(extract, d, kept)
    out = {}
    for k in kept:
        f = found.get(k)
        if f and f["matched"]:
            out[k] = (f["iv"], "timetable")
        elif osm_interval(d["lines"][k]):
            out[k] = (osm_interval(d["lines"][k]), "OSM")
        else:
            out[k] = (DEFAULT_INTERVAL[k[0]], "default")
    return out


# --- stand-ins


def osm_modes(feed, rtype):
    """the OSM modes (lines.mode) a GTFS route of this feed and type can be."""
    return {m for m, (f, ts) in FEED_OF.items() if f == feed and rtype in ts}


class Roads:
    """OSM's roads of the area as a directed graph over node ids."""

    def __init__(self, area):
        self.pos, self.ll, self.adj, self.tags = (
            {},
            {},
            collections.defaultdict(list),
            {},
        )
        for f in ("roads", "local"):
            for w in download.osm(area, f):
                if (
                    w["type"] != "way"
                    or len(w.get("nodes", ())) != len(w.get("geometry", ()))
                    or w["id"] in self.tags
                ):
                    continue
                t = w.get("tags", {})
                self.tags[w["id"]] = t
                pts = [geo.xy(g["lat"], g["lon"]) for g in w["geometry"]]
                for n, p, gg in zip(w["nodes"], pts, w["geometry"]):
                    self.pos[n] = p
                    self.ll[n] = {"lat": gg["lat"], "lon": gg["lon"]}
                ow = t.get("oneway", "no")
                if t.get("oneway:bus") == "no" or t.get("oneway:psv") == "no":
                    ow = "no"
                elif t.get("junction") in ("roundabout", "circular") and ow == "no":
                    ow = "yes"
                for a, b in zip(w["nodes"], w["nodes"][1:]):
                    L = math.dist(self.pos[a], self.pos[b])
                    if ow != "-1":
                        self.adj[a].append((b, L, w["id"]))
                    if ow in ("no", "-1"):
                        self.adj[b].append((a, L, w["id"]))
        # a stop snaps to the largest connected piece: a road the download cuts off (reached
        # over a service road it doesn't hold) would leave the bus no way on
        und = collections.defaultdict(set)
        for x, es in self.adj.items():
            for y, _, _ in es:
                und[x].add(y)
                und[y].add(x)
        main, seen = set(), set()
        for n in und:
            if n in seen:
                continue
            part, st = {n}, [n]
            while st:
                for y in und[st.pop()]:
                    if y not in part:
                        part.add(y)
                        st.append(y)
            seen |= part
            if len(part) > len(main):
                main = part
        self.grid = collections.defaultdict(list)
        for n in main:
            p = self.pos[n]
            self.grid[int(p[0] // 200), int(p[1] // 200)].append(n)

    def nearest(self, p):
        i, j = int(p[0] // 200), int(p[1] // 200)
        for r in range(0, 50):
            near = [
                n
                for a in range(i - r, i + r + 1)
                for b in range(j - r, j + r + 1)
                for n in self.grid.get((a, b), ())
            ]
            if near:
                n = min(near, key=lambda n: math.dist(p, self.pos[n]))
                return n, math.dist(p, self.pos[n])
        return None, math.inf

    def path(self, a, b):
        """[(node, way id that led to it)] from a to b, shortest by length; None when b is out of
        reach within ten times the straight line plus 2 km."""
        if a == b:
            return [(a, None)]
        bound = 10 * math.dist(self.pos[a], self.pos[b]) + 2000
        dist, prev = {a: 0.0}, {}
        q = [(0.0, a)]
        while q:
            d, n = heapq.heappop(q)
            if n == b:
                out = [(b, prev[b][1])]
                while out[-1][0] != a:
                    m, _ = prev[out[-1][0]]
                    out.append((m, prev[m][1] if m in prev else None))
                return out[::-1]
            if d > dist.get(n, math.inf) or d > bound:
                continue
            for m, L, wid in self.adj[n]:
                if d + L < dist.get(m, math.inf):
                    dist[m] = d + L
                    prev[m] = (n, wid)
                    heapq.heappush(q, (d + L, m))
        return None


def _candidates(g, osm_keys, places, osm_stop_pts, inside):
    """the area's timetable routes OSM has no line for, that have a stop within the larger reach
    of a place no OSM line serves within the smaller: {rid: (pattern stop lists)}."""
    small, large = REACHES
    have = {(m, norm(r)) for m, r in osm_keys}
    lonely = [
        q for q in places if not any(math.dist(q, p) <= small for p in osm_stop_pts)
    ]
    if not lonely:
        return {}
    stops = g["stops"]
    xy = {s: geo.xy(v[1], v[2]) for s, v in stops.items()}
    trips = collections.defaultdict(list)
    for tid, (rid, st) in g["trips"].items():
        trips[rid].append([s for _, s, _ in st if inside(xy[s])])
    out = {}
    for rid, (short, rtype, _) in g["routes"].items():
        feed = rid.split(":")[0]
        if rtype not in ROUTE_TAG or any(
            (m, norm(short)) in have for m in osm_modes(feed, rtype)
        ):
            continue
        seqs = [s for s in trips[rid] if len(s) >= 2]
        if not any(
            math.dist(q, xy[s]) <= large for q in lonely for sq in seqs for s in sq
        ):
            continue
        # patterns, most trips first; one inside a longer one of the route goes
        count = collections.Counter(tuple(s) for s in seqs)
        pats = sorted(count, key=lambda p: (-len(p), -count[p]))
        kept = []
        for p in pats:
            if not any(
                len(k) > len(p)
                and any(k[i : i + len(p)] == p for i in range(len(k) - len(p) + 1))
                for k in kept
            ):
                kept.append(p)
        out[rid] = kept
    return out


def _stand_ins(g, cands, roads, report):
    """relations, nodes and ways like OSM's for the candidate routes."""
    next_id = [FIRST_ID]

    def new_id():
        next_id[0] -= 1
        return next_id[0]

    def piece(run, wid):
        key = (wid, tuple(run))
        if key not in piece_id:
            pid = new_id()
            piece_id[key] = pid
            ways[pid] = {
                "type": "way",
                "id": pid,
                "nodes": list(run),
                "tags": dict(roads.tags.get(wid, {})),
                "geometry": [roads.ll[n] for n in run],
            }
        return piece_id[key]

    stops = g["stops"]
    rels, nodes, ways = [], {}, {}
    stop_node = {}
    piece_id = {}
    for rid, pats in cands.items():
        short, rtype, agency = g["routes"][rid]
        for pat in pats:
            members, hops = [], []
            for s in pat:
                if s not in stop_node:
                    nid = new_id()
                    stop_node[s] = nid
                    name, lat, lon, _ = stops[s]
                    nodes[nid] = {
                        "type": "node",
                        "id": nid,
                        "lat": lat,
                        "lon": lon,
                        "tags": {
                            "name": name,
                            "public_transport": "platform",
                            "source": "timetable",
                        },
                    }
                members.append({"type": "node", "ref": stop_node[s], "role": "stop"})
            at = []
            for s in pat:
                n, d = roads.nearest(geo.xy(stops[s][1], stops[s][2]))
                at.append(n)
                report["snap"].append(d)
            for a, b in zip(at, at[1:]):
                if a is None or b is None or a == b:
                    continue
                p = roads.path(a, b)
                if p is None:
                    report["straight"] += 1
                    key = ("straight", a, b)
                    if key not in piece_id:
                        wid = new_id()
                        piece_id[key] = wid
                        ways[wid] = {
                            "type": "way",
                            "id": wid,
                            "nodes": [a, b],
                            "tags": {"highway": "(straight)"},
                            "geometry": [roads.ll[n] for n in (a, b)],
                        }
                    hops.append(piece_id[key])
                    continue
                report["hops"] += 1
                # cut at the OSM ways it runs on
                run = [p[0][0]]
                cur = p[1][1] if len(p) > 1 else None
                for n, w in p[1:]:
                    if w != cur:
                        hops.append(piece(run, cur))
                        run, cur = [run[-1]], w
                    run.append(n)
                if len(run) >= 2:
                    hops.append(piece(run, cur))
            members += [{"type": "way", "ref": w, "role": ""} for w in hops]
            rels.append(
                {
                    "type": "relation",
                    "id": new_id(),
                    "members": members,
                    "tags": {
                        "type": "route",
                        "route": ROUTE_TAG[rtype],
                        "ref": short,
                        "name": f"{short} (timetable)",
                        "operator": agency,
                        "source": "timetable",
                    },
                }
            )
    return rels, nodes, ways


def add_stand_ins(area, extract, lines, stops_of, ways, nodes, places, inside):
    """put the stand-ins into the lines, stops, ways and nodes: (their keys, a report)."""
    from .lines import mode

    report = dict(snap=[], hops=0, straight=0, routes=0, feed=extract is not None)
    if extract is None:
        return [], report
    osm_keys = list(lines)
    pts = places["home"] + places["workplace"]
    osm_stop_pts = [
        p
        for k, rs in lines.items()
        if k[0] not in ("night", "train: long distance")
        for r in rs
        for _, p in stops_of[r["id"]]
    ]
    cands = _candidates(extract, osm_keys, pts, osm_stop_pts, inside)
    report["routes"] = len(cands)
    if not cands:
        return [], report
    rels, new_nodes, new_ways = _stand_ins(extract, cands, Roads(area), report)
    nodes.update(new_nodes)
    ways.update(new_ways)
    keys = set()
    for r in rels:
        seq = []
        for m in r["members"]:
            if m["type"] == "node":
                n = nodes[m["ref"]]
                p = geo.xy(n["lat"], n["lon"])
                if inside(p):
                    seq.append((n["tags"]["name"], p))
        if len(seq) < 2:
            continue
        k = (mode(r["tags"]), r["tags"]["ref"])
        lines[k].append(r)
        stops_of[r["id"]] = seq
        keys.add(k)
    return sorted(keys), report
