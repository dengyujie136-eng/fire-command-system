from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings

CATEGORY_LABELS = {
    "fire_spread": "Fire spread rules",
    "weather": "Weather impact rules",
    "terrain": "Terrain rules",
    "fuel": "Fuel rules",
    "risk": "Spatial risk rules",
    "rescue": "Rescue safety rules",
    "command": "Command decision rules",
}


def _rule_path() -> Path:
    settings_root = get_settings().project_root
    candidates = [
        settings_root / "config" / "rules" / "fire_emergency_rules.yaml",
        settings_root.parent / "config" / "rules" / "fire_emergency_rules.yaml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_rule_base_summary() -> dict[str, Any]:
    path = _rule_path()
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    categories: dict[str, int] = {}
    rule_count = 0
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("- rule_id:"):
            rule_count += 1
            continue
        if line.startswith("category:"):
            category = line.split(":", 1)[1].strip()
            categories[category] = categories.get(category, 0) + 1
    return {
        "schema_version": "fire.rule-base.summary.v0.1",
        "source_mode": "structured_rule_base",
        "path": str(path.as_posix()),
        "rule_count": rule_count,
        "categories": [
            {
                "category": category,
                "label": CATEGORY_LABELS.get(category, category),
                "rule_count": count,
            }
            for category, count in sorted(categories.items())
        ],
        "raw_yaml": text,
    }