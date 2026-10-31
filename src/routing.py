from __future__ import annotations

import csv
import math
import struct
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from graph_loader import EARTH_RADIUS_M, GraphData
from intersection import SpatialIndex
from python_dijkstra import PathResult


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


@dataclass(frozen=True)
class RouteLeg:
    source_index: int
    target_index: int
    result: PathResult
    edge_distances: list[dict[str, Any]]
    road_names: list[str]

    @property
    def distance_m(self) -> float:
        return float(self.result.distance)


@dataclass(frozen=True)
class CombinedRoute:
    waypoint_indices: list[int]
    legs: list[RouteLeg]
    path: list[int]
    distance_m: float


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


def snap_locations(graph: GraphData, locations: list[Location]) -> list[Location]:
    index = SpatialIndex(graph)
    snapped: list[Location] = []
    for location in locations:
        nearest = index.nearest(location.latitude, location.longitude)
        if nearest is None:
            raise ValueError(
                f"Could not snap location {location.id} to an intersection."
            )
        snapped.append(
            Location(
                id=location.id,
                name=location.name,
                role=location.role,
                latitude=location.latitude,
                longitude=location.longitude,
                source_url=location.source_url,
                notes=location.notes,
                node_index=nearest.node_index,
                osm_node=nearest.osm_node,
                snap_distance_m=nearest.distance_m,
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


def edge_distances(graph: GraphData, path: list[int]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source, target in pairwise(path):
        candidates = graph.edge_attributes.get((source, target), [])
        if not candidates:
            raise ValueError(f"Path edge {source} -> {target} is not in the graph.")
        edge = min(candidates, key=lambda item: item["length"])
        records.append(
            {
                "from_node_index": source,
                "to_node_index": target,
                "from_osm_node": graph.node_ids[source],
                "to_osm_node": graph.node_ids[target],
                "distance_m": float(edge["length"]),
                "name": edge["name"],
                "highway": edge["highway"],
            }
        )
    return records


def road_names(graph: GraphData, path: list[int]) -> list[str]:
    names: list[str] = []
    for edge in edge_distances(graph, path):
        name = edge["name"] or f"Unnamed {edge['highway'] or 'road'}"
        if not names or names[-1] != name:
            names.append(name)
    return names


def route_leg(
    solver: Any,
    graph: GraphData,
    source_index: int,
    target_index: int,
) -> RouteLeg:
    result = solver.shortest_path(source_index, target_index)
    if not result.reachable:
        raise ValueError(f"No route from node {source_index} to {target_index}.")
    if not result.path or result.path[0] != source_index:
        raise ValueError("Solver returned a path with the wrong source.")
    if result.path[-1] != target_index:
        raise ValueError("Solver returned a path with the wrong target.")
    reconstructed = path_distance(graph.adjacency, result.path)
    if abs(reconstructed - result.distance) > 1e-6:
        raise ValueError("Solver distance does not match its path.")
    return RouteLeg(
        source_index=source_index,
        target_index=target_index,
        result=result,
        edge_distances=edge_distances(graph, result.path),
        road_names=road_names(graph, result.path),
    )


def route_waypoints(
    solver: Any,
    graph: GraphData,
    waypoint_indices: list[int],
) -> CombinedRoute:
    if len(waypoint_indices) < 2:
        raise ValueError("At least a start and destination are required.")
    legs = [
        route_leg(solver, graph, source, target)
        for source, target in pairwise(waypoint_indices)
    ]
    combined_path: list[int] = []
    for leg in legs:
        if combined_path:
            combined_path.extend(leg.result.path[1:])
        else:
            combined_path.extend(leg.result.path)
    return CombinedRoute(
        waypoint_indices=list(waypoint_indices),
        legs=legs,
        path=combined_path,
        distance_m=sum(leg.distance_m for leg in legs),
    )
