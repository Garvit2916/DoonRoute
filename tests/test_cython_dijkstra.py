import math

import pytest
from cython_dijkstra import CythonDijkstra

from python_dijkstra import dijkstra
from routing import write_binary_adjacency


def _solver(tmp_path, adjacency):
    node_count = max(adjacency) + 1
    binary = write_binary_adjacency(adjacency, node_count, tmp_path / "graph.bin")
    return CythonDijkstra(binary, node_count)


def test_cython_agrees_with_python(tmp_path) -> None:
    adjacency = {
        0: [(1, 1.0), (2, 4.0)],
        1: [(2, 2.0), (3, 5.0)],
        2: [(3, 1.0)],
        3: [],
    }
    python_result = dijkstra(adjacency, 0, 3)
    with _solver(tmp_path, adjacency) as cython:
        cython_result = cython.shortest_path(0, 3)

    assert cython_result.reachable
    assert cython_result.distance == pytest.approx(python_result.distance)
    assert cython_result.path == python_result.path
    assert cython_result.visited == python_result.visited
    assert cython_result.relaxations == python_result.relaxations


def test_cython_unreachable_and_source_equals_target(tmp_path) -> None:
    adjacency = {0: [(1, 1.0)], 1: [], 2: []}
    with _solver(tmp_path, adjacency) as cython:
        unreachable = cython.shortest_path(0, 2)
        same_node = cython.shortest_path(1, 1)

    assert not unreachable.reachable
    assert math.isinf(unreachable.distance)
    assert same_node.reachable
    assert same_node.distance == 0.0
    assert same_node.path == [1]


def test_cython_rejects_invalid_nodes(tmp_path) -> None:
    adjacency = {0: [(1, 1.0)], 1: []}
    with _solver(tmp_path, adjacency) as cython:
        with pytest.raises(ValueError):
            cython.shortest_path(0, 5)
        with pytest.raises(ValueError):
            cython.shortest_path(-1, 1)
        with pytest.raises(TypeError):
            cython.shortest_path("0", 1)


def test_cython_benchmark_returns_repetitions(tmp_path) -> None:
    adjacency = {0: [(1, 1.0)], 1: [(2, 2.0)], 2: []}
    with _solver(tmp_path, adjacency) as cython:
        times = cython.benchmark(0, 2, repetitions=5)

    assert len(times) == 5
    assert all(value >= 0 for value in times)


def test_cython_rejects_bad_node_count(tmp_path) -> None:
    adjacency = {0: [(1, 1.0)], 1: []}
    binary = write_binary_adjacency(adjacency, 2, tmp_path / "graph.bin")
    with pytest.raises(ValueError):
        CythonDijkstra(binary, 3)


def test_cython_rejects_negative_weights(tmp_path) -> None:
    adjacency = {0: [(1, -1.0)], 1: []}
    with pytest.raises(ValueError):
        write_binary_adjacency(adjacency, 2, tmp_path / "graph.bin")
