# API

Base path `/api/v1`. Interactive documentation at `/docs`; the machine-readable schema at
`/openapi.json`.

---

## 1. Authentication

Two credential types resolve to the same `Principal`:

**Session token** — from `POST /auth/login` or `POST /auth/register`.

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**API key** — for automation.

```
X-API-Key: fk_live_a1b2c3d4_<secret>
```

An API key can never create another key, manage members, delete the workspace, change
billing or change security settings, regardless of its role.

---

## 2. Selecting a workspace

Every tenant-scoped endpoint needs a workspace. Supply it as a header (preferred) or a
query parameter:

```
X-Workspace-Id: 3f2c9b80-...
```

A key scoped to a single workspace defaults to it. A request for a workspace the caller
cannot access returns **404**, not 403 — the response must not confirm that the workspace
exists.

---

## 3. Error contract

Every failure, from any endpoint, has the same shape:

```json
{
  "error": {
    "code": "LOOK_AHEAD_VIOLATION",
    "message": "Evidence published after the information cutoff was requested.",
    "retryable": false,
    "details": { "cutoff": "2023-06-30T00:00:00Z" },
    "request_id": "req_8f21c0a4e9b24d17"
  }
}
```

`request_id` also appears on the response as `X-Request-ID` and in the server log, so an
incident can be found without the user pasting a stack trace. Raw exceptions are never
returned.

| Code | Status | |
| --- | --- | --- |
| `VALIDATION_FAILED` | 422 | `details.fields` names each offending field |
| `UNAUTHENTICATED` | 401 | missing, expired or revoked credential |
| `FORBIDDEN` | 403 | `details.required_permission` names what was needed |
| `NOT_FOUND` | 404 | also returned for cross-tenant access |
| `CONFLICT` | 409 | |
| `QUOTA_EXCEEDED` | 402 | plan limit reached |
| `RATE_LIMITED` | 429 | `Retry-After` is set |
| `FILE_TOO_LARGE` | 413 | |
| `UNSUPPORTED_FILE_TYPE` | 415 | |
| `MODEL_UNAVAILABLE` | 503 | the model's provider has no credentials |
| `PROVIDER_UNAVAILABLE` | 503 | |
| `LOOK_AHEAD_VIOLATION` | 409 | information published after the cutoff was requested |
| `BACKTEST_INVALID` | 422 | |
| `SANDBOX_DENIED` | 400 | the submitted code is not permitted |
| `SANDBOX_TIMEOUT` | 504 | |
| `AGENT_TIMEOUT` | 504 | |
| `AGENT_STEP_LIMIT` | 422 | |
| `INTERNAL_ERROR` | 500 | logged with the request id |

---

## 4. Rate limits

Four buckets: per user, per workspace, per API key, and a stricter one for operations that
spend money — research runs, suite runs, backtests and experiments. Responses carry
`X-RateLimit-Remaining`.

---

## 5. Endpoints

### Health — unauthenticated, outside the API prefix

| Method | Path | |
| --- | --- | --- |
| GET | `/health` | Liveness. Does not touch the database. |
| GET | `/readiness` | Per-component readiness, including which model providers are available |
| GET | `/version` | Build info and the data-training policy |

### Auth

| Method | Path | |
| --- | --- | --- |
| POST | `/auth/register` | Create account, organization, workspace and optional demo workspace |
| POST | `/auth/login` | Exchange credentials for tokens |
| POST | `/auth/refresh` | Rotate a refresh token (single use) |
| POST | `/auth/logout` | Revoke one session |
| POST | `/auth/logout-all` | Revoke every session for the user |
| GET | `/auth/me` | The authenticated user |
| GET | `/auth/sessions` | Active sessions |
| DELETE | `/auth/sessions/{session_id}` | Revoke one session |
| POST | `/auth/change-password` | Signs out other sessions |
| POST | `/auth/mfa/enrol` · `/auth/mfa/confirm` · `/auth/mfa/disable` | TOTP |
| POST | `/auth/invitations/accept` | Accept a workspace invitation |
| GET | `/auth/providers` | Which sign-in methods are configured |

### Workspaces and tenancy

| Method | Path | |
| --- | --- | --- |
| GET | `/organizations` | |
| PATCH | `/organizations/{id}/data-training` | Owner only; audited |
| GET · POST | `/workspaces` | |
| GET · PATCH · DELETE | `/workspaces/current` | |
| POST | `/workspaces/demo` | Seed the ACME demo workspace (idempotent) |
| GET | `/workspaces/current/members` | |
| POST | `/workspaces/current/invitations` | Token returned once |
| PATCH · DELETE | `/workspaces/current/members/{id}` | |
| GET · POST | `/workspaces/current/api-keys` | Plaintext returned once |
| DELETE | `/workspaces/current/api-keys/{id}` | |
| GET | `/roles` | The full permission matrix |

### Agents

| Method | Path | |
| --- | --- | --- |
| GET · POST | `/agents` | |
| GET · DELETE | `/agents/{id}` | Deletion is soft |
| GET · POST | `/agents/{id}/versions` | A change publishes a new immutable version |
| GET | `/agents/{id}/prompts` | Prompt history |
| GET | `/catalog/models` · `/catalog/tools` | Availability, cost estimates, mock flags |

### Research

| Method | Path | |
| --- | --- | --- |
| GET | `/research/templates` | |
| POST | `/research/tasks` | |
| GET · POST | `/research/runs` | `POST` accepts an inline task |
| GET | `/research/runs/{id}` | Plan, trace, evidence, citations, tool calls, model calls |
| POST | `/research/runs/{id}/execute` | Execute a queued run |
| POST | `/research/runs/{id}/reproduce` | Re-run the recorded configuration |
| POST | `/research/runs/{id}/debate` | Bull / bear / skeptic / judge |

### Evaluations

| Method | Path | |
| --- | --- | --- |
| GET | `/evaluations/suites` · `/evaluations/suites/{key}/cases` | |
| POST | `/evaluations/runs` | Score one run |
| POST | `/evaluations/suites/run` | Run a suite against an agent version |
| GET | `/evaluations` · `/evaluations/{id}` | |
| GET | `/evaluations/scoreboard` | Latest score per agent version |

### Backtests · Experiments · Benchmarks

| Method | Path | |
| --- | --- | --- |
| GET · POST | `/backtests` | |
| GET | `/backtests/{id}` | Splits, equity curves, findings, disclaimer |
| POST | `/backtests/{id}/run` | |
| GET · POST | `/experiments` · `/experiments/{id}` · `/experiments/{id}/run` | |
| POST | `/benchmarks` · `/benchmarks/{id}/run` | |
| GET | `/benchmarks/{id}` | Ranked entries plus the ranking basis |
| GET | `/comparisons/prompts` · `/comparisons/models` | |

### Data

| Method | Path | |
| --- | --- | --- |
| GET · POST | `/documents` | `POST` is `multipart/form-data` |
| GET · DELETE | `/documents/{id}` | |
| POST | `/documents/search` | Accepts `as_of` to restrict by publication date |
| GET | `/documents/stats` | |
| GET · POST | `/data-sources` | The credential is encrypted and never returned |
| GET | `/datasets` | |
| GET | `/providers/status` | Availability and boolean credential flags — never values |

### Platform

| Method | Path | |
| --- | --- | --- |
| GET | `/dashboard` · `/usage` · `/usage/trend` | |
| GET | `/audit-logs` | |
| GET | `/subscription` | |
| GET · POST · DELETE | `/webhooks` | Signing secret returned once |
| GET | `/notifications` · POST `/notifications/{id}/read` | |
| GET · POST · DELETE | `/alerts` | |
| POST | `/feedback` | |
| GET | `/admin/overview` · `/admin/configuration` | Platform administrators only |

---

## 6. Example: run research and score it

```bash
TOKEN=$(curl -sX POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@fund.com","password":"..."}' | jq -r .access_token)

WS=$(curl -s localhost:8000/api/v1/workspaces \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

RUN=$(curl -sX POST localhost:8000/api/v1/research/runs \
  -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $WS" \
  -H 'Content-Type: application/json' \
  -d '{
        "agent_id": "'"$AGENT"'",
        "run_now": true,
        "task": {
          "template": "earnings_analysis",
          "inputs": {"ticker": "ACME", "quarter": "Q4 2023"},
          "information_cutoff": "2024-03-01T00:00:00Z"
        }
      }' | jq -r .id)

curl -sX POST localhost:8000/api/v1/evaluations/runs \
  -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $WS" \
  -H 'Content-Type: application/json' \
  -d '{"run_id":"'"$RUN"'"}' | jq '{score: .overall_score, halluc: .hallucination_rate}'
```

---

## 7. Asynchrony

Research runs, suite runs, backtests and experiments are submitted through the job queue.
With `JOB_BACKEND=inline` they complete before the response returns; with
`JOB_BACKEND=celery` they are handed to a worker. **The response shape is identical either
way**: the resource row is created before the work is queued, so the client always has an
id to poll and never has to branch on the backend.

Poll the resource and read `status` (`QUEUED` → `RUNNING` → `SUCCEEDED` / `FAILED`).
