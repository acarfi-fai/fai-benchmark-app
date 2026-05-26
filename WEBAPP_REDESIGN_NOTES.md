# FusionAI Benchmark App Redesign Notes

This document records product, architecture, and design decisions for the rewrite of the benchmark results web app.

## Context

- Existing prototype lives in `fai-benchmark-app/`.
- Current app reads Inspect AI evaluation logs from Azure Blob Storage through Inspect AI log APIs.
- A custom viewer was created because deploying Inspect AI View directly on Azure App Service was blocked by path encoding / Azure path normalization conflicts.
- Desired rewrite:
  - Frontend: Angular
  - Styling: plain SCSS/CSS, no heavy component framework by default
  - Backend: FastAPI
  - Deployment target: Azure

## Initial Architecture Direction

### Frontend

**Decision:** Use Angular for the client application.

**Rationale:**
- Good fit for a structured dashboard-style application with routing, typed services, forms, and reusable UI components.
- Strong TypeScript support helps keep API contracts explicit.
- Angular router maps naturally to a log-list page and run-detail pages.
- Angular can be built as static assets and served either separately or by the FastAPI backend.

**Implications:**
- We should design a clear API boundary rather than embedding backend-rendered HTML.
- We should define frontend models that mirror normalized backend DTOs, not raw Inspect AI objects everywhere.
- We should avoid overbuilding early: start with plain SCSS/CSS and small local components.

### Backend

**Decision:** Use FastAPI for the API backend.

**Rationale:**
- Python integrates directly with Inspect AI APIs such as `list_eval_logs`, `read_eval_log`, and `read_eval_log_samples`.
- FastAPI provides OpenAPI docs, validation, typed response models, and straightforward async support.
- It is suitable for Azure App Service or container deployment.

**Implications:**
- Backend should hide Azure Blob / `abfs://` paths from the browser.
- Public route parameters should use safe opaque IDs, not raw paths.
- Backend should normalize Inspect AI data into stable response schemas for the frontend.

### Styling

**Decision:** Use plain SCSS/CSS initially.

**Rationale:**
- Keeps the app visually customizable and avoids generic component-library appearance.
- Suitable if the visual identity should be bespoke.
- Avoids committing to Material, Bootstrap, etc. before the product direction is clear.

**Implications:**
- We need a small design system: colors, typography, spacing, table/card patterns, status badges, charts, empty/error/loading states.
- Accessibility and responsive behavior must be handled explicitly.

## Deployment Decision

**Decision:** Single deployed web app on Azure App Service with container.

The Azure deployment should contain both:

- FastAPI backend
- Angular production build served as static files by FastAPI

### Rationale

- Simpler deployment and operations.
- No CORS complexity.
- One authentication/authorization boundary when auth is added.
- Frontend and backend versions remain in sync.
- Suitable for the current product stage.

### Implications

- API routes should live under `/api/...`.
- Angular owns browser routes such as `/`, `/runs`, and `/runs/:id`.
- FastAPI should serve Angular static assets and provide a fallback to `index.html` for frontend routes.
- Docker/build pipeline needs both Node/Angular build steps and Python/FastAPI runtime setup.
- This can be split later only if independent frontend/backend scaling or CDN hosting becomes necessary.

## Authentication Decision

**Decision:** Use Azure App Service Authentication with Microsoft Entra ID.

Rationale:

- Keeps authentication outside the application code for v1.
- Azure can block unauthenticated requests before they reach FastAPI.
- Avoids building custom login/session logic.
- Provides a natural path for organization-managed access control.

Implementation note:

- In the simplest v1 setup, FastAPI and Angular do not need to implement login flows.
- Azure App Service Authentication should be configured to require authentication for all requests.
- Later, if the UI needs to display the signed-in user or enforce app-specific roles, the backend can read Azure-provided identity headers.

## Product Name

**Decision:** Use **FusionAI Eval Console**.

## Proposed Information Architecture

### Page 1: Runs / Logs List

Initial route: `/runs` or `/`

Purpose: show all available Inspect AI logs / benchmark runs.

Candidate data:
- Run ID
- File name
- Task / task ID
- Model
- Status
- Started / completed time
- Duration
- Primary metric summary
- Number of samples, if available cheaply
- Tags / metadata
- File size / modified time

Candidate interactions:
- Search by task, model, filename, tag
- Filter by status, task, model, date range
- Sort by time, status, task, metric
- Click row/card to open run details
- Refresh logs

Decision: v1 uses a flat table; no grouping.

Selected v1 columns:
- Status
- Task
- Model
- Started/completed time
- Duration
- Primary metric
- Sample count, if cheaply available
- Tags
- File name

### Page 2: Run Detail

Route: `/runs/:id`

Purpose: show full benchmark run details.

Candidate sections:
- Header summary: task, model, status, time, duration, primary score
- Scores / metrics overview
- Eval configuration and metadata
- Samples table/list
- Sample detail drawer or sub-page
- Errors and warnings
- Raw JSON view for debugging

Decision: raw JSON should be hidden by default but accessible, e.g. behind a Debug / Raw JSON tab or disclosure.

### Page 3: Sample Detail

Possible route: `/runs/:id/samples/:sampleId` or inline drawer.

Candidate data:
- Input / prompt
- Target
- Model output / completion
- Scores
- Metadata
- Error, if any
- Messages / events / transcript if available from Inspect log

Decision: v1 sample layout should use a two-column comparison:
- Left: input + target
- Right: output + scores

Prioritize side-by-side comparison first, debugging second, raw JSON third.

## Initial API Shape

Candidate endpoints:

- `GET /api/health`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/samples?limit=&offset=`
- `GET /api/runs/{run_id}/samples/{sample_id}`
- `GET /api/runs/{run_id}/raw` for debug/admin use

Decision: raw log access should be hidden by default in the UI and exposed through a small `View raw JSON` disclosure/button in the metadata/debug area.

## Brand Inputs

### Logo

Logo asset is available at:

- `fai-benchmark-app/design-assets/logo.png`

Once the Angular frontend exists, copy or move it to:

- `fai-benchmark-app/frontend/src/assets/brand/logo.png`

The app should reference the Angular asset path rather than loading files from outside the frontend build.

### Brand Color

Company color:

- RGB: `rgb(0, 0, 200)`
- Hex: `#0000c8`

Initial use:

- primary actions
- active navigation state
- selected filters
- chart accent color
- focus rings, with accessible contrast handling

### Desired Product Feel

The app should feel **technical**: precise, structured, data-oriented, and suitable for benchmark inspection/debugging.

## Design Inputs Needed

To avoid a generic dashboard, collect examples and constraints before finalizing the visual direction.

Useful inputs:
- 3–5 websites or product screenshots whose design you like.
- For each reference, note what you like specifically: layout, density, typography, colors, navigation, tables, cards, charts, dark/light mode, etc.
- 1–3 examples you dislike, with reasons.
- Existing FusionAI brand assets: logo, colors, fonts, icon style, marketing site, slide deck, or brand guidelines.
- Primary users: internal researchers, customers, executives, engineers, auditors, etc.
- Usage context: quick daily monitoring, deep debugging, report generation, demo mode, compliance review.
- Desired tone: technical, premium, minimal, enterprise, research-lab, playful, etc.
- Data density preference: compact table-heavy UI vs. spacious card-based UI.
- Accessibility requirements and dark mode preference.

## Visual Direction Decisions

### Overall Feel

- Technical, precise, structured, and data-oriented.
- Mostly neutral technical tool with small FusionAI branding.
- Avoid an overly crowded enterprise-portal feeling.

### Density

**Decision:** Medium density.

Reference: closer to Linear spacing than Azure Portal crowdedness.

### Navigation

**Decision:** Minimal header plus page-level tabs.

Rationale:
- The app initially has few primary areas.
- Avoids unnecessary sidebar complexity.
- Keeps focus on benchmark data.

### Run List

**Decision:** Table-first.

The landing page should prioritize a sortable/filterable table of runs rather than cards.

Optional summary cards can be added later only if they provide clear value.

### Color Mood

**Decision:** Light technical UI.

- White / light gray base.
- FusionAI blue `#0000c8` as restrained accent.
- Avoid excessive saturated blue.
- Use semantic colors for statuses: success, failed, running, warning.

### Typography

Preference: LangSmith-like font feel.

Implication:
- Use a clean technical sans-serif.
- Candidate stack: `Inter`, `ui-sans-serif`, `system-ui`, `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, `sans-serif`.
- Consider a monospace font for JSON, IDs, model names, and code-like fields.

### Detail Page Priority

Sample/run detail should prioritize:

1. Side-by-side comparison of input / target / output / scores.
2. Debugging raw model behavior.
3. Optional raw JSON transparency.

### Explicit Negative Reference

Avoid Azure Portal-style crowdedness and excessive navigation chrome.

## Open Questions

### Product / UX

1. Who is the primary user of this viewer?
2. Is the main goal monitoring many runs, debugging individual samples, or presenting benchmark results?
3. Should the default landing page be the latest runs list, a dashboard summary, or a specific project/task view?
4. How many logs/runs should the app handle comfortably: hundreds, thousands, more?
5. Are logs grouped by project, dataset, task, model, date, or Azure container/prefix?
6. Do users need authentication/authorization?
7. Should users be able to compare two or more runs?
8. Should users export results as CSV/JSON/PDF?
9. Should users be able to add notes, labels, or review status to runs/samples?
10. Should the UI include raw JSON/debug views for all users?

### Data / Backend

1. What exact Inspect AI log fields are most important to expose?
2. Are all logs produced by the same benchmark recipes, or are schemas heterogeneous?
3. Are samples large enough to require pagination, virtualization, or lazy loading?
4. Should the backend cache run headers or sample summaries?
5. Should Azure Blob access happen directly through Inspect AI only, or do we also need direct Azure SDK access?
6. What Azure deployment model is preferred: App Service container, Azure Container Apps, Static Web Apps + API, or another setup?
7. What telemetry/logging is required: Application Insights, structured logs, user analytics?

### Visual Design

1. Should we support light mode only, dark mode only, or both?
2. Should the UI feel more like Inspect View, Azure Portal, GitHub, Linear, Grafana, Vercel, or something else?
3. Is there a FusionAI visual identity to follow?
4. Are charts needed in v1? If yes, which types?
5. Should run list be table-first or card-first?

## Routing Decisions

Frontend routes:

- `/` redirects to `/runs`
- `/runs` shows the run list
- `/runs/:runId` shows run detail

Sample detail should be shown inline through a drawer/panel in v1, not as a separate route.

## API/Data Decisions

- Sample count should be shown in the run list only if available cheaply from header/results data.
- Do not scan all samples just to compute sample counts for the run list.
- API responses should be normalized DTOs rather than raw Inspect AI objects, except for the hidden raw JSON debug endpoint.

## Local Development Decision

Support both development modes:

1. Angular dev server + FastAPI API during active frontend development.
2. FastAPI serving the built Angular app for production-like local testing and Azure deployment.

## Tentative MVP

1. Angular app with routing.
2. FastAPI backend with normalized run-list and run-detail endpoints.
3. Runs list page with search/filter/sort.
4. Run detail page with summary, metrics, metadata, and paginated samples.
5. Sample detail drawer/page using two-column comparison layout.
6. Plain SCSS design system with reusable components for tables, badges, panels, code blocks, and loading/error states.
7. Azure-safe opaque run IDs; no raw blob paths in browser routes.
8. Hidden-but-accessible raw JSON debug view.
9. Azure App Service Authentication / Microsoft Entra ID configured at platform level.

Explicitly out of scope for v1:
- Run comparison.
- Export to CSV/JSON/PDF.
- Backend caching layer.
- Grouped run navigation.

## Implementation Status

Initial rewrite scaffold implemented.

### Created Structure

- `backend/app/main.py` FastAPI application entrypoint.
- `backend/app/api/routes.py` API routes under `/api`.
- `backend/app/services/inspect_logs.py` Inspect AI log integration and normalized DTO mapping.
- `backend/app/schemas.py` Pydantic response models.
- `frontend/` Angular application.
- `frontend/src/assets/brand/logo.png` copied from `design-assets/logo.png`.
- `Dockerfile` multi-stage build: Angular build stage + Python/FastAPI runtime.
- `README.md` local development and deployment notes.

### Implemented Frontend

- `/` redirects to `/runs`.
- `/runs` table-first run list with search, status filter, refresh, and selected columns.
- `/runs/:runId` detail page with summary metrics, sample list, two-column sample comparison, metadata, and hidden raw JSON disclosure.
- Light technical SCSS visual system using FusionAI blue `#0000c8` as restrained accent.

### Implemented Backend

- `GET /api/health`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/samples`
- `GET /api/runs/{run_id}/raw`

### Verified

- Angular production build succeeds.
- FastAPI app imports successfully.
- API routes work against local `prrr/` Inspect logs.
- FastAPI serves Angular `index.html` fallback for frontend routes.

## Decisions Still Pending

- Whether app-specific roles are needed beyond Azure App Service Authentication.
- Whether the cheap sample count heuristic is sufficient across all log types.
