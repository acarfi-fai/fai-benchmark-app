# FusionAI Eval Console

Angular + FastAPI rewrite of the FusionAI benchmark log viewer.

## Local development

### Backend

The backend uses [`uv`](https://docs.astral.sh/uv/) for dependency management and local script execution.

From `fai-benchmark-app/`:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Set `INSPECT_LOG_DIR` or `LOG_DIR` to point to local logs or Azure Blob-backed Inspect logs:

```bash
export INSPECT_LOG_DIR=/path/to/logs
# or, for Azure Blob-backed Inspect logs:
export INSPECT_LOG_DIR=az://logs
```

Azure-backed log access requires the `adlfs` dependency, which is included in `backend/pyproject.toml`. Make sure your Azure credentials are available in the environment before using an `az://` log path.

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm start
```

Angular dev server proxies `/api` to `http://127.0.0.1:8000`.

## Production-style local run

```bash
cd frontend
npm install
npm run build
cd ../backend
uv sync
FRONTEND_DIST_DIR=../frontend/dist/fusionai-eval-console/browser \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Docker

From `fai-benchmark-app/`:

```bash
docker build -t fusionai-eval-console .
docker run --rm -p 8000:8000 -e INSPECT_LOG_DIR=/logs fusionai-eval-console
```

## Azure Container Registry build

From `fai-benchmark-app/`:

```bash
az acr build \
  --registry faibenchmarkacr \
  --image inspect-view:latest \
  .
```

## Routes

Frontend:

- `/` redirects to `/runs`
- `/runs`
- `/runs/:runId`

API:

- `GET /api/health`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/samples`
- `GET /api/runs/{run_id}/samples/{sample_offset}`
