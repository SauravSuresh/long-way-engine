# long-way-engine

Turns multi-month learning plans into daily Todoist tasks and a dashboard. The seasons layer (planned) decides which plan gets the owner's deep hours at any given time.

## Language

### Content

**Syllabus**:
A self-contained content bundle (`curricula/<key>/`) with phases, months, modules, books, rituals and reflection templates. Runs for months to years.
_Avoid_: curriculum (as a noun for the bundle), track, course

**Track**:
A named thread inside one Syllabus (e.g. "AWS Solutions Architect Associate" under Certifications) with a lifecycle state. Declared under `tracks:` in the syllabus. Never means a parallel Syllabus.
_Avoid_: using "track" for anything outside a Syllabus

**Ritual**:
A templated recurring task a Syllabus emits on a cadence.

### Seasons

**Season**:
A time-boxed focus on one Milestone. Has a start, an end, and a Lane. Six to twelve weeks is the intended size.

**Milestone**:
The deliverable a Season aims at, sized in hours. Optionally bound to a Syllabus and a range within it (a phase, a rung range). May have no Syllabus at all.
_Avoid_: project, goal, dream

**Bare Season**:
A Season whose Milestone has no Syllabus behind it. Gets only a deep-block task and hours tracking.

**Bucket**:
The ordered queue of Milestones not yet given a Season. Order is the only decision.
_Avoid_: backlog, todo list

**Lane**:
Which share of the week's deep blocks a Season holds: `main` (most blocks) or `side` (only the days marked side).

**Deep Block**:
A fixed daily window reserved for the active Season's Milestone.

**Discipline**:
A short daily habit (Anki, writing, workout) that never takes a Season. Scheduled by the seasons layer, life-wide, not owned by any Syllabus.
_Avoid_: habit, common task

**Rest Week**:
The week with no deep blocks between the end of one main Season and the start of the next.

**Off-season**:
A Syllabus that is not the Milestone of a live Season. Its state is paused and its month does not advance.
_Avoid_: disabled, parked
