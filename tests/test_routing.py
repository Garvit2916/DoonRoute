import pytest
from helpers import make_small_graph

from python_dijkstra import PythonDijkstra
from routing import (
    clear_route_cache,
    edge_distances,
    path_distance,
    road_names,
    route_leg,
    route_waypoints,
    snap_locations,
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


def test_route_segment_and_waypoint_caching() -> None:
    graph = make_small_graph()
    solver = PythonDijkstra(graph.adjacency)

    # First computation: populates leg and route cache
    route1 = route_waypoints(solver, graph, [0, 1, 3])
    assert getattr(graph, "_leg_cache", None) is not None
    assert getattr(graph, "_route_cache", None) is not None
    assert route1.algorithm_ms >= 0.0
    assert route1.workflow_ms >= 0.0
    assert sum(leg.algorithm_ms for leg in route1.legs) == pytest.approx(
        route1.algorithm_ms
    )

    # Repeated calculation: hits route cache directly
    route2 = route_waypoints(solver, graph, [0, 1, 3])
    assert route1 is route2

    # Partial overlap calculation: hits leg cache for [0, 1]
    leg_0_1 = route_leg(solver, graph, 0, 1)
    assert leg_0_1 is route1.legs[0]


def test_clear_route_cache() -> None:
    graph = make_small_graph()
    solver = PythonDijkstra(graph.adjacency)

    route1 = route_waypoints(solver, graph, [0, 1, 3])
    clear_route_cache(graph)
    assert len(graph._leg_cache) == 0
    assert len(graph._route_cache) == 0

    route2 = route_waypoints(solver, graph, [0, 1, 3])
    assert route1.distance_m == route2.distance_m
    assert route1.path == route2.path


def test_spatial_index_reuse() -> None:
    graph = make_small_graph()
    from routing import Location

    loc = [
        Location(
            id="test",
            name="Test",
            role="start",
            latitude=30.301,
            longitude=78.001,
        )
    ]
    snapped1 = snap_locations(graph, loc)
    idx1 = graph.spatial_index
    assert idx1 is not None

    snapped2 = snap_locations(graph, loc)
    assert graph.spatial_index is idx1
    assert snapped1[0].node_index == snapped2[0].node_index
