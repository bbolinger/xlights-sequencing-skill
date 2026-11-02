#!/usr/bin/env python
"""radius.py -- which WAY is a whole-house effect travelling? Radial centroid of lit energy over time.

Brightness cannot answer this. One song's opening measured a correct envelope (rise, fall to zero,
flash, rise) while the motion was still outward the whole time, because the shader's own flow
dominated and nothing measured direction. The owner, twice: the effect is still going the wrong
direction.

This weights each model by how much of it is lit and by its distance from the display centre
(WorldPosX/Y from the layout), and reports the mean radius per frame. Mean radius FALLING =
energy collecting toward the middle (an inhale). RISING = spreading outward (an exhale).

    radius.py <song.fseq> <start s> <end s> [--step 0.2] [--thr 28] [--skip "Matrix,Sign"]

Reads: the saved `.fseq` and the show above it (`xlights_rgbeffects.xml` + `xlights_networks.xml`
through `layout.Layout`: absolute start channel and stride per model; a model's node count is
bounded by the NEXT model's start channel). --skip names models to leave out of the centroid, such
as a matrix that holds most of the channels, or a sign that stays lit all song. Pillow is not needed.
Prints: the display centre and the largest prop radius, then one row per --step: time (seconds),
lit share of all nodes above --thr, mean radius as a fraction of the largest, and the direction
against the previous row (INWARD / outward / =, or dark).
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tc import mmss
from fseq import FSEQ, rgb
from layout import Layout, show_folder_of
from lxml import etree

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("fseq"); ap.add_argument("start", type=float); ap.add_argument("end", type=float)
ap.add_argument("--step", type=float, default=0.2)
ap.add_argument("--thr", type=int, default=28)
ap.add_argument("--skip", default="", help="comma-separated models left out of the centroid (a matrix, a sign)")
a = ap.parse_args()

f = Path(a.fseq).resolve(); show = show_folder_of(f)
L = Layout(show); F = FSEQ(str(f))
r = etree.parse(str(show / "xlights_rgbeffects.xml")).getroot()
pos = {m.get("name"): (float(m.get("WorldPosX") or 0), float(m.get("WorldPosY") or 0))
       for m in r.iter("model")}
st = sorted(L.start.items(), key=lambda x: x[1])
SKIP = {x.strip() for x in a.skip.split(",") if x.strip()}
models = [(m, c) for m, c in st if m not in SKIP and m in pos]
def span(m, b):
    n = min((c for _, c in st if c > b), default=b + 3)
    return (n - b) // L.stride[m]
# display centre = node-weighted centroid of the whole layout
tw = sum(span(m, c) for m, c in models)
cx = sum(pos[m][0] * span(m, c) for m, c in models) / tw
cy = sum(pos[m][1] * span(m, c) for m, c in models) / tw
rad = {m: ((pos[m][0] - cx) ** 2 + (pos[m][1] - cy) ** 2) ** 0.5 for m, _ in models}
rmax = max(rad.values()) or 1.0

print(f"display centre ({cx:.0f}, {cy:.0f})   max prop radius {rmax:.0f}")
print(f"{'t':>7} {'lit%':>6} {'meanR':>6}  direction")
prev = None
t = a.start
while t <= a.end + 1e-9:
    fr = F.frame(int(round(t / 0.025)))
    wsum = 0.0; rsum = 0.0; lit = 0
    for m, c in models:
        n = span(m, c); k = 0
        for i in range(1, n + 1):
            if max(rgb(fr, c, i)) > a.thr: k += 1
        if k:
            lit += k; wsum += k; rsum += rad[m] * k
    mr = (rsum / wsum / rmax) if wsum else float("nan")
    if wsum:
        arrow = "" if prev is None else ("  <-- INWARD" if mr < prev - 0.004
                                         else ("  --> outward" if mr > prev + 0.004 else "  ="))
        print(f"{mmss(t):>7} {100*lit/tw:5.1f}% {mr:6.3f}{arrow}")
        prev = mr
    else:
        print(f"{mmss(t):>7} {0.0:5.1f}% {'   -':>6}  (dark)")
        prev = None
    t += a.step
