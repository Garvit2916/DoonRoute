from __future__ import annotations

import csv
import math
import struct
import time
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
    algorithm_ms: float = 0.0

    @property
    def distance_m(self) -> float:
        return float(self.result.distance)


@dataclass(frozen=True)
class CombinedRoute:
    waypoint_indices: list[int]
    legs: list[RouteLeg]
    path: list[int]
    distance_m: float
    algorithm_ms: float = 0.0
    workflow_ms: float = 0.0


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
    index = getattr(graph, "spatial_index", None)
    if index is None:
        index = SpatialIndex(graph)
        try:
            graph.spatial_index = index
        except (AttributeError, TypeError):
            pass
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


def road_names(
    graph: GraphData,
    path: list[int],
    records: list[dict[str, Any]] | None = None,
) -> list[str]:
    names: list[str] = []
    if records is None:
        records = edge_distances(graph, path)
    for edge in records:
        name = edge["name"] or f"Unnamed {edge['highway'] or 'road'}"
        if not names or names[-1] != name:
            names.append(name)
    return names


def clear_route_cache(graph: GraphData | None = None) -> None:
    if graph is not None:
        if hasattr(graph, "_leg_cache") and graph._leg_cache is not None:
            graph._leg_cache.clear()
        if hasattr(graph, "_route_cache") and graph._route_cache is not None:
            graph._route_cache.clear()


def route_leg(
    solver: Any,
    graph: GraphData,
    source_index: int,
    target_index: int,
) -> RouteLeg:
    leg_cache = getattr(graph, "_leg_cache", None)
    if leg_cache is None:
        leg_cache = {}
        try:
            graph._leg_cache = leg_cache
        except (AttributeError, TypeError):
            pass
    solver_key = getattr(solver, "__class__", type(solver))
    cache_key = (solver_key, source_index, target_index)
    cached_leg = leg_cache.get(cache_key)
    if cached_leg is not None:
        return cached_leg

    t0_alg = time.perf_counter_ns()
    result = solver.shortest_path(source_index, target_index)
    alg_ms = (time.perf_counter_ns() - t0_alg) / 1_000_000.0

    if not result.reachable:
        raise ValueError(f"No route from node {source_index} to {target_index}.")
    if not result.path or result.path[0] != source_index:
        raise ValueError("Solver returned a path with the wrong source.")
    if result.path[-1] != target_index:
        raise ValueError("Solver returned a path with the wrong target.")
    edges = edge_distances(graph, result.path)
    reconstructed = sum(record["distance_m"] for record in edges)
    if abs(reconstructed - result.distance) > 1e-6:
        raise ValueError("Solver distance does not match its path.")
    names = road_names(graph, result.path, records=edges)
    leg = RouteLeg(
        source_index=source_index,
        target_index=target_index,
        result=result,
        edge_distances=edges,
        road_names=names,
        algorithm_ms=alg_ms,
    )
    leg_cache[cache_key] = leg
    return leg


def route_waypoints(
    solver: Any,
    graph: GraphData,
    waypoint_indices: list[int],
) -> CombinedRoute:
    if len(waypoint_indices) < 2:
        raise ValueError("At least a start and destination are required.")
    route_cache = getattr(graph, "_route_cache", None)
    if route_cache is None:
        route_cache = {}
        try:
            graph._route_cache = route_cache
        except (AttributeError, TypeError):
            pass
    solver_key = getattr(solver, "__class__", type(solver))
    route_key = (solver_key, tuple(waypoint_indices))
    cached_route = route_cache.get(route_key)
    if cached_route is not None:
        return cached_route

    t0_wf = time.perf_counter_ns()
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
    wf_ms = (time.perf_counter_ns() - t0_wf) / 1_000_000.0
    alg_ms = sum(leg.algorithm_ms for leg in legs)
    route = CombinedRoute(
        waypoint_indices=list(waypoint_indices),
        legs=legs,
        path=combined_path,
        distance_m=sum(leg.distance_m for leg in legs),
        algorithm_ms=alg_ms,
        workflow_ms=wf_ms,
    )
    route_cache[route_key] = route
    return route
