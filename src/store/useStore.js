import { create } from 'zustand';

const useStore = create((set, get) => ({
  // State
  runs: [],
  activeId: null,
  comparing: [],
  selEnvVal: "Production",
  mFilter: "all",
  openLogs: new Set(),
  aiCache: {},
  chatHist: {},
  agentEvents: {},
  isDark: false,
  apiKey: '',
  currentView: 'dashboard',

  // Actions
  setView: (view) => set({ currentView: view }),

  setApiKey: (key) => {
    window.__testops_api_key = key;
    set({ apiKey: key });
  },

  addRun: (run) => set(state => ({
    runs: [run, ...state.runs],
    activeId: run.id
  })),

  updateRun: (id, patch) => set(state => ({
    runs: state.runs.map(r => r.id === id ? { ...r, ...patch } : r)
  })),

  updateTest: (runId, catId, testIdx, patch) => set(state => ({
    runs: state.runs.map(r => {
      if (r.id !== runId) return r;
      return {
        ...r,
        categories: r.categories.map(c => {
          if (c.id !== catId) return c;
          return {
            ...c,
            tests: c.tests.map((t, i) => i === testIdx ? { ...t, ...patch } : t)
          };
        })
      };
    })
  })),

  setActiveId: (id) => set({ activeId: id }),

  toggleCompare: (id) => set(state => {
    const c = state.comparing;
    if (c.includes(id)) return { comparing: c.filter(x => x !== id) };
    if (c.length >= 2) return { comparing: [c[1], id] };
    return { comparing: [...c, id] };
  }),

  setMFilter: (f) => set({ mFilter: f }),

  toggleLog: (key) => set(state => {
    const s = new Set(state.openLogs);
    if (s.has(key)) s.delete(key);
    else s.add(key);
    return { openLogs: s };
  }),

  toggleTheme: () => set(state => {
    const isDark = !state.isDark;
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    return { isDark };
  }),

  pushEvent: (runId, event) => set(state => ({
    agentEvents: {
      ...state.agentEvents,
      [runId]: [...(state.agentEvents[runId] || []), event]
    }
  })),

  setCacheItem: (key, value) => set(state => ({
    aiCache: { ...state.aiCache, [key]: value }
  })),

  setChatHist: (runId, messages) => set(state => ({
    chatHist: { ...state.chatHist, [runId]: messages }
  })),

  appendChatMsg: (runId, msg) => set(state => ({
    chatHist: {
      ...state.chatHist,
      [runId]: [...(state.chatHist[runId] || []), msg]
    }
  })),

  setSelEnv: (env) => set({ selEnvVal: env }),
}));

export default useStore;
