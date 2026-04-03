import React, { useState, useEffect, useRef } from 'react';
import useStore from '../store/useStore.js';
import { M, ML } from '../data/constants.js';
import { runsApi } from '../utils/api.js';
import { mkId, calcStats } from '../utils/helpers.js';
import { llm } from '../utils/llm.js';

function AiPanel({ title, model, content, loading, icon }) {
  return (
    <div className="ai-panel">
      <div className="ai-panel-header">
        <div className="ai-panel-icon">{icon || '🤖'}</div>
        <div>
          <div className="ai-panel-title">{title}</div>
          <div className="ai-panel-model">
            <span className="model-chip">⚡ {ML[model] || model}</span>
          </div>
        </div>
      </div>
      <div className="ai-panel-body">
        {loading ? (
          <div className="ai-placeholder">
            <div className="ai-placeholder-line" style={{ width: '90%' }} />
            <div className="ai-placeholder-line" style={{ width: '75%' }} />
            <div className="ai-placeholder-line" style={{ width: '85%' }} />
            <div className="ai-placeholder-line" style={{ width: '60%' }} />
          </div>
        ) : content ? (
          <div className="ai-output" dangerouslySetInnerHTML={{ __html: content }} />
        ) : (
          <div className="text-faint text-sm" style={{ fontStyle: 'italic' }}>
            Click "Execute Run" to trigger AI analysis...
          </div>
        )}
      </div>
    </div>
  );
}

// Module-level map so EventSource survives component unmount/remount
const activeStreams = new Map(); // runId → EventSource

// ─── Monitoring Agent — Kafka SSE listener ───────────────────────────────────
// Connects to the backend SSE stream which fans out messages from testops-topic.
// Each Kafka message carries { run_id, event, ... } — see message format in
// backend/app/services/kafka_service.py and the stream router.
function kafkaMonitor(runId, store) {
  const { updateTest, updateRun, pushEvent } = store;

  // Close any stale stream for this run before opening a new one
  activeStreams.get(runId)?.close();

  const es = new EventSource(`/api/v1/runs/${runId}/stream`);
  activeStreams.set(runId, es);

  pushEvent(runId, {
    type: 'info',
    title: '🤖 Monitor Agent',
    body: `Connected to Kafka stream for run ${runId}`,
    time: new Date().toLocaleTimeString(),
  });

  es.onmessage = (event) => {
    let msg;
    try { msg = JSON.parse(event.data); } catch { return; }

    const now = new Date().toLocaleTimeString();

    // ── test_update ──────────────────────────────────────────────────────────
    if (msg.event === 'test_update') {
      const run = useStore.getState().runs.find(r => r.id === runId);
      const cat = run?.categories.find(c => c.id === msg.category_id);
      const testIdx = cat?.tests.findIndex(t => t.name === msg.test_name);

      if (cat && testIdx >= 0) {
        updateTest(runId, msg.category_id, testIdx, {
          status: msg.status,
          log: msg.log ?? '',
          duration: msg.duration_ms ?? null,
        });

        if (msg.status === 'passed' || msg.status === 'failed') {
          pushEvent(runId, {
            type: msg.status === 'passed' ? 'success' : 'error',
            title: msg.status === 'passed' ? 'Test Passed' : 'Test Failed',
            body: msg.test_name,
            time: now,
          });

          // Alert on critical category failure
          if (msg.status === 'failed') {
            const catDef = useStore.getState().catsArr.find(c => c.id === msg.category_id);
            if (catDef?.critical) {
              pushEvent(runId, {
                type: 'error',
                title: '⚠ Critical Failure Detected',
                body: `${msg.test_name} failed in critical category ${catDef.name}`,
                time: now,
              });
            }

            // Weak category warning — check after each failure
            const updatedRun = useStore.getState().runs.find(r => r.id === runId);
            const updatedCat = updatedRun?.categories.find(c => c.id === msg.category_id);
            if (updatedCat) {
              const s = calcStats(updatedCat.tests);
              if (s.total > 0 && s.passed + s.failed >= 3 && s.rate < 70) {
                pushEvent(runId, {
                  type: 'warn',
                  title: '⚠ Weak Category',
                  body: `${cat.name} is at ${s.rate}% pass rate — below 70% threshold`,
                  time: now,
                });
              }
            }
          }
        }
      }

      // ── auto-complete: if every test is now passed/failed, finalise ────────
      const currentRun = useStore.getState().runs.find(r => r.id === runId);
      if (currentRun) {
        const allTests = currentRun.categories.flatMap(c => c.tests);
        const done = allTests.every(t => t.status === 'passed' || t.status === 'failed');
        if (done && currentRun.status === 'running') {
          const passed = allTests.filter(t => t.status === 'passed').length;
          const rate = allTests.length > 0 ? Math.round((passed / allTests.length) * 100) : 0;
          const verdict = rate >= 95 ? 'ready' : rate >= 75 ? 'at-risk' : 'not-ready';
          const finalStatus = rate < 60 ? 'failed' : 'completed';
          const completedAt = new Date().toISOString();
          updateRun(runId, { status: finalStatus, overallRate: rate, verdict, completedAt });
          pushEvent(runId, {
            type: rate >= 95 ? 'success' : rate >= 75 ? 'warn' : 'error',
            title: '🤖 Monitor Agent',
            body: `All tests complete — ${rate}% pass rate (${verdict.replace('-', ' ')})`,
            time: now,
          });
          const finalCategories = useStore.getState().runs.find(r => r.id === runId)?.categories;
          runsApi.update(runId, {
            status: finalStatus, overall_rate: rate, verdict,
            categories: finalCategories, completed_at: completedAt,
          }).catch(err => console.warn('Failed to persist run to DB:', err));
          activeStreams.delete(runId);
          es.close();
        }
      }
    }

    // ── run_completed ────────────────────────────────────────────────────────
    if (msg.event === 'run_completed') {
      // Use server-provided rate or compute from store
      let rate = msg.overall_rate;
      if (rate == null) {
        const finalRun = useStore.getState().runs.find(r => r.id === runId);
        const allTests = finalRun?.categories.flatMap(c => c.tests) ?? [];
        const passed = allTests.filter(t => t.status === 'passed').length;
        rate = allTests.length > 0 ? Math.round((passed / allTests.length) * 100) : 0;
      }

      const verdict = rate >= 95 ? 'ready' : rate >= 75 ? 'at-risk' : 'not-ready';
      const finalStatus = rate < 60 ? 'failed' : 'completed';
      const completedAt = msg.timestamp ?? new Date().toISOString();

      updateRun(runId, { status: finalStatus, overallRate: rate, verdict, completedAt });

      pushEvent(runId, {
        type: rate >= 95 ? 'success' : rate >= 75 ? 'warn' : 'error',
        title: '🤖 Monitor Agent',
        body: `Run completed — ${rate}% pass rate (${verdict.replace('-', ' ')})`,
        time: now,
      });

      // Persist final state to DB
      const finalCategories = useStore.getState().runs.find(r => r.id === runId)?.categories;
      runsApi.update(runId, {
        status: finalStatus,
        overall_rate: rate,
        verdict,
        categories: finalCategories,
        completed_at: completedAt,
      }).catch(err => console.warn('Failed to persist run to DB:', err));

      activeStreams.delete(runId);
      es.close();
    }
  };

  es.onerror = () => {
    pushEvent(runId, {
      type: 'warn',
      title: '⚠ Monitor Agent',
      body: 'Stream disconnected — reconnecting…',
      time: new Date().toLocaleTimeString(),
    });
  };

  return es;
}

export default function Execute() {
  const store = useStore();
  const { runs, addRun, updateTest, updateRun, pushEvent, setActiveId, setView, selEnvVal, setSelEnv, aiCache, setCacheItem, locsMap, catsArr, envsArr, refDataLoaded, pendingRerun, clearPendingRerun } = store;

  const [selectedLoc, setSelectedLoc] = useState('');
  const [selectedCluster, setSelectedCluster] = useState('');
  const [selectedScope, setSelectedScope] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [runId, setRunId] = useState(() => mkId());
  const [runIdCopied, setRunIdCopied] = useState(false);

  // Initialise dropdown selections once DB data arrives (or from a rerun)
  useEffect(() => {
    if (!refDataLoaded) return;
    if (pendingRerun) {
      setSelectedLoc(pendingRerun.location);
      setSelectedCluster(pendingRerun.cluster);
      setSelEnv(pendingRerun.env);
      setSelectedScope(pendingRerun.scopeIds);
      clearPendingRerun();
    } else {
      const firstLoc = Object.keys(locsMap)[0] ?? '';
      setSelectedLoc(firstLoc);
      setSelectedCluster(locsMap[firstLoc]?.clusters[0] ?? '');
      setSelectedScope(catsArr.map(c => c.id));
    }
  }, [refDataLoaded]);
  const [preflightHtml, setPreflightHtml] = useState('');
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [patternsHtml, setPatternsHtml] = useState('');
  const [patternsLoading, setPatternsLoading] = useState(false);

  const monitorRef = useRef(null);

  const locOptions = Object.entries(locsMap);
  const clusterOptions = locsMap[selectedLoc]?.clusters || [];

  const handleLocChange = (e) => {
    setSelectedLoc(e.target.value);
    setSelectedCluster(locsMap[e.target.value].clusters[0]);
  };

  const toggleCat = (id) => {
    setSelectedScope(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const selectAll = () => setSelectedScope(catsArr.map(c => c.id));
  const selectCritical = () => setSelectedScope(catsArr.filter(c => c.critical).map(c => c.id));
  const clearAll = () => setSelectedScope([]);

  const selectedCats = catsArr.filter(c => selectedScope.includes(c.id));
  const totalTests = selectedCats.reduce((s, c) => s + c.tests.length, 0);

  // Pre-flight AI
  const runPreflight = async () => {
    const cacheKey = `preflight-${selectedLoc}-${selectedCluster}-${selEnvVal}-${selectedScope.join(',')}`;
    if (aiCache[cacheKey]) { setPreflightHtml(aiCache[cacheKey]); return; }

    setPreflightLoading(true);
    let text = '';
    await llm(
      [{ role: 'user', content: `Pre-flight check for OpenShift cluster ${selectedCluster} (${locsMap[selectedLoc]?.label}), environment: ${selEnvVal}. Test categories: ${selectedCats.map(c => c.name).join(', ')}. Total tests: ${totalTests}. List key risks and readiness checks needed. Be concise.` }],
      M.preflight,
      chunk => { text += chunk; setPreflightHtml(text + '...'); }
    );
    setPreflightHtml(text);
    setCacheItem(cacheKey, text);
    setPreflightLoading(false);
  };

  // Historical patterns AI
  const runPatterns = async () => {
    const completedRuns = runs.filter(r => r.status === 'completed' || r.status === 'failed');
    if (completedRuns.length === 0) {
      setPatternsHtml('No historical runs available yet. Execute some runs first.');
      return;
    }
    setPatternsLoading(true);
    let text = '';
    const summary = completedRuns.slice(0, 5).map(r =>
      `Run ${r.id}: ${r.overallRate}% pass rate on ${r.cluster} (${r.env})`
    ).join('\n');
    await llm(
      [{ role: 'user', content: `Historical pattern analysis for OpenShift test runs:\n${summary}\n\nIdentify patterns, trends, and risk factors. What should we watch for in the next run?` }],
      M.patterns,
      chunk => { text += chunk; setPatternsHtml(text + '...'); }
    );
    setPatternsHtml(text);
    setPatternsLoading(false);
  };

  const copyRunId = () => {
    navigator.clipboard.writeText(runId);
    setRunIdCopied(true);
    setTimeout(() => setRunIdCopied(false), 2000);
  };

  const handleExecute = async () => {
    if (isRunning || selectedScope.length === 0 || !runId.trim()) return;
    setIsRunning(true);
    const categories = selectedCats.map(cat => ({
      id: cat.id,
      name: cat.name,
      critical: cat.critical,
      tests: cat.tests.map(name => ({
        name,
        status: 'pending',
        log: '',
        duration: null
      }))
    }));

    const startedAt = new Date().toISOString();
    const run = {
      id: runId,
      status: 'running',
      env: selEnvVal,
      location: selectedLoc,
      cluster: selectedCluster,
      categories,
      overallRate: 0,
      verdict: 'running',
      startedAt,
      completedAt: null
    };

    addRun(run);
    setActiveId(runId);

    // Persist run to DB
    runsApi.create({
      id: runId,
      status: 'running',
      env: selEnvVal,
      location: selectedLoc,
      cluster: selectedCluster,
      overall_rate: 0,
      verdict: 'running',
      categories,
      started_at: startedAt,
    }).catch(err => console.warn('Failed to save run to DB:', err));

    // Start pre-flight AI analysis
    runPreflight();

    // Connect monitoring agent to Kafka SSE stream — updates flow in as
    // the external test framework publishes to testops-topic
    if (monitorRef.current) monitorRef.current.close();
    monitorRef.current = kafkaMonitor(runId, {
      updateTest: store.updateTest,
      updateRun: store.updateRun,
      pushEvent: store.pushEvent,
    });

    setIsRunning(false);
    setRunId(mkId()); // pre-generate ID for the next run
    setView('monitor');
  };

  if (!refDataLoaded) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, flexDirection: 'column', gap: 12 }}>
        <div className="spinner" />
        <span className="text-muted">Loading configuration from database…</span>
      </div>
    );
  }

  return (
    <div className="execute-layout">
      <div className="execute-main">
        {/* Configuration Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">⚙ Run Configuration</div>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Run ID — user-editable, shared with external test framework */}
            <div className="form-group">
              <label className="form-label">
                Run ID
                <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text3)', marginLeft: 8 }}>
                  — share this with your test framework so Kafka messages are tagged correctly
                </span>
              </label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  className="form-input"
                  style={{ fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.5px', flex: 1 }}
                  value={runId}
                  onChange={e => setRunId(e.target.value.trim())}
                  placeholder="PRT-XXXXX-000"
                  disabled={isRunning}
                />
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={copyRunId}
                  title="Copy Run ID"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {runIdCopied ? '✓ Copied' : '⎘ Copy'}
                </button>
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={() => setRunId(mkId())}
                  title="Generate new Run ID"
                  disabled={isRunning}
                >
                  ↺
                </button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="form-group">
                <label className="form-label">Data Centre / Location</label>
                <select className="form-select" value={selectedLoc} onChange={handleLocChange}>
                  {locOptions.map(([k, v]) => (
                    <option key={k} value={k}>{k} — {v.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Target Cluster</label>
                <select className="form-select" value={selectedCluster} onChange={e => setSelectedCluster(e.target.value)}>
                  {clusterOptions.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Environment</label>
              <div className="env-buttons">
                {envsArr.map(env => (
                  <button
                    key={env}
                    className={`env-btn ${selEnvVal === env ? 'active' : ''}`}
                    onClick={() => setSelEnv(env)}
                  >
                    {env === 'Production' ? '🔴' : env === 'UAT' ? '🟡' : '🟢'} {env}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Scope Selection */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">🎯 Test Scope ({selectedScope.length}/{catsArr.length} categories · {totalTests} tests)</div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn btn-sm btn-secondary" onClick={selectAll}>All</button>
              <button className="btn btn-sm btn-secondary" onClick={selectCritical}>Critical</button>
              <button className="btn btn-sm btn-ghost" onClick={clearAll}>Clear</button>
            </div>
          </div>
          <div className="card-body">
            <div className="scope-grid">
              {catsArr.map(cat => (
                <div
                  key={cat.id}
                  className={`scope-chip ${selectedScope.includes(cat.id) ? 'selected' : ''}`}
                  onClick={() => toggleCat(cat.id)}
                >
                  <div className="scope-chip-check">
                    {selectedScope.includes(cat.id) && '✓'}
                  </div>
                  <div>
                    <div className="scope-chip-name">{cat.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)' }}>{cat.tests.length} tests</div>
                  </div>
                  <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
                    <span className="scope-chip-count">{cat.tests.length}</span>
                    {cat.critical && <span className="scope-chip-critical">CRIT</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Execute Button */}
        <button
          className="execute-btn"
          onClick={handleExecute}
          disabled={isRunning || selectedScope.length === 0}
        >
          {isRunning ? (
            <><span className="spinner" /> Executing {totalTests} Tests...</>
          ) : (
            <>▶ Execute Production Readiness Check</>
          )}
        </button>
      </div>

      {/* Sidebar */}
      <div className="execute-sidebar">
        <AiPanel
          title="Pre-Flight Analysis"
          model={M.preflight}
          content={preflightHtml}
          loading={preflightLoading}
          icon="🛫"
        />

        <AiPanel
          title="Historical Patterns"
          model={M.patterns}
          content={patternsHtml}
          loading={patternsLoading}
          icon="📊"
        />

        <div className="card">
          <div className="card-header">
            <div className="card-title">📋 Run Summary</div>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, alignItems: 'center' }}>
              <span className="text-muted">Run ID</span>
              <span
                className="font-mono"
                style={{ fontSize: 11, color: 'var(--accent)', cursor: 'pointer', fontWeight: 600 }}
                onClick={copyRunId}
                title="Click to copy"
              >
                {runId || '—'} {runIdCopied ? '✓' : ''}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span className="text-muted">Location</span>
              <span className="font-bold">{locsMap[selectedLoc]?.label}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span className="text-muted">Cluster</span>
              <span className="font-bold font-mono" style={{ fontSize: 12 }}>{selectedCluster}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span className="text-muted">Environment</span>
              <span className="badge badge-blue">{selEnvVal}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span className="text-muted">Categories</span>
              <span className="font-bold">{selectedScope.length}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span className="text-muted">Total Tests</span>
              <span className="font-bold">{totalTests}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span className="text-muted">Critical Cats</span>
              <span className="badge badge-red">{selectedCats.filter(c => c.critical).length}</span>
            </div>

            <button
              className="btn btn-secondary btn-sm"
              style={{ marginTop: 8 }}
              onClick={() => { runPreflight(); runPatterns(); }}
              disabled={preflightLoading || patternsLoading}
            >
              {preflightLoading ? <><span className="spinner" /> Analyzing...</> : '🤖 Run AI Analysis'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
