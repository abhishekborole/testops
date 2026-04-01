import React, { useEffect } from 'react';
import useStore from './store/useStore.js';
import TopBar from './components/TopBar.jsx';
import Sidebar from './components/Sidebar.jsx';
import TabBar from './components/TabBar.jsx';
import Dashboard from './views/Dashboard.jsx';
import Execute from './views/Execute.jsx';
import Monitor from './views/Monitor.jsx';
import Insights from './views/Insights.jsx';
import History from './views/History.jsx';
import Compare from './views/Compare.jsx';

const VIEW_MAP = {
  dashboard: Dashboard,
  execute: Execute,
  monitor: Monitor,
  insights: Insights,
  history: History,
  compare: Compare,
};

export default function App() {
  const { currentView, isDark } = useStore();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  }, [isDark]);

  const ViewComponent = VIEW_MAP[currentView] || Dashboard;

  return (
    <div className="app-root">
      <TopBar />
      <div className="app-body">
        <Sidebar />
        <div className="main-area">
          <TabBar />
          <div className="view-content">
            <ViewComponent />
          </div>
        </div>
      </div>
    </div>
  );
}
