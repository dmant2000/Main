import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCallsXml, parseSmsXml, parseCsv, parseAny, decodeEntities } from '../js/parsers.js';

const CALLS_XML = `<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<calls count="4">
  <call number="+15551234567" duration="120" date="1735689600000" type="1" contact_name="Mom" />
  <call number="+15551234567" duration="300" date="1735776000000" type="2" contact_name="Mom" />
  <call number="5559876543" duration="0" date="1735862400000" type="3" contact_name="Jordan &amp; Co" />
  <call number="5550001111" duration="60" date="0" type="1" contact_name="Bad Date" />
</calls>`;

const SMS_XML = `<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<smses count="4">
  <sms address="+15551234567" date="1735689700000" type="1" body="hi" contact_name="Mom" />
  <sms address="+15551234567" date="1735689800000" type="2" body="hello" contact_name="Mom" />
  <sms address="5559876543" date="1735689900000" type="3" body="draft" contact_name="Jordan" />
  <sms address="5559876543" date="1735690000000" type="1" body="yo" contact_name="(Unknown)" />
</smses>`;

test('parseCallsXml maps types and skips invalid dates', () => {
  const events = parseCallsXml(CALLS_XML);
  assert.equal(events.length, 3);
  assert.deepEqual(events[0], {
    contactName: 'Mom', number: '+15551234567', kind: 'call',
    direction: 'in', ts: 1735689600000, durationSec: 120,
  });
  assert.equal(events[1].direction, 'out');
  assert.equal(events[2].direction, 'missed');
  assert.equal(events[2].contactName, 'Jordan & Co');
});

test('parseSmsXml keeps sent/received only and blanks unknown names', () => {
  const events = parseSmsXml(SMS_XML);
  assert.equal(events.length, 3);
  assert.equal(events[0].direction, 'in');
  assert.equal(events[1].direction, 'out');
  assert.equal(events[2].contactName, '');
  assert.ok(events.every((e) => e.kind === 'text'));
});

test('parseCsv reads ISO dates, epoch dates and quoted fields', () => {
  const csv = [
    'date,kind,direction,contact,number,duration_seconds',
    '2026-01-01T10:00:00Z,text,in,"Reyes, Jordan",5559876543,',
    '1735776000000,call,out,Mom,+15551234567,300',
    'not-a-date,call,in,Bad,555,10',
    '2026-01-02T10:00:00Z,email,in,Skip,555,',
    '',
  ].join('\n');
  const events = parseCsv(csv);
  assert.equal(events.length, 2);
  assert.equal(events[0].contactName, 'Reyes, Jordan');
  assert.equal(events[0].ts, Date.parse('2026-01-01T10:00:00Z'));
  assert.equal(events[1].durationSec, 300);
});

test('parseCsv accepts kind=meet with a blank direction', () => {
  const csv = [
    'date,kind,direction,contact,number,duration_seconds',
    '2026-05-30T19:00:00Z,meet,,Maya,+15557001001,',
    '2026-05-31T19:00:00Z,meet,met,Maya,+15557001001,',
  ].join('\n');
  const events = parseCsv(csv);
  assert.equal(events.length, 2);
  assert.ok(events.every((e) => e.kind === 'meet' && e.direction === 'met'));
});

test('parseCsv throws on missing required columns', () => {
  assert.throws(() => parseCsv('a,b\n1,2'), /must have/);
});

test('parseAny sniffs the format', () => {
  assert.equal(parseAny(CALLS_XML)[0].kind, 'call');
  assert.equal(parseAny(SMS_XML)[0].kind, 'text');
  const csv = 'date,kind,direction\n2026-01-01,text,in';
  assert.equal(parseAny(csv)[0].kind, 'text');
});

test('decodeEntities handles named and numeric entities', () => {
  assert.equal(decodeEntities('A &amp; B &lt;3 &#65; &#x42;'), 'A & B <3 A B');
});
