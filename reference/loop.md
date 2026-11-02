# The loop with the owner

The owner judges on a saved render of their own display. You never see it. Everything below exists to make one round
trip count.

## Before the first question

1. Measure the show's own sequences for the prop or the idiom before designing — durations, types, colours, pairings,
   buffer styles — weighted by use, per row of their file, excluding anything generated.
2. Say where their instruction differs from their habit. **Their instruction wins** [SPECIFIC example: a spider's
   hourglass red by their word; their files said purple 82 of 83 times].
3. Read the rule entry for the area you are about to touch (`rules.md`), in the session doing the work. A one-liner
   remembered from an earlier session is not enough.
4. Know what each prop IS and what each effect DOES before proposing either. Draw the model from its own definition,
   look at the photo of the house, read the show's file for that row.

## Questions

- **One decision per card**, recommended option first, the numbers in the option text ("three fire rings at 2:23.4 /
  2:27.0 / 2:31.4, 100/100/80 % — the first two peak 0.3 dB apart, the third collapses"). Never a list of questions in
  prose.
- Read the answer as words. Owners correct the premise more often than they pick an option. "go" means apply exactly what
  was shown.
- No questions while the owner is outside looking at the yard — they will tell you what they see. [the owner, 2026-10-26: no
  pop-up questions during a live look; they will respond on their own]
- "Is it possible?" gets an answer, not a build plan.
- Positions in m:ss; a duration under a minute in seconds.

## Placement

1. Dry-run twice, diff, show the placement list, then apply — additive, on the prop's own submodels, into free spans.
2. `validate` + `measure`; then prove it in the raw `<ElementEffects>` XML.
3. `open` → `render` → `save` (serial; nothing else in between; `safety.md` §2).
4. Decode the `.fseq` at the exact channels, strictly inside each span, peak over the span. Send a still of the prop
   from the render (`snap.py`) — a picture beats a count.
5. One effect at a time once a section is roughly right. One song at a time: wait for the owner's look before the next.

## Approval

- On approval: snapshot `analysis/<song>.vN-APPROVED-<range>.xsq`, add the range to `approved[]` with the owner's words
  in `why`, verify the next run reproduces it.
- The frontier `built_to` advances per window; below it nothing is regenerated.
- After any xLights save: re-baseline first, compare by frame, then run the next tool.
- Their hand edits in xLights outrank your config: diff against your last write and carry them; a tool that would rebuild
  an edited track refuses.

## What the owner's eye outranks

Every count, every measurement, every second opinion. Several of the worst errors — flames along the roofline, eyes
written into the view list, a decoder off by one channel, a face that "just moves up and down" — read as plausible in a
written critique. When they say *"I don't see it"*: raw XML of the element, then the `.fseq` at its channels, then the
row order above it. When they say they can't see it, it is too **dim** — never propose darker.

An outside review (another model, another person) is a perspective, not orders: check each claim against the file and
the render, split defects from the owner's decisions, push back with numbers.

## Session hygiene

- Journal first (dated, what was measured), then the rule, then the one-liner. Never the other way.
- A new rule is a journal entry → a rule entry with `Scope` → a one-liner. **When a rule matters, add the check that
  refuses the file** — a rule written in prose was broken four more times the same night by the agent that wrote it.
- When a data model goes from "one at a time" to "several at once", re-check every consumer at once (overlapping singers
  broke five tools, one round trip each).
- A check that quietly skips is worse than no check: `DID NOT RUN` is a failure.
- End every session by rewriting the handoff page (what was done, what is in flight, what to do first, the owner's last
  binding words, what is unproved). A session that ends without it has not ended.
