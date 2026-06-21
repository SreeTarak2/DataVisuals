# Signal Frontend

React-based UI for the Signal AI analytics platform.

## Stack

| Component | Technology |
|-----------|-----------|
| Framework | React 19 |
| Bundler | Vite 7 |
| Styling | Tailwind CSS 4 + CSS Modules |
| State Management | Zustand |
| Routing | React Router v7 |
| Charts | Plotly.js (react-plotly.js) |
| Animations | Framer Motion |
| HTTP Client | Axios |
| UI Components | Radix UI (Dialog, Dropdown, Toast, Tooltip, etc.) |
| Icons | Lucide React |

## Setup

```bash
cd version2/frontend
pnpm install
pnpm dev
```

The dev server runs at `http://localhost:3000` and proxies `/api` requests to `http://localhost:8000`.

### Scripts

| Script | Description |
|--------|-------------|
| `pnpm dev` | Start dev server with HMR |
| `pnpm build` | Production build |
| `pnpm preview` | Preview production build |
| `pnpm lint` | Run ESLint |

## Project Structure

```
frontend/
├── index.html                # HTML entry point with SEO meta tags
├── vite.config.js            # Vite config with proxy and aliases
├── package.json              # Dependencies
│
└── src/
    ├── main.jsx              # React root mount
    ├── App.jsx               # Router setup with lazy-loaded routes
    │
    ├── pages/                # Route-level page components
    │   ├── Landing/          # Public landing page (hero, features, pricing)
    │   ├── Dashboard/        # Main dashboard with KPIs, charts, layout
    │   ├── Chat/             # AI chat interface
    │   ├── insights/         # Deep analysis and insight reports
    │   ├── ChartsStudio/     # Chart creation and customization
    │   ├── Datasets/         # Dataset management
    │   ├── connectors/       # External DB connection setup
    │   ├── settings/         # User settings
    │   ├── auth/             # Google OAuth callback
    │   └── DataProfile/      # Dataset profiling view
    │
    ├── components/           # Reusable UI components
    │   ├── ui/               # Design system primitives (Button, Card, Dialog, etc.)
    │   ├── features/         # Feature-specific components
    │   │   ├── chat/         # Chat panel, streaming, loading states
    │   │   ├── charts/       # Chart canvas, encoding bar, insights
    │   │   ├── datasets/     # Upload modals, processing states
    │   │   ├── analysis/     # Anomaly feed, correlation, pivot tables
    │   │   └── databases/    # Connection UI, relationship graphs
    │   ├── layout/           # Dashboard layout, sidebar, header
    │   ├── landing/          # Landing page sections
    │   └── common/           # Error boundary, theme toggle, logo
    │
    ├── store/                # Zustand state stores
    │   ├── authStore.jsx     # Authentication state
    │   ├── chatStore.jsx     # Chat messages and streaming
    │   ├── datasetStore.jsx  # Dataset list and selection
    │   ├── themeStore.jsx    # Theme (dark/light)
    │   └── sidebarStore.jsx  # Sidebar state
    │
    ├── hooks/                # Custom React hooks
    │   ├── useWebSocket.js   # WebSocket with auto-reconnect
    │   ├── useDashboardData.js
    │   ├── useChartTheme.js
    │   └── use-toast.jsx
    │
    ├── services/             # API client (Axios with interceptors)
    ├── contexts/             # React contexts
    ├── assets/styles/        # Global CSS and component styles
    └── lib/                  # Utility functions
```

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Landing | Marketing site with hero, features, pricing, FAQ |
| `/login` | Login | Authentication |
| `/register` | Register | User registration |
| `/auth/google/callback` | Google Callback | OAuth redirect handler |
| `/app/dashboard` | Dashboard | Main analytics dashboard |
| `/app/workspace` | Datasets | Dataset management |
| `/app/chat` | Chat | AI chat interface |
| `/app/charts` | Charts Studio | Chart creation |
| `/app/analysis` | Insights | Deep analysis reports |
| `/app/connectors` | Connectors | External DB connections |
| `/app/settings` | Settings | User preferences |
| `/app/datasets/:id/profile` | Data Profile | Dataset profiling |
| `/app/datasets/:id/understanding` | Understanding Report | Dataset analysis |

## Features

- **Dashboard** — AI-generated KPI cards with anomaly detection, trend analysis, period-over-period comparison; drag-and-drop layout with priority management
- **AI Chat** — Streaming chat over datasets with follow-up suggestions, chart generation, and technical details
- **Charts Studio** — Chart recommendations, encoding configuration, multi-series overlays
- **Insights** — Executive summaries, trend analysis, anomaly spotlight, segment analysis, correlation explorer
- **Data Profile** — Column-level statistics, quality metrics, domain classification
- **Understanding Report** — Entity discovery, primary object identification, relationship detection
- **Connectors** — Connect external databases (PostgreSQL, MySQL, MongoDB) for querying

## Styling

Uses Tailwind CSS 4 with a custom dark theme. Key design tokens:

- **Background:** `slate-950` (almost black)
- **Accent:** Blue-500 gradients with glass morphism effects
- **Typography:** Inter (body), IBM Plex Mono (code), Satoshi (headings)
- **Components:** Glass cards, neon buttons, tactile interactions, particle backgrounds
