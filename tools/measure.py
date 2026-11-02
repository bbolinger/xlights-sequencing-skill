#!/usr/bin/env python
"""Measure a .xsq window against the preset targets in CLAUDE.md.

Reports the dials the owner judges by: effects/sec, median duration, %<500ms, %>2s,
onset-lock, elements, max layers, effect mix, and the palette/hue distribution per
section -- so a red effect in a green section is visible as a number, not a guess.

    measure.py <song.xsq> <from seconds> <to seconds> [<song folder>] [<show folder>]

The song folder holds `analysis/` (beats.json required; sections.json, scene_colors.json
optional) and defaults to the .xsq's own folder; the show folder holds xlights_rgbeffects.xml
and defaults to the first folder above the .xsq that has one.
"""
import sys, json, re, collections, colorsys
from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent))
from tc import mmss, mmss_ms, dur   # mm:ss, never raw seconds
from pathlib import Path
from lxml import etree

IDIOM = {"Flying Bat with Upper Wings", "Flying Bat Lower Wings", "tombstone eyes", "Bat"}
# The flap addresses the bat's own SUBMODELS -- `Bat Flying(Salmon)/Wings Up` and `/Wings Down`
# alternating one state per beat, body and eyes held under them (rules.md#bat). Only the two
# stock GROUPS were named here, so doing it the right way made the dials read like flicker:
# Day-O's Band In went from a 775ms median and 43% under 500ms to 400ms and 55% purely because
# the bat started flapping properly. A wing state is a micro-effect whichever element carries
# it. 2026-09-19 #dayo-bat

def is_idiom(el):
    """Micro-effects that are short or fragmented on purpose and must not skew the dials:
    wing-beats, eye-flashes, and the held eye beds, which are one continuous look chopped
    into segments so the flashes above them still read (see tools/eyes.py)."""
    model, _, sub = el.partition("/")
    return (model in IDIOM or model.startswith("Bat Flying")
            or sub.lower().endswith("eyes") or sub.lower().startswith("wings")
            # A spinner arm is a MECHANISM, not an event: spinner.py steps 24 spiral arms
            # round the disc at 2 per beat, so a rotation is ~60 micro-effects that mean one
            # gesture. Counting them as events makes a spinning prop read as flicker in the
            # dials, exactly as the bat's wings did. 2026-09-19 #spinner
            or sub.startswith(("Hook ", "Spoke ", "Torch ")))

def hue(h):
    r,g,b = (int(h[i:i+2],16)/255 for i in (1,3,5))
    H,S,V = colorsys.rgb_to_hsv(r,g,b)
    return H*360, S, V

def load(path):
    t = etree.parse(str(path)); r = t.getroot()
    pals = [(p.text or "") for p in r.iter("ColorPalette")]
    db   = [(e.text or "") for e in r.find("EffectDB")] if r.find("EffectDB") is not None else []
    out = []
    for el in r.find("ElementEffects").iter("Element"):
        if el.get("type") != "model": continue
        name = el.get("name")
        n = {}
        for lay in el.iter():
            if lay.tag == "EffectLayer": sub = name
            elif lay.tag == "SubModelEffectLayer": sub = f"{name}/{lay.get('name')}"
            else: continue
            ln = n.get(sub, 0); n[sub] = ln + 1
            for e in lay.findall("Effect"):
                pi, ri = e.get("palette"), e.get("ref")
                out.append(dict(el=sub, layer=ln, name=e.get("name"),
                                s=int(e.get("startTime")), e=int(e.get("endTime")),
                                pal=pals[int(pi)] if pi and int(pi) < len(pals) else "",
                                cfg=db[int(ri)] if ri and int(ri) < len(db) else ""))
    return out

def colors_of(p):
    act = set(re.findall(r"C_CHECKBOX_Palette(\d)=1", p))
    cols = dict(re.findall(r"C_BUTTON_Palette(\d)=(#[0-9A-Fa-f]{6})", p))
    return [cols[a].upper() for a in sorted(act) if a in cols]

def main():
    xsq, a, b = Path(sys.argv[1]), float(sys.argv[2])*1000, float(sys.argv[3])*1000
    an = Path(sys.argv[4])/"analysis" if len(sys.argv) > 4 else xsq.parent/"analysis"
    if not an.exists(): an = xsq.parent.parent/"analysis"
    eff = [e for e in load(xsq) if e["s"] < b and e["e"] > a]
    if not eff: print("no effects in window"); return
    beats = json.load(open(an/"beats.json"))
    onsets = [x*1000 for x in beats["onset_times"]]
    secs = json.load(open(an/"sections.json"))["sections"] if (an/"sections.json").exists() else []
    scene = {s["n"]: s for s in json.load(open(an/"scene_colors.json"))["sections"]} if (an/"scene_colors.json").exists() else {}

    real = [e for e in eff if not is_idiom(e["el"])]
    durs = sorted(e["e"]-e["s"] for e in real)
    med = durs[len(durs)//2]
    lock = sum(1 for e in real if onsets and min(abs(o-e["s"]) for o in onsets) < 100)/len(real)
    print(f"=== {xsq.name}  {mmss_ms(a,0)}-{mmss_ms(b,0)} ===")
    print(f"effects           {len(eff)}  ({len(real)} excl. idiom micro)")
    # BOTH numbers, because the other dials are computed on `real`: a prop with a mechanism on
    # it (a flapping bat, a spinning disc) can carry hundreds of micro-effects that mean one
    # gesture, and quoting only the raw rate makes a correct section read as 29 eff/s flicker.
    print(f"effects/sec       {len(real)/((b-a)/1000):.1f}  (excl. idiom micro; "
          f"{len(eff)/((b-a)/1000):.1f} raw)")
    print(f"median duration   {med}ms      (nightmare target ~1450ms)")
    print(f"% under 500ms     {100*sum(1 for d in durs if d<500)/len(durs):.0f}%   (target ~12%)")
    print(f"% over 2s         {100*sum(1 for d in durs if d>2000)/len(durs):.0f}%   (target ~40%)")
    print(f"onset-locked      {100*lock:.0f}%   (target ~68%)")
    print(f"elements          {len({e['el'] for e in eff})}   (target ~27)")
    print(f"max layer         {max(e['layer'] for e in eff)}   (target ~16)")
    print(f"effect types      {len({e['name'] for e in eff})}   (target 10+)")
    c = collections.Counter(e["name"] for e in eff)
    top = c.most_common(1)[0]
    print(f"mix               " + ", ".join(f"{k} {v} ({100*v/len(eff):.0f}%)" for k,v in c.most_common(10)))
    print(f"top-type share    {100*top[1]/len(eff):.0f}%   (monoculture if >50%)")

    # --- colour vs scene, per section: the bug-1 detector
    print("\n--- colour vs scene ---")
    for s in secs:
        ss, se = s["start"]*1000, s["end"]*1000
        if se <= a or ss >= b: continue
        win = [e for e in eff if e["s"] < min(se,b) and e["e"] > max(ss,a)]
        if not win: continue
        want = [c["hue"] for c in scene.get(s["n"],{}).get("colors",[])]
        off = collections.Counter()
        tot = 0
        for e in win:
            # Eyes are deliberately hue-fixed red (the owner, 2026-09-04) -- a constant across
            # every section, the same exemption white already gets on the line below.
            # Auditing them against the scene reports the decision back as an error.
            if is_idiom(e["el"]): continue
            for col in colors_of(e["pal"]):
                H,S,V = hue(col)
                if S < 0.15 or V < 0.10: continue      # white/black are neutral, always allowed
                tot += 1
                if want and min(min(abs(H-w)%360, 360-abs(H-w)%360) for w in want) > 60:
                    off[col] += 1
        pct = 100*sum(off.values())/tot if tot else 0
        print(f"  {s['name']:<26} scene hues {want}  off-scene {sum(off.values())}/{tot} ({pct:.0f}%)  {dict(off.most_common(4))}")

    # --- coverage: how many onsets get nothing (bug-2 detector)
    print("\n--- onset coverage by strength ---")
    env = sorted(((int(o['t']*1000), o['s']) for o in beats.get("onset_strength", [])), key=lambda x:x[0])
    allss = sorted(s for _,s in env); n=len(allss)
    p50, p75, p90 = allss[n//2], allss[3*n//4], allss[int(n*.9)]
    stems = beats.get("stem_onsets", {})
    drum = {int(x*1000) for x in stems.get("drums", [])}
    starts = sorted(e["s"] for e in eff)
    import bisect
    def covered(t, tol=250):
        i = bisect.bisect_left(starts, t-tol)
        return i < len(starts) and starts[i] <= t+tol
    win = [(t,s) for t,s in env if a<=t<b]
    tiers = [("top 10%% (s>=%.1f)"%p90, [x for x in win if x[1]>=p90]),
             ("upper quartile", [x for x in win if p75<=x[1]<p90]),
             ("upper half",     [x for x in win if p50<=x[1]<p75]),
             ("lower half",     [x for x in win if x[1]<p50])]
    for label, ks in tiers:
        if not ks: continue
        miss=[t for t,s in ks if not covered(t)]
        flag = "  <-- SILENT NOTES" if (label.startswith("top") or label.startswith("upper")) and miss else ""
        print(f"  {label:<22} {len(ks)-len(miss):>3}/{len(ks):<3} answered{flag}")
        if miss and not label.startswith("lower"):
            print(f"      silent at: {[mmss_ms(m) for m in miss[:14]]}")
    nd=[(t,s) for t,s in win if s>=p50 and not any(abs(t-d)<80 for d in drum)]
    m=[t for t,s in nd if not covered(t)]
    print(f"  non-drum, upper half   {len(nd)-len(m):>3}/{len(nd):<3} answered   (bug-2 check)")
    if m: print(f"      silent at: {[mmss_ms(x) for x in m[:14]]}")
    big = sorted(win, key=lambda x:-x[1])[:6]
    print("  biggest moments in window:")
    for t,s in sorted(big):
        print(f"      {mmss_ms(t):>8}  strength {s:5.2f}  {'ANSWERED' if covered(t) else '*** SILENT ***'}")

    # --- house coverage over time, in PHYSICAL MODELS.
    #     Two darknesses (CLAUDE.md): local dark is how a section breathes; MAJORITY
    #     dark is a slam punch and must be rare and intended. A dip at a section
    #     boundary is a transition bug, never a breath.
    #     Groups are expanded to their member models, because "Peaks" and
    #     "Peak 0 Horizontal" light the same physical house -- counting element NAMES
    #     instead of models reports an empty house whenever the writer used models.
    if len(sys.argv) > 5: show = Path(sys.argv[5])
    else:                                   # the show folder: the one holding xlights_rgbeffects.xml above the .xsq
        show = next((d for d in [xsq.resolve().parent, *xsq.resolve().parents] if (d/"xlights_rgbeffects.xml").exists()), None)
        if show is None: sys.exit(f"no xlights_rgbeffects.xml above {xsq}; pass the show folder as argument 5")
    rgb = etree.parse(str(show/"xlights_rgbeffects.xml")).getroot()
    models = {m.get("name") for m in rgb.iter("model")}
    raw = {g.get("name"): [x.strip() for x in (g.get("models") or "").split(",") if x.strip()]
           for g in rgb.iter("modelGroup")}
    def expand(name, seen=None):
        seen = seen or set()
        if name in seen: return set()
        seen.add(name)
        name = name.split("/")[0]              # a submodel lights its parent model
        if name in models: return {name}
        out = set()
        for m in raw.get(name, []): out |= expand(m, seen)
        return out
    cover = {k: expand(k) for k in {e["el"] for e in eff}}
    print(f"\n--- house coverage (share of the {len(models)} physical models lit) ---")
    step = 250
    grid = []
    for t in range(int(a), int(b), step):
        live = set()
        for e in eff:
            if e["s"] <= t < e["e"] and e["name"] != "Off": live |= cover.get(e["el"], set())
        grid.append((t, len(live)/max(1, len(models))))
    fr = [g[1] for g in grid]
    print(f"  mean {100*sum(fr)/len(fr):.0f}%   min {100*min(fr):.0f}%   max {100*max(fr):.0f}%   "
          f"frames under 25% (majority dark): {sum(1 for f in fr if f < 0.25)}/{len(fr)}")
    print(f"  {mmss_ms(a,0)} |" + "".join(" .:-=+*#%@"[min(9, int(g[1]*10))] for g in grid) + f"| {mmss_ms(b,0)}")
    runs, cur = [], None
    for t, f in grid:
        if f < 0.25: cur = [t, t+step] if cur is None else [cur[0], t+step]
        elif cur: runs.append(cur); cur = None
    if cur: runs.append(cur)
    if runs:
        print("  majority-dark stretches (must be rare and intentional):")
        for s0, e0 in runs: print(f"      {mmss_ms(s0)}-{mmss_ms(e0)} ({dur((e0-s0)/1000)})")
    else:
        print("  no majority-dark stretches -- the house keeps moving throughout")
    for s in secs:
        t = int(s["start"]*1000)
        if not (a+500 < t < b-500): continue
        near = [f for tt, f in grid if abs(tt-t) <= 1000]
        if near and min(near) < 0.30:
            print(f"  !! coverage dips to {100*min(near):.0f}% at the '{s['name']}' boundary ({mmss_ms(t)})")

    print("\n--- per-element load (top 12) ---")
    ec = collections.Counter(e["el"] for e in eff)
    for k,v in ec.most_common(12):
        d = sorted(x["e"]-x["s"] for x in eff if x["el"]==k)
        print(f"  {k:<34} {v:>4}  median {d[len(d)//2]:>5}ms")


if __name__ == "__main__":
    main()
