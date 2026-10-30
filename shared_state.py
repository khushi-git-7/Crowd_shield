"""Shared session-state defaults and constants used across pages."""

from datetime import datetime, timedelta, timezone

import streamlit as st

from crowdshield.risk import UNKNOWN, judge, risk_level

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


DEFAULT_LIMITS = (f"the defaults ({DEFAULT_THRESHOLDS['moderate']} / {DEFAULT_THRESHOLDS['high']} / "
                  f"{DEFAULT_THRESHOLDS['critical']} people in every zone)")


def limits_note() -> str:
    """One line on where the risk limits come from, so a count reads the same on every page."""
    source = st.session_state.get("limits_source", DEFAULT_LIMITS)
    note = f"Risk limits come from {source}."
    if source == DEFAULT_LIMITS:
        note += (" For limits based on each zone's real size, open the Site map and press Apply map areas "
                 "(or enter areas in Settings).")
    return note


def ist_now(fmt: str = "%H:%M:%S IST") -> str:
    """The time in India, for alert logs and history."""
    return datetime.now(IST).strftime(fmt)


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
    return judge(count, limits, view_share(seg)) if whole_zone_limits() else (risk_level(count, limits), limits)


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
