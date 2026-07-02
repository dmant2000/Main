// Deterministic demo dataset: eight relationships with distinct trajectories,
// generated over the 26 weeks leading up to `now`. Uses a seeded LCG so the
// demo looks the same on every load (modulo the current date).

function lcg(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

// Each profile maps week index (0 = oldest, 25 = current) to expected weekly
// texts / calls. `ramp` interpolates linearly across the 26 weeks.
function ramp(from, to, week) {
  return from + ((to - from) * week) / 25;
}

// meetWeek picks the weeks with an in-person hangout. Meets are generated
// arithmetically (no random draws) so they never perturb the seeded stream —
// the Swift port must stay bit-identical.
const PROFILES = [
  {
    name: 'Mom', number: '+15551000001', seed: 11,
    texts: () => 6, calls: () => 1, callMin: 22, outShare: 0.45,
    meetWeek: (w) => w % 2 === 0,
  },
  {
    name: 'Dad', number: '+15551000002', seed: 22,
    texts: () => 2, calls: (w) => (w % 2 === 0 ? 1 : 0.2), callMin: 15, outShare: 0.5,
    meetWeek: (w) => w % 4 === 1,
  },
  {
    // Accelerating ramp so the last month clearly outpaces the baseline.
    name: 'Alex Chen', number: '+15551000003', seed: 33,
    texts: (w) => 2 + 18 * (w / 25) ** 2, calls: (w) => 1.6 * (w / 25) ** 2, callMin: 12, outShare: 0.5,
    meetWeek: (w) => w >= 18 && w % 2 === 1,
  },
  {
    name: 'Jordan Reyes', number: '+15551000004', seed: 44,
    texts: (w) => ramp(20, 2, w), calls: (w) => ramp(1.5, 0.1, w), callMin: 18, outShare: 0.55,
    meetWeek: (w) => w < 10 && w % 2 === 0,
  },
  {
    name: 'Riley Park', number: '+15551000005', seed: 55,
    texts: () => 8, calls: () => 0.1, callMin: 6, outShare: 0.5,
    meetWeek: () => false,
  },
  {
    name: 'Sam Okafor', number: '+15551000006', seed: 66,
    texts: (w) => (w < 14 ? 7 : 0), calls: (w) => (w < 14 ? 0.6 : 0), callMin: 25, outShare: 0.5,
    meetWeek: (w) => w < 14 && w % 4 === 2,
  },
  {
    // One-sided: steady texting, but the user starts nearly every exchange.
    name: 'Taylor Brooks', number: '+15551000007', seed: 77,
    texts: () => 5, calls: () => 0, callMin: 9, outShare: 0.88,
    meetWeek: () => false,
  },
  {
    // New friend: quiet start ~3 months ago, ramping hard in recent weeks.
    name: 'Casey Nguyen', number: '+15551000008', seed: 88,
    texts: (w) => (w < 14 ? 0 : 1 + (15 * (w - 14)) / 11),
    calls: (w) => (w < 14 ? 0 : (0.8 * (w - 14)) / 11), callMin: 10, outShare: 0.5,
    meetWeek: (w) => w >= 22 && w % 2 === 0,
  },
];

function poissonish(rand, expected) {
  // Cheap integer draw around `expected` — good enough for demo texture.
  const jitter = 0.75 + rand() * 0.5;
  return Math.max(0, Math.round(expected * jitter));
}

export function generateDemoEvents(now = Date.now()) {
  const events = [];
  const start = now - 26 * WEEK_MS;
  for (const p of PROFILES) {
    const rand = lcg(p.seed);
    for (let w = 0; w < 26; w++) {
      const weekBase = start + w * WEEK_MS;
      const nTexts = poissonish(rand, p.texts(w));
      for (let i = 0; i < nTexts; i++) {
        const ts = weekBase + Math.floor(rand() * (WEEK_MS - DAY_MS));
        if (ts > now) continue;
        events.push({
          contactName: p.name, number: p.number, kind: 'text',
          direction: rand() < p.outShare ? 'out' : 'in', ts, durationSec: 0,
        });
      }
      const nCalls = rand() < (p.calls(w) % 1) ? Math.ceil(p.calls(w)) : Math.floor(p.calls(w));
      for (let i = 0; i < nCalls; i++) {
        const ts = weekBase + Math.floor(rand() * (WEEK_MS - DAY_MS));
        if (ts > now) continue;
        const missed = rand() < 0.12;
        events.push({
          contactName: p.name, number: p.number, kind: 'call',
          direction: missed ? 'missed' : rand() < p.outShare ? 'out' : 'in',
          ts,
          durationSec: missed ? 0 : Math.round(p.callMin * 60 * (0.7 + rand() * 0.6)),
        });
      }
      if (p.meetWeek(w)) {
        // Friday evening, fixed offset: deterministic and outside the LCG stream.
        const ts = weekBase + 4 * DAY_MS + 19 * 60 * 60 * 1000;
        if (ts <= now) {
          events.push({
            contactName: p.name, number: p.number, kind: 'meet',
            direction: 'met', ts, durationSec: 0,
          });
        }
      }
    }
  }
  events.sort((a, b) => a.ts - b.ts);
  return events;
}
