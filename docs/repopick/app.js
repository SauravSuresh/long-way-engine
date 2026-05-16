// Pure picker. No DOM, no `new Date()` without an explicit argument, no I/O.
// Browser bootstrap and rendering live elsewhere (added in step 6).
// SPEC.md §5 and §11 are the source of truth for the algorithm and constants.

export const START_WEEK = "2026-W20";
export const RECENCY_WEEKS_MAX = 12;
export const WEEKS_PER_LEVEL = 16;
export const PROXIMITY_SIGMA = 1.3;
export const THEMES = [
  "databases",
  "distributed-systems",
  "cli-tools",
  "networking",
  "compilers",
  "ml-infra",
  "runtime",
  "language",
  "storage",
  "unix-tools",
  "networking-tools",
];

// FNV-1a 32-bit. Deterministic, fast, enough mixing for our scale.
export function hash(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

// --- ISO week math (UTC throughout to dodge timezone shifts). ---

const MS_PER_DAY = 86_400_000;
const MS_PER_WEEK = 7 * MS_PER_DAY;
const WEEK_KEY_RE = /^(\d{4})-W(\d{1,2})$/;

function thursdayOfWeek(year, week) {
  // Jan 4 is always in ISO week 1 of its year.
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const jan4Day = jan4.getUTCDay() || 7; // ISO: Sun=7
  const thuW1 = new Date(jan4);
  thuW1.setUTCDate(jan4.getUTCDate() + (4 - jan4Day));
  const thu = new Date(thuW1);
  thu.setUTCDate(thuW1.getUTCDate() + (week - 1) * 7);
  return thu;
}

function dateToWeekKey(d) {
  const day = d.getUTCDay() || 7;
  const thu = new Date(d);
  thu.setUTCDate(d.getUTCDate() + (4 - day));
  const year = thu.getUTCFullYear();
  const thuW1 = thursdayOfWeek(year, 1);
  const diffDays = Math.round((thu - thuW1) / MS_PER_DAY);
  const week = Math.floor(diffDays / 7) + 1;
  return `${year}-W${String(week).padStart(2, "0")}`;
}

// Epoch (Jan 1 1970) is a Thursday, so Thursday-of-ISO-week ms / MS_PER_WEEK
// is always an exact integer. Indices are signed and may be subtracted directly.
export function weekKeyToIndex(weekKey) {
  const m = WEEK_KEY_RE.exec(weekKey);
  if (!m) throw new Error(`bad week key: ${weekKey}`);
  return Math.round(thursdayOfWeek(Number(m[1]), Number(m[2])).getTime() / MS_PER_WEEK);
}

export function indexToWeekKey(idx) {
  return dateToWeekKey(new Date(idx * MS_PER_WEEK));
}

// --- Picker primitives ---

export function recencyWeeks(repos) {
  return Math.min(RECENCY_WEEKS_MAX, Math.floor(repos.length * 0.4));
}

export function targetDifficulty(weekKey) {
  const w = weekKeyToIndex(weekKey) - weekKeyToIndex(START_WEEK);
  return 1 + Math.min(4, Math.max(0, Math.floor(w / WEEKS_PER_LEVEL)));
}

// Gaussian centred on target, width PROXIMITY_SIGMA. Returns a value in (0, 1].
export function proximity(d, target) {
  const diff = d - target;
  return Math.exp(-(diff * diff) / (2 * PROXIMITY_SIGMA * PROXIMITY_SIGMA));
}

// Deterministic weighted pick over (items, weights) keyed by `seed`.
function weightedPick(items, weights, seed) {
  let total = 0;
  for (let i = 0; i < weights.length; i++) total += weights[i];
  if (total <= 0) return null;
  const r = ((seed >>> 0) / 0x1_0000_0000) * total;
  let acc = 0;
  for (let i = 0; i < items.length; i++) {
    acc += weights[i];
    if (r < acc) return items[i];
  }
  return items[items.length - 1]; // float-rounding edge
}

// Pick for a week given a pre-computed set of recent ids. Pure.
// The simulator calls this directly so it can carry its own sliding window
// instead of replaying history every step.
export function pickAt(weekKey, repos, recentIds) {
  if (!Array.isArray(repos) || repos.length === 0) return null;

  const seed = hash(weekKey);
  const seedEntry = hash(weekKey + ":entry");
  const weekTheme = THEMES[seed % THEMES.length];
  const target = targetDifficulty(weekKey);

  const weights = repos.map((r) => {
    if (recentIds && recentIds.has(r.id)) return 0;
    const primary = r.themes[0];
    const themeScore =
      primary === weekTheme ? 1.0
      : r.themes.includes(weekTheme) ? 0.5
      : 0.2;
    return themeScore * proximity(r.difficulty, target);
  });

  const chosen = weightedPick(repos, weights, seed);
  if (!chosen) return null;

  const entryPoint =
    Array.isArray(chosen.entry_points) && chosen.entry_points.length > 0
      ? chosen.entry_points[seedEntry % chosen.entry_points.length]
      : null;

  return { repo: chosen, entryPoint, theme: weekTheme, target };
}

// Convenience: forward-replay from START_WEEK to derive the recency window,
// then pick. O((weekIndex - START_WEEK) * repos.length) — fine into the
// thousands of weeks at our pool size.
export function pick(weekKey, repos) {
  const start = weekKeyToIndex(START_WEEK);
  const target = weekKeyToIndex(weekKey);
  if (target <= start) {
    return pickAt(weekKey, repos, new Set());
  }
  const window = recencyWeeks(repos);
  const history = [];
  for (let i = start; i < target; i++) {
    const wk = indexToWeekKey(i);
    const recent = new Set(history.slice(-window).filter(Boolean));
    const p = pickAt(wk, repos, recent);
    history.push(p ? p.repo.id : null);
  }
  return pickAt(weekKey, repos, new Set(history.slice(-window).filter(Boolean)));
}

// --- Browser UI ------------------------------------------------------------
// Pure picker ends above. The rest of this file is the DOM-rendering side
// and a bootstrap. Node imports (tests, simulator) never reach the bootstrap
// because of the `window`/`document` guard at the bottom.

export function currentWeekKey(now = new Date()) {
  return dateToWeekKey(
    new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
    ),
  );
}

function refUrl(repo) {
  if (!repo.ref) return repo.url;
  return `${repo.url.replace(/\/+$/, "")}/tree/${encodeURIComponent(repo.ref)}`;
}

function el(tag, attrs, ...children) {
  const e = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k === "class") e.className = v;
      else e.setAttribute(k, v);
    }
  }
  for (const c of children) {
    if (c == null) continue;
    e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return e;
}

const EXT_LINK = { target: "_blank", rel: "noopener noreferrer" };
const SOURCE_URL =
  "https://github.com/SauravSuresh/long-way-engine/tree/main/docs/repopick";

export function render(state, root) {
  const { repo, entryPoint, theme, target, weekKey, prevWeekKey, nextWeekKey } =
    state;

  root.replaceChildren();

  root.appendChild(
    el(
      "section",
      { class: "pick" },
      el("h1", null, el("a", { href: refUrl(repo), ...EXT_LINK }, repo.name)),
      el("p", { class: "why" }, repo.why || ""),
    ),
  );

  if (entryPoint) {
    root.appendChild(
      el(
        "section",
        { class: "entry" },
        el("h2", null, "this week"),
        el("p", { class: "label" }, entryPoint.label),
        el(
          "ul",
          { class: "files" },
          ...entryPoint.files.map((f) => el("li", null, el("code", null, f))),
        ),
        el("p", { class: "question" }, entryPoint.question),
      ),
    );
  }

  if (Array.isArray(repo.reading) && repo.reading.length > 0) {
    root.appendChild(
      el(
        "section",
        { class: "reading" },
        el("h2", null, "reading"),
        el(
          "ul",
          null,
          ...repo.reading.map((r) =>
            el(
              "li",
              null,
              el("a", { href: r.url, ...EXT_LINK }, r.title),
              el("span", { class: "kind" }, r.kind),
            ),
          ),
        ),
      ),
    );
  }

  root.appendChild(
    el(
      "footer",
      null,
      el(
        "p",
        { class: "wk" },
        `${weekKey} · theme: ${theme} · target difficulty: ${target}`,
      ),
      el(
        "p",
        { class: "nav" },
        el("a", { href: `#week=${prevWeekKey}` }, "← prev week"),
        " · ",
        el("a", { href: `#week=${nextWeekKey}` }, "next week →"),
        " · ",
        el("a", { href: SOURCE_URL, ...EXT_LINK }, "source"),
      ),
    ),
  );
}

const HASH_RE = /^#week=(\d{4}-W\d{1,2})$/;

async function bootstrap() {
  const root = document.getElementById("app");
  if (!root) return;
  try {
    const res = await fetch("./data/repos.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`fetch repos.json: HTTP ${res.status}`);
    const repos = await res.json();

    const renderForHash = () => {
      const m = HASH_RE.exec(window.location.hash);
      const weekKey = m ? m[1] : currentWeekKey();
      const result = pick(weekKey, repos);
      if (!result) {
        root.replaceChildren();
        root.appendChild(
          el(
            "p",
            { class: "error" },
            `No pick available for ${weekKey}.`,
          ),
        );
        return;
      }
      const idx = weekKeyToIndex(weekKey);
      render(
        {
          ...result,
          weekKey,
          prevWeekKey: indexToWeekKey(idx - 1),
          nextWeekKey: indexToWeekKey(idx + 1),
        },
        root,
      );
    };

    renderForHash();
    window.addEventListener("hashchange", renderForHash);
  } catch (e) {
    root.replaceChildren();
    root.appendChild(
      el("p", { class: "error" }, `Failed to load: ${e.message}`),
    );
    console.error(e);
  }
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
}
