import { parseAny } from './parsers.js';
import { analyzeAll, formatNumber } from './analysis.js';
import { sparkline, columnChart } from './charts.js';
import { generateDemoEvents } from './demo.js';

const state = {
  events: [],
  analysis: null,
  rangeWeeks: 26,
  selectedIndex: null,
  listView: 'cards', // 'cards' | 'table'
  detailView: 'charts', // 'charts' | 'table'
  sourceLabel: '',
};

const STATUS = {
  rising: { icon: '↑', label: 'Rising', cls: 'status-rising' },
  steady: { icon: '→', label: 'Steady', cls: 'status-steady' },
  fading: { icon: '↓', label: 'Fading', cls: 'status-fading' },
  dormant: { icon: '⏸', label: 'Dormant', cls: 'status-dormant' },
};

const $ = (sel) => document.querySelector(sel);

function fmtDelta(deltaPct) {
  if (deltaPct === null || deltaPct === undefined) return '';
  const pct = Math.round(deltaPct * 100);
  return `${pct >= 0 ? '+' : ''}${pct}% vs prior 8 wks`;
}

function slicedSeries(contact) {
  return contact.series.slice(-state.rangeWeeks);
}

// ---- rendering --------------------------------------------------------------

function render() {
  const has = state.analysis && state.analysis.contacts.length > 0;
  $('#empty-state').hidden = has;
  $('#dashboard').hidden = !has;
  if (!has) return;
  renderSummary();
  renderList();
  renderDetail();
}

function renderSummary() {
  const { contacts } = state.analysis;
  const interactions = contacts.reduce(
    (s, c) => s + slicedSeries(c).reduce((t, w) => t + w.texts + w.calls + w.missed + w.meets, 0),
    0,
  );
  const rising = contacts.filter((c) => c.status === 'rising').length;
  const fading = contacts.filter((c) => c.status === 'fading' || c.status === 'dormant').length;

  setTile('#tile-contacts', contacts.length, '');
  setTile('#tile-interactions', interactions.toLocaleString(), '');
  setTile('#tile-rising', rising, rising > 0 ? 'good' : '');
  setTile('#tile-fading', fading, fading > 0 ? 'bad' : '');
  $('#source-label').textContent = state.sourceLabel;
}

function setTile(sel, value, tone) {
  const el = $(sel);
  el.textContent = value;
  el.classList.toggle('tile-good', tone === 'good');
  el.classList.toggle('tile-bad', tone === 'bad');
}

function statusBadge(contact) {
  const s = STATUS[contact.status];
  const badge = document.createElement('span');
  badge.className = `badge ${s.cls}`;
  const icon = document.createElement('span');
  icon.className = 'badge-icon';
  icon.textContent = s.icon;
  const label = document.createElement('span');
  label.textContent = s.label;
  badge.append(icon, label);
  return badge;
}

function renderList() {
  $('#list-view-toggle').textContent =
    state.listView === 'cards' ? 'View as table' : 'View as cards';
  if (state.listView === 'table') {
    renderListTable();
    return;
  }
  const grid = $('#contact-grid');
  grid.hidden = false;
  $('#contact-table-wrap').hidden = true;
  grid.replaceChildren();

  state.analysis.contacts.forEach((c, i) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'contact-card';
    card.classList.toggle('selected', state.selectedIndex === i);
    card.addEventListener('click', () => {
      state.selectedIndex = state.selectedIndex === i ? null : i;
      render();
      if (state.selectedIndex !== null) {
        $('#detail').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });

    const top = document.createElement('div');
    top.className = 'card-top';
    const name = document.createElement('span');
    name.className = 'card-name';
    name.textContent = c.name;
    top.append(name, statusBadge(c));

    const spark = document.createElement('div');
    spark.className = 'card-spark';

    const delta = document.createElement('div');
    delta.className = 'card-delta';
    if (c.status === 'dormant') {
      delta.textContent = `No contact in ${c.daysSinceLast} days`;
      delta.classList.add('delta-bad');
    } else if (c.deltaPct !== null) {
      delta.textContent = fmtDelta(c.deltaPct);
      if (c.deltaPct >= 0.25) delta.classList.add('delta-good');
      if (c.deltaPct <= -0.25) delta.classList.add('delta-bad');
    } else {
      delta.textContent = 'Building history…';
    }

    const meta = document.createElement('div');
    meta.className = 'card-meta';
    const parts = [`Last contact ${c.daysSinceLast === 0 ? 'today' : `${c.daysSinceLast}d ago`}`];
    if (c.outboundShare !== null && c.totals.events >= 10) {
      const pct = Math.round(c.outboundShare * 100);
      if (pct >= 75) parts.push(`You reach out ${pct}% of the time`);
      else if (pct <= 25) parts.push(`They reach out ${100 - pct}% of the time`);
    }
    meta.textContent = parts.join(' · ');

    card.append(top, spark, delta, meta);
    grid.appendChild(card);
    sparkline(spark, slicedSeries(c).map((w) => w.score), { width: 220, height: 44 });
  });
}

function renderListTable() {
  $('#contact-grid').hidden = true;
  const wrap = $('#contact-table-wrap');
  wrap.hidden = false;
  const tbody = $('#contact-table tbody');
  tbody.replaceChildren();
  for (const c of state.analysis.contacts) {
    const tr = document.createElement('tr');
    const cells = [
      c.name,
      STATUS[c.status].icon + ' ' + STATUS[c.status].label,
      c.deltaPct === null ? '—' : `${Math.round(c.deltaPct * 100)}%`,
      c.totals.texts.toLocaleString(),
      c.totals.calls.toLocaleString(),
      c.totals.callMinutes.toLocaleString(),
      c.daysSinceLast === 0 ? 'today' : `${c.daysSinceLast}d`,
      c.daysSinceLastMeet === null ? 'never' : c.daysSinceLastMeet === 0 ? 'today' : `${c.daysSinceLastMeet}d`,
      c.outboundShare === null ? '—' : `${Math.round(c.outboundShare * 100)}%`,
    ];
    cells.forEach((text, idx) => {
      const td = document.createElement('td');
      td.textContent = String(text);
      if (idx > 1) td.className = 'num';
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
}

function renderDetail() {
  const detail = $('#detail');
  if (state.selectedIndex === null || !state.analysis.contacts[state.selectedIndex]) {
    detail.hidden = true;
    return;
  }
  detail.hidden = false;
  const c = state.analysis.contacts[state.selectedIndex];
  const series = slicedSeries(c);

  $('#detail-name').textContent = c.name;
  $('#detail-number').textContent = c.number ? formatNumber(c.number) : '';
  const badgeWrap = $('#detail-badge');
  badgeWrap.replaceChildren(statusBadge(c));

  const facts = $('#detail-facts');
  facts.replaceChildren();
  const factList = [
    [c.totals.texts.toLocaleString(), 'texts'],
    [c.totals.calls.toLocaleString(), 'calls'],
    [c.totals.callMinutes.toLocaleString(), 'call minutes'],
    [c.daysSinceLast === 0 ? 'today' : `${c.daysSinceLast}d ago`, 'last contact'],
    [
      c.daysSinceLastMeet === null
        ? 'never'
        : c.daysSinceLastMeet === 0 ? 'today' : `${c.daysSinceLastMeet}d ago`,
      'seen in person',
    ],
  ];
  if (c.outboundShare !== null) {
    factList.push([`${Math.round(c.outboundShare * 100)}%`, 'started by you']);
  }
  for (const [value, label] of factList) {
    const f = document.createElement('div');
    f.className = 'fact';
    const v = document.createElement('div');
    v.className = 'fact-value';
    v.textContent = value;
    const l = document.createElement('div');
    l.className = 'fact-label';
    l.textContent = label;
    f.append(v, l);
    facts.appendChild(f);
  }

  $('#detail-view-toggle').textContent =
    state.detailView === 'charts' ? 'View as table' : 'View as charts';
  const charts = $('#detail-charts');
  const tableWrap = $('#detail-table-wrap');
  charts.hidden = state.detailView !== 'charts';
  tableWrap.hidden = state.detailView === 'charts';

  if (state.detailView === 'charts') {
    columnChart($('#chart-texts'), series.map((w) => ({ weekStart: w.weekStart, value: w.texts })), {
      color: 'var(--series-1)', unit: 'texts',
    });
    columnChart($('#chart-calls'), series.map((w) => ({ weekStart: w.weekStart, value: w.callMinutes })), {
      color: 'var(--series-2)', unit: 'call min',
    });
  } else {
    const tbody = $('#detail-table tbody');
    tbody.replaceChildren();
    for (const w of series) {
      const tr = document.createElement('tr');
      const d = new Date(w.weekStart);
      const cells = [
        d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }),
        w.texts, w.calls, w.missed, w.meets, w.callMinutes, w.score,
      ];
      cells.forEach((text, idx) => {
        const td = document.createElement('td');
        td.textContent = String(text);
        if (idx > 0) td.className = 'num';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  }
}

// ---- data loading -----------------------------------------------------------

function loadEvents(events, sourceLabel) {
  state.events = events;
  state.sourceLabel = sourceLabel;
  state.analysis = analyzeAll(events);
  state.selectedIndex = null;
  render();
}

async function importFiles(fileList) {
  const all = [];
  const errors = [];
  for (const file of fileList) {
    try {
      const text = await file.text();
      const events = parseAny(text);
      if (events.length === 0) errors.push(`${file.name}: no events recognized`);
      all.push(...events);
    } catch (err) {
      errors.push(`${file.name}: ${err.message}`);
    }
  }
  const status = $('#import-status');
  status.textContent = errors.join(' · ');
  if (all.length > 0) {
    loadEvents(all, `${all.length.toLocaleString()} events imported from ${fileList.length} file${fileList.length === 1 ? '' : 's'}`);
  }
}

// ---- wiring -----------------------------------------------------------------

function init() {
  for (const btn of document.querySelectorAll('[data-demo]')) {
    btn.addEventListener('click', () => {
      const events = generateDemoEvents();
      loadEvents(events, `Demo data · ${events.length.toLocaleString()} events`);
    });
  }
  for (const input of document.querySelectorAll('[data-import]')) {
    input.addEventListener('change', (e) => {
      if (e.target.files.length > 0) importFiles([...e.target.files]);
      e.target.value = '';
    });
  }
  for (const btn of document.querySelectorAll('#range-row [data-weeks]')) {
    btn.addEventListener('click', () => {
      state.rangeWeeks = Number(btn.dataset.weeks) || 9999;
      for (const b of document.querySelectorAll('#range-row [data-weeks]')) {
        b.classList.toggle('active', b === btn);
        b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
      }
      render();
    });
  }
  $('#list-view-toggle').addEventListener('click', () => {
    state.listView = state.listView === 'cards' ? 'table' : 'cards';
    renderList();
    $('#list-view-toggle').textContent =
      state.listView === 'cards' ? 'View as table' : 'View as cards';
  });
  $('#detail-view-toggle').addEventListener('click', () => {
    state.detailView = state.detailView === 'charts' ? 'table' : 'charts';
    renderDetail();
  });
  $('#detail-close').addEventListener('click', () => {
    state.selectedIndex = null;
    render();
  });
  window.addEventListener('resize', () => {
    if (state.selectedIndex !== null && state.detailView === 'charts') renderDetail();
  });
  render();
}

init();
