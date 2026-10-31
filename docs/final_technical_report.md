# DoonRoute — Final Technical Report

## 1. Abstract

This final technical report documents DoonRoute’s verified Python-versus-Cython
performance comparison. The central objective is strictly a performance
comparison between normal Python implemented with Python and an independent,
compiled Cython implementation.

Python is treated as the baseline normal Python implementation, while Cython
is treated as the independently implemented optimized implementation. The final
comparison uses exactly these two primary benchmark implementations. C++ and
NetworkX are excluded from the performance comparison.

The latest verified mandatory-route results were:

- Normal Python Dijkstra: **14.104200 ms**
- Cython Dijkstra: **1.339250 ms**
- Algorithm-only Cython speedup: **8.20×**

The complete workflow results were:

- Normal Python workflow: **18.670850 ms**
- Cython workflow: **11.104700 ms**
- Workflow speedup: **1.68×**

## 2. Problem Statement

DoonRoute addresses shortest-distance routing over a real road network in the
Dehradun region while preserving mandatory waypoint order. The technical problem
requires correctness across graph edges, snapping, path reconstruction, distance
calculation, JSON export, and reproducible performance measurement.

## 3. Project Objectives

The project objectives were to:

1. Route over the real Dehradun road network.
2. Support random geographical points and ordered mandatory waypoints.
3. Identify valid road intersections and snap points to them.
4. Implement normal Python Dijkstra.
5. Implement an independent Cython Dijkstra.
6. Compare only normal Python against Cython.
7. Verify route correctness and performance.
8. Export and present verified results professionally.

## 4. OpenStreetMap Road-Network Dataset

The final dataset contained:

- **28,248** graph nodes.
- **64,912** directed road edges.
- **17,804** valid intersections.
- Real Dehradun road-network source data.

## 5. Graph Representation

The Python implementation used a dictionary-of-lists adjacency mapping. The
Cython implementation used the same real-network comparison data through a
binary CSR-style graph representation.

Both implementations received the same source-target pairs, edge weights in
metres, and path-reconstruction logic for the benchmark comparison.

## 6. Random Geographical Point Generation

Random points were generated inside graph bounds with seeded randomness and
snapped to valid intersections using a KD-tree.

The audited sample used eight points and verified:

- All points were within bounds.
- All points snapped to valid intersections.
- All snapped coordinates matched graph intersections.
- Projected-plane distance versus haversine distance differed by at most
  **0.242780455 m**.
- Brute-force nearest checks found no mismatches.
- Excessive-distance handling raised a clear error when needed.

## 7. Road-Intersection Identification

Intersections were identified using undirected degree at least three or a
non-false OSM `junction` tag.

The final verified intersection count was **17,804**.

## 8. Intersection Snapping Methodology

Snapping used a projected local metre plane and KD-tree lookup.

The audited eight-point sample verified:

- Snapping distances ranged from approximately **14.9 m** to **85.3 m**.
- D and E snapped to the same node because they are in the same Centrio complex.
- Maximum audited deviation from haversine distance was **0.242780455 m**.

## 9. Normal Python Dijkstra Implementation

The normal Python implementation used a heap-based Dijkstra search with lazy
deletion, visited tracking, relaxation tracking, and deterministic path
reconstruction.

It rejected negative weights.

## 10. Cython Dijkstra Implementation

The Cython implementation was independent of the Python implementation. It used
typed C arrays, a C binary min-heap, and a `nogil` core loop, then reconstructed
the path through Python after the native search completed.

## 11. Python Versus Cython Architecture

The final architecture compared:

1. Normal Python Dijkstra.
2. Independent Cython Dijkstra.

Both used the same graph data, source and destination pairs, weights, and result
shape.

The performance comparison did not include C++ or NetworkX.

## 12. Benchmark Methodology

The benchmark used:

- Same real-network source and target pairs.
- Same binary graph for Cython.
- Same adjacency data for Python.
- Same edge weights and path reconstruction.
- Three warmup runs.
- Ten measured repetitions.
- Median execution time.
- Speedup calculated as Python median divided by Cython median.

Algorithm-only timing excluded graph loading and snapping. Complete workflow
timing included snapping, route composition, JSON document construction, and
serialization.

## 13. Algorithm-Only Benchmark Results

| Case | Normal Python Median | Cython Median | Speedup |
|---|---:|---:|---:|
| A -> B | 5.166150 ms | 0.595600 ms | 8.67× |
| B -> C | 0.105750 ms | 0.016000 ms | 6.61× |
| C -> D | 1.769000 ms | 0.247150 ms | 7.16× |
| Overall mandatory route | 7.040900 ms | 0.858750 ms | 8.20× |

## 14. Complete Workflow Benchmark Results

| Case | Normal Python Median | Cython Median | Speedup |
|---|---:|---:|---:|
| Mandatory route, including Python-side workflow | 18.670850 ms | 11.104700 ms | 1.68× |

## 15. Route Distance Verification

Final verified route distances:

| Leg | Distance |
|---|---:|
| A -> B | 14,354.483339 m |
| B -> C | 761.562784 m |
| C -> D | 2,899.095655 m |
| Mandatory total | 18,015.141778 m |
| Unconstrained A -> D | 14,835.391088 m |
| Mandatory detour | 3,179.750690 m |

Normal Python and Cython agreed within `1e-6 m`.

## 16. JSON Route Export

The final JSON export contained:

- Dataset path, node count, edge count, and road-distance units.
- Algorithm and execution time.
- Source, destination, and ordered waypoints.
- Original coordinates and snap distances.
- Per-leg distance, path nodes, and coordinates.
- Combined path, distance, and waypoint indices.

The final sample had three legs and 176 combined path nodes. Edge-distance
validation found no failures.

## 17. Streamlit and Folium Frontend

The Streamlit and Folium frontend was verified with live Playwright testing. It
displayed the Python-versus-Cython route comparison and separate workflow timing
after the final presentation update.

The final frontend comparison includes execution time, shortest distance,
visited-node count, relaxation count, and speedup.

## 18. Testing and Validation

Final validation completed:

- **32 tests passed**.
- Ruff lint passed.
- Ruff formatting passed.
- `pip check` passed.
- Cython build succeeded.
- Benchmark plots regenerated.
- Frontend compilation passed.
- JSON reload and route assertions passed.
- Secrets scan remained clean.

## 19. Limitations

- Results were measured on the local development machine and are machine-specific.
- Workflow speedup is not directly comparable with algorithm-only speedup.
- Frontend timings are single interactive runs; medians come from the benchmark
  harness.
- The final comparison intentionally excludes C++ and NetworkX.

## 20. Conclusion and Future Scope

The final DoonRoute technical state is a reproducible Python-versus-Cython
routing project. The verified final overall algorithm-only result is:

- Normal Python: **7.040900 ms**
- Cython: **0.858750 ms**
- Speedup: **8.20×**

The complete workflow result is:

- Normal Python: **18.670850 ms**
- Cython: **11.104700 ms**
- Speedup: **1.68×**

The final technical report documents the verified Python-versus-Cython design,
benchmarks, route validation, JSON export, and frontend presentation while
excluding C++ and NetworkX from the performance comparison.
