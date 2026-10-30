from __future__ import annotations

import heapq
import math
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

Node = Hashable
WeightedAdjacency: TypeAlias = Mapping[Node, Sequence[tuple[Node, float]]]


class NegativeWeightError(ValueError):
    pass


@dataclass(frozen=True)
class PathResult:
    distance: float
    path: list[Node]
    visited: int | None
    relaxations: int | None
    reachable: bool


def validate_adjacency(adjacency: WeightedAdjacency) -> None:
    for edges in adjacency.values():
        for _, weight in edges:
            if not math.isfinite(weight):
                raise ValueError("Edge weights must be finite.")
            if weight < 0:
                raise NegativeWeightError("Dijkstra requires non-negative weights.")


class PythonDijkstra:
    def __init__(
        self, adjacency: WeightedAdjacency, *, validate_weights: bool = True
    ) -> None:
        if validate_weights:
            validate_adjacency(adjacency)
        self.adjacency = adjacency

    def shortest_path(self, source: Node, target: Node) -> PathResult:
        return dijkstra(
            self.adjacency,
            source,
            target,
            validate_weights=False,
        )


def dijkstra(
    adjacency: WeightedAdjacency,
    source: Node,
    target: Node,
    *,
    validate_weights: bool = True,
) -> PathResult:
    if validate_weights:
        validate_adjacency(adjacency)

    if source == target:
        return PathResult(0.0, [source], 0, 0, True)

    distances: dict[Node, float] = {source: 0.0}
    predecessors: dict[Node, Node | None] = {source: None}
    settled: set[Node] = set()
    heap: list[tuple[float, Node]] = [(0.0, source)]
    visited = 0
    relaxations = 0
    found = False

    while heap:
        distance, node = heapq.heappop(heap)
        if node in settled:
            continue
        settled.add(node)
        visited += 1
        if node == target:
            found = True
            break
        for neighbor, weight in adjacency.get(node, ()):
            candidate = distance + weight
            if candidate < distances.get(neighbor, math.inf):
                distances[neighbor] = candidate
                predecessors[neighbor] = node
                relaxations += 1
                heapq.heappush(heap, (candidate, neighbor))

    if not found:
        return PathResult(math.inf, [], visited, relaxations, False)

    path: list[Node] = []
    current: Node | None = target
    while current is not None:
        path.append(current)
        if current == source:
            break
        current = predecessors.get(current)
    if not path or path[-1] != source:
        return PathResult(math.inf, [], visited, relaxations, False)

    path.reverse()
    return PathResult(distances[target], path, visited, relaxations, True)
