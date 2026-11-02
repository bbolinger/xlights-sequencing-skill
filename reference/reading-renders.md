# Reading a saved render as a whole yard

`snap.py` shows one prop. These five tools read the same saved `.fseq` as the whole yard: a still, a
video, the colour each part of the house shows per bar, the direction a whole-house effect travels,
and how much of the song each prop is lit. All of them are READ-ONLY: no render, save, playback,
video export, sequence edit or layout edit happens. Only the saved render is read, so unsaved or
unrendered timeline edits cannot be seen (a newer `.xsq` or layout file prints `POSSIBLY STALE`).

| Question | Tool | Command |
|---|---|---|
| What does the yard look like at 0:16? | `housesnap.py` | `housesnap.py <song>.fseq --at 0:16 --out yard.png` (contact sheet: `<song>.fseq 0:16 0:18 --step .5`, at most 40 frames) |
| What does it look like over time, with the song? | `yardvideo.py` | `yardvideo.py <song>.fseq <show folder> <audio.mp3> out.mp4 --title "<song>" [--from 0:30 --to 0:40]` |
| What colour does the house show around each flood, per bar? | `houseread.py` | `houseread.py <song>.fseq --xsq <song>.xsq --group <flood group> [--follow "Garage Doors,Windows,Peaks"]` |
| Is this whole-house gesture moving inward or outward? | `radius.py` | `radius.py <song>.fseq <start s> <end s> [--step 0.2] [--skip "<matrix>,<sign>"]` |
| Which props are dark for most of the song? | `litaudit.py` | `litaudit.py <song>.fseq [--show <show folder>] [--under 5]` |

## What each needs

- **A saved `.fseq`.** A render does not write it; a Save does. Wait until the file stops growing (2 s
  stable) before reading it, or you read a black show. `housesnap.py` refuses if the file changes while
  it is being read.
- **The layout:** the show folder's `xlights_rgbeffects.xml` (every model's geometry and submodels) and
  `xlights_networks.xml` (controller bases, in definition order, never a hardcoded table). The folder is
  an argument, or the first folder above the `.fseq` that holds `xlights_rgbeffects.xml` (`layout.show_folder_of`).
  `yardvideo.py` accepts an OLD show folder (a backup) so an old render is drawn on the layout it was made for.
- **Pillow** for `housesnap.py` and `yardvideo.py` (the other three run without it):
  `uv run --no-project --with pillow --with lxml --with zstandard --with numpy --python 3.12 python <tool> ...`
- **ffmpeg** on PATH for `yardvideo.py`; **numpy** for `litaudit.py`.
- `houseread.py` also reads the `.xsq` for the timing track whose marks are the bar edges (`--bars`, default `Bars`).

## The two rules that matter

1. **Sample strictly inside a span and take its peak.** An effect's first and last frames belong to its
   neighbours as often as to it (fades, 25 ms snapping, blending with the layer below). Judge a span
   by frames well inside it, and judge "is it lit" by the brightest sample, not the mean.
2. **Count lit pixels on EXCLUSIVE nodes; never `max()` over overlapping submodels.** Two submodels that
   share nodes are not two sets of lit pixels. Resolve a group to its concrete leaves (`Layout.expand`),
   read each model once at its absolute channels (byte = absolute channel minus 1; `fseq.rgb()` takes a
   1-based node and does the subtraction itself), and bound a model by the NEXT model's start channel,
   because `fseq.rgb()` does no bounds checking and a neighbour's channels look plausible.

## What is trustworthy, and what is approximate

- Colours come from the requested frame, at the header's frame interval, floor-selected; both the requested
  and the actual m:ss.mmm are recorded. An RGBW node consumes four bytes; its white is added for display.
- An FSEQ is **sparse**: xLights stores only the channels of models used in the sequence (plus No Controller
  models it numbers by NAME after the last controller). `fseq.FSEQ.frame()` lays the ranges back out at
  absolute channels; a model with no stored channels is skipped and NAMED (`NOT IN THIS SEQUENCE`), never
  drawn dark as if sequenced. A model only PARTLY stored makes `housesnap.py` refuse; `yardvideo.py` draws
  its unstored nodes dark, as they are on the lawn, and says so on stderr.
- The pictures are a **2D reconstruction**, not a House Preview screenshot: custom grids, wiring direction,
  scale, rotation and world position come from the layout; trees use the cone dimensions and strand angles
  in a front projection; arches, polyline spacing and window frames are approximations (listed per model
  in the JSON). No perspective, depth occlusion, background photo, glow, gamma or dimming. Where two LEDs
  share a screen pixel the brighter paints last; for numbers, decode the `.fseq` (`snap.py`, `fseq.rgb`).
- Unsupported geometry, colour order or channel reference fails loudly rather than omitting a model or
  reading its neighbour's channels.
- `houseread.py` weights each prop ONCE per frame by its lit share and brightness, so a matrix holding most
  of the channels is one prop, not the picture: never tune against a global mean.
- `radius.py` reports direction, which brightness cannot: a mean radius FALLING is energy collecting toward
  the middle, RISING is spreading outward. A thick wave that lights everything cannot move.

## Workflow

Open the PNG with the image-viewing tool; producing a filename is not inspecting it. A still cannot prove
motion: sample several nearby frames (the contact sheet) or make the video of just the changed window.
`yardvideo.py` prints "models drawn" at the START; send nothing until its "wrote ... N frames" line and an
`ffprobe` of the duration. `litaudit.py` after every first render: a prop under 5 %, or lit only by a
whole-house bed, is a suspect the owner will otherwise find by eye. What the owner sees on the lawn
outranks any number from these tools.
