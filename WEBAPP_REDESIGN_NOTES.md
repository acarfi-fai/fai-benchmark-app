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

## Initial API Shape

Candidate endpoints:

- `GET /api/health`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/samples?limit=&offset=`
- `GET /api/runs/{run_id}/samples/{sample_id}`
- `GET /api/runs/{run_id}/raw` for debug/admin use

Open question: whether raw log access should be exposed in production or gated behind an admin/debug flag.

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

## Tentative MVP

1. Angular app with routing.
2. FastAPI backend with normalized run-list and run-detail endpoints.
3. Runs list page with search/filter/sort.
4. Run detail page with summary, metrics, metadata, and paginated samples.
5. Sample detail drawer/page.
6. Plain SCSS design system with reusable components for tables, badges, panels, code blocks, and loading/error states.
7. Azure-safe opaque run IDs; no raw blob paths in browser routes.

## Decisions Still Pending

- Exact frontend route names.
- Deployment topology.
- Authentication model.
- Design direction and brand references.
- Whether to include comparison/export/review workflows in v1.
- Final API response schemas.
