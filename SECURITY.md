# Security policy

AutoDev executes repository code and can create branches and pull requests. It is designed for
supervised use: a human reviews every plan and every pull request. Treat the backend and sandbox
worker as privileged infrastructure, not as a public web service.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| < 0.1 | No |

## Reporting a vulnerability

Do not open a public issue for a security problem. Contact the maintainers privately with:

- affected version and component (`backend`, `frontend`, `worker`, workflow),
- reproduction steps and required configuration,
- impact assessment and any suggested fix.

Please allow reasonable time for a fix before disclosure. Do not include real tokens, private
repository contents or customer data in a report.

## Security invariants

These properties are enforced in code and covered by tests where practical:

1. **Tokens never reach the browser.** GitHub and AI credentials are read from backend environment
   variables. API responses expose only boolean configuration flags. Settings endpoints return
   masked values.
2. **No automatic merge or force-push.** The git manager can create `autodev/*` branches, commit,
   push those branches to a remote supplied by the backend, and open pull requests. It cannot push
   to a base branch, delete branches, merge or approve pull requests.
3. **Human approval gates.** Plan approval and pull-request creation are separate controls. Pull
   request creation requires `confirm: true` when `REQUIRE_PR_APPROVAL=true` (the default).
4. **Feature branches only.** Branch names are validated against
   `^autodev/[a-z0-9][a-z0-9._-]{0,120}$` before creation or push.
5. **Path confinement.** File reads, writes and test execution are confined to the per-execution
   workspace. Generated paths are normalized and checked against directory traversal, absolute
   paths, symlink escapes and protected files (`.git`, CI configuration, secrets, environment
   files, and the AutoDev backend itself).
6. **Command allowlist.** Test commands must parse to a single executable with no shell
   metacharacters. Shell interpreters, inline evaluation (`python -c`, `node -e`) and package
   manager lifecycle commands other than `test`/`run` are rejected. Allowlisted Python modules are
   limited to `pytest`, `ruff`, `unittest` and `mypy`.
7. **Secret scanning before commit and PR.** Unified diffs are scanned for common token formats,
   private keys and credential assignments. Validation fails closed on detected secrets.
8. **Prompt-injection boundaries.** Repository content, issue bodies and file contents are wrapped
   in explicit untrusted-data delimiters and the model is instructed not to follow instructions
   found inside them. Output is schema-validated before use; the model cannot directly run commands
   or write files.
9. **API authentication.** Set `AUTODEV_API_TOKEN` to require a bearer token on every API route
   except `/api/health`. The frontend stores a client token in `localStorage` only when the operator
   enters it on the Settings page. Use TLS in front of the API.
10. **Log and error redaction.** Known token patterns are redacted from errors and execution logs.
    Authenticated clone URLs are one-shot and never persisted.
11. **Sandbox separation.** In Docker mode the worker is on an internal-only network, runs as a
    non-root user, drops all capabilities, has a read-only root filesystem and shares only the
    workspace volume. The worker validates its own token, workspace path and allowlist.

## Deployment checklist

- [ ] Run behind HTTPS; never expose port 8000 or 8010 publicly.
- [ ] Set a strong `AUTODEV_API_TOKEN` and a unique `SANDBOX_TOKEN`.
- [ ] Prefer `SANDBOX_MODE=docker` for untrusted repositories.
- [ ] Use a fine-grained GitHub token limited to selected repositories, or a GitHub App.
- [ ] Keep `REQUIRE_PLAN_APPROVAL=true` and `REQUIRE_PR_APPROVAL=true`.
- [ ] Restrict egress from the sandbox network; the Compose network is `internal: true`.
- [ ] Back up `/data` (SQLite) and protect it as sensitive data.
- [ ] Pin dependencies and rebuild images regularly.
- [ ] Review the CodeQL workflow results and dependency advisories.

## Local sandbox risk

`SANDBOX_MODE=local` runs test commands directly on the host with a scrubbed environment, a
timeout, process-group termination and POSIX resource limits. It is intended for trusted local
development. It is **not** a security boundary for hostile repository code. Use Docker mode, or a
stronger isolated runtime, before processing untrusted repositories.

## Demo mode

Without `AI_API_KEY` (or with `AI_PROVIDER=demo`) AutoDev uses deterministic fixtures for the
bundled calculator repository. Demo mode is clearly labelled in the API and UI. Fixture-generated
edits and plans are not model output; tests, git diffs, validation and branch operations are real.
Demo mode does not relax any security control.

## Known limitations

- The in-process execution worker does not survive a backend restart; interrupted executions are
  marked failed and must be retried. Logs and diffs already produced are retained.
- SQLite is used for persistence. It is suitable for a single backend instance, not a horizontally
  scaled deployment.
- The Docker worker image contains Python, Node.js, npm and common test tools. Repositories that
  need other runtimes must extend the worker image.
- No inbound GitHub webhooks are implemented; repository connection and issue loading are explicit.
- AutoDev does not install repository dependencies before running tests. Repositories must be
  runnable in the sandbox image as-is, or the worker image must be extended.
