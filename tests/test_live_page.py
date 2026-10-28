"""The Live feed page, rendered headlessly (kept apart from test_app_pages.py so PRs don't collide)."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("cv2")

from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LIVE = next((ROOT / "views").glob("*_Live.py"))


def render() -> AppTest:
    app = AppTest.from_file(str(LIVE), default_timeout=60)
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def test_live_page_demo_feed_counts_and_charts(monkeypatch):
    """The demo feed runs end to end with a stand-in counter (the real model is not installed here)."""
    from crowdshield import counting
    from crowdshield.monitor import points_to_grid

    monkeypatch.setattr(counting, "make_counter",
                        lambda: (lambda f: points_to_grid([(150.0, 500.0 + i) for i in range(35)], f.shape), "test counter"))
    app = render()
    toggle = next(t for t in app.toggle if t.label == "Monitoring")
    toggle.set_value(True).run()
    assert not app.exception, [e.message for e in app.exception]
    text = " ".join(m.value for m in app.markdown)
    assert "Stairs" in text
    assert any("High Risk" in m.value or "Safe" in m.value or "Moderate" in m.value for m in app.markdown)


def test_live_page_refuses_a_private_stream_address():
    app = render()
    app.radio[0].set_value("My own camera").run()
    app.text_input[0].set_value("http://127.0.0.1:8080/stream").run()
    assert any("private network" in e.value for e in app.error)


def test_live_page_opens_a_public_camera_through_its_page_link(monkeypatch):
    import numpy as np

    from crowdshield import live

    monkeypatch.setattr(live, "resolve_stream", lambda link: ("https://s31.ipcamlive.com/streams/x/stream.m3u8", ""))
    monkeypatch.setattr(live, "check_url", lambda url, allow_private=None: (True, ""))
    monkeypatch.setattr(live, "grab_frame", lambda *a, **k: np.zeros((540, 960, 3), np.uint8))
    app = render()
    app.radio[0].set_value("A real public camera (live now)").run()
    assert not app.exception, [e.message for e in app.exception]
    assert any("Blackpool" in c.value for c in app.caption)
    assert any(t.label == "Monitoring" for t in app.toggle)


def test_live_page_says_when_a_public_camera_is_offline(monkeypatch):
    from crowdshield import live

    monkeypatch.setattr(live, "resolve_stream", lambda link: (None, "That camera is offline right now."))
    app = render()
    app.radio[0].set_value("A real public camera (live now)").run()
    assert any("offline" in e.value for e in app.error)


def test_a_live_alert_arrives_with_the_camera_picture(monkeypatch):
    from crowdshield import counting, notify
    from crowdshield.monitor import points_to_grid

    def crowded(frame):  # 80 heads on the stairs, well over what the zone holds
        h, w = frame.shape[:2]
        return points_to_grid([(h * 0.8, w * 0.75 + i) for i in range(80)], frame.shape)

    monkeypatch.setattr(counting, "make_counter", lambda: (crowded, "test counter"))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent = []
    monkeypatch.setattr(notify, "send_telegram",
                        lambda text, image=None, chat_id=None: sent.append((text, image, chat_id)) or (True, "Sent."))
    app = AppTest.from_file(str(LIVE), default_timeout=60)
    app.session_state["telegram_chat"] = {"id": "5", "name": "Asha"}
    app.run()
    next(t for t in app.toggle if t.label == "Send alerts").set_value(True).run()
    next(t for t in app.toggle if t.label == "Monitoring").set_value(True).run()
    assert not app.exception, [e.message for e in app.exception]
    text, image, chat = sent[0]
    assert chat == "5" and "Stairs" in text and image[:2] == b"\xff\xd8"  # a JPEG of the frame
