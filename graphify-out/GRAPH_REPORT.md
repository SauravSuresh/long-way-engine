# Graph Report - .  (2026-08-29)

## Corpus Check
- 81 files · ~180,128 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1751 nodes · 6433 edges · 41 communities detected
- Extraction: 39% EXTRACTED · 61% INFERRED · 0% AMBIGUOUS · INFERRED: 3906 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]

## God Nodes (most connected - your core abstractions)
1. `Config` - 209 edges
2. `SyllabusState` - 168 edges
3. `TodoistConfig` - 166 edges
4. `SharedState` - 138 edges
5. `State` - 130 edges
6. `Syllabus` - 119 edges
7. `DashboardConfig` - 114 edges
8. `ResolvedTemplate` - 113 edges
9. `Clock` - 109 edges
10. `MultiSyllabusConfig` - 96 edges

## Surprising Connections (you probably didn't know these)
- `Module` --shares_data_with--> `books_state Map`  [INFERRED]
  src/syllabus.py → README.md
- `Idempotency` --semantically_similar_to--> `Golden-Output Regression Tests`  [INFERRED] [semantically similar]
  SPEC.md → docs/superpowers/plans/2026-05-22-pluggable-curriculum.md
- `Long-Way Monthly Review Template` --semantically_similar_to--> `Neuroscience Monthly Review Template`  [INFERRED] [semantically similar]
  curricula/long-way/reflection_templates/monthly.md → examples/programmer-to-neuroscience-12mo/reflection_templates/monthly.md
- `Long-Way Monthly Review Template` --semantically_similar_to--> `ML-Engineer Monthly Review Template`  [INFERRED] [semantically similar]
  curricula/long-way/reflection_templates/monthly.md → examples/ml-engineer-12mo/reflection_templates/monthly.md
- `Long-Way Monthly Review Template` --semantically_similar_to--> `Frontend-Craft Monthly Review Template`  [INFERRED] [semantically similar]
  curricula/long-way/reflection_templates/monthly.md → examples/frontend-craft-6mo/reflection_templates/monthly.md

## Hyperedges (group relationships)
- **Idempotency & dedup machinery** — external_id, content_marker, task_cache, completion_cache [EXTRACTED 0.90]
- **Isolated Todoist client trio** — todoist_client, todoist_completion_client, todoist_admin_client [EXTRACTED 0.90]
- **Active learning practices** — read_real_code, trace_one_thing, build_thing_under, pair_engineer, debug_deliberately, oss_contribution, lineage_detours [EXTRACTED 0.90]
- **Weekly Reflection Templates Across Curricula** — longway_reflection_weekly, devops_reflection_weekly, neuro_reflection_weekly, ml_reflection_weekly, frontend_reflection_weekly [INFERRED 0.85]
- **Monthly Reflection Templates Across Curricula** — longway_reflection_monthly, devops_reflection_monthly, neuro_reflection_monthly, ml_reflection_monthly, frontend_reflection_monthly [INFERRED 0.82]
- **CS:APP Systems Learning Progression (12 Chapters)** — csapp_ch1_tour, csapp_ch2_data, csapp_ch3_machine, csapp_ch4_processor, csapp_ch5_optimization, csapp_ch6_memory, csapp_ch7_linking, csapp_ch8_ecf, csapp_ch9_vm, csapp_ch10_io, csapp_ch11_network, csapp_ch12_concurrent [EXTRACTED 1.00]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (180): App, Config, KeyError, assemble(), _cfg_shim(), initial_sections(), Pure logic for lw reflect: find targets, split/assemble template sections., (raw_frontmatter_block, sections) to pre-fill the form with.      If the stub fi (+172 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (175): NamespacedCache, Clock, FrozenClock, The single point where the system clock is read.  Every other module that needs, Reads the OS clock in the given timezone., Returns a fixed datetime.      `when` may be a date (combined with DEFAULT_TIME, DashboardConfig, MultiSyllabusConfig (+167 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (148): commit_and_push(), _git(), Auto commit+push for lw writes. Cron runs from GitHub: unpushed = invisible., append_log(), run(), sweep_past_due(), _daily_fires(), _is_first_of_quarter() (+140 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (147): _adherence_class(), _books_section(), build_data_multi_syllabus(), _catchup_days(), _end_of_journey(), _footer(), _github_blob_url(), _h() (+139 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (121): lift_flat_cache_under_syllabus(), load_cache(), load_namespaced_cache(), _looks_like_flat_cache(), prune(), Idempotency cache. Maps external_id -> task creation record.  The cache is the f, Drop entries whose created_at is older than `days`. Returns a new dict.      `no, Load cache from disk. Missing or corrupt -> empty dict. (+113 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (98): main(), lw — terminal interface to the long-way engine., build_streak_specs(), _build_parser(), _classify_skip(), Decision, main(), _module_titles_from_templates() (+90 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (69): _ensure_persistent_tasks(), apply_answers(), _atomic_write_yaml(), Write `data` as YAML to `path` atomically (write to .tmp then replace)., Persist per-syllabus state atomically., Persist shared (user-life-wide) state atomically., _dispatch(), evaluate_show_if() (+61 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (70): inject_banner(), main(), scripts/render_dashboard.py — synthetic-completion dashboard render.  Permanent, Insert the synthetic-render banner immediately after <body>., Treat every non-DRY-RUN cache task_id as a completion (flat cache)., synthetic_completion_set(), _coerce_date(), _coerce_optional_date() (+62 more)

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (77): Active Practices, AGENTS.md Curriculum Brief, Anki / Spaced Repetition Ritual, books_state Map, Build the Thing Under the Thing, Cadence Vocabulary, Single Clock Injection Point, .completion_cache.json (6h TTL) (+69 more)

### Community 9 - "Community 9"
Cohesion: 0.05
Nodes (56): load_config(), parse_env_file(), Tiny stdlib-only .env parser.      Lines like KEY=value. Blank lines and lines s, Token from .env if present, else from environment., Load config.yaml and resolve the Todoist token., _read_token(), external_id(), module_external_id() (+48 more)

### Community 10 - "Community 10"
Cohesion: 0.11
Nodes (50): _list_response(), make_client(), make_completion_client(), make_response(), make_template(), No syllabus:<key> label when template.syllabus_key is empty (transitional state), test_401_raises_immediately_no_retry(), test_4xx_other_raises_without_retry() (+42 more)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (51): _baseline_word_count(), count_words_in_body(), create_stub(), render_frontmatter(), _render_template(), split_frontmatter(), _strip_frontmatter_naively(), update_metadata() (+43 more)

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (49): build_multi_syllabus_scenario(), capture(), Golden-output capture: serialize run() decisions for a given date into a stable,, Write a fully-synthetic two-syllabus workspace into `tmp` and return     (config, Return a stable snapshot of every decision the engine makes for `today`.      Ca, write_golden(), load_templates(), Resolve placeholders in `s`. Public so reflections.py can reuse. (+41 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (39): _decl(), Tests for src/tracks.py: gate predicates + lifecycle transitions.  Both function, Owner skipped the window entirely; engine does NOT auto-flip., Owner started early (before window). Engine respects, no-op., _state(), test_expected_position_no_months_returns_pre_start(), test_expected_position_within_range(), test_gates_anded() (+31 more)

### Community 14 - "Community 14"
Cohesion: 0.1
Nodes (36): test_build_xp_lines_breakdown_and_ladder(), test_build_xp_lines_without_data(), _write_data(), _cfg(), _compute(), _syllabus(), test_cache_walk_classifies_and_respects_start_date(), test_defaults_when_config_missing() (+28 more)

### Community 15 - "Community 15"
Cohesion: 0.1
Nodes (23): ListItem, _brief_github_url(), Pure logic for lw rung start: brief discovery + paper/code scaffold.  No Todoist, The current rung's briefs (a/b/c), sorted by option letter., code_dir, if given, is the exact directory to scaffold code into     (e.g. the p, rung_options(), RungOption, scaffold() (+15 more)

### Community 16 - "Community 16"
Cohesion: 0.1
Nodes (33): load_multi_syllabus_config(), Two enabled syllabuses claim the same (ritual_times_key, clock_time)., SlotCollisionError, build_rows(), Collision, _extract_slot_key(), find_collisions(), _load_rituals_for_syllabus() (+25 more)

### Community 17 - "Community 17"
Cohesion: 0.1
Nodes (33): classify_reflection(), main(), One-shot migration: single-syllabus repo -> multi-syllabus repo.  Idempotent. Ru, _read_yaml(), rewrite_config_yaml(), run_migration(), split_state_yaml(), wrap_cache() (+25 more)

### Community 18 - "Community 18"
Cohesion: 0.15
Nodes (27): CurriculumError, Cross-cutting startup checks across all configured syllabuses.      Only enabled, Raised when a curriculum bundle has any validation violation., validate_multi_syllabus(), Exception, Validator must aggregate every violation into one CurriculumError.  Each test se, A syllabus.module without a matching once-per-module task is invalid., Build a curriculum dir with sane defaults, then apply overrides. (+19 more)

### Community 19 - "Community 19"
Cohesion: 0.1
Nodes (25): Amdahl's Law, Computer Systems: A Programmer's Perspective (CS:APP), Buffer Overflow and Code Security Vulnerabilities, Ch10: System-Level I/O, Ch11: Network Programming, Ch12: Concurrent Programming, Ch1: A Tour of Computer Systems, Ch2: Representing and Manipulating Information (+17 more)

### Community 20 - "Community 20"
Cohesion: 0.17
Nodes (17): bootstrap(), currentWeekKey(), dateToWeekKey(), el(), hash(), indexToWeekKey(), nextPick(), pick() (+9 more)

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (14): DevOps-Ready Monthly Retrospective Template, DevOps-Ready Weekly Reflection Template, Frontend-Craft Monthly Review Template, Frontend-Craft Weekly Review Template, Long-Way Annual Review Template, Long-Way Monthly Review Template, Long-Way Quarterly Synthesis Template, Long-Way Weekly Review Template (+6 more)

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (0): 

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): When the deadline gate resolved fail-forward (shipped/failed →     advance=True)

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): When the deadline gate resolved fail-forward (shipped/failed →     advance=True)

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): No syllabus:<key> label when template.syllabus_key is empty (transitional state)

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Cumulative XP required to reach level n. 0 for n <= 0.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): JSON-safe dict for data.json.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Load xp.yaml, filling any missing keys from built-in defaults.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Cumulative XP required to reach level n. 0 for n <= 0.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): JSON-safe dict for data.json.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): When the deadline gate resolved fail-forward (shipped/failed →     advance=True)

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): The picked challenge's meta.yaml for this rung, or None if not picked.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Repo-wide config for the multi-syllabus engine.      `default_ritual_times` is t

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Two enabled syllabuses claim the same (ritual_times_key, clock_time).

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Strip the Todoist token from any log record. Defense in depth.

## Knowledge Gaps
- **121 isolated node(s):** `Shared test fixtures.  Phase E added a dashboard render hook inside main.run().`, `CI environments don't have a real TODOIST_TOKEN, but several tests     exercise`, `Redirect src.main's path constants into a per-test tmp dir.      Tests that pass`, `Tests for scripts/migrate_to_multi_syllabus.py`, `A wrapped-but-empty namespace must not be double-wrapped.` (+116 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 22`** (2 nodes): `TestExpCalc()`, `exp_test.go`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `When the deadline gate resolved fail-forward (shipped/failed →     advance=True)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `When the deadline gate resolved fail-forward (shipped/failed →     advance=True)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `No syllabus:<key> label when template.syllabus_key is empty (transitional state)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Cumulative XP required to reach level n. 0 for n <= 0.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `JSON-safe dict for data.json.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Load xp.yaml, filling any missing keys from built-in defaults.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Cumulative XP required to reach level n. 0 for n <= 0.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `JSON-safe dict for data.json.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `When the deadline gate resolved fail-forward (shipped/failed →     advance=True)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `The picked challenge's meta.yaml for this rung, or None if not picked.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Repo-wide config for the multi-syllabus engine.      `default_ritual_times` is t`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Two enabled syllabuses claim the same (ritual_times_key, clock_time).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Strip the Todoist token from any log record. Defense in depth.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 9`, `Community 12`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `SyllabusState` connect `Community 1` to `Community 0`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 11`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `SyllabusEntry` connect `Community 1` to `Community 0`, `Community 4`, `Community 5`, `Community 6`, `Community 16`, `Community 18`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 206 inferred relationships involving `Config` (e.g. with `FakeSubtask` and `FakeReviewClient`) actually correct?**
  _`Config` has 206 INFERRED edges - model-reasoned connections that need verification._
- **Are the 166 inferred relationships involving `SyllabusState` (e.g. with `Add anki + morning-reading entries for date d. Returns (anki_id, morning_id).` and `Mon-Tue-Wed before Thu: 3 days, all done. Today=Thu.`) actually correct?**
  _`SyllabusState` has 166 INFERRED edges - model-reasoned connections that need verification._
- **Are the 164 inferred relationships involving `TodoistConfig` (e.g. with `FakeSubtask` and `FakeReviewClient`) actually correct?**
  _`TodoistConfig` has 164 INFERRED edges - model-reasoned connections that need verification._
- **Are the 136 inferred relationships involving `SharedState` (e.g. with `FakeSubtask` and `FakeReviewClient`) actually correct?**
  _`SharedState` has 136 INFERRED edges - model-reasoned connections that need verification._