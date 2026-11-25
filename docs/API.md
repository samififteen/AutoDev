# API reference

Base URL: `http://127.0.0.1:8000` (or the nginx origin at `/api`). Interactive OpenAPI docs are at
`/docs`.

Authentication: when `AUTODEV_API_TOKEN` is set, send `Authorization: Bearer <token>` on every route
except `GET /api/health`. The SSE endpoint also accepts `?token=<token>` because `EventSource`
cannot set headers.

## Health and system

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness, database reachability, demo-mode flag |
| GET | `/api/system/info` | Version, provider, sandbox mode, limits |
| GET | `/api/system/status` | Per-component status; GitHub is verified, not assumed |
| GET | `/api/dashboard/stats` | Stored metrics, 14-day chart, recent activity |

## Repositories and issues

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/repositories?search=&visibility=&page=` | Connected repositories |
| POST | `/api/repositories/connect` | Connect `{full_name, default_branch?}` |
| GET | `/api/repositories/{id}` | Repository and latest analysis |
| POST | `/api/repositories/{id}/analyze` | Clone and index the real repository |
| POST | `/api/repositories/{id}/refresh` | Refresh GitHub metadata |
| GET | `/api/repositories/{id}/issues?state=open` | Issues (demo fixtures for the demo repo) |

## Tasks and executions

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/tasks?repository_id=&status=&search=&page=` | Task queue |
| POST | `/api/tasks` | Create a task |
| POST | `/api/tasks/{id}/execute` | Queue an agent execution |
| GET | `/api/executions?status=&search=&sort=&order=&page=` | Execution history |
| GET | `/api/executions/{id}` | Full detail: plan, timeline, validation, tests, changes |
| GET | `/api/executions/{id}/logs?limit=` | Persisted logs |
| GET | `/api/executions/{id}/stream` | Server-Sent Events |
| POST | `/api/executions/{id}/approve-plan` | Approve a pending plan |
| POST | `/api/executions/{id}/cancel` | Request cancellation |
| POST | `/api/executions/{id}/retry` | New execution from the same task |
| GET | `/api/executions/{id}/diff` | Structured file diffs and unified diff |
| GET | `/api/executions/{id}/diff/patch` | Download `.patch` |
| GET | `/api/executions/{id}/pr-draft` | Pull request title/body draft |
| POST | `/api/executions/{id}/create-pr` | Create the pull request (requires `confirm: true` by default) |

### Example: create and run a task

```bash
curl -s http://127.0.0.1:8000/api/repositories | jq '.items[0].id'
curl -s -X POST http://127.0.0.1:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"repository_id":1,"title":"Fix multiplication","description":"multiply(2,3) returns 5","priority":"high"}'
curl -s -X POST http://127.0.0.1:8000/api/tasks/1/execute
curl -s -N http://127.0.0.1:8000/api/executions/1/stream
```

If plan approval is enabled the stream pauses in `awaiting_approval`:

```bash
curl -s -X POST http://127.0.0.1:8000/api/executions/1/approve-plan
```

### SSE events

Each event is JSON in `data:`:

```json
{"type":"log","id":42,"level":"info","stage":"tests","message":"8 passed in 0.41s","created_at":"2026-01-01T00:00:00Z"}
{"type":"state","status":"awaiting_approval","stage":"awaiting_approval"}
{"type":"end","status":"completed"}
```

Clients should treat the backend as the source of truth and refresh execution detail on state/end
events. Log IDs are persisted and can be replayed with `/logs`.

## Pull requests and settings

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/pull-requests?search=&status=&page=` | Pull requests created by AutoDev |
| GET | `/api/settings` | Runtime settings plus masked provider info |
| PUT | `/api/settings` | Update `{agent?, testing?}` with server-side validation |

## Errors

Errors use a consistent envelope:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Default test command is not allowed",
    "details": []
  }
}
```

Validation errors return HTTP 422, unsafe operations 400, missing records 404, configuration
problems 503 and GitHub failures 502. Tokens and authorization headers are never echoed.
