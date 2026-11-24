# CloudPilot Frontend

Web dashboard and interactive simulation interface for CloudPilot ML-based CPU resource allocation research.

Built with React 18, Vite, TypeScript strict mode, React Router 6, and custom lightweight CSS (light/dark mode via `prefers-color-scheme`).

## Pages

- `/`: Overview of CloudPilot, methodology, and prominent simulation disclaimer banner.
- `/study`: Static benchmark study findings from 10 seeded workloads (200 services, 4,032 steps per seed). Reports headline verdicts (H1, H2, H3), per-seed comparison table, median metrics, generator over-provisioning note, and plain-English analysis of the negative result. Loaded statically from bundled JSON without API calls.
- `/simulate`: Interactive simulator for running parameterized synthetic workloads. Fetches bounds from `/api/limits`, provides Small and Medium presets, validates inputs, displays live execution timer with cancellation support (`AbortController`), and presents performance metrics alongside an SVG allocation chart.
- `/upload`: Workload CSV upload form (drag-and-drop or file selector) with client-side 5 MB file size verification and schema guidance.
- `/history`: Visitor simulation history from `/api/runs` with pagination, detail drawer, and deletion confirmation modal.
- `*`: Accessible 404 page with return link.

## Security Architecture & Vercel Proxy

The client application never contains backend credentials or contacts the FastAPI backend directly. All network requests use same-origin `/api/...` endpoints serviced by a strict Vercel Serverless Function proxy (`api/[...path].ts`).

### Proxy Protection Guarantees

1. **Route Allowlist**: Only permits `GET /api/limits`, `GET /api/methods`, `POST /api/simulate`, `POST /api/simulate/csv`, `GET /api/runs`, `GET /api/runs/:uuid`, and `DELETE /api/runs/:uuid`. Any other path returns 404.
2. **Path Sanitization**: Rejects paths containing `..`, `%2f`, `%5c`, `\\`, and double slashes. Query parameters are strictly filtered (only integer `limit` and `offset` permitted on `GET /api/runs`).
3. **Credential Isolation**: Strips incoming `X-API-Key`, `Authorization`, `X-Visitor-Id`, `Host`, and `Cookie` headers from client requests. Injects server-side secret `X-API-Key` upstream.
4. **Visitor Scoping**: Reads the HttpOnly `cp_vid` cookie. If absent or invalid UUID4, generates a new UUID4 and sets `Set-Cookie: cp_vid=<uuid>; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000` on the response. Injects `X-Visitor-Id` upstream for visitor-isolated rate limiting and history.
5. **CSRF & Same-Origin**: Enforces matching `Origin` header on state-modifying `POST` and `DELETE` requests.
6. **Payload Guard**: Limits requests to 5.5 MB and enforces `application/json` or `multipart/form-data` content types.
7. **Timeout Protection**: Aborts upstream backend calls after 55 seconds (returning 504 Gateway Timeout) to prevent stalled executions.
8. **Error Masking**: Maps backend errors into generic HTTP statuses (502 Bad Gateway) without exposing upstream URLs, stack traces, or internal infrastructure details.

### Visitor Scoping Flow

```text
Browser Client                    Vercel Proxy                  FastAPI Backend
      │                                │                                │
      │  GET /api/runs                 │                                │
      │  Cookie: cp_vid=<uuid>         │                                │
      ├───────────────────────────────>│                                │
      │                                │ 1. Verify route allowlist       │
      │                                │ 2. Verify cp_vid is UUID4       │
      │                                │ 3. Strip client headers        │
      │                                │ 4. Inject X-API-Key (server)   │
      │                                │ 5. Inject X-Visitor-Id (<uuid>)│
      │                                ├───────────────────────────────>│
      │                                │                                │ Hash key + visitor_id
      │                                │                                │ Scope DB runs to visitor
      │                                │                                │ Apply visitor rate limit
      │                                │                                │
      │                                │<───────────────────────────────┤
      │                                │ 6. Strip internal headers      │
      │                                │ 7. Set Cache-Control: no-store │
      │<───────────────────────────────┤                                │
      │  Runs scoped to visitor        │                                │
```

## Environment Variables

These variables are defined in the Vercel project settings (or serverless environment). They are **never** injected into the client bundle:

| Variable | Required | Description |
| :--- | :--- | :--- |
| `BACKEND_URL` | Yes | Target FastAPI backend URL. Must use `https://` in production (e.g. `https://cloudpilot-backend.onrender.com`). `http://localhost` is permitted in local development. |
| `CLOUDPILOT_API_KEY` | Yes | Secret API key matching the backend's configured key for authenticating proxy requests. |

## Development Setup

```bash
cd frontend

# Install exact pinned dependencies
npm ci

# Run development server with Vite local proxy (routes /api to http://localhost:8000)
npm run dev

# Run ESLint linter
npm run lint

# Run TypeScript type check
npx tsc --noEmit

# Run Vitest unit tests
npm run test

# Build production bundle to dist/
npm run build

# Preview production build locally
npm run preview
```
