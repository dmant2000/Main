// Relationship trend analysis.
//
// Takes flat Event lists (see parsers.js), groups them by contact, buckets
// activity into calendar weeks, computes a weekly "connection score", and
// classifies each relationship as rising / steady / fading / dormant.

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

// Score weights: a completed call is worth more than a text, longer calls
// count for more, and an in-person meet is the richest contact of all. A
// missed call still shows intent to connect, so it counts a little.
export const WEIGHTS = { text: 1, call: 6, callMinute: 0.4, missed: 1, meet: 15 };

export const RECENT_WEEKS = 4;    // window treated as "now"
export const BASELINE_WEEKS = 8;  // window treated as "how things were"
export const TREND_THRESHOLD = 0.25; // ±25% change to call it a trend
export const DORMANT_WEEKS = 8;   // no contact this long = dormant

export function normalizeNumber(raw) {
  if (!raw) return '';
  const digits = String(raw).replace(/\D/g, '');
  if (digits.length === 11 && digits.startsWith('1')) return digits.slice(1);
  if (digits.length > 10) return digits.slice(-10);
  return digits;
}

export function formatNumber(raw) {
  const d = normalizeNumber(raw);
  if (d.length === 10) return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
  return raw || 'Unknown';
}

// Monday 00:00 UTC of the week containing ts.
export function weekStart(ts) {
  const d = new Date(ts);
  const day = (d.getUTCDay() + 6) % 7; // Monday = 0
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - day);
}

// Group events by contact identity (normalized number, falling back to name).
export function groupByContact(events) {
  const groups = new Map();
  for (const e of events) {
    const key = normalizeNumber(e.number) || e.contactName.toLowerCase() || 'unknown';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
  }
  return groups;
}

function displayName(events) {
  const counts = new Map();
  for (const e of events) {
    if (e.contactName) counts.set(e.contactName, (counts.get(e.contactName) || 0) + 1);
  }
  let best = '';
  let bestCount = 0;
  for (const [name, count] of counts) {
    if (count > bestCount) { best = name; bestCount = count; }
  }
  return best || formatNumber(events[0].number);
}

export function weekScore(w) {
  return (
    w.texts * WEIGHTS.text +
    w.calls * WEIGHTS.call +
    w.callMinutes * WEIGHTS.callMinute +
    w.missed * WEIGHTS.missed +
    w.meets * WEIGHTS.meet
  );
}

// Build a contiguous weekly series from the first event week through `now`.
export function weeklySeries(events, now) {
  if (events.length === 0) return [];
  const byWeek = new Map();
  let first = Infinity;
  for (const e of events) {
    const ws = weekStart(e.ts);
    first = Math.min(first, ws);
    if (!byWeek.has(ws)) {
      byWeek.set(ws, { weekStart: ws, texts: 0, calls: 0, missed: 0, meets: 0, callMinutes: 0, out: 0, in: 0 });
    }
    const w = byWeek.get(ws);
    if (e.kind === 'meet') {
      w.meets++;
    } else if (e.kind === 'text') {
      w.texts++;
      w[e.direction === 'out' ? 'out' : 'in']++;
    } else if (e.direction === 'missed') {
      w.missed++;
    } else {
      w.calls++;
      w.callMinutes += e.durationSec / 60;
      w[e.direction === 'out' ? 'out' : 'in']++;
    }
  }
  const last = weekStart(now);
  const series = [];
  for (let ws = first; ws <= last; ws += WEEK_MS) {
    const w = byWeek.get(ws) || { weekStart: ws, texts: 0, calls: 0, missed: 0, meets: 0, callMinutes: 0, out: 0, in: 0 };
    w.callMinutes = Math.round(w.callMinutes * 10) / 10;
    w.score = Math.round(weekScore(w) * 10) / 10;
    series.push(w);
  }
  return series;
}

function avg(arr) {
  return arr.length === 0 ? 0 : arr.reduce((s, v) => s + v, 0) / arr.length;
}

// Classify one contact's weekly series into a trend.
// The final series entry is the current, in-progress week — a partial week
// always undercounts, so it is excluded from every window.
// Returns { status: 'rising'|'steady'|'fading'|'dormant', deltaPct|null }
export function classifyTrend(series) {
  const complete = series.length > 1 ? series.slice(0, -1) : series;
  const scores = complete.map((w) => w.score);
  const recent = scores.slice(-RECENT_WEEKS);
  const baseline = scores.slice(-(RECENT_WEEKS + BASELINE_WEEKS), -RECENT_WEEKS);
  const recentAvg = avg(recent);
  const baselineAvg = avg(baseline);

  const dormantSlice = scores.slice(-DORMANT_WEEKS);
  if (dormantSlice.length === DORMANT_WEEKS && dormantSlice.every((s) => s === 0)) {
    return { status: 'dormant', deltaPct: -1, recentAvg, baselineAvg };
  }
  if (baseline.length === 0 || baselineAvg === 0) {
    // Not enough history to compare against: a live relationship reads steady,
    // one that just appeared from nothing reads rising.
    const status = recentAvg > 0 && baseline.length > 0 ? 'rising' : 'steady';
    return { status, deltaPct: null, recentAvg, baselineAvg };
  }
  const deltaPct = (recentAvg - baselineAvg) / baselineAvg;
  let status = 'steady';
  if (deltaPct >= TREND_THRESHOLD) status = 'rising';
  else if (deltaPct <= -TREND_THRESHOLD) status = 'fading';
  return { status, deltaPct, recentAvg, baselineAvg };
}

// Full per-contact analysis.
export function analyzeContact(events, now) {
  const sorted = [...events].sort((a, b) => a.ts - b.ts);
  const series = weeklySeries(sorted, now);
  const trend = classifyTrend(series);

  let out = 0;
  let directed = 0;
  let texts = 0;
  let calls = 0;
  let callMinutes = 0;
  let meets = 0;
  let lastMeetTs = null;
  for (const e of sorted) {
    if (e.kind === 'meet') { meets++; lastMeetTs = e.ts; continue; }
    if (e.kind === 'text') texts++;
    else if (e.direction !== 'missed') { calls++; callMinutes += e.durationSec / 60; }
    if (e.direction === 'in' || e.direction === 'out') {
      directed++;
      if (e.direction === 'out') out++;
    }
  }
  const lastTs = sorted[sorted.length - 1].ts;

  return {
    name: displayName(sorted),
    number: sorted.find((e) => e.number)?.number || '',
    events: sorted,
    series,
    ...trend,
    outboundShare: directed === 0 ? null : out / directed,
    daysSinceLast: Math.max(0, Math.floor((now - lastTs) / (24 * 60 * 60 * 1000))),
    daysSinceLastMeet: lastMeetTs === null
      ? null
      : Math.max(0, Math.floor((now - lastMeetTs) / (24 * 60 * 60 * 1000))),
    totals: { texts, calls, callMinutes: Math.round(callMinutes), meets, events: sorted.length },
  };
}

// Analyze everything: returns contacts sorted by total activity, plus summary.
export function analyzeAll(events, now = Date.now()) {
  const groups = groupByContact(events);
  const contacts = [];
  for (const group of groups.values()) {
    if (group.length < 2) continue; // one-off numbers (verification codes, spam) aren't relationships
    contacts.push(analyzeContact(group, now));
  }
  contacts.sort((a, b) => b.totals.events - a.totals.events);
  return {
    contacts,
    summary: {
      contacts: contacts.length,
      events: contacts.reduce((s, c) => s + c.totals.events, 0),
      rising: contacts.filter((c) => c.status === 'rising').length,
      fading: contacts.filter((c) => c.status === 'fading' || c.status === 'dormant').length,
    },
  };
}
