#!/usr/bin/env python3
"""litaudit.py -- how much of the song each PROP is lit in the saved render, and which rows reach it.

The owner found four dead props by eye on one song (2026-10-06: the floods, a sign's digits, a prop lit only by a
whole-house bed, a flying prop at 2 %): decode every model's lit share after the render, BEFORE the owner looks. A
prop lit under 5 % (or lit only by a whole-house group bed) is a suspect; the fix is the song's own idiom, never
another song's method.

For every model in the show layout (submodels and groups excluded): the share of frames (sampled every --step ms) in
which any of its nodes is lit above --thr, read at its absolute channels (`housesnap.start_channel`, `snap.node_count`;
4 bytes per node on an RGBW string), and the sequence rows that reach it (the model's own row, or a group whose
expansion names it). A model the song never stores reads dark (an FSEQ is sparse). Sorted darkest first.

    litaudit.py <song>.fseq [--show <show folder>] [--step 100] [--thr 20] [--under 100]

Reads: the `.fseq`, the show's `xlights_rgbeffects.xml` + `xlights_networks.xml` (the show folder is `--show`,
else the first folder above the `.fseq` holding `xlights_rgbeffects.xml`) and, when it exists beside the `.fseq`,
the `.xsq` (for the rows). Pillow is not needed. Prints: one header line (frames, length as m:ss, sample step),
then one line per prop under --under %: lit share, name, the first four rows reaching it (or NONE).
Written 2026-10-24.
"""
import argparse, sys
from pathlib import Path
import numpy as np
from lxml import etree
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fseq, housesnap as hs
from layout import show_folder_of
from tc import mmss


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fseq"); ap.add_argument("--show", help="show folder (default: the first folder above the .fseq holding xlights_rgbeffects.xml)")
    ap.add_argument("--step", type=int, default=100); ap.add_argument("--thr", type=int, default=20)
    ap.add_argument("--under", type=float, default=100.0, help="list only props lit under this %%")
    a = ap.parse_args()
    fsq = Path(a.fseq).expanduser(); show = Path(a.show).expanduser() if a.show else show_folder_of(fsq.resolve())
    lay = etree.parse(str(show / "xlights_rgbeffects.xml")).getroot()
    bases = hs.bases_from_network(show)
    groups = {g.get("name"): [m.strip() for m in (g.get("models") or "").split(",") if m.strip()] for g in lay.iter("modelGroup")}
    models = {}
    for m in lay.find("models").findall("model"):
        try: st, n = hs.start_channel(m, bases), hs.node_count(m)
        except Exception: continue
        k = 4 if "RGBW" in (m.get("StringType") or "") else 3
        models[m.get("name")] = (st - 1, n * k)
    xsq = fsq.with_suffix(".xsq"); rows = {}
    if xsq.exists():
        def leaves(n, seen=()):
            if n in groups: return {x for g in groups[n] if g not in seen for x in leaves(g, seen + (n,))}
            return {n.split("/")[0]}
        for el in etree.parse(str(xsq)).getroot().find("ElementEffects"):
            if el.get("type") != "model" or not any(True for _ in el.iter("Effect")): continue
            for leaf in leaves(el.get("name")): rows.setdefault(leaf, []).append(el.get("name"))
    F = fseq.FSEQ(str(fsq)); step = getattr(F, "step", None) or 25
    every = max(1, a.step // step); idx = range(0, F.frames, every)
    lit = {n: 0 for n in models}
    for fi in idx:
        fr = np.frombuffer(bytes(F.frame(fi)), np.uint8)
        for n, (b, c) in models.items():
            if b + c <= len(fr) and fr[b:b + c].max() > a.thr: lit[n] += 1
    tot = len(idx)
    print(f"{fsq.name}: {F.frames} frames ({mmss(F.frames * step / 1000)}), sampled every {every * step} ms; props lit under {a.under:g} %:")
    for n in sorted(models, key=lambda n: lit[n]):
        pct = 100 * lit[n] / tot
        if pct >= a.under: continue
        r = rows.get(n, [])
        print(f"  {pct:5.1f} %  {n[:40]:40} rows: " + (", ".join(sorted(r)[:4]) + (f" +{len(r) - 4}" if len(r) > 4 else "") if r else "NONE"))


if __name__ == "__main__":
    main()
