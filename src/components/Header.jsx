import React, { useState } from 'react';
import useStore from '../store/useStore.js';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'execute', label: 'Execute', icon: '▶' },
  { id: 'monitor', label: 'Monitor', icon: '👁' },
  { id: 'insights', label: 'AI Insights', icon: '🧠' },
  { id: 'history', label: 'History', icon: '📋' },
  { id: 'compare', label: 'Compare', icon: '⚖' },
];

export default function Header() {
  const { currentView, setView, isDark, toggleTheme, apiKey, setApiKey, runs } = useStore();
  const [showKey, setShowKey] = useState(false);

  const activeRuns = runs.filter(r => r.status === 'running');
  const agentCount = activeRuns.length > 0 ? 3 : 0;

  return (
    <header className="header">
      <div className="header-logo">
        <div className="header-logo-icon">🔬</div>
        <div>
          <div className="header-logo-text">TestOps</div>
          <div className="header-logo-sub">Production Readiness</div>
        </div>
      </div>

      <nav className="header-nav">
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            className={`nav-btn ${currentView === item.id ? 'active' : ''}`}
            onClick={() => setView(item.id)}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="header-right">
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
            className="btn-ghost"
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
