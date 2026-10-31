from __future__ import annotations

import random
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass

from python_dijkstra import PathResult


@dataclass(frozen=True)
class Timing:
    result: PathResult
    times_ms: list[float]

    @property
    def median_ms(self) -> float:
        return statistics.median(self.times_ms)

    @property
    def min_ms(self) -> float:
        return min(self.times_ms)


def measure_call(
    function: Callable[[], PathResult],
    repetitions: int = 10,
    warmups: int = 3,
) -> Timing:
    for _ in range(warmups):
        function()
    times: list[float] = []
    result = PathResult(0.0, [], None, None, False)
    for _ in range(repetitions):
        started = time.perf_counter_ns()
        result = function()
        finished = time.perf_counter_ns()
        times.append((finished - started) / 1_000_000.0)
    return Timing(result, times)


def synthetic_adjacency(
    node_count: int,
    average_degree: int = 6,
    seed: int = 42,
) -> dict[int, list[tuple[int, float]]]:
    rng = random.Random(seed)
    edges: dict[int, dict[int, float]] = {node: {} for node in range(node_count)}

    def add_edge(source: int, target: int) -> None:
        edges[source][target] = rng.uniform(1.0, 100.0)

    for node in range(node_count):
        target = (node + 1) % node_count
        add_edge(node, target)
        add_edge(target, node)

    target_edges = node_count * average_degree
    edge_count = sum(len(targets) for targets in edges.values())
    while edge_count < target_edges:
        source = rng.randrange(node_count)
        target = rng.randrange(node_count)
        if source == target or target in edges[source]:
            continue
        add_edge(source, target)
        edge_count += 1

    return {
        node: [(target, weight) for target, weight in targets.items()]
        for node, targets in edges.items()
    }
