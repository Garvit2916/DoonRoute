import math

import pytest

from python_dijkstra import NegativeWeightError, dijkstra


def test_basic_shortest_path() -> None:
    adjacency = {
        0: [(1, 1.0), (2, 4.0)],
        1: [(2, 2.0), (3, 5.0)],
        2: [(3, 1.0)],
        3: [],
    }

    result = dijkstra(adjacency, 0, 3)

    assert result.reachable
    assert result.distance == pytest.approx(4.0)
    assert result.path == [0, 1, 2, 3]


def test_alternative_shortest_path() -> None:
    adjacency = {
        0: [(1, 2.0), (2, 10.0)],
        1: [(2, 2.0)],
        2: [],
    }

    result = dijkstra(adjacency, 0, 2)

    assert result.distance == pytest.approx(4.0)
    assert result.path == [0, 1, 2]


def test_unreachable_destination() -> None:
    adjacency = {0: [(1, 1.0)], 1: [], 2: []}

    result = dijkstra(adjacency, 0, 2)

    assert not result.reachable
    assert math.isinf(result.distance)
    assert result.path == []


def test_source_equals_destination() -> None:
    adjacency = {0: [(1, 1.0)], 1: []}

    result = dijkstra(adjacency, 0, 0)

    assert result.reachable
    assert result.distance == 0.0
    assert result.path == [0]


def test_zero_weight_edge() -> None:
    adjacency = {0: [(1, 0.0)], 1: [(2, 2.0)], 2: []}

    result = dijkstra(adjacency, 0, 2)

    assert result.distance == pytest.approx(2.0)
    assert result.path == [0, 1, 2]


def test_negative_weight_rejected() -> None:
    adjacency = {0: [(1, -1.0)], 1: []}

    with pytest.raises(NegativeWeightError):
        dijkstra(adjacency, 0, 1)


def test_non_finite_weight_rejected() -> None:
    adjacency = {0: [(1, math.inf)], 1: []}

    with pytest.raises(ValueError):
        dijkstra(adjacency, 0, 1)


def test_path_reconstruction_is_valid() -> None:
    adjacency = {
        0: [(1, 1.5), (2, 9.0)],
        1: [(2, 2.5)],
        2: [(3, 3.0)],
        3: [],
    }

    result = dijkstra(adjacency, 0, 3)

    assert result.path[0] == 0
    assert result.path[-1] == 3
    edge_weights = {
        (source, target): weight
        for source, edges in adjacency.items()
        for target, weight in edges
    }
    reconstructed = sum(
        edge_weights[(result.path[index], result.path[index + 1])]
        for index in range(len(result.path) - 1)
    )
    assert reconstructed == pytest.approx(result.distance)


def test_directed_edge_handling() -> None:
    adjacency = {0: [(1, 1.0)], 1: []}

    forward = dijkstra(adjacency, 0, 1)
    reverse = dijkstra(adjacency, 1, 0)

    assert forward.reachable
    assert forward.distance == pytest.approx(1.0)
    assert not reverse.reachable
