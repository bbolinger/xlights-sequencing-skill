---
name: xlights-sequencing-skill
description: Sequence a song for an xLights light show with the house owner in the loop: measure their own finished sequences before proposing anything, analyse the audio (onsets per stem, sections, script), place additively into a .xsq a window at a time, validate and measure it, render and save through xLights' automation API, prove the result in the decoded .fseq, and tweak one effect at a time until the owner approves. Use when asked to sequence, build, review, fix or extend an xLights .xsq, or to set up a show folder for this way of working. Not for Vixen/LOR, not for hand-placing effects in the GUI.
---

# xLights sequencing: the method

You are helping one person light one house to one song. They judge on a saved render of their own display; you never
see it. So the whole method is: **measure before you propose, propose with numbers, place additively, prove it in the
rendered pixels, and let their eye outrank every number you have.**

Read `reference/safety.md` before touching xLights or a `.xsq`: every line in it cost a crash, a lost evening of the
owner's edits, or a show that played dark. Read `reference/loop.md` before your first question to the owner.
`reference/rules.md` holds the design rules with a hand-check each; read the entry for an area before placing anything
in it, in the session doing the work. `reference/xsq-format.md` is the file format as it actually behaves.

**What ships here is the method and the checking tools** (`tools/`: `validate.py` with 17 refusing checks, `measure.py`,
`xl.py` for the xLights API, `fseq.py` + `layout.py` + `snap.py` to read a render, `effects_diff.py`, `tc.py`). The
composer that placed effects on the show we learned this on, the forced-alignment / singing-face chain and the
prop-specific tools are **not** in this release: they are entangled with one house. You bring your own placer (a script
per song, xLights' own effects placed by hand, anything) and this method tells you how to check it, how to work with the
owner, and what not to do. Lines marked **[SPECIFIC]** describe that one show (a Halloween house with singing props, a
94k-channel matrix, an Intel Mac); replace them with the owner's facts and keep the shape.

## 0. What the owner brings, and what comes back

Ask for each by name; do not guess:

1. **The show folder**: `xlights_rgbeffects.xml` (models, submodels, groups, faces) and `xlights_networks.xml`
   (controllers → absolute channels). Every name you ever write must resolve here; a typo is silent dead air.
2. **One finished `.xsq` from that show, made by the owner.** Two jobs: it is the source of **row order** (the view they
   arranged; never re-sort it) and of **calibration** (their real durations, effect types, layer depths, buffer styles,
   palettes, per row). Without it you are guessing their taste: a prop class is not a licence and averages are not
   knowledge (the owner, 2026-10-03, after a build placed by prop-name class and matched dials came out as "blink city":
   look up what each prop is and how it is grouped before placing anything on it).
3. **The song** as an mp3 in `<show>/<song>/media/`; the film or video if one exists (the palette source). Only audio the
   owner is entitled to; never download it for them.
4. **`<song>/analysis/sections.json`**: authored by the owner's ear with your proposal as the first draft
   (`examples/sections.example.json`): sections with `intensity` and `intent`, `approved[]`, `stops[]`, `built_to`.
5. **The script**, if the song has characters: who says which line. Looked up, never inferred from pitch.

Back: the `.xsq` (one file, grown window by window), `<song>/analysis/*.json` (slow to recompute, so keep them), a dated
backup of every prior version (`analysis/<song>.vN-<why>.xsq`), a baseline copy after each xLights save, and a measured
report per window in m:ss.

## 1. Set up the show once

1. xLights **2026.17 or later** with the automation port on (Preferences → Output → API Port, or launch with `-a`):
   `POST /xlDoAutomation` on 49913 gives open, close, render, **save**, get/set effect settings. Older builds cannot save
   from automation, so nothing you render can be read. `tools/xl.py status` proves the link.
2. **GPU rendering OFF in Preferences** (`reference/safety.md` §1). It is the owner's setting; ask. With it off, `Fire`
   is allowed; `Shader` effects never are (no CPU path).
3. Load the layout. For every group you might sequence, **expand it to models and submodels** and record what it
   reaches: a group named like a roof section can swallow a whole prop. `validate.py` refuses an unresolved name.
4. Record every model's **buffer rows** (Arches `NumArches`, Single Line `NumStrings`, Custom `CustomHeight`, Tree
   `NodesPerString / StrandsPerString`). One row cannot carry a directional effect: it renders as a solid fill.
5. Record the **row order** of the show's finished `.xsq` and audit it once: a prop whose own effects must show over a
   group bed sits *below* the group (a later row paints over an earlier one). Inside one element the opposite holds:
   **layer 0 is on top**.
6. **Profile the show's file per ROW and per SETTING** (`reference/rules.md#knowledge`): for every prop, which effects they
   put on it, with which keys and values, how long, how bright, in which colours. That vocabulary is the only legal source
   of placements. Then **calibrate the dials** from their finished sequences, weighted by use, excluding anything
   generated: effects/s per 10 s window, median duration, % under 500 ms, % over 2 s, onset-lock, elements lit, layer
   depth, effect mix, buffer style per target type, palette pool. Three things held across every style measured
   [SPECIFIC]: effects follow **onsets, not beats**; **10+ distinct effect types** per song; a **low steady VU Meter** under
   the vocals. Everything else is a dial.

## 2. Analyse the song (once; keep the outputs)

The analysis tools are not in this release; the method is. Keep every result in `<song>/analysis/`.

1. **Beats and onsets**: full mix plus per stem (drums, bass, vocals, other; demucs, or xLights' own ML stem separation
   in 2026.16+). An onset's weight is the **peak it rises to**, never the value at the backtracked frame.
2. **Passages**: sustain vs attack, noisy vs tonal, energy; these drive character.
3. **Figures**: successions that are one gesture ("bum bum bum"; a pickup → its note).
4. **Lyrics: the real lyric sheet first**, then transcribe the vocals stem, then **force-align** the sheet's words to the
   audio (a transcript's word bounds are arithmetic, not listening). Never prime the transcriber with the words you hope
   for: it finds them (a flat 166 Hz synth note became "hee hee"). A transcript is one stream: it mis-hears, drops lines,
   hallucinates past the end, and absorbs an overlapping singer into the dominant one. Then **the script**: cast per LINE
   from it; a recovered second voice goes into the script marked `recovered: true`, never back into the transcript.
5. **Scene palette**: per section, from the film's own frames, clustered by hue. No film? Author it by hand in
   film-frame values (dark, desaturated), say so in a `source` field, and include no near-black entry (a neutral makes
   every palette admissible).
6. **Sections**: propose from the analysis; the owner corrects by ear; each start snaps to the first real event at or
   after it. Set `intensity` per section **explicitly** (passage energy inverts on a limited master).
7. **Intent, per section, before any placement** (`rules.md#intent`): what the music does there, the motif, why, how it
   builds. A chorus motif repeats and grows. Lit time is a check, never a target. Know what an effect DOES before placing it.
8. **Stops**: measured from the stems (bass and drums at −50 dB or below), stored as data. Nothing fills a stop.
9. **Instrumental?** `"instrumental": true`; then any timing track is a failure.

## 3. Build a window at a time

The unit of work is a window `[built_to, end)` ending on a section boundary. Everything below the frontier is **carried
over untouched** (approved or merely built) because additive passes were placed against a render and cannot be
regenerated. A window:

1. **Read the last ~5 s before every seam.** Carry or depart; never start cold. Beds lead in 1-1.5 s early on their own
   layer; heroes, punches and figures land *on* the boundary. An approval that ends mid-section cannot be built onto:
   its beds' lead-ins cross the edge; re-open below them or start at the next section.
2. **Budget by section:** events/s = `0.9 + (eps_max − 0.9) · intensity^2.2` [SPECIFIC constants]. Structure (bed,
   atmosphere, hero, faces, voice, authored dark) is placed regardless; only events compete, in weight order. Quiet means
   **still**, not narrow: below ~0.55 intensity a regular figure gets ONE gesture.
3. **Weight is continuous from the full mix; the stem only routes the answer.** A whole-house punch must be big against
   the song AND against the last 4 s, or simply huge [SPECIFIC gates]; everything else answers small. Equal strikes get
   equal brightness; a rising run rises 80 → 100 %. Element rest is constant (~750 ms [SPECIFIC]); density comes from more
   of the house answering. If a section feels flat, trace where its events were SENT before re-dialling it.
4. **Identity per section:** colour from the scene; vocabulary and speed rotate; direction alternates every bar.
5. **Colour:** keep the scene's hue; translate saturation and value for LEDs. White is always allowed. A gradient between
   two saturated colours far apart in hue passes through a colour nobody chose (red→green is olive): `validate.py`
   check 17 lists them.
6. **Props in their idiom, on their own submodels:** modes on a multiprop are exclusive **by pixel**; a face owns its
   pixels while singing; eyes ride a *rendered* lit body; a creature lit only by house beds reads as unused.
7. **A character on a big canvas is mostly absence**: glimpses and rare holds on real onsets, on the element's layer 0,
   authored at the target's own buffer, hard-thresholded.
8. **Write the file:** keys copied from the show's file (an unknown key is silently ignored); per-target choices routed
   by element, never baked into a helper (**a helper's defaults are baked-in values too**); every writer scoped to
   `<ElementEffects>`; a new row in BOTH element lists; row order from the show's file; times on the 25 ms grid; no blank
   layers.
9. **Dedupe on carry-over** and cap the layer spill. Past the show's own depths is accumulation, not composition.

Then, **every time, in this order:**

```
tools/validate.py <xsq> <show folder> [<sections.json>]   # names resolve, overlaps, sub-frame effects, timing tracks vs
                                                           # casting, buffer style, buried gestures, muddy gradients …
                                                           # "DID NOT RUN" is a failure: fix that first
tools/measure.py  <xsq> <start> <end>                      # the dials per section, hue vs scene, onset and house coverage
prove   awk '/<ElementEffects>/,/<\/ElementEffects>/' <xsq> | grep -c 'name="<Effect>"'
tools/xl.py open <xsq>  →  tools/xl.py render  →  tools/xl.py save      (serial; nothing in between; safety.md §2)
tools/snap.py …  /  fseq.py                                # decode the .fseq at the exact channels, strictly INSIDE a span,
                                                           # peak over the span, then send the owner the still
```

## 4. Additive passes (after a saved render)

Eyes, a prop's idiom the generator never reaches, punches a gate wrongly demoted, a character mask: all **append-only
into free spans of the prop's own submodels**, gated on the *rendered* body where they need one. That makes them legal
inside an approved range and idempotent (a second run adds 0). Every placer is deterministic (`--dry-run` twice, diff,
show the list, apply), matches on the TARGET when cleaning up its own earlier work, and writes to no element the run is
not for. Only the answer to a measured stop may **split** an existing effect: a bed cannot be stopped by appending.

## 5. Tweak, don't regenerate

Once a section is roughly right, the unit of iteration is **one effect**: type, span, settings or palette, in place,
through the API on the open sequence, or close → edit → open. Never while a render is in flight. Regenerate a section only
when the owner says it is all wrong; a `--rebuild` that ignores the frontier destroys the additive work.

## 6. Approval and the frontier

On approval: snapshot `analysis/<song>.vN-APPROVED-<range>.xsq`, add the range to `approved[]` with the owner's words in
`why`, and verify the next run reproduces it by (element, name, start ± 1 frame, end ± 1 frame). `built_to` advances per
window. After **any** xLights save, re-baseline before the next tool run (`effects_diff.py`): a save snaps times,
normalises strings and re-indexes the palette and effect tables.

## 7. Reporting

- Positions **always m:ss**; a duration under a minute stays in seconds.
- Numbers with the command that produced them. "I placed eyes" means: N spans, on these submodels, body luma ≥ 40 inside
  every span in the decoded render at these channels, and a still of it.
- When the owner says *"I don't see it"*, they are right and your count is wrong: the raw XML of the element it should be
  in, then the `.fseq` at its channels, then the row order above it. When they say they can't see it, it is too DIM;
  never propose darker.

## What is generic and what is not

| Generic (ship as-is) | Per song (re-derive) | Per house [SPECIFIC] |
|---|---|---|
| intent before placement; knowledge before numbers; density is a property of the section; windows grow out of each other; two darknesses; identity per section; restraint; weight continuous, stems route; script over inference; keys not values; eyes ride the body; layer 0 on top inside an element; rows paint later-over-earlier; a buffer is its wiring; every check that matters refuses the file | sections, intensity, preset, palettes, script and casting, stops, effect patterns, punch thresholds, the owner's words | prop names, submodel maps, a multiprop's overlap matrix, group expansions, channel bases, GPU and render behaviour, the show's measured dials |
