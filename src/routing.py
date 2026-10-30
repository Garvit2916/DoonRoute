from __future__ import annotations

import ast
import csv
import math
import struct
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import networkx as nx

from python_dijkstra import PathResult

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    role: str
    latitude: float
    longitude: float
    source_url: str = ""
    notes: str = ""
    node_index: int | None = None
    osm_node: int | None = None
    snap_distance_m: float | None = None


@dataclass
class GraphData:
    node_ids: list[int]
    index_of: dict[int, int]
    adjacency: dict[int, list[tuple[int, float]]]
    graph: nx.MultiDiGraph
    coordinates: list[tuple[float, float]]
    edge_attributes: dict[tuple[int, int], list[dict[str, Any]]]

    @property
    def node_count(self) -> int:
        return len(self.node_ids)

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self.adjacency.values())


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, (list, tuple, set)):
                return "; ".join(
                    str(item).strip() for item in parsed if str(item).strip()
                )
        return text
    if isinstance(value, (list, tuple, set)):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def load_graph(path: str | Path) -> GraphData:
    source = nx.read_graphml(str(path), node_type=int, force_multigraph=True)
    if not source.is_directed():
        source = source.to_directed()

    node_ids = [int(node) for node in source.nodes]
    index_of = {node: index for index, node in enumerate(node_ids)}
    coordinates = [
        (float(source.nodes[node]["x"]), float(source.nodes[node]["y"]))
        for node in node_ids
    ]
    adjacency: dict[int, list[tuple[int, float]]] = {
        index: [] for index in range(len(node_ids))
    }
    indexed = nx.MultiDiGraph()

    for source_node, target_node, key, data in source.edges(keys=True, data=True):
        source_index = index_of[int(source_node)]
        target_index = index_of[int(target_node)]
        length = float(data["length"])
        adjacency[source_index].append((target_index, length))
        indexed.add_edge(
            source_index,
            target_index,
            key=key,
            length=length,
            name=_text(data.get("name")),
            highway=_text(data.get("highway")),
        )

    edge_attributes: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for source_node, target_node, key, data in indexed.edges(keys=True, data=True):
        edge_attributes.setdefault((source_node, target_node), []).append(
            {
                "key": key,
                "length": float(data["length"]),
                "name": _text(data.get("name")),
                "highway": _text(data.get("highway")),
            }
        )

    return GraphData(
        node_ids=node_ids,
        index_of=index_of,
        adjacency=adjacency,
        graph=indexed,
        coordinates=coordinates,
        edge_attributes=edge_attributes,
    )


def write_binary_adjacency(
    adjacency: dict[int, list[tuple[int, float]]],
    node_count: int,
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    edge_count = sum(len(edges) for edges in adjacency.values())
    with destination.open("wb") as handle:
        handle.write(b"DRG1")
        handle.write(struct.pack("<QQ", node_count, edge_count))
        for source, edges in adjacency.items():
            for target, weight in edges:
                if not math.isfinite(weight) or weight < 0:
                    raise ValueError("Graph contains an invalid edge weight.")
                handle.write(struct.pack("<QQd", source, target, float(weight)))
    return destination


def write_binary_graph(graph: GraphData, path: str | Path) -> Path:
    return write_binary_adjacency(graph.adjacency, graph.node_count, path)


def read_locations(path: str | Path) -> list[Location]:
    locations: list[Location] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            locations.append(
                Location(
                    id=row["id"].strip(),
                    name=row["name"].strip(),
                    role=row["role"].strip(),
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    source_url=row.get("source_url", "").strip(),
                    notes=row.get("notes", "").strip(),
                )
            )
    return locations


def haversine_m(
    latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float
) -> float:
    latitude_a_rad = math.radians(latitude_a)
    latitude_b_rad = math.radians(latitude_b)
    delta_latitude = math.radians(latitude_b - latitude_a)
    delta_longitude = math.radians(longitude_b - longitude_a)
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude_a_rad)
        * math.cos(latitude_b_rad)
        * math.sin(delta_longitude / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(value))


def snap_locations(graph: GraphData, locations: list[Location]) -> list[Location]:
    snapped: list[Location] = []
    for location in locations:
        best_index = 0
        best_distance = math.inf
        for index, (longitude, latitude) in enumerate(graph.coordinates):
            distance = haversine_m(
                location.latitude,
                location.longitude,
                latitude,
                longitude,
            )
            if distance < best_distance:
                best_distance = distance
                best_index = index
        snapped.append(
            Location(
                id=location.id,
                name=location.name,
                role=location.role,
                latitude=location.latitude,
                longitude=location.longitude,
                source_url=location.source_url,
                notes=location.notes,
                node_index=best_index,
                osm_node=graph.node_ids[best_index],
                snap_distance_m=best_distance,
            )
        )
    return snapped


def location_by_role(locations: list[Location], role: str) -> Location:
    for location in locations:
        if location.role == role:
            if location.node_index is None:
                raise ValueError(f"Location {location.id} is not snapped.")
            return location
    raise ValueError(f"Missing required location role: {role}")


def path_distance(
    adjacency: dict[int, list[tuple[int, float]]], path: list[int]
) -> float:
    total = 0.0
    for source, target in pairwise(path):
        weights = [weight for node, weight in adjacency[source] if node == target]
        if not weights:
            raise ValueError(f"Path edge {source} -> {target} is not in the graph.")
        total += min(weights)
    return total


def road_names(graph: GraphData, path: list[int]) -> list[str]:
    names: list[str] = []
    for source, target in pairwise(path):
        candidates = graph.edge_attributes.get((source, target), [])
        if not candidates:
            continue
        edge = min(candidates, key=lambda item: item["length"])
        name = edge["name"] or f"Unnamed {edge['highway'] or 'road'}"
        if not names or names[-1] != name:
            names.append(name)
    return names


class NetworkXDijkstra:
    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph

    def shortest_path(self, source: int, target: int) -> PathResult:
        if source == target:
            return PathResult(0.0, [source], None, None, True)
        try:
            distance, path = nx.single_source_dijkstra(
                self.graph, source, target, weight="length"
            )
        except nx.NetworkXNoPath:
            return PathResult(math.inf, [], None, None, False)
        return PathResult(float(distance), list(path), None, None, True)
