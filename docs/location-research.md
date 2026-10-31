# DoonRoute — Location Research and Data Sources

**Report date:** 2026-10-30  
**Status:** Phase 1 report. Distances were recomputed with the custom Python and Cython Dijkstra implementations.

## 1. Journey brief

DoonRoute models a shortest-distance road journey subject to four mandatory stops:

1. **A — Zenith Youth Hostel, Bidholi** (start)
2. **B — Paltan Bazaar** (shopping)
3. **C — Ghanta Ghar** (landmark)
4. **D — Centrio Mall** (destination)
5. **E — Timezone bowling, inside Centrio/Unison Mall** (activity at the destination)

The order is fixed: A → B → C → D. Timezone is inside the Centrio complex, so D → E has **no separate road journey** and contributes **0 m** to road distance.

This is **not** the globally shortest A → D route. It is the shortest route that visits B and C in the required order.

## 2. Location evidence

Coordinates are reported to six decimal places only to make them machine-readable. Their real accuracy is lower. Every coordinate is snapped to the nearest routable graph node; the access walk from the point to the road is **not** modelled.

| Stop | Place | Latitude | Longitude | Evidence | Access note |
|---|---|---:|---:|---|---|
| A | Zenith Youth Hostel, Bidholi | 30.4092544 | 77.9692954 | India HCI 2023 student-accommodation page links to `https://maps.app.goo.gl/Krw7pUkKsMoPcNhB6`; the link resolves to “your space Zenith Hostel (PG near UPES)” and the published address matches KH. No. 576, 577KA, Mauza Bidholi, near UPES. Retrieved 2026-10-30. | Snapped to node `10011044543`, 14.9 m away. |
| B | Paltan Bazaar | 30.320501 | 78.037545 | Exa place listing for “Paltan Bazar”, 101 Paltan Bazar Rd, Kotwali, Paltan Bazaar; OSM `Paltan Bazar` tertiary way `105690330` has centroid 30.319995, 78.036773, about 89 m away. Retrieved 2026-10-30. | Snapped to node `1217127863`, 22.3 m away. |
| C | Ghanta Ghar | 30.3243249 | 78.0418653 | OSM Nominatim result for “Ghanta Ghar, Rajpur Road”, OSM way `1556686564`. Retrieved 2026-10-30. | Snapped to node `6699305178`, 16.2 m away. |
| D | Centrio Mall | 30.3433787 | 78.0479563 | OSM node `12119801701` for Centrio Mall. The mall’s own site gives New Cantt Road, Dehradun 248001; Unison Group and design-team pages identify Centrio as the Unison development at Rabindra Nath Tagore Marg. Retrieved 2026-10-30. | Snapped to node `10196569536`, 69.8 m away. |
| E | Timezone bowling | 30.343296 | 78.047733 | Timezone’s official Unison Mall page gives “Unison Mall, 3rd Floor, Rabindra Nath Tagore Marg, MDDA Dehradun, Dehradun, Uttarakhand, 248001”; the Exa place listing gives these coordinates. Both Centrio’s site and Unison Group list Timezone/TIMEZONE as an entertainment tenant. Retrieved 2026-10-30. | Snapped to the same node `10196569536`, 85.3 m away. |

### 2.1 Zenith coordinate discrepancy

Two plausible Zenith coordinates were found:

- **30.4092544, 77.9692954** — Google Maps place reached from the official India HCI 2023 accommodation link; the linked place is “your space Zenith Hostel (PG near UPES)” and the address matches.
- **30.408238, 77.966582** — Exa place listing for “Zenith Youth Luxury Hostel”, Bidholi.

They are about **284 m apart**. The official conference page’s Google Maps link is the stronger provenance because it ties the exact address to the exact map pin. The Exa coordinate is retained here as a documented alternative. Because both points are in the Bidholi/UPES area, the choice does not change the strategic route, but it can change the snapped start node and the first few hundred metres.

### 2.2 Paltan Bazaar coordinate

The selected point is on the Paltan Bazar road corridor and snaps 22.3 m to the graph. OSM’s `Paltan Bazar` way centroid is about 89 m away. Paltan Bazaar is a street market, not a single building, so either point is a simplification. The selected point is treated as the shopping-area access point; no specific shop entrance is claimed.

### 2.3 Centrio and Timezone

Centrio Mall’s own site describes a TimeZone Family Entertainment Center and a bowling alley. Timezone’s official page gives the Unison Mall address. The two coordinates are about 28 m apart and snap to the same routable node. Therefore:

- Timezone is associated with the **Centrio/Unison complex**, not Ghanta Ghar.
- The bowling activity is **not** a fifth road leg.
- Any indoor walking from the mall entrance to the third floor is outside the road-network model.

## 3. Nearby places requested for context

These are relevant Dehradun locations, but only A–E are optimisation waypoints.

| Place | Role in this project | Evidence in the routing data |
|---|---|---|
| UPES Bidholi | Start-side anchor for the Bidholi/UPES area | OSM way `Nanda Ki Chowki to UPES` is present in the filtered network. |
| Sudhowala | Nearby settlement west of the start area | Approximately 30.345, 77.937, inside the extraction bbox; not a waypoint. |
| Premnagar | Settlement/corridor between the western edge and central Dehradun | Inside the extraction bbox; not a waypoint. The chosen shortest route uses the Kaulagarh/Chakrata corridor rather than Premnagar. |
| Ballupur Chowk | Candidate junction on the Ballupur alternative corridor | `Ballupur Road` is present in the network. |
| Kishan Nagar Chowk | Candidate junction for context and future variants | OSM way `Kishan Nagar Chowk` is present in the network. |
| Chakrata Road | Major corridor used by the shortest A → B route | OSM ways named `Chakrata Road` are present. |
| Rajpur Road / Rajpur–Mussoorie Road | Corridor used between Ghanta Ghar and Centrio | OSM ways named `Rajpur-Mussoorie Road` are present. |
| New Cantt Road | Centrio access corridor | OSM spells it `New Contontment Road`; this is retained as source data, with a normalized display name. |

## 4. Road-network data source

### 4.1 Primary source

- **Dataset:** OpenStreetMap France — Uttarakhand extract
- **URL:** `https://download.openstreetmap.fr/extracts/asia/india/uttarakhand.osm.pbf`
- **Local file:** `data/raw/uttarakhand.osm.pbf`
- **File size:** 33,497,938 bytes
- **Server `Last-Modified`:** Fri, 30 Oct 2026 13:15:35 GMT
- **Retrieved:** 2026-10-30
- **Licence:** OpenStreetMap data, © OpenStreetMap contributors, available under the Open Database License (ODbL) 1.0. Attribution and share-alike requirements apply.

### 4.2 Extraction and graph construction

- **Bounding box:** west 77.90, south 30.26, east 78.10, north 30.46
- **Filter:** drivable public road classes; exclude service roads, paths, footways, cycleways, steps, construction, proposed roads, and access-restricted/private ways. Two `access=no` residential ways were removed during the reproducibility rebuild.
- **Tool:** Python `osmium` 4.3.2, because `pyrosm` had no installable distribution for this environment.
- **Filtered OSM XML:** `data/raw/dehradun_drive.osm` (31,362,235 bytes; 150,388 nodes; 16,476 ways)
- **Routing graph:** `data/raw/dehradun_drive.graphml` (29,538,418 bytes)
- **Graph type:** OSMnx `MultiDiGraph`
- **Graph size:** 28,248 nodes; 64,912 directed edges
- **Connectivity:** one weak component; not strongly connected, as expected on a directed road network with one-way streets
- **Edge weight:** OSM-derived road length in metres

The graph is a routing abstraction. Edge lengths are suitable for reproducible shortest-path experiments, not for legal, engineering, or survey-grade measurements.

### 4.3 Overpass API failure and workaround

The Overpass API was not usable for this build:

- `https://overpass-api.de/api/interpreter` returned HTTP 502 and “All query workers are busy”.
- Kumi Systems and `overpass.private.coffee` mirrors timed out.
- `overpass.osm.ch` is a Switzerland-only instance, so an India query returned no usable data.
- A public OpenStreetMap France Overpass endpoint returned HTTP 403 due to access restrictions.

The Uttarakhand PBF extract was therefore used. This is preferable for reproducibility because the exact source snapshot and its server timestamp are recorded.

## 5. Verified road distances

These values were produced by the custom Python Dijkstra implementation and matched the independent Cython implementation to within 1e-6 m.

| Leg | Distance | Nodes / edges | Main named roads |
|---|---:|---:|---|
| A → B | 14,354.5 m | 135 / 134 | Kaulagarh Road, Chakrata Road, Bindal Pul, Bindal Chowk, Kalika Marg, Moti Bazar Road, Paltan Bazar |
| B → C | 761.6 m | 15 / 14 | Dispensary Road, Gandhi Road |
| C → D | 2,899.1 m | 28 / 27 | Rajpur–Mussoorie Road, New Contontment Road |
| **Mandatory A → B → C → D** | **18,015.1 m** | — | — |
| Unconstrained A → D | 14,835.4 m | 131 / 130 | Kaulagarh Road, Thapa Niwas Road, Sherbag Road, Shaheed Durgamal Road, Beacher Road, New Cantonment Road |

The mandatory-stop detour over the unconstrained A → D route is **3,179.8 m**.

Some start-side links are unnamed in OSM. They are still valid drivable graph edges; the report does not invent road names for them.

## 6. Independent routing comparison

The public OSRM demo was queried for the three legs. OSRM’s default profile minimises **travel time**, not distance:

| Leg | OSRM distance | OSRM duration |
|---|---:|---:|
| A → B | 18,999.2 m | 1,463.9 s |
| B → C | 869.4 m | — |
| C → D | 2,959.4 m | — |

OSRM’s A → B route is about 4.6 km longer than the graph’s shortest-**distance** route. This is not evidence that the graph is wrong: a time-optimised route can prefer faster arterials over a shorter local corridor. DoonRoute must not call the distance-optimal route “fastest”, and must not present OSRM as distance ground truth.

## 7. Alternative-route baseline

A simple edge-penalty experiment on the actual graph produced a meaningful alternative by discouraging reuse of the primary A → B edges:

- **1.5× penalty:** the search selects a real-road A → B path with an actual length of 16,164.6 m via Kaulagarh Road, Shaheed Kashmirasingh Road, Ballupur Road, Tilak Road, Paltan Bazar. Full A → B → C → D actual total = **19,825.3 m**; extra over the mandatory shortest route = 1,810.2 m (10.05%).
- **2.0× penalty:** the search selects the Kanwali Road / Akhara Bazar Road / Sabzi Mandi Road / Paltan Bazar corridor. This is a further sensitivity case, not the chosen alternative.

K-shortest-path enumeration mostly returned near-identical parallel-edge variants (for example 14,354.5 m versus 14,355.1 m), which are artifacts of the multigraph and are not useful alternatives.

The application documents the alternative method explicitly: it is a **penalty-based scenario on the real graph**, with reported distances recomputed from unpenalised OSM edge lengths. It is not a claim that the alternative is the second-shortest simple path.

## 8. Modelling limitations

- No live traffic, road closures, construction, festivals, parking availability, fuel cost, or vehicle availability is modelled.
- No travel time is predicted. Road weights are distances in metres, and the route is not a "fastest" route.
- No walking route from a POI to its snapped road node is modelled.
- The graph uses OSM road centrelines and OSM-derived lengths.
- The selected Zenith point has a documented alternative coordinate; the selected Paltan point is a market-area simplification.
- Indoor mall movement, including access to Timezone on the third floor, is outside the model.
- OSM data can contain tagging errors. The final validation will check that every edge used by the route is drivable and that one-way restrictions are respected.

## 9. Source list

- OpenStreetMap France Uttarakhand extract: `https://download.openstreetmap.fr/extracts/asia/india/uttarakhand.osm.pbf`
- OpenStreetMap copyright and licence: `https://www.openstreetmap.org/copyright`
- ODbL 1.0: `https://opendatacommons.org/licenses/odbl/1-0/`
- India HCI 2023 accommodation: `https://www.indiahci.org/2023/accommodation/`
- Zenith Google Maps link from that page: `https://maps.app.goo.gl/Krw7pUkKsMoPcNhB6`
- Zenith alternative listing: `https://exa.ai/library/place/x0vqv10cn9n`
- Paltan Bazaar place listing: `https://exa.ai/library/place/7q4pfh038mf`
- Ghanta Ghar OSM way: `https://www.openstreetmap.org/way/1556686564`
- Centrio Mall OSM node: `https://www.openstreetmap.org/node/12119801701`
- Centrio Mall about page: `https://centriomall.in/about-us-as/`
- Unison Group commercial page: `https://www.unisonindia.com/retails-unison-group-dehradun`
- Timezone Unison Mall official page: `https://www.timezonegames.com/en-in/party-booking/north/unison-mall/`
- Timezone Unison Mall place listing: `https://exa.ai/library/place/wnn0klhb59v`
- OSRM public demo: `https://router.project-osrm.org/`
