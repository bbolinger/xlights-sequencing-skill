#!/usr/bin/env python
"""marktrack.py -- write a one-layer timing track of MARKS from analysis JSON, into BOTH element lists of a .xsq.

A song's own pulse (snaps, claps, a heartbeat) is often what a prop should answer, and a sequence does not always carry
it as a timing track. The marks are MEASURED elsewhere (onsets on a stem; the method and the evidence live in the JSON);
this tool only writes them:

    analysis/<marks>.json  {"track": "Snaps", "after": "Beats", "marks": [{"s": 1.65, "e": 1.9, "label": ""}, ...],
                            "why": "...", "method": "..."}

What it writes: one <Element type="timing"> in <DisplayElements> (the view list) AND one in <ElementEffects>, with a
single <EffectLayer> of <Effect label= startTime= endTime=> marks, placed after the track named by `after` (else after
the last timing track). xLights silently drops an ElementEffects row the view list does not know (reference/safety.md,
section 5). Times are seconds in the JSON and snap to the sequence's own frame grid (<sequenceTiming>, 25 ms when
absent); a mark is at least one frame long and is cut at the next mark; overlapping marks refuse.

Refuses: a track of that name already in either list (unless --replace, which rewrites its marks in the same position
in both lists); an `after` missing from either list; a file a running xLights holds open (save and close it first); a
backup name already taken. Before writing it copies the file to analysis/<song>.vNN-<tag>.xsq beside the song (NN = one
past the highest version there; the analysis folder must exist). A relative JSON path is read from the song's folder.

    marktrack.py <song.xsq> analysis/marks.json --dry-run | --apply [--replace] [--tag <word>]

A dry run prints the track name, the mark count, the span and every mark in m:ss, and writes nothing.
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path
from lxml import etree
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tc import mmss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xsq")
    ap.add_argument("marks")
    ap.add_argument("--tag", default="pre-marktrack")
    ap.add_argument("--replace", action="store_true",
                    help="the track exists: rewrite its marks in place (same position, both lists)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.dry_run == a.apply:
        ap.error("pick exactly one of --dry-run / --apply")
    src = Path(a.xsq).expanduser().resolve()
    an = src.parent / "analysis"
    mp = Path(a.marks)
    mp = mp if mp.is_absolute() else (src.parent / mp)
    cfg = json.load(open(mp))
    name = cfg["track"]
    tree = etree.parse(str(src))
    root = tree.getroot()
    ee, de = root.find("ElementEffects"), root.find("DisplayElements")
    m = re.match(r"\s*(\d+)", root.findtext(".//sequenceTiming") or "")
    G = int(m.group(1)) if m else 25                                   # the frame grid, ms
    snap = lambda t: int(round(t * 1000 / G) * G)
    tim = lambda lst: {x.get("name"): x for x in lst.findall("Element") if x.get("type") == "timing"}
    old = (tim(de).get(name), tim(ee).get(name))
    if any(x is not None for x in old) and not a.replace:
        raise SystemExit(f"track {name!r} already in the file -- --replace to rewrite its marks, or restore the backup")
    after = cfg.get("after")
    if after and (after not in tim(ee) or after not in tim(de)):
        raise SystemExit(f"after {after!r} is not a timing track in both lists")
    ms = sorted((snap(x["s"]), snap(x["e"]), x.get("label", "")) for x in cfg["marks"])
    out = []
    for i, (s, e, lab) in enumerate(ms):
        nxt = ms[i + 1][0] if i + 1 < len(ms) else 10 ** 9
        e = min(max(e, s + G), nxt)                                    # at least one frame; cut at the next mark
        if out and s < out[-1][1]:
            raise SystemExit(f"marks overlap at {mmss(s / 1000)}")
        out.append((s, e, lab))
    print(f"{name}: {len(out)} marks, {mmss(out[0][0] / 1000)}-{mmss(out[-1][1] / 1000)}, after {after!r}")
    print("  " + " ".join(mmss(s / 1000, 2) for s, _, _ in out))
    if a.dry_run:
        print("(dry run -- nothing written)")
        return
    if subprocess.run(["pgrep", "-x", "xLights"], capture_output=True).returncode == 0:
        import xl                                                      # the shipped xl.py, same folder
        held = (xl.status().get("fullseq") or "")
        if held and Path(held).expanduser().resolve() == src:
            raise SystemExit("xLights holds this file: xl.py save, xl.py close first")
    vers = [int(m.group(1)) for p in an.glob(f"{src.stem}.v*.xsq") for m in [re.match(r".*\.v(\d+)", p.stem)] if m]
    bak = an / f"{src.stem}.v{max(vers, default=0) + 1}-{a.tag}.xsq"
    if bak.exists():
        raise SystemExit(f"backup {bak.name} exists -- refusing")
    shutil.copy2(src, bak)
    nd = etree.Element("Element", collapsed="false", type="timing", name=name, visible="false", views="", active="false")
    ne = etree.Element("Element", type="timing", name=name)
    L = etree.SubElement(ne, "EffectLayer")
    for s, e, lab in out:
        etree.SubElement(L, "Effect", label=lab, startTime=str(s), endTime=str(e))
    if old[0] is not None and old[1] is not None:                      # --replace: same place in both lists
        old[0].addprevious(nd); old[0].getparent().remove(old[0])
        old[1].addprevious(ne); old[1].getparent().remove(old[1])
    elif after:
        tim(de)[after].addnext(nd)
        tim(ee)[after].addnext(ne)
    else:
        [x for x in de.findall("Element") if x.get("type") == "timing"][-1].addnext(nd)
        [x for x in ee.findall("Element") if x.get("type") == "timing"][-1].addnext(ne)
    tree.write(str(src), xml_declaration=True, encoding="UTF-8")
    print(f"wrote {name} ({len(out)} marks); backup {bak.name}")


if __name__ == "__main__":
    main()
