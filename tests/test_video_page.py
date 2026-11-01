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
    assert "may mix two separate areas" in warnings and "Far" in warnings
    assert any("Heads found in the three frames" in c.value for c in page.caption)


def test_the_box_check_warns_about_heads_outside_every_box(page):
    radio = next(r for r in page.radio if r.label == "Layout")
    radio.set_value("Custom boxes").run()
    press(page, "Check my boxes against the crowd")
    assert any("outside every box" in w.value for w in page.warning)
