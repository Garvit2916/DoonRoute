from __future__ import annotations

import csv
import time
from itertools import pairwise
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cython_dijkstra import CythonDijkstra

from graph_loader import GraphData, load_graph
from json_export import build_route_document, write_route_json
from python_dijkstra import PythonDijkstra
from routing import (
    Location,
    location_by_role,
    path_distance,
    read_locations,
    road_names,
    route_waypoints,
    snap_locations,
    write_binary_graph,
)

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "raw" / "dehradun_drive.graphml"
LOCATIONS_PATH = ROOT / "data" / "locations.csv"
PROCESSED = ROOT / "data" / "processed"
EXPORTS = ROOT / "data" / "exports"
RESULTS = ROOT / "results"
BINARY_GRAPH = PROCESSED / "graph.bin"
TOLERANCE_M = 1e-6


def validate_result(
    graph: GraphData,
    result: Any,
    source: Location,
    target: Location,
    implementation: str,
) -> None:
    if not result.reachable:
        raise AssertionError(f"{implementation} could not reach {target.id}.")
    if not result.path or result.path[0] != source.node_index:
        raise AssertionError(f"{implementation} path has the wrong source.")
    if result.path[-1] != target.node_index:
        raise AssertionError(f"{implementation} path has the wrong target.")
    reconstructed = path_distance(graph.adjacency, result.path)
    if abs(reconstructed - result.distance) > TOLERANCE_M:
        raise AssertionError(
            f"{implementation} distance does not match its reconstructed path."
        )


def result_row(
    graph: GraphData,
    record_type: str,
    leg: str,
    source: Location,
    target: Location,
    implementation: str,
    result: Any,
) -> dict[str, Any]:
    osm_path = [graph.node_ids[index] for index in result.path]
    return {
        "record_type": record_type,
        "leg": leg,
        "from_id": source.id,
        "from_name": source.name,
        "to_id": target.id,
        "to_name": target.name,
        "implementation": implementation,
        "distance_m": round(float(result.distance), 6),
        "edge_count": max(len(result.path) - 1, 0),
        "node_count": len(result.path),
        "visited": result.visited if result.visited is not None else "",
        "relaxations": result.relaxations if result.relaxations is not None else "",
        "path_nodes": " ".join(str(node) for node in osm_path),
        "road_names": "; ".join(road_names(graph, result.path)),
    }


def total_row(
    record_type: str,
    leg: str,
    source: Location,
    target: Location,
    implementation: str,
    distance: float,
    edge_count: int,
) -> dict[str, Any]:
    return {
        "record_type": record_type,
        "leg": leg,
        "from_id": source.id,
        "from_name": source.name,
        "to_id": target.id,
        "to_name": target.name,
        "implementation": implementation,
        "distance_m": round(distance, 6),
        "edge_count": edge_count,
        "node_count": "",
        "visited": "",
        "relaxations": "",
        "path_nodes": "",
        "road_names": "",
    }


def plot_route_comparison(
    leg_distances: list[float],
    mandatory_total: float,
    unconstrained: float,
    output: Path,
) -> None:
    detour = mandatory_total - unconstrained
    detour_pct = (detour / unconstrained) * 100
    labels = [
        "A to B",
        "B to C",
        "C to D",
        "Mandatory total",
        "Unconstrained A to D",
        f"Detour\n(+{detour_pct:.1f}%)",
    ]
    values = [
        value / 1000
        for value in [*leg_distances, mandatory_total, unconstrained, detour]
    ]
    colors = ["#4c78a8", "#4c78a8", "#4c78a8", "#2e7d32", "#1f77b4", "#d95f02"]
    figure, axis = plt.subplots(figsize=(10, 5.2))
    bars = axis.bar(labels, values, color=colors, width=0.62)
    for bar, value in zip(bars, values, strict=True):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.35,
            f"{value:.3f} km",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="normal",
        )
    axis.set_ylabel("Road distance (km)", fontsize=10)
    axis.set_title(
        "DoonRoute Road Distance & Mandatory Detour Comparison",
        fontsize=11,
        fontweight="bold",
    )
    axis.set_ylim(0, max(values) * 1.18)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", linestyle="--", alpha=0.3)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)

    print(f"Loading {GRAPH_PATH}")
    graph = load_graph(GRAPH_PATH)
    write_binary_graph(graph, BINARY_GRAPH)
    print(f"Graph: {graph.node_count:,} nodes, {graph.edge_count:,} directed edges")
    print(f"Intersections: {len(graph.intersection_indices):,}")

    locations = snap_locations(graph, read_locations(LOCATIONS_PATH))
    for location in locations:
        print(
            f"{location.id} {location.name}: node {location.osm_node}, "
            f"snap {location.snap_distance_m:.1f} m"
        )

    a = location_by_role(locations, "start")
    b = location_by_role(locations, "shopping")
    c = location_by_role(locations, "landmark")
    d = location_by_role(locations, "destination")
    stops = [a, b, c, d]
    legs = list(pairwise(stops))
    leg_names = ["A-B", "B-C", "C-D"]

    rows: list[dict[str, Any]] = []
    leg_distances_by_implementation: dict[str, list[float]] = {}
    unconstrained_by_implementation: dict[str, float] = {}

    with CythonDijkstra(BINARY_GRAPH) as cython:
        solvers = {
            "python": PythonDijkstra(graph.adjacency),
            "cython": cython,
        }

        for implementation, solver in solvers.items():
            distances: list[float] = []
            edge_count = 0
            for leg_name, (source, target) in zip(leg_names, legs, strict=True):
                result = solver.shortest_path(source.node_index, target.node_index)
                validate_result(graph, result, source, target, implementation)
                distances.append(float(result.distance))
                edge_count += max(len(result.path) - 1, 0)
                rows.append(
                    result_row(
                        graph,
                        "leg",
                        leg_name,
                        source,
                        target,
                        implementation,
                        result,
                    )
                )
            leg_distances_by_implementation[implementation] = distances
            rows.append(
                total_row(
                    "mandatory_total",
                    "A-D via mandatory stops",
                    a,
                    d,
                    implementation,
                    sum(distances),
                    edge_count,
                )
            )
            unconstrained_result = solver.shortest_path(a.node_index, d.node_index)
            validate_result(graph, unconstrained_result, a, d, implementation)
            unconstrained_by_implementation[implementation] = float(
                unconstrained_result.distance
            )
            rows.append(
                result_row(
                    graph,
                    "unconstrained",
                    "A-D direct",
                    a,
                    d,
                    implementation,
                    unconstrained_result,
                )
            )

    reference = leg_distances_by_implementation["python"]
    for implementation, distances in leg_distances_by_implementation.items():
        for index, (expected, observed) in enumerate(
            zip(reference, distances, strict=True)
        ):
            if abs(expected - observed) > TOLERANCE_M:
                raise AssertionError(
                    f"{implementation} disagrees on leg {leg_names[index]}."
                )

    mandatory_total = sum(reference)
    unconstrained = unconstrained_by_implementation["python"]
    for implementation, distance in unconstrained_by_implementation.items():
        if abs(distance - unconstrained) > TOLERANCE_M:
            raise AssertionError(
                f"{implementation} disagrees on the unconstrained route."
            )

    with (RESULTS / "route_results.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    plot_route_comparison(
        reference,
        mandatory_total,
        unconstrained,
        RESULTS / "route_comparison.png",
    )

    waypoint_metadata = [
        {
            "name": location.name,
            "original_latitude": location.latitude,
            "original_longitude": location.longitude,
            "snap_distance_m": location.snap_distance_m,
        }
        for location in stops
    ]
    python_solver = PythonDijkstra(graph.adjacency)
    started = time.perf_counter_ns()
    sample_route = route_waypoints(
        python_solver,
        graph,
        [location.node_index for location in stops],
    )
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
    sample_document = build_route_document(
        graph=graph,
        route=sample_route,
        waypoints=waypoint_metadata,
        algorithm="Python Dijkstra",
        execution_time_ms=elapsed_ms,
        dataset_path=str(GRAPH_PATH.relative_to(ROOT)),
    )
    sample_path = write_route_json(sample_document, EXPORTS / "route_export.json")

    print("\nRoute summary")
    for leg_name, distance in zip(leg_names, reference, strict=True):
        print(f"  {leg_name}: {distance / 1000:.3f} km")
    print(f"  Mandatory total: {mandatory_total / 1000:.3f} km")
    print(f"  Unconstrained A to D: {unconstrained / 1000:.3f} km")
    print(f"  Mandatory detour: {(mandatory_total - unconstrained) / 1000:.3f} km")
    print("\nAll implementations agree within 1e-6 m.")
    print(f"Sample JSON export: {sample_path}")


if __name__ == "__main__":
    main()
