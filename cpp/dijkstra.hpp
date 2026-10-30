#pragma once

#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace doonroute {

struct Edge {
    std::uint64_t target;
    double weight;
};

struct PathResult {
    double distance = std::numeric_limits<double>::infinity();
    bool reachable = false;
    std::uint64_t visited = 0;
    std::uint64_t relaxations = 0;
    std::vector<std::uint64_t> path;
};

class Graph {
public:
    explicit Graph(const std::string& binary_path);

    PathResult shortest_path(std::uint64_t source, std::uint64_t target) const;

    std::uint64_t node_count() const { return adjacency_.size(); }
    std::uint64_t edge_count() const { return edge_count_; }

private:
    std::vector<std::vector<Edge>> adjacency_;
    std::uint64_t edge_count_ = 0;
};

}  // namespace doonroute

struct DrPathResult {
    double distance;
    long long reachable;
    unsigned long long visited;
    unsigned long long relaxations;
    unsigned long long path_nodes;
};
