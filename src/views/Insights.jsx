import React, { useState, useRef, useEffect } from 'react';
import useStore from '../store/useStore.js';
import { CATS, M, ML, VM } from '../data/constants.js';
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

function GoNoGoPanel({ run }) {
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);
  const { aiCache, setCacheItem } = useStore();

  const runGoNoGo = async () => {
    if (!run) return;
    const key = `gong-${run.id}`;
    if (aiCache[key]) { setResult(aiCache[key]); return; }
    setLoading(true);
    setResult('');

    const catSummary = run.categories?.map(c => {
      const s = calcStats(c.tests);
      const catDef = CATS.find(x => x.id === c.id);
      return `${c.name} (${catDef?.critical ? 'CRITICAL' : 'non-critical'}): ${s.passed}/${s.total} passed (${s.rate}%)`;
    }).join('\n') || '';

    const prompt = `You are assessing production readiness for an OpenShift cluster.
Run ID: ${run.id}
Cluster: ${run.cluster}
Environment: ${run.env}
Overall pass rate: ${run.overallRate}%
Verdict: ${run.verdict}

Category results:
${catSummary}

Provide a definitive GO / NO-GO decision with:
1. DECISION (GO / CONDITIONAL GO / NO-GO) in bold
2. Key reasons (3-5 bullet points)
3. Any critical blockers
4. Risk assessment
Be authoritative and specific.`;

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
        <button className="btn btn-sm btn-secondary" onClick={runGoNoGo} disabled={loading}>
          {loading ? <><span className="spinner" /> Analyzing...</> : '▶ Assess'}
        </button>
      </div>
      <div className="card-body">
        <div className="verdict-panel" style={{
          borderColor: v.border,
          background: v.bg
        }}>
          <div className="verdict-icon-large">{v.icon}</div>
          <div className="verdict-label-large" style={{ color: v.color }}>{v.label}</div>
          <div className="verdict-sub">Run {run.id} · {run.cluster} · {run.overallRate}% pass rate</div>
          {result && (
            <div className="gong-ai-output" dangerouslySetInnerHTML={{ __html: md(result) }} />
          )}
          {loading && (
            <div className="ai-placeholder" style={{ marginTop: 16, textAlign: 'left' }}>
              <div className="ai-placeholder-line" style={{ width: '85%' }} />
              <div className="ai-placeholder-line" style={{ width: '70%' }} />
              <div className="ai-placeholder-line" style={{ width: '90%' }} />
            </div>
          )}
          {!result && !loading && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text3)', fontStyle: 'italic' }}>
              Click "Assess" to get Opus's deep reasoning Go/No-Go verdict
            </div>
          )}
        </div>
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
  const run = runs.find(r => r.id === activeId) || runs.find(r => r.status === 'completed' || r.status === 'failed');

  const [failHtml, setFailHtml] = useState('');
  const [failLoading, setFailLoading] = useState(false);
  const [remHtml, setRemHtml] = useState('');
  const [remLoading, setRemLoading] = useState(false);
  const [replayHtml, setReplayHtml] = useState('');
  const [replayLoading, setReplayLoading] = useState(false);

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

  if (!run) {
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
