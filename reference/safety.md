# Safety: what breaks xLights automation, and the refusals that stop it

Every item here was written down after it broke something, most of them twice. Where the shipped toolkit has a
refusal, it is named; where it does not, the hand-check is the minimum. Positions are m:ss, never raw seconds.
Lines marked **[SPECIFIC]** are the show this was learned on (an Intel MacBook Pro, Radeon Pro Vega 16, a 94,080-channel
matrix, xLights 2026.17); the mechanism is general, the numbers are not.

## 1. GPU rendering OFF in Preferences; then `Fire` is fine

[SPECIFIC origin, general caution] With GPU rendering ON, xLights' Metal shaders for `Fire` (`FireAdvanceEffect` /
`FireDrawEffect`) passed validation and never advanced an instruction (`ContentValidation = PASS`, `Execution point 0x0`)
while `WindowServer` waited on the same card: nine GPU resets and two hard reboots in one morning (2026-09-08). Parameters
did not matter and the hang was intermittent: the same file had rendered ~12 times the day before. The owner turned GPU
rendering OFF; same sequence, 24 Fires, 94,080 channels: **23.2 s mean on the GPU vs 22.5 s on the CPU**. No cost, and the
shader is never submitted. Since then `Fire` is allowed (the owner, 2026-09-12: *"fire is always allowed, turning gpu off is
fine"*). `Shader` effects are the one type with no CPU implementation, so GPU-off does not rescue them.

The residual risk is a preferences reset turning GPU rendering back on: a sequence carrying Fires will then freeze the
machine again. `validate.py` check 0 counts the Fires as **info** so you know the file is armed.

On macOS the flag xLights reads lives in `~/Library/Containers/org.xlights/Data/Library/Application Support/xLights/` as
`settings.json` → `"xLightsGPURendering"` (its start-up log names the file); the old `xLights Preferences` file can disagree.

Hand-check: `grep -c 'name="Fire"' <xsq>` (scoped to `<ElementEffects>`, §5), and ask the owner whether GPU rendering is off.

## 2. ONE render at a time; nothing touches the sequence while it is in flight

What took the GPU down was churn and queue depth, not automation itself: `renderAll` + close/open + `checkSequence`
inside 90 s (4 GPU resets in 80 s, 2026-09-02), and a cold headless `xLights -r` of the whole sequence (2026-09-04). One API
`renderAll` on the open sequence, warm cache, nothing else running, completes cleanly (tested, including cold, 23.4 s).

- `xl.py render` takes a lockfile; a second render refuses; `close` / `open` / `save` refuse while it is held.
- `reload` (= close + open + renderAll) is never exposed; neither is `checkSequence` (`validate.py` covers it).
- Headless `-r` is a last resort with xLights closed, GPU rendering off, once, with the owner watching. It launches a
  second instance and can migrate the show folder format.
- The render cache is keyed `Effect_Element_layer_starttime`, so a file a tool has just regenerated misses almost everywhere
  and the whole sequence is queued in one burst: a COLD cache is the worst case for queue depth. Prefer a warm one.
- **A render writes no `.fseq`; a save does.** Since xLights 2026.17 the API can save (`saveSequence`). The loop is
  `open → render → save`, serial, nothing between. **Wait until the `.fseq` stops growing (2 s stable) before reading it**:
  a read during the save sees a black show.

Hand-check: one render, then one save, then read. If anything else ran in between, you do not know what you rendered.

## 3. The LOADED SHOW FOLDER is part of a sequence's identity

Models and groups are per show folder. Opening, rendering or saving a sequence while xLights has a *different* show loaded
writes out every model that layout lacks, silently. `xl.py` asks `getShowFolder` first and refuses on a mismatch
(2026-09-19). Hand-check: the folder in xLights' title bar is the folder the `.xsq` lives under.

## 4. xLights holds the sequence (and the owner's unsaved edits) in memory

- A close discards them. **Save before close.** A chain that rewrites a file xLights has open must save first, then close,
  then write, then open. Autosave is not the hazard: it writes `<sequence>.xbkp` beside the file and *"No render created"*.
  It fires every 3 minutes by default (`AutoSaveInterval`) and *skips* when nothing changed since the last save, while
  playing, while suspended and during a batch render; a file written while xLights was closed never trips it at all.
  When the owner's work is missing, look in the `.xbkp`. `xl.py close` refuses while the `.xbkp` is newer than the `.xsq`.
- **The owner's hand edits outrank every tool.** Diff the saved file against **your last write** (never against a copy
  taken after their save) with `effects_diff.py`, and carry what they changed. A tool that regenerates a track the owner has
  edited by hand must refuse; the only legal direction is reading their edits back into config.
- Never write a `.xsq` that xLights has open. On 2026.17+ edit the open sequence through the API (`getEffectSettings` /
  `setEffectSettings`) so there is no stale copy at all.

## 5. Every reader and writer scopes to `root.find("ElementEffects")`

An `.xsq` carries `<Element type="model">` twice: in `<DisplayElements>` (the sequencer's view list) and in
`<ElementEffects>` (the effects). The view list comes first. `root.iter("Element")` once wrote 199 effects into the view
list and every count written the same way "confirmed" them; the owner saw nothing (2026-09-04). Its mirror: **a new row
must be added to BOTH lists**: xLights silently drops an `ElementEffects` row the view list does not know (2026-09-22).

Hand-check (the fastest proof an effect is real):
```
awk '/<ElementEffects>/,/<\/ElementEffects>/' "<xsq>" | grep -c 'name="Faces"'
```
The owner's *"I don't see it"* outranks any count from your own code.

## 6. An xLights Save rewrites the whole file: re-baseline after every save

Times snap to the 25 ms frame, settings and palette strings normalise, EffectDB / ColorPalettes re-index. Compare by
(element, effect name, start ± 1 frame, end ± 1 frame, settings, palette), never by raw string. A string diff once
reported 458 lost / 461 added that were really 0 / 6. Off-grid times you wrote snap on save (5680 → 5675), so write on the
grid and judge reproduction by content.

## 7. Row order and layer order are load-bearing

- xLights paints **rows** in sequencer order: a later row paints over an earlier one, but only where it DRAWS (alpha
  blend). A prop's own effects show over a group bed only if the prop's row sits *below* the group's. Never re-sort the
  owner's rows (a writer once sorted alphabetically and destroyed a hand-arranged view); a fix is a narrower row appended at
  the end, never a move.
- Inside one element the rule flips: **layer 0 is on TOP** (79 vs 886 white nodes, 2026-09-11).
- A WIDER element on a LATER row buries the narrower one under it: check what is already on those pixels before placing
  (`validate.py` check 9 flags it).

## 8. Placers: deterministic, on the grid, append-only, idempotent

- `--dry-run` twice and diff before applying; the file must match a placement list the owner actually saw; no sets
  feeding a greedy pick.
- Append-only into free spans of the tool's own submodels: legal inside an approved range, and a second run adds 0.
- An idempotent cleanup matches on the **target**, not just the times: a flame tool once deleted the matrix's own Fire
  because the window had been derived from it. Never touch an element the run is not writing to.
- Past the show's own layer depths is accumulation, not composition.
- A tool that writes its own input must never read its own output as ground truth (an aligner once narrowed every run
  from the run before).

## 9. A model's default buffer is its WIRING, not its shape

A Single Line or a 1-arch Arches model is ONE PIXEL TALL, so any directional effect renders as a solid fill. Compute the
buffer rows first (Arches `NumArches`, Single Line `NumStrings`, Custom `CustomHeight`, Tree `NodesPerString /
StrandsPerString`); one row means `Per Model Per Preview` + 2D. An irregular multiprop wants `Per Model Default Deep`.

## 10. Reading a render

- **Byte index = absolute channel − 1.** `fseq.rgb()` takes a **1-based node** and does the −1 itself; passing `node-1`
  shifts every reading by one node and still looks plausible (2026-09-06). Stride 3 for RGB; an RGBW model needs its own
  base + stride 4 (`layout.py`). Read raw and you get (G, B, R-of-next-node).
- **No bounds checking**: past a model's node count you read its neighbour. Bound by the next model's start channel.
- **An FSEQ is SPARSE**: xLights stores only the channels of models in that song, and numbers No-Controller models itself
  (by name, after the last controller). Read through `fseq.FSEQ.frame()`, which lays the ranges out at absolute channels;
  a model not in the song reads dark.
- **A sequence whose LENGTH changed keeps the old `.fseq`'s frame count** through open + render + save (5:58 of frames on a
  4:21 song = dead air on the player, 2026-10-07). Move the old `.fseq` aside before opening; check the header's frame count.
- Sample **strictly inside** a span and take the peak over the span; a boundary frame holds the neighbour's last frame.
- **Count lit pixels on EXCLUSIVE nodes; never `max()` over overlapping submodels.**
- Confirm the channel mapping on a frame you can predict before trusting any reading.
- **Export House Preview Video defaults to the FILM's path**: retype the output path every time.

## 11. Audio and lyrics

- A cut sequence carries the source's alignment: words land in a join's silence or on bleed (`validate.py` check 12b).
- Never prime a transcriber with the words you hope to find: it finds them (a 166 Hz synth note became "hee hee").
- A flat pitch line in the vocals stem is instrument bleed, not a voice. Never write lyrics from memory into any file.

## 12. Hygiene

- Keep tools in one folder and analysis beside the song; a scratch directory is wiped.
- Never install into the analysis venv from a research session.
- Installed and latest are two different questions: the app's `Info.plist` vs the GitHub releases page; numbering is year.week.
- A check that quietly skips is worse than no check: **`DID NOT RUN` is a failure. Fix it first.**
