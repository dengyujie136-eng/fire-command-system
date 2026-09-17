from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.services.realtime_demo_service import demo_manifest, preview_path, run_detection


router = APIRouter(prefix="/realtime-demo", tags=["realtime-image-demo"])


ARCHIVE_RELATIVE_DIR = Path("raw/realtime_demo/firms_archive/california_nevada_2025")


def _archive_dir() -> Path:
    return get_settings().resolved_data_dir / ARCHIVE_RELATIVE_DIR


def _archive_manifest() -> dict:
    path = _archive_dir() / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("FIRMS三个月演示数据清单不存在")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/firms-archive/manifest")
async def firms_archive_manifest() -> dict:
    try:
        return _archive_manifest()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/firms-archive/hotspots")
async def firms_archive_hotspots(
    observed_on: date | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=10000),
) -> dict:
    try:
        manifest = _archive_manifest()
        target = observed_on.isoformat() if observed_on else manifest["end_date"]
        source_path = _archive_dir() / "firms_three_months_combined.csv"
        if observed_on and not (manifest["start_date"] <= target <= manifest["end_date"]):
            raise HTTPException(status_code=422, detail=f"observed_on 超出数据范围：{manifest['start_date']} 至 {manifest['end_date']}")
        if not source_path.exists():
            raise FileNotFoundError("FIRMS 三个月演示合并 CSV 不存在")
        rows = []
        with source_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("acq_date") != target:
                    continue
                try:
                    longitude = float(row["longitude"])
                    latitude = float(row["latitude"])
                except (KeyError, TypeError, ValueError):
                    continue
                rows.append(
                    {
                        "detection_id": f"firms-archive-{row.get('acq_date')}-{row.get('acq_time')}-{row.get('latitude')}-{row.get('longitude')}",
                        "longitude": longitude,
                        "latitude": latitude,
                        "observed_at": f"{target}T{(row.get('acq_time') or '0000').zfill(4)[:4]}00Z",
                        "confidence": row.get("confidence"),
                        "frp_mw": row.get("frp"),
                        "daynight": row.get("daynight"),
                        "source": "FIRMS VIIRS_SNPP_SP",
                        "status": "candidate",
                    }
                )
                if len(rows) >= limit:
                    break
        return {
            "schema_version": "fire.realtime.demo.firms_archive.hotspots.v0.1",
            "observed_on": target,
            "source": "FIRMS VIIRS_SNPP_SP",
            "data_source_mode": "pre_downloaded_historical_simulated_reception",
            "items": rows,
            "total": len(rows),
            "truncated": len(rows) >= limit,
        }
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/manifest")
async def realtime_demo_manifest() -> dict:
    try:
        return demo_manifest()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/detect")
async def realtime_demo_detect(slot_index: int = Query(default=0, ge=0, le=99)) -> dict:
    try:
        return run_detection(slot_index)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"GOES影像检测失败: {exc}") from exc


@router.get("/preview/{slot_index}")
async def realtime_demo_preview(slot_index: int) -> FileResponse:
    try:
        path = preview_path(slot_index)
        return FileResponse(path, media_type="image/png", filename=path.name)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
