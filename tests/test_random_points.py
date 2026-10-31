import pytest
from helpers import make_small_graph

from random_points import generate_random_points


def test_random_points_are_reproducible() -> None:
    graph = make_small_graph()
    first = generate_random_points(
        graph,
        5,
        seed=7,
        max_snap_distance_m=5000.0,
    )
    second = generate_random_points(
        graph,
        5,
        seed=7,
        max_snap_distance_m=5000.0,
    )

    assert first == second
    assert [point.point_id for point in first] == list(range(5))
    assert all(78.0 <= point.longitude <= 78.01 for point in first)
    assert all(30.3 <= point.latitude <= 30.31 for point in first)


def test_random_points_snap_to_valid_intersections() -> None:
    graph = make_small_graph()
    points = generate_random_points(
        graph,
        8,
        seed=11,
        max_snap_distance_m=5000.0,
    )

    for point in points:
        assert point.node_index in graph.intersection_indices
        assert point.snap_distance_m <= 5000.0
        assert point.osm_node == graph.node_ids[point.node_index]


def test_random_points_change_with_seed() -> None:
    graph = make_small_graph()
    first = generate_random_points(graph, 3, seed=1, max_snap_distance_m=5000.0)
    second = generate_random_points(graph, 3, seed=2, max_snap_distance_m=5000.0)

    assert first != second


def test_random_points_count_zero() -> None:
    graph = make_small_graph()
    assert generate_random_points(graph, 0, seed=1) == []


def test_random_points_reject_negative_count() -> None:
    graph = make_small_graph()
    with pytest.raises(ValueError):
        generate_random_points(graph, -1, seed=1)


def test_random_points_reject_impossible_snap_distance() -> None:
    graph = make_small_graph()
    with pytest.raises(ValueError):
        generate_random_points(
            graph,
            1,
            seed=1,
            max_snap_distance_m=0.01,
            max_attempts_per_point=5,
        )
