"""The scan workflow's "Already scanned today?" guard must use the Calgary date, the one the scan writes."""
import re
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import yaml

import radar.windows  # noqa: F401  (loaded before the snippet swaps the datetime module)

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "scan.yml"


def _guard_step() -> dict:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["scan"]["steps"]
    return next(s for s in steps if s.get("id") == "done")


def test_guard_date_is_calgary_not_utc(monkeypatch, capsys):
    step = _guard_step()
    assert "date -u" not in step["run"]
    assert step["env"]["PYTHONTZPATH"] == ""   # same zone data as the Scan step
    snippet = re.search(r'\$\(python -c "([^"]*CALGARY[^"]*)"\)', step["run"]).group(1)

    class Frozen(datetime):   # 02:00 UTC on 24 Nov = 19:00 on 23 Nov in Calgary: the two dates differ
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 24, 2, 0, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setitem(sys.modules, "datetime", types.SimpleNamespace(datetime=Frozen))
    exec(snippet, {})
    assert capsys.readouterr().out.strip() == "2026-11-23"


def test_every_page_redeploys_the_site_when_pushed():
    """A push that changes only table.html (D-77's scoring table) waited for the next scan to deploy."""
    on = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))[True]   # YAML 1.1 reads the key `on` as true
    pages = {p.name for p in WORKFLOW.parents[2].glob("*.html")}
    assert pages and pages <= set(on["push"]["paths"])


def test_scheduled_runs_watch_the_daily_routine():
    """The routine has no alert of its own; the scheduled scan runs the watchdog in a job of its own (never blocking the scan)."""
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["watchdog"]
    assert job["if"] == "github.event_name == 'schedule'" and "needs" not in job
    assert job["steps"][-1]["run"] == "python3 scripts/watchdog.py"


def test_the_daily_note_commit_names_only_paths_that_exist():
    """`git add` with a missing path adds nothing and fails, so the commit after it never runs. `data/research` (made
    by the first researched candidate) did that on every radar-daily run, and the agent had to retry without it."""
    root = WORKFLOW.parents[2]
    delivery = (root / "routine" / "PROMPT-daily.md").read_text(encoding="utf-8").split("## Delivery", 1)[1]
    paths = re.search(r"`git add ([^`]+)`", delivery).group(1).split()
    assert [p for p in paths if not (root / p).exists()] == []
