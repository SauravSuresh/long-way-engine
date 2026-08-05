# Rung 1, Option C — Flashcard drill CLI

**Concept:** Small sharp tools; parsing; table-driven tests; clean errors.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
You review Anki decks daily, but the GUI drills every due card the same
way and its stats don't answer the questions you actually have about your
own review habits. You want a terminal drill over your own exported decks,
with ordering and stats you control.

## Situation
It's early morning before work. You've exported one of your decks from
Anki. You run the drill CLI, answer cards one at a time in the terminal,
and get a stats summary the moment the session ends — no app to open.

## Scope
- Loads cards from a file exported from Anki (a defined export format —
  document which one in the README).
- Drills cards one at a time: shows the front, waits for input before
  revealing the back, records right/wrong per card.
- Cards answered wrong resurface earlier in the session (or the next one)
  than cards answered right — the ordering responds to your answers.
- Prints session stats at the end: cards reviewed, percent correct.
- Malformed rows in the export (missing field, blank line, stray
  delimiter) are handled without crashing the session.

## Non-goals
- No Anki sync, plugin, or database access — reads an exported file only.
- No GUI, images, or audio on cards.
- No modification of the original Anki collection.
- No claim of matching Anki's own spaced-repetition scheduling exactly.

## How it should NOT work
- Never crashes on a malformed export row — it's reported or skipped, not
  fatal.
- Never marks a card correct/incorrect based on anything other than your
  actual input for that card.
- Never loops indefinitely or re-serves an already-passed card without
  the wrong-answer rule applying.

## Acceptance
- `flashdrill mydeck.txt` runs a full session and ends by printing cards
  reviewed and percent correct.
- A fixture with a known set of right/wrong answers demonstrates that
  wrong-answered cards resurface sooner than right-answered ones.
- Table-driven tests cover parsing of the export format, including at
  least 5 malformed rows (missing field, blank line, extra delimiter,
  empty front/back, trailing whitespace).
- `go test ./...` and `go vet ./...` clean.
- README with install, how to export from Anki, and usage examples.
- ADR names the consumer: your own daily review, used for real.

## Starting nudge
Grab a real export of one of your decks, write down five well-formed rows
and five broken ones (missing tab, empty back, stray blank line) with the
parse result you want for each. That table is both your fixture and your
spec for what "garbage input handled" means here.

## ADR question
How do you parse — and where's the seam between the CLI and the reusable core?
