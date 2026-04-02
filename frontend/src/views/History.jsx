import React, { useState } from 'react';
import useStore from '../store/useStore.js';
import { VM } from '../data/constants.js';
import { calcStats, timeAgo } from '../utils/helpers.js';

export default function History() {
  const { runs, activeId, setActiveId, setView, comparing, toggleCompare } = useStore();

  const [envFilter, setEnvFilter] = useState('all');
  const [verdictFilter, setVerdictFilter] = useState('all');
  const [clusterFilter, setClusterFilter] = useState('all');
  const [search, setSearch] = useState('');

  // Get unique values for filters
  const envs = [...new Set(runs.map(r => r.env).filter(Boolean))];
  const clusters = [...new Set(runs.map(r => r.cluster).filter(Boolean))];

  const filtered = runs.filter(r => {
    if (envFilter !== 'all' && r.env !== envFilter) return false;
    if (verdictFilter !== 'all' && r.verdict !== verdictFilter) return false;
    if (clusterFilter !== 'all' && r.cluster !== clusterFilter) return false;
    if (search && !r.id.toLowerCase().includes(search.toLowerCase()) &&
        !r.cluster?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const handleRunClick = (run) => {
    setActiveId(run.id);
    setView('monitor');
  };

  return (
    <div className="history-layout">
      {/* Filters */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">🔍 Filter Runs</div>
          <span className="badge badge-gray">{filtered.length} / {runs.length} runs</span>
        </div>
        <div className="card-body">
          <div className="history-filters">
            <input
              type="text"
              placeholder="Search by ID or cluster..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                padding: '7px 12px',
                border: '1px solid var(--border)',
                borderRadius: 8,
                background: 'var(--surface2)',
                color: 'var(--text)',
                fontSize: 13,
                fontFamily: 'var(--font)',
                width: 220,
              }}
            />

            <select className="filter-select" value={envFilter} onChange={e => setEnvFilter(e.target.value)}>
              <option value="all">All Environments</option>
              {envs.map(e => <option key={e} value={e}>{e}</option>)}
            </select>

            <select className="filter-select" value={verdictFilter} onChange={e => setVerdictFilter(e.target.value)}>
              <option value="all">All Verdicts</option>
              <option value="ready">Production Ready</option>
              <option value="at-risk">At Risk</option>
              <option value="not-ready">Not Ready</option>
              <option value="running">Running</option>
            </select>

            <select className="filter-select" value={clusterFilter} onChange={e => setClusterFilter(e.target.value)}>
              <option value="all">All Clusters</option>
              {clusters.map(c => <option key={c} value={c}>{c}</option>)}
            </select>

            {(envFilter !== 'all' || verdictFilter !== 'all' || clusterFilter !== 'all' || search) && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { setEnvFilter('all'); setVerdictFilter('all'); setClusterFilter('all'); setSearch(''); }}
              >
                ✕ Clear
              </button>
            )}

            {comparing.length > 0 && (
              <button
                className="btn btn-primary btn-sm"
                style={{ marginLeft: 'auto' }}
                onClick={() => setView('compare')}
              >
                ⚖ Compare ({comparing.length})
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Run List */}
      {filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-title">No Runs Found</div>
          <div className="empty-state-text">
            {runs.length === 0
              ? 'No test runs yet. Go to Execute to start your first run.'
              : 'No runs match the current filters. Try adjusting the filters above.'}
          </div>
        </div>
      ) : (
        <div className="history-list">
          {filtered.map(run => {
            const v = VM[run.verdict] || VM['running'];
            const catStats = run.categories?.map(cat => {
              const s = calcStats(cat.tests);
              return { id: cat.id, name: cat.name, rate: s.rate, failed: s.failed };
            }) || [];
            const failedCats = catStats.filter(c => c.failed > 0);
            const isComparing = comparing.includes(run.id);

            return (
              <div
                key={run.id}
                className="history-item"
                style={{ borderColor: activeId === run.id ? 'var(--accent)' : undefined }}
              >
                {/* Verdict Badge */}
                <div
                  className="history-verdict-badge"
                  style={{ background: v.bg, border: `2px solid ${v.border}` }}
                >
                  <span style={{ fontSize: 18 }}>{v.icon}</span>
                </div>

                {/* Info */}
                <div className="history-info" onClick={() => handleRunClick(run)} style={{ cursor: 'pointer' }}>
                  <div className="history-id">{run.id}</div>
                  <div className="history-meta">
                    {run.cluster} · {run.env} · {timeAgo(run.startedAt)}
                    {run.completedAt && ` · completed ${timeAgo(run.completedAt)}`}
                  </div>
                  <div className="history-tags">
                    <span className="badge badge-blue">{run.env}</span>
                    <span style={{ color: v.color, fontWeight: 600, fontSize: 11 }}>{v.label}</span>
                    {failedCats.slice(0, 3).map(c => (
                      <span key={c.id} className="badge badge-red">{c.name}</span>
                    ))}
                    {failedCats.length > 3 && (
                      <span className="badge badge-gray">+{failedCats.length - 3} more</span>
                    )}
                  </div>
                </div>

                {/* Stats */}
                <div className="history-stats">
                  <div className="history-stat">
                    <div className="history-stat-value" style={{
                      color: run.overallRate >= 95 ? '#22c55e' : run.overallRate >= 75 ? '#f59e0b' : '#ef4444'
                    }}>
                      {run.overallRate || 0}%
                    </div>
                    <div className="history-stat-label">Pass Rate</div>
                    <div className="history-rate-bar" style={{ marginTop: 4 }}>
                      <div style={{
                        height: '100%',
                        width: `${run.overallRate || 0}%`,
                        background: run.overallRate >= 95 ? '#22c55e' : run.overallRate >= 75 ? '#f59e0b' : '#ef4444',
                        borderRadius: 3
                      }} />
                    </div>
                  </div>
                  <div className="history-stat">
                    <div className="history-stat-value" style={{ color: '#22c55e' }}>
                      {run.categories?.flatMap(c => c.tests).filter(t => t.status === 'passed').length || 0}
                    </div>
                    <div className="history-stat-label">Passed</div>
                  </div>
                  <div className="history-stat">
                    <div className="history-stat-value" style={{ color: '#ef4444' }}>
                      {run.categories?.flatMap(c => c.tests).filter(t => t.status === 'failed').length || 0}
                    </div>
                    <div className="history-stat-label">Failed</div>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <button
                    className="btn btn-sm btn-secondary"
                    onClick={() => handleRunClick(run)}
                  >
                    👁 View
                  </button>
                  <button
                    className={`compare-toggle-btn ${isComparing ? 'selected' : ''}`}
                    onClick={() => toggleCompare(run.id)}
                  >
                    {isComparing ? '✓ Selected' : '⚖ Compare'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
