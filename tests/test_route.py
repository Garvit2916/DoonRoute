from functools import lru_cache
from itertools import pairwise
from pathlib import Path

from cython_dijkstra import CythonDijkstra

from graph_loader import load_graph
from python_dijkstra import PythonDijkstra
from random_points import generate_random_points
from routing import (
    location_by_role,
    path_distance,
    read_locations,
    route_waypoints,
    snap_locations,
    write_binary_graph,
)

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "raw" / "dehradun_drive.graphml"
LOCATIONS_PATH = ROOT / "data" / "locations.csv"
BINARY_GRAPH = ROOT / "data" / "processed" / "graph.bin"
TOLERANCE_M = 1e-6


@lru_cache(maxsize=1)
def real_graph():
    return load_graph(GRAPH_PATH)


@lru_cache(maxsize=1)
def real_binary_graph() -> Path:
    graph = real_graph()
    write_binary_graph(graph, BINARY_GRAPH)
    return BINARY_GRAPH


def test_real_graph_statistics_and_intersections() -> None:
    graph = real_graph()
    assert graph.node_count == 28_248
    assert graph.edge_count == 64_912
    assert len(graph.intersection_indices) > 10_000

    locations = snap_locations(graph, read_locations(LOCATIONS_PATH))
    for location in locations:
        assert location.node_index in graph.intersection_indices


def test_mandatory_waypoint_route_total() -> None:
    graph = real_graph()
    locations = snap_locations(graph, read_locations(LOCATIONS_PATH))
    stops = [
        location_by_role(locations, "start"),
        location_by_role(locations, "shopping"),
        location_by_role(locations, "landmark"),
        location_by_role(locations, "destination"),
    ]

    with CythonDijkstra(real_binary_graph()) as cython:
        solvers = {
            "python": PythonDijkstra(graph.adjacency),
            "cython": cython,
        }

        mandatory_totals: dict[str, float] = {}
        for implementation, solver in solvers.items():
            total = 0.0
            for source, target in pairwise(stops):
                result = solver.shortest_path(source.node_index, target.node_index)
                assert result.reachable
                assert (
                    abs(path_distance(graph.adjacency, result.path) - result.distance)
                    <= TOLERANCE_M
                )
                total += result.distance
            mandatory_totals[implementation] = total

        expected_mandatory_total = 18015.14177738222
        for total in mandatory_totals.values():
            assert abs(total - expected_mandatory_total) <= TOLERANCE_M

        unconstrained: dict[str, float] = {}
        for implementation, solver in solvers.items():
            result = solver.shortest_path(stops[0].node_index, stops[-1].node_index)
            assert result.reachable
            assert (
                abs(path_distance(graph.adjacency, result.path) - result.distance)
                <= TOLERANCE_M
            )
            unconstrained[implementation] = result.distance

        expected_unconstrained = 14835.391087727205
        for distance in unconstrained.values():
            assert abs(distance - expected_unconstrained) <= TOLERANCE_M


def test_random_points_route_on_real_graph() -> None:
    graph = real_graph()
    points = generate_random_points(
        graph,
        3,
        seed=42,
        max_snap_distance_m=2000.0,
    )
    assert len(points) == 3
    assert all(point.node_index in graph.intersection_indices for point in points)

    with CythonDijkstra(real_binary_graph()) as cython:
        python_solver = PythonDijkstra(graph.adjacency)
        python_route = route_waypoints(
            python_solver,
            graph,
            [points[0].node_index, points[-1].node_index],
        )
        cython_route = route_waypoints(
            cython,
            graph,
            [points[0].node_index, points[-1].node_index],
        )

    assert abs(python_route.distance_m - cython_route.distance_m) <= TOLERANCE_M
    assert python_route.path == cython_route.path
