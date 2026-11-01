"""Checking zone boxes against the heads in a picture."""

import json
from pathlib import Path

import numpy as np

from crowdshield.zone_check import check_zones

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "samples" / "paris_saint_lazare_analysis.json"
BOX = [(0, 0), (640, 0), (640, 360), (0, 360)]


def test_a_box_across_two_floors_is_flagged():
    rng = np.random.default_rng(1)
    upper = np.c_[640 * rng.random(60), rng.uniform(40, 100, 60)]
    lower = np.c_[640 * rng.random(80), rng.uniform(160, 340, 80)]
    assert check_zones(np.vstack([upper, lower]), [("All", BOX)], 640, 360)["mixed"] == ["All"]


def test_an_even_crowd_is_left_alone():
    rng = np.random.default_rng(2)
    crowd = np.c_[640 * rng.random(300), 360 * rng.random(300)]
    assert check_zones(crowd, [("All", BOX)], 640, 360)["mixed"] == []


def test_heads_outside_every_box_are_counted():
    fit = check_zones([(10, 10), (500, 300)], [("Left", [(0, 0), (100, 0), (100, 100), (0, 100)])], 640, 360)
    assert fit["outside"] == 1 and fit["total"] == 2 and fit["heads"] == {"Left": 1}


def test_the_paris_example_passes_and_its_old_walkway_box_would_not():
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    heads = np.vstack(data["points"][:3])
    zones = [(z["name"], z["polygon"]) for z in data["zones"]]
    assert check_zones(heads, zones, 640, 360)["mixed"] == []
    old = [("Old walkway", [(0, 61), (416, 61), (416, 187), (0, 187)])]
    assert check_zones(heads, old, 640, 360)["mixed"] == ["Old walkway"]
