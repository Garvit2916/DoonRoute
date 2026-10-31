from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

EARTH_RADIUS_M = 6_371_008.8


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, (list, tuple, set)):
                return "; ".join(
                    str(item).strip() for item in parsed if str(item).strip()
                )
        return text
    if isinstance(value, (list, tuple, set)):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


@dataclass
class GraphData:
    node_ids: list[int]
    index_of: dict[int, int]
    adjacency: dict[int, list[tuple[int, float]]]
    graph: nx.MultiDiGraph
    coordinates: list[tuple[float, float]]
    edge_attributes: dict[tuple[int, int], list[dict[str, Any]]]
    intersection_indices: list[int]
    bounds: tuple[float, float, float, float]
    spatial_index: Any = None

    @property
    def node_count(self) -> int:
        return len(self.node_ids)

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self.adjacency.values())

    @property
    def west_south_east_north(self) -> tuple[float, float, float, float]:
        return self.bounds


def load_graph(path: str | Path) -> GraphData:
    source = nx.read_graphml(str(path), node_type=int, force_multigraph=True)
    if not source.is_directed():
        source = source.to_directed()

    node_ids = [int(node) for node in source.nodes]
    index_of = {node: index for index, node in enumerate(node_ids)}
    coordinates = [
        (float(source.nodes[node]["x"]), float(source.nodes[node]["y"]))
        for node in node_ids
    ]
    adjacency: dict[int, list[tuple[int, float]]] = {
        index: [] for index in range(len(node_ids))
    }
    indexed = nx.MultiDiGraph()
    for node in node_ids:
        indexed.add_node(
            index_of[node],
            junction=str(source.nodes[node].get("junction", "")),
        )

    for source_node, target_node, key, data in source.edges(keys=True, data=True):
        source_index = index_of[int(source_node)]
        target_index = index_of[int(target_node)]
        if "length" not in data:
            raise ValueError(
                f"Edge {source_node} -> {target_node} has no length attribute."
            )
        length = float(data["length"])
        adjacency[source_index].append((target_index, length))
        indexed.add_edge(
            source_index,
            target_index,
            key=key,
            length=length,
            name=_text(data.get("name")),
            highway=_text(data.get("highway")),
        )

    edge_attributes: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for source_node, target_node, key, data in indexed.edges(keys=True, data=True):
        edge_attributes.setdefault((source_node, target_node), []).append(
            {
                "key": key,
                "length": float(data["length"]),
                "name": _text(data.get("name")),
                "highway": _text(data.get("highway")),
            }
        )

    longitudes = [coordinate[0] for coordinate in coordinates]
    latitudes = [coordinate[1] for coordinate in coordinates]
    bounds = (
        min(longitudes),
        min(latitudes),
        max(longitudes),
        max(latitudes),
    )

    graph = GraphData(
        node_ids=node_ids,
        index_of=index_of,
        adjacency=adjacency,
        graph=indexed,
        coordinates=coordinates,
        edge_attributes=edge_attributes,
        intersection_indices=[],
        bounds=bounds,
    )
    from intersection import SpatialIndex, find_intersections

    graph.intersection_indices = find_intersections(graph)
    if graph.intersection_indices:
        graph.spatial_index = SpatialIndex(graph)
    return graph
