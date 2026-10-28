"""The video console page: one self-contained HTML player built from a clip and its readings."""

import json

import pytest

pytest.importorskip("streamlit")

from video_console import console_html  # noqa: E402


def test_the_console_carries_the_clip_zones_readings_and_points():
    rows = [{"t": 0.0, "zone": "A", "people": 12.0, "per_m2": float("nan"), "level": None},
            {"t": 1.0, "zone": "A", "people": 30.0, "per_m2": float("nan"), "level": None}]
    html = console_html(b"\x00\x00\x00\x18ftypmp42", 25.0, (640, 360),
                        [{"name": "A", "polygon": [(0, 0), (320, 0), (320, 360), (0, 360)], "capacity": 40}],
                        rows, [{"t": 1.0, "event": "Surge: A speeding up"}], [[[10.0, 20.0]], [[11.0, 21.0]]], 25)
    data = json.loads(html.split("const D = ", 1)[1].split(";\n", 1)[0])
    assert data["zones"][0]["cap"] == 40 and len(data["rows"]) == 2 and data["points"][1] == [[11.0, 21.0]]
    assert data["rows"][0]["per_m2"] is None  # NaN would break the page's JSON
    assert data["events"] == [{"t": 1.0, "text": "A speeding up"}]
    assert html.count("data:video/mp4;base64,") == 1 and "__DATA__" not in html and "__SRC__" not in html
