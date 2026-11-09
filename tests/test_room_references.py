from pathlib import Path

from radar.config import load_references
from scripts.room_references import ladder, set_rooms


def test_ladder_is_the_median_of_the_ten_cheapest():
    assert ladder([104, 146, 168, 181, 198, 202, 206, 217, 218, 221, 400, 500]) == {"typical": 200, "good": 150, "exceptional": 115}
    assert ladder([150, 160]) is None                                   # too thin to call a market


def test_set_rooms_changes_one_line_of_one_city(tmp_path):
    text = Path("config/references.yaml").read_text(encoding="utf-8")
    new = set_rooms(text, "chicago", "summer", {"typical": 280, "good": 210, "exceptional": 160}, "google-hotels 2026-11-09")
    diff = [(a, b) for a, b in zip(text.splitlines(), new.splitlines()) if a != b]
    assert len(diff) == 1 and diff[0][1] == "    summer: {typical: 280, good: 210, exceptional: 160, source: google-hotels 2026-11-09}"
    p = tmp_path / "r.yaml"
    p.write_text(new, encoding="utf-8")
    assert load_references(p)["chicago"].rooms["summer"]["typical"] == 280
