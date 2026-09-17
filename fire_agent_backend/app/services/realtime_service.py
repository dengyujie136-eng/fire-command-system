from __future__ import annotations

import csv
import asyncio
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.realtime import RealtimeHotspot, RealtimeObservation


REGIONS: dict[str, dict[str, Any]] = {
    "goes18_north_america_west": {
        "label": "美国西部及北美西部",
        "satellite": "FIRMS NRT / VIIRS",
        "platform": "GOES-18 ABI区域入口",
        "coverage": "GOES-18覆盖区：北美西部",
        "bbox": [-140.0, 15.0, -80.0, 60.0],
        "refresh_minutes": 10,
        "supported": True,
    },
    "himawari_asia_pacific": {
        "label": "亚洲、澳大利亚及太平洋",
        "satellite": "FIRMS NRT / VIIRS",
        "platform": "Himawari-8/9区域入口",
        "coverage": "Himawari覆盖区：亚洲及太平洋",
        "bbox": [80.0, -20.0, 180.0, 60.0],
        "refresh_minutes": 10,
        "supported": True,
    },
    "meteosat_europe_africa": {
        "label": "欧洲及非洲",
        "satellite": "FIRMS NRT / VIIRS",
        "platform": "Meteosat区域入口",
        "coverage": "欧洲及非洲",
        "bbox": [-60.0, -45.0, 60.0, 70.0],
        "refresh_minutes": 15,
        "supported": False,
    },
    "fy4_china": {
        "label": "中国及西北太平洋",
        "satellite": "FIRMS NRT / VIIRS",
        "platform": "FY-4区域入口",
        "coverage": "中国及邻近区域",
        "bbox": [70.0, -10.0, 180.0, 60.0],
        "refresh_minutes": 15,
        "supported": False,
    },
}

_SYNC_LOCKS: dict[str, asyncio.Lock] = {}


def list_regions() -> list[dict[str, Any]]:
    return [
        {"id": region_id, **config, "source_mode": "firms_nrt_candidate"}
        for region_id, config in REGIONS.items()
    ]


def get_region(region_id: str) -> dict[str, Any]:
    config = REGIONS.get(region_id)
    if not config:
        raise ValueError(f"Unsupported realtime region: {region_id}")
    return {"id": region_id, **config, "source_mode": "firms_nrt_candidate"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_float(row: dict[str, str], key: str) -> float | None:
    value = (row.get(key) or "").strip()
    if not value or value.lower() in {"null", "nan", "none"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_confidence(value: str | None) -> float:
    value = (value or "").strip().lower()
    if value in {"high", "h"}:
        return 0.9
    if value in {"nominal", "n", "medium", "m"}:
        return 0.7
    if value in {"low", "l"}:
        return 0.45
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _parse_observed_at(row: dict[str, str]) -> datetime | None:
    date_value = (row.get("acq_date") or "").strip()
    time_value = (row.get("acq_time") or "").strip().zfill(4)
    if not date_value or len(time_value) < 4:
        return None
    try:
        return datetime.strptime(f"{date_value} {time_value[:4]}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _source_record_id(row: dict[str, str]) -> str:
    values = [
        row.get("satellite", ""),
        row.get("instrument", ""),
        row.get("acq_date", ""),
        row.get("acq_time", ""),
        row.get("latitude", ""),
        row.get("longitude", ""),
        row.get("frp", ""),
    ]
    return "|".join(values)


def _json_safe_row(row: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in row.items() if value not in (None, "")}


def _paths(settings, region_id: str, fetched_at: datetime) -> tuple[Path, Path, Path]:
    stamp = fetched_at.strftime("%Y%m%dT%H%M%SZ")
    raw_dir = settings.resolved_data_dir / "raw" / "realtime" / "firms_nrt" / region_id
    processed_dir = settings.resolved_data_dir / "processed" / "realtime" / "hotspots" / region_id
    manifest_dir = settings.resolved_data_dir / "processed" / "realtime" / "manifests"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir / f"{stamp}.csv", processed_dir / f"{stamp}.json", manifest_dir / f"{stamp}_{region_id}.json"


def _prune_files(directory: Path, suffix: str, keep: int) -> None:
    files = sorted(directory.glob(f"*{suffix}"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files[max(keep, 0):]:
        path.unlink(missing_ok=True)


def _sync_lock(region_id: str) -> asyncio.Lock:
    lock = _SYNC_LOCKS.get(region_id)
    if lock is None:
        lock = asyncio.Lock()
        _SYNC_LOCKS[region_id] = lock
    return lock


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _cached_response(db: AsyncSession, region: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    latest = await db.scalar(
        select(RealtimeObservation)
        .where(RealtimeObservation.region_id == region["id"])
        .order_by(RealtimeObservation.fetched_at.desc())
    )
    if latest is None:
        return None
    fetched_at = _as_utc(latest.fetched_at)
    refresh_at = fetched_at + timedelta(minutes=int(region["refresh_minutes"]))
    if now >= refresh_at:
        return None
    hotspots = (
        await db.scalars(
            select(RealtimeHotspot)
            .where(RealtimeHotspot.observation_id == latest.observation_id)
            .order_by(RealtimeHotspot.observed_at, RealtimeHotspot.detection_id)
        )
    ).all()
    return {
        "ready": True,
        "region_id": region["id"],
        "source": latest.source,
        "observed_at": latest.observed_at,
        "fetched_at": latest.fetched_at,
        "detection_status": "已复用缓存候选火点",
        "hotspots": [
            {
                "detection_id": item.detection_id,
                "source_record_id": item.source_record_id,
                "source": item.source,
                "observed_at": item.observed_at,
                "detected_at": item.detected_at,
                "longitude": item.longitude,
                "latitude": item.latitude,
                "confidence": item.confidence,
                "status": item.status,
                "source_asset_id": (item.attributes or {}).get("source_asset_id", ""),
                "algorithm": (item.attributes or {}).get("algorithm", "firms_nrt_product_v0.1"),
                "attributes": item.attributes or {},
            }
            for item in hotspots
        ],
        "total": len(hotspots),
        "data_source_mode": "realtime_candidate_cache",
        "cache_hit": True,
        "next_refresh_at": refresh_at,
        "source_file": latest.source_file,
    }


async def sync_region(db: AsyncSession, region_id: str) -> dict[str, Any]:
    async with _sync_lock(region_id):
        return await _sync_region_unlocked(db, region_id)


async def _sync_region_unlocked(db: AsyncSession, region_id: str) -> dict[str, Any]:
    settings = get_settings()
    region = get_region(region_id)
    if not region["supported"]:
        raise ValueError("该区域当前暂不支持实时火点监测")
    if not settings.firms_map_key:
        raise RuntimeError("FIRMS_MAP_KEY 未配置，请在仓库根目录 .env 中配置 NASA FIRMS MAP KEY")

    now = _utc_now()
    cached = await _cached_response(db, region, now)
    if cached is not None:
        return cached
    fetched_at = now
    west, south, east, north = region["bbox"]
    days = max(1, min(settings.firms_realtime_days, 10))
    endpoint = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{settings.firms_map_key}/VIIRS_SNPP_NRT/{west},{south},{east},{north}/{days}"
    )
    async with httpx.AsyncClient(timeout=settings.realtime_http_timeout_seconds, follow_redirects=True) as client:
        response = await client.get(endpoint)
    response.raise_for_status()
    content = response.content
    content_hash = hashlib.sha256(content).hexdigest()
    raw_path, processed_path, manifest_path = _paths(settings, region_id, fetched_at)
    raw_path.write_bytes(content)

    rows = list(csv.DictReader(io.StringIO(response.text)))
    parsed_by_source: dict[str, dict[str, Any]] = {}
    for row in rows:
        longitude = _parse_float(row, "longitude")
        latitude = _parse_float(row, "latitude")
        observed_at = _parse_observed_at(row)
        if longitude is None or latitude is None or observed_at is None:
            continue
        source_record_id = _source_record_id(row)
        detection_key = f"{region_id}|{source_record_id}"
        detection_id = f"realtime-{hashlib.sha1(detection_key.encode()).hexdigest()[:20]}"
        parsed_by_source[source_record_id] = (
            {
                "detection_id": detection_id,
                "source_record_id": source_record_id,
                "source": "FIRMS NRT / VIIRS",
                "observed_at": observed_at,
                "detected_at": fetched_at,
                "longitude": longitude,
                "latitude": latitude,
                "confidence": _parse_confidence(row.get("confidence")),
                "status": "candidate",
                "source_asset_id": f"firms-nrt-{content_hash[:16]}",
                "algorithm": "firms_nrt_product_v0.1",
                "attributes": {
                    "source_product": row.get("instrument") or "VIIRS_SNPP_NRT",
                    "source_record_id": source_record_id,
                    "frp_mw": _parse_float(row, "frp"),
                    "brightness_ti4": _parse_float(row, "bright_ti4"),
                    "brightness_ti5": _parse_float(row, "bright_ti5"),
                    "daynight": row.get("daynight"),
                    "raw": _json_safe_row(row),
                },
            }
        )

    # FIRMS can repeat a source record in a response; one source record maps to one candidate.
    parsed = list(parsed_by_source.values())

    observation_id = f"firms-nrt-{region_id}-{content_hash[:24]}"
    latest_observed_at = max((item["observed_at"] for item in parsed), default=None)
    existing_observation = await db.scalar(
        select(RealtimeObservation).where(RealtimeObservation.observation_id == observation_id)
    )
    if existing_observation is None:
        db.add(
            RealtimeObservation(
                observation_id=observation_id,
                region_id=region_id,
                source="FIRMS NRT / VIIRS",
                product="VIIRS_SNPP_NRT",
                observed_at=latest_observed_at or fetched_at,
                fetched_at=fetched_at,
                source_file=str(raw_path.relative_to(settings.resolved_data_dir)),
                metadata_json={
                    "region": region,
                    "endpoint": endpoint.replace(settings.firms_map_key, "<MAP_KEY>"),
                    "sha256": content_hash,
                    "row_count": len(rows),
                    "valid_hotspot_count": len(parsed),
                    "duplicate_hotspot_count": max(0, len(rows) - len(parsed)),
                    "data_source_mode": "realtime_candidate",
                },
            )
        )
    else:
        # Refresh the acquisition timestamp for an unchanged upstream batch so
        # the TTL cache reflects the latest successful API check.
        existing_observation.fetched_at = fetched_at
        existing_observation.observed_at = latest_observed_at or fetched_at
        existing_observation.source_file = str(raw_path.relative_to(settings.resolved_data_dir))
        existing_observation.metadata_json = {
            "region": region,
            "endpoint": endpoint.replace(settings.firms_map_key, "<MAP_KEY>"),
            "sha256": content_hash,
            "row_count": len(rows),
            "valid_hotspot_count": len(parsed),
            "duplicate_hotspot_count": max(0, len(rows) - len(parsed)),
            "data_source_mode": "realtime_candidate",
        }
    for item in parsed:
        existing = await db.scalar(
            select(RealtimeHotspot).where(RealtimeHotspot.detection_id == item["detection_id"])
        )
        if existing is None:
            db.add(
                RealtimeHotspot(
                    detection_id=item["detection_id"],
                    region_id=region_id,
                    observation_id=observation_id,
                    source_record_id=item["source_record_id"],
                    source=item["source"],
                    observed_at=item["observed_at"],
                    detected_at=item["detected_at"],
                    longitude=item["longitude"],
                    latitude=item["latitude"],
                    confidence=item["confidence"],
                    status=item["status"],
                    attributes={
                        **item["attributes"],
                        "source_asset_id": item["source_asset_id"],
                        "algorithm": item["algorithm"],
                    },
                )
            )
        else:
            # Keep idempotency while making the newest observation query complete.
            existing.observation_id = observation_id
            existing.observed_at = item["observed_at"]
            existing.detected_at = item["detected_at"]
            existing.longitude = item["longitude"]
            existing.latitude = item["latitude"]
            existing.confidence = item["confidence"]
            existing.status = item["status"]
            existing.attributes = {
                **item["attributes"],
                "source_asset_id": item["source_asset_id"],
                "algorithm": item["algorithm"],
            }
    await db.commit()

    processed_path.write_text(
        json.dumps(
            {
                "schema_version": "fire.realtime.hotspots.v0.1",
                "region": region,
                "observation_id": observation_id,
                "source": "FIRMS NRT / VIIRS",
                "observed_at": latest_observed_at.isoformat().replace("+00:00", "Z") if latest_observed_at else None,
                "fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
                "data_source_mode": "realtime_candidate",
                "algorithm": "firms_nrt_product_v0.1",
                "hotspots": parsed,
            },
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.isoformat().replace("+00:00", "Z") if isinstance(value, datetime) else str(value),
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "fire.realtime.observation-manifest.v0.1",
                "observation_id": observation_id,
                "region_id": region_id,
                "source": "FIRMS NRT / VIIRS",
                "raw_file": str(raw_path.relative_to(settings.resolved_data_dir)),
                "processed_file": str(processed_path.relative_to(settings.resolved_data_dir)),
                "sha256": content_hash,
                "row_count": len(rows),
                "valid_hotspot_count": len(parsed),
                "duplicate_hotspot_count": max(0, len(rows) - len(parsed)),
                "acquired_at": fetched_at.isoformat().replace("+00:00", "Z"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _prune_files(raw_path.parent, ".csv", settings.realtime_retention_count)
    _prune_files(processed_path.parent, ".json", settings.realtime_retention_count)
    _prune_files(manifest_path.parent, ".json", settings.realtime_retention_count)

    return {
        "ready": True,
        "region_id": region_id,
        "source": "FIRMS NRT / VIIRS",
        "observed_at": latest_observed_at,
        "fetched_at": fetched_at,
        "detection_status": "已完成候选火点提取",
        "hotspots": parsed,
        "total": len(parsed),
        "data_source_mode": "realtime_candidate",
        "cache_hit": False,
        "next_refresh_at": fetched_at + timedelta(minutes=int(region["refresh_minutes"])),
        "source_file": str(raw_path.relative_to(settings.resolved_data_dir)),
        "processed_file": str(processed_path.relative_to(settings.resolved_data_dir)),
    }
