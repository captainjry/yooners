"""Download the two OFL fonts the series design uses, plus their OFL.txt licences.

  python fetch_fonts.py [--out <project>/assets/fonts]

Skips any file that already exists. Uses urllib only (no requests dependency).
"""
import argparse, urllib.request
from pathlib import Path

FILES = {
    "Montserrat[wght].ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "IBMPlexMono-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/IBMPlexMono-Regular.ttf",
    "OFL-Montserrat.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/OFL.txt",
    "OFL-IBMPlexMono.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/OFL.txt",
}

AP = argparse.ArgumentParser()
AP.add_argument("--out", default="assets/fonts")
A = AP.parse_args()

OUT = Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)

for name, url in FILES.items():
    dst = OUT / name
    if dst.exists():
        print("skip (exists):", dst)
        continue
    urllib.request.urlretrieve(url, dst)
    print("fetched:", dst)
