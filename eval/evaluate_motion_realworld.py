"""Run Crowd Shield's surge alarm, unchanged, on real panic footage (Abnormal High-density Crowds, DbCL-1.0).

Every clip is processed with the app's default alarm settings. Nothing is tuned here: the point is to see
how the setting chosen on the UMN videos does on real crowds.
"""
import glob, json, os, subprocess, sys

subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/khushi-git-7/Crowd_shield.git", "/tmp/cs"], check=True)
sys.path.insert(0, "/tmp/cs")
import cv2, numpy as np  # noqa: E402
from crowdshield.motion import MotionAlarm, flow_stats, optical_flow  # noqa: E402

BASE = glob.glob("/kaggle/input/**/Abnormal High-density Crowds", recursive=True)[0]
print(open(os.path.join(BASE, "Read Me.txt"), errors="replace").read(), flush=True)
WIDTH = 320  # as the UMN test, so the alarm sees the same scale


def frames_from_video(path, start_s=0.0, end_s=None):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000)
    out = []
    while True:
        ok, f = cap.read()
        if not ok or (end_s is not None and len(out) / fps >= end_s - start_s):
            break
        out.append(cv2.resize(f, (WIDTH, int(f.shape[0] * WIDTH / f.shape[1]))))
    return out, fps


def frames_from_folder(folder, fps):
    files = sorted(glob.glob(os.path.join(folder, "*.png")) + glob.glob(os.path.join(folder, "*.jpg")))
    out = []
    for p in files:
        f = cv2.imread(p)
        out.append(cv2.resize(f, (WIDTH, int(f.shape[0] * WIDTH / f.shape[1]))))
    return out, fps


def run(name, frames, fps):
    alarm, prev, fired, per_s = MotionAlarm(), None, [], {}
    moving = []
    for i, f in enumerate(frames):
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            st = flow_stats(optical_flow(prev, g))
            moving.append(st["moving"])
            if alarm.update(st):
                fired.append([round(i / fps, 2), alarm.reason])
            if alarm.speed.normal:
                s = max(st["speed"] / alarm.speed.normal / alarm.speed.ratio, st["energy"] / alarm.energy.normal / alarm.energy.ratio)
                k = int(i / fps)
                per_s[k] = round(max(per_s.get(k, 0), s), 2)
        prev = g
    res = {"clip": name, "fps": fps, "seconds": round(len(frames) / fps, 1), "alarms": fired, "score_by_second": per_s,
           "median_moving_share": round(float(np.median(moving)), 3) if moving else None}
    print(json.dumps(res), flush=True)
    return res


results = []
ts = os.path.join(BASE, "1_Times_Square", "Footage.avi")
for view, (a, b) in {"Times Square view 1": (0, 47), "Times Square view 2": (48, 92), "Times Square view 3": (93, 138)}.items():
    fr, fps = frames_from_video(ts, a, b)
    results.append(run(view, fr, fps))
for p in sorted(glob.glob(os.path.join(BASE, "2_Las_Vegas", "*", "Footage.mp4"))):
    fr, fps = frames_from_video(p)
    results.append(run("Las Vegas " + p.split(os.sep)[-2], fr, fps))
lp = os.path.join(BASE, "3_Love Parade", "Footage.mp4")
fr, fps = frames_from_video(lp, 0, 180)
results.append(run("Love Parade (first 3 min)", fr, fps))
for v in sorted(glob.glob(os.path.join(BASE, "4_Italy", "*", "Test"))):
    fr, fps = frames_from_folder(v, 29.97)
    results.append(run("Italy " + v.split(os.sep)[-2] + " (frames at 29.97 fps assumed)", fr, fps))
json.dump(results, open("/kaggle/working/surge_realworld.json", "w"), indent=1)
