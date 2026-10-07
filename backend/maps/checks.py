"""What every map file has to keep, beyond what the upload refuses.

The importer refuses a file it cannot turn into a map: an edge to a node that
does not exist, a version index pointing nowhere. A file can pass that and
still be broken in a way nothing reports until a round is played on it — a
line that runs nothing in one of its versions, a link drawn twice, a home with
no way to work. Those are the checks here. Each is a rule any map has to keep,
whatever place it draws; what is true of one map only (its counts, its
names, its interventions) belongs in that map's own tests.

The upload does not run them, on purpose: a map in the editor is half drawn
most of the time, and its export has to import back as it is. They are what
`manage.py check_map` and `maps/tests/test_example_map.py` ask of a finished
map.

Every check reads the file the way the importer does (`maps/portability.py`
owns the format): absent `versions` means the base version, `[]` means none,
and a file without a `versions` block is one implicit base version. Messages
are German and name nodes and versions by the names the editor shows, because
whoever reads them is fixing the map.
"""

from collections import defaultdict, deque
from typing import NamedTuple

from maps.importer import MapImporter
from maps.portability import (
    STREET_FIELDS,
    base_index,
    chain_groups,
    element_versions,
    states_a_street,
    version_block,
    version_indices,
)
from sim import node_chain

BOARDING_TYPES = {"station", "bus_stop"}
LINE_FIGURES = ("capacity", "speed_kmh", "interval")


class Problem(NamedTuple):
    check: str
    message: str


def check_map(graph):
    """Every problem the file has, in the order of `CHECKS`.

    What the upload would refuse comes first and alone: every later check
    indexes into the file and would trip over the same defect.
    """
    refused = MapImporter(user=None)._validate_graph_data(graph)
    if refused:
        return [Problem("upload", message) for message in refused]
    found = MapFile(graph)
    return [problem for check in CHECKS for problem in check(found)]


class MapFile:
    """One map file, read the importer's way."""

    def __init__(self, graph):
        self.graph = graph
        block = version_block(graph)
        if block is None:
            name = (graph.get("map") or {}).get("name") or "Grundversion"
            block = [{"name": name, "base_version": True}]
        self.versions = block
        self.count = len(block)
        self.base = base_index(block)
        self.nodes = {str(node["id"]): node for node in graph.get("nodes") or []}
        self.edges = graph.get("edges") or []
        self.lines = [("bus", line) for line in graph.get("bus_lines") or []] + [
            ("train", line) for line in graph.get("train_lines") or []
        ]
        self.links = defaultdict(list)
        for idx, edge in enumerate(self.edges):
            self.links[self.ends(edge)].append(idx)

    def members(self, element):
        return version_indices(element, self.count, self.base)

    def routes(self, line):
        """`{version: [edge index, ...]}` — what the line runs, where."""
        routes = {}
        for versions, edges in chain_groups(line, self.members(line)):
            for version in versions:
                routes[version] = list(edges)
        return routes

    @staticmethod
    def ends(edge):
        return str(edge["start_node"]), str(edge["end_node"])

    def chain(self, route):
        return node_chain([self.ends(self.edges[idx]) for idx in route])

    def types(self, node_id):
        return set(self.nodes[node_id].get("types") or [])

    # -- naming things in a message ------------------------------------------

    def in_versions(self, indices):
        return ", ".join(f"„{self.versions[i]['name']}“" for i in sorted(indices))

    def node(self, node_id):
        return f"„{self.nodes[node_id].get('name') or node_id}“"

    def edge(self, idx):
        edge = self.edges[idx]
        start, end = self.ends(edge)
        label = f"Kante {idx} ({self.node(start)} → {self.node(end)})"
        return f"{label} „{edge['name']}“" if edge.get("name") else label

    @staticmethod
    def line(mode, name):
        return f"{'Buslinie' if mode == 'bus' else 'Bahnlinie'} „{name}“"


def _per_version(found, message):
    """One problem per key, naming every version it happens in.

    A line drawn on the wrong side in all eight versions is one mistake, and a
    message per version would bury the next one.
    """
    return [message(key, versions) for key, versions in found.items()]


# ---------------------------------------------------------------------------
# versions and the ballot
# ---------------------------------------------------------------------------


def ballot_one_way(found):
    """`compatible_versions` *is* the vote, and the vote goes both ways.

    The game offers what the active version's list reaches. The import stores
    the pair symmetrically, so a file naming one side only is a file that says
    something different from the map it becomes.
    """
    problems = []
    for idx, version in enumerate(found.versions):
        for other in version.get("compatible_versions") or []:
            if idx in (found.versions[other].get("compatible_versions") or []):
                continue
            problems.append(
                Problem(
                    "ballot-one-way",
                    f"{found.in_versions([idx])} bietet {found.in_versions([other])} "
                    f"zur Wahl an, aber nicht umgekehrt.",
                )
            )
    return problems


def version_unreachable(found):
    """A version no vote leads to is a version nobody ever plays."""
    neighbours = defaultdict(set)
    for idx, version in enumerate(found.versions):
        for other in version.get("compatible_versions") or []:
            neighbours[idx].add(other)
            neighbours[other].add(idx)
    seen = {found.base}
    frontier = [found.base]
    while frontier:
        for other in neighbours[frontier.pop()]:
            if other not in seen:
                seen.add(other)
                frontier.append(other)
    return [
        Problem(
            "version-unreachable",
            f"{found.in_versions([idx])} ist von der Grundversion aus mit keiner "
            f"Abstimmung zu erreichen, gespielt wird sie also nie.",
        )
        for idx in range(found.count)
        if idx not in seen
    ]


# ---------------------------------------------------------------------------
# what belongs where
# ---------------------------------------------------------------------------


def in_no_version(found):
    """`"versions": []` is a piece of the map nobody can see or ride.

    The format keeps `[]` apart from absent on purpose — a backup that quietly
    moved such leftovers into the base version would invent streets the map
    never had — so a file can say it. A finished map should not.
    """
    problems = []
    for node_id, node in found.nodes.items():
        if not found.members(node):
            problems.append(f"Knoten {found.node(node_id)}")
    for idx, edge in enumerate(found.edges):
        if not found.members(edge):
            problems.append(found.edge(idx))
    for mode, line in found.lines:
        if not found.members(line):
            problems.append(found.line(mode, line.get("name")))
    return [
        Problem("in-no-version", f"{what} gehört zu keiner Version.")
        for what in problems
    ]


def link_twice(found):
    """One link per direction per node pair, in every version.

    The editor refuses a second one (`edge-exists`), whatever its type, so a
    file with two is a map the editor cannot make — and the simulator would
    queue the same street's traffic on two links. Two links between the same
    nodes in *different* versions are fine: that is how a changed street is
    drawn, the original in one version and its clone in the other.
    """
    doubled = defaultdict(set)
    for ends, indices in found.links.items():
        if len(indices) < 2:
            continue
        for version in range(found.count):
            here = [i for i in indices if version in found.members(found.edges[i])]
            if len(here) > 1:
                doubled[(ends, tuple(here))].add(version)
    return _per_version(
        doubled,
        lambda key, versions: Problem(
            "link-twice",
            f"Von {found.node(key[0][0])} nach {found.node(key[0][1])} führen in "
            f"{found.in_versions(versions)} mehrere Kanten: "
            f"{', '.join(map(str, key[1]))}.",
        ),
    )


def edge_without_node(found):
    """An edge lives only where both its nodes live.

    The renderers draw an edge from its nodes' coordinates, so this is the
    difference between a line on screen and a crash.
    """
    missing = defaultdict(set)
    for idx, edge in enumerate(found.edges):
        for node_id in found.ends(edge):
            node_versions = set(found.members(found.nodes[node_id]))
            for version in found.members(edge):
                if version not in node_versions:
                    missing[(idx, node_id)].add(version)
    return _per_version(
        missing,
        lambda key, versions: Problem(
            "edge-without-node",
            f"{found.edge(key[0])} liegt in {found.in_versions(versions)}, "
            f"wo {found.node(key[1])} fehlt.",
        ),
    )


# ---------------------------------------------------------------------------
# streets, rails and paths
# ---------------------------------------------------------------------------


def street_numbers(found):
    """A street states its speed limit, its lanes and its bus lane.

    The speed limit is what the free-flow time and the CO2 curve run on. A
    `street` stating none of the three is read by the importer as a path with
    no street under it — a file meaning that should say `"type": "path"`.
    """
    problems = []
    for idx, edge in enumerate(found.edges):
        kind = edge.get("type", "both")
        if kind not in ("street", "both", "tram"):
            continue
        missing = [field for field in STREET_FIELDS if field not in edge]
        if not missing:
            continue
        hint = (
            " Ohne alle drei liest der Import sie als Weg ohne Straße — "
            "dann „path“ schreiben."
            if not states_a_street(edge)
            else ""
        )
        problems.append(
            Problem(
                "street-numbers",
                f"{found.edge(idx)} ist „{kind}“, nennt aber "
                f"{', '.join(missing)} nicht.{hint}",
            )
        )
    return problems


def street_figures(found):
    """A speed limit above zero and at least one lane.

    A zero speed limit divides into the free-flow time. `lanes` counts the
    whole street, bus and bike lane included, so a street needs at least one;
    a one-lane street with a bus lane is a legal bus gate, closed to cars.
    """
    problems = []
    for idx, edge in enumerate(found.edges):
        bad = []
        speed = edge.get("speed_limit")
        if speed is not None and not _positive(speed):
            bad.append(f"speed_limit {speed}")
        lanes = edge.get("lanes")
        if lanes is not None and not (isinstance(lanes, int) and lanes >= 1):
            bad.append(f"lanes {lanes}")
        if bad:
            problems.append(
                Problem("street-figures", f"{found.edge(idx)}: {', '.join(bad)}.")
            )
    return problems


def path_numbers(found):
    """A path has no street under it, and a street number says otherwise.

    `"type": "path"` is a way for bikes and pedestrians and nothing else; an
    editor pass that gave one lanes would open a car shortcut past every front
    door.
    """
    return [
        Problem(
            "path-numbers",
            f"{found.edge(idx)} ist ein Weg („path“) und nennt trotzdem "
            f"{', '.join(f for f in STREET_FIELDS if f in edge)}.",
        )
        for idx, edge in enumerate(found.edges)
        if edge.get("type") == "path" and states_a_street(edge)
    ]


def path_closed(found):
    """A path nobody may walk or cycle is a path nobody can use."""
    return [
        Problem(
            "path-closed",
            f"{found.edge(idx)} ist ein Weg, auf dem weder gegangen noch Rad "
            f"gefahren werden darf.",
        )
        for idx, edge in enumerate(found.edges)
        if edge.get("type") == "path"
        and edge.get("walking") is False
        and edge.get("biking") is False
    ]


def bike_lane_unstated(found):
    """The file describes the map, not a difference from a default.

    A key that only appears when it is true re-imports to the same value, but
    the next reader cannot tell "no bike lane here" from "this file is older
    than the field". Reported once for the whole file, since a file missing it
    usually misses it everywhere.
    """
    missing = [idx for idx, edge in enumerate(found.edges) if "bike_lane" not in edge]
    if not missing:
        return []
    shown = ", ".join(map(str, missing[:10])) + (" …" if len(missing) > 10 else "")
    return [
        Problem(
            "bike-lane-unstated",
            f"{len(missing)} Kanten nennen bike_lane nicht: {shown}.",
        )
    ]


# ---------------------------------------------------------------------------
# lines
# ---------------------------------------------------------------------------


def line_figures(found):
    """Seats, speed and interval, each above zero.

    The simulator and the client's route preview both read the speed from the
    line; a line with no seats boards nobody, and one with no interval never
    comes.
    """
    problems = []
    for mode, line in found.lines:
        bad = [field for field in LINE_FIGURES if not _positive(line.get(field))]
        if bad:
            problems.append(
                Problem(
                    "line-figures",
                    f"{found.line(mode, line.get('name'))}: {', '.join(bad)} fehlt oder ist "
                    f"nicht größer als null.",
                )
            )
    return problems


def line_runs_nothing(found):
    """A line in a version with no route there is a line nobody can board.

    The simulator measures it at 0 km, logs, and drives nothing, so the map
    shows a line that does not exist. Changing a street clones it, and a line's
    route moved onto the clone is exactly how a version loses a line this way.
    """
    empty = defaultdict(set)
    for mode, line in found.lines:
        routes = found.routes(line)
        for version in found.members(line):
            if not routes.get(version):
                empty[(mode, line.get("name"))].add(version)
    return _per_version(
        empty,
        lambda key, versions: Problem(
            "line-runs-nothing",
            f"{found.line(key[0], key[1])} gehört zu "
            f"{found.in_versions(versions)}, fährt dort aber keine Kante.",
        ),
    )


def line_outside_its_versions(found):
    """A route in a version the line is not in is a route the import drops."""
    outside = defaultdict(set)
    for mode, line in found.lines:
        belongs = set(found.members(line))
        for version in found.routes(line):
            if version not in belongs:
                outside[(mode, line.get("name"))].add(version)
    return _per_version(
        outside,
        lambda key, versions: Problem(
            "line-outside-its-versions",
            f"{found.line(key[0], key[1])} hat eine Strecke in "
            f"{found.in_versions(versions)}, gehört dort aber nicht dazu.",
        ),
    )


def line_broken(found):
    """A line is one connected walk, link after link.

    The simulator follows the chain and stops where it breaks: the rest of the
    line is never driven, and it is charged only for what it drives, so a
    broken line silently becomes a shorter one.
    """
    broken = defaultdict(set)
    for mode, line in found.lines:
        for version, route in found.routes(line).items():
            chain = found.chain(route)
            if route and len(chain) != len(route) + 1:
                broken[
                    (mode, line.get("name"), max(0, len(chain) - 1), len(route))
                ].add(version)
    return _per_version(
        broken,
        lambda key, versions: Problem(
            "line-broken",
            f"{found.line(key[0], key[1])} reißt in "
            f"{found.in_versions(versions)} nach {key[2]} von {key[3]} Kanten ab.",
        ),
    )


def line_off_version(found):
    """A line runs only over links its version has."""
    off = defaultdict(set)
    for mode, line in found.lines:
        for version, route in found.routes(line).items():
            for idx in route:
                if version not in found.members(found.edges[idx]):
                    off[(mode, line.get("name"), idx)].add(version)
    return _per_version(
        off,
        lambda key, versions: Problem(
            "line-off-version",
            f"{found.line(key[0], key[1])} fährt in "
            f"{found.in_versions(versions)} über {found.edge(key[2])}, die es dort "
            f"nicht gibt.",
        ),
    )


def line_wrong_side(found):
    """A line names the link going its way wherever the version has one.

    Each direction of a street is its own link with its own queue, and the
    order a line travels in is read from its nodes, so a route naming the
    other direction passes every other check. The simulator drives the right
    side anyway (`TrafficSimulator._its_own_way`); this keeps the file honest,
    and what the editor and the replay draw with it. Where the version has no
    link going the line's way — a one-way street — the drawn one is all there
    is, and that is fine.
    """
    wrong = defaultdict(set)
    for mode, line in found.lines:
        for version, route in found.routes(line).items():
            stops = found.chain(route)
            for i, idx in enumerate(route[: len(stops) - 1]):
                here, there = stops[i], stops[i + 1]
                if found.ends(found.edges[idx]) != (there, here):
                    continue
                own_way = [
                    other
                    for other in found.links[(here, there)]
                    if version in found.members(found.edges[other])
                    and _may_carry(mode, found.edges[other])
                ]
                if own_way:
                    wrong[(mode, line.get("name"), idx, tuple(own_way))].add(version)
    return _per_version(
        wrong,
        lambda key, versions: Problem(
            "line-wrong-side",
            f"{found.line(key[0], key[1])} fährt {found.edge(key[2])} gegen "
            f"ihre Richtung, in {found.in_versions(versions)}; in ihre Richtung "
            f"führt Kante {', '.join(map(str, key[3]))}.",
        ),
    )


def line_end_not_a_stop(found):
    """Both ends of a line are stops somebody can board at.

    The client boards only at `station` and `bus_stop` nodes. A line may run
    past an ordinary junction — that is what a bus does — but a terminus
    nobody can board at is a line that goes nowhere.
    """
    ends = defaultdict(set)
    for mode, line in found.lines:
        for version, route in found.routes(line).items():
            chain = found.chain(route)
            if not route or len(chain) != len(route) + 1:
                continue
            for node_id in (chain[0], chain[-1]):
                if not found.types(node_id) & BOARDING_TYPES:
                    ends[(mode, line.get("name"), node_id)].add(version)
    return _per_version(
        ends,
        lambda key, versions: Problem(
            "line-end-not-a-stop",
            f"{found.line(key[0], key[1])} endet in "
            f"{found.in_versions(versions)} an {found.node(key[2])}, und dort kann "
            f"niemand einsteigen (weder „station“ noch „bus_stop“).",
        ),
    )


def train_in_car_lane(found):
    """Only a tram runs on rails in the car lane.

    Whatever runs there waits with the cars (`StreetEdge.tram_track`), which
    is a tram on Friedrichstraße north and nothing an S- or U-Bahn does. A
    line that does not say its kind is a train.
    """
    wrong = defaultdict(set)
    for mode, line in found.lines:
        if mode != "train" or line.get("kind", "train") == "tram":
            continue
        for version, route in found.routes(line).items():
            for idx in route:
                if _rails_in_car_lane(found.edges[idx]):
                    wrong[(line.get("name"), idx)].add(version)
    return _per_version(
        wrong,
        lambda key, versions: Problem(
            "train-in-car-lane",
            f"{found.line('train', key[0])} ist keine Tram, fährt aber in "
            f"{found.in_versions(versions)} über {found.edge(key[1])}, wo die "
            f"Gleise in der Fahrspur liegen. Dort fährt nur eine Tram "
            f"(„kind“: „tram“).",
        ),
    )


def tram_without_rails(found):
    """A tram street has its rails wherever it has its street.

    `"type": "tram"` says the street's rails lie in it; a version that keeps
    the street but drops the railway under it (`train_versions`) would have a
    tram track with no track.
    """
    missing = defaultdict(set)
    for idx, edge in enumerate(found.edges):
        if edge.get("type") != "tram":
            continue
        own = found.members(edge)
        street = set(element_versions(edge, "street_versions", own, found.count))
        rails = set(element_versions(edge, "train_versions", own, found.count))
        for version in street - rails:
            missing[idx].add(version)
    return _per_version(
        missing,
        lambda idx, versions: Problem(
            "tram-without-rails",
            f"{found.edge(idx)} ist eine Tram-Straße, hat aber in "
            f"{found.in_versions(versions)} keine Gleise.",
        ),
    )


# ---------------------------------------------------------------------------
# whether the map can be played
# ---------------------------------------------------------------------------


def no_home_or_work(found):
    """Every version has somewhere to live and somewhere to work.

    Each seat gets a home node and its Gruppen go to workplaces; a version
    without either cannot start a round.
    """
    missing = defaultdict(set)
    for version in range(found.count):
        present = set()
        for node in found.nodes.values():
            if version in found.members(node):
                present |= set(node.get("types") or [])
        for kind in ("home", "workplace"):
            if kind not in present:
                missing[kind].add(version)
    words = {"home": "keinen Wohnort", "workplace": "keinen Arbeitsort"}
    return _per_version(
        missing,
        lambda kind, versions: Problem(
            "no-home-or-work",
            f"{found.in_versions(versions)} hat {words[kind]} („{kind}“).",
        ),
    )


def no_way(found):
    """Every home reaches every workplace and back, by some mode, in every version.

    A round is there and back, and the way home is found rather than reversed,
    so both directions are asked. Any link counts that something may use — a
    street, a path, a railway with a way alongside — and so does every hop a
    line makes, which is how a railway nobody may walk becomes a way. No length
    limit applies: whether a commute is short enough to walk is a question for
    the map's author, not a defect.
    """
    unreachable = defaultdict(set)
    for version in range(found.count):
        reach = defaultdict(set)
        for edge in found.edges:
            if version not in found.members(edge):
                continue
            if edge.get("type") == "train" and not (
                edge.get("walking") or edge.get("biking")
            ):
                continue
            start, end = found.ends(edge)
            reach[start].add(end)
        for _, line in found.lines:
            if version not in found.members(line):
                continue
            chain = found.chain(found.routes(line).get(version) or [])
            for here, there in zip(chain, chain[1:]):
                reach[here].add(there)

        here = [
            node_id
            for node_id, node in found.nodes.items()
            if version in found.members(node)
        ]
        homes = [n for n in here if "home" in found.types(n)]
        work = [n for n in here if "workplace" in found.types(n)]
        for origins, targets in ((homes, work), (work, homes)):
            for origin in origins:
                reached = _reachable(reach, origin)
                for target in targets:
                    if target not in reached:
                        unreachable[(origin, target)].add(version)
    return _per_version(
        unreachable,
        lambda key, versions: Problem(
            "no-way",
            f"Von {found.node(key[0])} nach {found.node(key[1])} gibt es in "
            f"{found.in_versions(versions)} keinen Weg, mit keinem Verkehrsmittel.",
        ),
    )


CHECKS = (
    ballot_one_way,
    version_unreachable,
    in_no_version,
    link_twice,
    edge_without_node,
    street_numbers,
    street_figures,
    path_numbers,
    path_closed,
    bike_lane_unstated,
    line_figures,
    line_runs_nothing,
    line_outside_its_versions,
    line_broken,
    line_off_version,
    line_wrong_side,
    line_end_not_a_stop,
    train_in_car_lane,
    tram_without_rails,
    no_home_or_work,
    no_way,
)


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _may_carry(mode, edge):
    """Whether a line of this mode can run on the edge — a bus needs a street."""
    if mode == "bus":
        return states_a_street(edge) or edge.get("type") == "tram"
    return edge.get("type", "both") in ("train", "both", "tram")


def _rails_in_car_lane(edge):
    """A tram street whose rails lie in the car lane — its default."""
    return edge.get("type") == "tram" and edge.get("tram_track", "lane") == "lane"


def _reachable(reach, origin):
    seen = {origin}
    queue = deque([origin])
    while queue:
        for other in reach[queue.popleft()]:
            if other not in seen:
                seen.add(other)
                queue.append(other)
    return seen
