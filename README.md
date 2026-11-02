# xlights-sequencing-skill

A [Claude Code](https://claude.com/claude-code) skill for sequencing xLights light shows **with the house owner in the
loop**: measure their own finished sequences before proposing anything, place additively a window at a time, validate and
measure, render and save through xLights' automation API, prove the result in the decoded `.fseq`, and tweak one effect
at a time until the owner approves.

It is the method and the checking tools we arrived at over one Halloween season on one house, people and agents
working together: 13 songs on a 44-model display with singing props and a 94k-channel matrix, each approved on a saved
render and played every night of the run. The rules in `reference/rules.md` each carry the evidence they came from and
a hand-check; 15 of the 23 are enforced by code because documentation alone failed us: a rule written one evening was
broken four more times the same night by the agent that wrote it.

## What's here

| Path | What |
|---|---|
| `SKILL.md` | the instructions the agent loads: setup, analysis, building a window at a time, additive passes, approval, reporting |
| `reference/safety.md` | what breaks xLights automation (GPU hangs, lost edits, the view-list fault, sparse renders) and the refusal for each |
| `reference/rules.md` | the design rules: statement, scope, evidence, enforcement, hand-check |
| `reference/loop.md` | how to work with the owner: one decision per card, their eye outranks every count |
| `reference/xsq-format.md` | the `.xsq` and `.fseq` as they actually behave |
| `tools/` | `validate.py` (17 checks that refuse a bad file), `measure.py`, `xl.py` (the API driver with its locks and guards), `fseq.py` + `layout.py` + `snap.py` (read a render, draw a prop), `effects_diff.py`, `tc.py` |
| `examples/` | the shape of the per-song config (`sections.json`, `casting.json`, `scene_colors.json`) with made-up content |

## What's not here, on purpose

- **The composer.** The script that placed effects on the show this was learned on is entangled with that house (its
  multiprops, its singing pumpkins, its matrix) and would place badly anywhere else. You bring your own placer (a script
  per song, effects placed by hand in xLights, another tool) and this skill tells you how to check it and how to work
  with the owner.
- **The singing chain** (lyric sheet → forced alignment → every word verified and broken into syllables → mouth shapes
  where the voice makes them → blinks and pre-closes). It is the largest thing in the original toolkit and the most
  house-specific. A second release, maybe.
- **Anything of the show itself**: sequences, renders, layouts, audio, lyrics, photos, controller addresses.

## Requirements

- xLights **2026.17 or later** with the automation port on (Preferences → Output → API Port). Earlier builds cannot save
  from automation, so a render cannot be read back.
- **GPU rendering OFF** in xLights' preferences (`reference/safety.md` §1 says why; it cost nothing on a 6-core i9).
- Python 3.12 with `lxml`, `numpy`, `zstandard`, `pillow` for the tools. No GPU, no ML models: the analysis stack
  (stems, onsets, alignment) is yours to choose; the method says what it has to produce.

## Install

```sh
git clone <this repo> ~/.claude/skills/xlights-sequencing-skill     # every project
# or
git clone <this repo> <show>/.claude/skills/xlights-sequencing-skill  # one show folder
```

Start Claude Code in the xLights show folder (the one with `xlights_rgbeffects.xml`). First thing to ask it:

> Use the xlights sequencing skill. Profile my sequence `<song>/<song>.xsq` per row and tell me what I actually do.

Then `tools/validate.py <song>.xsq <show folder>` on a sequence you made by hand; the report says which of these rules
your own files already follow.

## Honest caveats

- Proved on **one** show, one season. The numbers tagged `[SPECIFIC]` are that show's; re-derive them from your own
  files before trusting them.
- Our one stranger test so far (the same method on another household's Christmas layout) was rejected outright on its
  fourth version; the fourteenth is unjudged. The method's own rule is that a prop you have not profiled from the show's
  finished file is a prop you do not know, and that test is where we learned it.
- xLights' automation API is what it is in 2026.17; later versions may rename commands.

## Related

[nod/skill-xlights](https://github.com/nod/skill-xlights) is another public Claude Code skill for xLights, built the same
autumn for a Christmas yard with a different shape: one generator script per song, the whole sequence regenerated each
time, judged from a timeline picture. Twelve of its rules match this one's, reached separately. Read both.

## License

MIT. See `LICENSE`.
