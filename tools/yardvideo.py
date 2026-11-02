#!/usr/bin/env python3
"""yardvideo.py -- a whole-yard video of a SAVED render, with the song's audio, for the owner to watch.

    uv run --no-project --with pillow --with lxml --with zstandard --with numpy --python 3.12 python yardvideo.py \
        <song>.fseq <show folder> <song audio.mp3> <out.mp4> [--title "<song>"] [--fps 20] [--width 1280] \
        [--from m:ss --to m:ss] [--tail 1.0]              # or --still m:ss to write one PNG instead

Reads: the saved `.fseq`, the show folder's `xlights_rgbeffects.xml` + `xlights_networks.xml` (every model's
geometry and absolute channels, through housesnap's geometry and channel checks) and the audio file. Needs
`ffmpeg` on PATH. Draws every frame as a 2D reconstruction (not xLights' House Preview) and muxes the audio.
A node is drawn at its model's own layout PixelSize: a one-node flood with a large PixelSize becomes a soft
wall-wash glow behind the props (2026-10-11) instead of an invisible dot. The show folder may be an OLD show
folder (a backup) to draw an old render on the layout it was made for: pre-2026 files ("Tree 180", parm1/2/3)
are translated. A model the song reaches only through some submodels is "partly stored" in a sparse FSEQ; its
unstored nodes are drawn dark, as on the lawn. Written 2026-10-05. About 3 min for a 3-minute song at 20 fps.

--from / --to (m:ss or seconds): only that window, with its own audio slice (the owner, 2026-10-23: only the
patched portion is needed). --tail S: S seconds of black after the sequence's last frame, as the yard goes
dark when the show stops (default 1.0; none when --to ends before the sequence does).

Writes: the `.mp4` (video encoded first, audio muxed after it with no -shortest: piped frames plus -shortest
cut the last 8 s of audio off every preview; the owner, 2026-10-23: the previews never had audio at the end,
so the sequence had to be watched in xLights instead). Prints to stderr: "<N> models drawn; not in render:
[...]", any "partly stored" model, and finally "wrote <out>: <frames> frames (<m:ss.mmm>-<m:ss.mmm>[ + tail])".
Wait for the "wrote" line before sending the file anywhere: "models drawn" prints at the start.
"""
import sys, math, subprocess, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import housesnap as hs
from PIL import Image, ImageDraw
from lxml import etree as E
import copy
_geo = hs.geometry
PARMS = {"Arches": ("NumArches", "NodesPerArch", "LightsPerNode"), "Window Frame": ("TopNodes", "SideNodes", "BottomNodes"),
         "Custom": ("CustomWidth", "CustomHeight", "Depth"), "Single Line": ("NumStrings", "NodesPerString", "LightsPerNode"),
         "Poly Line": ("PolyStrings", "NodesPerString", "LightsPerNode"), "Circle": ("NumStrings", "NodesPerString", "LightsPerNode")}
def _geometry(m):
    k = m.get("DisplayAs") or ""
    if m.get("parm1") is not None:   # pre-2026 attribute names
        m = copy.deepcopy(m)
        for src, dst in zip(("parm1", "parm2", "parm3"), PARMS.get(k, ("NumStrings", "NodesPerString", "StrandsPerString"))):
            if m.get(src) is not None and m.get(dst) is None: m.set(dst, m.get(src))
    if k.startswith("Tree ") and k.split()[1].isdigit():   # pre-2026 files: "Tree 180" = Tree, 180 degrees
        m = copy.deepcopy(m); m.set("DisplayAs", "Tree")
        if not m.get("TreeDegrees"): m.set("TreeDegrees", k.split()[1])
    return _geo(m)
hs.geometry = _geometry
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("fseq"); ap.add_argument("show"); ap.add_argument("audio"); ap.add_argument("out")
ap.add_argument("--fps", type=float, default=20); ap.add_argument("--width", type=int, default=1280); ap.add_argument("--still"); ap.add_argument("--title", default="")
ap.add_argument("--from", dest="t_from", default=None); ap.add_argument("--to", dest="t_to", default=None)
ap.add_argument("--tail", type=float, default=1.0)
a = ap.parse_args()
fs = hs.FSEQ(Path(a.fseq)); show = Path(a.show).expanduser()
roots = E.parse(str(show / "xlights_rgbeffects.xml")).getroot().find("models")
bases = hs.bases_from_network(show); starts = {m.get("name"): hs.start_channel(m, bases) for m in roots}
ranges = hs.sparse_ranges(fs); span = max(s + n for s, n in ranges); models = []; absent = []
for m in roots:
    pos, note = hs.geometry(m)
    stride = 4 if m.get("StringType") == "RGBW Nodes" else 3; base = starts[m.get("name")]; end = base + max(pos) * stride - 1
    if not any(s <= base - 1 and end <= s + n for s, n in ranges):
        if not any(base - 1 < s + n and end > s for s, n in ranges):
            absent.append(m.get("name")); continue
        # partly stored: the song reaches only some submodels; unstored channels read 0 = dark, as on the lawn
        print(f"{m.get('name')}: partly stored (unstored nodes drawn dark)", file=sys.stderr)
    nextbase = min([s for s in starts.values() if s > base] + [span + 1])
    if base < 1 or end >= nextbase: raise SystemExit(f"{m.get('name')}: channels overlap next model / exceed FSEQ")
    models.append((m, pos, base, stride))
print(f"{len(models)} models drawn; not in render: {absent}", file=sys.stderr)
allxy = [xy for m, pos, b, s in models for xy in pos.values()]; xs, ys = zip(*allxy)
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys); W = a.width; scale = (W - 40) / (x1 - x0); H = math.ceil((y1 - y0) * scale) + 70; H += H % 2
font = hs.font(18)
# A model's own PixelSize (layout) is how big xLights draws each node: a flood is ONE node at a large size (a soft wall
# wash, Antialias 3 = blended circle), everything else about 2. Drawn as a 2 px dot the floods were invisible (the owner,
# 2026-10-11: the floods did not show in the video, tiny dots, while the layout draws them much bigger). Nodes over 4 px
# draw as a soft glow of that diameter (layout units -> video), BEHIND the props, brightest-wins where glows overlap.
from PIL import ImageChops
_masks = {}
def _glow_mask(R):
    if R not in _masks:
        g = Image.new("L", (2 * R, 2 * R)); px = g.load()
        for yy in range(2 * R):
            for xx in range(2 * R):
                dd = math.hypot(xx - R + .5, yy - R + .5) / R
                px[xx, yy] = int(255 * max(0.0, 1 - dd) ** 1.4)
        _masks[R] = g
    return _masks[R]
def draw(idx):
    frame = hs.read_frame(fs, idx, ranges); img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img); dots = []; glows = []
    for m, pos, base, stride in models:
        mx = m.get("DisplayAs") == "Matrix"
        psz = float(m.get("PixelSize") or 2)
        for n, (x, y) in pos.items():
            off = base - 1 + (n - 1) * stride; rgb = list(frame[off:off + 3])
            if stride == 4: rgb = [min(255, v + frame[off + 3]) for v in rgb]
            if not max(rgb): continue
            if psz > 4: glows.append((20 + (x - x0) * scale, 45 + (y1 - y) * scale, tuple(rgb), max(3, round(psz / 2 * scale))))
            else: dots.append((max(rgb), 20 + (x - x0) * scale, 45 + (y1 - y) * scale, tuple(rgb), mx))
    for x, y, col, R in glows:
        box = (round(x) - R, round(y) - R, round(x) + R, round(y) + R)
        lit = Image.composite(Image.new("RGB", (2 * R, 2 * R), col), Image.new("RGB", (2 * R, 2 * R)), _glow_mask(R))
        img.paste(ImageChops.lighter(img.crop(box), lit), box)
    for _, x, y, col, mx in sorted(dots):
        r = 1.0 if mx else 2.0; d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    d.text((12, 10), f"{a.title} {hs.stamp(idx * fs.step)}  (last saved render, 2D)", fill=(200, 200, 200), font=font)
    return img
if a.still:
    draw(hs.milliseconds(a.still) // fs.step).save(a.out); sys.exit()
def _ms(t): return hs.milliseconds(t) if ":" in str(t) else int(round(float(t) * 1000))
end_ms = fs.frames * fs.step
t0 = _ms(a.t_from) if a.t_from else 0
t1 = min(_ms(a.t_to), end_ms) if a.t_to else end_ms
tail = a.tail if t1 >= end_ms else 0.0
import os
tmp = str(Path(a.out).with_name(Path(a.out).stem + ".video-only.mp4"))
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
                      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", "-preset", "veryfast", tmp], stdin=subprocess.PIPE)
i = 0
while True:
    ms = t0 + round(i * 1000 / a.fps)
    if ms >= t1: break
    p.stdin.write(draw(ms // fs.step).tobytes()); i += 1
black = Image.new("RGB", (W, H)); ImageDraw.Draw(black).text((12, 10), f"{a.title} -- show over (black)", fill=(120, 120, 120), font=font)
for _ in range(int(round(tail * a.fps))):
    p.stdin.write(black.tobytes()); i += 1
p.stdin.close(); p.wait()
dur = i / a.fps
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-ss", f"{t0 / 1000:.3f}", "-t", f"{(t1 - t0) / 1000:.3f}", "-i", a.audio,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-t", f"{dur:.3f}", a.out], check=True)
os.remove(tmp)
print(f"wrote {a.out}: {i} frames ({hs.stamp(t0)}-{hs.stamp(t1)}" + (f" + {tail:.1f} s black" if tail else "") + ")", file=sys.stderr)
