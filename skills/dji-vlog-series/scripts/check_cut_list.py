"""Step 5: validate one episode's cut list before accepting it from a worker.

  python check_cut_list.py --review <review> --plan <project>/storyboard-plan.json 01 --target 330

Checks, in order: the beat cards match the approved storyboard (same ids, same order); every
shot's file is in frame-index.json; every out-point is inside its clip; in < out; audio mode is
keep|duck|music-only; beat_seconds equals the sum of its shots (±0.6 s); episode_seconds within
--tolerance (default 10 %) of --target. Exit 1 on any error so a dispatch loop can gate on it.
"""
import argparse, json, sys
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("episode", help="episode number, e.g. 01")
AP.add_argument("--review", required=True, help="<review> dir holding clip-review/ and frame-index.json")
AP.add_argument("--plan", default="", help="storyboard-plan.json; when given, beat order is checked against it")
AP.add_argument("--target", type=float, default=0, help="target runtime in seconds (0 = read target_runtime_s)")
AP.add_argument("--tolerance", type=float, default=0.10)
A = AP.parse_args()

R = Path(A.review)
d = json.load(open(R / "clip-review" / f"e{A.episode}.json", encoding="utf-8"))
durations = {e["file"]: e["duration"] for e in json.load(open(R / "frame-index.json", encoding="utf-8"))}
target = A.target or float(d.get("target_runtime_s", 0))
errs, total, n_shots = [], 0.0, 0

if A.plan:
    plan = json.load(open(A.plan, encoding="utf-8"))
    ep = next((e for e in plan["proposed_episodes"] if e["episode"] == A.episode), None)
    if ep is None:
        errs.append(f"episode {A.episode} not in {A.plan}")
    else:
        want = [b["card"] for b in ep["beats"]]
        got = [b["card"] for b in d["beats"]]
        if want != got:
            errs.append(f"beat order differs from the approved strip:\n    plan {want}\n    list {got}")

for b in d["beats"]:
    bs = 0.0
    for s in b["shots"]:
        n_shots += 1
        f = s["file"]
        if f not in durations:
            errs.append(f"{b['card']}: {f} not in frame-index.json")
        elif s["out"] > durations[f] + 0.01:
            errs.append(f"{b['card']}: {f} out {s['out']} > clip duration {durations[f]:.2f}")
        if s["in"] >= s["out"]:
            errs.append(f"{b['card']}: {f} in {s['in']} >= out {s['out']}")
        if s.get("audio") not in ("keep", "duck", "music-only"):
            errs.append(f"{b['card']}: {f} audio mode {s.get('audio')!r}")
        bs += s["out"] - s["in"]
    if abs(bs - b["beat_seconds"]) > 0.6:
        errs.append(f"{b['card']}: beat_seconds {b['beat_seconds']} but shots sum to {bs:.1f}")
    total += bs

dev = (total - target) / target if target else 0.0
if target and abs(dev) > A.tolerance:
    errs.append(f"episode_seconds {total:.1f} is {dev:+.0%} from target {target:.0f} (tolerance {A.tolerance:.0%})")
if abs(total - float(d.get("episode_seconds", total))) > 0.6:
    errs.append(f"episode_seconds field {d.get('episode_seconds')} but beats sum to {total:.1f}")

strong = sum(1 for m in d.get("human_audio_moments", []) if m.get("strength") == "strong")
print(f"e{A.episode}: {n_shots} shots, {total:.1f} s vs target {target:.0f} ({dev:+.1%}); "
      f"{strong} strong moments, {len(d.get('captions_candidates', []))} caption candidates, "
      f"{len(d.get('flags', []))} flags")
if errs:
    print("ERRORS:")
    for e in errs: print("  -", e)
    sys.exit(1)
print("clean")
