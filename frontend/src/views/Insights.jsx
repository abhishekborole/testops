import React, { useState, useRef, useEffect } from 'react';
import useStore from '../store/useStore.js';
import { M, ML, VM } from '../data/constants.js';
import { calcStats, md } from '../utils/helpers.js';
import { llm } from '../utils/llm.js';

function AiSection({ title, model, icon, onRun, content, loading, children }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          {icon} {title}
          <span className="model-chip" style={{ marginLeft: 8 }}>⚡ {ML[model] || model}</span>
        </div>
        <button className="btn btn-sm btn-secondary" onClick={onRun} disabled={loading}>
          {loading ? <><span className="spinner" /> Running...</> : '▶ Run'}
        </button>
      </div>
      <div className="card-body">
        {children}
        {loading && !content && (
          <div className="ai-placeholder">
            <div className="ai-placeholder-line" style={{ width: '90%' }} />
            <div className="ai-placeholder-line" style={{ width: '75%' }} />
            <div className="ai-placeholder-line" style={{ width: '85%' }} />
            <div className="ai-placeholder-line" style={{ width: '60%' }} />
          </div>
        )}
        {content && (
          <div className="ai-output" dangerouslySetInnerHTML={{ __html: md(content) }} />
        )}
        {!content && !loading && (
          <div className="text-faint text-sm" style={{ fontStyle: 'italic' }}>
            Click "Run" to get AI analysis for the active run.
          </div>
        )}
      </div>
    </div>
  );
}

// ── Feature impact mapping: test name → affected platform capabilities ────────
const FEATURE_IMPACT = {
  // cluster-health
  'Node readiness validation':              ['Pod scheduling', 'All workloads'],
  'Control plane component health':         ['All API operations', 'kubectl access', 'Automation'],
  'etcd cluster quorum check':              ['Cluster state persistence', 'All API operations'],
  'API server availability':               ['API access', 'CI/CD pipelines', 'Web console'],
  'Scheduler and controller-manager status':['Pod scheduling', 'Auto-healing', 'Deployments'],
  'DNS resolution (CoreDNS) verification':  ['Service discovery', 'Pod-to-service communication'],
  'Cluster operator health sweep':          ['Platform operators', 'OCP feature delivery'],
  // network
  'Pod-to-pod connectivity':               ['Microservices communication', 'Service mesh'],
  'East-west traffic via OVN-Kubernetes':  ['Internal networking', 'Multi-tenant isolation'],
  'Load balancer VIP assignment':          ['External service exposure', 'Ingress traffic'],
  'Ingress controller routing':            ['HTTP/HTTPS routing', 'Application access'],
  'NetworkPolicy enforcement':             ['Security isolation', 'Tenant separation'],
  'SDN MTU configuration':                 ['Network performance', 'Large packet transfers'],
  'DNS external resolution':               ['External API calls', 'Image pulls'],
  // storage
  'PVC dynamic provisioning (block)':      ['Databases', 'Stateful applications'],
  'PVC dynamic provisioning (file)':       ['Shared file storage', 'ReadWriteMany workloads'],
  'PowerMax host connectivity':            ['Enterprise storage', 'High-performance I/O'],
  'Storage class availability':            ['All persistent storage requests'],
  'Volume snapshot creation':              ['Point-in-time recovery', 'Data snapshots'],
  'PVC expansion validation':              ['Online storage resize', 'Storage scaling'],
  'Data persistence across pod restarts':  ['Stateful application reliability'],
  // vm-ops
  'VM create and boot cycle':              ['VM provisioning', 'IaaS workloads'],
  'VM start / stop / restart':             ['VM lifecycle management'],
  'VM disk hot-attach':                    ['Storage expansion without downtime'],
  'VM NIC hot-attach':                     ['Network reconfiguration without downtime'],
  'VM console access':                     ['VM debugging', 'Emergency break-glass access'],
  'VM resource limits enforcement':        ['Multi-tenant resource isolation'],
  'VM template instantiation':             ['Rapid VM deployment', 'Self-service VMs'],
  // vm-mig
  'Live migration (same node)':            ['Zero-downtime maintenance', 'Node evacuation'],
  'Live migration (cross-node)':           ['Node drain', 'Hardware maintenance windows'],
  'vSphere cold import via MTV':           ['vSphere VM migration'],
  'vSphere warm import via MTV':           ['Near-zero-downtime vSphere migration'],
  'Migration network bandwidth':           ['Migration performance SLA'],
  'Post-migration health check':           ['Migration validation', 'Workload integrity'],
  // security
  'RBAC policy enforcement':               ['Access control', 'Least-privilege model'],
  'SCC validation':                        ['Pod security', 'Container isolation'],
  'Network policy isolation':              ['Tenant security', 'Data separation'],
  'Secret encryption at rest':             ['Credential security', 'Data-at-rest protection'],
  'TLS certificate validity':              ['Encrypted API communications', 'HTTPS endpoints'],
  'Pod security admission':                ['Container security posture'],
  'Audit log availability':               ['Security forensics', 'Compliance audit trail'],
  // monitoring
  'Prometheus scrape targets':             ['Metrics collection', 'Alert triggers'],
  'Alertmanager connectivity':             ['Alert routing', 'Incident notifications'],
  'Grafana dashboard access':              ['Observability dashboards', 'Ops visibility'],
  'Loki log ingestion':                    ['Log aggregation', 'Log-based alerting'],
  'Alert routing verification':            ['On-call paging', 'PagerDuty/Slack integration'],
  'Custom metric collection':              ['Application performance monitoring'],
  // backup
  'OADP backup creation':                  ['Disaster recovery', 'Namespace backup'],
  'OADP restore validation':               ['Disaster recovery restore', 'Data recovery'],
  'Velero schedule execution':             ['Automated backup SLA'],
  'PV snapshot backup':                    ['Volume-level backup', 'Database backup'],
  'Cross-namespace restore':               ['Cross-environment recovery'],
  'Backup retention policy':               ['Backup lifecycle', 'Storage cost control'],
  // integration
  'ACM hub connectivity':                  ['Multi-cluster management', 'Policy distribution'],
  'GitOps (ArgoCD) sync':                  ['Continuous deployment', 'GitOps workflows'],
  'CI/CD pipeline trigger':               ['Automated builds', 'Deployment pipelines'],
  'LDAP authentication':                   ['Enterprise SSO', 'User login'],
  'External registry pull':               ['Image deployment', 'Container builds'],
  'Webhook endpoint validation':           ['Event-driven automation', 'CI triggers'],
  // compliance
  'CIS Kubernetes benchmark':              ['CIS compliance posture'],
  'PCI-DSS control mapping':              ['Payment card compliance', 'Audit readiness'],
  'Pod security standard audit':           ['Security compliance', 'PSS enforcement'],
  'Node hardening baseline':               ['OS security compliance'],
  'Image scan policy enforcement':         ['Supply chain security', 'Vulnerability management'],
  // self-service
  'OpenShift console login':               ['Developer portal access', 'Self-service UI'],
  'Project creation via self-service':     ['Namespace provisioning', 'Developer onboarding'],
  'Resource quota enforcement':            ['Fair resource sharing', 'Cost governance'],
  'User role assignment':                  ['Access management', 'RBAC provisioning'],
  'Namespace isolation check':             ['Tenant isolation', 'Security boundary'],
};

// ── ImpactMatrix: pure static analysis, no AI call needed ────────────────────
function ImpactMatrix({ run, catsArr }) {
  // Group failures by category
  const categoryImpacts = [];
  run.categories?.forEach(c => {
    const catDef = catsArr.find(x => x.id === c.id);
    const failed = c.tests
      .filter(t => t.status === 'failed')
      .map(t => ({ name: t.name, impacts: FEATURE_IMPACT[t.name] ?? ['Unknown capability'] }));
    if (failed.length > 0) {
      categoryImpacts.push({
        catId: c.id,
        catName: c.name,
        critical: catDef?.critical ?? false,
        failedTests: failed,
        allImpacts: [...new Set(failed.flatMap(t => t.impacts))],
      });
    }
  });

  if (categoryImpacts.length === 0) return null;

  // Sort: critical categories first
  categoryImpacts.sort((a, b) => b.critical - a.critical);

  const totalFailed = categoryImpacts.reduce((s, c) => s + c.failedTests.length, 0);
  const totalCapabilities = new Set(categoryImpacts.flatMap(c => c.allImpacts)).size;
  const criticalCats = categoryImpacts.filter(c => c.critical).length;

  return (
    <div className="impact-section">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>
          ⚡ Features That Will NOT Work in Production
        </span>
      </div>

      {/* Summary pills */}
      <div className="impact-summary-bar" style={{ marginBottom: 14 }}>
        <span className="impact-summary-pill critical">✕ {totalFailed} test{totalFailed !== 1 ? 's' : ''} failed</span>
        {criticalCats > 0 && (
          <span className="impact-summary-pill critical">⚠ {criticalCats} critical area{criticalCats !== 1 ? 's' : ''} affected</span>
        )}
        <span className="impact-summary-pill warning">🔒 {totalCapabilities} platform capabilities impacted</span>
      </div>

      {/* Grouped by category — this is the primary content */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {categoryImpacts.map(cat => (
          <div key={cat.catId} style={{
            background: cat.critical ? 'rgba(220,38,38,0.06)' : 'rgba(217,119,6,0.05)',
            border: `1px solid ${cat.critical ? 'rgba(220,38,38,0.28)' : 'rgba(217,119,6,0.28)'}`,
            borderRadius: 8,
            padding: '10px 14px',
          }}>
            {/* Category label */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
                {cat.critical ? '🔴' : '🟠'} {cat.catName}
              </span>
              {cat.critical && (
                <span style={{ fontSize: 10, fontWeight: 700, color: '#dc2626', background: 'rgba(220,38,38,0.15)', padding: '1px 7px', borderRadius: 10 }}>
                  CRITICAL
                </span>
              )}
              <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 'auto' }}>
                {cat.failedTests.length} test{cat.failedTests.length !== 1 ? 's' : ''} failed
              </span>
            </div>
            {/* Broken capabilities as pills */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {cat.allImpacts.map(cap => (
                <span key={cap} style={{
                  fontSize: 11,
                  padding: '2px 9px',
                  borderRadius: 12,
                  background: cat.critical ? 'rgba(220,38,38,0.13)' : 'rgba(217,119,6,0.13)',
                  color: cat.critical ? '#b91c1c' : '#b45309',
                  fontWeight: 500,
                  border: `1px solid ${cat.critical ? 'rgba(220,38,38,0.2)' : 'rgba(217,119,6,0.2)'}`,
                }}>
                  {cap}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Collapsible test-by-test breakdown */}
      <details style={{ marginTop: 12 }}>
        <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--text3)', fontWeight: 600, userSelect: 'none', padding: '4px 0', listStyle: 'none' }}>
          ▶ Test-by-test breakdown ({totalFailed} failures)
        </summary>
        <div style={{ maxHeight: 260, overflowY: 'auto', borderRadius: 8, border: '1px solid var(--border)', marginTop: 8 }}>
          <table className="impact-table">
            <thead>
              <tr>
                <th>Test Case</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Features Broken</th>
              </tr>
            </thead>
            <tbody>
              {categoryImpacts.flatMap(cat =>
                cat.failedTests.map((t, i) => (
                  <tr key={`${cat.catId}-${i}`}>
                    <td style={{ fontWeight: 500, color: 'var(--text)', maxWidth: 180 }}>{t.name}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{cat.catName}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {cat.critical
                        ? <span style={{ color: '#dc2626', fontWeight: 700, fontSize: 11 }}>🔴 CRITICAL</span>
                        : <span style={{ color: '#d97706', fontWeight: 600, fontSize: 11 }}>🟠 Standard</span>}
                    </td>
                    <td>
                      <div className="impact-features-cell">
                        {t.impacts.map(cap => (
                          <span key={cap} className={`impact-capability-tag ${cat.critical ? 'critical' : 'normal'}`} style={{ fontSize: 10 }}>
                            {cap}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

function GoNoGoPanel({ run }) {
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);
  const { aiCache, setCacheItem, catsArr } = useStore();

  const getFailedTests = () => run.categories?.flatMap(c => {
    const catDef = catsArr.find(x => x.id === c.id);
    return c.tests.filter(t => t.status === 'failed').map(t => ({
      name: t.name, catName: c.name, critical: catDef?.critical ?? false,
      impacts: FEATURE_IMPACT[t.name] ?? ['Unknown capability'],
    }));
  }) ?? [];

  const runGoNoGo = async () => {
    if (!run) return;
    const key = `gong-${run.id}`;
    if (aiCache[key]) { setResult(aiCache[key]); return; }
    setLoading(true);
    setResult('');

    const catSummary = run.categories?.map(c => {
      const s = calcStats(c.tests);
      const catDef = catsArr.find(x => x.id === c.id);
      return `${c.name} (${catDef?.critical ? 'CRITICAL' : 'non-critical'}): ${s.passed}/${s.total} passed (${s.rate}%)`;
    }).join('\n') || '';

    const failedTests = getFailedTests();
    const impactSummary = failedTests.map(t =>
      `- [${t.critical ? 'CRITICAL' : 'standard'}] ${t.name} → breaks: ${t.impacts.join(', ')}`
    ).join('\n') || 'None';

    const prompt = `You are assessing production readiness for an OpenShift cluster.
Run ID: ${run.id} | Cluster: ${run.cluster} | Environment: ${run.env}
Overall pass rate: ${run.overallRate}% | Current verdict: ${run.verdict}

Category results:
${catSummary}

Feature impact of failures (what will NOT work in production):
${impactSummary}

Provide a definitive GO / NO-GO decision with:
1. **DECISION** (GO / CONDITIONAL GO / NO-GO) — state clearly upfront
2. **Broader Business Impact** — based on the feature impact list above, describe what business operations, user workflows, and platform capabilities will be unavailable or degraded. Be specific about which teams/workloads are affected.
3. **Critical Blockers** — list any failures that are hard stops for production
4. **Conditional Requirements** — if CONDITIONAL GO, list what must be fixed before go-live
5. **Risk Summary** — overall risk level and key concerns

Be authoritative and specific. Prioritise business impact over technical detail.`;

    let text = '';
    await llm(
      [{ role: 'user', content: prompt }],
      M.goNoGo,
      chunk => { text += chunk; setResult(text); }
    );
    setCacheItem(key, text);
    setLoading(false);
  };

  if (!run) return null;

  const v = VM[run.verdict] || VM['not-ready'];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          🎯 Go / No-Go Decision
          <span className="model-chip" style={{ marginLeft: 8 }}>⚡ {ML[M.goNoGo]}</span>
        </div>
        {/* Compact verdict strip + Assess button side by side */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '4px 14px', borderRadius: 20,
            background: v.bg, border: `1px solid ${v.border}`,
          }}>
            <span style={{ fontSize: 16 }}>{v.icon}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: v.color }}>{v.label}</span>
            <span style={{ fontSize: 11, color: 'var(--text3)' }}>{run.overallRate}%</span>
          </div>
          <button className="btn btn-sm btn-secondary" onClick={runGoNoGo} disabled={loading}>
            {loading ? <><span className="spinner" /> Analyzing...</> : '▶ AI Assess'}
          </button>
        </div>
      </div>
      <div className="card-body">

        {/* Feature impact matrix — PRIMARY FOCUS */}
        <ImpactMatrix run={run} catsArr={catsArr} />

        {/* AI deep analysis — secondary, opt-in */}
        {(result || loading) && (
          <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 10 }}>
              🤖 Opus Business Impact Analysis
            </div>
            {result && (
              <div className="gong-ai-output" style={{ maxHeight: 'none' }} dangerouslySetInnerHTML={{ __html: md(result) }} />
            )}
            {loading && (
              <div className="ai-placeholder">
                <div className="ai-placeholder-line" style={{ width: '85%' }} />
                <div className="ai-placeholder-line" style={{ width: '70%' }} />
                <div className="ai-placeholder-line" style={{ width: '90%' }} />
                <div className="ai-placeholder-line" style={{ width: '65%' }} />
              </div>
            )}
          </div>
        )}
        {!result && !loading && (
          <div style={{ marginTop: 14, fontSize: 12, color: 'var(--text3)', fontStyle: 'italic', textAlign: 'center' }}>
            Click "AI Assess" for Opus deep reasoning on business impact
          </div>
        )}
      </div>
    </div>
  );
}

function ChatPanel({ run }) {
  const { chatHist, appendChatMsg, setChatHist } = useStore();
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const messagesEndRef = useRef(null);

  const messages = chatHist[run?.id] || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || streaming || !run) return;
    const userMsg = { role: 'user', content: input };
    // Snapshot history before appending
    const prevHist = useStore.getState().chatHist[run.id] || [];
    appendChatMsg(run.id, userMsg);
    setInput('');
    setStreaming(true);

    const catSummary = run.categories?.map(c => {
      const s = calcStats(c.tests);
      return `${c.name}: ${s.rate}% (${s.passed}/${s.total})`;
    }).join(', ') || '';

    const sys = `You are an SRE expert analyzing run ${run.id} on ${run.cluster} (${run.env}).
Overall: ${run.overallRate}% pass rate. Categories: ${catSummary}.
Answer questions about this specific run. Be concise and actionable.`;

    const historyMsgs = [...prevHist, userMsg].map(m => ({ role: m.role, content: m.content }));

    let aiText = '';
    // Add placeholder assistant message
    appendChatMsg(run.id, { role: 'assistant', content: '' });

    await llm(
      historyMsgs,
      M.chat,
      chunk => {
        aiText += chunk;
        // Update the last message (assistant placeholder) in the store
        const currentHist = useStore.getState().chatHist[run.id] || [];
        const updated = [...currentHist.slice(0, -1), { role: 'assistant', content: aiText }];
        setChatHist(run.id, updated);
      },
      sys
    );

    setStreaming(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  if (!run) return null;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          💬 SRE Assistant Chat
          <span className="model-chip" style={{ marginLeft: 8 }}>⚡ {ML[M.chat]}</span>
        </div>
      </div>
      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="text-faint text-sm" style={{ textAlign: 'center', padding: '20px 0' }}>
              Ask me anything about this run... e.g. "What failed in storage?" or "How can we fix the network issues?"
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`chat-msg ${msg.role === 'user' ? 'chat-msg-user' : 'chat-msg-ai'}`}>
              <div className="chat-msg-avatar">
                {msg.role === 'user' ? 'AB' : 'AI'}
              </div>
              <div className="chat-bubble">
                {msg.role === 'assistant'
                  ? <span dangerouslySetInnerHTML={{ __html: md(msg.content) }} />
                  : msg.content
                }
                {msg.role === 'assistant' && streaming && i === messages.length - 1 && (
                  <span className="ai-streaming" />
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <div className="chat-input-row">
          <textarea
            className="chat-input"
            placeholder="Ask about this run..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
          />
          <button
            className="btn btn-primary"
            onClick={sendMessage}
            disabled={streaming || !input.trim()}
          >
            {streaming ? <span className="spinner" /> : '→'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Insights() {
  const { runs, activeId, aiCache, setCacheItem, agentEvents } = useStore();

  const selectableRuns = runs.filter(r => r.status === 'completed' || r.status === 'failed');
  const defaultRun = runs.find(r => r.id === activeId && (r.status === 'completed' || r.status === 'failed'))
    || selectableRuns[0];

  const [selectedRunId, setSelectedRunId] = useState(defaultRun?.id ?? '');
  const run = selectableRuns.find(r => r.id === selectedRunId) || defaultRun;

  // Reset AI outputs when the selected run changes
  const [failHtml, setFailHtml] = useState('');
  const [failLoading, setFailLoading] = useState(false);
  const [remHtml, setRemHtml] = useState('');
  const [remLoading, setRemLoading] = useState(false);
  const [replayHtml, setReplayHtml] = useState('');
  const [replayLoading, setReplayLoading] = useState(false);

  useEffect(() => {
    setFailHtml(aiCache[`fail-${run?.id}`] || '');
    setRemHtml(aiCache[`rem-${run?.id}`] || '');
    setReplayHtml(aiCache[`replay-${run?.id}`] || '');
  }, [selectedRunId]);

  const getFailedTests = () => {
    if (!run?.categories) return [];
    return run.categories.flatMap(c =>
      c.tests.filter(t => t.status === 'failed').map(t => ({ cat: c.name, name: t.name, log: t.log }))
    );
  };

  const runFailAnalysis = async () => {
    if (!run) return;
    const key = `fail-${run.id}`;
    if (aiCache[key]) { setFailHtml(aiCache[key]); return; }
    setFailLoading(true);
    setFailHtml('');
    const failed = getFailedTests();
    if (failed.length === 0) {
      setFailHtml('No failures detected in this run.');
      setFailLoading(false);
      return;
    }
    const prompt = `Analyze these test failures from OpenShift cluster ${run.cluster} (${run.env}):\n\n${
      failed.slice(0, 8).map(f => `Category: ${f.cat}\nTest: ${f.name}\nLog snippet: ${f.log?.slice(0, 200) || 'N/A'}`).join('\n\n')
    }\n\nProvide root cause analysis for each failure. Group related failures. Identify systemic issues.`;
    let text = '';
    await llm([{ role: 'user', content: prompt }], M.failAnalysis, chunk => { text += chunk; setFailHtml(text); });
    setCacheItem(key, text);
    setFailLoading(false);
  };

  const runRemediation = async () => {
    if (!run) return;
    const key = `rem-${run.id}`;
    if (aiCache[key]) { setRemHtml(aiCache[key]); return; }
    setRemLoading(true);
    setRemHtml('');
    const failed = getFailedTests();
    if (failed.length === 0) {
      setRemHtml('No failures to remediate!');
      setRemLoading(false);
      return;
    }
    const prompt = `Create a prioritized remediation roadmap for these OpenShift failures on ${run.cluster}:\n\n${
      failed.slice(0, 8).map(f => `- ${f.cat} / ${f.name}`).join('\n')
    }\n\nProvide step-by-step remediation commands and procedures. Prioritize critical items. Include verification steps.`;
    let text = '';
    await llm([{ role: 'user', content: prompt }], M.remediation, chunk => { text += chunk; setRemHtml(text); });
    setCacheItem(key, text);
    setRemLoading(false);
  };

  const runReplay = async () => {
    if (!run) return;
    const key = `replay-${run.id}`;
    if (aiCache[key]) { setReplayHtml(aiCache[key]); return; }
    setReplayLoading(true);
    setReplayHtml('');
    const events = agentEvents[run.id] || [];
    const prompt = `Summarize this agent monitoring log from run ${run.id} on ${run.cluster}:\n\n${
      events.slice(0, 30).map(e => `[${e.time}] ${e.title}: ${e.body}`).join('\n')
    }\n\nHighlight key events, escalations, and the monitoring timeline. What did the agent detect?`;
    let text = '';
    await llm([{ role: 'user', content: prompt }], M.monitoring, chunk => { text += chunk; setReplayHtml(text); });
    setCacheItem(key, text);
    setReplayLoading(false);
  };

  if (selectableRuns.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🧠</div>
        <div className="empty-state-title">No Run Selected</div>
        <div className="empty-state-text">Execute a test run and come back here for AI-powered insights, root cause analysis, and remediation guidance.</div>
      </div>
    );
  }

  return (
    <div className="dashboard-grid">
      {/* Run selector */}
      <div className="insights-full">
        <div className="card">
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px' }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text3)', whiteSpace: 'nowrap' }}>Analysing run:</span>
            <select
              className="form-select"
              style={{ flex: 1, maxWidth: 560 }}
              value={selectedRunId}
              onChange={e => setSelectedRunId(e.target.value)}
            >
              {selectableRuns.map(r => (
                <option key={r.id} value={r.id}>
                  {r.id} — {r.cluster} · {r.env} · {r.overallRate}% pass
                  {r.status === 'failed' ? ' ⚠ Failed' : ''}
                </option>
              ))}
            </select>
            {run && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: 'var(--text3)' }}>{run.location}</span>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 12,
                  background: run.overallRate >= 90 ? 'rgba(34,197,94,0.15)' : run.overallRate >= 70 ? 'rgba(234,179,8,0.15)' : 'rgba(239,68,68,0.15)',
                  color: run.overallRate >= 90 ? '#16a34a' : run.overallRate >= 70 ? '#ca8a04' : '#dc2626',
                }}>
                  {run.overallRate}% pass
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Go/No-Go Panel - Full Width */}
      <div className="insights-full">
        <GoNoGoPanel run={run} />
      </div>

      {/* Two column layout */}
      <div className="insights-layout">
        {/* Failure Analysis */}
        <AiSection
          title="Failure Analyzer"
          model={M.failAnalysis}
          icon="🔍"
          onRun={runFailAnalysis}
          content={failHtml}
          loading={failLoading}
        />

        {/* Remediation */}
        <AiSection
          title="Remediation Roadmap"
          model={M.remediation}
          icon="🛠"
          onRun={runRemediation}
          content={remHtml}
          loading={remLoading}
        />

        {/* Agent Log Replay */}
        <AiSection
          title="Agent Log Replay"
          model={M.monitoring}
          icon="📼"
          onRun={runReplay}
          content={replayHtml}
          loading={replayLoading}
        >
          <div style={{ marginBottom: 12 }}>
            <span style={{ fontSize: 12, color: 'var(--text2)' }}>
              {(agentEvents[run.id] || []).length} agent events recorded during this run
            </span>
          </div>
        </AiSection>

        {/* Chat - Full Width */}
        <div style={{ gridColumn: '1 / -1' }}>
          <ChatPanel run={run} />
        </div>
      </div>
    </div>
  );
}
