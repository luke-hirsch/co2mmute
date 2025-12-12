from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Edge, GameMap, Node, NodeType, StreetEdge


class MapGenerationError(Exception):
    """Raised when the map generator fails to create a usable result."""


@dataclass(frozen=True)
class MapGenerationParameters:
    latitude: float
    longitude: float
    radius_m: int
    complexity: int
    name: Optional[str] = None


@dataclass(frozen=True)
class GeneratedMapResult:
    game_map: GameMap
    nodes: List[Node]
    edges: List[Edge]
    summary: Dict[str, int]


@dataclass
class _OsmNode:
    osm_id: int
    lat: float
    lon: float
    tags: Dict[str, str]
    neighbors: set[int]
    ways: set[int]


@dataclass
class _OsmWay:
    osm_id: int
    node_ids: List[int]
    tags: Dict[str, str]


@dataclass
class _SelectedNode:
    osm_node: _OsmNode
    code: str
    x_position: float
    y_position: float


class MapGenerationService:
    """Create simplified game maps by querying a self-hosted Overpass API."""

    GRID_SIZE = 100
    MIN_TOTAL_NODES = 20
    MAX_TOTAL_NODES = 120
    REQUEST_TIMEOUT = 90

    NODE_TYPE_LABELS = {
        "H": "Household",
        "W": "Workplace",
        "TS": "Train Station",
        "BS": "Bus Stop",
        "I": "Intersection",
    }

    HIGHWAY_SPEED_LIMITS = {
        "motorway": 110,
        "trunk": 100,
        "primary": 80,
        "secondary": 60,
        "tertiary": 50,
        "residential": 30,
        "living_street": 20,
        "service": 20,
        "cycleway": 25,
        "footway": 10,
    }

    def __init__(self, overpass_url: Optional[str] = None, session: Optional[requests.Session] = None):
        self.overpass_url = overpass_url or getattr(settings, "OVERPASS_API_URL", None)
        if not self.overpass_url:
            raise MapGenerationError("OVERPASS_API_URL setting is not configured.")
        self.session = session or requests.Session()

    def generate_map(
        self,
        *,
        author,
        updated_by=None,
        latitude: float,
        longitude: float,
        radius_m: int,
        complexity: int,
        name: Optional[str] = None,
    ) -> GeneratedMapResult:
        params = MapGenerationParameters(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            complexity=complexity,
            name=name,
        )
        raw_osm = self._fetch_osm(params)
        graph = self._build_graph(raw_osm)
        selected_nodes, relevant_ways = self._select_nodes(params, graph)
        if len(selected_nodes) < 3:
            raise MapGenerationError("Could not identify enough nodes to create a map.")
        scaled_nodes = self._scale_nodes(selected_nodes)
        return self._persist_map(params, scaled_nodes, relevant_ways, author, updated_by)

    # ------------------------------------------------------------------
    # OSM acquisition and graph construction
    # ------------------------------------------------------------------

    def _fetch_osm(self, params: MapGenerationParameters) -> Dict:
        query = self._build_query(params)
        try:
            response = self.session.post(
                self.overpass_url,
                data={"data": query},
                timeout=self.REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure guard
            raise MapGenerationError("Failed to contact Overpass API") from exc

        if response.status_code >= 500:
            raise MapGenerationError("Overpass API returned a server error")
        if response.status_code >= 400:
            raise MapGenerationError("Overpass API rejected the request")

        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - defensive JSON parsing guard
            raise MapGenerationError("Could not parse Overpass response") from exc

        if "elements" not in payload:
            raise MapGenerationError("Overpass response missing elements")
        return payload

    def _build_query(self, params: MapGenerationParameters) -> str:
        radius = max(50, min(params.radius_m, 5000))
        lat = params.latitude
        lon = params.longitude
        return (
            "[out:json][timeout:90];"
            "("  # begin union
            f"node(around:{radius},{lat},{lon})[\"highway\"];"
            f"way(around:{radius},{lat},{lon})[\"highway\"];"
            f"node(around:{radius},{lat},{lon})[\"railway\"=\"station\"];"
            f"node(around:{radius},{lat},{lon})[\"public_transport\"=\"station\"];"
            f"node(around:{radius},{lat},{lon})[\"highway\"=\"bus_stop\"];"
            f"node(around:{radius},{lat},{lon})[\"amenity\"];"
            f"node(around:{radius},{lat},{lon})[\"building\"];"
            f"way(around:{radius},{lat},{lon})[\"building\"];"
            ");"
            "out body;"
            ">;"
            "out skel qt;"
        )

    def _build_graph(self, payload: Dict) -> Tuple[Dict[int, _OsmNode], List[_OsmWay]]:
        nodes: Dict[int, _OsmNode] = {}
        ways: List[_OsmWay] = []

        # First pass: collect nodes
        for element in payload.get("elements", []):
            if element.get("type") != "node":
                continue
            osm_id = int(element["id"])
            nodes[osm_id] = _OsmNode(
                osm_id=osm_id,
                lat=float(element.get("lat")),
                lon=float(element.get("lon")),
                tags={k: str(v) for k, v in (element.get("tags") or {}).items()},
                neighbors=set(),
                ways=set(),
            )

        # Second pass: collect ways and augment node connectivity
        for element in payload.get("elements", []):
            if element.get("type") != "way":
                continue
            node_ids = [int(node_id) for node_id in element.get("nodes", [])]
            way = _OsmWay(
                osm_id=int(element["id"]),
                node_ids=node_ids,
                tags={k: str(v) for k, v in (element.get("tags") or {}).items()},
            )
            ways.append(way)
            for start, end in zip(node_ids, node_ids[1:]):
                if start in nodes and end in nodes:
                    nodes[start].neighbors.add(end)
                    nodes[end].neighbors.add(start)
                    nodes[start].ways.add(way.osm_id)
                    nodes[end].ways.add(way.osm_id)

        return nodes, ways

    # ------------------------------------------------------------------
    # Node selection and scaling
    # ------------------------------------------------------------------

    def _select_nodes(
        self,
        params: MapGenerationParameters,
        graph: Tuple[Dict[int, _OsmNode], List[_OsmWay]],
    ) -> Tuple[Dict[int, Tuple[_OsmNode, str]], List[_OsmWay]]:
        nodes, ways = graph
        rng = random.Random(self._seed_from_params(params))

        total_target = self._resolve_total_target(params.complexity)
        type_targets = self._resolve_type_targets(params.complexity, total_target)

        candidates: Dict[str, List[_OsmNode]] = {code: [] for code in self.NODE_TYPE_LABELS}

        for osm_node in nodes.values():
            code = self._classify_node(osm_node)
            if code:
                candidates[code].append(osm_node)
            elif osm_node.neighbors:
                candidates["I"].append(osm_node)

        selected: Dict[int, Tuple[_OsmNode, str]] = {}
        selected_counts: Dict[str, int] = {code: 0 for code in self.NODE_TYPE_LABELS}

        order = ["H", "W", "TS", "BS", "I"]
        for code in order:
            target = type_targets.get(code, 0)
            pool = candidates.get(code, [])
            if not pool:
                continue
            ranked = self._rank_candidates(code, pool)
            rng.shuffle(ranked)
            for osm_node in ranked:
                if selected_counts[code] >= target:
                    break
                if osm_node.osm_id in selected:
                    continue
                selected[osm_node.osm_id] = (osm_node, code)
                selected_counts[code] += 1

        # If we are short on the total target, top up with remaining intersection candidates.
        if len(selected) < total_target and candidates.get("I"):
            remaining = [node for node in self._rank_candidates("I", candidates["I"]) if node.osm_id not in selected]
            rng.shuffle(remaining)
            for osm_node in remaining:
                if len(selected) >= total_target:
                    break
                selected[osm_node.osm_id] = (osm_node, "I")
                selected_counts["I"] += 1

        return selected, ways

    def _classify_node(self, node: _OsmNode) -> Optional[str]:
        tags = node.tags
        highway = tags.get("highway")
        amenity = tags.get("amenity")
        building = tags.get("building")
        landuse = tags.get("landuse")
        public_transport = tags.get("public_transport")
        railway = tags.get("railway")

        if railway == "station" or public_transport == "station" or tags.get("station") == "train":
            return "TS"
        if highway == "bus_stop" or amenity in {"bus_station"} or public_transport in {"stop_position", "platform"}:
            return "BS"
        if amenity in {"university", "school", "hospital"}:
            return "W"
        if amenity in {"office", "coworking_space", "company", "factory", "industrial"}:
            return "W"
        if building in {"industrial", "commercial", "retail", "office"}:
            return "W"
        if landuse in {"industrial", "commercial"}:
            return "W"
        if building in {"house", "detached", "semidetached_house", "apartments", "residential"}:
            return "H"
        if amenity in {"restaurant", "cafe", "bar", "pub", "cinema"}:
            return "H"
        if landuse == "residential":
            return "H"
        if highway in {"traffic_signals", "crossing", "give_way"} or len(node.neighbors) >= 3:
            return "I"
        return None

    def _rank_candidates(self, code: str, nodes: Sequence[_OsmNode]) -> List[_OsmNode]:
        # Higher degree intersections are preferred when selecting nodes that rely on connectivity.
        if code == "I":
            return sorted(nodes, key=lambda node: len(node.neighbors), reverse=True)
        return list(nodes)

    def _resolve_total_target(self, complexity: int) -> int:
        total = max(self.MIN_TOTAL_NODES, 10 * max(1, complexity))
        return min(total, self.MAX_TOTAL_NODES)

    def _resolve_type_targets(self, complexity: int, total_target: int) -> Dict[str, int]:
        base = {
            "H": max(4, min(10, complexity * 2)),
            "W": max(4, min(10, complexity * 2)),
            "TS": max(1, complexity // 3 or 1),
            "BS": max(2, min(12, complexity + 2)),
        }
        assigned = sum(base.values())
        # Reduce counts if their sum exceeds the total target.
        while assigned > total_target:
            for code in ["BS", "TS", "W", "H"]:
                if assigned <= total_target:
                    break
                if base[code] > 1:
                    base[code] -= 1
                    assigned -= 1
        base["I"] = max(0, total_target - assigned)
        return base

    def _scale_nodes(self, selected: Dict[int, Tuple[_OsmNode, str]]) -> Dict[int, _SelectedNode]:
        lats = [item[0].lat for item in selected.values()]
        lons = [item[0].lon for item in selected.values()]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        lat_span = max(0.0001, max_lat - min_lat)
        lon_span = max(0.0001, max_lon - min_lon)

        scaled: Dict[int, _SelectedNode] = {}
        for osm_id, (osm_node, code) in selected.items():
            x = (osm_node.lon - min_lon) / lon_span * self.GRID_SIZE
            y = (osm_node.lat - min_lat) / lat_span * self.GRID_SIZE
            x = max(0.0, min(self.GRID_SIZE, x))
            y = max(0.0, min(self.GRID_SIZE, y))
            scaled[osm_id] = _SelectedNode(
                osm_node=osm_node,
                code=code,
                x_position=x,
                y_position=y,
            )
        return scaled

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_map(
        self,
        params: MapGenerationParameters,
        selected_nodes: Dict[int, _SelectedNode],
        ways: List[_OsmWay],
        author,
        updated_by,
    ) -> GeneratedMapResult:
        node_type_lookup = NodeType.objects.in_bulk(field_name="short")
        missing_codes = [code for code in self.NODE_TYPE_LABELS if code not in node_type_lookup]
        if missing_codes:
            raise MapGenerationError(
                "Missing NodeType definitions for: " + ", ".join(sorted(missing_codes))
            )

        scale = max(1.0, (params.radius_m * 2) / self.GRID_SIZE)
        map_name = (params.name or "").strip() or self._default_map_name(params)

        with transaction.atomic():
            game_map = GameMap.objects.create(
                name=map_name,
                x_dim=self.GRID_SIZE,
                y_dim=self.GRID_SIZE,
                scale=scale,
                author=author,
                updated_by=updated_by or author,
            )

            created_nodes: List[Node] = []
            node_counts: Dict[str, int] = {code: 0 for code in self.NODE_TYPE_LABELS}
            node_lookup: Dict[int, Node] = {}

            for osm_id, selected in selected_nodes.items():
                code = selected.code
                node_counts[code] += 1
                node_type = node_type_lookup[code]
                node_name = f"{node_type.name} {node_counts[code]}"
                node_obj = Node.objects.create(
                    game_map=game_map,
                    name=node_name,
                    x_position=selected.x_position,
                    y_position=selected.y_position,
                )
                node_obj.node_type.add(node_type)
                created_nodes.append(node_obj)
                node_lookup[osm_id] = node_obj

            created_edges = self._create_edges(game_map, node_lookup, selected_nodes, ways)

            summary = {
                "total_nodes": len(created_nodes),
                "total_edges": len(created_edges),
            }
            for code, label in self.NODE_TYPE_LABELS.items():
                summary[f"nodes_{code.lower()}"] = sum(
                    1 for selected in selected_nodes.values() if selected.code == code
                )

        return GeneratedMapResult(
            game_map=game_map,
            nodes=created_nodes,
            edges=created_edges,
            summary=summary,
        )

    def _create_edges(
        self,
        game_map: GameMap,
        node_lookup: Dict[int, Node],
        selected_nodes: Dict[int, _SelectedNode],
        ways: List[_OsmWay],
    ) -> List[Edge]:
        edges: List[Edge] = []
        seen: Set[Tuple[int, int]] = set()

        for way in ways:
            relevant_nodes = [osm_id for osm_id in way.node_ids if osm_id in node_lookup]
            if len(relevant_nodes) < 2:
                continue
            for start_id, end_id in zip(relevant_nodes, relevant_nodes[1:]):
                if start_id == end_id:
                    continue
                key = (start_id, end_id)
                reverse_key = (end_id, start_id)
                if key in seen or reverse_key in seen:
                    continue
                start_node = node_lookup[start_id]
                end_node = node_lookup[end_id]
                lanes = self._lanes(way.tags)
                edge = Edge.objects.create(
                    game_map=game_map,
                    name=self._edge_name(way, start_node, end_node),
                    start_node=start_node,
                    end_node=end_node,
                    bike_speed=self._bike_speed(way.tags),
                    walk_speed=self._walk_speed(way.tags),
                    max_lanes=lanes,
                )
                StreetEdge.objects.create(
                    edge=edge,
                    speed_limit=self._speed_limit(way.tags),
                    lanes=lanes,
                    dedicated_bus_lane=self._dedicated_bus_lane(way.tags),
                )
                edges.append(edge)
                seen.add(key)
                seen.add(reverse_key)

        if not edges:
            edges.extend(
                self._fallback_edges(game_map, node_lookup, selected_nodes, seen)
            )
        else:
            # Ensure isolated nodes get at least one connection.
            edges.extend(
                self._connect_isolated_nodes(game_map, node_lookup, selected_nodes, seen)
            )

        return edges

    def _fallback_edges(
        self,
        game_map: GameMap,
        node_lookup: Dict[int, Node],
        selected_nodes: Dict[int, _SelectedNode],
        seen: Set[Tuple[int, int]],
    ) -> List[Edge]:
        nodes = list(node_lookup.items())
        created: List[Edge] = []
        if len(nodes) < 2:
            return created
        for index, (osm_id, node) in enumerate(nodes):
            remaining = [item for idx, item in enumerate(nodes) if idx != index]
            nearest = sorted(remaining, key=lambda item: self._distance(selected_nodes[osm_id], selected_nodes[item[0]]))[:2]
            for neighbor_osm_id, neighbor_node in nearest:
                key = (osm_id, neighbor_osm_id)
                reverse_key = (neighbor_osm_id, osm_id)
                if key in seen or reverse_key in seen:
                    continue
                edge = Edge.objects.create(
                    game_map=game_map,
                    name=f"Link {node.name}-{neighbor_node.name}",
                    start_node=node,
                    end_node=neighbor_node,
                    bike_speed=15,
                    walk_speed=4,
                    max_lanes=1,
                )
                StreetEdge.objects.create(
                    edge=edge,
                    speed_limit=30,
                    lanes=1,
                    dedicated_bus_lane=False,
                )
                created.append(edge)
                seen.add(key)
                seen.add(reverse_key)
        return created

    def _connect_isolated_nodes(
        self,
        game_map: GameMap,
        node_lookup: Dict[int, Node],
        selected_nodes: Dict[int, _SelectedNode],
        seen: Set[Tuple[int, int]],
    ) -> List[Edge]:
        adjacency: Dict[int, set[int]] = {node_id: set() for node_id in node_lookup}
        for start_id, end_id in list(seen):
            adjacency[start_id].add(end_id)
            adjacency[end_id].add(start_id)

        created: List[Edge] = []
        for osm_id, node in node_lookup.items():
            if adjacency[osm_id]:
                continue
            nearest = self._nearest_neighbor(osm_id, selected_nodes, exclude={osm_id})
            if nearest is None:
                continue
            neighbor_node = node_lookup[nearest]
            key = (osm_id, nearest)
            reverse_key = (nearest, osm_id)
            if key in seen or reverse_key in seen:
                continue
            edge = Edge.objects.create(
                game_map=game_map,
                name=f"Link {node.name}-{neighbor_node.name}",
                start_node=node,
                end_node=neighbor_node,
                bike_speed=15,
                walk_speed=4,
                max_lanes=1,
            )
            StreetEdge.objects.create(
                edge=edge,
                speed_limit=30,
                lanes=1,
                dedicated_bus_lane=False,
            )
            created.append(edge)
            seen.add(key)
            seen.add(reverse_key)
        return created

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _seed_from_params(self, params: MapGenerationParameters) -> int:
        return hash((round(params.latitude, 4), round(params.longitude, 4), params.radius_m, params.complexity)) & 0xFFFFFFFF

    def _edge_name(self, way: _OsmWay, start: Node, end: Node) -> str:
        highway = way.tags.get("highway")
        if highway:
            return f"{highway.title()} {start.pk}-{end.pk}"
        return f"Edge {start.pk}-{end.pk}"

    def _bike_speed(self, tags: Dict[str, str]) -> int:
        highway = tags.get("highway")
        if highway == "cycleway":
            return 20
        if highway in {"motorway", "trunk"}:
            return 0
        return 15

    def _walk_speed(self, tags: Dict[str, str]) -> int:
        highway = tags.get("highway")
        if highway in {"motorway", "trunk"}:
            return 0
        return 4

    def _lanes(self, tags: Dict[str, str]) -> int:
        lanes = tags.get("lanes")
        if lanes and lanes.isdigit():
            return max(1, min(4, int(lanes)))
        highway = tags.get("highway")
        if highway in {"motorway", "trunk"}:
            return 4
        if highway in {"primary", "secondary"}:
            return 2
        return 1

    def _speed_limit(self, tags: Dict[str, str]) -> int:
        if "maxspeed" in tags:
            try:
                return int(tags["maxspeed"].split()[0])
            except (ValueError, IndexError):  # pragma: no cover - best effort parse
                pass
        highway = tags.get("highway")
        return self.HIGHWAY_SPEED_LIMITS.get(highway, 30)

    def _nearest_neighbor(
        self,
        osm_id: int,
        selected_nodes: Dict[int, _SelectedNode],
        exclude: Optional[Iterable[int]] = None,
    ) -> Optional[int]:
        exclude = set(exclude or [])
        origin = selected_nodes[osm_id]
        best_distance = math.inf
        best_neighbor: Optional[int] = None
        for candidate_id, candidate in selected_nodes.items():
            if candidate_id == osm_id or candidate_id in exclude:
                continue
            distance = self._distance(origin, candidate)
            if distance < best_distance:
                best_distance = distance
                best_neighbor = candidate_id
        return best_neighbor

    def _distance(self, a: _SelectedNode, b: _SelectedNode) -> float:
        return math.hypot(a.x_position - b.x_position, a.y_position - b.y_position)

    def _dedicated_bus_lane(self, tags: Dict[str, str]) -> bool:
        if tags.get("bus") == "designated":
            return True
        return any(tag_key.startswith("lanes:bus") for tag_key in tags)

    def _default_map_name(self, params: MapGenerationParameters) -> str:
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        return f"Generated Map {timestamp}"


__all__ = [
    "MapGenerationService",
    "MapGenerationError",
    "GeneratedMapResult",
]
