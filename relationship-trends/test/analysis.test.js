import test from 'node:test';
import assert from 'node:assert/strict';
import {
  normalizeNumber, weekStart, weeklySeries, weekScore, classifyTrend,
  analyzeAll, WEIGHTS,
} from '../js/analysis.js';

const WEEK = 7 * 24 * 60 * 60 * 1000;
const DAY = 24 * 60 * 60 * 1000;

test('normalizeNumber strips formatting and US country code', () => {
  assert.equal(normalizeNumber('+1 (555) 123-4567'), '5551234567');
  assert.equal(normalizeNumber('15551234567'), '5551234567');
  assert.equal(normalizeNumber('555-1234'), '5551234');
  assert.equal(normalizeNumber(''), '');
});

test('weekStart returns the Monday of the containing week (UTC)', () => {
  // 2026-01-01 is a Thursday; its week starts Monday 2025-12-29.
  assert.equal(weekStart(Date.UTC(2026, 0, 1, 15)), Date.UTC(2025, 11, 29));
  // A Monday maps to itself.
  assert.equal(weekStart(Date.UTC(2025, 11, 29, 3)), Date.UTC(2025, 11, 29));
});

test('weekScore applies the documented weights', () => {
  const w = { texts: 3, calls: 2, callMinutes: 10, missed: 1, meets: 1 };
  assert.equal(
    weekScore(w),
    3 * WEIGHTS.text + 2 * WEIGHTS.call + 10 * WEIGHTS.callMinute
      + 1 * WEIGHTS.missed + 1 * WEIGHTS.meet,
  );
});

test('weeklySeries builds contiguous weeks including empty ones', () => {
  const monday = Date.UTC(2026, 0, 5); // Monday
  const events = [
    { kind: 'text', direction: 'out', ts: monday + DAY, durationSec: 0 },
    { kind: 'call', direction: 'in', ts: monday + 3 * WEEK + DAY, durationSec: 600 },
    { kind: 'call', direction: 'missed', ts: monday + 3 * WEEK + 2 * DAY, durationSec: 0 },
  ];
  const now = monday + 3 * WEEK + 4 * DAY;
  const series = weeklySeries(events, now);
  assert.equal(series.length, 4);
  assert.deepEqual(series.map((w) => w.texts), [1, 0, 0, 0]);
  assert.deepEqual(series.map((w) => w.calls), [0, 0, 0, 1]);
  assert.deepEqual(series.map((w) => w.missed), [0, 0, 0, 1]);
  assert.equal(series[3].callMinutes, 10);
  assert.equal(series[0].out, 1);
  assert.equal(series[3].in, 1);
});

test('in-person meets count in weekly buckets and totals', () => {
  const monday = Date.UTC(2026, 0, 5);
  const now = monday + 2 * WEEK;
  const events = [
    { contactName: 'Maya', number: '5551112222', kind: 'text', direction: 'out', ts: monday, durationSec: 0 },
    { contactName: 'Maya', number: '5551112222', kind: 'meet', direction: 'met', ts: monday + DAY, durationSec: 0 },
    { contactName: 'Maya', number: '5551112222', kind: 'meet', direction: 'met', ts: monday + WEEK + DAY, durationSec: 0 },
  ];
  const { contacts } = analyzeAll(events, now);
  const maya = contacts[0];
  assert.equal(maya.series[0].meets, 1);
  assert.equal(maya.series[1].meets, 1);
  assert.equal(maya.series[0].score, 1 * WEIGHTS.text + 1 * WEIGHTS.meet);
  assert.equal(maya.totals.meets, 2);
  assert.equal(maya.daysSinceLastMeet, 6);
  // Meets are directionless: they never skew initiation balance.
  assert.equal(maya.outboundShare, 1);
});

test('daysSinceLastMeet is null when there are no meets', () => {
  const monday = Date.UTC(2026, 0, 5);
  const events = [
    { contactName: 'A', number: '5553334444', kind: 'text', direction: 'out', ts: monday, durationSec: 0 },
    { contactName: 'A', number: '5553334444', kind: 'text', direction: 'in', ts: monday + DAY, durationSec: 0 },
  ];
  const { contacts } = analyzeAll(events, monday + WEEK);
  assert.equal(contacts[0].daysSinceLastMeet, null);
});

function seriesOf(scores) {
  return scores.map((score, i) => ({ score, weekStart: i * WEEK }));
}

// Trailing 0 = the current in-progress week, which classification ignores.
test('classifyTrend: rising when recent 4 weeks up >= 25% vs prior 8', () => {
  const t = classifyTrend(seriesOf([...Array(8).fill(10), ...Array(4).fill(20), 0]));
  assert.equal(t.status, 'rising');
  assert.equal(t.deltaPct, 1);
});

test('classifyTrend: fading when down >= 25%', () => {
  const t = classifyTrend(seriesOf([...Array(8).fill(20), ...Array(4).fill(5), 0]));
  assert.equal(t.status, 'fading');
  assert.equal(t.deltaPct, -0.75);
});

test('classifyTrend: steady inside the threshold', () => {
  const t = classifyTrend(seriesOf([...Array(8).fill(10), ...Array(4).fill(11), 0]));
  assert.equal(t.status, 'steady');
});

test('classifyTrend: dormant after 8 silent weeks', () => {
  const t = classifyTrend(seriesOf([...Array(6).fill(15), ...Array(8).fill(0), 3]));
  assert.equal(t.status, 'dormant');
});

test('classifyTrend: the in-progress week does not drag the trend down', () => {
  // 12 identical complete weeks + a near-empty current week: still steady.
  const t = classifyTrend(seriesOf([...Array(12).fill(10), 1]));
  assert.equal(t.status, 'steady');
  assert.equal(t.deltaPct, 0);
});

test('classifyTrend: short history is steady with no delta', () => {
  const t = classifyTrend(seriesOf([5, 6, 7]));
  assert.equal(t.status, 'steady');
  assert.equal(t.deltaPct, null);
});

test('analyzeAll groups by normalized number and skips one-off contacts', () => {
  const monday = Date.UTC(2026, 0, 5);
  const now = monday + 2 * WEEK;
  const events = [
    // Same person, two formats of the same number
    { contactName: 'Mom', number: '+15551234567', kind: 'text', direction: 'out', ts: monday, durationSec: 0 },
    { contactName: 'Mom', number: '5551234567', kind: 'call', direction: 'in', ts: monday + DAY, durationSec: 300 },
    { contactName: '', number: '5551234567', kind: 'text', direction: 'out', ts: monday + 2 * DAY, durationSec: 0 },
    // One-off number (spam / verification code): excluded
    { contactName: '', number: '888555', kind: 'text', direction: 'in', ts: monday, durationSec: 0 },
  ];
  const { contacts, summary } = analyzeAll(events, now);
  assert.equal(contacts.length, 1);
  const mom = contacts[0];
  assert.equal(mom.name, 'Mom');
  assert.equal(mom.totals.texts, 2);
  assert.equal(mom.totals.calls, 1);
  assert.equal(mom.outboundShare, 2 / 3);
  assert.equal(mom.daysSinceLast, 12);
  assert.equal(summary.contacts, 1);
  assert.equal(summary.events, 3);
});
