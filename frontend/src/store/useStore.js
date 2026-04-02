import { create } from 'zustand';

const useStore = create((set, get) => ({
  // State
  runs: [],
  activeId: null,
  comparing: [],
  selEnvVal: '',
  mFilter: "all",
  openLogs: new Set(),
  aiCache: {},
  chatHist: {},
  agentEvents: {},
  isDark: false,
  apiKey: '',
  currentView: 'dashboard',

  // Reference data — populated from DB only, never from local constants
  locsMap: {},
  catsArr: [],
  envsArr: [],
  refDataLoaded: false,

  // Actions
  setView: (view) => set({ currentView: view }),

  setApiKey: (key) => {
    window.__testops_api_key = key;
    set({ apiKey: key });
  },

  loadRefData: async () => {
    try {
      const [locsRes, catsRes, envsRes] = await Promise.all([
        fetch('/api/v1/ref/locations/map'),
        fetch('/api/v1/ref/categories/flat'),
        fetch('/api/v1/ref/envs'),
      ]);
      if (!locsRes.ok || !catsRes.ok || !envsRes.ok) return;
      const locsMap = await locsRes.json();
      const catsArr = await catsRes.json();
      const envsArr = await envsRes.json();
      set({
        locsMap,
        catsArr,
        envsArr,
        selEnvVal: envsArr[0] ?? '',
        refDataLoaded: true,
      });
    } catch (err) {
      console.error('Failed to load reference data from DB:', err);
    }
  },

  loadRuns: async () => {
    try {
      const res = await fetch('/api/v1/runs/?limit=500');
      if (!res.ok) return;
      const { items } = await res.json();
      // Map DB snake_case fields to the camelCase shape the frontend uses
      const runs = items.map(r => ({
        id: r.id,
        status: r.status,
        env: r.env,
        location: r.location,
        cluster: r.cluster,
        categories: r.categories,
        overallRate: r.overall_rate,
        verdict: r.verdict,
        startedAt: r.started_at,
        completedAt: r.completed_at,
      }));
      set({ runs });
    } catch (err) {
      console.error('Failed to load runs from DB:', err);
    }
  },

  addRun: (run) => set(state => {
    const exists = state.runs.some(r => r.id === run.id);
    return {
      runs: exists ? state.runs : [run, ...state.runs],
      activeId: run.id,
    };
  }),

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
