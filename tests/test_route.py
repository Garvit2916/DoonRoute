from itertools import pairwise
from pathlib import Path

from cpp_dijkstra import CppDijkstra
from python_dijkstra import PythonDijkstra
from routing import (
    NetworkXDijkstra,
    load_graph,
    location_by_role,
    path_distance,
    read_locations,
    snap_locations,
)

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "raw" / "dehradun_drive.graphml"
LOCATIONS_PATH = ROOT / "data" / "locations.csv"
BINARY_GRAPH = ROOT / "data" / "processed" / "graph.bin"
TOLERANCE_M = 1e-6


def test_mandatory_waypoint_route_total() -> None:
    graph = load_graph(GRAPH_PATH)
    locations = snap_locations(graph, read_locations(LOCATIONS_PATH))
    stops = [
        location_by_role(locations, "start"),
        location_by_role(locations, "shopping"),
        location_by_role(locations, "landmark"),
        location_by_role(locations, "destination"),
    ]

    with CppDijkstra(BINARY_GRAPH, graph.node_count) as cpp:
        solvers = {
            "python": PythonDijkstra(graph.adjacency),
            "cpp": cpp,
            "networkx": NetworkXDijkstra(graph.graph),
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
