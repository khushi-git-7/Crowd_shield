"""Analyse a video: watch a crowd change second by second, with every head and every zone marked on the clip."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from crowdshield import counting
from shared_state import GLOBAL_CSS, init_state
from ui import nav_link, page_header, section, working, zone_picker
from video_console import show_console

st.set_page_config(page_title="Analyse a video • Crowd Shield", page_icon=None, layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_state()

page_header("Analyse a video", "See how a crowd changes second by second. Crowd Shield puts a dot on every head, "
            "colours each zone by how full it is, and raises an alarm if the crowd suddenly surges.", "Check a crowd")

SAMPLES = Path(__file__).resolve().parent.parent / "assets" / "samples"
SAMPLE_VIDEO = SAMPLES / "paris_saint_lazare_annotated.mp4"  # for download
SAMPLE_CLEAN = SAMPLES / "paris_saint_lazare_clean.mp4"  # what the player shows, with the analysis on top
SAMPLE_DATA = SAMPLES / "paris_saint_lazare_analysis.json"
SAMPLE_CREDIT = ("Clip: 15 s of \"2025-11-06 17-33-16 - Paris - Saint-Lazare\" by Baidax, "
                 "[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), via "
                 "[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:2025-11-06_17-33-16_-_Paris_-_Saint-Lazare.webm).")
MAX_WIDTH = 960  # frames are shrunk to this width; zone boxes are fractions of the picture, so any size works
# The free hosted demo has little memory and no GPU, so it analyses short clips. Set
# CROWDSHIELD_MAX_VIDEO_S on your own machine to allow longer ones.
MAX_SECONDS = int(os.environ.get("CROWDSHIELD_MAX_VIDEO_S", 20))
LEVEL_HEX = {"Safe": "#10b981", "Moderate": "#f59e0b", "High Risk": "#f97316", "Critical": "#ef4444",
             "Normal": "#10b981", "Crowded": "#f59e0b", "Dangerous": "#f97316", "Crush risk": "#ef4444"}
ZONE_HEX = ["#2a78d6", "#eb6834", "#1baf7a", "#8b5cf6"]
st.markdown("""
<style>
  .steps { display:grid; grid-template-columns: repeat(3, 1fr); gap:.8rem; margin:.2rem 0 1.2rem; }
  .step { background:#fff; border:1px solid #e3e8ef; border-radius:12px; padding:.75rem .9rem; }
  .step b { display:inline-flex; width:22px; height:22px; border-radius:7px; background:#0d9488; color:#fff;
            align-items:center; justify-content:center; font-size:.75rem; margin-right:.45rem; }
  .step span { font-weight:700; font-size:.88rem; color:#0f172a; }
  .step p { margin:.3rem 0 0; font-size:.8rem; color:#64748b; line-height:1.45; }
  @media (max-width: 640px) { .steps { gap:.4rem; } .step { padding:.5rem .55rem; } .step p { display:none; }
                              .step span { font-size:.78rem; } }
</style>
<div class="steps">
  <div class="step"><b>1</b><span>Choose a clip</span><p>From a camera that stays still: CCTV, a drone holding
    position, or a phone on a stand.</p></div>
  <div class="step"><b>2</b><span>Mark the zones</span><p>Pick a layout (left and right, four quarters...) and
    the number of people at which each zone is full.</p></div>
  <div class="step"><b>3</b><span>Watch the result</span><p>Your clip with every head marked, zones turning
    amber and red as they fill, and a chart of each zone over time.</p></div>
</div>
""", unsafe_allow_html=True)


# ── Shared: how a result is shown, for the example and for your own clip alike ──────────────────────
def show_result(clean: bytes, annotated: bytes | None, fps: float, size, zones: list[dict], rows: list[dict],
                events: list, points, count_every, calibrated: bool, handheld: bool = False, key: str = "r"):
    """The console (clean clip, analysis drawn live on top, side panel, timeline), then the details."""
    show_console(clean, fps, size, zones, rows, [] if handheld else events, points, count_every, calibrated)
    if handheld:
        st.info("Surge alarm off: the camera itself moves in this clip, so movement can't be judged.")
    df = pd.DataFrame(rows)
    if calibrated and not handheld:
        with st.expander("Walking speed, crowd pressure and time to danger"):
            from crowdshield.safety import HELBING_TURBULENCE_PRESSURE

            latest = df.groupby("zone").tail(1).set_index("zone")
            for zone, r in latest.iterrows():
                eta = r["eta_s"]
                when = ("no rising trend towards 5 people per m²" if eta is None or pd.isna(eta) else
                        "already above 5 people per m²" if eta == 0 else
                        f"reaches 5 people per m² in about {eta / 60:.1f} min at this trend")
                st.markdown(f"**{zone}**: walking {r['speed']:.2f} m/s · crowd pressure {r['pressure']:.3f}/s² "
                            f"(turbulent pushing began above {HELBING_TURBULENCE_PRESSURE}/s² at the 2006 Hajj "
                            f"disaster) · {when}.")
    d1, d2 = st.columns(2)
    d1.download_button("Download the readings (CSV)", df.to_csv(index=False), "crowd_readings.csv", "text/csv",
                       width="stretch", key=f"csv_{key}", icon=":material/table_view:")
    if annotated:
        d2.download_button("Download the video with dots and zones", annotated, "crowd_shield_video.mp4",
                           "video/mp4", width="stretch", key=f"mp4_{key}", icon=":material/movie:",
                           help="The clip with the analysis drawn in, to share or present.")


tab_example, tab_own = st.tabs(["Example: a busy Paris station", "Analyse your own clip"])

# ── Example: analysed in advance, so it shows instantly ─────────────────────────────────────────────
with tab_example:
    data = json.loads(SAMPLE_DATA.read_text(encoding="utf-8"))
    st.markdown("Fifteen seconds from a fixed camera above the concourse and stairs of Paris Saint-Lazare station, "
                "analysed by Crowd Shield. **Press play**, or click the timeline to jump to any second.")
    show_result(SAMPLE_CLEAN.read_bytes(), SAMPLE_VIDEO.read_bytes(), data["fps"], data["size"], data["zones"],
                data["rows"], data["events"], data["points"], data["count_every"], calibrated=False, key="example")
    st.caption(SAMPLE_CREDIT + f" Analysed with the same code as your own clips, counting once a second with the {data['counter']}. "
               "The zone sizes (40 and 50 people) are examples, chosen for the demo.")
    nav_link("views/8_Live.py", "Want this on a camera that is live right now? Watch a live camera",
             ":material/sensors:", "/Live")

# ── Your own clip ─────────────────────────────────────────────────────────────────────────────────────
def iter_frames(path, max_seconds):
    """Yield frames one at a time, shrunk to MAX_WIDTH, so a clip never sits in memory whole."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    try:
        for _ in range(int(fps * max_seconds)):
            ok, frame = cap.read()
            if not ok:
                break
            if frame.shape[1] > MAX_WIDTH:
                s = MAX_WIDTH / frame.shape[1]
                frame = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            yield frame
    finally:
        cap.release()


def video_fps(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.release()
    return fps


def probe(path, max_seconds, fps, step=3, scale=0.25):
    """First frame, frame count and how much the camera moves, keeping only tiny frames."""
    from crowdshield.motion import camera_motion

    first, n, small = None, 0, []
    for i, frame in enumerate(iter_frames(path, max_seconds)):
        if first is None:
            first = frame
        if i % step == 0:
            small.append(cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))
        n += 1
    camera = camera_motion(small, fps / step, step=1, scale=1.0) if small else 0.0
    return first, n, camera


def clip_on_disk(data: bytes, suffix: str) -> str:
    """OpenCV only reads video from a file. The caller deletes it as soon as decoding is done."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        return f.name


from crowdshield.video_render import _label  # noqa: E402


def preview(frame, corners, zones):
    out = frame.copy()
    if corners is not None:
        cv2.polylines(out, [np.int32(corners)], True, (0, 255, 255), 2)
    for i, (name, poly) in enumerate(zones):
        hexc = ZONE_HEX[i % 4].lstrip("#")
        colour = tuple(int(hexc[j:j + 2], 16) for j in (4, 2, 0))
        cv2.polylines(out, [np.int32(poly)], True, colour, 3)
        x, y = np.int32(poly).min(axis=0)
        _label(out, name, (int(x) + 10, int(y) + 24), bg=colour)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


with tab_own:
    section("1. Choose a clip")
    upload = st.file_uploader("Your clip (MP4, MOV, AVI or MKV)", type=["mp4", "avi", "mov", "mkv"])
    if upload is None:
        st.info("Upload a clip to start. A camera that stays still works best (CCTV, a drone holding position, a "
                f"phone on a stand). The hosted app analyses up to {MAX_SECONDS} seconds of it.")
        st.stop()

    data_bytes, suffix = upload.getvalue(), "." + upload.name.rsplit(".", 1)[-1].lower()
    digest = hashlib.sha1(data_bytes).hexdigest()[:12]
    max_seconds = MAX_SECONDS
    path = clip_on_disk(data_bytes, suffix)
    try:
        fps = video_fps(path)
        first, n_frames, camera = probe(path, max_seconds, fps)
    finally:
        os.remove(path)
    if first is None:
        st.error("Couldn't read this file. Try an MP4 (H.264), which every phone and CCTV system can export.")
        st.stop()
    from crowdshield.motion import CAMERA_MOVING

    h, w = first.shape[:2]
    handheld = camera > CAMERA_MOVING
    seconds = n_frames / fps
    if handheld:
        st.warning("The camera itself moves in this clip (like a handheld phone). Head counts still work, but the "
                   "surge alarm and walking speed would measure the camera, not the crowd, so they're switched off.")

    section("2. Mark the zones")
    left, right = st.columns([3, 2], gap="large")
    with right:
        zones, capacities = zone_picker(w, h, "vz")

        with st.expander("Optional: measure people per m²"):
            calibrate = st.checkbox("I know the size of a rectangle on the floor",
                                    help="Floor tiles, a doorway, parking lines, a stage edge. Then zones are judged "
                                         "by people per m² (crowd-safety levels) instead of by how many they hold.")
            corners = None
            if calibrate:
                st.caption("Its corners as they appear in the picture, in pixels: top-left, top-right, bottom-right, "
                           f"bottom-left. The picture is {w} × {h} px; the yellow outline shows where they are.")
                defaults = [(w * .35, h * .55), (w * .65, h * .55), (w * .8, h * .9), (w * .2, h * .9)]
                corners = []
                for label, (dx, dy) in zip(["Top-left", "Top-right", "Bottom-right", "Bottom-left"], defaults):
                    c1, c2 = st.columns(2)
                    corners.append((c1.number_input(f"{label} x", 0, w, int(dx), key=f"vc_x_{label}"),
                                    c2.number_input(f"{label} y", 0, h, int(dy), key=f"vc_y_{label}")))
                c1, c2 = st.columns(2)
                width_m = c1.number_input("Rectangle width (m)", 0.1, 500.0, 5.0)
                length_m = c2.number_input("Rectangle depth (m)", 0.1, 500.0, 5.0)
    with left:
        st.image(preview(first, corners, zones), width="stretch",
                 caption=f"First frame of your {seconds:.0f}-second clip, with the zones")

    settings = json.dumps([digest, zones, capacities, corners], default=str)
    run = st.button("Analyse video", type="primary", icon=":material/play_arrow:")
    done = st.session_state.get("video_result")
    if not run and not (done and done["settings"] == settings):
        st.caption(f"Counting takes a few seconds per second of video on the free server (about "
                   f"{max(1, round(seconds * 5 / 60))} min for this clip).")
        st.stop()

    if run:
        from crowdshield.config import NotEnoughMemory
        from crowdshield.geometry import GroundCalibration
        from crowdshield.monitor import VideoMonitor, Zone
        from crowdshield.video_render import PointRecorder, encode_clean, render

        calib = None
        if corners is not None:
            try:
                calib = GroundCalibration.from_rectangle(corners, width_m, length_m)
            except Exception as exc:
                st.error(f"Those four corners don't make a usable rectangle ({exc}).")
                st.stop()
        job = working("Analysing your clip", "Getting the counting model ready...")
        counter, counter_name = counting.make_counter()
        if counter is None:
            job.done()
            st.error(f"Can't analyse: {counter_name}.")
            st.stop()
        recorder = PointRecorder() if counter_name.startswith("point model") else None
        monitor = VideoMonitor(recorder or counter, fps, [Zone(n, p) for n, p in zones], calib=calib)
        path = clip_on_disk(data_bytes, suffix)
        out_path, clean_path = path + ".annotated.mp4", path + ".clean.mp4"
        try:
            rows, events = monitor.run(iter_frames(path, max_seconds), progress=lambda i: job.update(
                f"Counting people: second {i / fps:.0f} of {seconds:.0f}", 0.85 * (i + 1) / n_frames)
                if i % max(1, round(fps / 2)) == 0 else None)
            job.update("Preparing your clip for the player...", 0.88)
            encode_clean(iter_frames(path, max_seconds), fps, clean_path)
            job.update("Drawing the dots and zones for the download...", 0.94)
            render(iter_frames(path, max_seconds), fps, out_path, zones, rows, [] if handheld else events,
                   {} if calib else capacities, recorder.points if recorder else None, monitor.count_every)
            video, clean = Path(out_path).read_bytes(), Path(clean_path).read_bytes()
        except NotEnoughMemory as exc:
            job.done()
            st.error(str(exc))
            st.stop()
        finally:
            for p in (path, out_path, clean_path):
                if os.path.exists(p):
                    os.remove(p)
        job.done()
        st.session_state.video_result = {
            "settings": settings, "video": video, "clean": clean, "rows": rows, "events": events, "fps": fps,
            "size": [w, h], "count_every": monitor.count_every, "calibrated": calib is not None,
            "handheld": handheld, "counter": counter_name,
            "points": [[[round(float(c), 1), round(float(r), 1)] for r, c in pts] for pts in recorder.points]
            if recorder else []}
        done = st.session_state.video_result

    section("3. The result")
    show_result(done["clean"], done["video"], done["fps"], done["size"],
                [{"name": n, "polygon": poly, "capacity": None if done["calibrated"] else capacities.get(n)}
                 for n, poly in zones],
                done["rows"], done["events"], done["points"], done["count_every"], done["calibrated"],
                done["handheld"], key="own")
    st.caption(f"Counted with the {done['counter']}, once a second.")
