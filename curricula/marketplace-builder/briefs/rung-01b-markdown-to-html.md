# Rung 1, Option B — Markdown to HTML converter

**Concept:** Small sharp tools; parsing; table-driven tests; clean errors.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Previewing a markdown file — a README before you push, a note before you
paste it somewhere — usually means a browser plugin, an editor extension,
or pushing to GitHub just to see how it renders. You want one small binary
that turns a markdown file into HTML you can open directly, with no
service and no guessing at what it will do with malformed input.

## Situation
It's evening, you're finishing the README for one of your repos before you
push. You run `md2html README.md > README.html`, open it locally, and
catch a botched code fence before anyone else sees it.

## Scope
- Converts a single markdown file (or stdin) to an HTML file (or stdout):
  `md2html notes.md > notes.html`.
- Supports a defined subset of markdown: headings, paragraphs, bold/italic,
  inline code, fenced code blocks, links, and lists — the exact subset is
  yours to pick and must be stated in the README.
- Output for a given input is byte-for-byte identical on every run
  (deterministic).
- Malformed or edge-case input (unterminated fence, empty file, unclosed
  emphasis marker) is handled without a crash.
- `--help` explains usage in ≤10 lines.

## Non-goals
- No full CommonMark or GitHub-Flavored-Markdown compliance.
- No live preview, file watching, or server mode.
- No embedded images, syntax highlighting, or CSS theming.
- No config file for output style.

## How it should NOT work
- Never a stack trace or panic reaching the user, no matter the input
  (unterminated fence, empty file, deeply nested lists are all handled).
- Never silently drops content — a construct outside your declared subset
  is reported or passed through predictably, not eaten.
- Never produces different output for the same input on a second run.

## Acceptance
- `md2html sample.md` produces HTML matching a checked-in golden file for
  that input, byte for byte.
- Golden-file tests cover: headings, emphasis, inline code, fenced code
  blocks, links, lists, and at least 3 malformed/edge-case inputs.
- Malformed input (unterminated fence, empty file) exits cleanly with no
  crash, per the behavior documented in the README.
- `go test ./...` and `go vet ./...` clean.
- README stating the supported subset, install instructions, and 3 usage
  examples.
- ADR names a real consumer (per the rung rules: you, operating it — e.g.
  your own repo READMEs, previewed before push).

## Starting nudge
Pull five real markdown files you already have — a couple of your own
READMEs — and hand-write the HTML you want for each before writing any
parsing code. Those become your golden files and pin down exactly which
subset you're committing to.

## ADR question
How do you parse — and where's the seam between the CLI and the reusable core?
