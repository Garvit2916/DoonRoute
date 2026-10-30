from libc.stdlib cimport malloc, free
from python_dijkstra import PathResult

cdef extern from *:
    """
    #include "dijkstra.hpp"
    void* dr_load_graph(const char* path);
    void dr_free_graph(void* graph);
    int dr_shortest_path(void* graph, unsigned long long source, unsigned long long target, unsigned long long* path_buffer, unsigned long long path_capacity, void* output);
    int dr_benchmark(void* graph, unsigned long long source, unsigned long long target, unsigned long long repetitions, double* times, unsigned long long times_capacity);
    """

    void* dr_load_graph(const char* path) noexcept
    void dr_free_graph(void* graph) noexcept
    int dr_shortest_path(void* graph, unsigned long long source, unsigned long long target, unsigned long long* path_buffer, unsigned long long path_capacity, void* output) noexcept
    int dr_benchmark(void* graph, unsigned long long source, unsigned long long target, unsigned long long repetitions, double* times, unsigned long long times_capacity) noexcept

ctypedef struct DrPathResult:
    double distance
    long long reachable
    unsigned long long visited
    unsigned long long relaxations
    unsigned long long path_nodes

cdef class CythonDijkstra:
    cdef void* handle
    cdef unsigned long long node_count

    def __init__(self, graph_path, node_count: int):
        self.handle = dr_load_graph(str(graph_path).encode("utf-8"))
        if not self.handle:
            raise RuntimeError("Unable to load C++ graph from " + graph_path)
        self.node_count = node_count

    def close(self):
        if self.handle:
            dr_free_graph(self.handle)
            self.handle = <void *>0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()

    def shortest_path(self, source: int, target: int):
        cdef void* buffer_memory = malloc(sizeof(unsigned long long) * self.node_count)
        cdef unsigned long long* buffer = <unsigned long long*>buffer_memory
        cdef DrPathResult output
        if dr_shortest_path(self.handle, source, target, buffer, self.node_count, &output) != 0:
            raise RuntimeError("C++ Dijkstra failed")
        path = [buffer[i] for i in range(int(output.path_nodes))]
        result = PathResult(float(output.distance), path, int(output.visited), int(output.relaxations), bool(output.reachable))
        free(buffer_memory)
        return result

    def benchmark(self, source: int, target: int, repetitions: int = 5):
        cdef double* times = <double*>malloc(sizeof(double) * repetitions)
        if dr_benchmark(self.handle, source, target, repetitions, times, repetitions) != 0:
            raise RuntimeError("C++ benchmark failed")
        result = [times[i] for i in range(repetitions)]
        free(times)
        return result
