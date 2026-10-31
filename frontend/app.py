from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cython_dijkstra import CythonDijkstra

from graph_loader import GraphData, load_graph
from json_export import build_route_document
from python_dijkstra import PythonDijkstra
from random_points import RandomPoint, generate_random_points
from routing import CombinedRoute, route_waypoints, write_binary_graph

GRAPH_PATH = ROOT / "data" / "raw" / "dehradun_drive.graphml"
BINARY_GRAPH = ROOT / "data" / "processed" / "graph.bin"
RESULTS = ROOT / "results"
MAJOR_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary"}


@st.cache_resource
def load_assets() -> GraphData:
    graph = load_graph(GRAPH_PATH)
    write_binary_graph(graph, BINARY_GRAPH)
    return graph


def add_network(base: folium.Map, graph: GraphData, full_network: bool) -> None:
    group = folium.FeatureGroup(name="Dehradun road network", show=full_network)
    for source, edges in graph.adjacency.items():
        source_lon, source_lat = graph.coordinates[source]
        for target, _ in edges:
            if not full_network:
                attribute = graph.edge_attributes.get((source, target), [{}])[0]
                if attribute.get("highway") not in MAJOR_ROADS:
                    continue
            target_lon, target_lat = graph.coordinates[target]
            folium.PolyLine(
                [(source_lat, source_lon), (target_lat, target_lon)],
                color="#657786",
                weight=1.2 if full_network else 2.2,
                opacity=0.25 if full_network else 0.45,
            ).add_to(group)
    group.add_to(base)


def point_label(point: RandomPoint) -> str:
    return (
        f"P{point.point_id} | {point.latitude:.5f}, {point.longitude:.5f} "
        f"| node {point.osm_node}"
    )


def add_points(base: folium.Map, points: list[RandomPoint]) -> None:
    for point in points:
        folium.CircleMarker(
            [point.latitude, point.longitude],
            radius=3,
            color="#c0392b",
            fill=True,
            fill_opacity=0.7,
            popup=f"Random point P{point.point_id}",
        ).add_to(base)
        folium.CircleMarker(
            [point.snapped_latitude, point.snapped_longitude],
            radius=3,
            color="#2471a3",
            fill=True,
            fill_opacity=0.7,
            popup=(
                f"Snapped P{point.point_id} -> OSM {point.osm_node} "
                f"({point.snap_distance_m:.1f} m)"
            ),
        ).add_to(base)


def add_route(
    base: folium.Map,
    graph: GraphData,
    points: list[RandomPoint],
    route: CombinedRoute,
    waypoint_indices: list[int],
) -> None:
    route_coordinates = [
        (graph.coordinates[index][1], graph.coordinates[index][0])
        for index in route.path
    ]
    folium.PolyLine(
        route_coordinates,
        color="#e4572e",
        weight=5,
        opacity=0.9,
        tooltip=f"{route.distance_m / 1000:.3f} km",
    ).add_to(base)

    by_node = {point.node_index: point for point in points}
    for position, node_index in enumerate(waypoint_indices):
        point = by_node.get(node_index)
        if point is None:
            continue
        if position == 0:
            label = "Start"
        elif position == len(waypoint_indices) - 1:
            label = "Destination"
        else:
            label = f"Waypoint {position}"
        folium.Marker(
            [graph.coordinates[node_index][1], graph.coordinates[node_index][0]],
            tooltip=label,
            popup=f"{label} | OSM {graph.node_ids[node_index]}",
            icon=folium.Icon(
                color="green"
                if position == 0
                else "red"
                if position == len(waypoint_indices) - 1
                else "orange"
            ),
        ).add_to(base)


def main() -> None:
    st.set_page_config(page_title="DoonRoute", page_icon=":world_map:", layout="wide")
    st.title("DoonRoute")
    st.caption(
        "Real Dehradun road routing with random points, intersection snapping, "
        "Python vs. Cython Dijkstra, and JSON export."
    )

    graph = load_assets()

    with st.sidebar:
        st.header("Random points")
        count = st.number_input("Number of points", min_value=1, max_value=20, value=5)
        seed = st.number_input("Random seed", min_value=0, value=42)
        max_snap = st.slider(
            "Maximum snapping distance (m)",
            min_value=50,
            max_value=5000,
            value=1000,
            step=50,
        )
        if st.button("Generate random points", type="primary"):
            try:
                st.session_state["points"] = generate_random_points(
                    graph,
                    int(count),
                    seed=int(seed),
                    max_snap_distance_m=float(max_snap),
                )
                st.session_state.pop("route", None)
                st.session_state.pop("document", None)
            except ValueError as error:
                st.error(str(error))

        st.header("Map layers")
        full_network = st.checkbox("Show full road network", value=False)
        show_intersections = st.checkbox("Show intersections", value=False)

    points: list[RandomPoint] = st.session_state.get("points", [])
    if not points:
        base = folium.Map(
            location=[30.3165, 78.0322], zoom_start=12, tiles="OpenStreetMap"
        )
        add_network(base, graph, full_network)
        st.info("Generate random points to begin.")
        st_folium(base, width=None, height=620, returned_objects=[])
        return

    labels = [point_label(point) for point in points]
    with st.sidebar:
        st.header("Route selection")
        start_label = st.selectbox("Start", labels, index=0)
        destination_label = st.selectbox(
            "Destination",
            labels,
            index=min(1, len(labels) - 1),
        )
        start_index = labels.index(start_label)
        destination_index = labels.index(destination_label)
        remaining = [
            label
            for index, label in enumerate(labels)
            if index not in {start_index, destination_index}
        ]
        selected_waypoints = st.multiselect(
            "Ordered intermediate waypoints",
            remaining,
        )
        calculate = st.button("Calculate route", type="primary")

    waypoint_indices = [points[start_index].node_index]
    waypoint_indices.extend(labels.index(label) for label in selected_waypoints)
    waypoint_indices.append(points[destination_index].node_index)
    if len(set(waypoint_indices)) != len(waypoint_indices):
        st.warning("Start, destination, and waypoints must be distinct.")
        calculate = False

    if calculate:
        with st.spinner("Calculating Python and Cython routes..."):
            python_solver = PythonDijkstra(graph.adjacency)
            python_started = time.perf_counter_ns()
            python_route = route_waypoints(python_solver, graph, waypoint_indices)
            python_ms = (time.perf_counter_ns() - python_started) / 1_000_000.0

            with CythonDijkstra(BINARY_GRAPH) as cython_solver:
                cython_started = time.perf_counter_ns()
                cython_route = route_waypoints(cython_solver, graph, waypoint_indices)
                cython_ms = (time.perf_counter_ns() - cython_started) / 1_000_000.0

            waypoint_metadata = [
                {
                    "name": f"P{points[labels.index(label)].point_id}",
                    "original_latitude": points[labels.index(label)].latitude,
                    "original_longitude": points[labels.index(label)].longitude,
                    "snap_distance_m": points[labels.index(label)].snap_distance_m,
                }
                for label in [start_label, *selected_waypoints, destination_label]
            ]
            benchmark = {
                "python_interactive_ms": python_ms,
                "cython_interactive_ms": cython_ms,
                "speedup": python_ms / cython_ms if cython_ms else None,
                "distance_agreement_m": abs(
                    python_route.distance_m - cython_route.distance_m
                ),
                "note": "Single interactive run; use scripts/run_benchmarks.py for medians.",
            }
            document = build_route_document(
                graph=graph,
                route=cython_route,
                waypoints=waypoint_metadata,
                algorithm="Cython Dijkstra",
                execution_time_ms=cython_ms,
                dataset_path=str(GRAPH_PATH.relative_to(ROOT)),
                benchmark=benchmark,
            )
            st.session_state["route"] = (python_route, cython_route)
            st.session_state["waypoint_indices"] = waypoint_indices
            st.session_state["document"] = document
            st.session_state["timings"] = (python_ms, cython_ms)

    route_pair = st.session_state.get("route")
    base = folium.Map(location=[30.3165, 78.0322], zoom_start=12, tiles="OpenStreetMap")
    add_network(base, graph, full_network)
    add_points(base, points)
    if show_intersections:
        intersection_group = folium.FeatureGroup(name="Intersections")
        for index in graph.intersection_indices:
            longitude, latitude = graph.coordinates[index]
            folium.CircleMarker(
                [latitude, longitude],
                radius=1.5,
                color="#1f618d",
                fill=True,
                fill_opacity=0.5,
            ).add_to(intersection_group)
        intersection_group.add_to(base)

    if route_pair is not None:
        python_route, cython_route = route_pair
        stored_indices = st.session_state.get("waypoint_indices", waypoint_indices)
        add_route(base, graph, points, cython_route, stored_indices)

    map_column, data_column = st.columns([2.2, 1.0])
    with map_column:
        st_folium(base, width=None, height=650, returned_objects=[])
    with data_column:
        st.subheader("Route")
        if route_pair is None:
            st.write("Select points and calculate a route.")
        else:
            python_route, cython_route = route_pair
            python_ms, cython_ms = st.session_state["timings"]
            agreement = abs(python_route.distance_m - cython_route.distance_m)
            st.metric("Distance", f"{cython_route.distance_m / 1000:.3f} km")
            st.metric(
                "Cython speedup",
                f"{python_ms / cython_ms:.2f}x" if cython_ms else "n/a",
            )
            table = [
                {
                    "Algorithm": "Python",
                    "Execution time (ms)": round(python_ms, 3),
                    "Distance (m)": round(python_route.distance_m, 3),
                    "Path nodes": len(python_route.path),
                    "Visited": sum(leg.result.visited for leg in python_route.legs),
                    "Relaxations": sum(
                        leg.result.relaxations for leg in python_route.legs
                    ),
                    "Speedup (x)": 1.0,
                },
                {
                    "Algorithm": "Cython",
                    "Execution time (ms)": round(cython_ms, 3),
                    "Distance (m)": round(cython_route.distance_m, 3),
                    "Path nodes": len(cython_route.path),
                    "Visited": sum(leg.result.visited for leg in cython_route.legs),
                    "Relaxations": sum(
                        leg.result.relaxations for leg in cython_route.legs
                    ),
                    "Speedup (x)": round(python_ms / cython_ms, 2)
                    if cython_ms
                    else None,
                },
            ]
            st.dataframe(table, hide_index=True, width="stretch")
            st.caption(f"Distance agreement: {agreement:.9f} m")
            st.download_button(
                "Download JSON",
                data=json.dumps(
                    st.session_state["document"],
                    indent=2,
                    ensure_ascii=False,
                ),
                file_name="doonroute_route.json",
                mime="application/json",
            )
            workflow_path = RESULTS / "benchmark_results.csv"
            with workflow_path.open("r", encoding="utf-8") as handle:
                workflow_rows = [
                    row
                    for row in csv.DictReader(handle)
                    if row.get("benchmark_type") == "workflow"
                ]
            workflow_table = [
                {
                    "Algorithm": "Python",
                    "Median execution time (ms)": float(row["median_ms"]),
                    "Distance (m)": float(row["distance_m"]),
                    "Speedup (x)": float(row["speedup_vs_python"]),
                    "Wrapper overhead included": row["wrapper_overhead_included"],
                }
                for row in workflow_rows
                if row["implementation"] == "python"
            ] + [
                {
                    "Algorithm": "Cython",
                    "Median execution time (ms)": float(row["median_ms"]),
                    "Distance (m)": float(row["distance_m"]),
                    "Speedup (x)": float(row["speedup_vs_python"]),
                    "Wrapper overhead included": row["wrapper_overhead_included"],
                }
                for row in workflow_rows
                if row["implementation"] == "cython"
            ]
            st.subheader("Workflow timing (separate from algorithm-only)")
            st.dataframe(workflow_table, hide_index=True, width="stretch")

    st.divider()
    st.subheader("Published benchmark plots")
    plot_names = [
        "execution_time.png",
        "overall_performance.png",
        "speedup.png",
        "synthetic_scaling.png",
        "route_comparison.png",
    ]
    available = [name for name in plot_names if (RESULTS / name).exists()]
    if available:
        columns = st.columns(2)
        for index, name in enumerate(available):
            with columns[index % 2]:
                st.image(str(RESULTS / name), caption=name, width="stretch")
    else:
        st.info("Run scripts/run_benchmarks.py and scripts/run_analysis.py first.")


if __name__ == "__main__":
    main()
