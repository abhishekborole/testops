import React from 'react';
import useStore from '../store/useStore.js';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
    </svg>
  )},
  { id: 'execute', label: 'Execute', icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="5 3 19 12 5 21 5 3"/>
    </svg>
  )},
  { id: 'monitor', label: 'Monitor', icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  )},
  { id: 'insights', label: 'AI Insights', icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  )},
  { id: 'history', label: 'History', icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="12 8 12 12 14 14"/><path d="M3.05 11a9 9 0 1 1 .5 4m-.5 5v-5h5"/>
    </svg>
  )},
  { id: 'compare', label: 'Compare', icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  )},
];

export default function TabBar() {
  const { currentView, setView, runs } = useStore();
  const activeRuns = runs.filter(r => r.status === 'running');
  const insightsBadge = runs.filter(r => r.status !== 'running').length > 0;

  return (
    <div className="tabbar">
      {TABS.map(tab => {
        const isActive = currentView === tab.id;
        return (
          <button
            key={tab.id}
            className={`tab-btn${isActive ? ' active' : ''}`}
            onClick={() => setView(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span>{tab.label}</span>
            {tab.id === 'monitor' && activeRuns.length > 0 && (
              <span className="tab-badge tab-badge-red">{activeRuns.length}</span>
            )}
            {tab.id === 'insights' && insightsBadge && (
              <span className="tab-badge tab-badge-purple">AI</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
