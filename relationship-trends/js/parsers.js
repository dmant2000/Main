// Parsers for communication exports.
//
// Supported inputs:
//  - calls.xml / sms.xml from the Android "SMS Backup & Restore" app
//  - a generic CSV (see README for the column schema)
//
// Everything parses into a flat list of Event objects:
//   { contactName, number, kind: 'text'|'call', direction: 'in'|'out'|'missed',
//     ts (epoch ms), durationSec }

const XML_ENTITIES = {
  '&amp;': '&',
  '&lt;': '<',
  '&gt;': '>',
  '&quot;': '"',
  '&apos;': "'",
};

export function decodeEntities(str) {
  return str
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&(amp|lt|gt|quot|apos);/g, (m) => XML_ENTITIES[m]);
}

// Scan self-closing/opening tags of a given name and return attribute maps.
// SMS Backup & Restore output is flat, machine-generated XML, so a tag scanner
// is sufficient and works identically in the browser and in Node tests.
export function scanTags(xml, tagName) {
  const results = [];
  const tagRe = new RegExp(`<${tagName}\\b([^>]*?)/?>`, 'g');
  const attrRe = /([\w:]+)\s*=\s*"([^"]*)"/g;
  let m;
  while ((m = tagRe.exec(xml)) !== null) {
    const attrs = {};
    let a;
    attrRe.lastIndex = 0;
    while ((a = attrRe.exec(m[1])) !== null) {
      attrs[a[1]] = decodeEntities(a[2]);
    }
    results.push(attrs);
  }
  return results;
}

function cleanName(name) {
  if (!name || name === '(Unknown)' || name === 'null') return '';
  return name.trim();
}

// calls.xml: <call number=".." duration=".." date=".." type=".." contact_name=".." />
// type: 1 incoming, 2 outgoing, 3 missed, 5 rejected (treated as missed)
export function parseCallsXml(xml) {
  return scanTags(xml, 'call')
    .map((c) => {
      const type = Number(c.type);
      const direction = type === 2 ? 'out' : type === 1 ? 'in' : 'missed';
      return {
        contactName: cleanName(c.contact_name),
        number: c.number || '',
        kind: 'call',
        direction,
        ts: Number(c.date),
        durationSec: Number(c.duration) || 0,
      };
    })
    .filter((e) => Number.isFinite(e.ts) && e.ts > 0);
}

// sms.xml: <sms address=".." date=".." type=".." contact_name=".." />
// type: 1 received, 2 sent (other types — drafts, queued — are skipped)
export function parseSmsXml(xml) {
  return scanTags(xml, 'sms')
    .map((s) => {
      const type = Number(s.type);
      if (type !== 1 && type !== 2) return null;
      return {
        contactName: cleanName(s.contact_name),
        number: s.address || '',
        kind: 'text',
        direction: type === 2 ? 'out' : 'in',
        ts: Number(s.date),
        durationSec: 0,
      };
    })
    .filter((e) => e && Number.isFinite(e.ts) && e.ts > 0);
}

// Generic CSV with a header row. Recognized columns (case-insensitive):
//   date (ISO 8601 or epoch ms), kind (text|call|meet),
//   direction (in|out|missed; blank for meet), contact, number,
//   duration_seconds
export function parseCsv(text) {
  const rows = splitCsv(text);
  if (rows.length < 2) return [];
  const header = rows[0].map((h) => h.trim().toLowerCase());
  const col = (name) => header.indexOf(name);
  const iDate = col('date');
  const iKind = col('kind');
  const iDir = col('direction');
  const iContact = col('contact');
  const iNumber = col('number');
  const iDur = col('duration_seconds');
  if (iDate === -1 || iKind === -1 || iDir === -1) {
    throw new Error('CSV must have at least "date", "kind" and "direction" columns');
  }
  const events = [];
  for (let r = 1; r < rows.length; r++) {
    const row = rows[r];
    if (row.length === 1 && row[0].trim() === '') continue;
    const rawDate = (row[iDate] || '').trim();
    const ts = /^\d+$/.test(rawDate) ? Number(rawDate) : Date.parse(rawDate);
    const kind = (row[iKind] || '').trim().toLowerCase();
    let direction = (row[iDir] || '').trim().toLowerCase();
    if (!Number.isFinite(ts)) continue;
    if (kind === 'meet') direction = 'met'; // an in-person meet has no direction
    else if (kind !== 'text' && kind !== 'call') continue;
    else if (!['in', 'out', 'missed'].includes(direction)) continue;
    events.push({
      contactName: iContact === -1 ? '' : cleanName(row[iContact]),
      number: iNumber === -1 ? '' : (row[iNumber] || '').trim(),
      kind,
      direction,
      ts,
      durationSec: iDur === -1 ? 0 : Number(row[iDur]) || 0,
    });
  }
  return events;
}

function splitCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else inQuotes = false;
      } else field += ch;
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      row.push(field); field = '';
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = '';
      rows.push(row); row = [];
    } else {
      field += ch;
    }
  }
  if (field !== '' || row.length > 0) { row.push(field); rows.push(row); }
  return rows;
}

// Sniff the format of a file's text content and parse accordingly.
export function parseAny(text) {
  const head = text.slice(0, 2000);
  if (/<calls\b/.test(head) || /<call\b/.test(head)) return parseCallsXml(text);
  if (/<smses\b/.test(head) || /<sms\b/.test(head)) return parseSmsXml(text);
  return parseCsv(text);
}
