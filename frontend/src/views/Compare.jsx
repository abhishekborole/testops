import React, { useState } from 'react';
import useStore from '../store/useStore.js';
import { M, ML, VM } from '../data/constants.js';
import { calcStats, timeAgo, md } from '../utils/helpers.js';
import { llm } from '../utils/llm.js';

function RunCard({ run, label }) {
  if (!run) {
    return (
      <div className="compare-run-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 160, background: 'var(--surface2)', border: '2px dashed var(--border)' }}>
        <div className="text-faint" style={{ fontSize: 13 }}>No run selected</div>
        <div className="text-faint text-xs" style={{ marginTop: 4 }}>Go to History and toggle compare on a run</div>
      </div>
    );
  }
  const v = VM[run.verdict] || VM['not-ready'];
  return (
    <div className="compare-run-card" style={{ borderColor: v.border }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
            {label}
          </div>
          <div className="compare-run-id">{run.id}</div>
          <div className="compare-run-meta">{run.cluster} · {run.env}</div>
          <div className="compare-run-meta">{timeAgo(run.startedAt)}</div>
        </div>
        <div
          style={{ padding: '6px 12px', borderRadius: 8, background: v.bg, border: `1.5px solid ${v.border}`, color: v.color, fontWeight: 600, fontSize: 13 }}
        >
          {v.icon} {v.label}
        </div>
      </div>
      <div className="compare-run-rate" style={{ color: run.overallRate >= 95 ? '#22c55e' : run.overallRate >= 75 ? '#f59e0b' : '#ef4444' }}>
        {run.overallRate}%
      </div>
      <div className="compare-run-verdict" style={{ color: v.color }}>Pass Rate</div>

      <div style={{ display: 'flex', gap: 16, marginTop: 14 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#22c55e' }}>
            {run.categories?.flatMap(c => c.tests).filter(t => t.status === 'passed').length || 0}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text3)' }}>Passed</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#ef4444' }}>
            {run.categories?.flatMap(c => c.tests).filter(t => t.status === 'failed').length || 0}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text3)' }}>Failed</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>
            {run.categories?.flatMap(c => c.tests).length || 0}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text3)' }}>Total</div>
        </div>
      </div>
    </div>
  );
}

export default function Compare() {
  const { runs, comparing, toggleCompare, setView, aiCache, setCacheItem, catsArr } = useStore();
  const [compareHtml, setCompareHtml] = useState('');
  const [compareLoading, setCompareLoading] = useState(false);

  const runA = runs.find(r => r.id === comparing[0]);
  const runB = runs.find(r => r.id === comparing[1]);

  const runCompare = async () => {
    if (!runA || !runB) return;
    const key = `compare-${runA.id}-${runB.id}`;
    if (aiCache[key]) { setCompareHtml(aiCache[key]); return; }

    setCompareLoading(true);
    setCompareHtml('');

    const buildSummary = (run) => {
      const catSummary = run.categories?.map(c => {
        const s = calcStats(c.tests);
        return `${c.name}: ${s.rate}% (${s.passed}/${s.total})`;
      }).join('\n') || '';
      return `Run ${run.id} on ${run.cluster} (${run.env}): ${run.overallRate}% overall\n${catSummary}`;
    };

    const prompt = `Compare these two OpenShift production readiness test runs:

BASELINE (Run A):
${buildSummary(runA)}

CURRENT (Run B):
${buildSummary(runB)}

Provide:
1. Overall delta analysis (improved/degraded areas)
2. Category-by-category regression highlights
3. Root cause hypotheses for regressions
4. Recommendation (prefer A or B for production, or neither)
Be specific and actionable.`;

    let text = '';
    await llm(
      [{ role: 'user', content: prompt }],
      M.compare,
      chunk => { text += chunk; setCompareHtml(text); }
    );
    setCacheItem(key, text);
    setCompareLoading(false);
  };

  // Build delta table
  const buildDelta = () => {
    if (!runA || !runB) return [];
    return catsArr.map(cat => {
      const catA = runA.categories?.find(c => c.id === cat.id);
      const catB = runB.categories?.find(c => c.id === cat.id);
      const sA = catA ? calcStats(catA.tests) : null;
      const sB = catB ? calcStats(catB.tests) : null;
      const delta = sA && sB ? sB.rate - sA.rate : null;
      return { cat, sA, sB, delta };
    }).filter(row => row.sA || row.sB);
  };

  const deltaRows = buildDelta();

  if (comparing.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">⚖</div>
        <div className="empty-state-title">No Runs Selected for Comparison</div>
        <div className="empty-state-text">
          Go to History and select up to 2 runs using the "Compare" toggle button, then return here.
        </div>
        <button className="btn btn-primary" style={{ marginTop: 20 }} onClick={() => setView('history')}>
          → Go to History
        </button>
      </div>
    );
  }

  return (
    <div className="compare-layout">
      {/* Run Cards */}
      <div className="compare-runs-row">
        <RunCard run={runA} label="Baseline (A)" />
        <RunCard run={runB} label="Current (B)" />
      </div>

      {/* AI Comparison */}
      {runA && runB && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              🤖 AI Comparison Analysis
              <span className="model-chip" style={{ marginLeft: 8 }}>⚡ {ML[M.compare]}</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-sm btn-secondary" onClick={runCompare} disabled={compareLoading}>
                {compareLoading ? <><span className="spinner" /> Analyzing...</> : '▶ Compare with AI'}
              </button>
            </div>
          </div>
          <div className="card-body">
            {compareLoading && !compareHtml && (
              <div className="ai-placeholder">
                <div className="ai-placeholder-line" style={{ width: '90%' }} />
                <div className="ai-placeholder-line" style={{ width: '75%' }} />
                <div className="ai-placeholder-line" style={{ width: '85%' }} />
                <div className="ai-placeholder-line" style={{ width: '65%' }} />
                <div className="ai-placeholder-line" style={{ width: '80%' }} />
              </div>
            )}
            {compareHtml ? (
              <div className="ai-output" dangerouslySetInnerHTML={{ __html: md(compareHtml) }} />
            ) : !compareLoading && (
              <div className="text-faint text-sm" style={{ fontStyle: 'italic' }}>
                Click "Compare with AI" to get an intelligent analysis of the differences between these runs.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Category Delta Table */}
      {deltaRows.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">📊 Category Delta Table</div>
            <div style={{ display: 'flex', gap: 12, fontSize: 12, alignItems: 'center' }}>
              <span style={{ color: '#22c55e' }}>▲ Improved</span>
              <span style={{ color: '#ef4444' }}>▼ Regressed</span>
              <span style={{ color: 'var(--text3)' }}>= Unchanged</span>
            </div>
          </div>
          <div className="table-scroll">
            <table className="delta-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Critical</th>
                  <th>Run A Pass Rate</th>
                  <th>Run B Pass Rate</th>
                  <th>Delta</th>
                  <th>A Passed</th>
                  <th>A Failed</th>
                  <th>B Passed</th>
                  <th>B Failed</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {deltaRows.map(({ cat, sA, sB, delta }) => {
                  const deltaClass = delta === null ? 'delta-neutral' : delta > 0 ? 'delta-positive' : delta < 0 ? 'delta-negative' : 'delta-neutral';
                  const deltaPrefix = delta === null ? '—' : delta > 0 ? `+${delta}%` : `${delta}%`;
                  const rateColor = (rate) => rate >= 95 ? '#22c55e' : rate >= 75 ? '#f59e0b' : rate !== null ? '#ef4444' : 'var(--text3)';

                  let statusText = '';
                  if (delta === null) statusText = sA ? 'Not in B' : 'Not in A';
                  else if (delta > 5) statusText = '▲ Improved';
                  else if (delta < -5) statusText = '▼ Regressed';
                  else statusText = '≈ Stable';

                  return (
                    <tr key={cat.id}>
                      <td style={{ fontWeight: 600 }}>{cat.name}</td>
                      <td>{cat.critical ? <span className="badge badge-red">CRITICAL</span> : <span className="badge badge-gray">Optional</span>}</td>
                      <td style={{ color: rateColor(sA?.rate), fontWeight: 600 }}>{sA ? `${sA.rate}%` : '—'}</td>
                      <td style={{ color: rateColor(sB?.rate), fontWeight: 600 }}>{sB ? `${sB.rate}%` : '—'}</td>
                      <td className={deltaClass} style={{ fontSize: 14 }}>{deltaPrefix}</td>
                      <td style={{ color: '#22c55e' }}>{sA?.passed ?? '—'}</td>
                      <td style={{ color: '#ef4444' }}>{sA?.failed ?? '—'}</td>
                      <td style={{ color: '#22c55e' }}>{sB?.passed ?? '—'}</td>
                      <td style={{ color: '#ef4444' }}>{sB?.failed ?? '—'}</td>
                      <td>
                        <span style={{
                          fontSize: 12,
                          fontWeight: 600,
                          color: statusText.includes('Improved') ? '#22c55e' : statusText.includes('Regressed') ? '#ef4444' : 'var(--text3)'
                        }}>
                          {statusText}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Summary bar */}
          {runA && runB && (
            <div style={{ padding: '14px 18px', borderTop: '1px solid var(--border)', display: 'flex', gap: 24, alignItems: 'center' }}>
              <div>
                <span className="text-muted" style={{ fontSize: 12 }}>Overall Delta: </span>
                <span style={{
                  fontWeight: 700,
                  fontSize: 16,
                  color: (runB.overallRate - runA.overallRate) >= 0 ? '#22c55e' : '#ef4444'
                }}>
                  {runB.overallRate - runA.overallRate >= 0 ? '+' : ''}{runB.overallRate - runA.overallRate}%
                </span>
              </div>
              <div>
                <span className="text-muted" style={{ fontSize: 12 }}>A: </span>
                <span style={{ fontWeight: 700, color: runA.overallRate >= 95 ? '#22c55e' : '#f59e0b' }}>{runA.overallRate}%</span>
              </div>
              <div>
                <span className="text-muted" style={{ fontSize: 12 }}>B: </span>
                <span style={{ fontWeight: 700, color: runB.overallRate >= 95 ? '#22c55e' : '#f59e0b' }}>{runB.overallRate}%</span>
              </div>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => { toggleCompare(runA.id); toggleCompare(runB.id); }}>
                  Clear Comparison
                </button>
                <button className="btn btn-secondary btn-sm" onClick={() => setView('history')}>
                  ← Back to History
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
