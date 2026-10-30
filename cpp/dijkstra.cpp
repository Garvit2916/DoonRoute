#include "dijkstra.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <fstream>
#include <functional>
#include <queue>
#include <stdexcept>
#include <utility>

#ifdef _WIN32
#define DOONROUTE_EXPORT __declspec(dllexport)
#else
#define DOONROUTE_EXPORT
#endif

namespace doonroute {

namespace {

template <typename T>
void read_value(std::ifstream& input, T& value) {
    input.read(reinterpret_cast<char*>(&value), sizeof(T));
    if (!input) {
        throw std::runtime_error("Unexpected end of graph file.");
    }
}

}  // namespace

Graph::Graph(const std::string& binary_path) {
    std::ifstream input(binary_path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("Unable to open graph file: " + binary_path);
    }

    std::array<char, 4> magic{};
    input.read(magic.data(), magic.size());
    if (!input || magic != std::array<char, 4>{'D', 'R', 'G', '1'}) {
        throw std::runtime_error("Invalid graph file magic.");
    }

    std::uint64_t node_count = 0;
    read_value(input, node_count);
    read_value(input, edge_count_);
    if (node_count == 0) {
        throw std::runtime_error("Graph must contain at least one node.");
    }

    adjacency_.assign(node_count, {});
    for (std::uint64_t index = 0; index < edge_count_; ++index) {
        std::uint64_t source = 0;
        std::uint64_t target = 0;
        double weight = 0.0;
        read_value(input, source);
        read_value(input, target);
        read_value(input, weight);
        if (source >= node_count || target >= node_count) {
            throw std::runtime_error("Graph edge endpoint is out of range.");
        }
        if (!std::isfinite(weight) || weight < 0.0) {
            throw std::runtime_error("Graph contains an invalid edge weight.");
        }
        adjacency_[source].push_back(Edge{target, weight});
    }
}

PathResult Graph::shortest_path(std::uint64_t source, std::uint64_t target) const {
    const std::uint64_t node_count = adjacency_.size();
    if (source >= node_count || target >= node_count) {
        throw std::out_of_range("Source or target node is out of range.");
    }

    PathResult result;
    if (source == target) {
        result.distance = 0.0;
        result.reachable = true;
        result.path = {source};
        return result;
    }

    const double infinity = std::numeric_limits<double>::infinity();
    std::vector<double> distances(node_count, infinity);
    std::vector<std::int64_t> predecessors(node_count, -1);
    std::vector<bool> settled(node_count, false);
    using QueueItem = std::pair<double, std::uint64_t>;
    std::priority_queue<QueueItem, std::vector<QueueItem>, std::greater<QueueItem>> queue;

    distances[source] = 0.0;
    queue.emplace(0.0, source);
    bool found = false;

    while (!queue.empty()) {
        const auto [distance, node] = queue.top();
        queue.pop();
        if (settled[node]) {
            continue;
        }
        settled[node] = true;
        ++result.visited;
        if (node == target) {
            found = true;
            break;
        }
        for (const Edge& edge : adjacency_[node]) {
            const double candidate = distance + edge.weight;
            if (candidate < distances[edge.target]) {
                distances[edge.target] = candidate;
                predecessors[edge.target] = static_cast<std::int64_t>(node);
                ++result.relaxations;
                queue.emplace(candidate, edge.target);
            }
        }
    }

    if (!found) {
        return result;
    }

    result.distance = distances[target];
    result.reachable = true;
    for (std::int64_t current = static_cast<std::int64_t>(target); current != -1;
         current = predecessors[static_cast<std::size_t>(current)]) {
        result.path.push_back(static_cast<std::uint64_t>(current));
    }
    std::reverse(result.path.begin(), result.path.end());
    return result;
}

}  // namespace doonroute

struct DrGraph {
    explicit DrGraph(const std::string& path) : graph(path) {}
    doonroute::Graph graph;
};

extern "C++" {

DOONROUTE_EXPORT void* dr_load_graph(const char* path) {
    try {
        if (path == nullptr) {
            return nullptr;
        }
        return static_cast<void*>(new DrGraph(path));
    } catch (...) {
        return nullptr;
    }
}

DOONROUTE_EXPORT void dr_free_graph(void* graph) {
    delete static_cast<DrGraph*>(graph);
}

DOONROUTE_EXPORT int dr_shortest_path(
    void* graph,
    std::uint64_t source,
    std::uint64_t target,
    std::uint64_t* path_buffer,
    std::uint64_t path_capacity,
    void* output
) {
    DrGraph* dr_graph = static_cast<DrGraph*>(graph);
    if (dr_graph == nullptr || output == nullptr) {
        return 1;
    }
    try {
        const doonroute::PathResult result = dr_graph->graph.shortest_path(source, target);
        DrPathResult* dr_result = static_cast<DrPathResult*>(output);
        dr_result->distance = result.distance;
        dr_result->reachable = result.reachable ? 1 : 0;
        dr_result->visited = result.visited;
        dr_result->relaxations = result.relaxations;
        dr_result->path_nodes = static_cast<std::uint64_t>(result.path.size());
        if (result.path.size() > path_capacity || (result.path.size() > 0 && path_buffer == nullptr)) {
            return 2;
        }
        for (std::size_t index = 0; index < result.path.size(); ++index) {
            path_buffer[index] = result.path[index];
        }
        return 0;
    } catch (...) {
        return 3;
    }
}

DOONROUTE_EXPORT int dr_benchmark(
    void* graph,
    std::uint64_t source,
    std::uint64_t target,
    std::uint64_t repetitions,
    double* times,
    std::uint64_t times_capacity
) {
    DrGraph* dr_graph = static_cast<DrGraph*>(graph);
    if (dr_graph == nullptr || times == nullptr || repetitions == 0 || times_capacity < repetitions) {
        return 1;
    }
    try {
        double checksum = dr_graph->graph.shortest_path(source, target).distance;
        for (std::uint64_t index = 0; index < repetitions; ++index) {
            const auto started = std::chrono::steady_clock::now();
            checksum += dr_graph->graph.shortest_path(source, target).distance;
            const auto finished = std::chrono::steady_clock::now();
            times[index] = std::chrono::duration<double, std::milli>(finished - started).count();
        }
        return std::isfinite(checksum) ? 0 : 4;
    } catch (...) {
        return 3;
    }
}
}
