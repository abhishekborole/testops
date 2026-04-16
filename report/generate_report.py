#!/usr/bin/env python3
"""
TestOPS Report Generator
========================
Reads a testcases JSON file and produces a self-contained, interactive HTML report.

Usage:
    python generate_report.py                                   # uses defaults
    python generate_report.py input.json                        # custom input
    python generate_report.py input.json output.html            # custom input + output
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone


# ─────────────────────────────────────────────────
# HTML TEMPLATE  (sentinel __JSON_DATA__ is replaced at runtime)
# ─────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Test Execution Report — __RUN_ID__ | __CLUSTER__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg: #070e1c;
  --card: #0c1a30;
  --border: #1a3255;
  --text: #ddeaf8;
  --muted: #6b8fb5;
  --header: #040c18;
  --header2: #08142a;

  --passed: #22c55e;
  --passed-bg: #0b2518;
  --failed: #ef4444;
  --failed-bg: #280c0c;
  --inprogress: #f59e0b;
  --inprogress-bg: #271c06;
  --blocked: #8b9ab5;
  --blocked-bg: #141f30;

  --accent: #cc0000;
  --purple: #a78bfa;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.55;
}

/* ── HEADER ─────────────────────────────────────────────────── */
.page-header { background: var(--header); color: #fff; }

.header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 32px;
  border-bottom: 1px solid rgba(255,255,255,0.07);
}

.brand { display: flex; align-items: center; gap: 14px; }

.brand-logo {
  width: 38px; height: 38px;
  background: var(--accent);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 17px; color: #fff;
  flex-shrink: 0;
}

.brand-name { font-size: 17px; font-weight: 700; letter-spacing: -0.3px; }
.brand-sub  { font-size: 11px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 1.2px; margin-top: 1px; }

.header-actions { display: flex; gap: 8px; }

.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 5px; border: none;
  cursor: pointer; font-size: 12.5px; font-weight: 500;
  transition: opacity .15s;
}
.btn:hover { opacity: .8; }
.btn-ghost { background: rgba(255,255,255,0.08); color: #fff; border: 1px solid rgba(255,255,255,0.15); }

.header-meta {
  display: flex;
  flex-wrap: wrap;
  padding: 0 32px;
  background: rgba(0,0,0,0.25);
}

.meta-item { padding: 10px 32px 10px 0; }
.meta-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: rgba(255,255,255,0.35); margin-bottom: 2px; }
.meta-value { font-size: 13px; color: rgba(255,255,255,0.88); font-weight: 500; }

.env-badge {
  display: inline-block; padding: 1px 8px; border-radius: 12px;
  font-size: 11px; font-weight: 700; letter-spacing: .5px;
  background: #991b1b; color: #fecaca; text-transform: uppercase;
}

/* ── MAIN ────────────────────────────────────────────────────── */
.main { max-width: 1640px; margin: 0 auto; padding: 24px 32px; }

.section { margin-bottom: 22px; }

.section-label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 1px; color: var(--muted); margin-bottom: 10px;
}

/* ── KPI CARDS ───────────────────────────────────────────────── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

.kpi-card {
  background: var(--card); border-radius: 10px;
  border: 1px solid var(--border); border-left: 4px solid;
  padding: 16px 18px;
  transition: box-shadow .15s;
}
.kpi-card:hover { box-shadow: 0 3px 18px rgba(0,0,0,0.5); }

.kpi-card.k-total      { border-left-color: #6875f5; }
.kpi-card.k-passed     { border-left-color: var(--passed); }
.kpi-card.k-failed     { border-left-color: var(--failed); }
.kpi-card.k-inprogress { border-left-color: var(--inprogress); }
.kpi-card.k-blocked    { border-left-color: var(--blocked); }
.kpi-card.k-rate       { border-left-color: var(--purple); }

.kpi-icon { font-size: 18px; margin-bottom: 8px; }
.kpi-label { font-size: 10.5px; text-transform: uppercase; letter-spacing: .8px; color: var(--muted); margin-bottom: 4px; }

.kpi-value { font-size: 34px; font-weight: 800; line-height: 1; }
.k-total .kpi-value      { color: #6875f5; }
.k-passed .kpi-value     { color: var(--passed); }
.k-failed .kpi-value     { color: var(--failed); }
.k-inprogress .kpi-value { color: var(--inprogress); }
.k-blocked .kpi-value    { color: var(--blocked); }
.k-rate .kpi-value       { color: var(--purple); }

.kpi-sub { font-size: 11px; color: var(--muted); margin-top: 4px; }

/* ── CHARTS ──────────────────────────────────────────────────── */
.charts-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
}

.chart-card {
  background: var(--card); border-radius: 10px;
  border: 1px solid var(--border); padding: 20px 22px;
}

.chart-title { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 16px; }

.donut-wrapper {
  position: relative; height: 200px;
  display: flex; align-items: center; justify-content: center;
}

.donut-legend {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px;
  margin-top: 14px;
}

.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); }
.legend-dot  { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.legend-item strong { color: var(--text); }

/* ── CATEGORY SUMMARY ────────────────────────────────────────── */
.card {
  background: var(--card); border-radius: 10px;
  border: 1px solid var(--border); overflow: hidden;
}

table { width: 100%; border-collapse: collapse; }

thead tr { background: #0a1828; border-bottom: 2px solid var(--border); }

th {
  padding: 9px 14px; text-align: left;
  font-size: 10.5px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .7px;
  color: var(--muted); white-space: nowrap;
}

td {
  padding: 9px 14px; border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

tr:last-child td { border-bottom: none; }
tbody tr:hover { background: #0f2244; }

.cat-name { font-weight: 600; font-size: 13px; }
.cat-num  { font-size: 11px; font-weight: 700; color: var(--muted); text-align: center; }

.stacked-bar {
  display: flex; height: 8px; border-radius: 4px; overflow: hidden;
  background: #1a3255; min-width: 140px;
}
.bar-seg            { height: 100%; }
.bar-passed         { background: var(--passed); }
.bar-failed         { background: var(--failed); }
.bar-inprogress     { background: var(--inprogress); }
.bar-blocked        { background: var(--blocked); }

.pass-rate-text { font-size: 12px; font-weight: 700; }

/* ── BADGE ───────────────────────────────────────────────────── */
.badge {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 9px; border-radius: 20px;
  font-size: 11px; font-weight: 700; white-space: nowrap;
}
.badge-passed     { background: var(--passed-bg);     color: #86efac; }
.badge-failed     { background: var(--failed-bg);     color: #fca5a5; }
.badge-inprogress { background: var(--inprogress-bg); color: #fcd34d; }
.badge-blocked    { background: var(--blocked-bg);    color: #9ab5d4; }

/* ── FILTER BAR ──────────────────────────────────────────────── */
.filter-bar {
  display: flex; gap: 8px; align-items: center;
  flex-wrap: wrap; padding: 12px 16px;
  background: var(--card); border-bottom: 1px solid var(--border);
}

.filter-pill {
  padding: 4px 12px; border-radius: 20px;
  border: 1px solid var(--border); background: #0a1828;
  cursor: pointer; font-size: 12px; font-weight: 500;
  color: var(--muted); transition: all .15s; white-space: nowrap;
}
.filter-pill:hover                  { border-color: #3b6dba; color: var(--text); }
.filter-pill.fp-all.active          { background: #1e3d6e; color: #ddeaf8; border-color: #3b6dba; }
.filter-pill.fp-passed.active       { background: var(--passed);     color: #fff; border-color: var(--passed); }
.filter-pill.fp-failed.active       { background: var(--failed);     color: #fff; border-color: var(--failed); }
.filter-pill.fp-inprogress.active   { background: var(--inprogress); color: #fff; border-color: var(--inprogress); }
.filter-pill.fp-blocked.active      { background: var(--blocked);    color: #fff; border-color: var(--blocked); }

.search-box {
  flex: 1; min-width: 180px; max-width: 300px;
  padding: 5px 12px; border: 1px solid var(--border);
  border-radius: 5px; font-size: 13px; outline: none;
  background: #0a1828; color: var(--text);
  transition: border-color .15s;
}
.search-box:focus { border-color: #3b6dba; }
.search-box::placeholder { color: var(--muted); }

.cat-select {
  padding: 5px 10px; border: 1px solid var(--border);
  border-radius: 5px; font-size: 12.5px; background: #0a1828;
  cursor: pointer; outline: none; color: var(--text);
}

.filter-count { margin-left: auto; font-size: 12px; color: var(--muted); white-space: nowrap; }

/* ── TEST TABLE ──────────────────────────────────────────────── */
.tc-table tbody tr.data-row { cursor: pointer; transition: background .1s; }
.tc-table tbody tr.data-row:hover   { background: #0f2244; }
.tc-table tbody tr.data-row.row-open { background: #0a1e3a; }

.tc-id   { font-family: 'SFMono-Regular', Consolas, 'Courier New', monospace; font-size: 11.5px; font-weight: 700; color: var(--muted); }
.tc-name { font-weight: 500; max-width: 380px; }

.cat-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 10.5px; font-weight: 500;
  background: #1a3255; color: #7aafdc; white-space: nowrap;
}

.fail-detail { font-size: 11.5px; color: var(--failed); font-style: italic; }
.ev-count    { display: inline-flex; align-items: center; gap: 4px; font-size: 11.5px; color: var(--muted); }

.toggle-icon {
  display: inline-block; transition: transform .2s;
  font-size: 12px; color: var(--muted); margin-left: 6px;
}
.row-open .toggle-icon { transform: rotate(90deg); }

/* ── EVIDENCE ROW ────────────────────────────────────────────── */
.ev-row { display: none; }
.ev-row.open { display: table-row; }

.ev-row > td {
  background: #060e1c;
  padding: 12px 16px 14px 48px;
  border-bottom: 2px solid var(--border);
}

.ev-header {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .8px; color: var(--muted); margin-bottom: 10px;
}

.ev-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 10px;
}

.ev-block {
  background: #111827; color: #d1d5db;
  border-radius: 7px; padding: 10px 14px;
  font-family: 'SFMono-Regular', Consolas, 'Courier New', monospace;
  font-size: 11px; line-height: 1.65;
  overflow-x: auto; white-space: pre-wrap; word-break: break-all;
}

.ev-block .ev-num  { display: block; font-size: 10px; color: #3b6b9a; margin-bottom: 6px; letter-spacing: .5px; }
.ev-block .line-error { color: #f87171; }

/* ── NO RESULTS ──────────────────────────────────────────────── */
.no-results-row td { text-align: center; padding: 40px; color: var(--muted); }

/* ── FOOTER ──────────────────────────────────────────────────── */
.page-footer {
  text-align: center; padding: 20px 32px;
  color: var(--muted); font-size: 11.5px;
  border-top: 1px solid var(--border); margin-top: 8px;
}

/* ── RESPONSIVE ──────────────────────────────────────────────── */
@media (max-width: 1300px) {
  .kpi-grid     { grid-template-columns: repeat(3, 1fr); }
  .charts-grid  { grid-template-columns: 1fr; }
}
@media (max-width: 800px) {
  .main         { padding: 16px; }
  .header-top   { padding: 12px 16px; flex-wrap: wrap; gap: 10px; }
  .header-meta  { padding: 0 16px; flex-wrap: wrap; }
  .kpi-grid     { grid-template-columns: repeat(2, 1fr); }
}

/* ── PRINT ───────────────────────────────────────────────────── */
@media print {
  body { background: #070e1c; }
  .header-actions, .filter-bar, .toggle-icon { display: none !important; }
  .ev-row       { display: table-row !important; }
  .ev-row > td  { background: #060e1c !important; }
  .page-header  { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .badge, .kpi-value, .kpi-card, .card, body, thead tr { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .main { padding: 0; }
  .section { margin-bottom: 14px; }
}
</style>
</head>
<body>

<!-- HEADER -->
<header class="page-header">
  <div class="header-top">
    <div class="brand">
      <div class="brand-logo">T</div>
      <div>
        <div class="brand-name">TestOPS Production Readiness Portal</div>
        <div class="brand-sub">Test Execution Report</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn btn-ghost" onclick="window.print()">&#128438; Print / Export PDF</button>
    </div>
  </div>
  <div class="header-meta" id="header-meta"></div>
</header>

<!-- MAIN -->
<main class="main">

  <div class="section">
    <div class="section-label">Executive Summary</div>
    <div class="kpi-grid" id="kpi-grid"></div>
  </div>

  <div class="section">
    <div class="section-label">Status Overview</div>
    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-title">Overall Distribution</div>
        <div class="donut-wrapper"><canvas id="donutChart"></canvas></div>
        <div class="donut-legend" id="donut-legend"></div>
      </div>
      <div class="chart-card">
        <div class="chart-title">Status by Category</div>
        <canvas id="barChart" style="max-height:220px"></canvas>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">Category Breakdown</div>
    <div class="card">
      <table id="cat-table">
        <thead>
          <tr>
            <th>Category</th>
            <th style="text-align:center">Total</th>
            <th style="text-align:center">Passed</th>
            <th style="text-align:center">Failed</th>
            <th style="text-align:center">In Progress</th>
            <th style="text-align:center">Blocked</th>
            <th style="min-width:160px">Progress</th>
            <th style="text-align:center">Pass Rate</th>
          </tr>
        </thead>
        <tbody id="cat-tbody"></tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="section-label">Test Cases</div>
    <div class="card">
      <div class="filter-bar">
        <div style="display:flex;gap:4px;flex-wrap:wrap" id="filter-pills"></div>
        <input class="search-box" type="text" id="search-box" placeholder="&#128269; Search test cases&#8230;" oninput="applyFilters()">
        <select class="cat-select" id="cat-select" onchange="applyFilters()">
          <option value="">All Categories</option>
        </select>
        <span class="filter-count" id="filter-count"></span>
      </div>
      <table class="tc-table">
        <thead>
          <tr>
            <th style="width:80px">ID</th>
            <th>Test Case</th>
            <th>Category</th>
            <th style="width:110px">Status</th>
            <th>Failure Details</th>
            <th style="width:80px">Evidence</th>
          </tr>
        </thead>
        <tbody id="tc-tbody"></tbody>
      </table>
    </div>
  </div>

</main>

<footer class="page-footer" id="page-footer"></footer>

<script>
const REPORT = __JSON_DATA__;
const GENERATED_AT = "__GENERATED_AT__";

// ── Helpers ──────────────────────────────────────
const STATUS_KEY = s => s.replace(' ', '').toLowerCase();

function badgeHTML(status) {
  const key = STATUS_KEY(status);
  const labels = {passed:'&#10004; Passed', failed:'&#10006; Failed', inprogress:'&#9678; In Progress', blocked:'&#8856; Blocked'};
  return `<span class="badge badge-${key}">${labels[key] || status}</span>`;
}

// Flatten all test cases with their category attached
const ALL_TC = [];
REPORT.categories.forEach(cat => {
  cat.test_cases.forEach(tc => ALL_TC.push({...tc, category: cat.category}));
});

// Global stats
const STATS = {total:0, passed:0, failed:0, inprogress:0, blocked:0};
ALL_TC.forEach(tc => {
  STATS.total++;
  const k = STATUS_KEY(tc.status);
  if (STATS[k] !== undefined) STATS[k]++;
});

// Per-category stats
const CAT_STATS = REPORT.categories.map(cat => {
  const s = {category: cat.category, total:0, passed:0, failed:0, inprogress:0, blocked:0};
  cat.test_cases.forEach(tc => {
    s.total++;
    const k = STATUS_KEY(tc.status);
    if (s[k] !== undefined) s[k]++;
  });
  return s;
});

const COLORS = {
  passed:     '#16a34a',
  failed:     '#dc2626',
  inprogress: '#d97706',
  blocked:    '#9ca3af',
};

// ── Header metadata ───────────────────────────────
function renderMeta() {
  const m = REPORT.metadata;
  const items = [
    ['Run ID',         m.run_id],
    ['Cluster',        m.cluster_name],
    ['Environment',    `<span class="env-badge">${m.environment}</span>`],
    ['Executed By',    m.executed_by],
    ['Execution Date', m.execution_date],
    ['Remarks',        m.remarks],
  ];
  document.getElementById('header-meta').innerHTML = items.map(([l, v]) =>
    `<div class="meta-item"><div class="meta-label">${l}</div><div class="meta-value">${v}</div></div>`
  ).join('');
}

// ── KPI Cards ─────────────────────────────────────
function renderKPI() {
  const passRate = ((STATS.passed / STATS.total) * 100).toFixed(1);
  const cards = [
    {cls:'k-total',      icon:'&#128203;', label:'Total Tests',   value: STATS.total,       sub: `Across ${REPORT.categories.length} categories`},
    {cls:'k-passed',     icon:'&#10004;',  label:'Passed',        value: STATS.passed,      sub: `${((STATS.passed/STATS.total)*100).toFixed(1)}% of total`},
    {cls:'k-failed',     icon:'&#10006;',  label:'Failed',        value: STATS.failed,      sub: 'Requires attention'},
    {cls:'k-inprogress', icon:'&#9678;',   label:'In Progress',   value: STATS.inprogress,  sub: 'Execution ongoing'},
    {cls:'k-blocked',    icon:'&#8856;',   label:'Blocked',       value: STATS.blocked,     sub: 'Pending resolution'},
    {cls:'k-rate',       icon:'&#128202;', label:'Pass Rate',     value: passRate + '%',    sub: `${STATS.passed} / ${STATS.total} tests`},
  ];
  document.getElementById('kpi-grid').innerHTML = cards.map(c =>
    `<div class="kpi-card ${c.cls}">
      <div class="kpi-icon">${c.icon}</div>
      <div class="kpi-label">${c.label}</div>
      <div class="kpi-value">${c.value}</div>
      <div class="kpi-sub">${c.sub}</div>
    </div>`
  ).join('');
}

// ── Donut Chart ───────────────────────────────────
function renderDonut() {
  const ctx = document.getElementById('donutChart').getContext('2d');
  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Passed', 'Failed', 'In Progress', 'Blocked'],
      datasets: [{
        data: [STATS.passed, STATS.failed, STATS.inprogress, STATS.blocked],
        backgroundColor: [COLORS.passed, COLORS.failed, COLORS.inprogress, COLORS.blocked],
        borderWidth: 2, borderColor: '#fff', hoverOffset: 4,
      }]
    },
    options: {
      cutout: '68%', responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: {display: false},
        tooltip: {callbacks: {label: ctx => ` ${ctx.label}: ${ctx.raw} (${((ctx.raw/STATS.total)*100).toFixed(1)}%)`}}
      }
    }
  });

  document.getElementById('donut-legend').innerHTML = [
    {key:'passed', label:'Passed'},
    {key:'failed', label:'Failed'},
    {key:'inprogress', label:'In Progress'},
    {key:'blocked', label:'Blocked'},
  ].map(item =>
    `<div class="legend-item">
      <div class="legend-dot" style="background:${COLORS[item.key]}"></div>
      <span><strong>${STATS[item.key]}</strong> ${item.label}</span>
    </div>`
  ).join('');
}

// ── Stacked Bar Chart ─────────────────────────────
function renderBarChart() {
  const ctx = document.getElementById('barChart').getContext('2d');
  const labels = CAT_STATS.map(c => c.category.length > 22 ? c.category.slice(0, 20) + '\u2026' : c.category);
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {label: 'Passed',      data: CAT_STATS.map(c => c.passed),     backgroundColor: COLORS.passed,     borderRadius: 2},
        {label: 'Failed',      data: CAT_STATS.map(c => c.failed),     backgroundColor: COLORS.failed,     borderRadius: 2},
        {label: 'In Progress', data: CAT_STATS.map(c => c.inprogress), backgroundColor: COLORS.inprogress, borderRadius: 2},
        {label: 'Blocked',     data: CAT_STATS.map(c => c.blocked),    backgroundColor: COLORS.blocked,    borderRadius: 2},
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: {position: 'bottom', labels: {boxWidth: 12, font: {size: 11}, color: '#6b8fb5'}},
        tooltip: {mode: 'index', intersect: false}
      },
      scales: {
        x: {stacked: true, grid: {display: false}, ticks: {font: {size: 10}, color: '#6b8fb5'}},
        y: {stacked: true, grid: {color: '#1a3255'}, ticks: {stepSize: 2, font: {size: 11}, color: '#6b8fb5'}}
      }
    }
  });
}

// ── Category Summary Table ────────────────────────
function renderCatTable() {
  const tbody = document.getElementById('cat-tbody');
  const totals = {total:0, passed:0, failed:0, inprogress:0, blocked:0};

  tbody.innerHTML = CAT_STATS.map(c => {
    ['total','passed','failed','inprogress','blocked'].forEach(k => totals[k] += c[k]);
    const pct = t => c.total ? ((t / c.total) * 100).toFixed(0) : 0;
    const passRate = c.total ? ((c.passed / c.total) * 100).toFixed(0) : 0;
    const rateColor = passRate >= 80 ? COLORS.passed : passRate >= 50 ? COLORS.inprogress : COLORS.failed;
    return `<tr>
      <td><span class="cat-name">${c.category}</span></td>
      <td class="cat-num">${c.total}</td>
      <td class="cat-num" style="color:${COLORS.passed};font-weight:700">${c.passed}</td>
      <td class="cat-num" style="color:${c.failed ? COLORS.failed : 'var(--muted)'};font-weight:700">${c.failed}</td>
      <td class="cat-num" style="color:${c.inprogress ? COLORS.inprogress : 'var(--muted)'};font-weight:700">${c.inprogress}</td>
      <td class="cat-num" style="color:${c.blocked ? '#6b7280' : 'var(--muted)'};font-weight:700">${c.blocked}</td>
      <td>
        <div class="stacked-bar">
          <div class="bar-seg bar-passed"     style="width:${pct(c.passed)}%"     title="${c.passed} Passed"></div>
          <div class="bar-seg bar-failed"     style="width:${pct(c.failed)}%"     title="${c.failed} Failed"></div>
          <div class="bar-seg bar-inprogress" style="width:${pct(c.inprogress)}%" title="${c.inprogress} In Progress"></div>
          <div class="bar-seg bar-blocked"    style="width:${pct(c.blocked)}%"    title="${c.blocked} Blocked"></div>
        </div>
      </td>
      <td style="text-align:center">
        <span class="pass-rate-text" style="color:${rateColor}">${passRate}%</span>
      </td>
    </tr>`;
  }).join('') + `
    <tr style="background:#0a1828;font-weight:700;border-top:2px solid var(--border)">
      <td><span class="cat-name">Total</span></td>
      <td class="cat-num">${totals.total}</td>
      <td class="cat-num" style="color:${COLORS.passed}">${totals.passed}</td>
      <td class="cat-num" style="color:${COLORS.failed}">${totals.failed}</td>
      <td class="cat-num" style="color:${COLORS.inprogress}">${totals.inprogress}</td>
      <td class="cat-num" style="color:#6b7280">${totals.blocked}</td>
      <td>
        <div class="stacked-bar">
          <div class="bar-seg bar-passed"     style="width:${((totals.passed/totals.total)*100).toFixed(0)}%"></div>
          <div class="bar-seg bar-failed"     style="width:${((totals.failed/totals.total)*100).toFixed(0)}%"></div>
          <div class="bar-seg bar-inprogress" style="width:${((totals.inprogress/totals.total)*100).toFixed(0)}%"></div>
          <div class="bar-seg bar-blocked"    style="width:${((totals.blocked/totals.total)*100).toFixed(0)}%"></div>
        </div>
      </td>
      <td style="text-align:center">
        <span class="pass-rate-text" style="color:${COLORS.passed}">${((totals.passed/totals.total)*100).toFixed(1)}%</span>
      </td>
    </tr>`;
}

// ── Filters + Category Select ─────────────────────
let activeStatus = 'all';

function renderFilters() {
  const pills = [
    {val:'all',         label:`All (${STATS.total})`,                  cls:'fp-all'},
    {val:'Passed',      label:`&#10004; Passed (${STATS.passed})`,     cls:'fp-passed'},
    {val:'Failed',      label:`&#10006; Failed (${STATS.failed})`,     cls:'fp-failed'},
    {val:'In Progress', label:`&#9678; In Progress (${STATS.inprogress})`, cls:'fp-inprogress'},
    {val:'Blocked',     label:`&#8856; Blocked (${STATS.blocked})`,    cls:'fp-blocked'},
  ];
  document.getElementById('filter-pills').innerHTML = pills.map(p =>
    `<button class="filter-pill ${p.cls}${p.val==='all'?' active':''}" data-status="${p.val}" onclick="setStatus(this)">${p.label}</button>`
  ).join('');

  const sel = document.getElementById('cat-select');
  REPORT.categories.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.category;
    opt.textContent = c.category;
    sel.appendChild(opt);
  });
}

function setStatus(el) {
  activeStatus = el.dataset.status;
  document.querySelectorAll('.filter-pill').forEach(p => {
    p.classList.remove('active');
    if (p.dataset.status === activeStatus) p.classList.add('active');
  });
  applyFilters();
}

// ── Test Case Table ───────────────────────────────
function renderTCTable(tcs) {
  const tbody = document.getElementById('tc-tbody');
  document.getElementById('filter-count').textContent =
    tcs.length ? `${tcs.length} result${tcs.length !== 1 ? 's' : ''}` : '0 results';

  if (!tcs.length) {
    tbody.innerHTML = `<tr class="no-results-row"><td colspan="6">No test cases match the current filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = tcs.map(tc => {
    const key = STATUS_KEY(tc.status);
    const evHtml = tc.evidence.map((ev, j) => {
      const lines = ev.split('\n').map(line =>
        (line.toLowerCase().startsWith('error') || line.toLowerCase().includes('timeout'))
          ? `<span class="line-error">${line}</span>`
          : line
      ).join('\n');
      return `<div class="ev-block"><span class="ev-num">Evidence ${j + 1}</span>${lines}</div>`;
    }).join('');

    return `
      <tr class="data-row" id="row-${tc.id}" onclick="toggleEvidence('${tc.id}')">
        <td><span class="tc-id">${tc.id}</span></td>
        <td><span class="tc-name">${tc.test_case}</span><span class="toggle-icon">&#9654;</span></td>
        <td><span class="cat-tag">${tc.category}</span></td>
        <td>${badgeHTML(tc.status)}</td>
        <td>${tc.failure_details ? `<span class="fail-detail">${tc.failure_details}</span>` : '<span style="color:var(--muted);font-size:11px">\u2014</span>'}</td>
        <td><span class="ev-count">&#128196; ${tc.evidence.length}</span></td>
      </tr>
      <tr class="ev-row" id="ev-${tc.id}">
        <td colspan="6">
          <div class="ev-header">Evidence / Command Output</div>
          <div class="ev-grid">${evHtml}</div>
        </td>
      </tr>`;
  }).join('');
}

function toggleEvidence(id) {
  const row = document.getElementById(`row-${id}`);
  const ev  = document.getElementById(`ev-${id}`);
  const isOpen = ev.classList.contains('open');
  ev.classList.toggle('open', !isOpen);
  row.classList.toggle('row-open', !isOpen);
}

function applyFilters() {
  const search = document.getElementById('search-box').value.toLowerCase();
  const cat    = document.getElementById('cat-select').value;
  const filtered = ALL_TC.filter(tc => {
    const statusMatch = activeStatus === 'all' || tc.status === activeStatus;
    const catMatch    = !cat || tc.category === cat;
    const searchMatch = !search ||
      tc.id.toLowerCase().includes(search) ||
      tc.test_case.toLowerCase().includes(search) ||
      tc.category.toLowerCase().includes(search) ||
      (tc.failure_details || '').toLowerCase().includes(search);
    return statusMatch && catMatch && searchMatch;
  });
  renderTCTable(filtered);
}

// ── Footer ────────────────────────────────────────
function renderFooter() {
  document.getElementById('page-footer').innerHTML =
    `Generated by TestOPS Production Readiness Portal &nbsp;|&nbsp;
     Run <strong>${REPORT.metadata.run_id}</strong> &nbsp;|&nbsp;
     Cluster <strong>${REPORT.metadata.cluster_name}</strong> &nbsp;|&nbsp;
     ${GENERATED_AT}`;
}

// ── Init ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderMeta();
  renderKPI();
  renderDonut();
  renderBarChart();
  renderCatTable();
  renderFilters();
  renderTCTable(ALL_TC);
  renderFooter();
});
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────
# Stats helpers (used only for the console summary)
# ─────────────────────────────────────────────────
def compute_stats(data: dict) -> dict:
    stats = {"total": 0, "passed": 0, "failed": 0, "inprogress": 0, "blocked": 0}
    for cat in data["categories"]:
        for tc in cat["test_cases"]:
            stats["total"] += 1
            key = tc["status"].replace(" ", "").lower()
            if key in stats:
                stats[key] += 1
    return stats


# ─────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────
def generate(input_path: str, output_path: str) -> None:
    # Load JSON
    input_file = Path(input_path)
    if not input_file.exists():
        sys.exit(f"ERROR: input file not found: {input_path}")

    print(f"  Reading  : {input_file.resolve()}")
    with input_file.open(encoding="utf-8") as f:
        data = json.load(f)

    # Compute stats for console summary
    stats = compute_stats(data)
    pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] else 0

    # Prepare substitutions
    meta = data.get("metadata", {})
    run_id   = meta.get("run_id", "N/A")
    cluster  = meta.get("cluster_name", "N/A")
    generated_at = datetime.now().strftime("%d %B %Y, %I:%M %p")

    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    # Inject into template
    html = (
        HTML_TEMPLATE
        .replace("__JSON_DATA__",   json_str)
        .replace("__RUN_ID__",      run_id)
        .replace("__CLUSTER__",     cluster)
        .replace("__GENERATED_AT__", generated_at)
    )

    # Write output
    output_file = Path(output_path)
    output_file.write_text(html, encoding="utf-8")

    # Console summary
    print(f"  Writing  : {output_file.resolve()}")
    print(f"  Size     : {output_file.stat().st_size / 1024:.1f} KB")
    print()
    print("  +-----------------------------------------+")
    print(f"  |  Run ID   : {run_id:<27} |")
    print(f"  |  Cluster  : {cluster:<27} |")
    print(f"  |  Total    : {stats['total']:<27} |")
    print(f"  |  Passed   : {stats['passed']:<27} |")
    print(f"  |  Failed   : {stats['failed']:<27} |")
    print(f"  |  In Prog  : {stats['inprogress']:<27} |")
    print(f"  |  Blocked  : {stats['blocked']:<27} |")
    print(f"  |  Pass Rate: {pass_rate:.1f}%{'':<24} |")
    print("  +-----------------------------------------+")
    print()
    print(f"  Report ready: {output_file.name}")


def main() -> None:
    # Fix console encoding on Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    script_dir = Path(__file__).parent

    # Resolve paths from CLI args or defaults
    input_path  = sys.argv[1] if len(sys.argv) > 1 else str(script_dir / "testcases_with_realistic_evidence.json")
    output_path = sys.argv[2] if len(sys.argv) > 2 else str(script_dir / "test-execution-report.html")

    print()
    print("  TestOPS Report Generator")
    print("  " + "-" * 38)
    generate(input_path, output_path)


if __name__ == "__main__":
    main()
