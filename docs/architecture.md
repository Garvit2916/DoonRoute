# Architecture

DoonRoute is split into a data layer, routing core, export layer, command-line
workflows, and a Streamlit frontend. The routing core has no frontend or
plotting dependency.

```text
OSM extract / GraphML
        |
        v
  graph_loader.py
        |
        +-----------------------+
        |                       |
        v                       v
  intersection.py         routing.py
        |                       |
        v                       +--> python_dijkstra.py
  random_points.py                +--> cython_dijkstra.pyx
        |                       |
        +-----------+-----------+
                    |
                    v
             json_export.py
                    |
                    v
          data/exports/*.json

  benchmark.py --> scripts/run_benchmarks.py --> results/*.csv + *.png
  layout/assets --> frontend/app.py --> Streamlit + Folium
```

## Data layer

### `src/graph_loader.py`

Loads the GraphML dataset, assigns contiguous node indices, copies coordinates,
bounds, OSM IDs, and edge attributes, and detects intersections through
`intersection.py`. It exposes `GraphData`, which is the shared graph object.

### `src/intersection.py`

Implements valid-intersection detection and the KD-tree spatial index. It is the
single source of truth for snapping behavior.

### `src/random_points.py`

Generates reproducible random points, calls the snap index, and returns
`RandomPoint` records containing both original and snapped coordinates.

### `src/routing.py`

Owns locations, binary graph serialization, location snapping, path distance
validation, road-name extraction, single-leg routing, and ordered waypoint
composition. `write_binary_graph` and `write_binary_adjacency` define the format
consumed by the Cython extension.

## Routing core

### `src/python_dijkstra.py`

Pure Python reference implementation. It is used for correctness checks,
interactive comparison, and benchmark baselines.

### `src/cython_dijkstra.pyx`

Independent Cython implementation. It reads the binary CSR graph, runs a native
C search with typed arrays and a C heap, and returns the same `PathResult` shape
as the Python implementation.

### `src/benchmark.py`

Provides the median timing helper and the seeded synthetic graph generator. The
benchmark harness uses the same graph and path reconstruction for both
implementations.

## Export layer

### `src/json_export.py`

Builds and writes route documents. It depends on graph data and routing result
types, but not on Streamlit, Folium, or plotting.

## Command-line workflows

### `scripts/build_cython.py`

Builds the extension from `setup.py`. `setup.py` compiles the Cython-generated C
source into a native extension.

### `scripts/run_analysis.py`

Loads the real graph, snaps A-E, verifies mandatory and unconstrained routes,
checks Python/Cython agreement, writes `results/route_results.csv`, and writes
the sample `data/exports/route_export.json`.

### `scripts/run_benchmarks.py`

Runs real-network, synthetic, and end-to-end workflow benchmarks. It writes
`results/benchmark_results.csv` and generates the published plots.

### `scripts/build_network.py`

Optional data-rebuild utility. It is not needed to run the application because
the verified GraphML is included in the repository.

## Frontend

### `frontend/app.py`

A thin Streamlit application:

- loads the real graph once with `st.cache_resource`
- generates and snaps random points
- lets the user choose start, destination, and ordered waypoints
- runs Python and Cython on the same waypoint sequence
- displays the combined route on a Folium map
- shows distance, interactive timing, visited counts, and relaxations
- downloads the current route as JSON
- displays benchmark plots from `results/`

The frontend does not implement routing algorithms; it calls the shared modules.

## Generated artifacts

- `data/processed/graph.bin`: binary CSR graph for the Cython extension
- `data/exports/route_export.json`: sample export
- `results/benchmark_results.csv`: latest benchmark data
- `results/route_results.csv`: latest route verification data
- `results/*.png`: generated plots
- `src/cython_dijkstra.c`: generated C intermediate
- `src/cython_dijkstra*.pyd`: compiled extension on Windows

Generated C files, extensions, caches, and binary graph files are ignored by
Git. The verified source datasets and sample JSON export are kept.
