"""Shared session-state defaults and constants used across pages."""

import secrets
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

from crowdshield.risk import UNKNOWN, judge, risk_level, thresholds_from_area

# Constants live in the core package; re-exported here for the pages.
from crowdshield.config import (  # noqa: F401
    DEFAULT_THRESHOLDS, FRUIN_PRESETS, MAX_IMAGES_PER_SEGMENT, RISK_LEVELS,
    SEGMENTS, SOURCE_MODEL_MAP,
)

IST = timezone(timedelta(hours=5, minutes=30))  # the hosted server runs on UTC

RISK_COLORS = {
    "Safe":      "#10b981",
    "Moderate":  "#f59e0b",
    "High Risk": "#f97316",
    "Critical":  "#ef4444",
    UNKNOWN:     "#94a3b8",
}
# How much ground the photos show. A photo alone can't tell: that needs a known distance in the picture.
AREA_SIZES = {"Not sure": 0, "Small: a gate or corridor (about 50 m²)": 50,
              "Medium: a platform or stretch of street (about 300 m²)": 300,
              "Large: a courtyard or ghat section (about 1,500 m²)": 1500,
              "Very large: open ground (about 10,000 m²)": 10000}
VIEW_SHARES = {"Not sure": None, "All of it": 1.0, "About three quarters": 0.75, "About half": 0.5,
               "About a quarter": 0.25}


def init_state():
    if "agents" not in st.session_state:
        st.session_state.agents = {s: "" for s in SEGMENTS}
    if "uploaded_images" not in st.session_state:
        st.session_state.uploaded_images = {s: [] for s in SEGMENTS}
    if "image_names" not in st.session_state:
        st.session_state.image_names = {s: [] for s in SEGMENTS}
    if "image_sources" not in st.session_state:
        st.session_state.image_sources = {s: [] for s in SEGMENTS}
    if "crowd_data" not in st.session_state:
        st.session_state.crowd_data = {}
    if "active_model" not in st.session_state:
        st.session_state.active_model = "crowd_yolo"
    if "thresholds" not in st.session_state:
        st.session_state.thresholds = {
            s: dict(DEFAULT_THRESHOLDS) for s in SEGMENTS
        }
    if "seg_areas" not in st.session_state:
        st.session_state.seg_areas = {s: 0 for s in SEGMENTS}
    if "alert_count" not in st.session_state:
        st.session_state.alert_count = 0
    if "limits_source" not in st.session_state:  # where the zones' risk limits came from, said on every page
        st.session_state.limits_source = DEFAULT_LIMITS
    if "detection_history" not in st.session_state:
        st.session_state.detection_history = []


PHOTO_AREA_PRESET = "Standard (mixed venues)"
DEFAULT_LIMITS = (f"the defaults ({DEFAULT_THRESHOLDS['moderate']} / {DEFAULT_THRESHOLDS['high']} / "
                  f"{DEFAULT_THRESHOLDS['critical']} people in every zone)")


def limits_note() -> str:
    """One line on where the risk limits come from, so a count reads the same on every page."""
    source = st.session_state.get("limits_source", DEFAULT_LIMITS)
    note = f"Risk limits come from {source}."
    if source == DEFAULT_LIMITS:
        note += (" Those numbers know nothing about the place, so a low count shows as Unknown until you give the "
                 "area in the photos below, or apply a Site map (or enter areas in Settings).")
    return note


def ist_now(fmt: str = "%H:%M:%S IST") -> str:
    """The time in India, for alert logs and history."""
    return datetime.now(IST).strftime(fmt)


# A refresh starts a new Streamlit session. Work is kept in server memory for a while, and a cookie with a
# random token lets this browser, and only this browser, find it again. Unlike a link, it can't be shared by accident.
COOKIE = "cs_session"
KEEP_SECONDS = 2 * 60 * 60
KEEP_SESSIONS = 12  # the free server's memory is small; the oldest go first
KEEP = ("agents", "uploaded_images", "image_names", "image_sources", "crowd_data", "thresholds", "seg_areas",
        "limits_source", "detection_history", "alert_count", "zone_names", "zone_adjacency", "custom_site",
        "applied_preset", "photo_area", "zone_view", "example_event", "telegram_chat", "telegram_code",
        "sample_shown", "live", "live_key", "live_sig", "live_first", "live_on", "live_streams")


@st.cache_resource
def _kept_sessions() -> dict:
    return {}


def browser_token() -> str | None:
    return st.context.cookies.get(COOKIE)


def restore_session() -> None:
    """Bring back this browser's work after a refresh. Runs before anything else on a new session."""
    if "session_token" in st.session_state:
        return
    token, kept = browser_token(), _kept_sessions()
    saved = kept.get(token)
    if saved and time.time() - saved["at"] < KEEP_SECONDS:
        st.session_state.update(saved["state"])
    st.session_state.session_token = token or secrets.token_hex(16)


def remember_session() -> None:
    """Keep this session's work, and give the browser its token."""
    token, kept, now = st.session_state.session_token, _kept_sessions(), time.time()
    kept[token] = {"at": now, "state": {k: st.session_state[k] for k in KEEP if k in st.session_state}}
    for old in [t for t, s in kept.items() if now - s["at"] >= KEEP_SECONDS]:
        del kept[old]
    for old in sorted(kept, key=lambda t: kept[t]["at"])[:-KEEP_SESSIONS]:
        del kept[old]
    st.sidebar.html(f"<script>document.cookie = '{COOKIE}={token}; path=/; max-age={KEEP_SECONDS}; SameSite=Lax';"
                    "</script>", unsafe_allow_javascript=True)


def telegram_chat() -> str | None:
    """The Telegram chat this visitor linked in Team and alerts, if any (kept for this session only)."""
    return (st.session_state.get("telegram_chat") or {}).get("id")


def get_seg_thresholds(seg: str) -> dict:
    t = st.session_state.get("thresholds", {})
    if seg not in t:
        t[seg] = dict(DEFAULT_THRESHOLDS)
        st.session_state.thresholds = t
    return t[seg]


def view_share(seg: str) -> float | None:
    """How much of the zone its photos show, as the user said; None if they haven't."""
    return VIEW_SHARES[st.session_state.get("zone_view", {}).get(seg, "Not sure")]


def whole_zone_limits() -> bool:
    """Limits from a site map are for each zone's full area, not for what one camera sees."""
    return st.session_state.get("limits_source", "").startswith("each zone's area on the")


def zone_risk(seg: str, count: int) -> tuple[str, dict]:
    """(risk, limits in use) for a counted zone. The one place pages get this from, so they agree."""
    limits = get_seg_thresholds(seg)
    if whole_zone_limits():
        return judge(count, limits, view_share(seg))
    if st.session_state.get("limits_source", DEFAULT_LIMITS) == DEFAULT_LIMITS:
        # The defaults know nothing of the place, so a low count needs the area in view before it means anything.
        area = st.session_state.get("photo_area", {}).get(seg)
        if not area:
            return judge(count, limits, None)
        limits = thresholds_from_area(area, FRUIN_PRESETS[PHOTO_AREA_PRESET])
    return risk_level(count, limits), limits


EXAMPLE_EVENT = {"A": ("IN_03.jpg", "Bathing ghat"), "B": ("IN_08.jpg", "Railway approach"),
                 "C": ("IN_05.jpg", "Main road"), "D": ("IN_21.jpg", "Riverside"), "E": ("IN_12.jpg", "Market street")}
EXAMPLE_LIMITS = {"moderate": 200, "high": 400, "critical": 800}
EXAMPLE_NOTE = ("Example event: five real Indian crowd photos from different places, standing in for one site, with "
                "counts made in advance at full detail. The zone names and limits are made up. Count your own photos "
                "to replace it.")


def load_example_event() -> None:
    """Fill all five zones from the sample photos, so the plan can be seen without any photos of your own."""
    import cv2

    from crowdshield import benchmark
    from crowdshield.detection import render_overlay

    rows = {r["image"]: r for r in benchmark.load()}
    data = {}
    for seg, (image, _) in EXAMPLE_EVENT.items():
        row = rows[image]
        img = cv2.imread(str(benchmark.INDIA / "images" / image))
        overlay = render_overlay(img, [], [], None, benchmark.points_rc(row["model_points"]))
        count = round(row["model"])
        data[seg] = {"count": count, "body_count": count, "head_count": 0, "image_count": 1, "model_key": "points",
                     "per_image": [{"count": count, "body_count": count, "head_count": 0, "overlay": overlay,
                                    "model_key": "points"}],
                     "per_img_sources": ["ground"], "combine": "sum", "counter": "points"}
    st.session_state.crowd_data = data
    st.session_state.zone_names = {seg: name for seg, (_, name) in EXAMPLE_EVENT.items()}
    st.session_state.thresholds = {seg: dict(EXAMPLE_LIMITS) for seg in SEGMENTS}
    st.session_state.limits_source = "the example event (made-up limits)"
    st.session_state.zone_adjacency = None
    st.session_state.example_event = True


def size_question(seg: str) -> bool:
    """Whether the app needs to be told how much a zone's photos show before it can judge a low count."""
    return whole_zone_limits() or st.session_state.get("limits_source", DEFAULT_LIMITS) == DEFAULT_LIMITS


def size_picker(seg: str, label: str | None = None) -> None:
    """The one-click question that lets a zone be judged, on whichever page it is asked."""
    if whole_zone_limits():
        views = st.session_state.setdefault("zone_view", {})
        st.session_state.setdefault(f"view_{seg}", views.get(seg, "Not sure"))
        views[seg] = st.selectbox(label or "How much of this zone do the photos show?", list(VIEW_SHARES),
                                  key=f"view_{seg}",
                                  help="The limits are for the whole zone. A photo of one corner can look safe "
                                       "while the rest is packed, so without this the risk is Unknown.")
    else:
        areas = st.session_state.setdefault("photo_area", {})
        names = list(AREA_SIZES)
        st.session_state.setdefault(f"size_{seg}", next((n for n in names if AREA_SIZES[n] == areas.get(seg)), names[0]))
        areas[seg] = AREA_SIZES[st.selectbox(label or "How big is the area in the photos?", names, key=f"size_{seg}",
                                             help="A rough size is enough. It turns the count into how tightly "
                                                  f"people stand ({PHOTO_AREA_PRESET} limits). For an exact figure, "
                                                  "use Settings or a Site map.")]


def zone_title(seg: str) -> str:
    """HTML for a zone card's title: the letter, and its place name on its own line so narrow cards never cut it."""
    import html

    name = st.session_state.get("zone_names", {}).get(seg)
    return (f"<div style='min-width:0'><b style='font-size:.9rem'>Zone {seg}</b>"
            + (f"<div style='font-size:.76rem;color:#64748b;line-height:1.3'>{html.escape(name)}</div>" if name else "")
            + "</div>")


def zone_label(seg: str) -> str:
    """"Zone A", or "Zone A · Sangam Nose" once a site map has named the zones."""
    name = st.session_state.get("zone_names", {}).get(seg)
    return f"Zone {seg} · {name}" if name else f"Zone {seg}"


from ui import GLOBAL_CSS  # noqa: E402,F401  (the design system lives in ui.py)
