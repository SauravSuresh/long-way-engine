// Seasons forecast — JS port of src/forecast.py (the canonical implementation).
// Same input shapes as the YAML files (seasons.yaml, state/seasons.yaml), same
// output shape as tests/golden/seasons/*.yaml `expected`. tests/test_forecast_js.py
// runs this file against every golden fixture via node.

export const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
export const HORIZON_DAYS = 730;
export const REST_DAYS = 7;

const DAY = 864e5;
const parse = (iso) => (iso instanceof Date ? iso : new Date(iso + "T00:00:00Z"));
const iso = (d) => (d ? d.toISOString().slice(0, 10) : null);
const addDays = (d, n) => new Date(d.getTime() + n * DAY);
const diffDays = (a, b) => Math.round((b - a) / DAY);
const weekday = (d) => WEEKDAYS[(d.getUTCDay() + 6) % 7];

/** Mirror src/seasons.py loader defaults on a parsed seasons.yaml object. */
export function normalizeSeasons(raw) {
  raw = raw || {};
  const r = raw.rhythm || {};
  const blocks = {};
  for (const [day, b] of Object.entries(r.deep_blocks || {})) {
    if (b) blocks[String(day).toLowerCase()] = { start: String(b.start), minutes: +b.minutes, lane: b.lane === "side" ? "side" : "main" };
  }
  const bucket = (raw.bucket || []).map((m) => ({
    id: String(m.id || ""),
    name: String(m.name || ""),
    area: String(m.area || ""),
    hours: +m.hours || 0,
    lane: m.lane === "side" ? "side" : "main",
    syllabus: m.syllabus || null,
    track: m.track && typeof m.track === "object" ? [String(m.track.category), String(m.track.item)] : null,
    modules: m.modules ? [+m.modules[0], +m.modules[1]] : null,
    pin_start: m.pin_start ? iso(parse(String(m.pin_start).slice(0, 10))) : null,
  }));
  const disciplines = (raw.disciplines || []).map((d) => ({
    id: String(d.id || ""),
    name: String(d.name || ""),
    minutes: +d.minutes || 0,
    start: String(d.start || ""),
    days: d.days ? d.days.map((x) => String(x).toLowerCase()) : WEEKDAYS.slice(),
  }));
  return {
    todoist_project_id: String(raw.todoist_project_id || ""),
    rhythm: {
      sleep: { from: String((r.sleep || {}).from || "22:30"), to: String((r.sleep || {}).to || "06:00") },
      fixed_hours: {
        from: String((r.fixed_hours || {}).from || "09:30"),
        to: String((r.fixed_hours || {}).to || "18:30"),
        days: ((r.fixed_hours || {}).days || WEEKDAYS.slice(0, 5)).map((x) => String(x).toLowerCase()),
      },
      shutdown: String(r.shutdown || "21:00"),
      rest_week: r.rest_week !== false,
      deep_blocks: blocks,
    },
    bucket,
    disciplines,
  };
}

export function normalizeState(raw) {
  raw = raw || {};
  const milestones = {};
  for (const [k, v] of Object.entries(raw.milestones || {})) {
    const logged = {};
    for (const [d, m] of Object.entries((v && v.logged) || {})) logged[iso(parse(String(d).slice(0, 10)))] = +m;
    milestones[k] = { logged, done: v && v.done ? iso(parse(String(v.done).slice(0, 10))) : null };
  }
  return {
    milestones,
    rest_until: raw.rest_until ? iso(parse(String(raw.rest_until).slice(0, 10))) : null,
    rests: (raw.rests || []).map((x) => [iso(parse(String(x.from).slice(0, 10))), iso(parse(String(x.to).slice(0, 10)))]),
    last_run: raw.last_run || { main: null, side: null, resting: false },
  };
}

export const twoLanes = (seasons) => Object.values(seasons.rhythm.deep_blocks).some((b) => b.lane === "side");
export const loggedMinutes = (state, id) =>
  Object.values((state.milestones[id] || {}).logged || {}).reduce((a, b) => a + b, 0);

/** forecast(seasons, state, todayISO) -> same shape as the golden `expected` block. */
export function forecast(seasons, state, todayISO) {
  const today = parse(todayISO);
  const two = twoLanes(seasons);
  const live = seasons.bucket.filter((m) => !(state.milestones[m.id] && state.milestones[m.id].done));
  const rem = {}, info = {};
  for (const m of live) {
    rem[m.id] = Math.max(0, Math.round(m.hours * 60) - loggedMinutes(state, m.id));
    info[m.id] = { start: null, end: null, hours_reached: false, segments: [] };
  }
  const mainQ = two ? live.filter((m) => m.lane !== "side") : live.slice();
  const sideQ = two ? live.filter((m) => m.lane === "side") : [];
  const sideMinutes = two ? Object.values(seasons.rhythm.deep_blocks).filter((b) => b.lane === "side").reduce((a, b) => a + b.minutes, 0) : 0;
  const dayOf = (n) => addDays(today, n);
  const pinOk = (m, d) => m.pin_start === null || parse(m.pin_start) <= d;
  const pick = (q, n) => q.find((m) => rem[m.id] > 0 && pinOk(m, dayOf(n))) || null;
  const remainingElsewhere = () => live.some((m) => rem[m.id] > 0);
  const mark = (m, lane, n) => {
    const f = info[m.id], d = dayOf(n);
    if (f.start === null) f.start = d;
    const last = f.segments[f.segments.length - 1];
    if (last && last.lane === lane && diffDays(last.to, d) === 1) last.to = d;
    else f.segments.push({ lane, from: d, to: d });
  };
  const rests = [];
  let restTo = -1;
  if (state.rest_until !== null) {
    const r = diffDays(today, parse(state.rest_until));
    if (r >= 0) { restTo = r; rests.push([today, parse(state.rest_until)]); }
  }
  const restingToday = restTo >= 0;
  let curMain = mainQ.find((m) => pinOk(m, today)) || null;
  let curSide = sideQ.find((m) => pinOk(m, today)) || null;
  const currentMainId = curMain ? curMain.id : null;
  const currentSideId = curSide ? curSide.id : null;
  const finish = (m, n, asMain) => {
    rem[m.id] = 0;
    info[m.id].end = dayOf(n);
    if (seasons.rhythm.rest_week && asMain && remainingElsewhere()) {
      restTo = n + REST_DAYS;
      rests.push([dayOf(n + 1), dayOf(n + REST_DAYS)]);
    }
  };
  for (const [m, asMain] of [[curMain, true], [curSide, curMain === null]]) {
    if (m !== null && rem[m.id] <= 0 && !restingToday) {
      info[m.id].hours_reached = true;
      mark(m, asMain ? "main" : "side", 0);
      finish(m, 0, asMain);
    }
  }
  if (curMain !== null && rem[curMain.id] <= 0) curMain = null;
  if (curSide !== null && rem[curSide.id] <= 0) curSide = null;

  let n = 0;
  while (n < HORIZON_DAYS) {
    if (curMain === null || rem[curMain.id] <= 0) curMain = pick(mainQ, n);
    if (curSide === null || rem[curSide.id] <= 0) curSide = pick(sideQ, n);
    if (curMain === null && curSide === null && !remainingElsewhere()) break;
    if (n <= restTo) { n++; continue; }
    if (curMain !== null) mark(curMain, "main", n);
    if (curSide !== null) {
      if (curMain === null) mark(curSide, "main", n);
      else if (sideMinutes > 0) mark(curSide, "side", n);
    }
    const block = seasons.rhythm.deep_blocks[weekday(dayOf(n))];
    if (!block) { n++; continue; }
    const target = two && block.lane === "side" ? curSide || curMain : curMain || curSide;
    if (target === null) { n++; continue; }
    rem[target.id] -= block.minutes;
    if (rem[target.id] <= 0) finish(target, n, target === curMain || curMain === null);
    n++;
  }
  const milestones = {};
  for (const [id, f] of Object.entries(info)) {
    milestones[id] = {
      start: iso(f.start), end: iso(f.end), hours_reached: f.hours_reached,
      segments: f.segments.map((s) => ({ lane: s.lane, from: iso(s.from), to: iso(s.to) })),
    };
  }
  return {
    current: { main: currentMainId, side: currentSideId, resting: restingToday },
    milestones,
    rests: rests.map(([a, b]) => ({ from: iso(a), to: iso(b) })),
    overflow: n >= HORIZON_DAYS,
  };
}
