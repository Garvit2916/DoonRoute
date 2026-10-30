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

The benchmark compares Python, C++, and NetworkX on the same real road legs.

For each measured case, it records median execution time, minimum execution time, distance, visited nodes where available, and relaxations where available.

For the mandatory total, the benchmark records the sum of leg medians.

A separate synthetic scaling benchmark is used when real-road timings are small.

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
