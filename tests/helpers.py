from __future__ import annotations

import networkx as nx

from graph_loader import GraphData


def make_small_graph() -> GraphData:
    coordinates = [
        (78.0000, 30.3000),
        (78.0100, 30.3000),
        (78.0000, 30.3100),
        (78.0100, 30.3100),
    ]
    adjacency = {
        0: [(1, 100.0), (2, 100.0), (3, 200.0)],
        1: [(0, 100.0), (2, 150.0), (3, 100.0)],
        2: [(0, 100.0), (1, 150.0), (3, 100.0)],
        3: [(0, 200.0), (1, 100.0), (2, 100.0)],
    }
    names = {
        (0, 1): "Road A",
        (1, 0): "Road A",
        (0, 2): "Road B",
        (2, 0): "Road B",
        (1, 2): "Road C",
        (2, 1): "Road C",
        (1, 3): "Road D",
        (3, 1): "Road D",
        (2, 3): "Road E",
        (3, 2): "Road E",
        (0, 3): "Road F",
        (3, 0): "Road F",
    }
    graph = nx.MultiDiGraph()
    for node in range(4):
        graph.add_node(node)
    edge_attributes = {}
    for source, edges in adjacency.items():
        for target, weight in edges:
            name = names[(source, target)]
            graph.add_edge(
                source, target, length=weight, name=name, highway="residential"
            )
            edge_attributes.setdefault((source, target), []).append(
                {
                    "key": 0,
                    "length": weight,
                    "name": name,
                    "highway": "residential",
                }
            )
    return GraphData(
        node_ids=[10, 11, 12, 13],
        index_of={10: 0, 11: 1, 12: 2, 13: 3},
        adjacency=adjacency,
        graph=graph,
        coordinates=coordinates,
        edge_attributes=edge_attributes,
        intersection_indices=[0, 1, 2, 3],
        bounds=(78.0, 30.3, 78.01, 30.31),
    )
