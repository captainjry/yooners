#!/bin/sh
# Step 11: QC one finished file and write the evidence beside it.
# Checks geometry, duration, black frames, freezes, silence and loudness, plus a contact sheet.
#
#   sh qc_episode.sh <final>.mp4 [--expect-duration 405.8] [--expect-size 3840x2160] [--qc <dir>]
#
# Run this only while nothing is rendering: concurrent ffmpeg has stalled captures.
# The contact sheet is the check that catches what the filters miss - LOOK at the PNG afterwards.
set -e
F="$1"; shift || true
[ -s "$F" ] || { echo "usage: sh qc_episode.sh <file.mp4> [--expect-duration S] [--expect-size WxH]"; exit 1; }
DUR_EXP=""; SIZE_EXP=""; QC="$(dirname "$F")/qc"
while [ $# -gt 0 ]; do
  case "$1" in
    --expect-duration) DUR_EXP="$2"; shift 2 ;;
    --expect-size) SIZE_EXP="$2"; shift 2 ;;
    --qc) QC="$2"; shift 2 ;;
    *) shift ;;
  esac
done
mkdir -p "$QC"
B=$(basename "$F" .mp4)
REPORT="$QC/$B-qc.txt"

{
  echo "=== ffprobe geometry/duration ==="
  ffprobe -v error -show_entries format=duration:stream=codec_name,width,height -of csv=p=0 "$F"
  [ -n "$SIZE_EXP" ] && echo "expected size: $SIZE_EXP"
  [ -n "$DUR_EXP" ] && echo "expected duration: ${DUR_EXP}s"

  echo "=== blackdetect (expect 0) ==="
  ffmpeg -hide_banner -nostdin -i "$F" -vf blackdetect=d=0.4:pic_th=0.98 -an -f null - 2>&1 \
    | grep -c black_start || true

  echo "=== freezedetect (expect one hit, at the end card) ==="
  ffmpeg -hide_banner -nostdin -i "$F" -vf freezedetect=n=0.001:d=2 -an -f null - 2>&1 \
    | grep freeze_start || echo "none"

  echo "=== silencedetect (expect none, or the end card only) ==="
  ffmpeg -hide_banner -nostdin -i "$F" -af silencedetect=n=-50dB:d=3 -vn -f null - 2>&1 \
    | grep silence_start || echo "none"

  echo "=== ebur128 loudness (target ~ -20 LUFS, true peak < -1 dBFS) ==="
  ffmpeg -hide_banner -nostdin -i "$F" -af ebur128=peak=true -vn -f null - 2>&1 \
    | grep -E '^\s+(I|Peak):' | tail -2
} 2>&1 | tee "$REPORT"

# one-pass contact sheet: 1 frame per 20 s, 7x3 grid
SHEET="$QC/$B-sheet.png"
ffmpeg -hide_banner -nostdin -y -i "$F" -vf "fps=1/20,scale=320:-1,tile=7x3" -frames:v 1 "$SHEET" 2>/dev/null
echo "contact sheet: $SHEET" | tee -a "$REPORT"
echo "NOW LOOK AT THE SHEET: real footage in every tile, upright, stamps upright." | tee -a "$REPORT"
echo "(trailing empty tiles are grid padding when duration/20 < 21)"
echo "report: $REPORT"
