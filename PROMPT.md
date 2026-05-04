# Prompt for Claude Code

Paste everything below the line into Claude Code, in a fresh empty directory you've just `git init`'d. Three files should be in the directory: `SPEC.md`, `the-long-way.md`, and this `PROMPT.md`.

---

You are helping me build a personal task-engine for a 3-year learning syllabus. The system creates Todoist tasks, captures reflections as version-controlled markdown, and renders a static dashboard on GitHub Pages. Three files are in the working directory:

- `SPEC.md` — full design, including a phased build plan (Phases A through G).
- `the-long-way.md` — the syllabus the engine serves.
- `PROMPT.md` — this document.

## Workflow

**Read both `SPEC.md` and `the-long-way.md` in full before doing anything else.** Don't skim. The spec has explicit non-goals, a code-review checklist, and a phased plan; the syllabus has the rhythm structure that the templates will mirror. Both matter.

After reading:

1. **Ask me clarifying questions.** Section "Open questions for the owner" at the end of `SPEC.md` lists seven; add any you have of your own. Bundle them; don't ask one at a time. If a question's answer is obvious from the spec, skip it.

2. **Propose a Phase A plan.** List every file you'll create, what each contains, the order, and the smallest test for each piece. Wait for my approval before writing code.

3. **Implement Phase A only.** Phase A is the walking skeleton: two daily tasks, idempotency, one workflow, one test file, real Todoist integration. Do not start Phase B in this session even if Phase A finishes early. The phasing is the discipline; respect it.

4. **At the end of Phase A, write `STATUS.md`** summarizing what works, what's stubbed, what's next. This is the bridge for the next session.

## Phase boundaries (do not cross without explicit instruction)

The spec defines seven phases. **You are working on Phase A in this session.** When I'm ready for Phase B, I'll start a new conversation pointing at `STATUS.md` and the spec. Each phase has a "Done when" criterion in the spec — that's the verification gate. We do not move past a phase until I have manually confirmed the gate.

If you finish Phase A early in this session, options are:
- Add more tests within Phase A's scope.
- Improve docstrings, refactor for readability.
- Update `STATUS.md` with more detail.

Do **not** start Phase B speculatively.

## Constraints

- **Python 3.11+, stdlib plus `requests`, `pyyaml`, `pytest`, `markdown`.** No frameworks. No async unless justified. Type hints required.
- **Idempotency is the most important property.** Implement both layers (cache + content marker) in Phase A. Test both.
- **Strict read/write separation in `todoist.py`.** Phase A is write-only on Todoist. The read-only completion API arrives in Phase E. The architecture must support adding it without refactor.
- **Owner TZ from `config.yaml` (Asia/Kolkata) everywhere.** `zoneinfo` from stdlib. Never the runner's local time. Never naive datetimes.
- **Todoist token via GitHub Actions secrets and a local `.env` for dev.** Never committed. Never logged. If you write any debug output of config, the token must be redacted.
- **No deletes, no completions, no edits to existing tasks. Ever.**
- **Repo will be public.** State, reflections, logs are world-readable. Don't put anything in templates that the owner would mind being public.
- **Code is read by a learner.** Clarity over cleverness. Short functions. Module boundaries match the spec's diagram.
- **Commits: small, logical, imperative messages.** The git log is part of the artifact.

## Things that should make you stop and ask

- Wanting to add a database, a queue, a worker library, a hosted scheduler, an ORM, anything cloud-hosted: stop. The spec is deliberately minimal. Ask before adding.
- Wanting to parse the markdown syllabus more than the spec describes (the only runtime parse is `{current_book}` lookup): stop. Templates are the operational layer.
- Wanting to use any LLM call at runtime (for task content, reflection prompts, anything): no. Determinism is the design.
- A test feels hard to write: usually means the code is doing too much. Refactor before adding mocks.
- Hitting a real ambiguity: ask. Don't invent a workaround that I'll have to undo.

## What good Phase A looks like

By the end of this session:

- I can `cd` into the repo and read it without help.
- The Todoist project ID is in `config.yaml`, my token is configured locally and as a GH secret.
- I trigger `daily.yml` manually from the GitHub Actions UI (workflow_dispatch).
- Two tasks appear in my Todoist "Long Way" project, dated today, with the daily-ritual label.
- I trigger it again. Zero new tasks. The cache file's content marker logic is doing its job.
- I run `pytest` locally and on a PR. All tests pass.
- `STATUS.md` tells me exactly what's working and what Phase B should add.

## How to work with me

- After reading: ask the bundled questions.
- After my answers: propose the Phase A plan. Wait for approval.
- After approval: implement, committing as you go. Group commits logically; don't commit hundreds of tiny diffs.
- If you hit something genuinely blocking: stop and ask. Don't invent.
- Don't apologize, don't pad, don't repeat my instructions. Just build the thing.

Begin by reading `SPEC.md` and `the-long-way.md`, then ask your bundled questions.
