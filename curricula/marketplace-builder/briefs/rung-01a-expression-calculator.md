# Rung 1, Option A — Expression calculator CLI

**Concept:** Small sharp tools; parsing; table-driven tests; clean errors.
**Language:** Go by default; another language is allowed if your ADR argues it teaches more.

## Problem
Shell arithmetic is miserable: `expr` chokes on `*`, `bc` needs flags to do
floats, and neither gives a usable error when you typo an expression. You
want one small binary that evaluates ordinary infix arithmetic exactly the
way a calculator would, and tells you precisely what's wrong when it can't.

## Situation
You're in a terminal splitting a gear-rental invoice: `calc '(1450*3 + 800) / 4'`.
You fat-finger a parenthesis. Instead of a cryptic `parse error`, the tool
shows you where the expression broke and you fix it without breaking flow.

## Scope
- Evaluates a single expression passed as one CLI argument: `calc '2*(3+4)'` → `14`.
- Operators: `+ - * /`, unary minus, parentheses, decimal numbers.
- Correct precedence and associativity (`2+3*4` → `14`; `2-3-4` → `-5`).
- Division by zero reported as an error, not a panic or `+Inf`.
- Malformed input produces a one-line error naming the position or token
  that broke parsing, and a non-zero exit code.
- `--help` explains usage in ≤10 lines.

## Non-goals
- No variables, functions, or constants (`pi`, `sqrt` — no).
- No REPL/interactive mode; one expression per invocation.
- No arbitrary-precision arithmetic; float64 is fine.
- No expression history, config file, or colors.

## How it should NOT work
- Never a stack trace or panic reaching the user, no matter the input
  (`calc '((('`, `calc ''`, `calc '$(rm -rf /)'` are all one-line errors).
- Never a wrong answer accepted silently — precedence bugs are the failure
  mode this rung exists to catch.
- Never exit 0 when evaluation failed.

## Acceptance
- `calc '2*(3+4)'` prints `14`, exit 0.
- `calc '2+3*4'` prints `14` (precedence, not left-to-right `20`).
- `calc '1/0'` prints a one-line error mentioning division by zero, exit 1.
- `calc '2*('` prints a one-line error pointing at the problem, exit 1.
- Table-driven tests cover: precedence, associativity, parentheses, unary
  minus, decimals, and at least 5 malformed inputs.
- `go test ./...` and `go vet ./...` clean.
- README with install + 3 usage examples.
- ADR names a real consumer (per the rung rules: you, operating it).

## Starting nudge
Write the table of test cases first — valid expressions with expected
values, malformed ones with the error you'd want to see. That table forces
you to decide error wording and edge behavior before any parsing code
exists, and it becomes your table-driven test verbatim.

## ADR question
How do you parse — and where's the seam between the CLI and the reusable core?
