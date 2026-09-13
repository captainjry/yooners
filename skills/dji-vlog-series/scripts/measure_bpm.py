"""Step 13 helper: measure a music bed's tempo, beat period and 4/4 downbeat phase.

The teaser cut is locked to the music, so the grid is measured rather than guessed
(the social-reel skill, reference/audio-modes.md).

  python measure_bpm.py --audio assets/bgm/carefree.m4a --seconds 90

What it does, in order:

1. Decodes the first --seconds of the bed to mono 22.05 kHz with ffmpeg (audio only, -vn, so a
   video container costs nothing). Writes to a temp WAV and deletes it afterwards unless --keep-wav.
2. `librosa.onset.onset_strength` -> `librosa.beat.beat_track` for a first tempo estimate.
3. Least-squares fit of beat index against beat time -> a period, i.e. the tempo the track was
   *produced* at rather than the one that was detected. If that period is within --snap-tolerance
   of a round BPM, the round number is reported as the grid to use: forcing it reproduces the
   detected beats with the same residual, and a round tempo keeps the bar math exact.
4. Downbeat phase: grid beats are grouped by index mod 4 and each group scored on sub-180 Hz
   energy (a 4/4 kick lands on beat 1). The winning group is the downbeat; its phase is reported
   as D(k) = phase + bar * k. The full per-group bass and onset profile is printed so the expected
   strong -> weakest shape can be eyeballed before the grid is trusted.

Every picture cut in the teaser then sits on D(k) snapped to the nearest frame line.
Read-only on the bed.
"""
import argparse, os, subprocess, sys, tempfile

AP = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
AP.add_argument("--audio", required=True, help="music bed (any container ffmpeg reads)")
AP.add_argument("--seconds", type=float, default=90.0, help="how much of the head to analyse")
AP.add_argument("--sr", type=int, default=22050)
AP.add_argument("--beats-per-bar", type=int, default=4)
AP.add_argument("--bass-hz", type=float, default=180.0, help="downbeat scoring band, 0..bass-hz")
AP.add_argument("--snap-tolerance", type=float, default=0.05,
                help="report a round BPM if the fitted tempo is within this many BPM of one")
AP.add_argument("--fps", type=float, default=25.0, help="frame grid the cuts will be snapped to")
AP.add_argument("--ffmpeg", default="ffmpeg")
AP.add_argument("--keep-wav", default="", help="write the decoded WAV here instead of a temp file")
A = AP.parse_args()

import numpy as np
import librosa

wav = A.keep_wav or os.path.join(tempfile.gettempdir(), "measure_bpm_%d.wav" % os.getpid())
cmd = [A.ffmpeg, "-v", "error", "-y", "-t", str(A.seconds), "-i", A.audio,
       "-vn", "-ac", "1", "-ar", str(A.sr), wav]
subprocess.run(cmd, check=True)
try:
    y, sr = librosa.load(wav, sr=A.sr, mono=True)
finally:
    if not A.keep_wav:
        try:
            os.remove(wav)
        except OSError:
            pass

env = librosa.onset.onset_strength(y=y, sr=sr)
tempo, beats = librosa.beat.beat_track(onset_envelope=env, sr=sr)
tempo = float(np.atleast_1d(tempo)[0])
bt = librosa.frames_to_time(beats, sr=sr)
if len(bt) < 8:
    sys.exit("only %d beats detected in %.0f s - analyse a longer window" % (len(bt), A.seconds))

# --- least-squares fit of beat index vs beat time -------------------------------------------
idx = np.arange(len(bt), dtype=float)
period, phase0 = np.polyfit(idx, bt, 1)
resid = float(np.sqrt(np.mean((phase0 + period * idx - bt) ** 2)))
fit_bpm = 60.0 / period

grid_bpm, grid_period, forced_resid = fit_bpm, period, resid
rounded = round(fit_bpm)
if abs(fit_bpm - rounded) <= A.snap_tolerance:
    grid_bpm = float(rounded)
    grid_period = 60.0 / grid_bpm
    ph = float(np.mean(bt - grid_period * idx))
    forced_resid = float(np.sqrt(np.mean((ph + grid_period * idx - bt) ** 2)))
    phase0 = ph

bar = grid_period * A.beats_per_bar

# --- downbeat phase: group grid beats by index mod N, score sub-bass-hz energy ---------------
n_grid = int((len(y) / sr - phase0) / grid_period)
gt = phase0 + grid_period * np.arange(max(n_grid, 0))
gt = gt[(gt >= 0) & (gt + 0.12 < len(y) / sr)]

S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
band = freqs <= A.bass_hz
bass = S[band].sum(axis=0)
bass_t = librosa.frames_to_time(np.arange(bass.shape[0]), sr=sr, hop_length=512)
env_t = librosa.frames_to_time(np.arange(env.shape[0]), sr=sr, hop_length=512)


def _score(series, series_t, times, window=0.09):
    out = []
    for t in times:
        m = (series_t >= t - window) & (series_t <= t + window)
        out.append(float(series[m].max()) if m.any() else 0.0)
    return np.array(out)


bass_at = _score(bass, bass_t, gt)
onset_at = _score(env, env_t, gt)
groups = np.arange(len(gt)) % A.beats_per_bar
prof_bass = [float(bass_at[groups == k].mean()) for k in range(A.beats_per_bar)]
prof_onset = [float(onset_at[groups == k].mean()) for k in range(A.beats_per_bar)]
win = int(np.argmax(prof_bass))
downbeat_phase = phase0 + grid_period * win
while downbeat_phase - bar >= 0:
    downbeat_phase -= bar

frame = round(downbeat_phase * A.fps) / A.fps

print("audio                 %s (first %.0f s, mono %d Hz)" % (A.audio, A.seconds, sr))
print("beats detected        %d" % len(bt))
print("beat_track tempo      %.3f BPM" % tempo)
print("least-squares fit     period %.6f s = %.3f BPM (rms %.4f s)" % (period, fit_bpm, resid))
if grid_bpm != fit_bpm:
    print("grid (snapped)        %.3f BPM -> period %.6f s (rms %.4f s)"
          % (grid_bpm, grid_period, forced_resid))
print("BPM                   %.3f" % grid_bpm)
print("period (beat)         %.6f s" % grid_period)
print("bar (%d/4)             %.6f s" % (A.beats_per_bar, bar))
print("group profile         bass  %s" % "  ".join("k=%d %.1f" % (k, v) for k, v in enumerate(prof_bass)))
print("                      onset %s" % "  ".join("k=%d %.2f" % (k, v) for k, v in enumerate(prof_onset)))
print("downbeat group        k=%d" % win)
print("downbeat phase        %.4f s   D(k) = %.4f + %.4f k" % (downbeat_phase, downbeat_phase, bar))
print("phase on %g fps grid   %.4f s (%d frames)" % (A.fps, frame, round(frame * A.fps)))
