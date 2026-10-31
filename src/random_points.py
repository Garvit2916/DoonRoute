from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any

from graph_loader import GraphData
from intersection import SpatialIndex


@dataclass(frozen=True)
class RandomPoint:
    point_id: int
    latitude: float
    longitude: float
    node_index: int
    osm_node: int
    snapped_latitude: float
    snapped_longitude: float
    snap_distance_m: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_random_points(
    graph: GraphData,
    count: int,
    *,
    seed: int | None = None,
    max_snap_distance_m: float = 500.0,
    max_attempts_per_point: int = 1000,
) -> list[RandomPoint]:
    """Generate random points and snap each to a nearby road intersection."""
    if count < 0:
        raise ValueError("Point count must be non-negative.")
    if max_snap_distance_m <= 0:
        raise ValueError("Maximum snapping distance must be positive.")
    if count == 0:
        return []

    west, south, east, north = graph.bounds
    index = getattr(graph, "spatial_index", None)
    if index is None:
        index = SpatialIndex(graph)
        try:
            graph.spatial_index = index
        except (AttributeError, TypeError):
            pass
    rng = random.Random(seed)
    points: list[RandomPoint] = []

    for point_id in range(count):
        for _ in range(max_attempts_per_point):
            latitude = rng.uniform(south, north)
            longitude = rng.uniform(west, east)
            snapped = index.nearest(
                latitude,
                longitude,
                max_distance_m=max_snap_distance_m,
            )
            if snapped is None:
                continue
            points.append(
                RandomPoint(
                    point_id=point_id,
                    latitude=latitude,
                    longitude=longitude,
                    node_index=snapped.node_index,
                    osm_node=snapped.osm_node,
                    snapped_latitude=snapped.latitude,
                    snapped_longitude=snapped.longitude,
                    snap_distance_m=snapped.distance_m,
                )
            )
            break
        else:
            raise ValueError(
                "Could not find a road intersection within the snapping "
                f"distance for point {point_id}; increase the maximum distance."
            )
    return points
