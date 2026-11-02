# tools/

Read-only helpers for judging an xLights sequence by its **file** and its **render**. Positions
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

## Dependencies

- Python 3.12; `lxml`, `numpy`, `zstandard`; `pillow` for `snap.py` (or
  `uv run --no-project --with pillow --with lxml --with zstandard --with numpy --python 3.12 python snap.py …`).
- `validate.py` lip-sync checks want `soundfile` + `librosa` and `<song>/media/stems/<media stem>/vocals.wav`
  (else `DID NOT RUN`); word checks read xLights' dictionaries (`/Applications/xLights.app/Contents/Resources/dictionaries`
  or `$XLIGHTS_DICTIONARIES`).
- `xl.py`: xLights 2026.17+ with the API port on (Preferences → Output → API Port → Port A 49913, or `-a`).
  Not running: the tool says so, exit 1.

Rules encoded: readers scope to `<ElementEffects>`; byte index = absolute channel − 1; one render at a
time, save before close; no check skips quietly: each says `ok`, `WARN`, `FAIL`, `n/a` or `DID NOT RUN`.
