#!/usr/bin/env node
// Simulates the picker over 156 weeks starting at START_WEEK and writes
// scripts/simulate-output/picks.csv + summary.txt.
//
// Imports pick() (the real forward-replay function), not pickAt — if replay
// has a bug we want to see it here, not work around it.
// Deterministic: re-running produces byte-identical output.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  pick,
  weekKeyToIndex,
  indexToWeekKey,
  recencyWeeks,
  START_WEEK,
  THEMES,
} from "../app.js";

const WEEKS = 156;
const BLOCK = 12;

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const outDir = resolve(here, "simulate-output");
mkdirSync(outDir, { recursive: true });

const reposPath = resolve(root, "data/repos.json");
const repos = JSON.parse(readFileSync(reposPath, "utf8"));
if (!Array.isArray(repos) || repos.length === 0) {
  console.error(
    "FATAL: data/repos.json is empty. Run `node scripts/make-stub.mjs` first.",
  );
  process.exit(2);
}

// --- run the picker for every week ---
const startIdx = weekKeyToIndex(START_WEEK);
const rows = [];
for (let w = 0; w < WEEKS; w++) {
  const wk = indexToWeekKey(startIdx + w);
  const p = pick(wk, repos);
  if (!p) {
    console.error(`FATAL: null pick at ${wk} (week ${w}). Investigate weights.`);
    process.exit(2);
  }
  rows.push({
    week: w,
    weekKey: wk,
    repoId: p.repo.id,
    theme: p.theme,
    target: p.target,
    actualDifficulty: p.repo.difficulty,
  });
}

// --- picks.csv ---
const csv =
  [
    "week,weekKey,repoId,theme,target,actualDifficulty",
    ...rows.map((r) =>
      [r.week, r.weekKey, r.repoId, r.theme, r.target, r.actualDifficulty].join(","),
    ),
  ].join("\n") + "\n";
writeFileSync(resolve(outDir, "picks.csv"), csv);

// --- analysis ---
function regress(xs, ys) {
  const n = xs.length;
  let sx = 0, sy = 0;
  for (let i = 0; i < n; i++) { sx += xs[i]; sy += ys[i]; }
  const xm = sx / n, ym = sy / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) {
    num += (xs[i] - xm) * (ys[i] - ym);
    den += (xs[i] - xm) ** 2;
  }
  return { slope: num / den, intercept: ym - (num / den) * xm };
}

function correlation(xs, ys) {
  const n = xs.length;
  let sx = 0, sy = 0;
  for (let i = 0; i < n; i++) { sx += xs[i]; sy += ys[i]; }
  const xm = sx / n, ym = sy / n;
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) {
    num += (xs[i] - xm) * (ys[i] - ym);
    dx += (xs[i] - xm) ** 2;
    dy += (ys[i] - ym) ** 2;
  }
  return num / Math.sqrt(dx * dy);
}

const weeks = rows.map((r) => r.week);
const targets = rows.map((r) => r.target);
const actuals = rows.map((r) => r.actualDifficulty);
const targetReg = regress(weeks, targets);
const actualReg = regress(weeks, actuals);
const corr = correlation(targets, actuals);

function plateauMean(t) {
  const xs = rows.filter((r) => r.target === t);
  if (xs.length === 0) return { n: 0, mean: NaN };
  return {
    n: xs.length,
    mean: xs.reduce((a, r) => a + r.actualDifficulty, 0) / xs.length,
  };
}
const plat4 = plateauMean(4);
const plat5 = plateauMean(5);

const counts = new Map();
for (const r of repos) counts.set(r.id, 0);
for (const row of rows) counts.set(row.repoId, counts.get(row.repoId) + 1);
const sortedCounts = [...counts.entries()].sort(
  (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
);

const picksByRepo = new Map();
for (const r of repos) picksByRepo.set(r.id, []);
for (const row of rows) picksByRepo.get(row.repoId).push(row.week);

function median(xs) {
  if (xs.length === 0) return NaN;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

const recWk = recencyWeeks(repos);
const gapMinFloor = recWk + 1;
const gapRows = [];
for (const [id, picks] of picksByRepo) {
  if (picks.length < 3) continue;
  const gaps = [];
  for (let i = 1; i < picks.length; i++) gaps.push(picks[i] - picks[i - 1]);
  gapRows.push({
    id,
    count: picks.length,
    minGap: Math.min(...gaps),
    medianGap: median(gaps),
  });
}
gapRows.sort((a, b) => b.count - a.count || a.id.localeCompare(b.id));
const recencyBugs = gapRows.filter((g) => g.minGap < gapMinFloor);
const windowTight = gapRows.filter((g) => g.count >= 8 && g.medianGap < 13);

const numBlocks = Math.ceil(WEEKS / BLOCK);
const themeBlocks = [];
for (let b = 0; b < numBlocks; b++) {
  const m = new Map();
  for (const t of THEMES) m.set(t, 0);
  for (let w = b * BLOCK; w < Math.min((b + 1) * BLOCK, WEEKS); w++) {
    m.set(rows[w].theme, (m.get(rows[w].theme) ?? 0) + 1);
  }
  themeBlocks.push(m);
}
const themeTotals = new Map();
for (const t of THEMES) themeTotals.set(t, 0);
for (const row of rows) {
  themeTotals.set(row.theme, (themeTotals.get(row.theme) ?? 0) + 1);
}

// --- summary.txt ---
const expectedAvg = WEEKS / repos.length;
const zeros = sortedCounts.filter(([, c]) => c === 0).map(([id]) => id);
const heavy = sortedCounts.filter(([, c]) => c > 8);

const fmt = (n, d = 4) => n.toFixed(d);
const padR = (s, w) => String(s).padEnd(w);
const padL = (s, w) => String(s).padStart(w);

const out = [];
out.push(`read-real-code picker simulation`);
out.push(
  `START_WEEK=${START_WEEK}  weeks=${WEEKS}  repos=${repos.length}  recencyWeeks=${recencyWeeks(repos)}`,
);
out.push("");
out.push(`# Difficulty curve  (target vs actual)`);
out.push(
  `  target  slope/week ${fmt(targetReg.slope)}   intercept ${fmt(targetReg.intercept)}   mean ${fmt(targets.reduce((a, v) => a + v, 0) / targets.length, 3)}`,
);
out.push(
  `  actual  slope/week ${fmt(actualReg.slope)}   intercept ${fmt(actualReg.intercept)}   mean ${fmt(actuals.reduce((a, v) => a + v, 0) / actuals.length, 3)}`,
);
out.push(`  correlation r(target, actual): ${fmt(corr)}`);
out.push(
  `  plateau mean actual difficulty @ target=4 (N=${plat4.n}): ${isNaN(plat4.mean) ? "n/a" : fmt(plat4.mean, 3)}`,
);
out.push(
  `  plateau mean actual difficulty @ target=5 (N=${plat5.n}): ${isNaN(plat5.mean) ? "n/a" : fmt(plat5.mean, 3)}`,
);
out.push("");
out.push(`# Pick count per repo  (expected ≈${expectedAvg.toFixed(1)}; flag = ZERO if 0, HEAVY if >8)`);
const idW = Math.max(...repos.map((r) => r.id.length));
for (const [id, c] of sortedCounts) {
  const flag = c === 0 ? "  ZERO" : c > 8 ? "  HEAVY" : "";
  out.push(`  ${padR(id, idW)}  ${padL(c, 3)}${flag}`);
}
out.push("");
out.push(
  `# Pick gap distribution  (repos with ≥3 picks; gap = weeks between consecutive picks)`,
);
out.push(
  `  RECENCY-BUG flag: min gap < ${gapMinFloor} (= recencyWeeks + 1). Means exclusion failed.`,
);
out.push(
  `  WINDOW-TIGHT flag: count ≥ 8 AND median gap < 13. Recency window too short at scale.`,
);
out.push(`  ${padR("repo", idW)}  count  min  median  flags`);
for (const g of gapRows) {
  const flags = [];
  if (g.minGap < gapMinFloor) flags.push("RECENCY-BUG");
  if (g.count >= 8 && g.medianGap < 13) flags.push("WINDOW-TIGHT");
  out.push(
    `  ${padR(g.id, idW)}  ${padL(g.count, 5)}  ${padL(g.minGap, 3)}  ${padL(g.medianGap.toFixed(1), 6)}  ${flags.join(" ")}`,
  );
}
out.push("");
out.push(
  `# Recency-bug rows:  ${recencyBugs.length === 0 ? "none" : recencyBugs.map((g) => `${g.id}(min=${g.minGap})`).join(", ")}`,
);
out.push(
  `# Window-tight rows: ${windowTight.length === 0 ? "none" : windowTight.map((g) => `${g.id}(median=${g.medianGap.toFixed(1)})`).join(", ")}`,
);
out.push("");
out.push(`# Theme per 12-week block  (rows = themes in rotation order, cols b00..b${String(numBlocks - 1).padStart(2, "0")})`);
const themeW = Math.max(...THEMES.map((t) => t.length));
const blockCols = themeBlocks.map((_, i) => `b${String(i).padStart(2, "0")}`).join(" ");
out.push(`  ${padR("theme", themeW)}  ${blockCols}  total`);
for (const t of THEMES) {
  const cells = themeBlocks
    .map((m) => padL(m.get(t) ?? 0, 3))
    .join(" ");
  out.push(`  ${padR(t, themeW)}  ${cells}  ${padL(themeTotals.get(t), 5)}`);
}
out.push("");
out.push(
  `# Repos never picked: ${zeros.length === 0 ? "none" : zeros.join(", ")}`,
);
out.push(
  `# Repos picked >8 times: ${heavy.length === 0 ? "none" : heavy.map(([id, c]) => `${id}=${c}`).join(", ")}`,
);
out.push("");

writeFileSync(resolve(outDir, "summary.txt"), out.join("\n"));
console.log(`wrote ${rows.length} rows → scripts/simulate-output/picks.csv`);
console.log(`wrote summary    → scripts/simulate-output/summary.txt`);
