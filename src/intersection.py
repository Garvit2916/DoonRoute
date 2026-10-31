from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from scipy.spatial import cKDTree

from graph_loader import EARTH_RADIUS_M

if TYPE_CHECKING:
    from graph_loader import GraphData


@dataclass(frozen=True)
class Snap:
    node_index: int
    osm_node: int
    latitude: float
    longitude: float
    distance_m: float


def find_intersections(graph: GraphData) -> list[int]:
    """Return graph indices that are real road junctions.

    A node is treated as a junction when its undirected road degree is at least
    three, or when the source OSM data carries a positive ``junction`` tag.
    """
    neighbours: list[set[int]] = [set() for _ in range(graph.node_count)]
    for source, edges in graph.adjacency.items():
        for target, _ in edges:
            if target != source:
                neighbours[source].add(target)
                neighbours[target].add(source)

    indices: list[int] = []
    for index in range(graph.node_count):
        node_data = graph.graph.nodes[index]
        junction = str(node_data.get("junction", "")).strip().lower()
        if len(neighbours[index]) >= 3 or junction not in {"", "no", "false"}:
            indices.append(index)
    return indices


class SpatialIndex:
    """KD-tree over valid intersections using a local metre projection."""

    def __init__(
        self,
        graph: GraphData,
        indices: list[int] | None = None,
    ) -> None:
        self.graph = graph
        self.indices = list(graph.intersection_indices if indices is None else indices)
        if not self.indices:
            raise ValueError("The graph has no valid intersections.")

        latitudes = [graph.coordinates[index][1] for index in self.indices]
        longitudes = [graph.coordinates[index][0] for index in self.indices]
        self.latitude_origin = sum(latitudes) / len(latitudes)
        self.longitude_origin = sum(longitudes) / len(longitudes)
        self.x_scale = (
            math.radians(1.0)
            * EARTH_RADIUS_M
            * math.cos(math.radians(self.latitude_origin))
        )
        self.y_scale = math.radians(1.0) * EARTH_RADIUS_M
        self.points = [
            self._project(latitude, longitude)
            for latitude, longitude in zip(latitudes, longitudes, strict=True)
        ]
        self.tree = cKDTree(self.points)

    def _project(self, latitude: float, longitude: float) -> tuple[float, float]:
        x = (longitude - self.longitude_origin) * self.x_scale
        y = (latitude - self.latitude_origin) * self.y_scale
        return x, y

    def nearest(
        self,
        latitude: float,
        longitude: float,
        max_distance_m: float | None = None,
    ) -> Snap | None:
        x, y = self._project(latitude, longitude)
        distance, position = self.tree.query((x, y), k=1)
        distance = float(distance)
        if max_distance_m is not None and distance > max_distance_m:
            return None
        node_index = self.indices[int(position)]
        snapped_longitude, snapped_latitude = self.graph.coordinates[node_index]
        return Snap(
            node_index=node_index,
            osm_node=self.graph.node_ids[node_index],
            latitude=snapped_latitude,
            longitude=snapped_longitude,
            distance_m=distance,
        )
