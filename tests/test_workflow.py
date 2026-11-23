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
