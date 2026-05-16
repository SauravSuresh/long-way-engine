#!/usr/bin/env node
// Validates data/repos.json against the rules in SPEC.md §4.
// Default: offline checks (schema, types, duplicates). Always fail on error.
// --strict: also HEAD-checks each url and, when `ref` is set, {url}/tree/{ref}.
//   Network failures become warnings, not errors — CI runs this step under
//   continue-on-error so flaky GitHub doesn't break the build.

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const strict = process.argv.includes("--strict");

const errors = [];
const warnings = [];
const err = (m) => errors.push(m);
const warn = (m) => warnings.push(m);

const reposPath = resolve(root, "data/repos.json");
let repos;
try {
  repos = JSON.parse(readFileSync(reposPath, "utf8"));
} catch (e) {
  console.error(`FATAL: cannot read/parse ${reposPath}: ${e.message}`);
  process.exit(2);
}
if (!Array.isArray(repos)) {
  console.error("FATAL: repos.json root must be an array");
  process.exit(2);
}

const REQUIRED = [
  "id", "name", "url", "language", "themes",
  "difficulty", "why", "entry_points", "reading",
];
const KINDS = new Set(["blog", "paper", "talk", "doc"]);
const ID_RE = /^[a-z0-9-]+$/;

const seenIds = new Set();

for (let i = 0; i < repos.length; i++) {
  const r = repos[i];
  const loc = `[${i}]${r?.id ? ` id=${r.id}` : ""}`;

  if (!r || typeof r !== "object" || Array.isArray(r)) {
    err(`${loc}: not an object`);
    continue;
  }

  for (const f of REQUIRED) {
    if (!(f in r)) err(`${loc}: missing required field "${f}"`);
  }

  if ("id" in r) {
    if (typeof r.id !== "string") err(`${loc}: id must be a string`);
    else if (!ID_RE.test(r.id)) err(`${loc}: id must match ${ID_RE}`);
    else if (seenIds.has(r.id)) err(`${loc}: duplicate id "${r.id}"`);
    else seenIds.add(r.id);
  }

  for (const f of ["name", "url", "language", "why"]) {
    if (f in r && typeof r[f] !== "string") err(`${loc}: ${f} must be a string`);
  }

  if ("ref" in r && typeof r.ref !== "string") {
    err(`${loc}: ref must be a string when present`);
  }

  if ("themes" in r) {
    if (
      !Array.isArray(r.themes) ||
      r.themes.length === 0 ||
      !r.themes.every((t) => typeof t === "string")
    ) {
      err(`${loc}: themes must be a non-empty array of strings`);
    }
  }

  if ("difficulty" in r) {
    if (!Number.isInteger(r.difficulty) || r.difficulty < 1 || r.difficulty > 5) {
      err(`${loc}: difficulty must be an integer in 1..5`);
    }
  }

  if ("loc_estimate" in r) {
    if (!Number.isInteger(r.loc_estimate) || r.loc_estimate < 0) {
      err(`${loc}: loc_estimate must be a non-negative integer`);
    }
  }

  if ("entry_points" in r) {
    if (!Array.isArray(r.entry_points) || r.entry_points.length === 0) {
      err(`${loc}: entry_points must be a non-empty array`);
    } else {
      r.entry_points.forEach((ep, j) => {
        const eloc = `${loc}.entry_points[${j}]`;
        if (!ep || typeof ep !== "object" || Array.isArray(ep)) {
          err(`${eloc}: not an object`);
          return;
        }
        if (typeof ep.label !== "string") err(`${eloc}: label must be a string`);
        if (typeof ep.question !== "string") err(`${eloc}: question must be a string`);
        if (
          !Array.isArray(ep.files) ||
          ep.files.length === 0 ||
          !ep.files.every((f) => typeof f === "string")
        ) {
          err(`${eloc}: files must be a non-empty array of strings`);
        }
      });
    }
  }

  if ("reading" in r) {
    if (!Array.isArray(r.reading)) {
      err(`${loc}: reading must be an array (may be empty)`);
    } else {
      r.reading.forEach((rd, j) => {
        const rloc = `${loc}.reading[${j}]`;
        if (!rd || typeof rd !== "object" || Array.isArray(rd)) {
          err(`${rloc}: not an object`);
          return;
        }
        if (typeof rd.title !== "string") err(`${rloc}: title must be a string`);
        if (typeof rd.url !== "string") err(`${rloc}: url must be a string`);
        if (!KINDS.has(rd.kind)) {
          err(`${rloc}: kind must be one of ${[...KINDS].join("|")}`);
        }
      });
    }
  }
}

async function headCheck(url, label) {
  try {
    let res = await fetch(url, { method: "HEAD", redirect: "follow" });
    // Some hosts reject HEAD; retry with GET (don't read body).
    if (res.status === 405 || res.status === 501) {
      res = await fetch(url, { method: "GET", redirect: "follow" });
    }
    if (!res.ok) warn(`${label}: ${url} → HTTP ${res.status}`);
  } catch (e) {
    warn(`${label}: ${url} → ${e.message}`);
  }
}

if (strict) {
  const tasks = [];
  for (let i = 0; i < repos.length; i++) {
    const r = repos[i];
    if (!r || typeof r !== "object") continue;
    const loc = `[${i}]${r.id ? ` id=${r.id}` : ""}`;
    if (typeof r.url !== "string") continue;
    tasks.push(headCheck(r.url, `${loc}: url`));
    if (typeof r.ref === "string" && r.ref.length > 0) {
      const refUrl = `${r.url.replace(/\/+$/, "")}/tree/${encodeURIComponent(r.ref)}`;
      tasks.push(headCheck(refUrl, `${loc}: ref=${r.ref}`));
    }
  }
  await Promise.all(tasks);
}

for (const w of warnings) console.warn(`WARN  ${w}`);
for (const e of errors) console.error(`ERROR ${e}`);

if (errors.length > 0) {
  console.error(
    `\nValidation failed: ${errors.length} error(s), ${warnings.length} warning(s).`,
  );
  process.exit(1);
}

const noun = repos.length === 1 ? "entry" : "entries";
console.log(`OK: ${repos.length} ${noun} valid, ${warnings.length} warning(s).`);
