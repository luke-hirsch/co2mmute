"""Changes on the base version of a co2mmute map, over the instance's own API.

    python3 modify.py maps
    python3 modify.py places <map>
    python3 modify.py edge <map> <north|east|south|west> [<n>]
    python3 modify.py place <map> <node> <home|workplace> "<name>"
    python3 modify.py commuters <map> <n>
    python3 modify.py footpath <map> <from node> <to node> "<name>" [--no-bike]
    python3 modify.py move <map> <node> <x> <y>
    python3 modify.py street <map> <from node> <to node> "<name>" <lanes> <km/h> [--oneway]
    python3 modify.py export <map> <out.json>

<map> and <node> are ids, as `maps`, `places` and `edge` print them (look a name up with
map-versions' `versions.py find`). Every command that writes first saves the map's export next to
where it is run, and says where. The calls are the ones the map editor makes
(`frontend/src/lib/queries/map-editor.ts`); what is drawn goes into the base version, and into every
version built on it. The instance and a staff account come from CO2MMUTE_URL (default
http://127.0.0.1:8000, Django itself), CO2MMUTE_USER and CO2MMUTE_PASSWORD. Standard library only.
"""

import http.cookiejar
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("CO2MMUTE_URL", "http://127.0.0.1:8000").rstrip("/")
SIDES = ("north", "east", "south", "west")
PLACES = {"home": "Wohnort", "workplace": "Arbeit"}
# The editor refuses these too: a name that is only what the map would call it anyway.
DEFAULT_NAME = re.compile(r"(knoten|kante|node|edge)\s*\d+\s*$", re.IGNORECASE)


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


def base_version(api, map_id):
    for version in rows(api.call("GET", f"/api/maps/{map_id}/versions/")):
        if version["base_version"]:
            return version
    sys.exit(f"Karte {map_id} hat keine Basisversion.")


def load(api, map_id):
    return api.call("GET", f"/api/maps/{map_id}/graph/baseversion/")


def node_label(graph, node_id):
    node = next(n for n in graph["nodes"] if n["id"] == node_id)
    if node["name"]:
        return f"{node['name']} ({node_id})"
    streets = sorted(
        {
            e["name"]
            for e in graph["edges"]
            if e["name"] and node_id in (e["start_node"], e["end_node"])
        }
    )
    return (
        ("Ecke " + " / ".join(streets[:3]) + f" ({node_id})")
        if streets
        else f"Knoten {node_id}"
    )


def need_node(graph, node_id):
    node_id = int(node_id)
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node
    sys.exit(f"Knoten {node_id} gibt es in der Basisversion nicht.")


def need_name(name):
    name = (name or "").strip()
    if not name or DEFAULT_NAME.search(name):
        sys.exit(
            f"„{name}“ ist kein Name: nicht leer und nicht „Knoten 12“. Gib einen besseren."
        )
    return name


def backup(api, map_id):
    """Save the export before the first write; a map is hours of work."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = f"map-{map_id}-before-{stamp}.json"
    with open(path, "wb") as fh:
        fh.write(api.call("GET", f"/api/maps/{map_id}/export/", raw=True))
    print(f"Export vorher: {os.path.abspath(path)}")


def cmd_maps(api):
    for row in rows(api.call("GET", "/api/maps/")):
        print(f"{row['id']}\t{row['name']}")


def cmd_places(api, map_id):
    graph = load(api, map_id)
    row = api.call("GET", f"/api/maps/{map_id}/")
    print(
        f"{row['name']}: {row['district_commuters']} Pendler, "
        f"{'gemessen am ' + row['calibrated_at'][:10] if row['calibrated_at'] else 'nicht gemessen'}, "
        f"Maßstab {row['scale']} m je Einheit, Karte {row['x_dim']} × {row['y_dim']}"
    )
    for kind in PLACES:
        found = [
            n for n in graph["nodes"] if kind in [t["name"] for t in n["node_type"]]
        ]
        print(f"{kind}: {len(found)}")
        for node in sorted(found, key=lambda n: n["id"]):
            print(
                f"  {node_label(graph, node['id'])}  x {node['x_position']:.2f} y {node['y_position']:.2f}"
            )


def cmd_edge(api, map_id, side, count="8"):
    """The outermost nodes on one side, for where a bordering town would lie."""
    if side not in SIDES:
        sys.exit(f"Seite: {', '.join(SIDES)}")
    graph = load(api, map_id)
    row = api.call("GET", f"/api/maps/{map_id}/")
    # y grows downwards on the map: "north" is the smallest y.
    gap = {
        "north": lambda n: n["y_position"],
        "south": lambda n: row["y_dim"] - n["y_position"],
        "west": lambda n: n["x_position"],
        "east": lambda n: row["x_dim"] - n["x_position"],
    }[side]
    for node in sorted(graph["nodes"], key=gap)[: int(count)]:
        print(
            f"{node_label(graph, node['id'])}  x {node['x_position']:.2f} "
            f"y {node['y_position']:.2f}  "
            f"({gap(node) * row['scale'] / 1000:.1f} km vom {side}-Rand der Karte)"
        )


def cmd_place(api, map_id, node_id, kind, name):
    if kind not in PLACES:
        sys.exit("home oder workplace")
    name = need_name(name)
    graph = load(api, map_id)
    node = need_node(graph, node_id)
    types = {t["name"]: t["id"] for t in rows(api.call("GET", "/api/maps/node-types/"))}
    if kind not in types:
        sys.exit(f"Die Instanz kennt den Knotentyp „{kind}“ nicht.")
    have = [t["id"] for t in node["node_type"]]
    if types[kind] in have:
        sys.exit(f"Knoten {node['id']} ist schon {kind}.")
    backup(api, map_id)
    api.call(
        "PATCH",
        f"/api/maps/{map_id}/nodes/{node['id']}/",
        {"name": name, "node_type": have + [types[kind]]},
    )
    print(
        f"Knoten {node['id']} (vorher: {node_label(graph, node['id'])}) ist jetzt {kind} „{name}“."
    )
    print("Orte geändert: calibrate_map --commuters N --out muss neu laufen.")


def cmd_commuters(api, map_id, count):
    count = int(count)
    if count < 1:
        sys.exit("Pendler: mindestens 1.")
    row = api.call("GET", f"/api/maps/{map_id}/")
    backup(api, map_id)
    api.call(
        "PATCH",
        f"/api/maps/{map_id}/",
        {"district_commuters": count, "calibrated_at": None},
    )
    print(
        f"Pendler {row['district_commuters']} → {count}, „gemessen“ jetzt falsch. "
        f"Messen: calibrate_map <export> --commuters {count} --out <datei>."
    )


def cmd_footpath(api, map_id, a, b, name, *flags):
    name = need_name(name)
    graph = load(api, map_id)
    a, b = need_node(graph, a)["id"], need_node(graph, b)["id"]
    if a == b:
        sys.exit("Zwei verschiedene Knoten.")
    base = base_version(api, map_id)
    backup(api, map_id)
    api.call(
        "POST",
        f"/api/maps/{map_id}/edges/",
        {
            "game_map": int(map_id),
            "name": name,
            "start_node": a,
            "end_node": b,
            "walking": True,
            "biking": "--no-bike" not in flags,
            "bidirectional": True,
            "map_versions": [base["id"]],
        },
    )
    print(
        f"Fußweg „{name}“ in beide Richtungen: {node_label(graph, a)} ↔ {node_label(graph, b)}"
        + (" (nur zu Fuß)" if "--no-bike" in flags else " (zu Fuß und mit dem Rad)")
    )


def cmd_move(api, map_id, node_id, x, y):
    graph = load(api, map_id)
    node = need_node(graph, node_id)
    row = api.call("GET", f"/api/maps/{map_id}/")
    x, y = float(x), float(y)
    if not (0 <= x <= row["x_dim"] and 0 <= y <= row["y_dim"]):
        sys.exit(f"Außerhalb der Karte (0–{row['x_dim']} × 0–{row['y_dim']}).")
    moved = math.hypot(x - node["x_position"], y - node["y_position"]) * row["scale"]
    backup(api, map_id)
    api.call(
        "PATCH",
        f"/api/maps/{map_id}/nodes/{node['id']}/",
        {"x_position": x, "y_position": y},
    )
    print(
        f"{node_label(graph, node['id'])}: {moved:.0f} m verschoben. Die Kanten daran "
        "folgen mit ihrer Biegung (circuity); Haltestellen und Linien bleiben dran."
    )


def cmd_street(api, map_id, a, b, name, lanes, speed, *flags):
    name = need_name(name)
    lanes, speed = int(lanes), int(speed)
    graph = load(api, map_id)
    a, b = need_node(graph, a)["id"], need_node(graph, b)["id"]
    if a == b:
        sys.exit("Zwei verschiedene Knoten.")
    base = base_version(api, map_id)
    backup(api, map_id)
    ways = [(a, b)] if "--oneway" in flags else [(a, b), (b, a)]
    for start, end in ways:
        edge = api.call(
            "POST",
            f"/api/maps/{map_id}/edges/",
            {
                "game_map": int(map_id),
                "name": name,
                "start_node": start,
                "end_node": end,
                "walking": True,
                "biking": True,
                "max_lanes": lanes,
                "map_versions": [base["id"]],
            },
        )
        api.call(
            "POST",
            f"/api/maps/{map_id}/street-edges/",
            {
                "edge": edge["id"],
                "lanes": lanes,
                "speed_limit": speed,
                "map_versions": [base["id"]],
            },
        )
        print(
            f"Straße „{name}“: {node_label(graph, start)} → {node_label(graph, end)}, "
            f"{lanes} Spur(en), {speed} km/h (Kante {edge['id']})"
        )


def cmd_export(api, map_id, out):
    with open(out, "wb") as fh:
        fh.write(api.call("GET", f"/api/maps/{map_id}/export/", raw=True))
    print(f"Export: {os.path.abspath(out)}")


COMMANDS = {
    "maps": cmd_maps,
    "places": cmd_places,
    "edge": cmd_edge,
    "place": cmd_place,
    "commuters": cmd_commuters,
    "footpath": cmd_footpath,
    "move": cmd_move,
    "street": cmd_street,
    "export": cmd_export,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[argv[1]](Api(), *argv[2:])


if __name__ == "__main__":
    main(sys.argv)
