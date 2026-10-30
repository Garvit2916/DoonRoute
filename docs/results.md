# Results

## Verified road distances

| Item | Value |
|---|---:|
| A to B | 14354.483 m |
| B to C | 761.563 m |
| C to D | 2899.096 m |
| Mandatory A to B to C to D | 18015.141 m |
| Unconstrained A to D | 14835.391 m |
| Mandatory detour | 3179.751 m |

The implementation stores distances in metres and reports road comparisons in kilometres.

The mandatory route is the shortest route satisfying all mandatory stops in order.

## Benchmark evidence

The primary benchmark compares pure Python running on CPython 3.11 with the native C++17 Dijkstra engine (linked via Cython) on the identical road graph.

| Route Leg | CPython Median | Native C++ Median | Speedup vs CPython |
| :--- | :---: | :---: | :---: |
| A → B (14.354 km) | 6.494 ms | 0.513 ms | **12.65×** |
| B → C (0.762 km) | 0.117 ms | 0.014 ms | **8.32×** |
| C → D (2.899 km) | 3.535 ms | 0.303 ms | **11.67×** |
| **Overall (Sum of Medians)** | **10.146 ms** | **0.831 ms** | **12.22×** |

*Note: The overall metric is the sum of the three route-leg medians. NetworkX is retained exclusively as an independent correctness reference.*

For each measured case, the harness records median execution time, minimum execution time, distance, visited nodes, and relaxations.

A separate synthetic scaling benchmark evaluates CPython and Native C++ on synthetic random graphs from 1,000 to 25,000 nodes.

Generated benchmark and plot files:

- results/benchmark_results.csv
- results/execution_time.png
- results/overall_performance.png
- results/speedup.png
- results/synthetic_scaling.png

## Reproducibility

Run the analysis and benchmark scripts from the project root:

```powershell
.venv/Scripts/python scripts/run_analysis.py
.venv/Scripts/python scripts/run_benchmarks.py
```

The final implementation must report actual measurements and must not fabricate timing or speedup results.
