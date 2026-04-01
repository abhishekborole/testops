import React, { useRef, useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  ArcElement, Tooltip, Legend, Filler
} from 'chart.js';
import { Line, Doughnut } from 'react-chartjs-2';
import useStore from '../store/useStore.js';
import { CATS, LOCS, VM } from '../data/constants.js';
import { calcStats, timeAgo, getVerdictInfo } from '../utils/helpers.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, ArcElement, Tooltip, Legend, Filler);

function KpiCard({ label, value, sub, icon, color }) {
  return (
    <div className="kpi-card" style={{ '--kpi-color': color }}>
      <div className="kpi-icon">{icon}</div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={{ color }}>{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function RingCard({ cat, stats }) {
  const r = 25;
  const circ = 2 * Math.PI * r;
  const rate = stats ? stats.rate : 0;
  const fill = (rate / 100) * circ;
  const color = rate >= 95 ? '#22c55e' : rate >= 75 ? '#f59e0b' : '#ef4444';

  return (
    <div className="cat-ring-card">
      <div className="ring-container">
        <svg className="ring-svg" viewBox="0 0 60 60">
          <circle className="ring-bg" cx="30" cy="30" r={r} />
          <circle
            className="ring-fg"
            cx="30" cy="30" r={r}
            stroke={color}
            strokeDasharray={`${fill} ${circ - fill}`}
            strokeDashoffset="0"
          />
        </svg>
        <div className="ring-text" style={{ color }}>{rate}%</div>
      </div>
      <div className="cat-ring-name">{cat.name}</div>
      {cat.critical && <div className="cat-ring-critical">CRITICAL</div>}
    </div>
  );
}

function HeatmapCell({ rate, label }) {
  const bg = rate === null ? 'var(--border)' :
    rate >= 95 ? '#22c55e' : rate >= 80 ? '#84cc16' : rate >= 60 ? '#f59e0b' : '#ef4444';
  const opacity = rate === null ? 0.2 : 0.2 + (rate / 100) * 0.8;
  return (
    <div
      className="heatmap-cell"
      style={{ background: bg, opacity }}
      title={`${label}: ${rate !== null ? rate + '%' : 'No data'}`}
    />
  );
}

export default function Dashboard() {
  const { runs, setView, setActiveId } = useStore();
  const [aiSummary, setAiSummary] = useState('');

  const completedRuns = runs.filter(r => r.status === 'completed' || r.status === 'failed');
  const latest = completedRuns[0];

  // KPI calculations
  const totalRuns = runs.length;
  const passRate = completedRuns.length > 0
    ? Math.round(completedRuns.reduce((sum, r) => sum + (r.overallRate || 0), 0) / completedRuns.length)
    : 0;
  const activeRuns = runs.filter(r => r.status === 'running').length;
  const criticalFailures = completedRuns.reduce((sum, r) => {
    if (!r.categories) return sum;
    return sum + r.categories.filter(c => {
      const cat = CATS.find(x => x.id === c.id);
      if (!cat?.critical) return false;
      const s = calcStats(c.tests);
      return s.failed > 0;
    }).length;
  }, 0);

  // Trend data (last 7 runs)
  const trendRuns = [...completedRuns].reverse().slice(-7);
  const trendLabels = trendRuns.map(r => r.id.split('-')[2] || r.id.slice(-5));
  const trendData = trendRuns.map(r => r.overallRate || 0);

  const lineData = {
    labels: trendLabels.length > 0 ? trendLabels : ['Run 1', 'Run 2', 'Run 3'],
    datasets: [{
      label: 'Pass Rate %',
      data: trendData.length > 0 ? trendData : [0, 0, 0],
      borderColor: '#DB0011',
      backgroundColor: 'rgba(219,0,17,0.08)',
      fill: true,
      tension: 0.4,
      pointRadius: 4,
      pointBackgroundColor: '#DB0011'
    }]
  };

  const lineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
    scales: {
      y: { min: 0, max: 100, grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#64748b' } },
      x: { grid: { display: false }, ticks: { color: '#64748b' } }
    }
  };

  // Donut chart for latest run
  const latestStats = latest?.categories ? (() => {
    let passed = 0, failed = 0, pending = 0;
    latest.categories.forEach(c => {
      c.tests.forEach(t => {
        if (t.status === 'passed') passed++;
        else if (t.status === 'failed') failed++;
        else pending++;
      });
    });
    return { passed, failed, pending };
  })() : { passed: 0, failed: 0, pending: 0 };

  const donutData = {
    labels: ['Passed', 'Failed', 'Pending'],
    datasets: [{
      data: [latestStats.passed, latestStats.failed, latestStats.pending],
      backgroundColor: ['#22c55e', '#ef4444', '#94a3b8'],
      borderWidth: 0,
      hoverOffset: 4
    }]
  };

  const donutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
    cutout: '65%'
  };

  // Category stats from latest run
  const catStats = {};
  if (latest?.categories) {
    latest.categories.forEach(c => {
      catStats[c.id] = calcStats(c.tests);
    });
  }

  // Cluster health from all runs
  const clusterHealth = {};
  runs.forEach(r => {
    if (!r.cluster) return;
    if (!clusterHealth[r.cluster]) clusterHealth[r.cluster] = { runs: 0, rate: 0, loc: r.location };
    clusterHealth[r.cluster].runs++;
    clusterHealth[r.cluster].rate += r.overallRate || 0;
  });
  Object.keys(clusterHealth).forEach(k => {
    clusterHealth[k].avgRate = Math.round(clusterHealth[k].rate / clusterHealth[k].runs);
  });

  // Heatmap data: cats x recent runs (up to 11 runs for heatmap)
  const hmRuns = completedRuns.slice(0, 11).reverse();

  const recentRuns = completedRuns.slice(0, 8);

  return (
    <div className="dashboard-grid">
      {/* KPI Row */}
      <div className="kpi-row">
        <KpiCard label="Total Runs" value={totalRuns} sub="All time" icon="🚀" color="var(--accent)" />
        <KpiCard
          label="Avg Pass Rate"
          value={`${passRate}%`}
          sub={completedRuns.length > 0 ? `${completedRuns.length} completed runs` : 'No runs yet'}
          icon="✓"
          color={passRate >= 95 ? '#22c55e' : passRate >= 75 ? '#f59e0b' : '#ef4444'}
        />
        <KpiCard label="Active Runs" value={activeRuns} sub="Currently executing" icon="⏳" color="#3b82f6" />
        <KpiCard label="Critical Fails" value={criticalFailures} sub="In completed runs" icon="⚠" color={criticalFailures > 0 ? '#ef4444' : '#22c55e'} />
      </div>

      {/* Chart Row */}
      <div className="chart-row">
        <div className="card">
          <div className="card-header">
            <div className="card-title">📈 Pass Rate Trend</div>
            <span className="badge badge-gray">{trendRuns.length} runs</span>
          </div>
          <div className="card-body">
            <div style={{ height: 180 }}>
              <Line data={lineData} options={lineOptions} />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">🏥 Cluster Health</div>
          </div>
          <div className="card-body">
            <div className="cluster-health-grid">
              {Object.keys(clusterHealth).slice(0, 5).map(cluster => {
                const h = clusterHealth[cluster];
                const color = h.avgRate >= 95 ? '#22c55e' : h.avgRate >= 75 ? '#f59e0b' : '#ef4444';
                return (
                  <div className="cluster-health-item" key={cluster}>
                    <div className="cluster-status-dot" style={{ background: color }} />
                    <div className="cluster-info">
                      <div className="cluster-name">{cluster}</div>
                      <div className="cluster-loc">{h.loc || 'Unknown'}</div>
                    </div>
                    <div className="cluster-rate" style={{ color }}>{h.avgRate}%</div>
                  </div>
                );
              })}
              {Object.keys(clusterHealth).length === 0 && (
                <div className="text-muted text-sm" style={{ textAlign: 'center', padding: '20px 0' }}>
                  No cluster data yet. Run a test to populate.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Heatmap Row */}
      <div className="heatmap-row">
        <div className="card">
          <div className="card-header">
            <div className="card-title">🗺 Test Coverage Heatmap</div>
            <span className="text-faint text-xs">Categories × Recent Runs</span>
          </div>
          <div className="card-body">
            {hmRuns.length > 0 ? (
              <>
                <div className="heatmap-grid">
                  {CATS.map(cat => {
                    return hmRuns.map((run, ri) => {
                      const c = run.categories?.find(x => x.id === cat.id);
                      const rate = c ? calcStats(c.tests).rate : null;
                      return <HeatmapCell key={`${cat.id}-${ri}`} rate={rate} label={`${cat.name} / ${run.id}`} />;
                    });
                  }).flat()}
                </div>
                <div className="heatmap-labels">
                  {CATS.map(cat => (
                    <div className="heatmap-label" key={cat.id}>{cat.name.split(' ')[0]}</div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 12, marginTop: 10, fontSize: 11, color: 'var(--text3)' }}>
                  <span>🟩 ≥95%</span><span>🟨 ≥80%</span><span>🟧 ≥60%</span><span>🟥 &lt;60%</span>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">🗺</div>
                <div className="empty-state-title">No Data</div>
                <div className="empty-state-text">Run tests to see the coverage heatmap</div>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">🍩 Test Results</div>
            {latest && <span className="badge badge-gray">{latest.id}</span>}
          </div>
          <div className="card-body">
            {latest ? (
              <>
                <div style={{ height: 160 }}>
                  <Doughnut data={donutData} options={donutOptions} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 12 }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#22c55e' }}>{latestStats.passed}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)' }}>Passed</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#ef4444' }}>{latestStats.failed}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)' }}>Failed</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text3)' }}>{latestStats.pending}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)' }}>Pending</div>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">🍩</div>
                <div className="empty-state-title">No Results</div>
                <div className="empty-state-text">Execute a test run to see results</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Category Rings */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">🎯 Category Pass Rates</div>
          {latest && (
            <span style={{ fontSize: 12, color: 'var(--text3)' }}>Latest: {latest.id}</span>
          )}
        </div>
        <div className="card-body">
          <div className="cat-rings-row">
            {CATS.map(cat => (
              <RingCard
                key={cat.id}
                cat={cat}
                stats={catStats[cat.id] || { rate: 0 }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Recent Runs + Activity Feed */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16 }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">📋 Recent Runs</div>
            <button className="btn btn-sm btn-ghost" onClick={() => setView('history')}>View All →</button>
          </div>
          <div className="table-scroll">
            {recentRuns.length > 0 ? (
              <table className="runs-table">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Environment</th>
                    <th>Cluster</th>
                    <th>Pass Rate</th>
                    <th>Verdict</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {recentRuns.map(run => {
                    const v = VM[run.verdict] || VM['not-ready'];
                    return (
                      <tr key={run.id} onClick={() => { setActiveId(run.id); setView('monitor'); }}>
                        <td><span className="font-mono" style={{ fontSize: 12 }}>{run.id}</span></td>
                        <td><span className="badge badge-blue">{run.env}</span></td>
                        <td><span style={{ fontSize: 12, color: 'var(--text2)' }}>{run.cluster}</span></td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontWeight: 700, color: run.overallRate >= 95 ? '#22c55e' : run.overallRate >= 75 ? '#f59e0b' : '#ef4444' }}>
                              {run.overallRate}%
                            </span>
                            <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', minWidth: 60 }}>
                              <div style={{ height: '100%', width: `${run.overallRate}%`, background: run.overallRate >= 95 ? '#22c55e' : run.overallRate >= 75 ? '#f59e0b' : '#ef4444', borderRadius: 2 }} />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span style={{ color: v.color, fontWeight: 600, fontSize: 12 }}>{v.icon} {v.label}</span>
                        </td>
                        <td style={{ color: 'var(--text3)', fontSize: 12 }}>{timeAgo(run.startedAt)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">📋</div>
                <div className="empty-state-title">No Runs Yet</div>
                <div className="empty-state-text">Go to Execute to start your first test run</div>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">⚡ Activity Feed</div>
          </div>
          <div className="card-body">
            <div className="activity-feed">
              {runs.slice(0, 10).map((run, i) => {
                const v = VM[run.verdict] || VM['running'];
                return (
                  <div className="activity-item" key={run.id + i}>
                    <div className="activity-dot" style={{ background: v.color }} />
                    <div>
                      <div className="activity-text">
                        {v.icon} Run <strong>{run.id}</strong> {run.status === 'running' ? 'is executing' : `completed as ${v.label}`}
                      </div>
                      <div className="activity-time">{run.cluster} · {run.env} · {timeAgo(run.startedAt)}</div>
                    </div>
                  </div>
                );
              })}
              {runs.length === 0 && (
                <div className="text-muted text-sm" style={{ textAlign: 'center', padding: '20px 0' }}>
                  No activity yet
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
