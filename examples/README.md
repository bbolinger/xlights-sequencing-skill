# Examples: the shape of the per-song config

These are the files the method keeps beside each song in `<song>/analysis/`. The content is made up; the **fields** are
the real ones. Keys beginning with `//` are comments and are ignored by every tool.

| File | What it holds | Who writes it |
|---|---|---|
| `sections.example.json` | sections with `intensity`, `intent` and `why`; the style `preset`; the whole-house group; `approved[]` ranges with the owner's words; measured `stops[]`; `casting`, `designs`, `tune_to`; the build frontier `built_to` | the agent proposes from the analysis; **the owner's ear corrects it**; the agent records approvals |
| `casting.example.json` | who sings from where, per line, from the script; which faces; blinks; `hand_edited` | the script, then the owner |
| `scene_colors.example.json` | the song's own palette per section, from the film's frames, with a `source` field saying whether it was sampled or authored by hand | the film, or the agent by hand (and it says so) |

Two rules the shapes carry:

- **Intent before placement.** A section without an `intent` (portion, what the music does, motif, why, build) is not
  ready to be built; the build says what each portion does as it builds it.
- **Approved ranges are locked.** `approved[]` + a snapshot `analysis/<song>.vN-APPROVED-<range>.xsq`; the next run
  reproduces the range by (element, effect, start ± 1 frame, end ± 1 frame) or refuses.

No real sequence is included: the show's sequences, layout and audio are theirs.
