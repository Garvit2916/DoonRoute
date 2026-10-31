# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""Independent Cython Dijkstra implementation.

The graph is loaded once from DoonRoute's ``DRG1`` binary format into
contiguous C arrays.  The shortest-path search uses a C binary min-heap and
runs without the GIL; path reconstruction happens after the search.
"""

import time

from libc.math cimport INFINITY, isfinite
from libc.stdint cimport uint64_t
from libc.stdio cimport FILE, fclose, fopen, fread
from libc.stdlib cimport free, malloc

from python_dijkstra import PathResult


cdef uint64_t EMPTY = <uint64_t>-1


cdef class CythonDijkstra:
    cdef uint64_t _node_count
    cdef uint64_t _edge_count
    cdef uint64_t* _offsets
    cdef uint64_t* _targets
    cdef double* _weights
    cdef double* _distance
    cdef uint64_t* _predecessor
    cdef uint64_t* _settled
    cdef double* _heap_distance
    cdef uint64_t* _heap_node
    cdef uint64_t _heap_size
    cdef bint _loaded

    def __cinit__(self) -> None:
        self._node_count = 0
        self._edge_count = 0
        self._offsets = NULL
        self._targets = NULL
        self._weights = NULL
        self._distance = NULL
        self._predecessor = NULL
        self._settled = NULL
        self._heap_distance = NULL
        self._heap_node = NULL
        self._heap_size = 0
        self._loaded = False

    def __init__(self, graph_path: object, node_count: object = None) -> None:
        self._load(str(graph_path), node_count)

    def __dealloc__(self) -> None:
        self._free_buffers()

    @property
    def node_count(self) -> int:
        return int(self._node_count)

    @property
    def edge_count(self) -> int:
        return int(self._edge_count)

    def __enter__(self):
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._free_buffers()

    cdef void _free_buffers(self) noexcept:
        if self._offsets != NULL:
            free(self._offsets)
            self._offsets = NULL
        if self._targets != NULL:
            free(self._targets)
            self._targets = NULL
        if self._weights != NULL:
            free(self._weights)
            self._weights = NULL
        if self._distance != NULL:
            free(self._distance)
            self._distance = NULL
        if self._predecessor != NULL:
            free(self._predecessor)
            self._predecessor = NULL
        if self._settled != NULL:
            free(self._settled)
            self._settled = NULL
        if self._heap_distance != NULL:
            free(self._heap_distance)
            self._heap_distance = NULL
        if self._heap_node != NULL:
            free(self._heap_node)
            self._heap_node = NULL
        self._loaded = False
        self._node_count = 0
        self._edge_count = 0
        self._heap_size = 0

    cdef int _load(self, str graph_path, object expected_node_count) except -1:
        cdef bytes encoded_path = graph_path.encode("utf-8")
        cdef const char* path = encoded_path
        cdef FILE* handle = NULL
        cdef char magic[4]
        cdef uint64_t node_count = 0
        cdef uint64_t edge_count = 0
        cdef uint64_t source = 0
        cdef uint64_t target = 0
        cdef double weight = 0.0
        cdef uint64_t index
        cdef uint64_t node
        cdef uint64_t position
        cdef uint64_t* sources = NULL
        cdef uint64_t* temp_targets = NULL
        cdef double* temp_weights = NULL
        cdef uint64_t* cursor = NULL

        handle = fopen(path, "rb")
        if handle == NULL:
            raise FileNotFoundError(f"Cannot open graph file: {graph_path}")

        try:
            if fread(magic, 1, 4, handle) != 4:
                raise ValueError("Graph file is truncated before its magic header.")
            if magic[0] != 68 or magic[1] != 82 or magic[2] != 71 or magic[3] != 49:
                raise ValueError("Invalid graph magic; expected DRG1.")
            if fread(&node_count, sizeof(uint64_t), 1, handle) != 1:
                raise ValueError("Graph file is missing node metadata.")
            if fread(&edge_count, sizeof(uint64_t), 1, handle) != 1:
                raise ValueError("Graph file is missing edge metadata.")
            if node_count == 0:
                raise ValueError("Graph must contain at least one node.")
            if expected_node_count is not None and int(expected_node_count) != node_count:
                raise ValueError("Graph node count does not match node_count argument.")

            sources = <uint64_t*>malloc(edge_count * sizeof(uint64_t))
            temp_targets = <uint64_t*>malloc(edge_count * sizeof(uint64_t))
            temp_weights = <double*>malloc(edge_count * sizeof(double))
            if (edge_count > 0) and (
                sources == NULL or temp_targets == NULL or temp_weights == NULL
            ):
                raise MemoryError("Could not allocate temporary edge arrays.")

            for index in range(edge_count):
                if fread(&source, sizeof(uint64_t), 1, handle) != 1:
                    raise ValueError("Graph file is truncated while reading sources.")
                if fread(&target, sizeof(uint64_t), 1, handle) != 1:
                    raise ValueError("Graph file is truncated while reading targets.")
                if fread(&weight, sizeof(double), 1, handle) != 1:
                    raise ValueError("Graph file is truncated while reading weights.")
                if source >= node_count or target >= node_count:
                    raise ValueError("Graph contains an out-of-range node index.")
                if not isfinite(weight) or weight < 0.0:
                    raise ValueError("Graph contains an invalid edge weight.")
                sources[index] = source
                temp_targets[index] = target
                temp_weights[index] = weight

            self._offsets = <uint64_t*>malloc((node_count + 1) * sizeof(uint64_t))
            self._targets = <uint64_t*>malloc(edge_count * sizeof(uint64_t))
            self._weights = <double*>malloc(edge_count * sizeof(double))
            if self._offsets == NULL or (
                edge_count > 0 and (self._targets == NULL or self._weights == NULL)
            ):
                raise MemoryError("Could not allocate graph arrays.")

            for index in range(node_count + 1):
                self._offsets[index] = 0
            for index in range(edge_count):
                self._offsets[sources[index] + 1] += 1
            for index in range(node_count):
                self._offsets[index + 1] += self._offsets[index]

            cursor = <uint64_t*>malloc(node_count * sizeof(uint64_t))
            if cursor == NULL:
                raise MemoryError("Could not allocate the CSR cursor array.")
            for index in range(node_count):
                cursor[index] = self._offsets[index]
            for index in range(edge_count):
                source = sources[index]
                position = cursor[source]
                self._targets[position] = temp_targets[index]
                self._weights[position] = temp_weights[index]
                cursor[source] = position + 1

            self._distance = <double*>malloc(node_count * sizeof(double))
            self._predecessor = <uint64_t*>malloc(node_count * sizeof(uint64_t))
            self._settled = <uint64_t*>malloc(node_count * sizeof(uint64_t))
            self._heap_distance = <double*>malloc(
                (node_count + edge_count + 1) * sizeof(double)
            )
            self._heap_node = <uint64_t*>malloc(
                (node_count + edge_count + 1) * sizeof(uint64_t)
            )
            if (
                self._distance == NULL
                or self._predecessor == NULL
                or self._settled == NULL
                or self._heap_distance == NULL
                or self._heap_node == NULL
            ):
                raise MemoryError("Could not allocate Dijkstra workspace.")
        finally:
            if handle != NULL:
                fclose(handle)
            if sources != NULL:
                free(sources)
            if temp_targets != NULL:
                free(temp_targets)
            if temp_weights != NULL:
                free(temp_weights)
            if cursor != NULL:
                free(cursor)

        self._node_count = node_count
        self._edge_count = edge_count
        self._loaded = True
        return 0

    cdef inline bint _less(
        self,
        double left_distance,
        uint64_t left_node,
        double right_distance,
        uint64_t right_node,
    ) noexcept nogil:
        return left_distance < right_distance or (
            left_distance == right_distance and left_node < right_node
        )

    cdef void _heap_push(self, double distance, uint64_t node) noexcept nogil:
        cdef uint64_t index = self._heap_size
        cdef uint64_t parent
        self._heap_size += 1
        while index > 0:
            parent = (index - 1) // 2
            if not self._less(
                distance,
                node,
                self._heap_distance[parent],
                self._heap_node[parent],
            ):
                break
            self._heap_distance[index] = self._heap_distance[parent]
            self._heap_node[index] = self._heap_node[parent]
            index = parent
        self._heap_distance[index] = distance
        self._heap_node[index] = node

    cdef double _heap_pop(self, uint64_t* node_out) noexcept nogil:
        cdef double top_distance = self._heap_distance[0]
        cdef uint64_t top_node = self._heap_node[0]
        cdef uint64_t index = 0
        cdef uint64_t left
        cdef uint64_t right
        cdef uint64_t smallest
        cdef double swap_distance
        cdef uint64_t swap_node

        self._heap_size -= 1
        if self._heap_size > 0:
            self._heap_distance[0] = self._heap_distance[self._heap_size]
            self._heap_node[0] = self._heap_node[self._heap_size]
            while True:
                left = 2 * index + 1
                right = left + 1
                smallest = index
                if left < self._heap_size and self._less(
                    self._heap_distance[left],
                    self._heap_node[left],
                    self._heap_distance[smallest],
                    self._heap_node[smallest],
                ):
                    smallest = left
                if right < self._heap_size and self._less(
                    self._heap_distance[right],
                    self._heap_node[right],
                    self._heap_distance[smallest],
                    self._heap_node[smallest],
                ):
                    smallest = right
                if smallest == index:
                    break
                swap_distance = self._heap_distance[index]
                swap_node = self._heap_node[index]
                self._heap_distance[index] = self._heap_distance[smallest]
                self._heap_node[index] = self._heap_node[smallest]
                self._heap_distance[smallest] = swap_distance
                self._heap_node[smallest] = swap_node
                index = smallest

        node_out[0] = top_node
        return top_distance

    cdef bint _search(
        self,
        uint64_t source,
        uint64_t target,
        uint64_t* visited_out,
        uint64_t* relaxations_out,
    ) noexcept nogil:
        cdef uint64_t index
        cdef uint64_t node
        cdef uint64_t neighbour
        cdef uint64_t edge_index
        cdef uint64_t start
        cdef uint64_t end
        cdef double distance
        cdef double candidate
        cdef double weight
        cdef uint64_t visited = 0
        cdef uint64_t relaxations = 0
        cdef bint found = False

        for index in range(self._node_count):
            self._distance[index] = INFINITY
            self._predecessor[index] = EMPTY
            self._settled[index] = 0

        self._heap_size = 0
        self._distance[source] = 0.0
        self._heap_push(0.0, source)

        while self._heap_size > 0:
            distance = self._heap_pop(&node)
            if self._settled[node]:
                continue
            self._settled[node] = 1
            visited += 1
            if node == target:
                found = True
                break

            start = self._offsets[node]
            end = self._offsets[node + 1]
            for edge_index in range(start, end):
                neighbour = self._targets[edge_index]
                weight = self._weights[edge_index]
                candidate = distance + weight
                if candidate < self._distance[neighbour]:
                    self._distance[neighbour] = candidate
                    self._predecessor[neighbour] = node
                    relaxations += 1
                    self._heap_push(candidate, neighbour)

        visited_out[0] = visited
        relaxations_out[0] = relaxations
        return found

    def shortest_path(self, source: object, target: object):
        cdef uint64_t source_index
        cdef uint64_t target_index
        cdef uint64_t visited = 0
        cdef uint64_t relaxations = 0
        cdef uint64_t current
        cdef bint found
        cdef list path = []

        if not self._loaded:
            raise RuntimeError("CythonDijkstra is closed.")
        if not isinstance(source, int) or not isinstance(target, int):
            raise TypeError("Source and target must be integers.")
        if source < 0 or target < 0:
            raise ValueError("Source and target must be non-negative.")
        if source >= self._node_count or target >= self._node_count:
            raise ValueError("Source or target is outside the graph.")
        source_index = <uint64_t>source
        target_index = <uint64_t>target

        if source_index == target_index:
            return PathResult(0.0, [int(source_index)], 0, 0, True)

        with nogil:
            found = self._search(
                source_index,
                target_index,
                &visited,
                &relaxations,
            )

        if not found:
            return PathResult(
                float("inf"),
                [],
                int(visited),
                int(relaxations),
                False,
            )

        current = target_index
        while True:
            path.append(int(current))
            if current == source_index:
                break
            current = self._predecessor[current]
            if current == EMPTY:
                return PathResult(
                    float("inf"),
                    [],
                    int(visited),
                    int(relaxations),
                    False,
                )
        path.reverse()
        return PathResult(
            self._distance[target_index],
            path,
            int(visited),
            int(relaxations),
            True,
        )

    def benchmark(
        self,
        source: object,
        target: object,
        repetitions: int = 10,
    ) -> list[float]:
        if repetitions <= 0:
            raise ValueError("Repetitions must be positive.")
        cdef list times = []
        cdef int index
        cdef long long started
        for index in range(repetitions):
            started = time.perf_counter_ns()
            self.shortest_path(source, target)
            times.append((time.perf_counter_ns() - started) / 1_000_000.0)
        return times
