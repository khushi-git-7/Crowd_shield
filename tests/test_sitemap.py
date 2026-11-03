from crowdshield.config import FRUIN_PRESETS
from crowdshield.sitemap import (assess, list_sites, load_site, scenario_counts, site_from_drawings,
                                 timeline, to_geojson)

EVENTS = FRUIN_PRESETS["Crowded events / concerts"]


def test_demo_site_zones_form_one_walkable_network():
    view = assess(load_site(), {}, EVENTS)
    assert set(view["zones"]) == {"A", "B", "C", "D", "E"}
    # The Sangam Nose (A) connects to the rest only through the Sangam Ghat approach (B).
    assert view["adjacency"]["A"] == ["B"]
    assert all(view["adjacency"][z] for z in view["zones"])
    assert all(10_000 < r["area_m2"] < 200_000 for r in view["zones"].values())


def test_demo_scenario_shows_every_risk_level_and_routes_round_the_crowd():
    site = load_site()
    view = assess(site, scenario_counts(site), EVENTS)
    risks = {z: r["risk"] for z, r in view["zones"].items()}
    assert risks == {"A": "Critical", "B": "Moderate", "C": "High Risk",
                     "D": "Safe", "E": "Safe"}
    by_zone = {p["high"]: p for p in view["plans"]}
    assert by_zone["A"]["path"] == ["A", "B", "D"]  # nearest Safe zone, through the approach
    assert by_zone["C"]["path"] == ["C", "E"]


def test_zones_without_counts_are_drawn_but_not_planned():
    view = assess(load_site(), {"A": 10}, EVENTS)
    assert view["zones"]["B"]["count"] is None and view["zones"]["B"]["risk"] is None
    assert view["plans"] == []


def test_drawn_shapes_become_a_site():
    ring = [[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]]
    features = [{"geometry": {"type": "Polygon", "coordinates": [ring]}},
                {"geometry": {"type": "LineString", "coordinates": ring}}]
    site = site_from_drawings(features, {"C": "North gate"}, {0: "C", 1: "D"})
    assert list(site["zones"]) == ["C"]
    assert site["zones"]["C"]["name"] == "North gate"
    assert site["centre"] == [0.0005, 0.0005]


def test_every_bundled_site_is_one_connected_network():
    sites = list_sites()
    assert [s["short"] for s in sites][0] == "Sangam, Prayagraj"  # the demo opens first
    assert any("Madurai" in s["short"] for s in sites)
    for site in sites:
        graph = assess(site, {}, EVENTS)["adjacency"]
        reached, todo = set(), [next(iter(graph))]
        while todo:
            zone = todo.pop()
            if zone not in reached:
                reached.add(zone)
                todo.extend(graph[zone])
        assert reached == set(graph), site["short"]


def test_madurai_routes_people_off_the_riverbed_towards_the_city():
    site = next(s for s in list_sites() if "Madurai" in s["short"])
    view = assess(site, scenario_counts(site), EVENTS)
    assert view["zones"]["A"]["risk"] == "Critical"
    big = max(view["plans"], key=lambda p: p["move"])
    assert big["path"][:2] == ["A", "C"]  # the biggest flow leaves the riverbed by the south bank


def test_the_surge_timeline_scales_counts_and_peaks_at_one():
    site = load_site()
    steps = timeline(site)
    assert max(s["factor"] for s in steps) == 1.0
    half = scenario_counts(site, 0.5)
    full = scenario_counts(site)
    assert all(abs(half[z] - full[z] / 2) <= 1 for z in full)


def test_geojson_export_carries_the_numbers():
    view = assess(load_site(), scenario_counts(load_site()), EVENTS)
    fc = to_geojson(view)
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 5
    props = fc["features"][0]["properties"]
    assert {"zone", "name", "area_m2", "people", "per_m2", "risk", "connected_to"} <= set(props)


def test_walking_speed_follows_weidmann():
    from crowdshield.sitemap import walking_speed

    assert walking_speed(0) == 1.34
    assert abs(walking_speed(2.0) - 0.61) < 0.01  # a busy platform: about half of free walking speed
    assert walking_speed(5.4) == 0.0


def test_walk_minutes_adds_up_the_path_and_stops_when_packed():
    from crowdshield.sitemap import walk_minutes, walking_speed

    distance = {("A", "B"): 300.0, ("C", "B"): 300.0}
    assert abs(walk_minutes(["A", "B", "C"], distance, {}) - 600 / 1.34 / 60) < 0.01
    assert walk_minutes(["A", "B"], distance, {"A": 5.5}) is None
    slow = walk_minutes(["A", "B"], distance, {"A": 4.0, "B": 0.0})  # the step is walked at the mean of 4 and 0 per m²
    assert abs(slow - 300 / walking_speed(2.0) / 60) < 0.01
