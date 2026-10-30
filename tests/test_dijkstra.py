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


from cpp_dijkstra import CppDijkstra
from routing import write_binary_adjacency


def _cpp_graph(tmp_path, adjacency):
    node_count = max(adjacency) + 1
    binary = write_binary_adjacency(adjacency, node_count, tmp_path / "graph.bin")
    return CppDijkstra(binary, node_count)


def test_cpp_agrees_with_python(tmp_path) -> None:
    adjacency = {
        0: [(1, 1.0), (2, 4.0)],
        1: [(2, 2.0), (3, 5.0)],
        2: [(3, 1.0)],
        3: [],
    }
    python_result = dijkstra(adjacency, 0, 3)
    with _cpp_graph(tmp_path, adjacency) as cpp:
        cpp_result = cpp.shortest_path(0, 3)

    assert cpp_result.reachable
    assert cpp_result.distance == pytest.approx(python_result.distance)
    assert cpp_result.path[0] == 0
    assert cpp_result.path[-1] == 3
    assert cpp_result.visited == python_result.visited
    assert cpp_result.relaxations == python_result.relaxations


def test_cpp_unreachable_and_source_equals_target(tmp_path) -> None:
    adjacency = {0: [(1, 1.0)], 1: [], 2: []}
    with _cpp_graph(tmp_path, adjacency) as cpp:
        unreachable = cpp.shortest_path(0, 2)
        same_node = cpp.shortest_path(1, 1)

    assert not unreachable.reachable
    assert math.isinf(unreachable.distance)
    assert same_node.reachable
    assert same_node.distance == 0.0
    assert same_node.path == [1]


def test_cpp_benchmark_returns_repetitions(tmp_path) -> None:
    adjacency = {0: [(1, 1.0)], 1: [(2, 2.0)], 2: []}
    with _cpp_graph(tmp_path, adjacency) as cpp:
        times = cpp.benchmark(0, 2, repetitions=5)

    assert len(times) == 5
    assert all(value >= 0 for value in times)


import networkx as nx

from routing import NetworkXDijkstra


def test_networkx_agrees_with_python() -> None:
    adjacency = {
        0: [(1, 1.0), (2, 4.0)],
        1: [(2, 2.0), (3, 5.0)],
        2: [(3, 1.0)],
        3: [],
    }
    graph = nx.MultiDiGraph()
    for source, edges in adjacency.items():
        graph.add_node(source)
        for target, weight in edges:
            graph.add_edge(source, target, length=weight)

    result = NetworkXDijkstra(graph).shortest_path(0, 3)

    assert result.reachable
    assert result.distance == pytest.approx(4.0)
    assert result.path == [0, 1, 2, 3]


def test_networkx_unreachable() -> None:
    graph = nx.MultiDiGraph()
    graph.add_edge(0, 1, length=1.0)
    graph.add_node(2)

    result = NetworkXDijkstra(graph).shortest_path(0, 2)

    assert not result.reachable
    assert math.isinf(result.distance)
