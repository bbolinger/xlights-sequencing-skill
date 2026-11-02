# Portable design rules: statement, scope, enforcement, hand-check

The rulebook we built for one xLights show, rewritten so another house, song or agent can use it.
One entry per rule, in the live rulebook's index order; the rules about props that exist only in
that layout are condensed at the end as examples of how a prop rule is written. Every entry has
the same four headers: the **statement**, its **Scope**, what **Enforced by** names, and a
**Check** you can run by hand on a `.xsq` or a render with no toolkit at all.

**The one lesson behind the whole file: a rule that lives only in prose gets broken by the agent
that wrote it, the same night** (2026-09-07: a rule written, then broken four more times that
evening). Fifteen of the twenty-three rules are enforced by code in the toolkit we learned this
with, not by this text; this release ships the checks of `validate.py` and `measure.py`, and each
entry's **Enforced by** says which. Where a rule matters, add the check that refuses the file.

**Scope**: *universal* (holds on any house); *universal method with one show's numbers* (the
method ports, the dials do not); *one show's prop* (the shape ports, the content does not).
**Enforced by** names a tool only when it ships with this skill: `validate.py` (with its check
numbers), `measure.py`, `xl.py`, `fseq.py`, `snap.py`, `tc.py`, `effects_diff.py`; everything
else is *not in this release: hand-check*, and the Check line is then the enforcement. A number
tagged **[SPECIFIC]** was measured from one show's sequences, layout or taste; re-derive it
from your own files. The owner's words are paraphrased where they were blunt, kept where they were plain, and always dated, because
they are the evidence.
Positions are m:ss; durations under a minute stay in seconds or milliseconds.

---

## intent: Every song is designed portion by portion before anything is placed, and the lead says what each portion does as it builds it

**Scope:** universal.
**Enforced by:** not in this release: hand-check. (The composer's own build of `validate.py` carries a check 15 that FAILs a section with no `intent` block; the `validate.py` shipped here is the show's checker, which predates it; the rule was found broken again on 10-18 in exactly that gap.)

Identify the song's portions by listening (lyrics, stems, the owner's ear), never by energy boundaries. Each portion gets an intent record: `portion` (verse 1, chorus 2, the stop…), `music` (what it does there), `motif` (what the house plays), `why`, `build` (how it grows or pulls back from the one before). A chorus motif repeats and grows (1 < 2 < 3); a verse carries one gesture; a bridge pulls back; a stop is the punchline; the climax joins everything that has appeared; the finale is one gesture and a hold.

Two layers, both from the design (the owner, 2026-10-04, on a pass that played alone: *the pass had no impact. Filler is fine, but every portion needs intentionality: fill, move, drive with the beats, and a reason for each*). `intent.bed` is the filler: every reference row at its own coverage × the portion's level (0.15 dark → 0.95 full), a palette, a speed, the families it may touch; and it MUST change between adjacent portions. `intent.plays` is the impact on top: the motif on the hook, the gags, the build, the one punch; and the bed dips under them. A bed obeys its portion (`allow` / `deny` effect kinds): narration gets washes and holds, never a rotation or a burst. Morph, Sketch and Shape are never filler: a Morph is a line travelling between two points, and without a written destination it is bars on a slice (10-04).

Know what an effect DOES before placing it. Lit time, eff/s and coverage are checks after the fact, never targets. As each portion is built the lead reports it in one line: *"0:42-0:52 chorus 1: the chorus motif (spinners up, tips flash, trees chase) because 'there goes' is the hook and it repeats twice more."* The owner, 2026-10-04: *"every song needs this before it ever begins and the lead has to communicate this as it builds each portion of the song."*

**Check:** open the song's section file: every section names its portion, what the music does, the motif, why, and the build. Then open the sequence: each effect on a hero or a prop family inside that section should be the motif, a gag the lyric earns, or the build; if you cannot say which, it is filler placed by a number. Adjacent portions whose bed rows, palette and speed are identical fail.

## knowledge: Know what each prop IS before placing anything on it

**Scope:** universal.
**Enforced by:** not in this release: hand-check. (The composer's own build of `validate.py` carries a check 14 that refuses an effect on a row, or of a type on a row, that the show's reference file never uses unless the section file declares an exception; neither that check nor the profiler that writes the prop sheet ships here.)

A finished sequence on the SAME layout is the knowledge of how each prop is meant to be used. Before placing, draw every model from its own definition (a Custom model from its grid with submodels coloured; a Tree / Star / Window from its parameters), map it onto the house photo, and profile the show's reference file per ROW and per SETTING: which rows are beds (84-87 % lit [SPECIFIC]), which are flashers (18 %), which live in their submodel groups, which are nearly dark, which copy another row, and which are never a model row at all. Then the settings, the verbatim string of every effect used 5+ times: the owner's chases carry no fade and set speed by `Chase_Rotations`; the show's spinners are a one-arm twisted Pinwheel; the show's whole-house groups run 7-27 % [SPECIFIC].

**A prop class is not a licence**: "spinner" from the word spinner put effects on props that should never carry them. **Averages are not knowledge**: matching 18.6 eff/s and a 1.1 s median produced "blink city" because the shape of every row was wrong. The owner, 2026-10-03: *look up what each prop is, how the props are grouped and how each can be used before placing anything; a hand-off built from numbers instead of that knowledge is worth nothing* Order of work on any layout: profile → the owner corrects the prop sheet → sections → a window placed ONLY from that vocabulary → validate → render → the owner judges. A prop the reference never touches may take a library preset only with an exception the owner declared.

**Check:** a prop sheet exists with every model drawn and placed, and every row of the reference profiled as above (effects, coverage, lengths, fades, buffer styles, verbatim settings). If any of that is missing, nothing may be placed yet. For any effect you are about to place, find the same (row, effect type) in the reference; absent means refuse, or declare the exception in writing.

## rulebook-test: A measured professional rulebook wins where it disagrees with the rules below (applied 2026-09-30; decided, don't re-ask)

**Scope:** universal method (adopt a measured benchmark of professional sequences as the floor); the numbers are from one benchmark [SPECIFIC].
**Enforced by:** `validate.py` check 3a refuses a bed of 2.5 s or more with `*_Shimmer=1`. The lint and the pass-runner: not in this release: hand-check.

The owner, 2026-09-30: *"I want to test the rulebook… a professional editor called us out on it too. So we need to test the new rules."* Where it overrides entries below: a hit DECAYS (`On` End 0), it does not fade (R2); pulses ≤ 1 s get no fades, and fade-in + fade-out ≤ 25 % of any effect (R3); one song palette (film hues merged within 12°, value in 4 steps), not a fresh palette per section (R4); opaque beds below textures, fewest rows (R5/R6), EXCEPT that an element carrying an `Off`, a Canvas effect or a blend keeps its exact stacking, because those work ON the rows beneath (reordering them lit an approved dark intro solid green); SingleStrand chases are the backbone (R7); starts snap to the nearest Beats / Bars / Onsets / Drum Hits mark within 150 ms, outside moment windows (R1).

Measured with it, 10-01 [SPECIFIC]: a decaying `On` over a lit row is **Additive** (Normal blacks the bed out after every hit); `C_SLIDER_Brightness` scales value, so a dim shade is the full colour plus Brightness; a chase bed passes each pixel every 0.7-2 s and lights 25-60 %; a Normal wash sits UNDER the texture it overlaps; a bed never drops below Brightness 10; an outline reads lit ≥ 85 %.

**Moments first.** Before any pass that places, replaces or converts, the song's moments (rolls, marches, stingers, stops, film cues) are written down as data and as a timing track; inside a moment the gesture that answers it is never moved, trimmed or converted, only craft is fixed. **One owner per prop per moment**: the outline families own the house outline; the whole-house group only for whole-house moments; a prop's own row only for its idiom; no bed under an idiom prop (the sign, the eyes, the singing faces). **The whole-house bed is a PAIR** (a wash on the bottom row, an atmosphere above, both at the section's bed level) that reads as one bed only if the wash shares its atmosphere's start and end (±50 ms). A preset's fill never overrides the section's bed level.

**Check:** play the same seconds of the before and after files side by side in xLights. By hand: no effect under 1 s carrying a fade longer than itself; every bed ≥ 2.5 s with shimmer fails; every chase ≥ 0.7 s passes a pixel in 0.7-2.1 s (a Bounce is two passes); no `Off` / Canvas / blend element reordered or merged; every mark on the Moments track is answered by something that was not moved.

## density: Density is a property of the SECTION, not of the song

**Scope:** universal.
**Enforced by:** `measure.py` reports eff/s and median duration per section. The event budget and movement merging: not in this release: hand-check.

Section intensity is an explicit dial (`#restraint`); passage energy is only a proxy. Event budget = `0.9 + (eps_max − 0.9) · intensity^2.2` effects per second [SPECIFIC: `eps_max` is per preset]. Structure (bed, atmosphere, hero, faces, voice, authored dark) is placed regardless; only events compete, admitted in weight order. The unit of structure is a **movement**: neighbouring passages merge until long enough to re-voice (9 s at low intensity, 4.5 s at high [SPECIFIC]).

**Quiet does not mean narrow. Quiet means still.** Below ~0.55 intensity [SPECIFIC] a regular figure gets ONE gesture across the whole figure, not one effect per member. A quiet section that is merely faster-and-smaller is the failure: one song's 37 s ambient float came out 61 % under 500 ms until the one-gesture rule (09-08).

Why: the show's own quietest intro, per 10 s, reads `1.0 0.2 2.2 0.0 18.2 23.3 20.8` [SPECIFIC]: 0.6 eff/s for 44 s of spoken intro, 28 effects of 10-22 s each while lighting 20+ elements at once. The 11.4 in a preset table is the average across that shape; applying the average to a section repeats the cross-song averaging error one level down.

**Check:** count effects in `<ElementEffects>` inside a 10 s window of the quietest section and one of the loudest; divide by 10. Quiet ≈ 0.6-2, loud ≈ 10-25 [SPECIFIC]. Compare median effect duration between the two windows too: quiet must be LONGER, not merely fewer.

## transitions: A new window grows out of the one before it

**Scope:** universal.
**Enforced by:** `validate.py` check 5 FAILs a section start with nothing already running across it; `effects_diff.py` compares two versions by (element, name, start±frame, end±frame); `fseq.py` decodes two renders for a frame diff. Carry-over and the seam reader: not in this release: hand-check.

Every window after the first is a continuation. Before composing, read the last ~5 s of what is already written (beds, elements, palette, fade-outs) at EVERY seam: the window start and the end of every approved range. Two legitimate answers, the music picks: carry it on (default) or depart deliberately with the old material ringing out underneath. Starting cold at a boundary is never right. A seam inside a section is a continuation; only a section boundary is a transition. Beds lead in 1-1.5 s early [SPECIFIC] on their own layer; heroes, punches and figures land ON the boundary. The owner: *"it sees five seconds back, doesn't change it, but grows into the next. Whether that fades to black or actually takes the colors and carries on will depend on the music. This is true for any section."*

Two traps. **An approval landing mid-section cannot be built onto**: the section's beds lead in early, so their lead-ins cross the edge, are carried whole, and the new beds stack on top (Day-O 09-21); cutting the straddlers is worse: their fade-outs dim the end of the approved range. Re-open below the lead-ins, or build from the next section. **Byte-for-byte XML is necessary and NOT sufficient, so diff the RENDERS**: Meteors, Fire and Galaxy re-seed when layer indices change (Day-O 09-21: 0 content differences, 614 of 2960 frames differed, all inside those spans). After any xLights save, re-baseline: a save snaps to the 25 ms frame and normalises strings, so an exact-string diff reports hundreds "lost" that are not.

**Check:** for each section start `t`, count effects whose span strictly contains `(t − 200 ms, t + 200 ms)`. Zero crossing effects is a hard cut. Read the last 5 s before and the first 5 s after: at least one element carries the same effect type across, or the hero lands exactly on `t`. After a rebuild, decode the old and new `.fseq` over the protected range and attribute every differing frame.

## carry-over: Regeneration must not accumulate

**Scope:** universal.
**Enforced by:** `effects_diff.py` (per-element counts between versions). Dedupe on carry-over, the spill cap, free-span-only placers: not in this release: hand-check.

An effect matching another on element, type, span, settings and palette is the same effect however it got there; drop it. Relocating a structural effect to a free layer is for a handful of crossfading beds; an unbounded pile means something upstream is duplicating (cap: 8 spilled layers per window [SPECIFIC]). Every additive tool writes only into FREE spans of its own targets, so it is legal inside an approved range and idempotent (a second run adds 0). The tell after repeated regeneration at the same end: many layers holding one effect each, identical spans starting at the previous window edge.

**Check:** diff effect counts per element against the previous version. Two effects on one element with the same name and start within one frame are a duplicate, not a layer. Count `EffectLayer` per model: past the show's own depths is accumulation, not composition [SPECIFIC: matrix 20, big tree 21, whole-house group 15]; more than ~8 added in one window means the cap is not working.

## darkness: Two different darknesses; do not confuse them

**Scope:** universal (the owner's words).
**Enforced by:** `measure.py` (house coverage over time); `fseq.py` + `snap.py` to read the render. The `stops` subtraction and `"dark": true`: not in this release: hand-check.

**Local darkness is the breathing mechanism**: props and groups going dark while others carry the movement is HOW a section breathes; there is no requirement for a bed under everything. **Whole-house dark is a different instrument**: a slam punch, reserved for a moment the music itself makes (a silence, a stop, the bottom before a drop), and then the whole house, not a fade. Never majority-dark at a boundary because one section ended and the next has not started. The owner: *"Black can let things breathe… It breathes because it continues the movement throughout the entire house by turning on and off various props… We don't need lights under it all the time."* / *"if it goes dark, it is a slam punch."*

**A stop is DATA, not an absence** (`stops` in the section file). Nothing fills a stop (no idle bed, no carried bed, no atmosphere); only the character making the sound stays lit. A stop is measured in the STEMS, not the mix (bass at −60 dB while one voice yells alone [SPECIFIC]), not a quiet bar. The answer to a stop is the house DROPPING: every bed crossing it is split in place (trimmed to the stop's start, re-added from the restart to its original end, no fade-in so the return is a slam), never an effect laid on top of an unbroken bed, which reads as more of the same (09-07).

**A section may be dark** (`"dark": true`): no bed, no rings, no events; the faces and the sign carry it. Without that flag no intensity setting makes the house black (one opening came out as one unbroken 16 s wash where the reference is black, swells, and goes black again). **Darkness is the absence of a bed, never a bed plus a mask**: an `Off` on an empty element renders identically to an empty row and is clutter (the owner: *an Off effect over a span where nothing else is loaded is pointless. Darkness is the absence of effects, not an effect*).

**Direction is not brightness.** A gesture reads as travelling only if most of the house is DARK at every instant: a thick Shockwave lit 72-75 % of the buffer and its radial centroid sat flat for 3.5 s; narrowed, with nothing beneath, the same span ran monotonically inward at 3-5 % lit. A multi-front wave is staggered by RADIUS, not by width or start time. Eye, coverage and brightness never caught this; the radial centroid did. **Sample a reference finer than the structure you want** (2 s sampling hid a shape obvious at 0.25 s); a mean is not a shape.

**Check:** sample the render every 500 ms; count models with any pixel above 25 luma. Whole-house dark (under ~25 % of models lit [SPECIFIC]) must line up with a stop measured in the stems. Any majority-dark stretch at a section seam is a bug. For a travelling gesture, compute the lit pixels' mean distance from the gesture's centre at 100 ms steps: it must climb (or fall) monotonically, never oscillate.

## identity: Every section needs its own identity

**Scope:** universal.
**Enforced by:** not in this release: hand-check (the show's composer holds deterministic per-section palettes, vocabulary rotation by section index, and speed as a function of tempo and intensity).

Adjacent sections must differ in colour, vocabulary and speed even when they sound similar, and a section must look like itself whichever window generated it. Density having an arc is not enough. The owner, on a first pass that hit the beats: *a new section that changes no colours, no speeds and no effects to follow the music is boring* Cause: every section composed from one lookup table keyed only on passage kind.

**Within a section, DIRECTION alternates per bar** (the owner, 2026-09-19: *go left for one four-count and right for the next, and the same when the motion turns vertical. The direction alternates every bar*). The flip lands on the downbeat and is resolved from the effect's FINAL start, after any re-timing. A bed is CUT at the bar lines to alternate, because one xLights effect holds one direction: the pieces abut, each at least one bar, fades on the outer ends only. A direction that means something musically (bars following a vocal line's contour) is left alone.

**Check:** list the distinct effect names and palettes in two adjacent sections; identical sets means no identity. For each directional answer on a roofline or punch layer, find the bar its start falls in: two consecutive bars sharing a direction is the bug. For a bed, cross-correlate consecutive frames of one wide model and check the net shift reverses sign at each bar line; a centroid cannot see it, because a multi-crest wave keeps its centroid in the middle whichever way it travels.

## restraint: Restraint is the governing rule

**Scope:** universal; the gates and the rest are the show's numbers [SPECIFIC].
**Enforced by:** `measure.py` (per-element gaps, the whole-house effect list). The punch gate, the constant rest, the responder pool, the intensity dial: not in this release: hand-check.

Bigness is rationed, not banned. A whole-house punch must be big two ways at once, against the song (`w_abs` = onset strength / song p98 ≥ 0.66) AND against the last 4 s (`w_loc` = strength / median of the last 4 s ≥ 0.72), or simply huge (`PUNCH_ABS` 1.05, which admits two onsets song-wide) [SPECIFIC]. Everything below answers small: prop + roofline for a mid hit, a wing-beat or an eye-flash for a light one. The bed never shouts: no shimmer, calm cycles; impact is contrast against a still bed. The owner: *"There's times for a bigger effect, but it needs to be very subtle… it's hard to achieve a balance of feeling the music without it being bam in your face."*

**Element rest is constant (750 ms [SPECIFIC]) and density comes from more of the house answering**, so the responder pool widens with intensity instead of the rest shrinking. A rest that shrank with intensity reproduced the documented flicker (42 effects on one prop, 20 % under 500 ms). Short bed hits sit on a steady beat grid from the downbeat, ≥ 750 ms apart; scattered on-beat hits read as glitching (10-18).

**Intensity is a DIAL in the section file**, because passage energy inverts on a limited master (one song's ambient float measured 0.74 and its finale 0.52, backwards). Derive it from what the song DOES (onset density, arrangement) and record the derived value beside the dial. **If a section feels flat, trace where its events were SENT before re-dialling**: a pool scanned from index 0 every time sent 13 of 14 events to one prop while a dozen sat dark (09-22); the lever the rule names would not have fixed it. Then raise intensity or give the bed texture; never loosen the gate.

**Check:** list every whole-house effect and look up its onset strength: top decile of the song AND above the median of the previous 4 s. Per element, list gaps between consecutive effects: gaps under 750 ms [SPECIFIC] are flicker. If a section is flat, histogram which elements its events landed on before touching a dial.

## presets: Style is a set of dials, set per song, derived from the song

**Scope:** universal method; the numbers are the owner's [SPECIFIC].
**Enforced by:** `measure.py` reports the dials. The preset table: not in this release: hand-check.

The owner varies style deliberately per song; there is no single style to imitate. Identify the **driver** (bass line, movie-rhythm hook, dialogue, ostinato) and pick or derive a preset before placing anything: from the song, never from an average across songs. Four presets were measured from 6,204 hand-placed effects [SPECIFIC]; "part-writing vs whole-house unison" is its own dial. **Only three invariants held across all four**: effects follow **onsets, not beats** (pooled median 54 ms to onset vs 83 ms to beat); **10+ distinct effect types** per song; a `VU Meter` in every song at a low steady rate (1-4 %) [SPECIFIC].

**A dial counted per ROW is a fact about the FILE, not the yard: expand before quoting it.** One song read "2 elements, 0.9 eff/s: whole-house unison, very sparse". Its one group expands to 38 of 44 models; its 116 effects run 9 layers deep with a whole-house effect up 72 % of the song, in 29 effect types: the DENSEST coverage of the four, not the sparsest (the owner, 09-16: *the whole-house layer described as sparse was anything but*). Low effect COUNT because one effect does the work of thirty.

Character → effect, from the show's placements [SPECIFIC]: attack = Morph, Bars, SingleStrand, Shockwave; sustain (~1.7-2 s) = Pinwheel, Warp, Wave, Spirals, Fan, VU Meter; chime = Shockwave / Ripple with a long fade-out, never a fade-in; voice = VU Meter off the vocals stem; deliberate darkness = `Off` as an authored element. Calibration anchor: a first pass had onset alignment fine at 75 % and still failed on a 420 ms median and 4 layers: **timing was never the problem; duration, character and layer depth were.**

**Check:** measure a finished sequence of the target style: eff/s per section, distinct effect types, a low steady VU Meter underneath. Expand every group before quoting a per-row number. Everything else is per song.

## designs: Every song picks its own effect PATTERNS, and every hero can carry a power effect

**Scope:** universal.
**Enforced by:** not in this release: hand-check (the show's spinner placer REFUSES a song with no `designs.scenes` rather than inheriting another song's look).

Colour is derived per song from the scene and the dials are a per-song preset; **the PATTERN is the third thing chosen per song**, from the song's feeling and its film, written into the section file with the reason. A design is taken from the library as a PATTERN and recoloured to the song's own palette, never the preset's colours. **Every hero family can carry a power effect** (the big tree, the spinners, the matrix, the whole house): one simple, strong gesture landed on the section's biggest onset. The model: a ring leaving a point, 6-13 % of the yard lit [SPECIFIC].

The owner, 2026-09-19: *songs must not all feel and look the same with the same effects; consider the variety and style of each, how its music creates a feeling, how its film or video used it. The mega tree, spinners, matrix and whole house can each be a power effect. Simple, powerful, fun* The fault it names is real: one vocabulary table keyed on passage kind makes every song reach for the same effects. Worked example: a film's possessed dinner guests → that song's spinners move like limbs, not pinwheels; another song must pick its own.

**Check:** list the effect names and settings on each hero family in two different songs. Matching sets means the second song has no look of its own; the generator's table is showing through.

## colour: Colour comes from the song's own scene

**Scope:** universal method.
**Enforced by:** `validate.py` check 17 WARNs on a muddy palette gradient (two saturated stops ≥ 60° apart whose midpoint is grey or olive, with its lit seconds); `measure.py` off-scene audit (palettes only); `fseq.py` / `snap.py` to audit the render. Scene sampling and LED translation: not in this release: hand-check.

Palettes come from the film's own frames per section, clustered by hue (or one song palette, R4). Roles are jobs (bed / atmosphere / hero / accent / neutral), never hues. Film and LED are different media: keep the hue exactly, translate saturation and value: deep for a bed, full for an accent. White is hue-free and always available (the show's most-used colour, 13 % [SPECIFIC]); eyes are fixed red by decision. Palette pools lifted from OTHER songs are wrong: those were colours chosen for those songs. The owner: *"we need colors based on this video and song. There's gold, green, yellow, red etc. I'm good with dark purple green etc to create moods but think of the song."* **No video? Author the scene by hand and say so in the file**: film-frame values (dark and desaturated) with a `source` field, and NO near-black entry, because a neutral at distance 0 makes every palette admissible and silently collapses the section's colour constraint.

**An effect that makes its own colours is outside the palette audit.** `Fire` ignores its palette; its only colour control is `E_SLIDER_Fire_HueShift`, 0-100 across the whole wheel (degrees ÷ 3.6); a Fire with a perfect scene palette rendered red-orange across a green section. Only the render can audit these. **A palette GRADIENT makes mud on its own**: red → green's midpoint is olive #7f7f00. A Halloween green beside red must be WET green (neon, ~110-125°), never olive / forest / lime (~70-105°) even when that is the film's own hue (the owner, 10-02: *"a wet green not a christmas tree green"*) [SPECIFIC to that holiday].

**Check:** sample the rendered `.fseq` across a section and histogram the hue of every saturated node, not the palettes. Compare against the dominant hues of the section's frames: hue should match; saturation and value should not. More than a few percent outside the scene's hues is a break. A scene with 0 % white should not carry white washes.

## model-contrast: The foreground must survive the layers beneath and above it

**Scope:** universal method; the levels and palette choices are song- and layout-specific.
**Enforced by:** not in this release: hand-check (no validator refuses a visually flat stack; the saved-render review is the acceptance test).

Give each featured model or group ONE readable foreground movement over a restrained background. Remove redundant washes and long competing movements before adding another layer. When two layers share a hue, separate brightness and hue deliberately (one song's approved options: dark forest background, emerald / lime responses, ivory highlights, not fixed colours; keep them coherent with the scene). Reserve coverage and brightness for the build and the climax (~21 active models early against ~40 at the climax [SPECIFIC]: evidence, not quotas). After changing body lighting, re-check every eye and highlight that rode it: append-only placement cannot repair a floating highlight. The owner, 2026-09-09, on the rendered edit: *"much better make that a rule, for our models"*.

**Check:** expand every group reaching the featured prop; list the overlapping layers and the row order; read the render per model with the right stride (RGB 3, RGBW 4); record active-node fraction and brightness per model; exclude a dominant matrix from house comparisons. Watch the motion through its full cycle, because matching foreground and background greens can merge even when the XML lists different effects. Metrics do not establish readability; the owner's playback judgement does.

## punches: Weight is continuous, from the full mix; drums only route the answer

**Scope:** universal; the gates are the show's numbers [SPECIFIC].
**Enforced by:** not in this release: hand-check (the show's composer holds `w_abs`, `w_loc`, `PUNCH_ABS`, level grouping within 1.3 s, palette-value brightness, and peak-sampled onset strength).

A big orchestral stab with no drum under it is still a big moment: the **full mix** decides how big; the stem only decides which part of the house answers (drums / bass → roofline + props; vocals → face + VU Meter; other → hero and beds). Weight is continuous, never a bin, judged against the song AND the local context, but local context never makes the response non-monotonic: a hit huge against the song punches regardless. An onset the stems missed is still a sound. Speech consonants are not notes: the voice is answered as a phrase; music in the clear between lines weighs ×1.6, consonants ×0.55 [SPECIFIC]. **The weight of an onset is the peak it rises to**: sampling the envelope at the backtracked onset frame reads the valley: 48 of 773 onsets under-read by 2× or more [SPECIFIC].

**The owner's level rule (2026-09-04):** *"It just depends on the level of the hit… if it's the same strike, all three same level; if it builds with volume or intensity then the effect is still dramatic but the brightness can increase from 80-100%."* Every onset gets a level against the strongest hit within 1.3 s; one that fails the gate but sits at ≥ 78 % of a punched neighbour is the same strike and punches too, brightness 80 → 100 % through the palette's VALUE; the show's files never set `B_SLIDER_Brightness` [SPECIFIC].

**Drums SITE and LEVEL a whole-house hit, not just route it.** The full-mix onset list ranks a vocal re-entry above a kick 16 dB louder in the drums stem; the drums stem detected no onset at the biggest hit at all. Before siting a whole-house punch, read the drum stem's peak LEVEL across the window, not its onset list and not the full-mix envelope. A hit decays (R2); a decaying `On` over a lit row is Additive.

**Check:** for each of the biggest onsets in a window, something whole-house answers within ~100 ms, sited on the drum stem's peak. Inside a run of hits, equal strikes get equal brightness and a rising run rises; read the palette's value, not a brightness slider.

## layers: Before placing anything, check what is ALREADY on those pixels

**Scope:** universal.
**Enforced by:** `validate.py` check 9 flags a WIDER element on a LATER row painting over a narrower one beneath it (burial); the reverse (a group bed early, narrower detail later) is the documented pattern and is not flagged. `"owned": true` sections and lead-in clipping: not in this release: hand-check.

Adding an effect is never the whole job. **Always check the other layers and what is left underneath, and confirm every overlap is deliberate.** The owner, 2026-09-16, after a whole-house shader went on top of the beds instead of replacing them: *make it a rule to check the other layers and what is already there before placing. Wipes were added over a set of props without cleaning up what sat under them* 47 effects were alive in one 3.4 s window; after the fix, 7. **Per-element layer counts cannot see this**: the colliding effects sit on DIFFERENT elements and meet only after expansion. **A group reaches a prop's SUBMODELS without claiming the prop**: a whole-model check passed a group that still reached 32 ring submodels of three singing props. Expand to the LEAF, never the model. If the overlap IS deliberate, the thing underneath should not be there at all: mark the section `"owned": true` so nothing else is placed in it.

**How xLights composites, measured off saved renders.** Between elements, a LATER row paints over an earlier one; nothing about "specificity" decides it (09-06: a group bed buried a submodel's own flashes; the fix is the prop's row BELOW the group's). With model blending on, a later row covers an earlier one only WHERE IT DRAWS: a Color Wash / Fire / Video buries everything beneath it on those pixels; Bars or a VU Meter only where their bars are, so the effect list cannot say what is buried. Inside one element the order is the reverse: **layer 0 is on TOP** (`#shape`). `On` intensity below 100 is alpha over what is beneath (a 50 % red over a lit green bed reads grey).

**Check:** for the span you are about to write, list EVERY effect already alive on every element whose expansion touches the same models (to the leaf), not just the element you are writing to. More than a handful and the new gesture is soup. For each eye or idiom prop, confirm its row sits BELOW every group bed that reaches it. For a doubtful stack, render the row alone and diff it against the full render.

## machine-made: Eleven tells, each individually noticeable to an owner

**Scope:** universal (items 1-11); the prop specifics the owner attached to item 4 are in the prop section below.
**Enforced by:** `validate.py` check 5 holds items 1 and 8 at section starts; check 3a holds item 9's shimmer clause. The rest: hand-check.

From the owner's review of a generated sequence; each was individually noticeable to the owner.

1. **Every transition lands on a real musical event**: onsets per stem, never a timer. Sections come from the owner's ear; the analyzer proposes; each start snaps to its first real event.
2. **Never change mid-phrase** (phrase bounds on the vocals stem).
3. **Sequence to groups, not models, but check what a group EXPANDS to, never its name.** A group named like a roofline section held three whole multiprops; a `Bars` wipe ran straight across them.
4. **Every prop gets used, in its idiom** (*"pretty much everything will be used"*). A prop lit but not animated in its idiom reads as unused. Every effect traces to an event: passage, figure, hit, voice window, section.
5. **Open on a hit, not a fade: skip a bland intro; end where the song ends**, with a 2-3 s fade that follows the music's own [SPECIFIC].
6. **Don't re-voice a hero model every few bars**: it reads as rapid flashing.
7. **Copy effect setting KEYS from the show's files; never a sample's value as a constant** (`#keys`).
8. **A transition is a region, not a point.** Two effects on one layer cannot crossfade: incoming on its own layer, ~1-1.5 s early, fade-in over the outgoing fade-out. Events are trimmed, never dropped; structure is relocated, never trimmed. **Trimming is where flicker comes from**, so rate-limit per element (≥ half the mid length) and spread across siblings. The lead belongs to the bed only.
9. **Shimmer is flicker, never a default.** A whole-house bed with shimmer is a strobe; shimmer is one element, one moment (the owner, 10-01: *the flickering has to stop*). A drum lights the roofline or a prop, not the whole house. No blank layers "just because" (xLights' own single empty `EffectLayer` on an effect-less element is the exception).
10. **Bind successions into figures: look ahead.** Three hits are one "bum bum bum"; the drum ~0.4 s before a sung note is the pickup, and the effect goes on the note.
11. **Leave things dark and vary density per section.** The arc is non-monotonic.

**Check:** each item is checkable on its own. The two that catch the most: **expand every group you sequence and look for a multiprop inside it**, and **dry-run any placer twice and diff**: byte-identical output, or it is not deterministic and the file will not match the list you showed the owner.

## casting: One speaker, one voice, one timing track; the script is the source of truth

**Scope:** universal data model and method; the cast and the face map are per song.
**Enforced by:** `validate.py` check 6 (tracks match the casting file; `instrumental: true` → n/a and FAILs any track; loud `DID NOT RUN` when it cannot run; a multi-mouth face uses its full mouth set), 10 (visemes inside their words), 11 (vowel visemes vs the stem's spectral centroid, `LOOK:` list), 12 (voice with no mouth → `LISTEN:`), 12b (a word sung into silence after an audio cut), 13 (one voice, one prop at a time), 16 (every word verified and broken down); `snap.py --sub` decodes a mouth. Aligner, caster, face packer, breakdown, voice-mouth and gag placers: not in this release: hand-check.

**Get the script.** Who says what is looked up, never inferred from audio; the script wins over pitch and diarization. Cast per LINE, never per word, never per section. **Every named character gets a full timing track**, solo lines AND every group line, never a collective bucket (the owner, 2026-09-06: *they are different people, so each gets their own line; it makes later edits easier, and it should be a rule*). The cast is per-song CONFIG, never code; a reader REFUSES an unknown character instead of dropping it: a defaulted cast once rendered a song with no face anywhere while every check passed (09-16).

**A transcript is ONE STREAM**: it mis-hears, drops whole lines, hallucinates past the end, and ABSORBS an overlapping singer into the dominant line without failing; no model or setting fixes it. Find the second voice by LOCAL contrast inside the lead's own line; recovered lines are MEASURED INPUT with a `source`, and nothing downstream rewrites them: a tool that writes its own input ratchets. A flat pitch line in the vocal stem is instrument bleed, never a mouth; never prime the transcriber with the sound you hope for; a held note lands on the word BEFORE it. **Once the owner hand-edits a song's tracks, the FILE outranks the analysis and the chain REFUSES to rebuild.**

**Mouths come from the AUDIO.** Forced alignment, never arithmetic over word bounds. Word and viseme layers come from ONE set of spans; a word's shapes FILL the word, and a `rest` lives only in a gap BETWEEN two words of one phrase (the owner, 09-14: *rests were placed everywhere for no reason*). Word START from the aligner, END from the transcript capped at the next word's start; a start dispute of ≥ 0.30 s goes to the stem: the first periodic frame after ≥ 150 ms unvoiced, per-frame autocorrelation, never a level gate [SPECIFIC]. Verify a viseme fix against the stem's spectral centroid, never the transcript or the aligner alone.

**Every word VERIFIED and BROKEN DOWN** (10-18: *"we need all words verified and broken down"*): verified = a real pronunciation from a dictionary, never spelled from letters; broken down = 2+ syllables show 2+ shapes when the word lasts ≥ 150 ms, syllables from the singer's stem dips or the aligner on that word's slice, never stress weights (10-14: *it plays the word as one shape every time, so it stutters*). **Sounds are placed where the VOICE makes them, long enough to see** (10-23: *"It just doesn't say words"*): the aligner times every letter; a consonant between vowels sits at its spike for 75 ms (MBP / FV / WQ) or 50 ms, vowels fill the rest and show ≥ 75 ms, nothing under 50 ms [SPECIFIC].

**Faces.** One voice, one PLACE: a face MOVES, never copies, and every moved face leaves a marked BLACK HOLE for the owner to evaluate (09-30: *one person singing from two places is a bug*). Never light a face with no words. A dedicated singing prop stays lit all song: rest is the CLOSED mouth, the lit look between lines a fixed-mouth idle, and a song that trades lines idles CLOSED (10-24); a multi-mode prop's face stays windowed. **A face blinks and pre-closes** (10-15: *the faces looked unsettling. They never blinked*): `Eyes=Auto` never blinks a long NodeRange piece, so blinks are PLACED (every 4.5-5.5 s, 125 ms), every other piece is `Eyes=Open`, a windowed face blinks only on screen, and every line pre-closes 125 ms [SPECIFIC]. A face definition maps one WHOLE mouth submodel per sound; a track uses the FULL mouth set, never open-shut (10-09: *the mouth just moves up and down, on a prop that has eight mouth shapes*); xLights reads the mouth from the THIRD track layer. An eye is never painted dark: a blink is `Eyes=Closed`, never `Off` on an eye submodel; a tint over a lit face is Normal, never Additive; a gag is timed by the film's mouths, never audio pulses. A backup group's membership is the owner's word; a doubled lead shows as vocals-stem stereo width [SPECIFIC]. In tight banter the centre holds and the sides answer (a non-lead takes the centre only when the lead is silent ≥ 4 s [SPECIFIC]). A face definition is KEPT on rebuild: the file's, else config, else ASK.

**Check:** each character's mark count against the casting file; `rest` marks present, between words only; every word mark has a viseme inside it and none crosses a word edge; three lines spot-checked by ear (a word span under ~60 % of its line means the aligner missed the start). Decode the render frame by frame on a word the owner names: one open per syllable with a visible shut between; a 2+ syllable word shows 2+ shapes; every one of the prop's mouths appears across the song, proved on EXACT mouth node sets (mouths share nodes). Rendered blinks ≈ every 5 s, 5 frames; the frame before each line's first word is the closed mouth; no two props sing one track at the same instant.

## shape: A character on a hero canvas is mostly ABSENCE, and always on layer 0

**Scope:** universal method; the schedule is per song.
**Enforced by:** `fseq.py` to read the canvas back. The shape placer (`Pictures` / `Video` on layer 0, strays moved up, a span more than 100 ms off the clip length refused): not in this release: hand-check.

Putting a character on the matrix or the big tree is a lighting move, not a slide show. Two shapes only: **glimpses** (300-450 ms, no fade-in, a 100-150 ms fade-out, on a real onset, gone before you are sure you saw it) and **holds** (3-8 s, on the drops and the finale) [SPECIFIC]. Absence is the effect: budget the longest gap deliberately, and let at most two appearances be ones the music does not announce.

Images are authored AT the target's own buffer (a matrix 224 × 140; a tree 32 strands × 100 [SPECIFIC]) so `Scale To Fit` is a no-op, black transparent so the surround never lights the panel. A tree buffer's aspect is not the tree's aspect, so pre-squash, then read the tree's channels back and correct. Hard-threshold after the downscale (a soft edge at 32 px eats the silhouette); a dark film frame needs a black-floor lift, `clip((v − floor) · gain)`, never gamma (which lifts the background too). Moving assets are `Video`; `DurationTreatment=Normal` does not stretch, so the span MUST match the clip.

**Layer 0, and ONE of them.** Inside an element xLights composites layer 0 ON TOP (the opposite of the between-elements row rule), proved in the render 09-11: 79 white nodes on a last layer, 886 on layer 0, because a hero carries a bed and on a lower layer the mask shows only where that bed is black. All of one element's appearances share that layer and never overlap in time. The schedule is DATA the owner edits.

**Check:** sum on-screen time per target ÷ song length; past ~15 % on the big canvas it is television. Every appearance sits on a real onset or a measured level change, never a round number. In the raw `<ElementEffects>` XML, every `Pictures` / `Video` is on the element's FIRST `EffectLayer`. Read the canvas back from the render: the silhouette you drew, at the brightness you expect.

## keys: Copy the setting KEY; never a sample's value as a constant

**Scope:** universal.
**Enforced by:** `validate.py` check 3b (buffer style on props). Key harvesting from the show's files and per-target routing: not in this release: hand-check.

An unknown key is silently ignored and the effect falls back to defaults: renders fine, looks wrong. Absence from the show's files does not prove a key invalid (xLights omits settings at defaults). Before baking any value into a helper, **count its distribution across the show's files, weighted by actual use, per target type, excluding generated files**; a grep of EffectDB entries counts definitions, not uses. Buffer style, blend mode, fade length and direction are per-target decisions: route them by element, never set them in a helper. **A helper's DEFAULTS are baked-in values too**: a Morph helper's factory geometry, `start=(0,50,0,50) end=(100,50,100,50)`, draws a band between two coincident lines, ONE PIXEL tall; 87 % and 83 % of two songs' Morphs were that streak against 8 % in 2787 of the owner's own (09-22: *"a single line that cuts the middle of the tree"*) [SPECIFIC].

**A model's default buffer is its WIRING, not its shape.** A 1-arch Arches or a Single Line is one pixel tall, so any directional effect (`Location=Bottom`, a bar, a wipe) has nothing to travel along and renders as a solid fill (*"the arches are just solid green"*). Compute the rows first (Arches: `NumArches`; Single Line: `NumStrings`; Custom: `CustomHeight`; Window Frame: `SideNodes`; Tree: `NodesPerString / StrandsPerString`). One row means `Per Model Per Preview` + 2D, so the buffer is the prop's physical footprint and an arch burns from its feet. **A group's default buffer is ONE grid over the whole group**: `Location=Bottom` on a group is the bottom of the HOUSE. A prop-level effect cannot beat a group whose row sits below it; the fix is a NARROWER group appended as its own row, never a re-sort: adding a row is safe, moving one is not.

**Some effects ignore the palette, and some sliders are not in the units they look like.** `Fire` colours only by `E_SLIDER_Fire_HueShift`, 0-100 across the wheel (degrees ÷ 3.6). A shader's sliders are its own declared ISF inputs (one takes `R/G/B`, another lowercase `r/g/b`; one whose first input is `inputImage` warps the layer beneath and renders nothing alone), so read the fragment code. Calibrate any control against the render before trusting its name, and check the COLOUR you test for before concluding an effect did nothing.

**Check:** before any directional effect, compute the target's buffer rows; one row means it has nowhere to travel. Before baking a value, count it across the show's files by use, per target type. Check what a house group EXPANDS to before trusting it to mean "everywhere". Place, render, read the pixels.

---

## Prop idioms (one show's: the shape of a prop rule)

One layout's props, here to show how a prop rule is written, not to be followed. Each says what the prop IS (nodes and submodels from the layout file, never its name), its IDIOM (measured from the show's files and words), what enforces it, and the one check that reads the render. Write one for every prop in your layout before placing on it (`#knowledge`).

### matrix: A dominant element dominates every global measurement

**What it is:** one element holding 78 % of all channels [SPECIFIC]; also the heaviest GPU load in a render. **Idiom:** never tune against a global mean: it is a matrix reading with noise; compute per element. A full-panel effect held ~2 s adds more to the global mean than a whole climax: short stabs, never a bed under a quiet section. Effect intensity is not predictable from type: place, render, measure. **Enforced by:** nothing; a measurement caveat. **Check:** when reading a render, bound each model by the NEXT model's start channel, or you read its neighbour's pixels and the numbers still look plausible.

### matrix-video: Video only on marquee moments

**Idiom:** video on the big canvas only in per-song windows written in the section file (the title hits and one cut); keep the intro burst generated, not video, so the biggest weapon is not spent before the song has earned it. When the mp3 was extracted from the mp4 the timelines match and `Video_Starttime` is the window start. **Enforced by:** not in this release: hand-check. **Check:** compare the listed windows against where the matrix is actually bright in the render; video outside a marquee moment reads as television, not lighting.

### matrix-rear: The matrix is a rear-projected video the player plays by media name

**What it is:** at show time not a pixel model but a projector behind a screen; the player plays `videos/<song>.mp4` by media name (the owner, 10-13: *it is rear-projected, so everything must be mirrored*). **Idiom:** the sequence keeps the matrix as the street sees it; a tool turns the SAVED render into the player's file: the whole frame mirrored, 1280 × 720 at 30 fps, the picture in the top ~88 %, the station banner scrolling at the show's measured pace (329 px/s), the song's audio muxed in. Never on a song whose matrix already plays an old export; probe the video first. **Enforced by:** not in this release: hand-check. **Check:** `ffprobe` the file (duration = the song); one frame shows the banner reading BACKWARDS; the sequence's own matrix row is NOT mirrored.

### hattitude: A multiprop with overlapping submodels has exclusive modes

**What it is:** a ~700-pixel GE multiprop, three side by side, its pixels mapped into overlapping submodels: faces, rings, spinners, spokes, 24-arm hook spirals, torches, bat, spider. **Idiom:** modes overlap in time but are EXCLUSIVE BY PIXEL: check every pair by node overlap, never by name; a face owns its pixels while on, and the only face-safe pairing is `Outer Ring` (0 overlap); never an effect on the WHOLE prop row but `Faces` / `Off` (10-07: *"lighting up all of my pixels instead of the spinners, spokes, rings"*); a vendor disc maps to the spinner groups; props get `Per Model Default Deep` (Per Preview sweeps physical space across every concentric ring); the rings are a SET: one bed per section on the set groups, two HUES ≥ 60° apart, at bed speed, never shimmer, never a Canvas mask taken as a bed, hits per prop and Additive, the set fading for the centre face; the hooks ROTATE (unused in 14 of the show's files). **Enforced by:** `validate.py` check 3c (a whole-row effect on the multiprop FAILs), check 3b (buffer style). **Check:** at any instant no two modes claim overlapping pixels on one prop; nothing per-preview on it; the ring pixels' mean frame-to-frame change sits at bed speed (1.5/255 reads as static, 62 as shimmer [SPECIFIC]).

### bat: A flapping creature flaps by its wings on a fitted grid

**What it is:** a model whose two wing groups both contain the body, so alternating the groups re-lights the body every beat and it blinks. **Idiom:** flap by the WING submodels: `/Wings Up` then `/Wings Down` alternating, one wing state per beat (*"a flap is half… four flaps per"* bar), `/Body` and `/Eyes` spanning the stroke; the body is DERIVED from the wings (first wing start → last wing end), so a lit-but-still bat is not expressible; a sustained flap rides a least-squares beat grid, `t = t0 + k·period` (median 28 ms from a real hit; detected beats wander ±30 %), and ends where its pulse dies, which may be the bass, not the drums; a single onset outside a flap window gets one full stroke, never a 150 ms `On` to a wing group (09-22: *it only blinks, and that looks bad*). **Enforced by:** not in this release: hand-check. **Check:** wing effects alternate and share boundaries, never overlap; body span equals the wing span exactly; count lit pixels on each wing's EXCLUSIVE nodes: the wings share a node and the body shares one with each, so a `max()` over a submodel reads both wings lit and a correct flap looks broken.

### eyes: Eyes ride the body

**What they are:** dedicated eye submodels with 0 node overlap with their own body, reached whole by the house beds: camouflaged, not dark; the job is contrast, not illumination. **Idiom:** every eye span is clipped to when that creature's own body is lit IN THE RENDER (sampled every 250 ms, ≥ 40 luma, hold ≥ 1 s, bridge < 0.5 s [SPECIFIC]; tighter where a body pulses or chases); a Shockwave sweeping through is not a body; fixed red; a dim base is a darker hue at 100 %, never a lower intensity (that is alpha); the prop's row sits below any group bed that reaches it (the owner: *"they shouldn't be on if the body shape isn't there"*). **Enforced by:** not in this release: hand-check (`measure.py` excludes eye elements from the dials). **Check:** every eye span sits inside a span where the body reads above ~40 luma, sampled strictly inside, never at a boundary frame; group expansion proving an effect REACHES the body is not the body being LIT.

### spider: A creature lit only by house beds reads as unused

**What it is:** a separate 158-node RGBW model: `body` 35, `timeclock` 11 (the red hourglass, 0 overlap with the body), fangs, eleven leg groupings, no eye submodel; found by its real layout name, never by searching "spider": the multiprop's spider MODE is a different thing, and events placed there read as a spinner. **Idiom** from the show's files: SingleStrand chases along the legs on hits (median 450 ms, ≥ 4 s apart [SPECIFIC]) and a red `On` on the hourglass whenever the body is lit; no eyes by decision. **Enforced by:** not in this release: hand-check. **Check:** the hourglass is red only while the body reads lit; leg chases land only on hits with a lit body; decode with the RGBW stride.

### tune-to: The sign shows the station for the whole song

**What it is:** a sign model with one digit submodel per character of the station and a `BORDER` that belongs to the house groups. **Idiom** (the owner, 09-13: *no one driving by would know which station to tune to; the sign normally stays lit the whole song except in a blackout, with a fade in and out at the ends*): one plain `On` per digit per section, in the section's brightest scene colour lifted to full value (below luminance 0.18, white), abutting at seams, ~2 s fade in and out at the ends, dark ONLY inside a `stops` blackout (slam, no fade); never carried by a group bed; never answering a hit unless the song's config says so. **Enforced by:** `validate.py` check 7 (more than 1 s uncovered between show start and song end outside `stops` FAILs; n/a without a `tune_to` block). **Check:** expand the model in the sequencer: an unbroken `On` chain per digit from the first effect of the show to the song's end; on the render the digits read at every instant except inside a stop.

### minitrees: The small trees carry the big one; they are never the prop that is barely used

**What they are:** two 15 × 12 cones (180 nodes each) beside the big tree: a real grid, so directional effects travel. **Idiom** (the owner, 09-14: *"my mini trees are barely used. I often take the megatree and apply most of the effects over to them too to help carry it through the songs"*): every big-tree effect mirrored onto both, same span, palette and layer, with density or type TRANSLATED for the cone; a copied setting is not a copied effect (*they will never look the same, so the effect is translated so that it carries*); buffer style per axis (a mini tree ROW carries the big tree's style, the pair's GROUP row takes the show's per-type group style); never faces, masks, a Fire where the tree already burns, or anything over the tree's own material. **Enforced by:** `validate.py` check 8 (WARN when effect-seconds reaching the mini trees are under 40 % of the big tree's [SPECIFIC]; n/a said aloud when the layout lacks them). **Check:** scrub the big tree and both cones together: the same gesture, colour and span wherever the big tree moves; sum effect-seconds reaching each ÷ the big tree's (under 0.40 is the empty spot in the yard); on a render, lit node-seconds in the owner's 27-68 % band, not 7 %.

### floods: The floods match what the house shows and react the way the song does

**What they are:** five wall-wash channels pointed at the house, never in a house group (one pixel takes one sample of the group's pattern and blinks). **Idiom** (four songs, 10-06 to 10-11): the colour is never picked; it FOLLOWS the house read from the saved render (the garage, else the windows, else the peaks), change by change (*"I do need you to read the actual house"*); the reaction is the song's: a clap idiom flashes per clap, dark between; a wash song pulses on its own beat over a dim gliding bed that holds a FLOOR so a pulse never flashes from black (*"brighter not full on / off"*); a pulse in the wall's own hue behind props of that hue reads as the props pushing, so pulse the hits in white. **Enforced by:** not in this release: hand-check. **Check:** decode the flood channels every 50 ms: the colour matches the house's at that moment (lag ≈ 0; a 0.5 s lag was visible); where the song has a pulse the level rises on each one and falls back, never held steady.

### mesh3d: A 3D model is projected onto the prop's own geometry, never photographed onto it

**What the prop is:** a 180° cone (`TreeDegrees=180`, `TreeBottomTopRatio=7`, 32 strands × 100, read from the layout file, never assumed), so a buffer column is 5.6° of arc, not a flat pixel; the matrix is a flat screen. **Idiom:** a solid WRAPS the cone (it leaves the left edge because it has gone behind the tree and returns on the right), where a photograph of it is correct from one spot on the lawn only; a print file has NO paint and is painted ON ITS FEATURES, found in its own geometry, never by position or a projected photo (09-19: *do not project a photo onto the character's face; paint the actual model*); a textured glb that arrives painted skips all of it; **the tree gets the BODY, the screen gets the FACE** (detail is confetti at 32 columns, regions at 224); on an unlit prop a dark colour is a HOLE, so the silhouette boundary is outlined in a lit colour (*"black on a black tree… looks like white chunks and then missing pieces"*); a placed character CLAIMS its element unless it is a foreground clip with transparent black; a replaced clip gets a NEW NAME; the owner judges MOTION on a video of the cone, never a still. **Enforced by:** not in this release: hand-check. **Check:** the head's height range stays inside 0..1 for most of the span; peak coverage clears 5 % of the prop or it renders as a smudge; watch a preview drawn on the REAL cone, because on the unwrapped buffer a coil looks like a diagonal stripe.
