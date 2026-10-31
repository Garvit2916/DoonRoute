import json

from helpers import make_small_graph

from json_export import build_route_document, load_route_json, write_route_json
from python_dijkstra import PythonDijkstra
from routing import route_waypoints


def test_json_export_round_trip(tmp_path) -> None:
    graph = make_small_graph()
    solver = PythonDijkstra(graph.adjacency)
    route = route_waypoints(solver, graph, [0, 1, 3])
    waypoints = [
        {
            "name": "Start",
            "original_latitude": 30.3,
            "original_longitude": 78.0,
            "snap_distance_m": 1.0,
        },
        {
            "name": "Waypoint",
            "original_latitude": 30.3,
            "original_longitude": 78.01,
            "snap_distance_m": 2.0,
        },
        {
            "name": "Destination",
            "original_latitude": 30.31,
            "original_longitude": 78.01,
            "snap_distance_m": 3.0,
        },
    ]
    document = build_route_document(
        graph=graph,
        route=route,
        waypoints=waypoints,
        algorithm="Python Dijkstra",
        execution_time_ms=12.5,
        dataset_path="data/raw/dehradun_drive.graphml",
        benchmark={"python_median_ms": 12.5},
    )
    destination = write_route_json(document, tmp_path / "route.json")
    loaded = load_route_json(destination)

    assert loaded["project"] == "DoonRoute"
    assert loaded["dataset"]["node_count"] == 4
    assert loaded["combined_route"]["distance_m"] == 200.0
    assert loaded["combined_route"]["distance_km"] == 0.2
    assert loaded["combined_route"]["path_node_ids"] == [10, 11, 13]
    assert len(loaded["combined_route"]["path_coordinates"]) == 3
    assert len(loaded["legs"]) == 2
    assert loaded["source"]["osm_node"] == 10
    assert loaded["destination"]["osm_node"] == 13
    assert loaded["algorithm"] == "Python Dijkstra"


def test_json_export_is_plain_json(tmp_path) -> None:
    graph = make_small_graph()
    solver = PythonDijkstra(graph.adjacency)
    route = route_waypoints(solver, graph, [0, 3])
    document = build_route_document(
        graph=graph,
        route=route,
        waypoints=[
            {"name": "A"},
            {"name": "B"},
        ],
        algorithm="Python Dijkstra",
        execution_time_ms=1.0,
        dataset_path="graph.graphml",
    )
    raw = json.dumps(document, allow_nan=False)
    assert "DoonRoute" in raw
