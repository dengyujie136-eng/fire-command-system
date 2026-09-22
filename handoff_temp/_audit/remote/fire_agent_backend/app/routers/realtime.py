from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.realtime import RealtimeSyncRequest
from app.services.realtime_service import get_region, list_regions, sync_region


router = APIRouter(prefix="/realtime", tags=["realtime-monitor"])


@router.get("/regions")
async def realtime_regions() -> dict[str, Any]:
    return {"schema_version": "fire.realtime.regions.v0.1", "items": list_regions()}


@router.post("/sync")
async def realtime_sync(
    request: RealtimeSyncRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        get_region(request.region_id)
        return await sync_region(db, request.region_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        return {
            "ready": False,
            "region_id": request.region_id,
            "source": "FIRMS NRT / VIIRS",
            "fetched_at": datetime.now(timezone.utc),
            "detection_status": "同步失败",
            "hotspots": [],
            "total": 0,
            "error": str(exc),
        }


@router.get("/status")
async def realtime_status(
    region_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        get_region(region_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await db.execute(
        text(
            """
            SELECT observation_id, source, product, observed_at, fetched_at,
                   source_file, metadata_json
            FROM realtime_observations
            WHERE region_id = :region_id
            ORDER BY fetched_at DESC
            LIMIT 1
            """
        ),
        {"region_id": region_id},
    )
    row = result.mappings().first()
    if row is None:
        return {"ready": False, "region_id": region_id, "status": "未同步", "hotspot_count": 0}
    count = await db.scalar(
        text("SELECT COUNT(*) FROM realtime_hotspots WHERE observation_id = :observation_id"),
        {"observation_id": row["observation_id"]},
    )
    return {
        "ready": True,
        "region_id": region_id,
        "status": "已同步",
        "observation": dict(row),
        "hotspot_count": int(count or 0),
    }


@router.get("/hotspots")
async def realtime_hotspots(
    region_id: str = Query(...),
    observation_id: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        get_region(region_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    condition = "region_id = :region_id"
    params: dict[str, Any] = {"region_id": region_id, "limit": limit}
    if observation_id:
        condition += " AND observation_id = :observation_id"
        params["observation_id"] = observation_id
    else:
        latest = await db.scalar(
            text(
                "SELECT observation_id FROM realtime_observations "
                "WHERE region_id = :region_id ORDER BY fetched_at DESC LIMIT 1"
            ),
            {"region_id": region_id},
        )
        if latest is None:
            return {"schema_version": "fire.realtime.hotspots.v0.1", "region_id": region_id, "items": [], "total": 0}
        condition += " AND observation_id = :observation_id"
        params["observation_id"] = latest
    result = await db.execute(
        text(
            f"""
            SELECT detection_id, region_id, source, observed_at, detected_at,
                   longitude, latitude, confidence, status, attributes
            FROM realtime_hotspots
            WHERE {condition}
            ORDER BY observed_at, detection_id
            LIMIT :limit
            """
        ),
        params,
    )
    items = []
    for row in result.mappings().all():
        item = dict(row)
        attributes = item.pop("attributes") or {}
        item["source_asset_id"] = attributes.get("source_asset_id", "")
        item["algorithm"] = attributes.get("algorithm", "firms_nrt_product_v0.1")
        item["attributes"] = attributes
        items.append(item)
    return {
        "schema_version": "fire.realtime.hotspots.v0.1",
        "region_id": region_id,
        "items": items,
        "total": len(items),
    }


@router.get("/observations")
async def realtime_observations(
    region_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            SELECT observation_id, region_id, source, product, observed_at,
                   fetched_at, source_file, metadata_json
            FROM realtime_observations
            WHERE region_id = :region_id
            ORDER BY fetched_at DESC
            LIMIT :limit
            """
        ),
        {"region_id": region_id, "limit": limit},
    )
    return {
        "schema_version": "fire.realtime.observations.v0.1",
        "region_id": region_id,
        "items": [dict(row) for row in result.mappings().all()],
    }
