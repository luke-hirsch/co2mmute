"""Changes on a co2mmute map as versions, over the instance's own API.

    python3 versions.py maps
    python3 versions.py find <map> <text>
    python3 versions.py route <map> <from node> <to node>
    python3 versions.py add <map> <change.json>
    python3 versions.py ballot <map> <version> [<version> ...]
    python3 versions.py list <map>
    python3 versions.py delete <map> <version>
    python3 versions.py export <map> <out.json>

<map>, <version> and <node> are ids, as `maps`, `list` and `find` print them.
Every change is drawn on the base version. The instance and a staff account
come from CO2MMUTE_URL (default http://127.0.0.1:8000, Django itself),
CO2MMUTE_USER and CO2MMUTE_PASSWORD. Standard library only.
"""

import heapq
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("CO2MMUTE_URL", "http://127.0.0.1:8000").rstrip("/")
MAX_CHANGES = 4
KINDS = ("bus_lane", "interval", "close", "bus_line", "footpath")


class Api:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self._login()

    def _csrf(self):
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value
        return ""

    def _login(self):
        user = os.environ.get("CO2MMUTE_USER")
        password = os.environ.get("CO2MMUTE_PASSWORD")
        if not user or not password:
            sys.exit("CO2MMUTE_USER und CO2MMUTE_PASSWORD fehlen.")
        self.opener.open(BASE + "/accounts/login/")
        body = urllib.parse.urlencode(
            {
                "username": user,
                "password": password,
                "csrfmiddlewaretoken": self._csrf(),
            }
        ).encode()
        request = urllib.request.Request(
            BASE + "/accounts/login/",
            data=body,
            headers={"Referer": BASE + "/accounts/login/"},
        )
        self.opener.open(request)
        if not any(cookie.name == "sessionid" for cookie in self.jar):
            sys.exit("Anmeldung abgelehnt: Name, Passwort oder CO2MMUTE_URL prüfen.")

    def call(self, method, path, payload=None, raw=False):
        data = None
        headers = {
            "X-CSRFToken": self._csrf(),
            "Referer": BASE + "/",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            BASE + path, data=data, headers=headers, method=method
        )
        try:
            with self.opener.open(request) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            sys.exit(f"{method} {path}: {error.code} {error.read().decode()[:500]}")
        if raw:
            return body
        return json.loads(body) if body else None


def rows(answer):
    return answer["results"] if isinstance(answer, dict) else answer


def all_versions(api, map_id):
    return rows(api.call("GET", f"/api/maps/{map_id}/versions/"))


def base_version(api, map_id):
    for version in all_versions(api, map_id):
        if version["base_version"]:
            return version
    sys.exit(f"Karte {map_id} hat keine Basisversion.")


class Graph:
    """One version's graph, with the names a person would use for it."""

    def __init__(self, api, map_id, version_id=None):
        path = (
            f"/api/maps/{map_id}/graph/baseversion/"
            if version_id is None
            else f"/api/maps/{map_id}/graph/version/{version_id}/"
        )
        data = api.call("GET", path)
        self.version_id = data["version_id"]
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = {e["id"]: e for e in data["edges"]}
        self.lines = data["bus_lines"] + data["train_lines"]
        self.at = {}
        for edge in self.edges.values():
            self.at.setdefault(edge["start_node"], []).append(edge)
            self.at.setdefault(edge["end_node"], []).append(edge)
        self.lines_on = {}
        for line in self.lines:
            for edge_id in line["edges"]:
                self.lines_on.setdefault(edge_id, set()).add(line_label(line))

    def node_label(self, node_id):
        node = self.nodes[node_id]
        if node["name"]:
            return f"{node['name']} ({node_id})"
        streets = sorted({e["name"] for e in self.at.get(node_id, []) if e["name"]})
        if streets:
            return "Ecke " + " / ".join(streets[:3]) + f" ({node_id})"
        return f"Knoten {node_id}"

    def edge_line(self, edge):
        street = edge["street_edge"]
        bits = [f"Kante {edge['id']}"]
        bits.append(
            f"{self.node_label(edge['start_node'])} → {self.node_label(edge['end_node'])}"
        )
        if street:
            lanes = f"{street['lanes']} Spur" + ("en" if street["lanes"] != 1 else "")
            bits.append(f"{lanes}, {street['speed_limit']} km/h")
            if street["dedicated_bus_lane"]:
                bits.append("Busspur")
        elif edge["train_edge"]:
            bits.append("Schiene")
        else:
            bits.append("Weg")
        if edge["id"] in self.lines_on:
            bits.append("Linien " + ", ".join(sorted(self.lines_on[edge["id"]])))
        return " · ".join(bits)

    def stretches(self, name):
        """The edges called `name`, in pieces that touch each other."""
        named = [
            e for e in self.edges.values() if e["name"] == name and e["street_edge"]
        ]
        left = {e["id"] for e in named}
        pieces = []
        while left:
            first = min(left)
            piece, todo = set(), [first]
            while todo:
                edge = self.edges[todo.pop()]
                if edge["id"] in piece:
                    continue
                piece.add(edge["id"])
                for node in (edge["start_node"], edge["end_node"]):
                    for other in self.at.get(node, []):
                        if other["id"] in left and other["id"] not in piece:
                            todo.append(other["id"])
            left -= piece
            pieces.append(sorted(piece))
        return pieces

    def stretch_ends(self, piece):
        near = {}
        for edge_id in piece:
            a, b = self.edges[edge_id]["start_node"], self.edges[edge_id]["end_node"]
            near.setdefault(a, set()).add(b)
            near.setdefault(b, set()).add(a)
        ends = sorted(n for n, others in near.items() if len(others) == 1)
        first = ends[0] if ends else min(near)

        def far(node):
            a, b = self.nodes[first], self.nodes[node]
            return (a["x_position"] - b["x_position"]) ** 2 + (
                a["y_position"] - b["y_position"]
            ) ** 2

        return first, max(sorted(near), key=far)


def line_label(line):
    kind = "Bus" if line["type"] == "bus" else line.get("kind", "train")
    kind = {"train": "Bahn", "tram": "Tram"}.get(kind, kind)
    return f"{kind} {line['name']}"


def cmd_maps(api):
    for row in rows(api.call("GET", "/api/maps/")):
        print(f"{row['id']}\t{row['name']}")


def cmd_find(api, map_id, text):
    graph = Graph(api, map_id)
    needle = text.casefold()
    hits = 0
    names = sorted(
        {e["name"] for e in graph.edges.values() if needle in e["name"].casefold()}
    )
    for name in [n for n in names if graph.stretches(n)]:
        for number, piece in enumerate(graph.stretches(name), 1):
            hits += 1
            start, end = graph.stretch_ends(piece)
            print(
                f"STRASSE {name} #{number}: {len(piece)} Kanten, "
                f"{graph.node_label(start)} … {graph.node_label(end)}"
            )
            print(f"  kanten {json.dumps(piece)}")
            for edge_id in piece:
                print("  " + graph.edge_line(graph.edges[edge_id]))
    for node in sorted(graph.nodes.values(), key=lambda n: n["id"]):
        if node["name"] and needle in node["name"].casefold():
            hits += 1
            types = ", ".join(t["name"] for t in node["node_type"])
            print(f"KNOTEN {graph.node_label(node['id'])} · {types}")
    for line in graph.lines:
        if needle in line["name"].casefold() or needle in line_label(line).casefold():
            hits += 1
            stops = line["stops"]
            print(
                f"LINIE {line_label(line)} (id {line['id']}, {line['type']}): "
                f"alle {line['interval']} min, "
                f"{graph.node_label(stops[0])} → {graph.node_label(stops[-1])}"
                if stops
                else f"LINIE {line_label(line)} (id {line['id']}, {line['type']})"
            )
    if hits == 0:
        print(f"nichts gefunden für „{text}“")
    elif hits > 1:
        print(f"{hits} Treffer: frag, welcher gemeint ist.")


def car_street(edge):
    street = edge["street_edge"]
    if not street:
        return False
    reserved = (
        int(street["dedicated_bus_lane"])
        + int(edge["bike_lane"])
        + int(street["tram_track"] == "own")
    )
    return street["lanes"] - reserved > 0 or street["dedicated_bus_lane"]


def cmd_route(api, map_id, start, end):
    """The shortest way along streets a bus can drive, for a new line."""
    graph = Graph(api, map_id)
    start, end = int(start), int(end)
    for node in (start, end):
        if node not in graph.nodes:
            sys.exit(f"Knoten {node} gibt es auf dieser Karte nicht.")
    best = {start: 0.0}
    came = {}
    heap = [(0.0, start)]
    while heap:
        dist, node = heapq.heappop(heap)
        if node == end:
            break
        if dist > best.get(node, float("inf")):
            continue
        for edge in graph.at.get(node, []):
            if edge["start_node"] != node or not car_street(edge):
                continue
            nxt = edge["end_node"]
            step = dist + edge["distance_m"]
            if step < best.get(nxt, float("inf")):
                best[nxt] = step
                came[nxt] = edge
                heapq.heappush(heap, (step, nxt))
    if end not in came:
        sys.exit(
            f"kein Weg auf Straßen von {graph.node_label(start)} "
            f"nach {graph.node_label(end)}"
        )
    path, node = [], end
    while node != start:
        edge = came[node]
        path.append(edge)
        node = edge["start_node"]
    path.reverse()
    streets = []
    for edge in path:
        if not streets or streets[-1] != edge["name"]:
            streets.append(edge["name"] or "(ohne Namen)")
    print(
        f"{graph.node_label(start)} → {graph.node_label(end)}: "
        f"{best[end] / 1000:.1f} km, {len(path)} Kanten, über " + " – ".join(streets)
    )
    print(f"kanten {json.dumps([e['id'] for e in path])}")


def street_id(graph, edge_id):
    edge = graph.edges.get(edge_id)
    if not edge:
        sys.exit(f"Kante {edge_id} gibt es in der Basisversion nicht.")
    if not edge["street_edge"]:
        sys.exit(f"Kante {edge_id} ist keine Straße.")
    return edge["street_edge"]["id"]


def find_line(graph, label):
    hits = [line for line in graph.lines if line_label(line) == label]
    if len(hits) != 1:
        known = ", ".join(sorted(line_label(line) for line in graph.lines))
        sys.exit(f"Linie „{label}“: {len(hits)} Treffer. Bekannt: {known}")
    return hits[0]


def build_diff(graph, change):
    """The create-from-diff payload for one change file, or exit with why not."""
    payload = {
        "source_version_id": graph.version_id,
        "version_name": change["name"],
        "poll_text": change["poll_text"],
        "revert_poll_text": change["revert_poll_text"],
        "edge_changes": [],
        "pt_line_changes": [],
        "new_edges": [],
        "deleted_edge_ids": [],
    }
    notes = []
    for step in change["changes"]:
        kind = step.get("kind")
        if kind not in KINDS:
            sys.exit(f"unbekannte Art „{kind}“, bekannt: {', '.join(KINDS)}")
        if kind == "bus_lane":
            for edge_id in step["edges"]:
                street_id(graph, edge_id)
                street = graph.edges[edge_id]["street_edge"]
                left = street["lanes"] - 1 - int(graph.edges[edge_id]["bike_lane"])
                if left <= 0 and not step.get("closes_to_cars"):
                    sys.exit(
                        f"Kante {edge_id} hat {street['lanes']} Spur(en): eine "
                        "Busspur sperrt sie für Autos. Sag es dem Menschen und "
                        'setz "closes_to_cars": true, wenn es so gemeint ist.'
                    )
                if left <= 0:
                    notes.append(f"Kante {edge_id}: für Autos gesperrt")
                if edge_id not in graph.lines_on:
                    notes.append(f"Kante {edge_id}: auf ihr fährt keine Linie")
                payload["edge_changes"].append(
                    {"edge_id": edge_id, "dedicated_bus_lane": True}
                )
        elif kind == "interval":
            line = find_line(graph, step["line"])
            payload["pt_line_changes"].append(
                {
                    "action": "modify",
                    "line_type": line["type"],
                    "id": line["id"],
                    "interval": int(step["minutes"]),
                }
            )
            notes.append(
                f"{step['line']}: alle {line['interval']} → {step['minutes']} min"
            )
        elif kind == "close":
            for edge_id in step["edges"]:
                edge = graph.edges.get(edge_id)
                if not edge or not edge["street_edge"]:
                    sys.exit(f"Kante {edge_id} ist keine Straße der Basisversion.")
                if edge_id in graph.lines_on:
                    sys.exit(
                        f"Kante {edge_id}: auf ihr fahren "
                        f"{', '.join(sorted(graph.lines_on[edge_id]))}. Eine "
                        "gesperrte Straße mit Linie bricht die Linie; frag, ob "
                        "eine Busspur gemeint ist."
                    )
                payload["deleted_edge_ids"].append(edge_id)
                # Closed to cars, open to feet and bikes: the street goes and a
                # path takes its place between the same two nodes.
                payload["new_edges"].append(
                    {
                        "temp_start_node": str(edge["start_node"]),
                        "temp_end_node": str(edge["end_node"]),
                        "walking": True,
                        "biking": True,
                    }
                )
        elif kind == "bus_line":
            for direction in ("there", "back"):
                chain = step.get(direction)
                if not chain:
                    continue
                for a, b in zip(chain, chain[1:]):
                    if graph.edges[a]["end_node"] != graph.edges[b]["start_node"]:
                        sys.exit(f"{direction}: Kante {a} endet nicht, wo {b} beginnt.")
                payload["pt_line_changes"].append(
                    {
                        "action": "add",
                        "line_type": "bus",
                        "name": step["line_name"],
                        "interval": int(step["minutes"]),
                        "edge_ids": [street_id(graph, e) for e in chain],
                    }
                )
            if not step.get("back"):
                notes.append(f"Bus {step['line_name']}: nur eine Richtung")
        elif kind == "footpath":
            a, b = int(step["from"]), int(step["to"])
            for node in (a, b):
                if node not in graph.nodes:
                    sys.exit(f"Knoten {node} gibt es in der Basisversion nicht.")
            payload["new_edges"].append(
                {
                    "temp_start_node": str(a),
                    "temp_end_node": str(b),
                    "bidirectional": True,
                    "walking": True,
                    "biking": bool(step.get("biking", True)),
                }
            )
    return payload, notes


def cmd_add(api, map_id, path):
    with open(path, encoding="utf-8") as fh:
        change = json.load(fh)
    for key in ("name", "poll_text", "revert_poll_text", "changes"):
        if not change.get(key):
            sys.exit(f"In {path} fehlt „{key}“.")
    names = {v["name"] for v in all_versions(api, map_id)}
    if change["name"] in names:
        sys.exit(f"Eine Version „{change['name']}“ gibt es schon.")
    graph = Graph(api, map_id)
    payload, notes = build_diff(graph, change)
    version = api.call(
        "POST", f"/api/maps/{map_id}/versions/create-from-diff/", payload
    )
    print(f"Version {version['id']} „{version['name']}“ angelegt.")
    for note in notes:
        print("  " + note)


def touched(base, other):
    """What a version changes against base: street node pairs and line names."""

    def streets(graph):
        out = {}
        for edge in graph.edges.values():
            street = edge["street_edge"]
            key = (edge["start_node"], edge["end_node"])
            out[key] = (
                bool(street),
                street and street["lanes"],
                street and street["speed_limit"],
                street and street["dedicated_bus_lane"],
                edge["walking"],
                edge["biking"],
            )
        return out

    def lines(graph):
        # By the nodes a line runs through: a changed street is a clone with a
        # new id, and the line on it has not changed for that.
        return {
            line_label(line): (
                line["interval"],
                tuple(
                    (graph.edges[e]["start_node"], graph.edges[e]["end_node"])
                    for e in line["edges"]
                ),
            )
            for line in graph.lines
        }

    mine, theirs = streets(base), streets(other)
    pairs = {k for k in mine.keys() | theirs.keys() if mine.get(k) != theirs.get(k)}
    pairs = {tuple(sorted(k)) for k in pairs}
    a, b = lines(base), lines(other)
    names = {k for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
    return pairs, names


def cmd_ballot(api, map_id, *version_ids):
    ids = [int(v) for v in version_ids]
    if not ids:
        sys.exit("Welche Versionen?")
    if len(ids) > MAX_CHANGES:
        sys.exit(
            f"Höchstens {MAX_CHANGES} Änderungen: das sind schon 2^4 − 1 = 15 Versionen."
        )
    base = base_version(api, map_id)
    by_id = {v["id"]: v for v in all_versions(api, map_id)}
    for vid in ids:
        if vid not in by_id or by_id[vid]["base_version"]:
            sys.exit(f"Version {vid} ist keine Änderung dieser Karte.")
    base_graph = Graph(api, map_id)
    seen = {}
    for vid in ids:
        pairs, names = touched(base_graph, Graph(api, map_id, vid))
        for item in [("Straße", p) for p in pairs] + [("Linie", n) for n in names]:
            if item in seen:
                sys.exit(
                    f"„{by_id[seen[item]]['name']}“ und „{by_id[vid]['name']}“ "
                    f"ändern beide {item[0]} {item[1]}: nicht auf einen Stimmzettel."
                )
            seen[item] = vid
    if len(ids) == 1:
        partners = sorted(set(base["compatible_versions"]) | {ids[0]})
        api.call(
            "PATCH",
            f"/api/maps/{map_id}/versions/{base['id']}/",
            {"compatible_versions": partners},
        )
        print(f"Stimmzettel: Basis ↔ „{by_id[ids[0]]['name']}“.")
        return
    answer = api.call(
        "POST",
        f"/api/maps/{map_id}/versions/generate-combinations/",
        {"version_ids": ids},
    )
    print(
        f"Stimmzettel aus {len(ids)} Änderungen, {answer['created']} Kombinationen neu."
    )


def cmd_list(api, map_id):
    for version in sorted(all_versions(api, map_id), key=lambda v: v["id"]):
        mark = "BASIS " if version["base_version"] else ""
        print(
            f"{version['id']}\t{mark}{version['name']}\t"
            f"Stimmzettel mit {version['compatible_versions']}"
        )
        if not version["base_version"]:
            print(f"\tja: {version['poll_text']}")
            print(f"\tnein: {version['revert_poll_text']}")


def cmd_delete(api, map_id, version_id):
    api.call("DELETE", f"/api/maps/{map_id}/versions/{int(version_id)}/")
    print(f"Version {version_id} gelöscht.")


def cmd_export(api, map_id, out):
    body = api.call("GET", f"/api/maps/{map_id}/export/", raw=True)
    with open(out, "wb") as fh:
        fh.write(body)
    detail = api.call("GET", f"/api/maps/{map_id}/")
    print(f"{out}: {len(body) // 1024} KB")
    print(f"Pendler der Karte: {detail.get('district_commuters')}")


COMMANDS = {
    "maps": cmd_maps,
    "find": cmd_find,
    "route": cmd_route,
    "add": cmd_add,
    "ballot": cmd_ballot,
    "list": cmd_list,
    "delete": cmd_delete,
    "export": cmd_export,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[argv[1]](Api(), *argv[2:])


if __name__ == "__main__":
    main(sys.argv)
