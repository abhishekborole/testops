# TestOPS Production Readiness Portal

## Stack
- React 18 + Vite 5
- Zustand 4 (global state)
- Chart.js 4 + react-chartjs-2 (trend line, donut charts)
- Claude API — streaming, called directly from the browser

## Dev Commands
```bash
export PATH="/d/Program Files/nodejs:$PATH"
npm run dev      # http://localhost:5173
npm run build    # output to dist/
npm run preview  # preview production build
```

## Project Structure
```
src/
  App.jsx                  # View router, theme init
  main.jsx                 # React root
  index.css                # All styles (CSS custom property theme tokens)
  data/
    constants.js           # LOCS, CATS, ALL_TESTS, VM, M, ML model routing
  store/
    useStore.js            # Zustand store — all global state + actions
  utils/
    llm.js                 # Streaming fetch to Anthropic API
    helpers.js             # calcStats, mkId, fakeLog, esc, md renderer
  components/
    Header.jsx             # Nav tabs, API key input, theme toggle, indicators
  views/
    Dashboard.jsx          # KPIs, charts, heatmap, activity feed
    Execute.jsx            # Config form, scope chips, simulation + monitoring agent
    Monitor.jsx            # Live test table, category cards, agent event feed
    Insights.jsx           # Go/No-Go (Opus), failure analysis, remediation, chat
    History.jsx            # Run history with filters + compare toggle
    Compare.jsx            # Cross-run delta table + AI comparison
```

## Global State (useStore.js)
Key fields: `runs`, `activeId`, `comparing`, `selEnvVal`, `mFilter`, `openLogs`, `aiCache`, `chatHist`, `agentEvents`, `isDark`, `apiKey`

## AI Agents & Model Routing (src/data/constants.js)
| Agent | Model |
|---|---|
| Pre-flight Advisor | claude-haiku-4-5-20251001 |
| Monitoring Agent | claude-haiku-4-5-20251001 |
| Log Summarizer | claude-haiku-4-5-20251001 |
| Failure Analyzer | claude-sonnet-4-6 |
| Remediation Roadmap | claude-sonnet-4-6 |
| Compare Insights | claude-sonnet-4-6 |
| Pattern Analysis | claude-sonnet-4-6 |
| Go/No-Go Decision | claude-opus-4-6 |
| SRE Chat | claude-sonnet-4-6 |

## Key Conventions
- All AI calls go through `src/utils/llm.js` — never fetch Anthropic API directly
- API key is stored in Zustand (`apiKey`) and entered via the Header input field
- Simulation: 88% pass rate, 380–1130ms per test, sequential execution
- Monitoring agent polls every 600ms via `setInterval`
- Theme: toggle `data-theme="dark"` on `document.documentElement`
- CSS uses custom properties (`--bg-card`, `--text-primary`, etc.) for theming
- Dark mode overrides are in `index.css` under `[data-theme="dark"]`

## Test Categories (11 total in CATS)
cluster-health, network, storage, vm-ops, vm-mig, security, monitoring, backup, integration, compliance, self-service

## Locations & Clusters
- DC-MUM-01: Mumbai DC (3 clusters)
- DC-DEL-01: Delhi DC (2 clusters)
- DC-BLR-01: Bangalore DC (3 clusters)
- DC-HYD-01: Hyderabad DC (2 clusters)
