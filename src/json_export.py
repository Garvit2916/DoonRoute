from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from graph_loader import GraphData
from routing import CombinedRoute, RouteLeg


def _point_record(
    graph: GraphData,
    node_index: int,
    *,
    name: str = "",
    original_latitude: float | None = None,
    original_longitude: float | None = None,
    snap_distance_m: float | None = None,
) -> dict[str, Any]:
    longitude, latitude = graph.coordinates[node_index]
    return {
        "name": name,
        "node_index": node_index,
        "osm_node": graph.node_ids[node_index],
        "latitude": latitude,
        "longitude": longitude,
        "original_latitude": original_latitude,
        "original_longitude": original_longitude,
        "snap_distance_m": snap_distance_m,
    }


def _leg_record(graph: GraphData, leg: RouteLeg) -> dict[str, Any]:
    return {
        "source_node_index": leg.source_index,
        "target_node_index": leg.target_index,
        "source_osm_node": graph.node_ids[leg.source_index],
        "target_osm_node": graph.node_ids[leg.target_index],
        "distance_m": float(leg.distance_m),
        "distance_km": float(leg.distance_m / 1000.0),
        "path_node_count": len(leg.result.path),
        "path_node_ids": [graph.node_ids[index] for index in leg.result.path],
        "path_coordinates": [
            {
                "node_index": index,
                "osm_node": graph.node_ids[index],
                "latitude": graph.coordinates[index][1],
                "longitude": graph.coordinates[index][0],
            }
            for index in leg.result.path
        ],
        "road_names": list(leg.road_names),
        "edge_distances": list(leg.edge_distances),
        "visited": leg.result.visited,
        "relaxations": leg.result.relaxations,
    }


def build_route_document(
    *,
    graph: GraphData,
    route: CombinedRoute,
    waypoints: list[dict[str, Any]],
    algorithm: str,
    execution_time_ms: float,
    dataset_path: str,
    benchmark: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if len(waypoints) != len(route.waypoint_indices):
        raise ValueError("Waypoint metadata does not match the route stops.")

    stops = [
        _point_record(
            graph,
            node_index,
            name=str(waypoint.get("name", "")),
            original_latitude=waypoint.get("original_latitude"),
            original_longitude=waypoint.get("original_longitude"),
            snap_distance_m=waypoint.get("snap_distance_m"),
        )
        for waypoint, node_index in zip(waypoints, route.waypoint_indices, strict=True)
    ]
    combined_road_names: list[str] = []
    for leg in route.legs:
        for name in leg.road_names:
            if not combined_road_names or combined_road_names[-1] != name:
                combined_road_names.append(name)

    return {
        "project": "DoonRoute",
        "exported_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "path": dataset_path,
            "node_count": graph.node_count,
            "edge_count": graph.edge_count,
            "weight": "road distance in metres",
        },
        "algorithm": algorithm,
        "execution_time_ms": float(execution_time_ms),
        "source": stops[0],
        "destination": stops[-1],
        "waypoints": stops,
        "legs": [_leg_record(graph, leg) for leg in route.legs],
        "combined_route": {
            "distance_m": float(route.distance_m),
            "distance_km": float(route.distance_m / 1000.0),
            "path_node_count": len(route.path),
            "path_node_ids": [graph.node_ids[index] for index in route.path],
            "path_coordinates": [
                {
                    "node_index": index,
                    "osm_node": graph.node_ids[index],
                    "latitude": graph.coordinates[index][1],
                    "longitude": graph.coordinates[index][0],
                }
                for index in route.path
            ],
            "road_names": combined_road_names,
        },
        "benchmark": benchmark,
    }


def write_route_json(document: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    return destination


def load_route_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
