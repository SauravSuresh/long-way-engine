#!/usr/bin/env node
// Smoke tests for the picker. Run: node scripts/test-picker.mjs
// Exits non-zero on any failure. When tuning constants, update expectations
// here to match the new values — that's the contract these tests pin down.

import {
  hash,
  weekKeyToIndex,
  indexToWeekKey,
  targetDifficulty,
  proximity,
  recencyWeeks,
  pick,
  pickAt,
  nextPick,
  START_WEEK,
  THEMES,
} from "../app.js";

const tests = [];
const eq = (label, a, b) =>
  tests.push([label, JSON.stringify(a) === JSON.stringify(b), a, b]);

const startIdx = weekKeyToIndex(START_WEEK);
const offset = (n) => indexToWeekKey(startIdx + n);

// hash
eq("hash deterministic", hash("2026-W20"), hash("2026-W20"));
eq("hash differs across keys", hash("2026-W20") !== hash("2026-W21"), true);

// ISO week round-trips (incl. 53-week year 2026 and year boundaries)
for (const wk of [
  "2026-W20", "2026-W01", "2026-W52", "2026-W53",
  "2025-W01", "2025-W52",
]) {
  eq(`round-trip ${wk}`, indexToWeekKey(weekKeyToIndex(wk)), wk);
}
eq(
  "adjacent weeks differ by 1",
  weekKeyToIndex("2026-W20") - weekKeyToIndex("2026-W19"),
  1,
);
eq(
  "year boundary 2025-W52 → 2026-W01",
  indexToWeekKey(weekKeyToIndex("2025-W52") + 1),
  "2026-W01",
);

// Difficulty curve: 16 weeks per level, cap at 5
eq("target +0w  = 1", targetDifficulty(START_WEEK), 1);
eq("target +15w = 1", targetDifficulty(offset(15)), 1);
eq("target +16w = 2", targetDifficulty(offset(16)), 2);
eq("target +63w = 4", targetDifficulty(offset(63)), 4);
eq("target +64w = 5", targetDifficulty(offset(64)), 5);
eq("target +200w cap=5", targetDifficulty(offset(200)), 5);

// Proximity: gaussian, sigma=1.3
eq("proximity exact match = 1", proximity(3, 3), 1);
eq("proximity symmetric", proximity(2, 3), proximity(4, 3));
eq("proximity decays with distance", proximity(1, 3) < proximity(2, 3), true);
// exp(-4 / 3.38) ≈ 0.30623
eq(
  "proximity(diff=2) ≈ 0.3062 at sigma=1.3",
  Math.round(proximity(2, 4) * 10000),
  3062,
);

// Recency window — min(12, floor(N * 0.4))
eq("recency N=0",   recencyWeeks([]),           0);
eq("recency N=20",  recencyWeeks(Array(20)),    8);
eq("recency N=30",  recencyWeeks(Array(30)),   12);
eq("recency N=40",  recencyWeeks(Array(40)),   12);
eq("recency N=100", recencyWeeks(Array(100)),  12);

// Synthetic repo set
const repos = [
  {
    id: "a", themes: ["databases", "storage"], difficulty: 2,
    entry_points: [
      { label: "x", files: ["a"], question: "?" },
      { label: "y", files: ["b"], question: "?" },
    ],
  },
  {
    id: "b", themes: ["networking"], difficulty: 3,
    entry_points: [{ label: "x", files: ["a"], question: "?" }],
  },
  {
    id: "c", themes: ["compilers", "runtime"], difficulty: 4,
    entry_points: [{ label: "x", files: ["a"], question: "?" }],
  },
  {
    id: "d", themes: ["cli-tools", "search"], difficulty: 1,
    entry_points: [{ label: "x", files: ["a"], question: "?" }],
  },
];

const p1 = pick("2026-W20", repos);
const p2 = pick("2026-W20", repos);
eq("pick deterministic", p1.repo.id, p2.repo.id);
eq(
  "pick shape",
  Object.keys(p1).sort(),
  ["entryPoint", "repo", "target", "theme"],
);
eq("pick theme is in THEMES rotation", THEMES.includes(p1.theme), true);
eq(
  "pickAt at START_WEEK ≡ pick (no history)",
  pickAt(START_WEEK, repos, new Set()).repo.id,
  pick(START_WEEK, repos).repo.id,
);

const chosen = pickAt("2026-W20", repos, new Set()).repo.id;
const excluded = pickAt("2026-W20", repos, new Set([chosen]));
eq("recency excludes chosen", excluded.repo.id !== chosen, true);
eq(
  "all-excluded returns null",
  pickAt("2026-W20", repos, new Set(repos.map((r) => r.id))),
  null,
);
eq("empty pool returns null", pick("2026-W20", []), null);

// nextPick (sequence-mode reading list)
const np0 = nextPick(repos, new Set());
eq("nextPick empty completed returns pick", np0 !== null, true);
eq(
  "nextPick empty completed ≡ pick at START_WEEK",
  np0.repo.id,
  pick(START_WEEK, repos).repo.id,
);
eq("nextPick includes weekKey", typeof np0.weekKey, "string");

const np1 = nextPick(repos, new Set([np0.repo.id]));
eq("nextPick skips completed repo", np1.repo.id !== np0.repo.id, true);

const allDone = new Set(repos.map((r) => r.id));
eq("nextPick returns null when all completed", nextPick(repos, allDone), null);

eq("nextPick empty pool returns null", nextPick([], new Set()), null);

let pass = 0, fail = 0;
for (const [label, ok, got, want] of tests) {
  if (ok === true) pass++;
  else {
    fail++;
    console.log(
      "FAIL",
      label,
      "\n  got:  ",
      JSON.stringify(got),
      "\n  want: ",
      JSON.stringify(want),
    );
  }
}
console.log(`${pass} pass, ${fail} fail`);
process.exit(fail === 0 ? 0 : 1);
