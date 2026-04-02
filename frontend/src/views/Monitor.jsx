import React, { useState, useEffect, useRef } from 'react';
import useStore from '../store/useStore.js';
import { M, ML, VM } from '../data/constants.js';
import { calcStats, formatDuration, timeAgo } from '../utils/helpers.js';
import { llm } from '../utils/llm.js';

function StatusBadge({ status }) {
  const cfg = {
    passed: { label: 'PASSED', cls: 'status-passed', icon: '✓' },
    failed: { label: 'FAILED', cls: 'status-failed', icon: '✗' },
    running: { label: 'RUNNING', cls: 'status-running', icon: '⏳' },
    pending: { label: 'PENDING', cls: 'status-pending', icon: '·' }
  };
  const c = cfg[status] || cfg.pending;
  return (
    <span className={`test-status-badge ${c.cls}`}>
      {c.icon} {c.label}
    </span>
  );
}

function AgentEvent({ event }) {
  const typeMap = {
    info: 'agent-event-info',
    warn: 'agent-event-warn',
    error: 'agent-event-error',
    success: 'agent-event-success',
    ai: 'agent-event-ai'
  };
  return (
    <div className={`agent-event ${typeMap[event.type] || 'agent-event-info'}`}>
      <div className="agent-event-header">
        <span className="agent-event-type">{event.title}</span>
        <span className="agent-event-time">{event.time}</span>
      </div>
      <div className="agent-event-body">{event.body}</div>
    </div>
  );
}

export default function Monitor() {
  const { runs, activeId, setActiveId, openLogs, toggleLog, agentEvents, mFilter, setMFilter, aiCache, setCacheItem, catsArr, rerun } = useStore();
  const [selectedCat, setSelectedCat] = useState(null);
  const [logSummaryHtml, setLogSummaryHtml] = useState({});
  const [summaryLoading, setSummaryLoading] = useState({});
  const agentFeedRef = useRef(null);

  const run = runs.find(r => r.id === activeId) || runs[0];

  useEffect(() => {
    if (agentFeedRef.current) {
      agentFeedRef.current.scrollTop = agentFeedRef.current.scrollHeight;
    }
  }, [agentEvents]);

  useEffect(() => {
    if (run && !selectedCat && run.categories?.length > 0) {
      setSelectedCat(run.categories[0].id);
    }
  }, [run?.id]);

  if (!run) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">👁</div>
        <div className="empty-state-title">No Active Run</div>
        <div className="empty-state-text">Execute a test run to monitor it here. Your latest run will appear automatically.</div>
      </div>
    );
  }

  const allStats = calcStats(run.categories?.flatMap(c => c.tests) || []);
  const activeCategory = run.categories?.find(c => c.id === selectedCat);
  const events = agentEvents[run.id] || [];

  const filteredTests = activeCategory ? activeCategory.tests.filter(t => {
    if (mFilter === 'all') return true;
    return t.status === mFilter;
  }) : [];

  const overallVerdict = VM[run.verdict] || VM['running'];

  const handleLogSummary = async (catId, testIdx, testName, log) => {
    const key = `${run.id}-${catId}-${testIdx}`;
    if (aiCache[key]) { setLogSummaryHtml(prev => ({ ...prev, [key]: aiCache[key] })); return; }
    setSummaryLoading(prev => ({ ...prev, [key]: true }));
    let text = '';
    await llm(
      [{ role: 'user', content: `Summarize this test log in 2-3 sentences. Test: ${testName}\n\n${log}` }],
      M.logSummary,
      chunk => { text += chunk; setLogSummaryHtml(prev => ({ ...prev, [key]: text })); }
    );
    setCacheItem(key, text);
    setSummaryLoading(prev => ({ ...prev, [key]: false }));
  };

  return (
    <div className="monitor-layout">
      <div className="monitor-main">
        {/* Run header */}
        <div className="card">
          <div className="card-body">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span className="font-mono" style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>{run.id}</span>
                  {run.status === 'running' && <div className="running-badge"><div className="pulse-dot" /> Running</div>}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>
                  {run.cluster} · {run.env} · {run.location} · Started {timeAgo(run.startedAt)}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: allStats.rate >= 95 ? '#22c55e' : allStats.rate >= 75 ? '#f59e0b' : '#ef4444' }}>
                    {allStats.rate}%
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text3)' }}>Pass Rate</div>
                </div>
                <div
                  className="verdict-display"
                  style={{ color: overallVerdict.color, borderColor: overallVerdict.border, background: overallVerdict.bg }}
                >
                  {overallVerdict.icon} {overallVerdict.label}
                </div>
                {run.status !== 'running' && (
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={() => rerun(run)}
                    title="Re-run with same config"
                  >
                    ↺ Rerun
                  </button>
                )}
              </div>
            </div>

            {/* Progress bar */}
            <div style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text3)', marginBottom: 6 }}>
                <span>{allStats.passed + allStats.failed} / {allStats.total} tests complete</span>
                <span>{allStats.passed} passed · {allStats.failed} failed · {allStats.running + allStats.pending} remaining</span>
              </div>
              <div className="progress-bar-wrap" style={{ height: 8 }}>
                <div className="progress-bar" style={{
                  width: `${allStats.total > 0 ? ((allStats.passed + allStats.failed) / allStats.total) * 100 : 0}%`,
                  background: 'linear-gradient(90deg, #22c55e, #16a34a)'
                }} />
              </div>
            </div>
          </div>
        </div>

        {/* Meta grid */}
        <div className="meta-grid">
          <div className="meta-item">
            <div className="meta-label">Total Tests</div>
            <div className="meta-value">{allStats.total}</div>
          </div>
          <div className="meta-item">
            <div className="meta-label">Passed</div>
            <div className="meta-value" style={{ color: '#22c55e' }}>{allStats.passed}</div>
          </div>
          <div className="meta-item">
            <div className="meta-label">Failed</div>
            <div className="meta-value" style={{ color: '#ef4444' }}>{allStats.failed}</div>
          </div>
          <div className="meta-item">
            <div className="meta-label">Running</div>
            <div className="meta-value" style={{ color: 'var(--accent)' }}>{allStats.running}</div>
          </div>
          <div className="meta-item">
            <div className="meta-label">Pending</div>
            <div className="meta-value" style={{ color: 'var(--text3)' }}>{allStats.pending}</div>
          </div>
          <div className="meta-item">
            <div className="meta-label">Environment</div>
            <div className="meta-value">{run.env}</div>
          </div>
          <div className="meta-item">
            <div className="meta-label">Cluster</div>
            <div className="meta-value font-mono" style={{ fontSize: 11 }}>{run.cluster}</div>
          </div>
          <div className="meta-item">
            <div className="meta-label">Started</div>
            <div className="meta-value" style={{ fontSize: 12 }}>{timeAgo(run.startedAt)}</div>
          </div>
        </div>

        {/* Category cards */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">📁 Categories</div>
          </div>
          <div className="card-body">
            <div className="cat-status-grid">
              {(run.categories || []).map(cat => {
                const s = calcStats(cat.tests);
                const color = s.rate >= 95 ? '#22c55e' : s.rate >= 75 ? '#f59e0b' : '#ef4444';
                const isActive = selectedCat === cat.id;
                const catDef = catsArr.find(c => c.id === cat.id);
                return (
                  <div
                    key={cat.id}
                    className={`cat-status-card ${isActive ? 'active' : ''}`}
                    onClick={() => setSelectedCat(cat.id)}
                  >
                    <div className="cat-status-header">
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span className="cat-status-name">{cat.name}</span>
                        {catDef?.critical && <span style={{ fontSize: 9, color: 'var(--accent)', fontWeight: 700 }}>CRITICAL</span>}
                      </div>
                      <span className="cat-status-rate" style={{ color }}>{s.rate}%</span>
                    </div>
                    <div className="mini-progress">
                      <div className="mini-progress-fill" style={{ width: `${s.rate}%`, background: color }} />
                    </div>
                    <div className="cat-status-counts">
                      <span style={{ color: '#22c55e' }}>✓{s.passed}</span>
                      <span style={{ color: '#ef4444' }}>✗{s.failed}</span>
                      {s.running > 0 && <span style={{ color: 'var(--accent)' }}>⏳{s.running}</span>}
                      {s.pending > 0 && <span>·{s.pending}</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Test table */}
        {activeCategory && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">🧪 {activeCategory.name} Tests</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {['all', 'passed', 'failed', 'running', 'pending'].map(f => (
                  <button
                    key={f}
                    className={`tab-btn ${mFilter === f ? 'active' : ''}`}
                    style={{ flex: 'none', minWidth: 'unset' }}
                    onClick={() => setMFilter(f)}
                  >
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div className="table-scroll">
              <table className="test-table">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>#</th>
                    <th>Test Name</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Logs</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTests.map((test, idx) => {
                    const realIdx = activeCategory.tests.findIndex(t => t === test);
                    const logKey = `${activeCategory.id}-${realIdx}`;
                    const aiKey = `${run.id}-${activeCategory.id}-${realIdx}`;
                    const isLogOpen = openLogs.has(logKey);
                    return (
                      <React.Fragment key={realIdx}>
                        <tr>
                          <td style={{ color: 'var(--text3)', fontSize: 11 }}>{realIdx + 1}</td>
                          <td style={{ fontWeight: 500 }}>{test.name}</td>
                          <td><StatusBadge status={test.status} /></td>
                          <td style={{ color: 'var(--text3)', fontSize: 12 }}>
                            {test.duration ? formatDuration(test.duration) : '—'}
                          </td>
                          <td>
                            {test.log ? (
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button className="log-toggle-btn" onClick={() => toggleLog(logKey)}>
                                  {isLogOpen ? '▲ Hide' : '▼ Logs'}
                                </button>
                                {test.status === 'failed' && (
                                  <button
                                    className="log-toggle-btn"
                                    style={{ color: 'var(--purple)' }}
                                    onClick={() => { toggleLog(logKey); handleLogSummary(activeCategory.id, realIdx, test.name, test.log); }}
                                  >
                                    🤖 AI
                                  </button>
                                )}
                              </div>
                            ) : '—'}
                          </td>
                        </tr>
                        {isLogOpen && (
                          <tr className="log-row">
                            <td colSpan={5}>
                              <div className="log-block">{test.log}</div>
                              {logSummaryHtml[aiKey] && (
                                <div className="inline-ai-block">
                                  <strong>🤖 AI Summary:</strong> {logSummaryHtml[aiKey]}
                                  {summaryLoading[aiKey] && <span className="ai-streaming" />}
                                </div>
                              )}
                              {summaryLoading[aiKey] && !logSummaryHtml[aiKey] && (
                                <div className="inline-ai-block">
                                  <span className="spinner" style={{ color: 'var(--purple)' }} /> Summarizing log...
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
              {filteredTests.length === 0 && (
                <div className="empty-state" style={{ padding: '30px 20px' }}>
                  <div className="empty-state-text">No tests match this filter</div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Agent Feed Sidebar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card" style={{ position: 'sticky', top: 80 }}>
          <div className="card-header">
            <div className="card-title">🤖 Agent Feed</div>
            <span className="badge badge-purple">{events.length} events</span>
          </div>
          <div className="card-body" style={{ padding: 12 }}>
            <div className="agent-feed" ref={agentFeedRef} style={{ maxHeight: '70vh' }}>
              {events.length === 0 ? (
                <div className="text-faint text-sm" style={{ textAlign: 'center', padding: '20px 0' }}>
                  Agent events will appear here during execution...
                </div>
              ) : (
                [...events].reverse().map((event, i) => (
                  <AgentEvent key={i} event={event} />
                ))
              )}
            </div>
          </div>
        </div>

        {/* Run selector */}
        {runs.length > 1 && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">🔄 Switch Run</div>
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {runs.slice(0, 5).map(r => {
                const v = VM[r.verdict] || VM['running'];
                return (
                  <button
                    key={r.id}
                    className={`btn btn-sm ${activeId === r.id ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ justifyContent: 'flex-start', fontFamily: 'var(--mono)', fontSize: 11 }}
                    onClick={() => setActiveId(r.id)}
                  >
                    {v.icon} {r.id}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
