# Claude routine capabilities (probed 2026-11-09)

Routines are created through the `RemoteTrigger` API (environment `Default`). Month one runs on
`claude-opus-5-5` (D-28): `radar-daily` and the weekly digest. The hit routine is on Sonnet 5.5 (it
only runs after go-live). Each routine is limited to the Gmail connector. `radar-daily` and the
GitHub probe carry a one-line prompt that reads their instructions from `routine/PROMPT-*.md` in the
repo, so editing the file is enough (D-35).

## GitHub probe, 2026-11-09 14:38 UTC (before the Claude GitHub App was installed)

Routine `radar-probe-github` (`trig_01NCvvPT6cUDiLLFkr7HN6tv`, Sonnet, no connectors), session
https://claude.ai/code/session_01Gg7wycMRsTfLmpuTs6pkfv. Prompt: `routine/PROMPT-probe-github.md`.

| Check | Result |
|---|---|
| Sandbox | Python 3.11.18 (the package now allows 3.11, D-34); `gh` installed; `GH_TOKEN`/`GITHUB_TOKEN` set; `api.github.com` reachable. |
| GitHub tools | `mcp__github__*` present: `create_pull_request`, `pull_request_read`, `merge_pull_request`, `update_pull_request`, `list_pull_requests` and more. |
| `gh pr ...` | Never works here: "GitHub GraphQL is not available from Claude Code sessions; use the REST API". `gh api` (REST) is the CLI route. |
| (a) push to `main` | **No**, 403: "Claude doesn't have GitHub access to WilliamEbong/spontaneous-travel-radar". |
| (b) branch push and PR | **No**: the branch push got the same 403, and `create_pull_request` returned 403 "Resource not accessible by integration". |
| (c) read PR comments | Not tested (no PR could be opened). Unauthenticated REST reads return 200, so reading comments on a public PR works without the App. |
| Tests | Failed only because `requires-python` was `>=3.12`. Fixed (D-34); 58 pass on 3.11. |

All the failures trace back to the missing Claude GitHub App. Re-run the probe after it is installed
(steps in `HANDOFF.md`).

## Probe run

Routine `radar-probe` (one-off, Haiku 5.5, Gmail connector only) ran 2026-11-09 07:47 UTC,
session https://claude.ai/code/session_01Gg7wydvKoz6mxEbeNU18b5.

| Capability | Result |
|---|---|
| Read the repo | **Yes.** The public repo clones fine; README read, `data/latest.json` not there yet (first scan running). |
| Commit / push | **No.** Push to `main` and to a `claude/` branch both returned 403: "Claude doesn't have GitHub access to WilliamEbong/spontaneous-travel-radar". Fix: install the Claude GitHub App on this repo (https://github.com/apps/claude/installations/select_target). |
| Email via Gmail | **Yes.** `mcp__Gmail__send_message` sent the test email to your Gmail (message id 1a1bf476f1da75f3). |

Consequences:
- The weekly digest checks `git push --dry-run` first: if pushing works it commits
  `data/digests/<date>.md` (shown on the dashboard), otherwise it emails the digest. Until the GitHub
  App is installed, digests arrive by email only.
- The hit routine emails its judgment; it appends "Claude's take" to the brief only when it can push.
- The probe is a one-shot routine and has ended; delete it at https://claude.ai/code/routines if you
  like (the API cannot delete).

## Webhook trigger (for the hit routine)

- Shape that passes validation up to the GitHub check:
  `{"routine_trigger_id": "<id>", "hook_type": "app", "source": "github",
  "scope_id": "WilliamEbong/spontaneous-travel-radar", "events": ["push"], "filter": {...}}`
- **Blocked:** "The Claude GitHub App is not installed on williamebong/spontaneous-travel-radar.
  Install it at https://github.com/apps/claude/installations/select_target so GitHub can deliver
  webhook events." Installing an app on your account is yours to do, so the webhook was not created.
- The hit routine (`radar-hit`) exists, **disabled**, with no schedule. It cannot fire.
- Path filtering (`hits/*.json` only, excluding `hits/dry-run/`, `hits/index.json`, `.md`, `data/**`)
  was not confirmed: `filter.added_paths` is rejected, and `filter.paths` was not checked because the
  app check fails first. Since every daily scan pushes to `main`, a push trigger without a path
  filter would fire the routine every day. Do not enable it that way.

## What to do at go-live

1. Install the Claude GitHub App on this repo (link above).
2. Retry `create_webhook_trigger` with the shape above and a path filter. If the API cannot filter
   on paths, keep the hit routine disabled and run it by hand from claude.ai when the dashboard shows
   a live hit: one run per hit, no polling.
