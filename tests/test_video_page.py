"""The Video page with a real clip: checking boxes against the crowd before analysing."""

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("streamlit")
pytest.importorskip("cv2")

from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAGE = next((ROOT / "views").glob("*_Video.py"))
SAMPLES = ROOT / "assets" / "samples"


class Clip:
    name = "clip.mp4"

    def getvalue(self):
        return (SAMPLES / "paris_saint_lazare_clean.mp4").read_bytes()


@pytest.fixture
def page(monkeypatch):
    """The page with the clip uploaded, and the saved head points in place of the model."""
    import streamlit as st

    from crowdshield import points

    saved = json.loads((SAMPLES / "paris_saint_lazare_analysis.json").read_text(encoding="utf-8"))["points"]
    calls = iter(saved[::7])  # as the button samples: spread across the clip
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: Clip())
    monkeypatch.setattr(points, "count_points", lambda frame: {"points": np.array(next(calls), float)[:, ::-1]})
    app = AppTest.from_file(str(PAGE), default_timeout=60).run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def press(app, label):
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception, [e.message for e in app.exception]


def test_the_box_check_warns_about_a_bad_layout(page):
    next(r for r in page.radio if r.label == "Layout").set_value("Near and far").run()
    press(page, "Check my boxes against the crowd")
    warnings = " ".join(w.value for w in page.warning)
    assert "Near may mix two separate areas" in warnings  # the floor on the left, the stairs on the right
    assert any("Heads found in the three frames" in c.value for c in page.caption)


def test_the_box_check_warns_about_heads_outside_every_box(page):
    next(r for r in page.radio if r.label == "Layout").set_value("Custom boxes").run()
    page.slider(key="vz_y_0").set_value((30, 100)).run()
    page.slider(key="vz_y_1").set_value((30, 100)).run()
    press(page, "Check my boxes against the crowd")
    assert any("outside every box" in w.value for w in page.warning)


def choose(app, label):
    next(r for r in app.radio if r.label == "Layout").set_value(label).run()
    assert not app.exception, [e.message for e in app.exception]


def test_the_whole_picture_is_not_passed_as_a_good_fit(page):
    press(page, "Check my boxes against the crowd")
    assert any("covers nearly the whole picture" in i.value for i in page.info)
    assert not page.success


def test_custom_boxes_start_by_covering_the_picture_top_to_bottom(page):
    choose(page, "Custom boxes")
    press(page, "Check my boxes against the crowd")
    assert not any("outside every box" in w.value for w in page.warning)


def test_a_custom_box_with_both_ends_on_one_number_still_works(page, monkeypatch):
    choose(page, "Custom boxes")
    page.slider(key="vz_x_0").set_value((40, 40)).run()
    page.slider(key="vz_y_1").set_value((100, 100)).run()
    assert not page.exception, [e.message for e in page.exception]
    press(page, "Check my boxes against the crowd")


def test_two_custom_zones_with_one_name_stay_separate(page):
    choose(page, "Custom boxes")
    page.text_input(key="vz_name_Custom boxes_1").set_value("Zone A").run()
    assert not page.exception, [e.message for e in page.exception]
    press(page, "Check my boxes against the crowd")
    assert any("Zone A 2" in c.value for c in page.caption)


def test_overlapping_custom_boxes_warn_about_counting_twice(page):
    choose(page, "Custom boxes")
    page.slider(key="vz_x_0").set_value((0, 80)).run()
    press(page, "Check my boxes against the crowd")
    assert any("counted twice" in w.value for w in page.warning)


def test_a_custom_layout_goes_all_the_way_through_the_analysis(page, monkeypatch):
    from crowdshield import counting
    from crowdshield.monitor import points_to_grid

    monkeypatch.setattr(counting, "make_counter", lambda: (
        lambda frame: points_to_grid([(200.0, 100.0)] * 7 + [(200.0, 500.0)] * 3, frame.shape), "test counter"))
    page.default_timeout = 180
    choose(page, "Custom boxes")
    press(page, "Analyse video")
    player = page.get("iframe")[-1].proto.srcdoc
    assert '"name":"Zone A"' in player and '"name":"Zone B"' in player
    rows = json.loads(player.split('"rows":', 1)[1].split(',"events"', 1)[0])
    assert {r["zone"]: r["people"] for r in rows if r["t"] == 0} == {"Zone A": 7.0, "Zone B": 3.0}


def test_the_results_of_a_check_stay_in_place_on_the_next_run(page):
    """The page's layout must match between runs, or an old copy of the message stays on screen, greyed out."""
    press(page, "Check my boxes against the crowd")
    def layout():
        return [type(e).__name__ for e in page.main]

    pressed = layout()
    assert "Help" not in pressed  # a bare expression returning an element makes Streamlit print its documentation
    page.run()
    assert layout() == pressed


def test_a_moving_camera_gets_no_verdict_on_its_boxes(page, monkeypatch):
    from crowdshield import motion

    monkeypatch.setattr(motion, "CAMERA_MOVING", -1.0)
    page.run()
    choose(page, "Near and far")
    press(page, "Check my boxes against the crowd")
    assert any("Boxes can't be checked on this clip" in i.value for i in page.info)
    assert not page.success and not any("may mix" in w.value for w in page.warning)
