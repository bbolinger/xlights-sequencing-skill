#!/usr/bin/env python
"""profile.py: know what each prop IS before placing anything on it (reference/rules.md#knowledge).

    profile.py <show folder> [--reference <finished.xsq>] [--out <dir>] [--render <reference.fseq>]
               [--min-uses 5] [--held-back Fire,Video,...] [--no-draw]
    profile.py --reference <finished.xsq> [--out <dir>]        (the show folder is found above the .xsq)

Reads the show's `xlights_rgbeffects.xml` and ONE finished sequence on that layout (the owner's own, or
the professional one that shipped with a prop; default: the single .xsq in the show outside `analysis/`,
`Backup/` and `_archive/`, else `--reference` is required) and writes, into `--out` (DEFAULT: THE CURRENT
DIRECTORY, never the show folder unless you pass it):

  props/<model>.png     every distinct Custom model drawn from its own grid, submodels coloured
  props/_layout_map.png every model labelled on the background photo (if the layout has one)
  vocabulary.json       per ROW of the reference: effects, counts, coverage, median length, fade habits,
                        buffer styles, the verbatim settings of every effect used --min-uses times,
                        palettes, the timing track a VU Meter follows; SLICE SETS: the B_CUSTOM_SubBuffer
                        slices the reference starts together (same start +-50 ms, distinct boxes) with each
                        member's verbatim settings, box, length and layer, and how often a slice runs alone
                        (a slice placed alone reads as an odd division of the prop); a set counts only when
                        its boxes' UNION tiles >= SET_UNION_MIN of the buffer, the rest are
                        `slice_sets_partial` (one reference's lone and partial slices sat under its baked
                        Video: nobody ever saw them, so nobody should copy them); `slice_starts` per row
                        (starts / lone / full / partial, the way the owner counts them);
                        MIRRORED MEMBERS per group row (a Custom grid whose node 1 sits on the other side,
                        a two-point model or Poly Line running the other way, a different Dir/StartSide)
                        with `direction_safe_styles` (this row's styles that draw in PREVIEW space) and
                        `direction_symmetric_chases`; PER LAYER: lit share (all effects, and without the
                        HELD_BACK effects) and the effects on that layer; rows never used; rows that COPY
                        another row; whole-file layer/transition/value-curve habits; with --render,
                        `render_lit` per model (lit % and brightness-when-lit of the reference's own saved
                        render: the per-PROP truth the XML cannot show, 2026-10-04)
  PROPS.md              the human page: what each model is (type, size, nodes, submodels, where, groups),
                        and the per-row table. The owner reads and corrects this BEFORE any placement.

Nothing here invents: every number is counted, every settings string is the reference's own. The
drawings need Pillow (`uv run --no-project --with pillow --with lxml --with numpy --with zstandard
--python 3.12 python profile.py ...`); without it the tool writes everything else and says so.

HELD_BACK: the effects a placer never draws blind (Fire, Video, Faces, Text, Shader, Off and the rest of the
list below). `coverage_usable` and `layer_lit[].lit_usable` are the lit shares WITHOUT them, so a bed's real
coverage is not inflated by a baked Video or a Faces track. In the full toolkit this set came from a preset
library built from purchased professional sequences; that library is not in this release. The set is the
only thing it contributed here, so it is inlined as a plain constant and `--held-back` overrides it.

--render reads the reference's own saved `.fseq` through the public `fseq.py` and `layout.py` only: a model's
start channel and channels per node come from `layout.Layout` (3, or 4 for RGBW), its node count from its own
attributes (`node_count_attrs`), and the model spans are PROVED against the file before a byte is read (a
dense render must be tiled exactly; a sparse one must have no overlapping spans and every stored range inside
the models' union). A `>OtherModel:n` chained start channel or a single-colour string is not resolved by the
public layout reader: the proof refuses rather than reporting a plausible wrong number. `lit` = a frame where
more than 5 % of the model's nodes have a channel above 32; `bright` = the mean, over lit frames, of the max
channel of the lit nodes.

Why this exists: 2026-10-03, two renders on a layout the tools had never seen were rejected as "blink city"
because props were classified by NAME and the reference file was read as averages. The file in front of us
held the answer per row and per setting. A prop class is not a licence; averages are not knowledge.
"""
from __future__ import annotations
import argparse, json, re, statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tc import mmss                                   # positions print as m:ss, never raw seconds
from layout import Layout, show_folder_of             # the show's channel layout, for --render

# The effects a placer never draws unasked (pictures, text, faces, baked media, a blackout). Lit shares
# are reported with and without them; `--held-back` replaces the list.
HELD_BACK = {"Fire", "Plasma", "Strobe", "Lightning", "Text", "Video", "Pictures", "Shader", "DMX",
             "Faces", "Music Effect", "State", "Piano", "Snowstorm", "Life", "Tendril", "Off"}


# ----------------------------------------------------------------------------- layout
def expand_ranges(spec: str) -> set[int]:
    out = set()
    # commas OR whitespace: a hand-typed submodel node list can drop a comma ("... 29, 31 33", 2026-10-18)
    for part in re.split(r"[,\s]+", (spec or "").strip()):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
            out.update(range(min(a, b), max(a, b) + 1))
        else:
            out.add(int(part))
    return out


GROUP_LAYOUT: dict = {}     # group -> its `layout` attribute (minimalGrid / grid = preview space; horizontal / vertical = per model)


def read_layout(show: Path):
    root = etree.parse(str(show / "xlights_rgbeffects.xml")).getroot()
    models, groups = {}, {}
    for m in root.find("models"):
        subs = []
        for sm in m.findall("subModel"):
            nodes = set().union(*[expand_ranges(sm.get(k)) for k in sm.attrib if k.startswith("line")]) if any(
                k.startswith("line") for k in sm.attrib) else set()
            subs.append({"name": sm.get("name"), "nodes": sorted(nodes), "bufferstyle": sm.get("bufferstyle"),
                         "type": sm.get("type")})
        pts = {}
        cm = m.get("CustomModelCompressed") or ""
        # CustomModelCompressed is `node,ROW,COL[,layer];...` and row 0 is the TOP of the grid (a 21-wide, 47-high
        # cane puts node 1 at "46,0" = bottom row, left column). Stored here as (col, row) = (x, y). An earlier
        # version read it as (x, y) and drew every grid transposed (2026-10-04).
        for t in cm.split(";"):
            if t:
                n, row, col = (int(v) for v in t.split(",")[:3]); pts[n] = (col, row)
        models[m.get("name")] = {
            "DisplayAs": m.get("DisplayAs"), "parm1": m.get("parm1"), "parm2": m.get("parm2"), "parm3": m.get("parm3"),
            "StringType": m.get("StringType"), "StartChannel": m.get("StartChannel"),
            "WorldPosX": float(m.get("WorldPosX") or 0), "WorldPosY": float(m.get("WorldPosY") or 0),
            "CustomWidth": m.get("CustomWidth"), "CustomHeight": m.get("CustomHeight"), "custom_points": pts,
            "custom_key": cm, "submodels": subs, "attrs": dict(m.attrib), "extra": {k: m.get(k) for k in
                ("TreeDegrees", "TreeBottomTopRatio", "TreeSpiralRotations", "Hollow", "PixelSize", "StarSizes") if m.get(k)},
        }
    for g in root.find("modelGroups"):
        groups[g.get("name")] = [x.strip() for x in (g.get("models") or "").split(",") if x.strip()]
        GROUP_LAYOUT[g.get("name")] = g.get("layout") or "minimalGrid"
    bg = next((e.get("value") for e in root.iter("backgroundImage")), None)
    pw = next((int(e.get("value")) for e in root.iter("previewWidth")), 1280)
    ph = next((int(e.get("value")) for e in root.iter("previewHeight")), 720)
    return models, groups, bg, (pw, ph)


def leaf_models(name, models, groups, seen=None):
    seen = seen or set()
    if name in seen:
        return set()
    seen.add(name)
    base = name.split("/")[0]
    if base in models:
        return {base}
    out = set()
    for m in groups.get(name, []):
        out |= leaf_models(m, models, groups, seen)
    return out


def node_count_attrs(a: dict) -> int:
    """Nodes from a model's own attributes (xLights 2026 format: named keys; parm1..3 only in old files)."""
    d = a.get("DisplayAs", ""); g = lambda k, dflt=0: int(a.get(k) or dflt)
    if d == "Custom":
        return len([t for t in (a.get("CustomModelCompressed") or "").split(";") if t])
    if d == "Arches":   return g("NumArches", 1) * g("NodesPerArch")
    if d == "Window Frame": return g("TopNodes") + 2 * g("SideNodes") + g("BottomNodes")
    if d == "Cube":     return g("CubeWidth") * g("CubeHeight") * g("CubeDepth")
    if a.get("NodesPerString"):
        return max(g("NumStrings", 1), g("PolyStrings", 1), g("Strings", 1)) * g("NodesPerString")
    p1, p2, p3 = g("parm1"), g("parm2"), g("parm3")
    return p1 * p2 if p1 and p2 else max(p1, p2)


def node_count(m) -> int:
    return node_count_attrs(m["attrs"])


def describe(name, m, groups) -> str:
    d = m["DisplayAs"]; A = m["attrs"]
    p1 = A.get("NumStrings") or A.get("NumArches") or A.get("TopNodes") or A.get("CubeWidth") or A.get("parm1")
    p2 = A.get("NodesPerString") or A.get("NodesPerArch") or A.get("SideNodes") or A.get("CubeHeight") or A.get("parm2")
    p3 = A.get("StarPoints") or A.get("BottomNodes") or A.get("CubeDepth") or A.get("parm3")
    if d == "Custom":
        shape = f"Custom {m['CustomWidth']}x{m['CustomHeight']} grid"
    elif d.startswith("Tree"):
        shape = f"{d} {p1} strings x {p2} nodes, {m['extra'].get('TreeDegrees','?')}°"
    elif d in ("Matrix", "Vert Matrix", "Horiz Matrix"):
        shape = f"{d} {p1}x{p2}"
    elif d == "Star":
        shape = f"Star {p3} points, {p2} nodes"
    elif d == "Window Frame":
        shape = f"Window Frame top {p1} / sides {p2} / bottom {p3}"
    elif d == "Single Line":
        shape = f"Single Line {p2} nodes" + (" (ONE PIXEL: a flood)" if (p2 or "") in ("1",) else "")
    elif d == "Arches":
        shape = f"Arches {p1} arch x {p2} nodes, hollow {m['extra'].get('Hollow','?')}"
    elif d == "Icicles":
        shape = f"Icicles {p2} nodes"
    elif d == "Poly Line":
        shape = f"Poly Line {p2} nodes"
    elif d == "Cube":
        shape = f"Cube {p1}x{p2}x{p3}"
    else:
        shape = f"{d} {p1}/{p2}/{p3}"
    subs = [s["name"] for s in m["submodels"]]
    ing = [g for g, mem in groups.items() if any(x.split("/")[0] == name for x in mem)]
    return f"{shape}; {node_count(m)} nodes" + (f"; submodels: {', '.join(subs[:12])}{'…' if len(subs) > 12 else ''}" if subs else "") + \
           (f"; in groups: {', '.join(ing)}" if ing else "; in NO group")


# ----------------------------------------------------------------------------- drawings
def draw(out_dir: Path, show: Path, models, bg, preview):
    """Draw every distinct Custom grid and the layout map into `<out_dir>/props/`. `show` is only used to
    find a background image given by its file name."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import colorsys
    except ImportError:
        print("Pillow not importable: skipping drawings (run under uv --with pillow to get props/*.png)")
        return []
    out = out_dir / "props"; out.mkdir(parents=True, exist_ok=True); font = ImageFont.load_default(); written = []
    seen = {}
    for name, m in models.items():
        if m["DisplayAs"] != "Custom":
            continue
        seen.setdefault(m["custom_key"], []).append(name)
    for key, names in seen.items():
        m = models[names[0]]; W, H = int(m["CustomWidth"]), int(m["CustomHeight"]); pts = m["custom_points"]
        S = max(2, min(8, 700 // max(W, H))); pad = 20; subs = m["submodels"]; legend_h = 14 * (len(subs) // 4 + 2)
        img = Image.new("RGB", (W * S + 2 * pad, H * S + 2 * pad + legend_h), (15, 15, 15)); dr = ImageDraw.Draw(img)
        for n, (x, y) in pts.items():
            dr.rectangle([pad + x * S, pad + y * S, pad + x * S + S - 1, pad + y * S + S - 1], fill=(70, 70, 70))
        claimed = {}
        for i, s in enumerate(subs):
            col = tuple(int(255 * c) for c in colorsys.hsv_to_rgb((i * 0.137) % 1.0, 0.85, 1.0))
            for n in s["nodes"]:
                if n in pts and n not in claimed:
                    claimed[n] = s["name"]; x, y = pts[n]
                    dr.rectangle([pad + x * S, pad + y * S, pad + x * S + S - 1, pad + y * S + S - 1], fill=col)
            dr.rectangle([pad + (i % 4) * (W * S // 4), H * S + 2 * pad + 14 * (i // 4), pad + (i % 4) * (W * S // 4) + 10,
                          H * S + 2 * pad + 14 * (i // 4) + 10], fill=col)
            dr.text((pad + (i % 4) * (W * S // 4) + 13, H * S + 2 * pad + 14 * (i // 4) - 1), s["name"][:22], fill=(220, 220, 220), font=font)
        dr.text((pad, 2), f"{names[0]} (+{len(names)-1} same) grid {W}x{H} nodes {len(pts)} submodels {len(subs)} unclaimed {len(pts)-len(claimed)}",
                fill=(255, 255, 255), font=font)
        fn = out / (re.sub(r"[^A-Za-z0-9_-]+", "_", names[0]) + ".png"); img.save(fn); written.append(fn.name)
    bgp = None
    if bg:
        for cand in (Path(bg), show / Path(bg.replace("\\", "/")).name):
            if cand.exists():
                bgp = cand; break
    pw, ph = preview
    base = Image.open(bgp).convert("RGB").resize((1920, int(1920 * ph / pw))) if bgp else Image.new("RGB", (1920, int(1920 * ph / pw)), (20, 20, 30))
    dr = ImageDraw.Draw(base); sx, sy = base.size[0] / pw, base.size[1] / ph
    for name, m in models.items():
        X, Y = m["WorldPosX"] * sx, (ph - m["WorldPosY"]) * sy
        dr.ellipse([X - 4, Y - 4, X + 4, Y + 4], fill=(255, 200, 0)); dr.text((X + 6, Y - 6), name, fill=(255, 255, 255), font=font)
    base.save(out / "_layout_map.png"); written.append("_layout_map.png")
    return written


# ----------------------------------------------------------------------------- reference
def kv(s: str) -> dict:
    d = {}
    for part in s.split(","):
        if "=" in part:
            k, v = part.split("=", 1); d[k] = v
    return d


def core(d: dict) -> str:
    return ",".join(f"{k}={v}" for k, v in sorted(d.items())
                    if not k.startswith("T_TEXTCTRL_Fade") and k not in ("T_CHOICE_In_Transition_Type", "T_CHOICE_Out_Transition_Type"))


FULL_AREA = 0.99       # a SubBuffer whose box, clipped to the buffer, covers this much IS the whole buffer (a shifted
                       # full-width box such as `0x-120x100x101` or `0x-21x100x119` is the whole buffer once clipped)
SET_UNION_MIN = 0.90   # a slice SET must tile this much of the buffer (the owner, 2026-10-04: bars in one corner, or
                       # scattered as if the screen were divided at random, read as a mistake)
SET_WINDOW_MS = 50     # effects starting this close together on one row start TOGETHER
MAX_SET_MEMBERS = 5    # a set needs one layer per member; the largest set measured so far has 5


def slice_box(sb: str):
    """The box a `B_CUSTOM_SubBuffer` string draws into, clipped to the buffer, as (x1, y1, x2, y2) in percent,
    or None when a field is a value curve (a MOVING slice: its box at any instant is unknown here)."""
    if not sb:
        return None
    try:
        v = [float(x) for x in sb.split("x")][:4]
    except ValueError:
        return None
    if len(v) < 4:
        return None
    x1, y1, x2, y2 = max(0.0, min(v[0], v[2])), max(0.0, min(v[1], v[3])), min(100.0, max(v[0], v[2])), min(100.0, max(v[1], v[3]))
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else (0.0, 0.0, 0.0, 0.0)


def slice_area(sb: str) -> float:
    """Share of the buffer a SubBuffer string covers (clipped); 0 for a moving (value-curve) slice."""
    b = slice_box(sb)
    return (b[2] - b[0]) * (b[3] - b[1]) / 10000.0 if b else 0.0


def union_area(keys) -> float:
    """Share of the buffer covered by the UNION of the boxes (clipped); moving slices contribute nothing."""
    rects = [b for b in (slice_box(k) for k in keys) if b and b[2] > b[0]]
    if not rects:
        return 0.0
    xs = sorted({r[0] for r in rects} | {r[2] for r in rects}); ys = sorted({r[1] for r in rects} | {r[3] for r in rects})
    tot = 0.0
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rects):
                tot += (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
    return tot / 10000.0


def subbuffer_key(d: dict):
    """The slice a settings dict draws into, or None for the whole buffer. `B_CUSTOM_SubBuffer` is
    x1 x y1 x x2 x y2 (percent; 2026 files add two more fields). A box whose CLIPPED area covers >= FULL_AREA
    of the buffer (`0x0x100x100`, the shifted `0x-120x100x101`, `-0.35x-0.04x100.35x99.63`) IS the whole buffer.
    A value-curve-driven (moving) slice keeps its own string as the key: it is a slice whose box moves."""
    sb = d.get("B_CUSTOM_SubBuffer")
    if not sb:
        return None
    b = slice_box(sb)
    if b is None:
        return sb
    if slice_area(sb) >= FULL_AREA:
        return None
    return "x".join(f"{x:g}" for x in b)


def is_slice(settings: str) -> bool:
    """True when a verbatim settings string draws into a slice of its buffer (a placer asks this)."""
    return subbuffer_key(kv(settings)) is not None


def start_clusters(effs):
    """Non-Off effects of ONE row grouped by start: a cluster is every effect starting within SET_WINDOW_MS of the
    cluster's FIRST start, in (start, layer) order. The one definition a profiler and a placer must share."""
    live = sorted((x for x in effs if x[0] != "Off"), key=lambda x: (x[1], x[3]))
    clusters = []
    for x in live:
        if clusters and x[1] - clusters[-1][0][1] <= SET_WINDOW_MS:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return live, clusters


def slice_starts(effs):
    """Per row, the way the owner counts: every start at which a slice begins, classed as
    `lone` (one slice, nothing else sliced starts with it), `full` (>= 2 boxes whose union covers >= SET_UNION_MIN),
    or `partial` (>= 2 boxes under it). Returns (starts, lone, full, partial, Counter of lone 'Effect box')."""
    _, clusters = start_clusters(effs)
    starts = lone = full = partial = 0
    lone_c = Counter()
    for cl in clusters:
        sl = [(x, subbuffer_key(x[4])) for x in cl if subbuffer_key(x[4]) is not None]
        if not sl:
            continue
        starts += 1
        boxes = {k for _, k in sl}
        if len(boxes) < 2:
            lone += 1; lone_c[f"{sl[0][0][0]} {sl[0][1]}"] += 1
        elif union_area(boxes) >= SET_UNION_MIN:
            full += 1
        else:
            partial += 1
    return starts, lone, full, partial, lone_c


def slice_sets(effs):
    """effs: [(name, s, e, layer, settings dict, palette)] of ONE row, Off excluded.
    Sets = clusters of effects starting within SET_WINDOW_MS of each other whose SLICE members
    (B_CUSTOM_SubBuffer not the whole buffer) span >= 2 distinct boxes AND whose boxes' union covers
    >= SET_UNION_MIN of the buffer: the reference TILES the prop with them (a Bars pair at 0-50 / 50-100;
    four SingleStrand bands across a matrix). A cluster of >= 2 boxes under the union is a PARTIAL tiling
    (alternating SingleStrand bands on a tree at 0/41/81 then 21/61: each start covers 60 % / 40 %) and is
    recorded apart; nobody places it.
    Returns (sets, n_slices, n_alone, n_alone_covered, partial):
      sets  [{n, union, members: [{effect, settings_verbatim, subbuffer, len_ms, layer, palette}], span_covered}]
            one per distinct signature (sorted (effect, box) tuple), members in the reference's layer
            order (a lower index renders on top), each member's settings the most common verbatim
            string at that position, len_ms its median; sorted by -n then signature: deterministic.
      n_alone          slices starting with no differently-boxed slice sibling (LONE: never placed)
      n_alone_covered  of those, how many start while ANOTHER layer of the row is already lit
      partial          [{n, union, span_covered}] the partial tilings, by signature, with their occurrence counts"""
    live, clusters = start_clusters(effs)
    occ = defaultdict(list); part = defaultdict(list)
    n_slices = n_alone = n_alone_cov = 0
    for cl in clusters:
        sl = [(x, subbuffer_key(x[4])) for x in cl if subbuffer_key(x[4]) is not None]
        if not sl:
            continue
        boxes = {k for _, k in sl}
        n_slices += len(sl)
        if len(boxes) >= 2:
            # members ordered by the reference's layer (top first); the signature ignores the order
            mem = sorted(sl, key=lambda xk: (xk[0][3], xk[0][0], xk[1]))[:MAX_SET_MEMBERS]
            sig = tuple(sorted((x[0], k) for x, k in mem))
            u = union_area({k for _, k in mem})
            (occ if u >= SET_UNION_MIN else part)[sig].append((mem, u))
        else:
            n_alone += len(sl)
            t0 = cl[0][1]
            for x, _ in sl:
                if any(y[1] < t0 - SET_WINDOW_MS and y[2] > t0 + 200 and y[3] != x[3] for y in live):
                    n_alone_cov += 1
    sets = []
    for sig, occs in occ.items():
        k = len(occs[0][0])
        members = []
        for j in range(k):
            col = [o[j] for o, _u in occs if len(o) > j]
            settings = Counter(core(x[4]) for x, _ in col).most_common(1)[0][0]
            lens = sorted(x[2] - x[1] for x, _ in col)
            members.append({"effect": Counter(x[0] for x, _ in col).most_common(1)[0][0],
                            "settings_verbatim": settings,
                            "subbuffer": Counter(kk for _, kk in col).most_common(1)[0][0],
                            "len_ms": lens[len(lens) // 2],
                            "layer": Counter(x[3] for x, _ in col).most_common(1)[0][0],
                            "palette": Counter(x[5] for x, _ in col).most_common(1)[0][0]})
        members.sort(key=lambda m: (m["layer"], m["effect"], m["subbuffer"]))
        sets.append({"n": len(occs), "union": round(min(u for _, u in occs), 3), "members": members,
                     "span_covered": "; ".join(f"{m['effect']} [{m['subbuffer']}]" for m in members)})
    sets.sort(key=lambda d: (-d["n"], d["span_covered"]))
    partial = sorted(({"n": len(v), "union": round(min(u for _, u in v), 3),
                       "span_covered": "; ".join(f"{e} [{k}]" for e, k in sig)} for sig, v in part.items()),
                     key=lambda d: (-d["n"], d["span_covered"]))
    return sets, n_slices, n_alone, n_alone_cov, partial


# ----------------------------------------------------------------------------- mirrored members
# The owner, 2026-10-04, on a render: the same effect on the candy canes left and right of the driveway ran
# backwards on one side, so the pair looked upside down. The two pairs were DIFFERENT custom grids, node 1
# bottom-left on one pair and bottom-right on the other, so any buffer style that runs in NODE ORDER or on the
# model's own grid runs a directional chase the opposite way across the driveway. Only PREVIEW-space styles
# see the yard as the eye does.
SIDE_MIN = 0.2          # node 1 counts as left/right when its column sits this far (share of the width) from the centre
DIRECTION_SAFE_STYLES = ("Per Model Per Preview", "Per Preview")      # + any `Overlay - *`, + `default` on a minimalGrid GROUP
DIRECTION_SYMMETRIC_CHASES = ("From Middle", "To Middle", "Dual Chase", "Dual Bounce", "Bounce from Left",
                              "Bounce from Right", "Bounce from Middle")


def style_is_screen_space(style: str, row_is_group: bool, group_layout: str = "minimalGrid") -> bool:
    """Does this buffer style draw in PREVIEW coordinates (so a mirrored member reads the same as its twin)?
    `Per Model Per Preview`, `Per Preview` and every `Overlay - *` do. `default` on a GROUP whose layout is
    minimalGrid/grid is the group's 2-D preview grid; `horizontal`/`vertical` group layouts stack the models
    and are NOT. `default` on a model row is the model's own grid: no twin to mirror, so it is safe there too."""
    s = (style or "default")
    if s in DIRECTION_SAFE_STYLES or s.startswith("Overlay - "):
        return True
    if s.lower() == "default":
        return (group_layout or "minimalGrid").lower() in ("minimalgrid", "grid") if row_is_group else True
    return False


def handedness(m: dict):
    """Which way a model RUNS in the preview, from the layout alone: (axis, sign) with axis 'h' or 'v' and sign +-1,
    or None when the file says nothing (a Tree, a Matrix, a Star: node order is their own and identical per type).
      Custom      the column of node 1 against the grid centre (left -1 / right +1; a centre start is None)
      two-point   Single Line / Arches / Icicles: the end point X2,Y2 relative to the start, the dominant axis
      Poly Line   PointData first -> last point, the dominant axis
    Dir / StartSide are compared separately (same-type models whose wiring attributes differ)."""
    a = m["attrs"]; d = m["DisplayAs"]
    if d == "Custom":
        pts = m["custom_points"]
        if 1 not in pts or not m["CustomWidth"]:
            return None
        W = int(m["CustomWidth"]); col = pts[1][0]
        off = (col - (W - 1) / 2) / max(W, 1)
        return ("h", 1 if off > 0 else -1) if abs(off) >= SIDE_MIN else None
    if "X2" in a and "Y2" in a:
        x2, y2 = float(a.get("X2") or 0), float(a.get("Y2") or 0)
        if abs(x2) < 1e-6 and abs(y2) < 1e-6:
            return None
        return ("h", 1 if x2 > 0 else -1) if abs(x2) >= abs(y2) else ("v", 1 if y2 > 0 else -1)
    if d == "Poly Line" and a.get("PointData"):
        v = [float(x) for x in a["PointData"].split(",") if x != ""]
        if len(v) >= 6:
            dx, dy = v[-3] - v[0], v[-2] - v[1]
            if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                return None
            return ("h", 1 if dx > 0 else -1) if abs(dx) >= abs(dy) else ("v", 1 if dy > 0 else -1)
    return None


def mirrored_members(leaves, models):
    """Members of a row that run the OPPOSITE way to the majority of their axis class, plus members whose Dir /
    StartSide differ from the majority of their DisplayAs. Returns [{model, why}] sorted by model name."""
    out = {}
    by_axis = defaultdict(list)
    for name in leaves:
        m = models.get(name)
        if not m: continue
        h = handedness(m)
        if h: by_axis[h[0]].append((name, h[1]))
    for axis, lst in by_axis.items():
        if len({s for _, s in lst}) < 2: continue
        pos = sum(1 for _, s in lst if s > 0); neg = len(lst) - pos
        maj = 1 if pos > neg else (-1 if neg > pos else lst[0][1])       # a tie: the first-listed member's way wins
        for name, s in lst:
            if s != maj:
                out[name] = (f"runs {'right' if s > 0 else 'left'}" if axis == "h" else f"runs {'up' if s > 0 else 'down'}") + \
                            f" where {'%d' % max(pos, neg)} of {len(lst)} run the other way"
    by_type = defaultdict(list)
    for name in leaves:
        m = models.get(name)
        if m: by_type[m["DisplayAs"]].append((name, (m["attrs"].get("Dir") or "L", m["attrs"].get("StartSide") or "B")))
    for d, lst in by_type.items():
        if len({w for _, w in lst}) < 2: continue
        maj = Counter(w for _, w in lst).most_common(1)[0][0]
        for name, w in lst:
            if w != maj:
                out[name] = (out.get(name, "") + "; " if name in out else "") + f"Dir/StartSide {w[0]}/{w[1]} where most {d} are {maj[0]}/{maj[1]}"
    return [{"model": n, "why": out[n]} for n in sorted(out)]


def profile_reference(xsq: Path, models, groups, min_uses: int, held_back=HELD_BACK):
    root = etree.parse(str(xsq)).getroot(); ee = root.find("ElementEffects")
    dur = float(root.find("head/sequenceDuration").text); fps = 20
    db = [e.text or "" for e in root.find("EffectDB")]; pal = [e.text or "" for e in root.find("ColorPalettes")]
    rows = {}; sig = {}; whole = {"blend": Counter(), "in": Counter(), "out": Counter(), "vc": Counter(), "fades": Counter()}
    timing = [el.get("name") for el in ee.findall("Element") if el.get("type") == "timing"]
    for el in ee.findall("Element"):
        if el.get("type") == "timing":
            continue
        name = el.get("name"); effs = []
        layers = el.findall("EffectLayer")
        for li, L in enumerate(layers):
            for f in L.findall("Effect"):
                ref, pr = f.get("ref"), f.get("palette")
                s = db[int(ref)] if ref and ref.isdigit() and int(ref) < len(db) else ""
                pp = pal[int(pr)] if pr and pr.isdigit() and int(pr) < len(pal) else ""
                effs.append((f.get("name"), int(f.get("startTime")), int(f.get("endTime")), li, kv(s), pp))
        subrows = {}
        for sm in el.findall("SubModelEffectLayer"):
            n = sum(len(L.findall("Effect")) for L in sm.findall("EffectLayer"))
            if n:
                subrows[sm.get("name")] = n
        if not effs and not subrows:
            continue
        lit = [0] * int(dur * fps); litu = [0] * int(dur * fps)
        for n, s, e, li, d, pp in effs:
            if n != "Off":
                for i in range(s * fps // 1000, min(e * fps // 1000, len(lit))):
                    lit[i] = 1
                    if n not in held_back: litu[i] = 1
        durs = [e - s for _, s, e, *_ in effs]
        # Per LAYER: what share of the song each layer is lit, with and without the held-back effects
        # (a hero's layer 0 is a baked Video over an Off; its source material sits on L2+), and the
        # effects on it. The owner stacks several part-time layers on one row and the union is the
        # row's coverage; a placer that runs one chain per row cannot reach it (2026-10-04).
        layer_lit = []
        for li, L in enumerate(layers):
            la = [0] * len(lit); lu = [0] * len(lit); cnt = Counter()
            for n, s, e, lli, d, pp in effs:
                if lli != li or n == "Off": continue
                cnt[n] += 1
                for i in range(s * fps // 1000, min(e * fps // 1000, len(lit))):
                    la[i] = 1
                    if n not in held_back: lu[i] = 1
            layer_lit.append({"lit": round(sum(la) / max(len(lit), 1), 3), "lit_usable": round(sum(lu) / max(len(lit), 1), 3),
                              "effects": dict(cnt.most_common())})
        per = {}
        for eff in sorted({x[0] for x in effs}):
            lst = [x for x in effs if x[0] == eff]
            ds = sorted(e - s for _, s, e, *_ in lst)
            fades = Counter((d.get("T_TEXTCTRL_Fadein", "0"), d.get("T_TEXTCTRL_Fadeout", "0")) for *_, d, pp in lst)
            styles = Counter(d.get("B_CHOICE_BufferStyle", "default") for *_, d, pp in lst)
            tracks = Counter(d.get("E_CHOICE_VUMeter_TimingTrack") for *_, d, pp in lst if d.get("E_CHOICE_VUMeter_TimingTrack"))
            entry = {"n": len(lst), "n_slice": sum(subbuffer_key(d) is not None for *_, d, pp in lst),
                     "median_ms": ds[len(ds) // 2], "p90_ms": ds[int(len(ds) * 0.9)],
                     "share_le_1s": round(sum(x <= 1000 for x in ds) / len(ds), 2),
                     "fades": [[a, b, c] for (a, b), c in fades.most_common(3)],
                     # every style the reference puts on this effect here (a validator can attest a Per Preview
                     # from this list; a top-3 list once hid a 1-of-48 variant, 2026-10-04)
                     "buffer_styles": [[k, c] for k, c in styles.most_common(8)],
                     "timing_tracks": [[k, c] for k, c in tracks.most_common(2)]}
            if len(lst) >= min_uses:
                cs = Counter(core(d) for *_, d, pp in lst); ps = Counter(pp for *_, d, pp in lst)
                # up to 8 variants: a placer picks one BY COUNT, and a top-3 list once hid a tree's
                # full-buffer SingleStrand variants behind three slice variants of 10 each (2026-10-04)
                entry["settings"] = [[s_, c] for s_, c in cs.most_common(8)]
                entry["settings_covered"] = round(sum(c for _, c in cs.most_common(8)) / len(lst), 2)
                entry["palettes"] = [[p_, c] for p_, c in ps.most_common(3)]
            per[eff] = entry
            for *_, d, pp in lst:
                whole["blend"][d.get("T_CHOICE_LayerMethod", "Normal")] += 1
                whole["in"][d.get("T_CHOICE_In_Transition_Type", "Fade")] += 1
                whole["out"][d.get("T_CHOICE_Out_Transition_Type", "Fade")] += 1
                whole["fades"][(d.get("T_TEXTCTRL_Fadein", "0"), d.get("T_TEXTCTRL_Fadeout", "0"))] += 1
                for k, v in d.items():
                    if "VALUECURVE" in k and "Active=TRUE" in v:
                        whole["vc"][k] += 1
        sets, n_sl, n_alone, n_alone_cov, partial = slice_sets(effs)
        _starts, _lone, _full, _part, _ = slice_starts(effs)
        leaves = sorted(leaf_models(name, models, groups))
        is_group = name in groups
        # which members run the other way, and which of THIS row's buffer styles draw in preview space
        mirrored = mirrored_members(leaves, models) if is_group else []
        styles_here = {s for v in per.values() for s, _c in v["buffer_styles"]}
        safe_styles = sorted(s for s in styles_here if style_is_screen_space(s, is_group, GROUP_LAYOUT.get(name, "minimalGrid")))
        rows[name] = {"kind": "group" if is_group else ("model" if name in models else "UNKNOWN"),
                      "n": len(effs), "coverage": round(sum(lit) / len(lit), 3) if lit else 0,
                      "slice_sets": sets, "slice_sets_partial": partial, "slices": n_sl, "slice_alone": n_alone,
                      "slice_starts": {"starts": _starts, "lone": _lone, "full": _full, "partial": _part},
                      "slice_alone_share": round(n_alone / n_sl, 3) if n_sl else None,
                      "slice_alone_covered_share": round(n_alone_cov / n_alone, 3) if n_alone else None,
                      "mirrored_members": mirrored,
                      "direction_safe_styles": safe_styles,
                      "direction_symmetric_chases": list(DIRECTION_SYMMETRIC_CHASES),
                      "coverage_usable": round(sum(litu) / len(litu), 3) if litu else 0,   # the same without held-back effects
                      "median_ms": st.median(durs) if durs else 0, "layers": len(layers),
                      "effects": per, "submodel_rows": subrows, "layer_lit": layer_lit,
                      "leaf_models": leaves}
        sig[name] = tuple(sorted((n, s, e) for n, s, e, *_ in effs))
    copies = []
    names = list(sig)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if sig[a] == sig[b] and len(sig[a]) >= 20:
                copies.append([a, b])
    used = set(rows)
    never = {"groups": sorted(g for g in groups if g not in used), "models": sorted(m for m in models if m not in used)}
    whole_out = {k: [[(list(a) if isinstance(a, tuple) else a), c] for a, c in v.most_common(10)] for k, v in whole.items()}
    return {"reference": xsq.name, "duration_s": dur, "effects": sum(r["n"] for r in rows.values()), "timing_tracks": timing,
            "rows": rows, "copies": copies, "never_used": never, "whole_file": whole_out}


# ----------------------------------------------------------------------------- the render (--render)
LIT_CH = 32          # a channel above this is "on"
LIT_FRAC = 0.05      # a model is lit when more than this share of its nodes is on


def prove_spans(M, F):
    """The model spans must tile the fseq's channels exactly: a wrong node-count attribute or a wrong
    start-channel rule shows up here, not as a plausible number in the table.
    A SPARSE render (xLights stores only the channels of the models the song uses) cannot tile: there the
    proof is that the model spans never overlap and every stored range lies inside the models' union."""
    if getattr(F, "ranges", None) and F.ranges != [(0, F.channels)]:
        spans = sorted((m["start"], m["start"] + m["ch"]) for m in M.values())
        for (a, b), (c, d) in zip(spans, spans[1:]):
            assert c >= b, f"model spans overlap at channel {c} (a start channel resolved wrong)"
        for s0, n in F.ranges:                     # 0-based start -> channels s0+1 .. s0+n
            lo, hi = s0 + 1, s0 + n
            cov = sum(max(0, min(hi + 1, b) - max(lo, a)) for a, b in spans)
            assert cov == n, f"sparse range {lo}-{hi} is not fully inside the layout's models ({cov} of {n} channels)"
        return
    total = sum(m["ch"] for m in M.values())
    assert total == F.channels, (f"model channel spans sum to {total}, the fseq holds {F.channels}: a node count "
                                 f"or start channel is wrong (node_count_attrs / layout.Layout)")
    spans = sorted((m["start"], m["start"] + m["ch"]) for m in M.values())
    for (a, b), (c, d) in zip(spans, spans[1:]):
        assert c >= b, f"model spans overlap at channel {c} (a start channel resolved wrong)"
    assert spans[-1][1] - 1 == F.channels, f"last model ends at {spans[-1][1] - 1}, fseq has {F.channels}"


def render_lit(show: Path, fseq_path: Path, models, step: float = 0.5):
    """Per model, from the reference's own saved render: {model: {lit_pct, bright_when_lit, lit, frames_sampled}}.
    Why: a render that LOOKS darker than the owner's was not dimmer per pixel (brightness-when-lit was identical);
    it was lit for LESS TIME per prop, because the owner's lit time is the UNION of several rows reaching the same
    pixels. The XML cannot show that; the render can (2026-10-04).
    Channels come from the public `layout.Layout` (absolute 1-based start; stride 3, or 4 for RGBW) and the node
    count from the model's own attributes; frames through `fseq.FSEQ.frame()` (sparse ranges laid out at absolute
    channels; byte index = absolute channel - 1). The spans are proved before a byte is read."""
    import numpy as np
    import fseq
    lay = Layout(show)
    M, missing = {}, []
    for name, m in models.items():
        if name not in lay.start:
            missing.append(name); continue
        n = node_count(m); cpn = lay.stride[name]
        M[name] = {"start": lay.start[name], "nodes": n, "cpn": cpn, "ch": n * cpn}
    if missing:
        raise SystemExit(f"--render: {len(missing)} models have a start channel layout.py does not resolve "
                         f"(a `>Model:n` chain or an unknown controller): {missing[:8]}")
    F = fseq.FSEQ(str(fseq_path))
    prove_spans(M, F)
    fps = 1000.0 / F.step
    every = max(1, int(round(step * fps)))
    out = {n: {"lit": 0, "bright": 0.0, "n": 0} for n in M}
    for i in range(0, F.frames, every):
        fr = np.frombuffer(F.frame(i), dtype=np.uint8)
        for n, m in M.items():
            a = fr[m["start"] - 1:m["start"] - 1 + m["ch"]]
            if a.size == 0: continue
            mx = a.reshape(-1, m["cpn"]).max(1)
            on = mx > LIT_CH
            out[n]["n"] += 1
            if on.mean() > LIT_FRAC:
                out[n]["lit"] += 1; out[n]["bright"] += float(mx[on].mean())
    for n, o in out.items():
        o["lit_pct"] = round(100 * o["lit"] / max(o["n"], 1), 1)
        o["bright_when_lit"] = round(o["bright"] / max(o["lit"], 1), 0)
        o["frames_sampled"] = o.pop("n")
    return out


# ----------------------------------------------------------------------------- PROPS.md
def write_props_md(out_dir: Path, show: Path, models, groups, vocab, drawings):
    rl = vocab.get("render_lit") or {}
    L = []
    L.append(f"# {show.name}: what each prop IS, and how the reference uses it\n")
    L.append(f"Generated by `profile.py` from `xlights_rgbeffects.xml` and `{vocab['reference']}` ({mmss(vocab['duration_s'])}, {vocab['effects']} effects, rows profiled: {len(vocab['rows'])}). **Read it, correct it, then sequence.** Drawings: `props/` ({len(drawings)} files). Verbatim settings per row: `vocabulary.json`.\n")
    L.append("## Models\n\n" + ("ref lit % = share of the reference's own RENDER this model is lit (> 5 % of its nodes above 32), "
             "and its brightness when lit, from `--render` (fseq.py + layout.py).\n\n" if rl else "")
             + "| model | what it is | where (x, y) |" + (" ref lit % | bright |" if rl else "") + "\n|---|---|---|" + ("---|---|" if rl else ""))
    for name, m in sorted(models.items(), key=lambda kv_: (kv_[1]['DisplayAs'], kv_[0])):
        extra = f" {rl[name]['lit_pct']:.0f} | {rl[name]['bright_when_lit']:.0f} |" if name in rl else (" | |" if rl else "")
        L.append(f"| {name} | {describe(name, m, groups)} | {m['WorldPosX']:.0f}, {m['WorldPosY']:.0f} |" + extra)
    L.append("\n## Groups (what each expands to)\n\n| group | members | leaf models |\n|---|---|---|")
    for g, mem in groups.items():
        L.append(f"| {g} | {', '.join(mem)[:160]} | {len(leaf_models(g, models, groups))} |")
    L.append("\n## The reference, per row\n\nkind · effects · % of song lit · median ms · layers (lit % per layer, held-back effects excluded) · effect types (n, median ms, ≤1 s share, top fades, top buffer style)\n")
    L.append("| row | kind | n | lit % | median | layers | effects |\n|---|---|---|---|---|---|---|")
    for name, r in sorted(vocab["rows"].items(), key=lambda kv_: -kv_[1]["n"]):
        effs = "; ".join(f"**{e}** {v['n']}× {v['median_ms']}ms ≤1s {int(v['share_le_1s']*100)}% fades {v['fades'][0][0]}/{v['fades'][0][1]} {v['buffer_styles'][0][0]}"
                         + (f" track {v['timing_tracks'][0][0]}" if v['timing_tracks'] else "")
                         for e, v in sorted(r["effects"].items(), key=lambda kv_: -kv_[1]["n"])[:5])
        ll = " ".join(str(int(x["lit_usable"] * 100)) for x in (r.get("layer_lit") or [])[:8]) + ("…" if len(r.get("layer_lit") or []) > 8 else "")
        L.append(f"| {name} | {r['kind']} | {r['n']} | {int(r['coverage']*100)} | {int(r['median_ms'])} | {r['layers']} ({ll}) | {effs} |")
    mir = [(n, r) for n, r in vocab["rows"].items() if r.get("mirrored_members")]
    L.append("\n## Mirrored members\n\nMembers that RUN the other way from the rest of their row, read from the layout "
             "(a Custom grid's node-1 column; a two-point model's X2/Y2; a Poly Line's first-to-last point; Dir/StartSide). "
             "On these rows a DIRECTIONAL effect is written only in a preview-space buffer style or with a symmetric chase type.\n")
    if mir:
        L.append("| row | mirrored members | preview-space styles in this row's vocabulary |\n|---|---|---|")
        for n, r in sorted(mir):
            L.append(f"| {n} | " + "; ".join(f"{m['model']} ({m['why']})" for m in r["mirrored_members"]) +
                     f" | {', '.join(r['direction_safe_styles']) or 'none'} |")
    else:
        L.append("- none found in the layout")
    sl = [(n, r["slice_starts"]) for n, r in vocab["rows"].items() if r.get("slice_starts", {}).get("starts")]
    L.append("\n## Slice starts in the reference\n\nstarts at which a SubBuffer slice begins: lone (one slice) / full "
             f"(>= 2 boxes tiling >= {int(SET_UNION_MIN*100)} %) / partial. Only FULL sets are ever placed; the lone and partial ones were "
             "under the reference's baked media and nobody saw them.\n\n| row | starts | lone | full | partial |\n|---|---|---|---|---|")
    for n, s in sorted(sl, key=lambda x: -x[1]["starts"]):
        L.append(f"| {n} | {s['starts']} | {s['lone']} | {s['full']} | {s['partial']} |")
    L.append("\n## Copies (identical effect lists)\n\n" + ("\n".join(f"- {a} = {b}" for a, b in vocab["copies"]) or "- none"))
    nu = vocab["never_used"]
    L.append(f"\n## Never used by the reference\n\n- groups: {', '.join(nu['groups']) or 'none'}\n- models as rows: {', '.join(nu['models']) or 'none'}")
    w = vocab["whole_file"]
    L.append("\n## Whole-file habits\n\n- blend: " + ", ".join(f"{a} {c}" for a, c in w["blend"]) +
             "\n- fades (in/out): " + ", ".join(f"{a[0]}/{a[1]} {c}" for a, c in w["fades"]) +
             "\n- in transitions: " + ", ".join(f"{a} {c}" for a, c in w["in"]) +
             "\n- out transitions: " + ", ".join(f"{a} {c}" for a, c in w["out"]) +
             "\n- value curves active: " + ", ".join(f"{a} {c}" for a, c in w["vc"]))
    L.append("\n## Owner's notes\n\n(Write here what the tool cannot know: what a prop looks like in the yard, what it must never do, which rows are the heroes.)\n")
    (out_dir / "PROPS.md").write_text("\n".join(L))


def find_reference(show: Path):
    cands = [p for p in show.rglob("*.xsq") if not any(part in ("analysis", "Backup", "_archive") for part in p.parts)]
    if len(cands) == 1:
        return cands[0]
    raise SystemExit(f"need --reference: found {len(cands)} .xsq in {show}: {[str(c.relative_to(show)) for c in cands][:6]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show", nargs="?", help="the show folder (holds xlights_rgbeffects.xml); omit it to take the one above --reference")
    ap.add_argument("--reference", help="the finished .xsq to profile (default: the single .xsq in the show)")
    ap.add_argument("--out", default=".", help="where PROPS.md, vocabulary.json and props/ are written (default: the current directory; never the show folder unless you say so)")
    ap.add_argument("--min-uses", type=int, default=5)
    ap.add_argument("--render", help="the reference's own saved .fseq: adds render_lit per model (fseq.py + layout.py)")
    ap.add_argument("--held-back", help="comma-separated effect names to exclude from the `usable` lit shares (default: the HELD_BACK list)")
    ap.add_argument("--no-draw", action="store_true")
    a = ap.parse_args()
    if a.show:
        show = Path(a.show).expanduser().resolve()
    elif a.reference:
        show = show_folder_of(Path(a.reference).expanduser().resolve())
    else:
        raise SystemExit("give a show folder, or --reference <xsq> inside one")
    if not (show / "xlights_rgbeffects.xml").exists():
        raise SystemExit(f"{show} has no xlights_rgbeffects.xml")
    ref = Path(a.reference).expanduser().resolve() if a.reference else find_reference(show)
    out_dir = Path(a.out).expanduser().resolve(); out_dir.mkdir(parents=True, exist_ok=True)
    held_back = {x.strip() for x in a.held_back.split(",") if x.strip()} if a.held_back is not None else HELD_BACK
    models, groups, bg, preview = read_layout(show)
    print(f"layout: {len(models)} models, {len(groups)} groups; reference: {ref.relative_to(show) if ref.is_relative_to(show) else ref}")
    drawings = [] if a.no_draw else draw(out_dir, show, models, bg, preview)
    vocab = profile_reference(ref, models, groups, a.min_uses, held_back)
    unknown = [r for r, v in vocab["rows"].items() if v["kind"] == "UNKNOWN"]
    if unknown:
        print(f"WARNING: the reference has {len(unknown)} rows the layout does not know: {unknown[:8]}")
    if a.render:
        lm = render_lit(show, Path(a.render).expanduser().resolve(), models)
        vocab["render_lit"] = {n: {"lit_pct": d["lit_pct"], "bright_when_lit": d["bright_when_lit"]} for n, d in lm.items()}
        vocab["render_lit_source"] = Path(a.render).name
        print(f"render_lit from {Path(a.render).name}: {len(lm)} models, mean lit {sum(d['lit_pct'] for d in lm.values()) / max(len(lm), 1):.0f} %")
    (out_dir / "vocabulary.json").write_text(json.dumps(vocab, indent=1))
    write_props_md(out_dir, show, models, groups, vocab, drawings)
    print(f"rows profiled {len(vocab['rows'])}; copies {vocab['copies']}; never used: {len(vocab['never_used']['groups'])} groups, {len(vocab['never_used']['models'])} models as rows")
    print(f"wrote {out_dir/'PROPS.md'}, {out_dir/'vocabulary.json'}, {len(drawings)} drawings in {out_dir/'props'}")


if __name__ == "__main__":
    main()
