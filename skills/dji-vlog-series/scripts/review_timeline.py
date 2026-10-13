"""Optional, between steps 6 and 8: nudge one episode's cuts by hand on a FilmCraft timeline.

  python review_timeline.py --config series.json push 01 --open    # cut list -> timeline, open it
  python review_timeline.py --config series.json pull 01           # print what the editor changed
  python review_timeline.py --config series.json pull 01 --write   # write it into the cut list
  python review_timeline.py --selftest

push lays the shots of <cut_lists>/eNN.json back to back on V1 of <review>/timeline/eNN.fcproj,
reading picture from the proxies, with one marker per beat. The editor trims, slips, deletes or
reorders shots inside a beat and saves. pull reads the saved project and rewrites each shot's
in/out, in seconds of the ORIGINAL file like every other cut-list time. The timeline carries cuts
only: text layers, the music bed and the audio modes stay with build_episodes.py.

A cut can move outward only as far as its proxy reaches (the handle); pull --write then means a
make_proxies.py re-run to restore the handles. A shot the editor did not touch keeps its exact
in/out. pull refuses, and writes nothing, on a clip it cannot trace to a shot (a razor split, a
clip dragged in from the bin), a speed change, a shot moved into another beat, or an emptied beat.

FilmCraft (https://github.com/storytold/filmcraft) is found through --filmcraft-cli, then the
FILMCRAFT_CLI environment variable, then PATH.
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

# FilmCraft's time base: every time in its commands and its inspect output is in these ticks.
TICKS_PER_SECOND = 254_016_000_000

AP = argparse.ArgumentParser()
AP.add_argument("action", nargs="?", choices=["push", "pull"])
AP.add_argument("episode", nargs="?", help="episode number, e.g. 01")
AP.add_argument("--config", help="series.json (see templates/series.json)")
AP.add_argument("--filmcraft-cli", default="", help="path to filmcraft-cli; default $FILMCRAFT_CLI, then PATH")
AP.add_argument("--open", action="store_true", help="push: open the timeline in FilmCraft afterwards")
AP.add_argument("--force", action="store_true", help="push: replace a timeline that already exists")
AP.add_argument("--write", action="store_true", help="pull: write the changes into the cut list")
AP.add_argument("--selftest", action="store_true", help="run inline synthetic self-checks and exit (no file I/O)")
A = AP.parse_args()


def ticks(seconds):
    return int(round(seconds * TICKS_PER_SECOND))


def proxy_name(shot):
    return Path(shot["file"]).stem + ".mp4"


def build_commands(cut, item_ids, offsets, fps, canvas, name):
    """The FilmCraft commands that lay `cut` on V1, on the same frame grid as build_episodes.py."""
    new_sequence = {"id": "file.newSequence",
                    "params": {"name": name, "width": canvas[0], "height": canvas[1],
                               "fps": fps, "sampleRate": 48000}}
    commands = [new_sequence]
    frames_so_far = 0
    for beat in cut["beats"]:
        marker = {"id": "markers.add",
                  "params": {"target": "program", "time": ticks(frames_so_far / fps), "name": beat["card"]}}
        commands.append(marker)
        for shot in beat["shots"]:
            stem = Path(shot["file"]).stem
            frames = int(round((shot["out"] - shot["in"]) * fps))
            place = {"id": "timeline.place",
                     "params": {"item": item_ids[proxy_name(shot)], "track": "V1",
                                "time": ticks(frames_so_far / fps),
                                "sourceIn": ticks(shot["in"] - offsets[stem]),
                                "duration": ticks(frames / fps)}}
            commands.append(place)
            frames_so_far += frames
    return commands


def apply_timeline(cut, sequence, clip_to_shot, offsets, fps):
    """Returns (new cut list, change lines, error lines) for the saved timeline `sequence`."""
    # push rounds a shot to whole frames and FilmCraft keeps source times on the frame grid, so an
    # untouched shot can read back up to half a frame off; a real nudge is a whole frame or more.
    untouched = 0.5 / fps + 0.001
    changes, errors = [], []
    review_track = sequence["video"][0]
    for track in sequence["video"][1:]:
        if track["items"]:
            errors.append(f"{track['name']} holds {len(track['items'])} clips; keep every shot on {review_track['name']}")

    kept = [[] for _ in cut["beats"]]          # per beat: (old shot index, new shot), timeline order
    furthest_beat = 0
    for item in sorted(review_track["items"], key=lambda i: i["start"]):
        where = clip_to_shot.get(str(item["clip"]))
        at = f"{item['name']} at {item['start'] / TICKS_PER_SECOND:.2f}s"
        if where is None:
            errors.append(f"{at} is not a shot from the cut list (split or added in the timeline)")
            continue
        beat_index, shot_index = where
        beat = cut["beats"][beat_index]
        old = beat["shots"][shot_index] if shot_index < len(beat["shots"]) else None
        if old is None or proxy_name(old) != item["name"]:
            errors.append(f"{at}: the cut list changed since push; push again")
            continue
        if item["speed"] != 1.0 or item["reverse"]:
            errors.append(f"{at}: speed {item['speed']}, reverse {item['reverse']}; the renderer plays shots at 1x forward")
            continue
        if beat_index < furthest_beat:
            errors.append(f"{at} belongs to beat {beat['card']} but now sits after a later beat")
            continue
        furthest_beat = beat_index

        offset = offsets[Path(old["file"]).stem]
        timeline_in = item["sourceIn"] / TICKS_PER_SECOND + offset
        timeline_out = item["sourceOut"] / TICKS_PER_SECOND + offset
        new_in = old["in"] if abs(timeline_in - old["in"]) < untouched else round(timeline_in, 3)
        new_out = old["out"] if abs(timeline_out - old["out"]) < untouched else round(timeline_out, 3)
        if (new_in, new_out) != (old["in"], old["out"]):
            changes.append(f"{beat['card']}: {old['file']} {old['in']}-{old['out']} -> {new_in}-{new_out}")
        new = dict(old)
        new["in"] = new_in
        new["out"] = new_out
        kept[beat_index].append((shot_index, new))

    new_beats = []
    for beat, shots in zip(cut["beats"], kept):
        order = [index for index, _ in shots]
        for index, old in enumerate(beat["shots"]):
            if index not in order:
                changes.append(f"{beat['card']}: {old['file']} {old['in']}-{old['out']} removed")
        if order != sorted(order):
            changes.append(f"{beat['card']}: shots reordered")
        if not shots:
            errors.append(f"beat {beat['card']} has no shots left; a beat is dropped in the storyboard, not here")
        new_beat = dict(beat)
        new_beat["shots"] = [new for _, new in shots]
        if new_beat["shots"] != beat["shots"]:
            new_beat["beat_seconds"] = round(sum(s["out"] - s["in"] for s in new_beat["shots"]), 1)
        new_beats.append(new_beat)

    new_cut = dict(cut)
    new_cut["beats"] = new_beats
    if changes:
        new_cut["episode_seconds"] = round(sum(s["out"] - s["in"] for b in new_beats for s in b["shots"]), 1)
    return new_cut, changes, errors


def run_selftest():
    fps = 25
    shot_a = {"file": "A.MP4", "in": 0.9, "out": 7.9, "why": "a", "audio": "keep"}
    shot_b = {"file": "B.MP4", "in": 12.4, "out": 18.8, "why": "b", "audio": "duck"}
    shot_c = {"file": "A.MP4", "in": 20.0, "out": 22.0, "why": "c", "audio": "keep"}
    cut = {"episode": "01",
           "beats": [{"card": "e01-1", "shots": [shot_a, shot_b], "beat_seconds": 13.4},
                     {"card": "e01-2", "shots": [shot_c], "beat_seconds": 2}],
           "episode_seconds": 15.4}
    offsets = {"A": 0.0, "B": 11.4}
    clip_to_shot = {"11": [0, 0], "14": [0, 1], "17": [1, 0]}

    commands = build_commands(cut, {"A.mp4": 1, "B.mp4": 2}, offsets, fps, [3840, 2160], "e01")
    assert [c["id"] for c in commands] == ["file.newSequence", "markers.add", "timeline.place",
                                           "timeline.place", "markers.add", "timeline.place"]
    place_b = commands[3]["params"]
    assert place_b["item"] == 2 and place_b["time"] == ticks(7.0), place_b
    assert place_b["sourceIn"] == ticks(1.0) and place_b["duration"] == ticks(6.4), "proxy offset not applied"
    assert commands[4]["params"]["time"] == ticks(13.4), "beat marker off the frame grid"

    def item(clip, name, start, source_in, source_out, speed=1.0):
        return {"clip": clip, "name": name, "start": ticks(start), "sourceIn": ticks(source_in),
                "sourceOut": ticks(source_out), "speed": speed, "reverse": False}

    def timeline(*items):
        return {"video": [{"name": "Video 1", "items": list(items)}, {"name": "Video 2", "items": []}]}

    a, b, c = item(11, "A.mp4", 0, 0.9, 7.9), item(14, "B.mp4", 7, 1.0, 7.4), item(17, "A.mp4", 13.4, 20, 22)

    new_cut, changes, errors = apply_timeline(cut, timeline(a, b, c), clip_to_shot, offsets, fps)
    assert (new_cut, changes, errors) == (cut, [], []), "an untouched timeline must change nothing"

    half_frame_off = item(11, "A.mp4", 0, 0.92, 7.92)
    new_cut, changes, errors = apply_timeline(cut, timeline(half_frame_off, b, c), clip_to_shot, offsets, fps)
    assert new_cut == cut and not changes, "frame-grid rounding read as an edit"

    trimmed = item(14, "B.mp4", 7.2, 1.2, 7.4)          # in-point dragged 5 frames later
    new_cut, changes, errors = apply_timeline(cut, timeline(a, trimmed, c), clip_to_shot, offsets, fps)
    moved = new_cut["beats"][0]["shots"][1]
    assert (moved["in"], moved["out"], moved["why"]) == (12.6, 18.8, "b") and not errors, moved
    assert new_cut["beats"][0]["beat_seconds"] == 13.2 and new_cut["episode_seconds"] == 15.2
    assert new_cut["beats"][1] == cut["beats"][1] and len(changes) == 1

    new_cut, changes, errors = apply_timeline(cut, timeline(a, c), clip_to_shot, offsets, fps)
    assert len(new_cut["beats"][0]["shots"]) == 1 and "removed" in changes[0] and not errors

    swapped = timeline(item(14, "B.mp4", 0, 1.0, 7.4), item(11, "A.mp4", 6.4, 0.9, 7.9), c)
    new_cut, changes, errors = apply_timeline(cut, swapped, clip_to_shot, offsets, fps)
    assert [s["why"] for s in new_cut["beats"][0]["shots"]] == ["b", "a"] and changes == ["e01-1: shots reordered"]

    refused = [timeline(a, b, c, item(99, "A.mp4", 20, 3, 4)),              # split or added clip
               timeline(a, b, item(17, "A.mp4", 13.4, 20, 22, speed=2.0)),  # speed change
               timeline(item(17, "A.mp4", 0, 20, 22), a, b),                # moved across a beat
               timeline(a, b),                                              # emptied beat
               timeline(a, b, item(17, "B.mp4", 13.4, 20, 22))]             # cut list changed since push
    for sequence in refused:
        assert apply_timeline(cut, sequence, clip_to_shot, offsets, fps)[2], f"not refused: {sequence}"
    on_v2 = timeline(a, b)
    on_v2["video"][1]["items"] = [c]
    assert any("Video 2" in e for e in apply_timeline(cut, on_v2, clip_to_shot, offsets, fps)[2])
    print("selftest: all assertions passed")


if A.selftest:
    run_selftest()
    raise SystemExit(0)
if not (A.action and A.episode and A.config):
    AP.error("push|pull, an episode number and --config are required")

CFG = json.load(open(A.config, encoding="utf-8"))
CFGDIR = Path(A.config).resolve().parent
if not CFG.get("proxies"):
    sys.exit(f'{A.config} has no "proxies" key: set it to the make_proxies.py --out dir')
CUTS = (CFGDIR / CFG["cut_lists"]).resolve()
PROXIES = (CFGDIR / CFG["proxies"]).resolve()
FPS = CFG.get("fps", 25)
CANVAS = CFG.get("canvas", [1920, 1080])

CUT_LIST = CUTS / f"e{A.episode}.json"
TIMELINES = CUTS.parent / "timeline"
PROJECT = TIMELINES / f"e{A.episode}.fcproj"
CLIP_MAP = TIMELINES / f"e{A.episode}.map.json"

CLI = A.filmcraft_cli or os.environ.get("FILMCRAFT_CLI") or shutil.which("filmcraft-cli")
if not CLI or not Path(CLI).exists():
    sys.exit("filmcraft-cli not found: pass --filmcraft-cli, set FILMCRAFT_CLI, or put it on PATH. "
             "FilmCraft is optional: without it, edit the in/out values in the cut list.")

RANGES = PROXIES / "_ranges.json"
if not RANGES.exists():
    sys.exit(f"{RANGES} not found: run make_proxies.py first")
OFFSETS = {stem: float(v.get("offset", 0.0)) for stem, v in json.load(open(RANGES, encoding="utf-8")).items()}


def filmcraft(*args, stdin=None):
    """Run filmcraft-cli and return its stdout; any failure ends the run with its message."""
    r = subprocess.run([CLI, "--compact", *map(str, args)], input=stdin, capture_output=True,
                       text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"filmcraft-cli {args[0] if args else ''} failed: {(r.stderr or r.stdout).strip()[-600:]}")
    return r.stdout


def push():
    cut = json.load(open(CUT_LIST, encoding="utf-8"))
    if PROJECT.exists() and not A.force:
        sys.exit(f"{PROJECT} exists; pull it first, or --force to replace it and lose its unpulled edits")
    proxies = []
    for beat in cut["beats"]:
        for shot in beat["shots"]:
            proxy = PROXIES / proxy_name(shot)
            if Path(shot["file"]).stem not in OFFSETS or not proxy.exists():
                sys.exit(f"no proxy for {shot['file']}: run make_proxies.py first")
            if proxy not in proxies:
                proxies.append(proxy)
    TIMELINES.mkdir(parents=True, exist_ok=True)
    PROJECT.unlink(missing_ok=True)

    imported = json.loads(filmcraft("--save-as", PROJECT, "import", *proxies))
    if imported["errors"]:
        sys.exit(f"FilmCraft could not import: {imported['errors']}")
    bin_items = json.loads(filmcraft("--project", PROJECT, "inspect", "project"))["root"]["children"]
    item_ids = {i["name"]: i["item"] for i in bin_items}

    commands = build_commands(cut, item_ids, OFFSETS, FPS, CANVAS, f"e{A.episode}")
    script = "\n".join(json.dumps(c) for c in commands)
    results = filmcraft("--project", PROJECT, "--save", "run", "-", stdin=script)
    failed = [line for line in results.splitlines() if line.strip() and not json.loads(line)["ok"]]
    if failed:
        sys.exit("FilmCraft refused:\n  " + "\n  ".join(failed[:5]))

    # The clip ids come from the timeline itself: V1 in timeline order is the shots in cut order.
    sequence = json.loads(filmcraft("--project", PROJECT, "inspect", "sequence"))
    placed = sorted(sequence["video"][0]["items"], key=lambda i: i["start"])
    shots = [(b, s) for b, beat in enumerate(cut["beats"]) for s in range(len(beat["shots"]))]
    if len(placed) != len(shots):
        sys.exit(f"placed {len(placed)} clips for {len(shots)} shots; {PROJECT} is not usable")
    clip_to_shot = {str(item["clip"]): list(shot) for item, shot in zip(placed, shots)}
    json.dump(clip_to_shot, open(CLIP_MAP, "w", encoding="utf-8"), indent=1)

    print(f"e{A.episode}: {len(shots)} shots, {sequence['durationFrames'] / FPS:.1f} s on V1 -> {PROJECT}")
    if A.open:
        app = Path(CLI).with_name("filmcraft.exe" if os.name == "nt" else "filmcraft")
        subprocess.Popen([str(app), str(PROJECT)])
    print(f"Trim in FilmCraft, save (Ctrl+S), then: review_timeline.py --config {A.config} pull {A.episode}")


def pull():
    cut = json.load(open(CUT_LIST, encoding="utf-8"))
    if not PROJECT.exists() or not CLIP_MAP.exists():
        sys.exit(f"{PROJECT} not found: push {A.episode} first")
    clip_to_shot = json.load(open(CLIP_MAP, encoding="utf-8"))
    sequence = json.loads(filmcraft("--project", PROJECT, "inspect", "sequence"))
    new_cut, changes, errors = apply_timeline(cut, sequence, clip_to_shot, OFFSETS, FPS)

    for line in changes:
        print("  ~", line)
    if errors:
        print("REFUSED, nothing written:")
        for line in errors:
            print("  -", line)
        sys.exit(1)
    if not changes:
        print(f"e{A.episode}: timeline matches the cut list (unsaved edits in FilmCraft are not seen)")
        return
    print(f"e{A.episode}: {len(changes)} changes, {cut.get('episode_seconds')} s -> {new_cut['episode_seconds']} s")
    if not A.write:
        print("dry run: add --write to apply")
        return
    # The backup stays out of <cut_lists>: every tool there globs e*.json as a cut list.
    backup = TIMELINES / f"e{A.episode}.cut-list-before-pull.json"
    shutil.copy2(CUT_LIST, backup)
    json.dump(new_cut, open(CUT_LIST, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"wrote {CUT_LIST} (previous version: {backup}); next: check_cut_list.py, make_proxies.py")


if A.action == "push":
    push()
else:
    pull()
