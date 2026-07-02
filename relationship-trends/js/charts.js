// Minimal SVG chart components: sparkline and weekly column chart.
// Colors come from CSS custom properties so light/dark swap automatically.

const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(name, attrs = {}) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

// ---- shared tooltip ---------------------------------------------------------

let tooltipEl = null;

function tooltip() {
  if (!tooltipEl) {
    tooltipEl = document.createElement('div');
    tooltipEl.className = 'chart-tooltip';
    tooltipEl.setAttribute('role', 'status');
    tooltipEl.hidden = true;
    document.body.appendChild(tooltipEl);
  }
  return tooltipEl;
}

// rows: [{value, label}] — value leads, label follows.
export function showTooltip(x, y, title, rows) {
  const tip = tooltip();
  tip.replaceChildren();
  const t = document.createElement('div');
  t.className = 'chart-tooltip-title';
  t.textContent = title;
  tip.appendChild(t);
  for (const row of rows) {
    const r = document.createElement('div');
    r.className = 'chart-tooltip-row';
    const v = document.createElement('span');
    v.className = 'chart-tooltip-value';
    v.textContent = row.value;
    const l = document.createElement('span');
    l.className = 'chart-tooltip-label';
    l.textContent = row.label;
    r.append(v, l);
    tip.appendChild(r);
  }
  tip.hidden = false;
  const rect = tip.getBoundingClientRect();
  const px = Math.min(x + 12, window.innerWidth - rect.width - 8);
  const py = Math.max(8, y - rect.height - 12);
  tip.style.left = `${px + window.scrollX}px`;
  tip.style.top = `${py + window.scrollY}px`;
}

export function hideTooltip() {
  if (tooltipEl) tooltipEl.hidden = true;
}

// ---- sparkline --------------------------------------------------------------

// 2px line + 10% area wash + ring-backed end dot. Single series, no axes.
export function sparkline(container, values, { width = 160, height = 40 } = {}) {
  container.replaceChildren();
  const svg = svgEl('svg', {
    viewBox: `0 0 ${width} ${height}`,
    width,
    height,
    'aria-hidden': 'true',
  });
  const max = Math.max(...values, 1);
  const pad = 5;
  const step = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0;
  const xy = values.map((v, i) => [
    pad + i * step,
    height - pad - (v / max) * (height - pad * 2),
  ]);

  const line = xy.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${line} L${xy[xy.length - 1][0].toFixed(1)},${height - pad} L${pad},${height - pad} Z`;

  svg.appendChild(svgEl('path', { d: area, fill: 'var(--series-1)', opacity: '0.1' }));
  svg.appendChild(svgEl('path', {
    d: line, fill: 'none', stroke: 'var(--series-1)',
    'stroke-width': '2', 'stroke-linejoin': 'round', 'stroke-linecap': 'round',
  }));
  const [ex, ey] = xy[xy.length - 1];
  svg.appendChild(svgEl('circle', { cx: ex, cy: ey, r: '6', fill: 'var(--surface-1)' }));
  svg.appendChild(svgEl('circle', { cx: ex, cy: ey, r: '4', fill: 'var(--series-1)' }));
  container.appendChild(svg);
}

// ---- weekly column chart ----------------------------------------------------

function niceTicks(max) {
  if (max <= 0) return [0, 1];
  const raw = max / 3;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const ticks = [];
  for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(Math.round(v * 100) / 100);
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}

function roundedTopRect(x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h} L${x},${y + rr} Q${x},${y} ${x + rr},${y} L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} L${x + w},${y + h} Z`;
}

function shortDate(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' });
}

// data: [{weekStart, value}], opts: {color, unit, height}
// Columns capped at 24px wide with 2px surface gaps, 4px rounded data-end,
// hairline solid gridlines, per-mark hover tooltip (mark is the hit target).
export function columnChart(container, data, { color = 'var(--series-1)', unit = '', height = 180 } = {}) {
  container.replaceChildren();
  const width = Math.max(280, container.clientWidth || 560);
  const margin = { top: 8, right: 8, bottom: 24, left: 36 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;

  const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, width: '100%', role: 'img' });
  const max = Math.max(...data.map((d) => d.value), 1);
  const ticks = niceTicks(max);
  const yMax = ticks[ticks.length - 1];
  const y = (v) => margin.top + plotH - (v / yMax) * plotH;

  for (const t of ticks) {
    svg.appendChild(svgEl('line', {
      x1: margin.left, x2: width - margin.right, y1: y(t), y2: y(t),
      stroke: t === 0 ? 'var(--axis)' : 'var(--gridline)', 'stroke-width': '1',
    }));
    const label = svgEl('text', {
      x: margin.left - 6, y: y(t) + 3, 'text-anchor': 'end', class: 'axis-label',
    });
    label.textContent = t.toLocaleString();
    svg.appendChild(label);
  }

  const band = plotW / data.length;
  const barW = Math.min(24, Math.max(2, band - 2));
  const labelEvery = Math.max(1, Math.ceil(data.length / 6));

  data.forEach((d, i) => {
    const cx = margin.left + band * i + band / 2;
    const x = cx - barW / 2;
    const h = (d.value / yMax) * plotH;
    const top = margin.top + plotH - h;

    if (d.value > 0) {
      svg.appendChild(svgEl('path', {
        d: roundedTopRect(x, top, barW, h, 4),
        fill: color,
        class: 'col-mark',
        'data-i': i,
      }));
    }
    // Hit target bigger than the mark: the full band, full plot height.
    const hit = svgEl('rect', {
      x: margin.left + band * i, y: margin.top, width: band, height: plotH,
      fill: 'transparent', class: 'col-hit', 'data-i': i, tabindex: '0',
    });
    const weekLabel = `Week of ${shortDate(d.weekStart)}`;
    hit.addEventListener('pointermove', (ev) => {
      highlight(svg, i);
      showTooltip(ev.clientX, ev.clientY, weekLabel, [
        { value: `${Math.round(d.value * 10) / 10}${unit ? ' ' + unit : ''}`, label: unit || 'value' },
      ]);
    });
    hit.addEventListener('focus', () => {
      highlight(svg, i);
      const r = hit.getBoundingClientRect();
      showTooltip(r.left + r.width / 2, r.top, weekLabel, [
        { value: `${Math.round(d.value * 10) / 10}${unit ? ' ' + unit : ''}`, label: unit || 'value' },
      ]);
    });
    hit.addEventListener('pointerleave', () => { highlight(svg, -1); hideTooltip(); });
    hit.addEventListener('blur', () => { highlight(svg, -1); hideTooltip(); });
    svg.appendChild(hit);

    if (i % labelEvery === 0) {
      const xl = svgEl('text', {
        x: cx, y: height - 6, 'text-anchor': 'middle', class: 'axis-label',
      });
      xl.textContent = shortDate(d.weekStart);
      svg.appendChild(xl);
    }
  });

  container.appendChild(svg);
}

function highlight(svg, index) {
  for (const mark of svg.querySelectorAll('.col-mark')) {
    mark.style.opacity = index === -1 || Number(mark.dataset.i) === index ? '1' : '0.55';
  }
}
