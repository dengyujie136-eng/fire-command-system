"""Download a small, reproducible GOES-18 ABI fire-monitoring demo set.

The demo is deliberately independent from Dixie Fire and FIRMS history. It
uses public NOAA GOES-18 CONUS files around the 2024 Park Fire period.
"""

from __future__ import annotations

import argparse
import json
import sys
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path


BUCKET = "https://noaa-goes18.s3.amazonaws.com"
NAMESPACE = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def s3_keys(prefix: str) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({"list-type": "2", "prefix": prefix, "max-keys": "1000"})
    url = f"{BUCKET}/?{query}"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read()
    except urllib.error.URLError:
        # Windows systems with a managed proxy often have a working curl TLS
        # stack while the active Python environment does not.
        payload = subprocess.check_output(["curl.exe", "-fsSL", "--retry", "3", url], timeout=90)
    root = ET.fromstring(payload)
    return [
        {
            "key": item.findtext(f"{NAMESPACE}Key", ""),
            "size": item.findtext(f"{NAMESPACE}Size", "0"),
            "last_modified": item.findtext(f"{NAMESPACE}LastModified", ""),
        }
        for item in root.findall(f"{NAMESPACE}Contents")
    ]


def choose_file(files: list[dict[str, str]], timestamp: datetime) -> dict[str, str] | None:
    if not files:
        return None
    stamp = timestamp.strftime("%Y%j%H%M")
    candidates = [item for item in files if f"s{stamp}" in item["key"]]
    if candidates:
        return candidates[0]
    return min(
        files,
        key=lambda item: abs(
            datetime.strptime(item["key"].split("_s", 1)[1][:13], "%Y%j%H%M%S").replace(tzinfo=timezone.utc).timestamp()
            - timestamp.timestamp()
        ),
    )


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        print(f"exists: {destination.name}")
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"download: {url}")
    try:
        with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
    except urllib.error.URLError:
        temporary.unlink(missing_ok=True)
        subprocess.run(["curl.exe", "-fL", "--retry", "3", "--retry-delay", "2", "-o", str(temporary), url], check=True, timeout=600)
    temporary.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="2024-07-25", help="UTC date, default is Park Fire 2024 period")
    parser.add_argument("--start-hour", type=int, default=20)
    parser.add_argument("--slots", type=int, default=3, help="Number of 10-minute slots")
    parser.add_argument("--download", action="store_true", help="Actually download NetCDF files")
    parser.add_argument("--output", type=Path, default=Path("data/raw/realtime_demo/goes18/park_fire_2024"))
    args = parser.parse_args()

    date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    first_slot = date.replace(hour=args.start_hour, minute=0)
    slots = [first_slot + timedelta(minutes=10 * index) for index in range(max(1, args.slots))]
    manifest: dict[str, object] = {
        "schema_version": "fire.realtime.demo.goes18.v0.1",
        "event_id": "park_fire_2024_demo",
        "display_name": "Park Fire 2024 GOES-18 high-temporal-resolution demo",
        "data_source_mode": "pre_downloaded_real_satellite_simulated_reception",
        "platform": "GOES-18",
        "instrument": "ABI",
        "coverage": "CONUS",
        "source_url": BUCKET,
        "license": "NOAA Open Data",
        "temporal_resolution_minutes": 10,
        "bands": {"C07": "3.9 um shortwave infrared", "C14": "11.2 um longwave infrared"},
        "reference_product": "ABI-L2-FDCC",
        "slots": [],
    }

    for timestamp in slots:
        year = timestamp.year
        day = timestamp.timetuple().tm_yday
        hour = timestamp.hour
        slot_entry: dict[str, object] = {
            "observed_at": timestamp.isoformat().replace("+00:00", "Z"),
            "assets": [],
        }
        for product, channel in (("ABI-L1b-RadC", "C07"), ("ABI-L1b-RadC", "C14"), ("ABI-L2-FDCC", "FDCC")):
            prefix = f"{product}/{year}/{day:03d}/{hour:02d}/"
            files = s3_keys(prefix)
            if product == "ABI-L1b-RadC":
                files = [item for item in files if f"M6{channel}" in item["key"]]
            chosen = choose_file(files, timestamp)
            if chosen is None:
                print(f"no asset found for {timestamp.isoformat()} {channel}", file=sys.stderr)
                continue
            relative = Path(channel) / Path(chosen["key"]).name
            local_path = args.output / relative
            asset = {
                "asset_id": f"goes18-park-fire-2024-{timestamp.strftime('%Y%m%dT%H%MZ')}-{channel.lower()}",
                "product": product,
                "channel": channel,
                "uri": f"{BUCKET}/{chosen['key']}",
                "local_path": str(local_path).replace("\\", "/"),
                "mime_type": "application/x-netcdf4",
                "size_bytes": int(chosen["size"] or 0),
                "acquired_at": chosen["last_modified"],
                "coverage_bbox": [-125.0, 24.0, -66.0, 50.0],
                "crs": "GOES-R ABI fixed grid (NetCDF projection metadata)",
            }
            slot_entry["assets"].append(asset)
            if args.download:
                download(asset["uri"], local_path)
            time.sleep(0.1)
        manifest["slots"].append(slot_entry)

    manifest["asset_count"] = sum(len(slot["assets"]) for slot in manifest["slots"])
    manifest["downloaded"] = args.download
    manifest_path = args.output / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest: {manifest_path}")
    print(f"assets: {manifest['asset_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
