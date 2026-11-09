You are a one-off capability probe for the repo WilliamEbong/spontaneous-travel-radar (already
cloned). Do exactly these steps, then reply with the report. Never print token or secret values.

1. Environment: `python3 --version`; `which gh` and, if present, `gh auth status`; the NAMES (not
   values) of environment variables matching `GH|GITHUB`; the names of any tools you have whose names
   mention github or pull requests; whether `curl -sI https://api.github.com/rate_limit` returns 200.
2. (a) Push to main: `git push --dry-run origin main`. Record exit code and the last line of output.
3. (b) Branch and PR: `git checkout -b radar/probe-$(date -u +%Y%m%d%H%M)`, add the file
   `docs/notes/probe.txt` containing `routine capability probe, close me`, commit
   (`chore: routine capability probe`), push the branch. Then open a PR into `main` titled
   `probe: routine capability test (close me)` with whatever works: `gh pr create`, a GitHub tool,
   or `curl -X POST https://api.github.com/repos/WilliamEbong/spontaneous-travel-radar/pulls` with any
   token you have. Record which method worked and the PR URL, or every error.
4. (c) Read review comments. If a PR exists, every 2 minutes for up to 10 minutes fetch
   `/pulls/<n>/reviews`, `/pulls/<n>/comments` and `/issues/<n>/comments` from
   `https://api.github.com/repos/WilliamEbong/spontaneous-travel-radar` (unauthenticated curl first;
   `gh api` if that fails). Record HTTP status, and the login and first 100 characters of any review
   or comment that appears (Codex reviews on PR open). Stop polling once a review appears.
5. Tests: `pip install -q -e ".[dev]" && python -m pytest -q`; record the last line.
6. Clean up: close the PR (API or tool), and `git push origin --delete <branch>`. Confirm the PR shows
   closed.

Report format, one line each:
ENV: python=<v> gh=<present/authed/absent> token_vars=<names or none> github_tools=<names or none> api=<status>
A_PUSH_MAIN: <yes/no> <detail>
B_BRANCH_PUSH: <yes/no> <detail>
B_OPEN_PR: <yes/no> <method> <url or error>
C_READ_COMMENTS: <yes/no> <status codes> <review seen: login or none>
TESTS: <last pytest line>
CLEANUP: <PR closed yes/no, branch deleted yes/no>
