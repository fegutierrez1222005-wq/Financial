# Security

Every control here is asserted by a test. Where a control has a test, it is named.

---

## 1. Tenancy

Every tenant-visible row carries `organization_id`, and every workspace-scoped row also
carries `workspace_id` (`OrganizationScopedMixin` / `WorkspaceScopedMixin` in
`apps/api/finagent_api/db/base.py`). Isolation is enforced in the query, not after it:
`DbDocumentRetriever._base_query` filters by workspace before any similarity computation,
so there is no window in which another tenant's text exists in memory.

**Cross-tenant access returns `404`, never `403`.** A `403` would confirm that the
workspace exists. `deps.get_workspace_context` raises `NotFoundError` for both "no such
workspace" and "not your workspace", and logs the attempt as `cross_tenant_access_denied`.

A platform administrator may read any workspace, at `VIEWER` level, and the access is
written to the audit log as `platform_admin_workspace_access`.

> Asserted by `test_agent_cannot_access_another_workspace` and
> `test_run_evidence_never_crosses_workspaces`.

---

## 2. Authentication

| Credential | Lifetime | Storage |
| --- | --- | --- |
| Password | — | bcrypt, cost 12 |
| Access token | 30 min | Signed JWT; the browser holds it in an httpOnly cookie |
| Refresh token | 30 days | Only a SHA-256 hash is stored; rotated on every use |
| API key | optional expiry | Only a SHA-256 hash and an 8-character prefix are stored |
| TOTP secret | — | Encrypted at rest with a key derived from `SECRET_KEY` |

- **Refresh tokens rotate.** Presenting a used refresh token fails, so a stolen token is
  usable at most once and the theft is detectable.
- **Sessions are revocable.** The access token carries a session id; revoking the session
  invalidates the access token immediately rather than waiting for it to expire.
- **Lockout.** Eight consecutive failures locks the account for fifteen minutes. The
  failure response is identical whether or not the account exists.
- **MFA.** TOTP (RFC 6238) with a ±1 period skew window. `REQUIRE_MFA_FOR_ADMINS` refuses
  platform-admin access to a session that did not satisfy MFA.
- **SSO.** `OAuthRegistry` declares Google Workspace, Microsoft Entra ID and Okta. A
  provider without client credentials reports `configured=false` and is not offered at
  sign-in rather than failing after the user clicks it.

> Asserted by `tests/api/test_api_surface.py::TestAuthentication`.

---

## 3. Authorization

`apps/api/finagent_api/rbac.py` declares the entire authorisation surface as one matrix, so
it can be reviewed in a single screen. Roles are strictly nested:

```
VIEWER ⊂ RESEARCHER ⊂ ADMIN ⊂ OWNER
```

Every route states the permission it needs with
`Depends(require_permission(Permission.X))`. No route re-derives role logic.

**API keys are for automation, not administration.** `API_KEY_FORBIDDEN` lists permissions
a key can never exercise regardless of its role — creating API keys, managing members,
deleting the workspace, changing billing, changing security settings. A key cannot mint
another key, which is what stops a leaked key from becoming persistent access.

A member cannot grant a role above their own.

> Asserted by `tests/api/test_api_surface.py::TestAuthorization` and
> `test_api_key_plaintext_is_returned_once_and_never_again`.

---

## 4. Secrets

**No endpoint returns a provider credential.** `Settings.provider_status_summary()` returns
booleans only. The provider-status endpoint reports availability; the admin configuration
endpoint reports *problems* with the configuration, never values.

| Secret | Handling |
| --- | --- |
| Provider API keys | Environment only. Never persisted, never serialised. |
| Data-source credentials | Fernet-encrypted column; only the last four characters are retained in clear text so an operator can recognise which key is installed. |
| Webhook signing secrets | Encrypted at rest; the plaintext is returned exactly once at creation. |
| API keys | Plaintext returned exactly once; only a hash is stored. |

Log output is redacted: `finagent_core.logging.redact` replaces any value under a key in
`SENSITIVE_KEYS` with `[REDACTED]`, recursively, before the record is formatted.

The browser never holds a token or a credential. The Next.js app keeps the session in an
httpOnly cookie and performs every API call from a server component or server action.

> Asserted by `test_provider_api_key_never_appears_in_a_response`,
> `test_stored_connector_secret_is_never_returned`.

---

## 5. Code execution

The `PYTHON` tool exists because quantitative research needs it. It runs in
`services/agent-runner/finagent_agent_runner/sandbox.py` under the following constraints:

| Control | Mechanism |
| --- | --- |
| Process isolation | Separate subprocess in its own process group, killed as a group |
| CPU | `RLIMIT_CPU` |
| Memory | `RLIMIT_AS` |
| File size | `RLIMIT_FSIZE` |
| Wall clock | `subprocess.communicate(timeout=…)` then `SIGKILL` |
| Network | Socket construction raises; no network module is importable |
| Filesystem | `open` is replaced; the working directory is a throwaway temp directory |
| Imports | Allow-list enforced twice — a static AST scan before execution, and a restricted `__builtins__` inside the sandbox namespace |

The import guard is installed as a restricted `__builtins__` **in the sandbox namespace**
rather than by deleting names from the `builtins` module. Deleting them globally breaks
libraries that legitimately use `exec` and `compile` internally — pandas among them — which
would have forced the choice between a usable sandbox and a safe one.

The container runs as a non-root user, so a sandbox escape does not become a container
escape. In production the worker is a separate container with its own memory and PID caps.

> Asserted by `tests/unit/test_core_primitives.py::TestSandbox`.

---

## 6. Information integrity

The information cutoff is the control that makes historical research meaningful, so it is
enforced at three independent layers:

1. **Retrieval** — `DbDocumentRetriever._base_query` adds
   `publication_timestamp <= cutoff` to the SQL, and `publication_timestamp IS NOT NULL`.
2. **Providers** — each data provider calls `_enforce_cutoff` before returning a record.
3. **Backtesting** — `PriceDataset.history_for(as_of)` returns bars strictly *before*
   `as_of`, so a signal can never be computed from the bar it trades on.

**A record with an unknown publication timestamp is inadmissible under a cutoff.** Unknown
provenance cannot be proven to precede the cutoff, and treating it as admissible would make
the control decorative.

The cutoff is never implemented as a prompt instruction. A model asked not to look at
something has no mechanism to comply.

> Asserted by `test_agent_cannot_retrieve_information_after_the_cutoff`,
> `test_search_endpoint_honours_the_cutoff`,
> `test_backtest_history_excludes_the_traded_bar`.

---

## 7. Deletion and retention

Content deletion is soft (`SoftDeleteMixin`): the row is retained with `deleted_at` set so
audit trails and historical traces remain intact, and every retrieval path filters
`deleted_at IS NULL`. A deleted document disappears from search immediately; its past
appearances in run evidence remain visible as a record of what the agent saw at the time.

> Asserted by `test_deleted_document_cannot_be_retrieved`.

---

## 8. Input handling

- Request bodies are validated by Pydantic models; a validation failure names the offending
  field and never echoes the submitted value.
- Uploads are capped by `MAX_UPLOAD_BYTES`, type-checked by extension and sniffed content,
  and hashed (SHA-256) for deduplication.
- All database access goes through SQLAlchemy with bound parameters.
- Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Cache-Control: no-store`, HSTS in production) are set by middleware on every response.

---

## 9. Rate limiting

Four independent buckets: per user, per workspace, per API key, and a stricter one for
operations that spend money (`expensive_operation_guard` — research runs, suite runs,
backtests, experiments). Redis-backed in production, in-process in development; the backend
in use is reported by `/readiness` rather than assumed.

---

## 10. Error handling

No raw exception reaches a client. Every error response is:

```json
{
  "error": {
    "code": "LOOK_AHEAD_VIOLATION",
    "message": "A human-readable, safe description.",
    "retryable": false,
    "details": {},
    "request_id": "req_8f21c0a4e9b24d17"
  }
}
```

`request_id` appears on the response, in the log line, and in the audit record, so support
can find the incident without the user pasting a stack trace.

> Asserted by `tests/api/test_api_surface.py::TestErrorHandling`.

---

## 11. Audit

`AuditLog` records authentication events, permission changes, agent and prompt versions,
document uploads and deletions, research runs, evaluations, backtests, API key lifecycle
and configuration changes — each with actor, resource, outcome, IP, user agent and request
id. Audit rows are never deleted by content deletion.

---

## 12. Data handling policy

> Customer data is isolated and is not used for model training unless explicitly
> authorized.

`Organization.data_training_opt_in` defaults to `false` and can only be changed by an
organization owner, through a dedicated endpoint, and the change is audited. The policy
statement is served by `/version` so it is verifiable rather than only documented.

---

## 13. Reporting a vulnerability

Open a private security advisory on the repository. Please do not file a public issue for
anything affecting tenant isolation, authentication, or the sandbox.
