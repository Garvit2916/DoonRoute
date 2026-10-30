"""Download the OSM extract, filter the Dehradun bbox, and build the GraphML network."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import osmium
import osmnx as ox
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PBF_PATH = RAW / "uttarakhand.osm.pbf"
XML_PATH = RAW / "dehradun_drive.osm"
GRAPH_PATH = RAW / "dehradun_drive.graphml"
PBF_URL = "https://download.openstreetmap.fr/extracts/asia/india/uttarakhand.osm.pbf"

WEST, SOUTH, EAST, NORTH = 77.90, 30.26, 78.10, 30.46
DRIVABLE_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}
EXCLUDED_ACCESS = {
    "private",
    "no",
    "customers",
    "permit",
    "agricultural",
    "forestry",
    "delivery",
}


def download_pbf(force: bool = False) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    if PBF_PATH.exists() and not force:
        print(f"Using existing PBF: {PBF_PATH} ({PBF_PATH.stat().st_size:,} bytes)")
        return PBF_PATH
    print(f"Downloading {PBF_URL}")
    with requests.get(PBF_URL, stream=True, timeout=180) as response:
        response.raise_for_status()
        temporary = PBF_PATH.with_suffix(".pbf.part")
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
        temporary.replace(PBF_PATH)
    print(f"Saved {PBF_PATH} ({PBF_PATH.stat().st_size:,} bytes)")
    return PBF_PATH


def _inside_bbox(lon: float, lat: float) -> bool:
    return WEST <= lon <= EAST and SOUTH <= lat <= NORTH


def _is_drivable(tags: dict[str, Any]) -> bool:
    highway = tags.get("highway", "")
    if not isinstance(highway, str):
        return False
    highway_classes = {part.strip() for part in highway.split(";") if part.strip()}
    if not highway_classes.intersection(DRIVABLE_HIGHWAYS):
        return False
    for key in ("access", "motor_vehicle", "motorcar", "vehicle"):
        value = str(tags.get(key, "")).strip().lower()
        if value in EXCLUDED_ACCESS:
            return False
    return str(tags.get("area", "")).strip().lower() != "yes"


class WaySelector(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self.selected_ways: set[int] = set()
        self.needed_nodes: set[int] = set()

    def way(self, way: osmium.osm.Way) -> None:
        tags = {tag.k: tag.v for tag in way.tags}
        if not _is_drivable(tags):
            return
        coordinates = [
            (node.location.lon, node.location.lat)
            for node in way.nodes
            if node.location.valid()
        ]
        if not any(_inside_bbox(lon, lat) for lon, lat in coordinates):
            return
        self.selected_ways.add(way.id)
        self.needed_nodes.update(node.ref for node in way.nodes)


class FilteredWriter(osmium.SimpleHandler):
    def __init__(
        self, selected_ways: set[int], needed_nodes: set[int], destination: Path
    ) -> None:
        super().__init__()
        self.selected_ways = selected_ways
        self.needed_nodes = needed_nodes
        self.writer = osmium.SimpleWriter(str(destination))
        self.nodes_written = 0
        self.ways_written = 0

    def node(self, node: osmium.osm.Node) -> None:
        if node.id in self.needed_nodes:
            self.writer.add_node(node)
            self.nodes_written += 1

    def way(self, way: osmium.osm.Way) -> None:
        if way.id in self.selected_ways:
            self.writer.add_way(way)
            self.ways_written += 1

    def close(self) -> None:
        self.writer.close()


def filter_pbf(source: Path, destination: Path) -> tuple[int, int]:
    print("Selecting drivable ways inside the Dehradun bbox")
    selector = WaySelector()
    selector.apply_file(str(source), locations=True)
    print(
        f"Selected {len(selector.selected_ways):,} ways and {len(selector.needed_nodes):,} nodes"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = FilteredWriter(selector.selected_ways, selector.needed_nodes, destination)
    writer.apply_file(str(source))
    writer.close()
    print(
        f"Wrote {writer.nodes_written:,} nodes and {writer.ways_written:,} ways to {destination}"
    )
    return writer.nodes_written, writer.ways_written


def build_graph(xml_path: Path, graph_path: Path) -> None:
    print("Building OSMnx MultiDiGraph")
    graph = ox.graph_from_xml(str(xml_path), simplify=True, retain_all=False)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(graph, graph_path)
    print(
        f"Saved {graph_path} | {graph.number_of_nodes():,} nodes | "
        f"{graph.number_of_edges():,} directed edges"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--force-filter", action="store_true")
    parser.add_argument("--rebuild-graph", action="store_true")
    args = parser.parse_args()

    pbf = download_pbf(args.force_download)
    if args.force_filter or not XML_PATH.exists():
        filter_pbf(pbf, XML_PATH)
    else:
        print(
            f"Using existing filtered XML: {XML_PATH} ({XML_PATH.stat().st_size:,} bytes)"
        )
    if args.rebuild_graph or not GRAPH_PATH.exists():
        build_graph(XML_PATH, GRAPH_PATH)
    else:
        print(
            f"Using existing graph: {GRAPH_PATH} ({GRAPH_PATH.stat().st_size:,} bytes)"
        )


if __name__ == "__main__":
    main()
