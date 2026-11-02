#!/usr/bin/env python3
"""houseread.py -- READ THE HOUSE: per bar, the main colour the props around each flood actually show.

The owner, 2026-10-06: the house itself has to be read; a solid wall wash that does not match the sequence
at all is bad. This reads the SAVED render (never xLights), every --step, and for each member of the flood
group takes the props whose nodes lie within --radius (world X) of it. Per frame each prop counts ONCE,
weighted by how much of it is lit and how bright, so a matrix that holds most of the channels is one prop,
not the picture (never tune against a global mean). Lit colours fall into hue buckets; per bar the winning
bucket's mean colour is "what the house shows there", with its share of the lit weight and the region's lit
level.

    uv run --no-project --with pillow --with lxml --with zstandard --with numpy --python 3.12 python houseread.py \
        <song>.fseq --xsq <song>.xsq --group <flood group> [--show <show folder>] [--exclude "<sign>,<group>"] \
        [--bars Bars] [--radius 260] [--step 0.1] [--lit 40] [--json out.json]
    Follow named groups instead of flood regions (first lit group gives the colour):
        ... --follow "Garage Doors,Windows,Peaks" [--min-level 0.03] [--series picks.json]

Reads: the `.fseq` (sparse ranges at absolute channels), the show's `xlights_rgbeffects.xml` (geometry
through housesnap, groups, the flood group's members) and `xlights_networks.xml`, and the `.xsq` for the
timing track named by --bars (its marks are the bar edges). The show folder is `--show`, else the first
folder above the `.fseq` holding `xlights_rgbeffects.xml`. Pillow is not needed for this tool.
Prints: the props in each region, then one row per bar (m:ss) with, per flood or followed group, the
winning bucket, its share and the lit level; with --follow also the per-bar pick (source group, colour,
level, rgb). --json writes the per-bar table; --series writes the per-FRAME pick instead and stops, printing
the run-length histogram of colour changes.
"""
from pathlib import Path
import argparse, colorsys, json, math, sys
from lxml import etree as E
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fseq import FSEQ
from housesnap import geometry, bases_from_network, start_channel
from layout import show_folder_of
from tc import mmss

BUCKETS = ["white", "red", "orange", "yellow", "green", "cyan", "blue", "purple", "magenta"]


def bucket(rgb):
    r, g, b = (v / 255 for v in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.25: return "white"
    d = h * 360
    for lo, hi, n in ((15, 40, "orange"), (40, 70, "yellow"), (70, 160, "green"), (160, 200, "cyan"),
                      (200, 255, "blue"), (255, 290, "purple"), (290, 345, "magenta")):
        if lo <= d < hi: return n
    return "red"


def short_names(names):
    """Column headers: when every name starts with the same word (e.g. 'Flood Left', 'Flood Right') that
    word is dropped; then the first 12 characters."""
    words = [n.split(" ", 1) for n in names]
    if len(names) > 1 and all(len(w) == 2 for w in words) and len({w[0] for w in words}) == 1:
        return {n: w[1][:12] for n, w in zip(names, words)}
    return {n: n[:12] for n in names}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fseq"); ap.add_argument("--xsq", required=True)
    ap.add_argument("--show"); ap.add_argument("--radius", type=float, default=260)
    ap.add_argument("--step", type=float, default=0.1); ap.add_argument("--lit", type=int, default=40)
    ap.add_argument("--group", required=True, help="the model GROUP holding the floods; one column per member")
    ap.add_argument("--bars", default="Bars", help="timing track whose marks are the bar edges")
    ap.add_argument("--exclude", default="", help="comma-separated props that never carry the song's colour (a tune-to sign, say)")
    ap.add_argument("--follow", default="", help="priority list of GROUPS, e.g. 'Garage Doors,Windows,Peaks' (the owner, 2026-10-06: "
                    "garage colours first, then windows, then peaks): per bar the first lit group gives the colour")
    ap.add_argument("--min-level", type=float, default=0.03, help="a source group counts as lit at or above this level")
    ap.add_argument("--series", help="with --follow: write the per-FRAME pick (every --step) to this JSON and stop; the "
                    "colour changes where the house changes them, not on a bar grid (the owner, 2026-10-06: colour changes were still being missed)")
    ap.add_argument("--json")
    a = ap.parse_args()
    path = Path(a.fseq).expanduser().resolve(); show = Path(a.show).expanduser() if a.show else show_folder_of(path)
    lay = E.parse(str(show / "xlights_rgbeffects.xml")).getroot()
    floods = next(g for g in lay.iter("modelGroup") if g.get("name") == a.group).get("models").split(",")
    bases = bases_from_network(show); fs = FSEQ(path)
    stored = fs.ranges; excl = {x for x in a.exclude.split(",") if x} | set(floods)
    props = []
    for m in lay.find("models"):
        n = m.get("name")
        if n in excl or m.get("StringType") not in ("RGB Nodes", "RGBW Nodes"): continue
        try: pos, _ = geometry(m)
        except ValueError: continue
        base = start_channel(m, bases); stride = 4 if m.get("StringType") == "RGBW Nodes" else 3
        end = base + max(pos) * stride - 1
        if not any(s <= base - 1 and end <= s + c for s, c in stored): continue   # not in this song
        props.append((n, pos, base, stride))
    fx = {f: float(next(m for m in lay.find("models") if m.get("name") == f).get("WorldPosX")) for f in floods}
    region = {f: [(n, [k for k, (x, y) in pos.items() if abs(x - fx[f]) <= a.radius], base, stride)
                  for n, pos, base, stride in props] for f in floods}
    region = {f: [p for p in ps if p[1]] for f, ps in region.items()}
    groups = {g.get("name"): [x.strip() for x in (g.get("models") or "").split(",") if x.strip()] for g in lay.iter("modelGroup")}
    def leaves(n, seen=()):
        return [y for x in groups[n] if x not in seen for y in (leaves(x, seen + (x,)) if x in groups else [x])] if n in groups else [n]
    follow = [x.strip() for x in a.follow.split(",") if x.strip()]
    if follow:
        bynm = {n: (n, list(pos), base, stride) for n, pos, base, stride in props}
        region = {g: [bynm[m] for m in leaves(g) if m in bynm] for g in follow}
        floods = follow
        for g in follow: print(f"source {g:14s}: {', '.join(p[0] for p in region[g])}")
    else:
        for f in floods: print(f"{f:22s} X {fx[f]:6.0f}: {', '.join(p[0] for p in region[f])}")

    if a.series:
        if not follow: raise SystemExit("--series needs --follow")
        step = max(fs.step, int(a.step * 1000)); ser = []
        for t in range(0, fs.frames * fs.step, step):
            fr = fs.frame(t // fs.step); pick = None
            for g in follow:
                acc = {k: [0.0, [0.0, 0.0, 0.0]] for k in BUCKETS}; lvl = 0.0
                for n, nodes, base, stride in region[g]:
                    lit = [fr[base - 1 + (k - 1) * stride: base - 1 + (k - 1) * stride + 3] for k in nodes]
                    lit = [rgb for rgb in lit if max(rgb) >= a.lit]
                    if not lit: continue
                    frac = len(lit) / len(nodes)
                    for rgb in lit:
                        w = frac * max(rgb) / 255 / len(lit); c = acc[bucket(rgb)]; c[0] += w
                        for i in range(3): c[1][i] += w * rgb[i]
                    lvl += frac * (sum(max(x) for x in lit) / len(lit) / 255) / len(region[g])
                if lvl >= a.min_level:
                    k, (w, sm) = max(acc.items(), key=lambda kv: kv[1][0])
                    pick = [t, g, k, [round(x / w) for x in sm], round(lvl, 3)]; break
            ser.append(pick or [t, None, "dark", [0, 0, 0], 0.0])
        json.dump({"follow": follow, "step_ms": step, "frames": ser}, open(a.series, "w"))
        from collections import Counter
        runs = [1]
        for x, y in zip(ser, ser[1:]):
            if x[2] == y[2]: runs[-1] += 1
            else: runs.append(1)
        print(f"{len(ser)} frames at {step} ms; {len(runs)} colour runs; run length ms: "
              + ", ".join(f"<{lim}: {sum(1 for r in runs if r * step < lim)}" for lim in (100, 200, 300, 400, 800)))
        return
    root = E.parse(str(Path(a.xsq).expanduser())).getroot()
    tr = next(e for e in root.find("ElementEffects").findall("Element") if e.get("name") == a.bars)
    bars = [int(e.get("startTime")) for e in tr.find("EffectLayer").findall("Effect")]
    song_ms = fs.frames * fs.step
    edges = [0] + bars + [song_ms] if bars[0] > 0 else bars + [song_ms]
    out = []
    step = max(fs.step, int(a.step * 1000))
    for b0, b1 in zip(edges, edges[1:]):
        acc = {f: {k: [0.0, [0.0, 0.0, 0.0]] for k in BUCKETS} for f in floods}
        lvl = {f: 0.0 for f in floods}; nfr = 0
        for t in range(b0, b1, step):
            fr = fs.frame(t // fs.step); nfr += 1
            for f in floods:
                for n, nodes, base, stride in region[f]:
                    lit = []
                    for k in nodes:
                        o = base - 1 + (k - 1) * stride; rgb = fr[o:o + 3]
                        if max(rgb) >= a.lit: lit.append(rgb)
                    if not lit: continue
                    frac = len(lit) / len(nodes)
                    for rgb in lit:
                        w = frac * max(rgb) / 255 / len(lit)
                        c = acc[f][bucket(rgb)]; c[0] += w
                        for i in range(3): c[1][i] += w * rgb[i]
                    lvl[f] += frac * (sum(max(x) for x in lit) / len(lit) / 255) / len(region[f])
        row = {"t0": b0, "t1": b1}
        for f in floods:
            tot = sum(v[0] for v in acc[f].values())
            if tot <= 0: row[f] = {"bucket": "dark", "share": 0, "rgb": [0, 0, 0], "level": 0}; continue
            k, (w, s) = max(acc[f].items(), key=lambda kv: kv[1][0])
            row[f] = {"bucket": k, "share": round(w / tot, 2), "rgb": [round(x / w) for x in s],
                      "level": round(lvl[f] / max(1, nfr), 3),
                      "second": sorted(((v[0] / tot, kk) for kk, v in acc[f].items() if kk != k), reverse=True)[0][1]}
        out.append(row)
    short = short_names(floods)
    print(f"\n{'bar':>7s} " + " ".join(f"{short[f]:>22s}" for f in floods))
    for r in out:
        print(f"{mmss(r['t0']/1000):>7s} " + " ".join(
            f"{r[f]['bucket']:>8s} {r[f]['share']:>4.0%} L{r[f]['level']:.2f}  " for f in floods))
    if follow:
        for r in out:
            src = next((g for g in follow if r[g]["level"] >= a.min_level), None)
            r["pick"] = {"source": src, **(r[src] if src else {"bucket": "dark", "rgb": [0, 0, 0], "level": 0})}
        print(f"\n{'bar':>7s}  pick (source, colour, level)")
        for r in out:
            p = r["pick"]; print(f"{mmss(r['t0']/1000):>7s}  {str(p['source']):14s} {p['bucket']:>8s} {p.get('share', 0):>4.0%} L{p['level']:.2f}  rgb {p['rgb']}")
    if a.json: json.dump({"floods": floods, "follow": follow, "radius": a.radius, "bars": out}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
