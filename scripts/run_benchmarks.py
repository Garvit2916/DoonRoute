from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from cython_dijkstra import CythonDijkstra

from benchmark import Timing, measure_call, networkx_from_adjacency, synthetic_adjacency
from python_dijkstra import PythonDijkstra
from routing import (
    NetworkXDijkstra,
    load_graph,
    location_by_role,
    read_locations,
    snap_locations,
    write_binary_adjacency,
    write_binary_graph,
)

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "raw" / "dehradun_drive.graphml"
LOCATIONS_PATH = ROOT / "data" / "locations.csv"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
BINARY_GRAPH = PROCESSED / "graph.bin"
REPETITIONS = 10
WARMUPS = 3
IMPLEMENTATIONS = ["python", "cpp"]
COLORS = {"python": "#4c78a8", "cpp": "#2e7d32"}
IMPL_LABELS = {"python": "CPython (heapq)", "cpp": "Native C++17 (Cython)"}
LEG_LABELS = {"A-B": "A to B", "B-C": "B to C", "C-D": "C to D"}


def row(
    benchmark_type: str,
    case: str,
    implementation: str,
    graph_nodes: int,
    graph_edges: int,
    source: int,
    target: int,
    timing: Timing,
    timing_method: str,
) -> dict[str, Any]:
    return {
        "benchmark_type": benchmark_type,
        "case": case,
        "implementation": implementation,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "source": source,
        "target": target,
        "repetitions": REPETITIONS,
        "warmups": WARMUPS,
        "median_ms": round(timing.median_ms, 6),
        "min_ms": round(timing.min_ms, 6),
        "distance_m": round(float(timing.result.distance), 6),
        "visited": timing.result.visited if timing.result.visited is not None else "",
        "relaxations": (
            timing.result.relaxations if timing.result.relaxations is not None else ""
        ),
        "speedup_vs_python": 1.0,
        "timing_method": timing_method,
        "wrapper_overhead_included": "yes"
        if timing_method == "cpp_end_to_end"
        else "no",
    }


def add_speedups(rows: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in rows:
        groups.setdefault((item["benchmark_type"], item["case"]), []).append(item)
    for group in groups.values():
        if any(item["implementation"] == "python" for item in group):
            python_row = next(
                item for item in group if item["implementation"] == "python"
            )
            python_median = float(python_row["median_ms"])
        else:
            base_case = str(group[0]["case"]).removesuffix(" (end-to-end)")
            python_row = next(
                item
                for item in rows
                if item["benchmark_type"] == group[0]["benchmark_type"]
                and item["case"] == base_case
                and item["implementation"] == "python"
            )
            python_median = float(python_row["median_ms"])

        for item in group:
            item["speedup_vs_python"] = round(
                python_median / float(item["median_ms"]), 4
            )


def measure_cpp(cpp: CythonDijkstra, source: int, target: int) -> Timing:
    for _ in range(WARMUPS):
        cpp.shortest_path(source, target)
    times = cpp.benchmark(source, target, REPETITIONS)
    result = cpp.shortest_path(source, target)
    return Timing(result, times)


def measure_cpp_end_to_end(cpp: CythonDijkstra, source: int, target: int) -> Timing:
    for _ in range(WARMUPS):
        cpp.shortest_path(source, target)
    return measure_call(
        lambda source=source, target=target: cpp.shortest_path(source, target),
        repetitions=REPETITIONS,
    )


def add_overall_rows(
    rows: list[dict[str, Any]],
    graph_nodes: int,
    graph_edges: int,
    mandatory_distance: float,
) -> None:
    for implementation in IMPLEMENTATIONS:
        cases = [
            item
            for item in rows
            if item["benchmark_type"] == "real"
            and item["implementation"] == implementation
            and item["case"] in LEG_LABELS
        ]
        cases.sort(key=lambda item: list(LEG_LABELS).index(item["case"]))
        median_total = sum(float(item["median_ms"]) for item in cases)
        rows.append(
            {
                "benchmark_type": "real",
                "case": "overall",
                "implementation": implementation,
                "graph_nodes": graph_nodes,
                "graph_edges": graph_edges,
                "source": cases[0]["source"],
                "target": cases[-1]["target"],
                "repetitions": REPETITIONS,
                "warmups": WARMUPS,
                "median_ms": round(median_total, 6),
                "min_ms": "",
                "distance_m": round(mandatory_distance, 6),
                "visited": "",
                "relaxations": "",
                "speedup_vs_python": 1.0,
                "timing_method": "sum_of_leg_medians",
                "wrapper_overhead_included": "no",
            }
        )


def plot_execution_time(rows: list[dict[str, Any]], output: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 5.0))
    positions = np.arange(len(LEG_LABELS))
    width = 0.32
    for index, implementation in enumerate(IMPLEMENTATIONS):
        values = [
            float(
                next(
                    item["median_ms"]
                    for item in rows
                    if item["benchmark_type"] == "real"
                    and item["case"] == case
                    and item["implementation"] == implementation
                )
            )
            for case in LEG_LABELS
        ]
        bars = axis.bar(
            positions + (index - 0.5) * width,
            values,
            width,
            label=IMPL_LABELS[implementation],
            color=COLORS[implementation],
        )
        for bar, value in zip(bars, values, strict=True):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value * 1.30,
                f"{value:.3f} ms",
                ha="center",
                va="bottom",
                fontsize=8.5,
                fontweight="medium",
            )
    axis.set_yscale("log")
    axis.set_xticks(positions, list(LEG_LABELS.values()))
    axis.set_ylabel("Median execution time (ms, log scale)", fontsize=10)
    axis.set_title(
        "Execution Time Comparison: CPython vs. Native C++17",
        fontsize=11,
        fontweight="bold",
    )
    real_medians = [
        float(item["median_ms"])
        for item in rows
        if item["benchmark_type"] == "real"
        and item["implementation"] in IMPLEMENTATIONS
    ]
    axis.set_ylim(bottom=min(real_medians) * 0.35, top=max(real_medians) * 4.5)
    axis.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=9)
    axis.grid(axis="y", which="both", linestyle="--", alpha=0.3)
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def plot_overall(rows: list[dict[str, Any]], output: Path) -> None:
    overall = {
        item["implementation"]: float(item["median_ms"])
        for item in rows
        if item["benchmark_type"] == "real" and item["case"] == "overall"
    }
    values = [overall[name] for name in IMPLEMENTATIONS]
    labels = [IMPL_LABELS[name] for name in IMPLEMENTATIONS]
    figure, axis = plt.subplots(figsize=(7.0, 4.8))
    bars = axis.bar(
        labels,
        values,
        color=[COLORS[name] for name in IMPLEMENTATIONS],
        width=0.48,
    )
    for bar, value in zip(bars, values, strict=True):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.30,
            f"{value:.3f} ms",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="medium",
        )
    speedup = float(
        next(
            item["speedup_vs_python"]
            for item in rows
            if item["benchmark_type"] == "real"
            and item["case"] == "overall"
            and item["implementation"] == "cpp"
        )
    )
    axis.text(
        0.5,
        0.88,
        f"Native C++ Speedup: {speedup:.2f}×",
        transform=axis.transAxes,
        ha="center",
        fontsize=10,
        fontweight="bold",
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": "#e8f5e9",
            "edgecolor": "#2e7d32",
            "alpha": 0.9,
        },
    )
    axis.set_yscale("log")
    axis.set_ylabel("Sum of leg medians (ms, log scale)", fontsize=10)
    axis.set_title(
        "Overall Mandatory Route Benchmark (Sum of Leg Medians)",
        fontsize=11,
        fontweight="bold",
    )
    axis.set_ylim(bottom=min(values) * 0.35, top=max(values) * 4.5)
    axis.grid(axis="y", which="both", linestyle="--", alpha=0.3)
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def plot_speedup(rows: list[dict[str, Any]], output: Path) -> None:
    cases = [*LEG_LABELS, "overall"]
    labels = [*LEG_LABELS.values(), "Overall"]
    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    positions = np.arange(len(cases))
    width = 0.50
    values = [
        float(
            next(
                item["speedup_vs_python"]
                for item in rows
                if item["benchmark_type"] == "real"
                and item["case"] == case
                and item["implementation"] == "cpp"
            )
        )
        for case in cases
    ]
    bars = axis.bar(
        positions,
        values,
        width,
        label="Native C++ vs. CPython",
        color="#2e7d32",
    )
    for bar, value in zip(bars, values, strict=True):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.35,
            f"{value:.2f}×",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="medium",
        )
    axis.set_xticks(positions, labels)
    axis.set_ylabel("Speedup relative to CPython (×)", fontsize=10)
    axis.set_title(
        "Native C++ Speedup vs. CPython (Ratio of Medians)",
        fontsize=11,
        fontweight="bold",
    )
    axis.set_ylim(0, max(values) * 1.18)
    axis.axhline(
        1.0,
        color="#888888",
        linestyle=":",
        linewidth=1,
        label="CPython Baseline (1.0×)",
    )
    axis.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=9)
    axis.grid(axis="y", linestyle="--", alpha=0.3)
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def plot_synthetic(rows: list[dict[str, Any]], output: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 5.0))
    synthetic = [
        item
        for item in rows
        if item["benchmark_type"] == "synthetic"
        and not item["case"].endswith("(end-to-end)")
    ]
    for implementation in IMPLEMENTATIONS:
        series = sorted(
            (item for item in synthetic if item["implementation"] == implementation),
            key=lambda item: int(item["graph_nodes"]),
        )
        axis.plot(
            [int(item["graph_nodes"]) for item in series],
            [float(item["median_ms"]) for item in series],
            marker="o",
            markersize=6,
            linewidth=2,
            label=IMPL_LABELS[implementation],
            color=COLORS[implementation],
        )
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("Synthetic graph nodes (V, log scale)", fontsize=10)
    axis.set_ylabel("Median execution time (ms, log scale)", fontsize=10)
    axis.set_title(
        "Synthetic Graph Scaling: CPython vs. Native C++17",
        fontsize=11,
        fontweight="bold",
    )
    axis.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=9)
    axis.grid(which="both", linestyle="--", alpha=0.3)
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def load_results_from_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for item in csv.DictReader(handle):
            rows.append(dict(item))
    return rows


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(
        description="Run DoonRoute benchmarks or render plots from CSV."
    )
    parser.add_argument(
        "--plot-only",
        action="store_true",
        help="Generate plots directly from existing benchmark_results.csv",
    )
    args = parser.parse_args()

    if args.plot_only:
        csv_path = RESULTS / "benchmark_results.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing {csv_path}")
        rows = load_results_from_csv(csv_path)
        plot_execution_time(rows, RESULTS / "execution_time.png")
        plot_overall(rows, RESULTS / "overall_performance.png")
        plot_speedup(rows, RESULTS / "speedup.png")
        plot_synthetic(rows, RESULTS / "synthetic_scaling.png")
        print(f"Generated benchmark plots from {csv_path}")
        return

    print(f"Loading {GRAPH_PATH}")
    graph = load_graph(GRAPH_PATH)
    write_binary_graph(graph, BINARY_GRAPH)
    locations = snap_locations(graph, read_locations(LOCATIONS_PATH))
    a = location_by_role(locations, "start")
    b = location_by_role(locations, "shopping")
    c = location_by_role(locations, "landmark")
    d = location_by_role(locations, "destination")
    legs = [("A-B", a, b), ("B-C", b, c), ("C-D", c, d)]

    rows: list[dict[str, Any]] = []
    with CythonDijkstra(BINARY_GRAPH, graph.node_count) as cpp:
        python_solver = PythonDijkstra(graph.adjacency)
        networkx_solver = NetworkXDijkstra(graph.graph)

        for label, source, target in legs:
            source_index = source.node_index
            target_index = target.node_index
            timing = measure_call(
                lambda source_index=source_index, target_index=target_index: (
                    python_solver.shortest_path(source_index, target_index)
                ),
                repetitions=REPETITIONS,
            )
            rows.append(
                row(
                    "real",
                    label,
                    "python",
                    graph.node_count,
                    graph.edge_count,
                    source_index,
                    target_index,
                    timing,
                    "python_perf_counter",
                )
            )

            timing = measure_cpp(cpp, source_index, target_index)
            rows.append(
                row(
                    "real",
                    label,
                    "cpp",
                    graph.node_count,
                    graph.edge_count,
                    source_index,
                    target_index,
                    timing,
                    "cpp_internal_steady_clock",
                )
            )
            timing = measure_cpp_end_to_end(cpp, source_index, target_index)
            rows.append(
                row(
                    "real",
                    f"{label} (end-to-end)",
                    "cpp",
                    graph.node_count,
                    graph.edge_count,
                    source_index,
                    target_index,
                    timing,
                    "cpp_end_to_end",
                )
            )

            # Independent correctness validation against NetworkX reference solver
            nx_res = networkx_solver.shortest_path(source_index, target_index)
            if abs(nx_res.distance - timing.result.distance) > 1e-6:
                raise AssertionError(f"NetworkX reference disagrees on leg {label}")

    add_overall_rows(
        rows,
        graph.node_count,
        graph.edge_count,
        sum(
            float(
                next(
                    item["distance_m"]
                    for item in rows
                    if item["benchmark_type"] == "real"
                    and item["case"] == case
                    and item["implementation"] == "python"
                )
            )
            for case in LEG_LABELS
        ),
    )

    with tempfile.TemporaryDirectory() as temporary_directory:
        for node_count in (1_000, 5_000, 10_000, 25_000):
            adjacency = synthetic_adjacency(node_count)
            binary_path = Path(temporary_directory) / f"synthetic_{node_count}.bin"
            write_binary_adjacency(adjacency, node_count, binary_path)
            networkx_graph = networkx_from_adjacency(adjacency)
            python_solver = PythonDijkstra(adjacency)
            networkx_solver = NetworkXDijkstra(networkx_graph)
            source = 0
            target = node_count - 1
            edge_count = sum(len(edges) for edges in adjacency.values())
            with CythonDijkstra(binary_path, node_count) as cpp:
                timing = measure_call(
                    lambda solver=python_solver, source=source, target=target: (
                        solver.shortest_path(source, target)
                    ),
                    repetitions=REPETITIONS,
                )
                assert (
                    abs(
                        networkx_solver.shortest_path(source, target).distance
                        - timing.result.distance
                    )
                    <= 1e-6
                )
                rows.append(
                    row(
                        "synthetic",
                        f"n={node_count}",
                        "python",
                        node_count,
                        edge_count,
                        source,
                        target,
                        timing,
                        "python_perf_counter",
                    )
                )
                timing = measure_cpp(cpp, source, target)
                rows.append(
                    row(
                        "synthetic",
                        f"n={node_count}",
                        "cpp",
                        node_count,
                        edge_count,
                        source,
                        target,
                        timing,
                        "cpp_internal_steady_clock",
                    )
                )
                timing = measure_cpp_end_to_end(cpp, source, target)
                rows.append(
                    row(
                        "synthetic",
                        f"n={node_count} (end-to-end)",
                        "cpp",
                        node_count,
                        edge_count,
                        source,
                        target,
                        timing,
                        "cpp_end_to_end",
                    )
                )

    add_speedups(rows)

    with (RESULTS / "benchmark_results.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    plot_execution_time(rows, RESULTS / "execution_time.png")
    plot_overall(rows, RESULTS / "overall_performance.png")
    plot_speedup(rows, RESULTS / "speedup.png")
    plot_synthetic(rows, RESULTS / "synthetic_scaling.png")

    print("Benchmark results")
    for item in rows:
        if item["benchmark_type"] == "real" and item["implementation"] == "cpp":
            print(
                f"  {item['case']:8} C++ median {item['median_ms']:.6f} ms "
                f"| speedup {item['speedup_vs_python']:.2f}x"
            )
    print(f"Wrote {RESULTS / 'benchmark_results.csv'}")


if __name__ == "__main__":
    main()
