import React, { useState, useEffect, useRef } from 'react';
import useStore from '../store/useStore.js';
import { M, ML } from '../data/constants.js';
import { runsApi } from '../utils/api.js';
import { mkId, fakeLog, calcStats } from '../utils/helpers.js';
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

// ─── Simulation ──────────────────────────────────────────────────────────────
async function doSimulate(runId, categories, store) {
  const { updateTest, updateRun, pushEvent } = store;
  const allTests = [];
  categories.forEach(cat => {
    cat.tests.forEach((test, idx) => {
      allTests.push({ catId: cat.id, testIdx: idx, name: test.name });
    });
  });

  let completedCount = 0;
  for (const item of allTests) {
    // Set running
    updateTest(runId, item.catId, item.testIdx, { status: 'running' });
    const duration = 380 + Math.random() * 750;
    await new Promise(r => setTimeout(r, duration));

    const ok = Math.random() < 0.88;
    const log = fakeLog(item.name, ok);
    updateTest(runId, item.catId, item.testIdx, {
      status: ok ? 'passed' : 'failed',
      log,
      duration: Math.round(duration)
    });
    completedCount++;

    pushEvent(runId, {
      type: ok ? 'success' : 'error',
      title: ok ? 'Test Passed' : 'Test Failed',
      body: item.name,
      time: new Date().toLocaleTimeString()
    });
  }

  // Calculate final stats
  const state = store.getState ? store.getState() : null;
  // Recalculate from store
  setTimeout(() => {
    const storeRuns = useStore.getState().runs;
    const run = storeRuns.find(r => r.id === runId);
    if (!run) return;
    let totalPassed = 0, totalTests = 0;
    run.categories.forEach(cat => {
      cat.tests.forEach(t => {
        totalTests++;
        if (t.status === 'passed') totalPassed++;
      });
    });
    const rate = totalTests > 0 ? Math.round((totalPassed / totalTests) * 100) : 0;
    const verdict = rate >= 95 ? 'ready' : rate >= 75 ? 'at-risk' : 'not-ready';
    updateRun(runId, {
      status: rate < 60 ? 'failed' : 'completed',
      overallRate: rate,
      verdict,
      completedAt: new Date().toISOString()
    });
    pushEvent(runId, {
      type: rate >= 95 ? 'success' : rate >= 75 ? 'warn' : 'error',
      title: 'Run Completed',
      body: `Overall pass rate: ${rate}% — ${verdict.replace('-', ' ')}`,
      time: new Date().toLocaleTimeString()
    });
  }, 100);
}

// ─── Monitoring Agent ────────────────────────────────────────────────────────
function agMonitor(runId, pushEvent) {
  let seenTests = new Set();
  let checkCount = 0;

  const interval = setInterval(() => {
    const runs = useStore.getState().runs;
    const run = runs.find(r => r.id === runId);
    if (!run) { clearInterval(interval); return; }

    if (run.status !== 'running') {
      clearInterval(interval);
      pushEvent(runId, {
        type: 'ai',
        title: '🤖 Monitor Agent',
        body: 'Run completed. Monitoring stopped.',
        time: new Date().toLocaleTimeString()
      });
      return;
    }

    checkCount++;
    if (!run.categories) return;

    run.categories.forEach(cat => {
      cat.tests.forEach((test, idx) => {
        const key = `${cat.id}-${idx}`;
        if (seenTests.has(key)) return;
        if (test.status === 'passed' || test.status === 'failed') {
          seenTests.add(key);
          const catDef = useStore.getState().catsArr.find(c => c.id === cat.id);
          if (test.status === 'failed' && catDef?.critical) {
            pushEvent(runId, {
              type: 'error',
              title: '⚠ Critical Failure Detected',
              body: `${test.name} failed in critical category ${catDef.name}`,
              time: new Date().toLocaleTimeString()
            });
          }
        }
      });
    });

    // Every 10 checks, analyze weak categories
    if (checkCount % 10 === 0) {
      run.categories.forEach(cat => {
        const s = calcStats(cat.tests);
        if (s.total > 0 && s.rate < 70 && s.passed + s.failed > 2) {
          pushEvent(runId, {
            type: 'warn',
            title: '⚠ Weak Category',
            body: `${cat.id} is at ${s.rate}% pass rate — below 70% threshold`,
            time: new Date().toLocaleTimeString()
          });
        }
      });
    }
  }, 600);

  return interval;
}

export default function Execute() {
  const store = useStore();
  const { runs, addRun, updateTest, updateRun, pushEvent, setActiveId, setView, selEnvVal, setSelEnv, aiCache, setCacheItem, locsMap, catsArr, envsArr, refDataLoaded } = store;

  const [selectedLoc, setSelectedLoc] = useState('');
  const [selectedCluster, setSelectedCluster] = useState('');
  const [selectedScope, setSelectedScope] = useState([]);
  const [isRunning, setIsRunning] = useState(false);

  // Initialise dropdown selections once DB data arrives
  useEffect(() => {
    if (!refDataLoaded) return;
    const firstLoc = Object.keys(locsMap)[0] ?? '';
    setSelectedLoc(firstLoc);
    setSelectedCluster(locsMap[firstLoc]?.clusters[0] ?? '');
    setSelectedScope(catsArr.map(c => c.id));
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

  const handleExecute = async () => {
    if (isRunning || selectedScope.length === 0) return;
    setIsRunning(true);

    const runId = mkId();
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

    // Run preflight
    runPreflight();

    // Start monitor agent
    pushEvent(runId, {
      type: 'info',
      title: '🤖 Monitor Agent',
      body: `Monitoring run ${runId} on ${selectedCluster}`,
      time: new Date().toLocaleTimeString()
    });

    monitorRef.current = agMonitor(runId, pushEvent);

    // Start simulation
    await doSimulate(runId, categories, {
      updateTest: store.updateTest,
      updateRun: store.updateRun,
      pushEvent: store.pushEvent,
    });

    // Patch DB with final run state
    const finalRun = useStore.getState().runs.find(r => r.id === runId);
    if (finalRun) {
      runsApi.update(runId, {
        status: finalRun.status,
        overall_rate: finalRun.overallRate,
        verdict: finalRun.verdict,
        categories: finalRun.categories,
        completed_at: finalRun.completedAt,
      }).catch(err => console.warn('Failed to update run in DB:', err));
    }

    setIsRunning(false);
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
