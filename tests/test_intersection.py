from helpers import make_small_graph

from intersection import SpatialIndex, find_intersections


def test_find_intersections_uses_connectivity() -> None:
    graph = make_small_graph()
    assert find_intersections(graph) == [0, 1, 2, 3]


def test_spatial_index_returns_nearest_intersection() -> None:
    graph = make_small_graph()
    index = SpatialIndex(graph)
    snap = index.nearest(30.30001, 78.00001)

    assert snap is not None
    assert snap.node_index == 0
    assert snap.osm_node == 10
    assert snap.distance_m < 5.0


def test_spatial_index_respects_maximum_distance() -> None:
    graph = make_small_graph()
    index = SpatialIndex(graph)

    assert index.nearest(30.5, 78.5, max_distance_m=100.0) is None
