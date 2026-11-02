# tools/

Helpers for judging an xLights sequence by its **file** and its **render**; all read-only except `marktrack.py`
(writes a timing track) and `profile.py` (writes its reports to `--out`). Positions
print as `m:ss`, never raw seconds. Run from anywhere; each tool puts its own folder on `sys.path`.

| Tool | What it is | CLI |
|---|---|---|
| `tc.py` | Timecode formatting: `mmss`, `mmss_ms`, `span`, `dur`. | library |
| `fseq.py` | FSEQ v2 reader (zstd / zlib / raw; sparse ranges laid out at absolute channels). `rgb(frame, abs_start, node)` takes a **1-based** node and does the byte-index −1 itself. | library |
| `layout.py` | The show's channel layout from its own `xlights_rgbeffects.xml` + `xlights_networks.xml`: per-model absolute start channel, stride (3, or 4 for RGBW), submodel node lists, group expansion. | library |
| `validate.py` | Pre-flight checks on a `.xsq`: names, overlaps, sub-frame effects, bed shimmer, prop buffers, timing tracks vs `casting.json`, tune-to sign, mini trees vs MegaTree, buried gestures, word/viseme agreement, words verified + broken down, lip-sync vs the vocals stem, muddy gradients. A prop the layout lacks → `n/a … no such prop in this layout`. Exit 1 on FAIL. | `validate.py <song.xsq> <show folder> [<sections.json>]` |
| `measure.py` | The dials of a window: effects/s, median duration, onset lock, layers, effect mix, colour vs scene, onset coverage, house coverage, per-element load. Needs `analysis/beats.json`. | `measure.py <song.xsq> <from s> <to s> [<song folder>] [<show folder>]` |
| `xl.py` | Drive the running xLights through its API (port 49913): `status`, `open`, `render` (one at a time, lockfile), `save` (waits for the `.fseq` to settle), `close` (refuses over unsaved edits). `reload` / `check` are refused. | `xl.py status \| open <xsq> \| render \| save \| close [--discard]` |
| `effects_diff.py` | Re-baseline after an xLights save: compare two `.xsq` by content (element, effect, start/end frame), never by raw string. | `effects_diff.py <A.xsq> <B.xsq>` |
| `snap.py` | A still of one prop decoded from a saved `.fseq` at a timestamp, nodes placed from the layout geometry; per-submodel table; frame strip. Deterministic. | `snap.py --fseq <f.fseq> --model <name> --at <m:ss[.t]> [--sub] [--out png] [--strip a..b --step s]` |
| `housesnap.py` | A still of the WHOLE yard from one saved `.fseq` frame (every stored model at its layout position) plus a JSON report; contact sheets of up to 40 frames. Pillow. | `housesnap.py <song.fseq> --at <m:ss> [--show <folder>] [--out png]`; `housesnap.py <song.fseq> <a> <b> --step s` |
| `yardvideo.py` | The yard as a video of a saved render with the song's audio, for a window or the whole song; floods drawn as glows at their pixel size. Pillow + ffmpeg. Wait for its `wrote` line before sending the file. | `yardvideo.py <song.fseq> <show folder> <audio> <out.mp4> [--from m:ss --to m:ss] [--still m:ss]` |
| `houseread.py` | Per bar, the main colour the props around a flood group (or in followed groups) actually show in the render: hue buckets, share, level. The input for floods that match the house. | `houseread.py <song.fseq> --xsq <song.xsq> --group <flood group> [--follow "G1,G2"] [--series json]` |
| `radius.py` | Direction of a whole-house effect: radial centroid of lit energy per step (falling = inward). Direction is not brightness. | `radius.py <song.fseq> <start s> <end s> [--step 0.2] [--skip "a,b"]` |
| `litaudit.py` | Share of the song each prop is lit in the render, darkest first, with the rows that reach it. Run it before the owner's look. | `litaudit.py <song.fseq> [--show <folder>] [--under %]` |
| `profile.py` | Profile the show's reference `.xsq` per ROW and per SETTING into `vocabulary.json` + `PROPS.md`; draws every Custom model from its grid and maps all models on the photo; `--render` adds per-model lit % from the saved `.fseq`. Writes to `--out`, never the show folder. | `profile.py <show folder> [--reference <f.xsq>] [--out <dir>] [--render <f.fseq>] [--min-uses 5] [--held-back a,b] [--no-draw]` |
| `marktrack.py` | Write a one-layer timing track of measured marks (snaps, claps, a pulse) from `analysis/<marks>.json` into BOTH `<DisplayElements>` and `<ElementEffects>`, after a named track; snaps to the frame grid, backs up to `analysis/<song>.vNN-<tag>.xsq`; refuses an existing track (unless `--replace`), overlapping marks, a file xLights holds open. | `marktrack.py <song.xsq> analysis/marks.json --dry-run \| --apply [--replace] [--tag <word>]` |

## Dependencies

- Python 3.12; `lxml`, `numpy`, `zstandard`; `pillow` for `snap.py`, `housesnap.py`, `yardvideo.py` and the drawings of `profile.py`; `ffmpeg` on the PATH for `yardvideo.py` (or
  `uv run --no-project --with pillow --with lxml --with zstandard --with numpy --python 3.12 python snap.py …`).
- `validate.py` lip-sync checks want `soundfile` + `librosa` and `<song>/media/stems/<media stem>/vocals.wav`
  (else `DID NOT RUN`); word checks read xLights' dictionaries (`/Applications/xLights.app/Contents/Resources/dictionaries`
  or `$XLIGHTS_DICTIONARIES`).
- `xl.py`: xLights 2026.17+ with the API port on (Preferences → Output → API Port → Port A 49913, or `-a`).
  Not running: the tool says so, exit 1.

Rules encoded: readers scope to `<ElementEffects>`; byte index = absolute channel − 1; one render at a
time, save before close; no check skips quietly: each says `ok`, `WARN`, `FAIL`, `n/a` or `DID NOT RUN`.
