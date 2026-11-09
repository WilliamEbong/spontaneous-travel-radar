# Claude routine capabilities (probed 2026-11-09)

Routines are created through the `RemoteTrigger` API (environment `Default`, model `claude-haiku-5-5`,
the cheapest offered). Each routine is limited to the Gmail connector.

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
