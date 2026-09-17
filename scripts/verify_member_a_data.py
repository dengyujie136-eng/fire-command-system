"""Read-only acceptance checks for member A's data and realtime demo."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON: {path.relative_to(ROOT)} ({exc})")


def main() -> None:
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip()
    if branch != "member/qingzhe_ivory":
        fail(f"current branch is {branch!r}, expected member/qingzhe_ivory")

    required = [
        "data/raw/weather/dixie_fire_2021_nasa_power_daily.json",
        "data/raw/weather/dixie_fire_2021_nasa_power_hourly.json",
        "data/processed/weather/dixie_fire_2021_nasa_power_daily.csv",
        "data/processed/weather/dixie_fire_2021_nasa_power_hourly.csv",
        "data/raw/realtime_demo/goes18/park_fire_2024/manifest.json",
    ]
    for relative in required:
        path = ROOT / relative
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing or empty file: {relative}")

    manifest = load_json(ROOT / "data/raw/realtime_demo/goes18/park_fire_2024/manifest.json")
    slots = manifest.get("slots", [])
    if len(slots) != 3:
        fail(f"GOES demo expected 3 slots, found {len(slots)}")
    asset_count = 0
    for slot in slots:
        for asset in slot.get("assets", []):
            asset_count += 1
            path = ROOT / asset["local_path"]
            if not path.exists():
                fail(f"missing GOES asset: {asset['local_path']}")
            if path.stat().st_size != int(asset["size_bytes"]):
                fail(f"size mismatch: {asset['local_path']}")
    if asset_count != 9:
        fail(f"GOES demo expected 9 assets, found {asset_count}")

    for index in range(3):
        result = load_json(ROOT / f"data/processed/realtime_demo/hotspots/slot_{index:02d}.json")
        if int(result.get("total", 0)) <= 0:
            fail(f"slot {index} has no detected hotspots")
        if float(result.get("evaluation", {}).get("f1", 0)) < 0.8:
            fail(f"slot {index} F1 is below 0.8")
        preview = ROOT / f"data/processed/realtime_demo/previews/slot_{index:02d}.png"
        if not preview.exists() or preview.stat().st_size == 0:
            fail(f"missing preview: {preview.relative_to(ROOT)}")

    daily = load_json(ROOT / "data/raw/weather/dixie_fire_2021_nasa_power_daily.json")
    hourly = load_json(ROOT / "data/raw/weather/dixie_fire_2021_nasa_power_hourly.json")
    if daily.get("header", {}).get("time_standard") != "UTC":
        fail("daily weather is not marked UTC")
    if hourly.get("header", {}).get("time_standard") != "UTC":
        fail("hourly weather is not marked UTC")

    print("OK: member A branch, weather files, GOES assets, detections, and previews are valid")


if __name__ == "__main__":
    main()
