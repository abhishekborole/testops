import React, { useState } from 'react';
import useStore from '../store/useStore.js';

export default function TopBar() {
  const { isDark, toggleTheme, apiKey, setApiKey, runs } = useStore();
  const [showKey, setShowKey] = useState(false);

  const activeRuns = runs.filter(r => r.status === 'running');
  const agentCount = activeRuns.length > 0 ? 3 : 0;

  return (
    <header className="topbar">
      <div className="topbar-logo">
        <div className="topbar-logo-icon">T</div>
        <div>
          <div className="topbar-logo-text">TestOPS</div>
          <div className="topbar-logo-sub">Production Readiness</div>
        </div>
      </div>

      <div className="topbar-right">
        <div className="api-key-wrap">
          <span style={{ fontSize: 11, color: 'var(--text3)' }}>🔑</span>
          <input
            className="api-key-input"
            type={showKey ? 'text' : 'password'}
            placeholder="sk-ant-api..."
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            title="Anthropic API Key"
          />
          <button
            style={{ padding: '4px 6px', fontSize: 11, borderRadius: 4, border: 'none', cursor: 'pointer', background: 'transparent', color: 'var(--text3)' }}
            onClick={() => setShowKey(v => !v)}
          >
            {showKey ? '🙈' : '👁'}
          </button>
        </div>

        {activeRuns.length > 0 && (
          <div className="running-badge">
            <div className="pulse-dot" />
            {activeRuns.length} Running
          </div>
        )}

        {agentCount > 0 && (
          <div className="agent-badge">
            🤖 {agentCount} Agents
          </div>
        )}

        <button className="theme-btn" onClick={toggleTheme} title="Toggle theme">
          {isDark ? '☀️' : '🌙'}
        </button>

        <div className="user-badge">
          <div className="user-avatar">AB</div>
          <span>abhishekborole</span>
        </div>
      </div>
    </header>
  );
}
