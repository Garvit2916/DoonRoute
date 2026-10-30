# Algorithm

DoonRoute uses the shortest-path objective of minimum road distance on a real, directed OpenStreetMap-derived graph.

## Objective

Compute the minimum-distance route that visits the mandatory stops in order.

1. Zenith Youth Hostel, Bidholi
2. Paltan Bazaar
3. Ghanta Ghar
4. Centrio Mall

The final activity at Centrio Mall is not modelled as a road leg.

## Graph representation

The graph is loaded as a directed OSMnx MultiDiGraph. Edges use OSM-derived length values in metres, including one-way restrictions.

The routing layer converts the graph into:

- a canonical indexed adjacency list for Python and C++
- a NetworkX MultiDiGraph for the independent reference implementation

Parallel edges are retained during loading and handled by selecting the shortest edge for path-distance reconstruction.

## Dijkstra implementations

### 1. Pure Python (CPython)
The pure Python implementation (`src/python_dijkstra.py`) uses a binary heap (`heapq`), stale-entry handling, settled-node tracking, visited and relaxation counters, predecessor-based path reconstruction, negative-weight validation, unreachable-target handling, and source-equals-destination handling.

### 2. Native C++17 (via Cython)
The native C++ implementation (`cpp/dijkstra.cpp`, `src/cython_dijkstra.pyx`) uses `std::priority_queue` over a flat indexed adjacency representation, compiling to a native extension for sub-millisecond execution.

### 3. Optional Independent Correctness Reference (NetworkX)
NetworkX (`networkx.single_source_dijkstra`) is retained solely as an independent reference solver to verify path correctness, distances, and topology in automated tests. It is not a competing implementation in the primary performance benchmarks.

## Mandatory-route composition

The project evaluates:

1. A to B
2. B to C
3. C to D

Then it sums the three mandatory legs for the mandatory route. It also evaluates the unconstrained A to D route for comparison.

The mandatory route is not necessarily the globally shortest A to D route; it is constrained by mandatory stops.

## Complexity

For V nodes and E directed edges, the heap-based Dijkstra implementations use:

- time complexity: O((V + E) log V)
- space complexity: O(V + E)

The route is selected by shortest distance, not shortest travel time.

## Validation

The real road legs are validated across Python, C++, and NetworkX. Observed discrepancies are compared with a 1e-6 m tolerance.
