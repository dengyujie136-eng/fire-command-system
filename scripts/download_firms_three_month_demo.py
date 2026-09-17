"""Download a small three-month FIRMS archive for the realtime demo."""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "realtime_demo" / "firms_archive" / "california_nevada_2025"
SOURCE = "VIIRS_SNPP_SP"
BBOX = (-125.0, 32.0, -114.0, 42.0)
START = date(2025, 6, 15)
END = date(2025, 9, 15)
CHUNK_DAYS = 5


def main() -> int:
    key = os.getenv("FIRMS_MAP_KEY", "").strip()
    if not key:
        env_path = ROOT / ".env"
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("FIRMS_MAP_KEY="):
                key = line.split("=", 1)[1].strip()
                break
    if not key:
        raise SystemExit("FIRMS_MAP_KEY is missing from environment or repository .env")

    OUT.mkdir(parents=True, exist_ok=True)
    rows_by_id: dict[str, dict[str, str]] = {}
    chunks: list[dict[str, object]] = []
    current = START
    while current <= END:
            chunk_end = min(current + timedelta(days=CHUNK_DAYS - 1), END)
            url = (
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{SOURCE}/"
                f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}/{CHUNK_DAYS}/{chunk_end.isoformat()}"
            )
            try:
                with urllib.request.urlopen(url, timeout=90) as response:
                    text = response.read().decode("utf-8")
            except urllib.error.URLError:
                text = subprocess.check_output(["curl.exe", "-fsSL", "--retry", "3", url], timeout=120).decode("utf-8")
            chunk_path = OUT / f"firms_{current.isoformat()}_{chunk_end.isoformat()}.csv"
            chunk_path.write_text(text, encoding="utf-8")
            parsed = list(csv.DictReader(io.StringIO(text)))
            for row in parsed:
                key_row = "|".join(row.get(field, "") for field in ("acq_date", "acq_time", "latitude", "longitude", "satellite", "instrument"))
                rows_by_id[key_row] = row
            chunks.append({"start": current.isoformat(), "end": chunk_end.isoformat(), "rows": len(parsed), "file": str(chunk_path.relative_to(ROOT)).replace("\\", "/")})
            print(f"{current}..{chunk_end}: {len(parsed)} rows")
            current = chunk_end + timedelta(days=1)
            time.sleep(0.15)

    all_rows = list(rows_by_id.values())
    fields = list(all_rows[0]) if all_rows else ["latitude", "longitude", "acq_date", "acq_time"]
    combined = OUT / "firms_three_months_combined.csv"
    with combined.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)
    manifest = {
        "schema_version": "fire.realtime.demo.firms_archive.v0.1",
        "display_name": "FIRMS three-month historical realtime demonstration",
        "source": SOURCE,
        "source_url": "https://firms.modaps.eosdis.nasa.gov/",
        "bbox_wgs84": list(BBOX),
        "start_date": START.isoformat(),
        "end_date": END.isoformat(),
        "data_source_mode": "pre_downloaded_historical_simulated_reception",
        "chunk_days": CHUNK_DAYS,
        "chunks": chunks,
        "unique_rows": len(all_rows),
        "combined_file": str(combined.relative_to(ROOT)).replace("\\", "/"),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"unique rows: {len(all_rows)}")
    print(f"manifest: {OUT / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
