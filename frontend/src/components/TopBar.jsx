import React from 'react';
import useStore from '../store/useStore.js';

export default function TopBar() {
  const { isDark, toggleTheme, runs } = useStore();

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
