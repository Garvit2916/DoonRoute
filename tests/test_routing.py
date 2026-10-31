import pytest
from helpers import make_small_graph

from python_dijkstra import PythonDijkstra
from routing import (
    edge_distances,
    path_distance,
    road_names,
    route_waypoints,
)


def test_multiple_waypoints_combine_without_duplicate_boundaries() -> None:
    graph = make_small_graph()
    solver = PythonDijkstra(graph.adjacency)

    route = route_waypoints(solver, graph, [0, 1, 3])

    assert route.waypoint_indices == [0, 1, 3]
    assert len(route.legs) == 2
    assert route.path == [0, 1, 3]
    assert route.distance_m == pytest.approx(200.0)
    assert route.legs[0].distance_m == pytest.approx(100.0)
    assert route.legs[1].distance_m == pytest.approx(100.0)


def test_route_edges_and_road_names() -> None:
    graph = make_small_graph()
    solver = PythonDijkstra(graph.adjacency)
    route = route_waypoints(solver, graph, [0, 1, 3])

    records = edge_distances(graph, route.path)
    assert [record["distance_m"] for record in records] == [100.0, 100.0]
    assert road_names(graph, route.path) == ["Road A", "Road D"]
    assert path_distance(graph.adjacency, route.path) == pytest.approx(route.distance_m)


def test_route_requires_two_waypoints() -> None:
    graph = make_small_graph()
    solver = PythonDijkstra(graph.adjacency)

    with pytest.raises(ValueError):
        route_waypoints(solver, graph, [0])
