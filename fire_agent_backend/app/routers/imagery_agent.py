from __future__ import annotations

import hashlib
import base64
import io
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import numpy as np
import rasterio
from affine import Affine
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from PIL import Image
from pydantic import BaseModel, Field, field_validator
from rasterio.features import shapes, sieve
from rasterio.warp import transform_bounds, transform_geom
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, get_db
from app.models.event import FireEvent
from app.models.imagery import ImageryAcquisitionTask
from app.services.imagery_products import build_multiband_product
from app.visual_verification.models import ImageryAssetCatalogRecord, RemoteSensingAnalysisRecord, VisualCaseAssetRecord, VisualVerificationCaseRecord
from app.visual_verification.image_processing.paths import SafeImagePathResolver
from app.visual_verification.providers.qwen import HttpxQwenChatTransport, QwenProviderError, _image_data_url

router = APIRouter(prefix="/data-agent/imagery", tags=["imagery-agent"])
STAC = "https://earth-search.aws.element84.com/v1/search"
PORTALS = {
    "sentinel": "https://browser.dataspace.copernicus.eu/",
    "landsat": "https://earthexplorer.usgs.gov/",
    "goes": "https://www.star.nesdis.noaa.gov/goes/",
}
REQUIRED = {
    "primary": ["B02", "B03", "B04", "B08", "B12"],
    "comparison_pre": ["B02", "B03", "B04", "B08", "B12"],
    "comparison_post": ["B02", "B03", "B04", "B08", "B12"],
}
S2_ASSETS = {"B02": "blue", "B03": "green", "B04": "red", "B08": "nir", "B12": "swir22"}
LANDSAT_ASSETS = {"B02": "blue", "B03": "green", "B04": "red", "B08": "nir08", "B12": "swir22"}


class AcquireRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=80)
    phase: str = "primary"
    start_at: datetime | None = None
    end_at: datetime | None = None
    bbox: tuple[float, float, float, float] | None = None
    satellite: str = "auto"


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)[:180]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _catalog_path(event_id: str, scene_id: str, band: str) -> Path:
    root = get_settings().resolved_data_dir / "raw" / "imagery"
    return root / _safe(event_id) / _safe(scene_id) / (band + ".tif")


def _is_trusted(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "earth-search.aws.element84.com"
        or host == "s3.amazonaws.com"
        or host.endswith(".amazonaws.com")
        or host.endswith(".copernicus.eu")
    )


def _task_data(task: ImageryAcquisitionTask) -> dict:
    age = (datetime.now(UTC) - _utc(task.started_at)).total_seconds() if task.started_at else 0
    status = task.status
    message = task.message
    if status in ("searching", "downloading") and age >= 60:
        message += " 已等待超过一分钟，可用以下场景链接或官方入口手动下载；后台任务仍在继续。"
    return {
        "task_id": task.task_id, "event_id": task.event_id, "phase": task.phase,
        "status": status, "message": message, "scene_id": task.scene_id,
        "required_bands": task.required_bands or [],
        "available_bands": task.available_bands or [],
        "missing_bands": sorted(set(task.required_bands or []) - set(task.available_bands or [])),
        "local_files": task.local_files or {}, "source": task.source_name,
        "download_url": task.download_url or PORTALS["sentinel"],
        "manual_import_folder": "data/raw/imagery/import",
        "search": {"start_at": task.time_start.isoformat(), "end_at": task.time_end.isoformat(), **(task.details or {})},
        "elapsed_seconds": int(age),
    }


async def _event(db: AsyncSession, event_id: str) -> FireEvent:
    event = await db.scalar(select(FireEvent).where(FireEvent.event_id == event_id))
    if event is None:
        raise HTTPException(404, "火灾事件不存在")
    lon, lat = event.ignition_longitude, event.ignition_latitude
    if lon is None or lat is None or not (-125 <= lon <= -114 and 32 <= lat <= 42.2):
        raise HTTPException(422, "当前影像数据库只支持加利福尼亚州事件")
    return event


def _time_window(event: FireEvent, request: AcquireRequest) -> tuple[datetime, datetime]:
    anchor = _utc(event.started_at)
    if request.phase == "comparison_pre":
        defaults = (anchor - timedelta(days=35), anchor - timedelta(days=1))
    elif request.phase == "comparison_post":
        end = _utc(event.closed_at) if event.closed_at else anchor + timedelta(days=100)
        defaults = (end + timedelta(days=1), end + timedelta(days=35))
    else:
        defaults = (anchor, anchor + timedelta(days=1))
    start = _utc(request.start_at) if request.start_at else defaults[0]
    end = _utc(request.end_at) if request.end_at else defaults[1]
    if end <= start or (end - start).days > 365:
        raise HTTPException(422, "影像查询时段无效或超过一年")
    if request.phase == "primary" and (end - start > timedelta(days=1) or start < anchor or (event.closed_at and end > _utc(event.closed_at))):
        raise HTTPException(422, "火点核验只允许火灾期间连续 24 小时内的同期影像；请指定候选火点对应时段")
    return start, end


async def _save_asset(
    db: AsyncSession, task: ImageryAcquisitionTask, scene: dict,
    band: str, path: Path, url: str, source: str,
) -> None:
    digest = _sha256_file(path)
    asset_id = "img_" + hashlib.sha256((task.event_id + ":" + scene["id"] + ":" + band).encode()).hexdigest()[:28]
    existing = await db.scalar(select(ImageryAssetCatalogRecord).where(ImageryAssetCatalogRecord.asset_id == asset_id))
    acquired = datetime.fromisoformat(scene["properties"]["datetime"].replace("Z", "+00:00"))
    with rasterio.open(path) as raster:
        bounds = transform_bounds(raster.crs, "EPSG:4326", *raster.bounds) if raster.crs else None
        resolution = abs(raster.res[0])
        crs = str(raster.crs) if raster.crs else None
    footprint = scene.get("geometry")
    if not footprint and bounds:
        w, s, e, n = bounds
        footprint = {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
    relative = path.relative_to(get_settings().resolved_data_dir).as_posix()
    metadata = {"scene_id": scene["id"], "download_url": url, "local_path": str(path), "provider": source}
    if existing:
        existing.content_uri = relative
        existing.checksum_sha256 = digest
        existing.quality_status = "available"
        existing.metadata_json = metadata
    else:
        db.add(ImageryAssetCatalogRecord(
            asset_id=asset_id, event_id=task.event_id, source_name=source,
            source_type="stac_download", analysis_phase=task.phase, mime_type="image/tiff",
            time_start=acquired, time_end=acquired, content_uri=relative,
            footprint_geojson=footprint, crs=crs, resolution_m=resolution,
            bands=[band], cloud_cover=scene.get("properties", {}).get("eo:cloud_cover"),
            quality_status="available", checksum_sha256=digest,
            metadata_json=metadata, is_simulated=False,
        ))
    files = dict(task.local_files or {})
    files[band] = str(path)
    task.local_files = files
    task.available_bands = sorted(files)
    await db.commit()


async def _set(task: ImageryAcquisitionTask, db: AsyncSession, status: str, message: str) -> None:
    task.status, task.message = status, message
    await db.commit()


async def _search(client: httpx.AsyncClient, collection: str, bbox: list[float], start: datetime, end: datetime) -> list[dict]:
    response = await client.post(STAC, json={
        "collections": [collection], "bbox": bbox, "limit": 16,
        "datetime": start.isoformat().replace("+00:00", "Z") + "/" + end.isoformat().replace("+00:00", "Z"),
    })
    response.raise_for_status()
    features = response.json().get("features", [])
    return sorted(features, key=lambda item: (item.get("properties", {}).get("eo:cloud_cover") or 100, item.get("properties", {}).get("datetime") or ""))


async def _download(client: httpx.AsyncClient, url: str, path: Path) -> None:
    if not _is_trusted(url):
        raise ValueError("STAC 返回的影像链接不在可信来源范围内")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".part")
    count = 0
    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            if not _is_trusted(str(response.url)):
                raise ValueError("影像下载发生了不可信重定向")
            with temporary.open("wb") as output:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    count += len(chunk)
                    if count > 350 * 1024 * 1024:
                        raise ValueError("单波段影像超过 350 MB，请从场景链接手动下载或缩小范围")
                    output.write(chunk)
        if count < 1024:
            raise ValueError("下载文件过小，无法作为影像使用")
        with rasterio.open(temporary) as raster:
            if raster.count < 1 or raster.crs is None:
                raise ValueError("下载影像缺少波段或坐标参考")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


async def _run_acquisition(task_id: str) -> None:
    async with AsyncSessionLocal() as db:
        task = await db.scalar(select(ImageryAcquisitionTask).where(ImageryAcquisitionTask.task_id == task_id))
        if task is None:
            return
        event = await db.scalar(select(FireEvent).where(FireEvent.event_id == task.event_id))
        if event is None:
            await _set(task, db, "failed", "火灾事件已不存在")
            return
        bbox = (task.details or {}).get("bbox") or [
            event.ignition_longitude - .08, event.ignition_latitude - .08,
            event.ignition_longitude + .08, event.ignition_latitude + .08,
        ]
        requested_satellite = (task.details or {}).get("satellite", "auto")
        collections = (
            ["sentinel-2-l2a"] if requested_satellite == "sentinel"
            else ["landsat-c2-l2"] if requested_satellite == "landsat"
            else ["sentinel-2-l2a", "landsat-c2-l2"]
        )
        errors: list[str] = []
        missing: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(25, read=90), follow_redirects=True) as client:
                selected = None
                asset_map = S2_ASSETS
                source = "Element84 Earth Search / Sentinel-2 L2A"
                for collection in collections:
                    try:
                        scenes = await _search(client, collection, bbox, _utc(task.time_start), _utc(task.time_end))
                    except (httpx.HTTPError, ValueError) as exc:
                        errors.append(collection + ": " + str(exc))
                        continue
                    if not scenes:
                        errors.append(collection + ": 查询时段及范围内没有场景")
                        continue
                    mapping = S2_ASSETS if collection == "sentinel-2-l2a" else LANDSAT_ASSETS
                    for scene in scenes:
                        assets = scene.get("assets", {})
                        absent = [band for band in task.required_bands if mapping[band] not in assets]
                        if absent:
                            missing.extend(absent)
                            continue
                        selected, asset_map = scene, mapping
                        source = "Element84 Earth Search / " + collection
                        break
                    if selected:
                        break
                if selected is None:
                    reason = "查询条件内未找到具备所需波段的影像。" if missing else "查询条件内没有符合要求的同期影像，或数据接口不可用。"
                    task.details = {**(task.details or {}), "search_errors": errors, "missing_bands": sorted(set(missing))}
                    task.download_url = PORTALS["sentinel"] if requested_satellite != "landsat" else PORTALS["landsat"]
                    await _set(task, db, "missing_bands" if missing else "no_match" if not any("HTTP" in e or "timed out" in e for e in errors) else "network_error", reason + " " + "；".join(errors[:3]))
                    return
                task.scene_id = selected["id"]
                task.source_name = source
                task.download_url = selected["assets"][asset_map[task.required_bands[0]]].get("href") or PORTALS["sentinel"]
                task.details = {**(task.details or {}), "scene_time": selected.get("properties", {}).get("datetime"), "cloud_cover": selected.get("properties", {}).get("eo:cloud_cover")}
                await _set(task, db, "downloading", "已选中真实场景 " + selected["id"] + "，正在获取所需波段")
                for band in task.required_bands:
                    asset = selected["assets"][asset_map[band]]
                    url = asset.get("href", "")
                    path = _catalog_path(task.event_id, selected["id"], band)
                    if not path.is_file():
                        await _download(client, url, path)
                    await _save_asset(db, task, selected, band, path, url, source)
                product_id = await _register_product_and_link(db, task, selected)
                await _set(task, db, "completed", "已下载并登记全部所需波段及分析产品 " + product_id)
        except (httpx.HTTPError, OSError, ValueError, rasterio.errors.RasterioError) as exc:
            task.details = {**(task.details or {}), "error_type": type(exc).__name__}
            if not task.download_url:
                task.download_url = PORTALS["sentinel"]
            await _set(task, db, "failed", "影像下载或校验失败：" + str(exc))


@router.post("/acquire", status_code=202)
async def acquire(request: AcquireRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)) -> dict:
    if request.phase not in REQUIRED or request.satellite not in ("auto", "sentinel", "landsat"):
        raise HTTPException(422, "影像用途或卫星类型不支持")
    event = await _event(db, request.event_id)
    start, end = _time_window(event, request)
    bbox = list(request.bbox) if request.bbox else [
        event.ignition_longitude - .08, event.ignition_latitude - .08,
        event.ignition_longitude + .08, event.ignition_latitude + .08,
    ]
    if not (-125 <= bbox[0] < bbox[2] <= -114 and 32 <= bbox[1] < bbox[3] <= 42.2):
        raise HTTPException(422, "查询范围必须在加利福尼亚州内")
    required = REQUIRED[request.phase]
    rows = (await db.execute(select(ImageryAssetCatalogRecord).where(
        ImageryAssetCatalogRecord.event_id == request.event_id,
        ImageryAssetCatalogRecord.analysis_phase == request.phase,
        ImageryAssetCatalogRecord.time_start >= start,
        ImageryAssetCatalogRecord.time_start <= end,
        ImageryAssetCatalogRecord.quality_status == "available",
    ))).scalars().all()
    by_scene: dict[str, dict[str, str]] = {}
    products: set[str] = set()
    for row in rows:
        scene = (row.metadata_json or {}).get("scene_id")
        path = (row.metadata_json or {}).get("local_path")
        if scene and path and Path(path).is_file():
            if row.source_type == "analysis_composite":
                products.add(scene)
            for band in row.bands or []:
                by_scene.setdefault(scene, {})[band] = path
    reusable = next(((scene, files) for scene, files in by_scene.items() if scene in products and set(required) <= set(files)), None)
    task = ImageryAcquisitionTask(
        task_id="imgtask_" + uuid4().hex[:20], event_id=request.event_id, phase=request.phase,
        time_start=start, time_end=end, status="reused" if reusable else "searching",
        message="复用已有影像和所需波段" if reusable else "正在查询 Element84 Earth Search 场景目录",
        scene_id=reusable[0] if reusable else None, required_bands=required,
        available_bands=sorted(reusable[1]) if reusable else [], local_files=reusable[1] if reusable else {},
        details={"bbox": bbox, "satellite": request.satellite},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    if not reusable:
        background_tasks.add_task(_run_acquisition, task.task_id)
    return {"ok": True, "data": _task_data(task)}


@router.get("/tasks/{task_id}")
async def task_status(task_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    task = await db.scalar(select(ImageryAcquisitionTask).where(ImageryAcquisitionTask.task_id == task_id))
    if not task:
        raise HTTPException(404, "影像任务不存在")
    return {"ok": True, "data": _task_data(task)}


@router.get("/catalog/{event_id}")
async def catalog(event_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    await _event(db, event_id)
    rows = (await db.execute(select(ImageryAssetCatalogRecord).where(
        ImageryAssetCatalogRecord.event_id == event_id
    ).order_by(ImageryAssetCatalogRecord.time_start.desc()))).scalars().all()
    return {"ok": True, "data": [
        {"asset_id": row.asset_id, "source_type": row.source_type, "scene_id": (row.metadata_json or {}).get("scene_id"),
         "satellite": row.source_name, "acquired_at": row.time_start, "phase": row.analysis_phase,
         "bands": row.bands, "resolution_m": row.resolution_m, "footprint": row.footprint_geojson,
         "download_url": (row.metadata_json or {}).get("download_url"),
         "local_path": (row.metadata_json or {}).get("local_path"),
         "available_locally": bool((row.metadata_json or {}).get("local_path") and Path((row.metadata_json or {})["local_path"]).is_file()),
         "quality_status": row.quality_status, "is_simulated": row.is_simulated}
        for row in rows
    ]}


class HistoricalEventRequest(BaseModel):
    event_id: str = Field(pattern=r"^[a-z0-9_]{4,80}$")
    name: str = Field(min_length=2, max_length=200)
    started_at: datetime
    ended_at: datetime | None = None
    longitude: float = Field(ge=-125, le=-114)
    latitude: float = Field(ge=32, le=42.2)
    perimeter_geojson: dict | None = None
    source_url: str = ""


@router.get("/events")
async def historical_events(db: AsyncSession = Depends(get_db)) -> dict:
    rows = (await db.execute(select(FireEvent).where(FireEvent.source_mode == "historical").order_by(FireEvent.started_at.desc()))).scalars().all()
    return {"ok": True, "data": [
        {"event_id": row.event_id, "name": row.name, "started_at": row.started_at,
         "ended_at": row.closed_at, "longitude": row.ignition_longitude,
         "latitude": row.ignition_latitude,
         "perimeter_geojson": (row.metadata_json or {}).get("perimeter_geojson"),
         "source_url": (row.metadata_json or {}).get("source_url")}
        for row in rows if row.ignition_longitude is not None and row.ignition_latitude is not None
        and -125 <= row.ignition_longitude <= -114 and 32 <= row.ignition_latitude <= 42.2
    ]}


@router.post("/events", status_code=201)
async def register_event(request: HistoricalEventRequest, db: AsyncSession = Depends(get_db)) -> dict:
    if request.ended_at and _utc(request.ended_at) < _utc(request.started_at):
        raise HTTPException(422, "火灾结束时间早于开始时间")
    if await db.scalar(select(FireEvent).where(FireEvent.event_id == request.event_id)):
        raise HTTPException(409, "事件 ID 已存在")
    event = FireEvent(
        event_id=request.event_id, name=request.name, status="archived",
        scenario_id=request.event_id, source_mode="historical",
        ignition_longitude=request.longitude, ignition_latitude=request.latitude,
        started_at=_utc(request.started_at), closed_at=_utc(request.ended_at) if request.ended_at else None,
        metadata_json={"region": "California", "perimeter_geojson": request.perimeter_geojson,
                       "source_url": request.source_url},
    )
    db.add(event)
    await db.commit()
    return {"ok": True, "data": {"event_id": event.event_id, "name": event.name}}


class LocalImportRequest(BaseModel):
    event_id: str
    phase: str
    scene_id: str
    acquired_at: datetime
    relative_path: str
    bands: list[str] = Field(min_length=1)
    source_url: str = ""


@router.post("/register-local")
async def register_local(request: LocalImportRequest, db: AsyncSession = Depends(get_db)) -> dict:
    await _event(db, request.event_id)
    if request.phase not in REQUIRED or any(band not in REQUIRED["primary"] for band in request.bands):
        raise HTTPException(422, "用途或波段不支持")
    root = (get_settings().resolved_data_dir / "raw" / "imagery" / "import").resolve()
    path = (root / request.relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "文件不在影像导入目录：" + str(root))
    if path.suffix.lower() not in (".tif", ".tiff"):
        raise HTTPException(422, "目前只支持地理配准 GeoTIFF")
    try:
        with rasterio.open(path) as raster:
            if raster.count != len(request.bands) or raster.crs is None:
                raise HTTPException(422, "GeoTIFF 波段数量、声明波段或坐标参考不匹配")
            w, s, e, n = transform_bounds(raster.crs, "EPSG:4326", *raster.bounds)
            if e < -125 or w > -114 or n < 32 or s > 42.2:
                raise HTTPException(422, "影像覆盖范围不含加利福尼亚州")
            descriptions = [x.upper() for x in raster.descriptions if x]
            if descriptions and [("B0" + x[1:] if len(x) == 2 and x.startswith("B") else x) for x in descriptions] != request.bands:
                raise HTTPException(422, "文件内的波段描述与登记波段不一致")
            crs, resolution = str(raster.crs), abs(raster.res[0])
            footprint = {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
    except rasterio.errors.RasterioError as exc:
        raise HTTPException(422, "无法读取 GeoTIFF：" + str(exc)) from exc
    digest = _sha256_file(path)
    asset_id = "img_" + hashlib.sha256((request.event_id + ":" + request.scene_id + ":" + ",".join(request.bands)).encode()).hexdigest()[:28]
    existing = await db.scalar(select(ImageryAssetCatalogRecord).where(ImageryAssetCatalogRecord.asset_id == asset_id))
    if existing:
        if existing.checksum_sha256 == digest:
            return {"ok": True, "data": {"asset_id": asset_id, "status": "reused", "bands": existing.bands}}
        raise HTTPException(409, "同一场景和波段已有不同内容；请核对影像")
    row = ImageryAssetCatalogRecord(
        asset_id=asset_id, event_id=request.event_id, source_name="manual_import",
        source_type="local_geotiff", analysis_phase=request.phase, mime_type="image/tiff",
        time_start=_utc(request.acquired_at), time_end=_utc(request.acquired_at),
        content_uri=path.relative_to(get_settings().resolved_data_dir).as_posix(),
        footprint_geojson=footprint, crs=crs, resolution_m=resolution,
        bands=request.bands, quality_status="available" if descriptions else "unassessed",
        checksum_sha256=digest, is_simulated=False,
        metadata_json={"scene_id": request.scene_id, "download_url": request.source_url,
                       "local_path": str(path), "band_identity": "GeoTIFF_description" if descriptions else "user_declared"},
    )
    db.add(row)
    await db.flush()
    linked = 0
    if descriptions and set(REQUIRED[request.phase]) <= set(request.bands):
        cases = (await db.execute(select(VisualVerificationCaseRecord).where(
            VisualVerificationCaseRecord.event_id == request.event_id,
            VisualVerificationCaseRecord.is_simulated.is_(False),
        ))).scalars().all()
        for case in cases:
            if request.phase == "primary" and abs((_utc(case.observed_at) - _utc(request.acquired_at)).total_seconds()) > 86400:
                continue
            if not (w <= case.longitude <= e and s <= case.latitude <= n):
                continue
            db.add(VisualCaseAssetRecord(
                visual_case_id=case.visual_case_id, source_asset_id=asset_id,
                asset_role=request.phase, source_type="local_geotiff",
                source_name="manual_import", mime_type="image/tiff",
                acquired_at=_utc(request.acquired_at), content_uri=row.content_uri,
                quality_status="available", checksum_sha256=digest, is_simulated=False,
            ))
            if request.phase == "primary" and case.status in ("received", "imagery_searching", "failed"):
                case.imagery_status, case.status = "available", "imagery_ready"
            linked += 1
    await db.commit()
    return {"ok": True, "data": {"asset_id": asset_id, "status": "registered", "bands": request.bands,
                                 "analysis_ready": bool(descriptions), "linked_visual_cases": linked}}



@router.post("/upload")
async def upload_imagery(
    body: Request,
    event_id: str = Query(),
    phase: str = Query(),
    scene_id: str = Query(),
    acquired_at: datetime = Query(),
    bands: str = Query(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a GeoTIFF as the raw request body, then validate and catalog it."""
    declared = [value.strip().upper() for value in bands.split(",") if value.strip()]
    if not declared:
        raise HTTPException(422, "必须声明影像文件的波段")
    root = get_settings().resolved_data_dir / "raw" / "imagery" / "import"
    root.mkdir(parents=True, exist_ok=True)
    name = _safe(scene_id) + "_" + uuid4().hex[:12] + ".tif"
    target = root / name
    received = 0
    try:
        with target.open("wb") as destination:
            async for chunk in body.stream():
                received += len(chunk)
                if received > 350 * 1024 * 1024:
                    raise HTTPException(413, "单文件超过 350 MB，请将文件放入 data/raw/imagery/import 后登记")
                destination.write(chunk)
        if received < 1024:
            raise HTTPException(422, "上传内容过小，不是有效 GeoTIFF")
        request = LocalImportRequest(
            event_id=event_id, phase=phase, scene_id=scene_id,
            acquired_at=acquired_at, relative_path=name, bands=declared,
        )
        return await register_local(request, db)
    except Exception:
        target.unlink(missing_ok=True)
        raise


async def _register_product_and_link(db: AsyncSession, task: ImageryAcquisitionTask, scene: dict) -> str:
    root = get_settings().resolved_data_dir
    target = root / "processed" / "imagery" / _safe(task.event_id) / (_safe(scene["id"]) + "_" + task.phase + ".tif")
    path, product = build_multiband_product(task.local_files, target, (task.details or {})["bbox"])
    asset_id = "img_" + hashlib.sha256((task.event_id + ":" + scene["id"] + ":" + task.phase + ":multiband").encode()).hexdigest()[:28]
    acquired = datetime.fromisoformat(scene["properties"]["datetime"].replace("Z", "+00:00"))
    existing = await db.scalar(select(ImageryAssetCatalogRecord).where(ImageryAssetCatalogRecord.asset_id == asset_id))
    if existing is None:
        existing = ImageryAssetCatalogRecord(
            asset_id=asset_id, event_id=task.event_id, source_name=task.source_name or "STAC",
            source_type="analysis_composite", analysis_phase=task.phase,
            mime_type="image/tiff", time_start=acquired, time_end=acquired,
            content_uri=path.relative_to(root).as_posix(),
            footprint_geojson=scene.get("geometry"), crs=product["crs"],
            resolution_m=None, bands=["B04", "B03", "B02", "B08", "B12"],
            cloud_cover=scene.get("properties", {}).get("eo:cloud_cover"),
            quality_status="available", checksum_sha256=_sha256_file(path),
            metadata_json={"scene_id": scene["id"], "local_path": str(path),
                           "download_url": task.download_url, "product": product},
            is_simulated=False,
        )
        db.add(existing)
        await db.flush()
    cases = (await db.execute(select(VisualVerificationCaseRecord).where(
        VisualVerificationCaseRecord.event_id == task.event_id,
        VisualVerificationCaseRecord.is_simulated.is_(False),
    ).order_by(VisualVerificationCaseRecord.observed_at.desc()))).scalars().all()
    if not cases:
        event = await db.scalar(select(FireEvent).where(FireEvent.event_id == task.event_id))
        if event:
            from app.services.workflow_runtime_service import _auto_import_candidate
            imported = await _auto_import_candidate(db, event)
            cases = [imported] if imported else []
    linked = 0
    for case in cases:
        if case is None:
            continue
        if task.phase == "primary" and abs((_utc(case.observed_at) - acquired).total_seconds()) > 86400:
            continue
        scene_bbox = scene.get("bbox") or []
        if len(scene_bbox) >= 4 and not (
            scene_bbox[0] <= case.longitude <= scene_bbox[2]
            and scene_bbox[1] <= case.latitude <= scene_bbox[3]
        ):
            continue
        attachment = await db.scalar(select(VisualCaseAssetRecord).where(
            VisualCaseAssetRecord.visual_case_id == case.visual_case_id,
            VisualCaseAssetRecord.source_asset_id == asset_id,
            VisualCaseAssetRecord.asset_role == task.phase,
        ))
        if attachment is None:
            db.add(VisualCaseAssetRecord(
                visual_case_id=case.visual_case_id, source_asset_id=asset_id,
                asset_role=task.phase, source_type="analysis_composite",
                source_name=task.source_name, mime_type="image/tiff",
                acquired_at=acquired, content_uri=existing.content_uri,
                quality_status="available", checksum_sha256=existing.checksum_sha256,
                is_simulated=False,
            ))
        if task.phase == "primary" and case.status in ("received", "imagery_searching", "failed"):
            case.imagery_status = "available"
            case.status = "imagery_ready"
        linked += 1
    task.details = {**(task.details or {}), "product_asset_id": asset_id, "linked_visual_cases": linked}
    await db.commit()
    return asset_id


class QwenRecoveryAssessment(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    affected_features: list[str] = Field(default_factory=list, max_length=12)
    reconstruction_advice: list[str] = Field(default_factory=list, max_length=12)
    limitations: list[str] = Field(default_factory=list, max_length=12)


class QwenImageryPairRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=80)
    before_asset_id: str = Field(min_length=1, max_length=200)
    after_asset_id: str = Field(min_length=1, max_length=200)


class QwenImageryPairAssessment(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    affected_region: list[str] = Field(default_factory=list, max_length=12)
    affected_features: list[str] = Field(default_factory=list, max_length=12)
    reconstruction_advice: list[str] = Field(default_factory=list, max_length=12)
    limitations: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("affected_region", "affected_features", "reconstruction_advice", "limitations", mode="before")
    @classmethod
    def coerce_qwen_list(cls, value: object) -> list[str]:
        """Qwen sometimes returns a paragraph instead of the requested JSON array."""
        if value is None:
            return []
        if isinstance(value, str):
            parts = [part.strip(" -•\t") for part in re.split(r"\r?\n|[；;]", value) if part.strip(" -•\t")]
            return parts[:12]
        if isinstance(value, (list, tuple)):
            normalized: list[str] = []
            for part in value:
                if isinstance(part, dict):
                    text = "；".join(f"{key}：{item}" for key, item in part.items() if str(item).strip())
                else:
                    text = str(part).strip()
                if text:
                    normalized.append(text)
            return normalized[:12]
        return [str(value).strip()]


def _catalog_preview_data_url(path: Path, *, max_dimension: int = 1400) -> str:
    """Convert a local catalog GeoTIFF into a compact RGB JPEG for Qwen."""
    with rasterio.open(path) as raster:
        if raster.count < 1:
            raise ValueError("影像没有可读取的波段")
        indexes = [1, 2, 3] if raster.count >= 3 else [1]
        scale = min(1.0, max_dimension / max(raster.width, raster.height))
        out_width = max(1, int(raster.width * scale))
        out_height = max(1, int(raster.height * scale))
        data = raster.read(indexes, out_shape=(len(indexes), out_height, out_width), resampling=rasterio.enums.Resampling.bilinear).astype("float32")
    if data.shape[0] == 1:
        data = np.repeat(data, 3, axis=0)
    channels = []
    for channel in data[:3]:
        valid = channel[np.isfinite(channel)]
        low, high = np.percentile(valid, [2, 98]) if valid.size else (0.0, 1.0)
        if high <= low:
            high = low + 1.0
        channels.append(np.clip((channel - low) / (high - low) * 255, 0, 255).astype("uint8"))
    image = Image.fromarray(np.moveaxis(np.stack(channels), 0, -1), mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _catalog_asset_path(row: ImageryAssetCatalogRecord) -> Path:
    settings = get_settings()
    metadata_path = (row.metadata_json or {}).get("local_path")
    candidate = Path(str(metadata_path)) if metadata_path else settings.resolved_data_dir / row.content_uri
    if not candidate.is_absolute():
        candidate = settings.resolved_data_dir / candidate
    resolved = candidate.resolve()
    root = settings.resolved_data_dir.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("影像路径不在数据目录内")
    if not resolved.is_file():
        raise FileNotFoundError(str(resolved))
    return resolved


def _footprint_overlap_ratio(before: ImageryAssetCatalogRecord, after: ImageryAssetCatalogRecord) -> float | None:
    """Return intersection over the smaller footprint using catalog bounds."""
    def bounds(footprint: object) -> tuple[float, float, float, float] | None:
        points: list[tuple[float, float]] = []
        def collect(value: object) -> None:
            if not isinstance(value, list):
                return
            if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
                points.append((float(value[0]), float(value[1])))
                return
            for item in value:
                collect(item)
        collect((footprint or {}).get("coordinates") if isinstance(footprint, dict) else None)
        if not points:
            return None
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return min(xs), min(ys), max(xs), max(ys)

    first, second = bounds(before.footprint_geojson), bounds(after.footprint_geojson)
    if not first or not second:
        return None
    intersection = max(0.0, min(first[2], second[2]) - max(first[0], second[0])) * max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    smaller = min(first_area, second_area)
    return intersection / smaller if smaller else None


def _window_sum(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return values.astype("float32")
    padded = np.pad(values.astype("float32"), radius, mode="constant")
    integral = np.pad(padded, ((1, 0), (1, 0)), mode="constant").cumsum(axis=0).cumsum(axis=1)
    size = radius * 2 + 1
    return integral[size:, size:] - integral[:-size, size:] - integral[size:, :-size] + integral[:-size, :-size]


def _binary_close_open(mask: np.ndarray) -> np.ndarray:
    close_radius = 3
    close_size = (close_radius * 2 + 1) ** 2
    dilated = _window_sum(mask, close_radius) > 0
    closed = _window_sum(dilated, close_radius) >= close_size
    open_radius = 1
    open_size = (open_radius * 2 + 1) ** 2
    eroded = _window_sum(closed, open_radius) >= open_size
    return _window_sum(eroded, open_radius) > 0


def _polygon_area(geometry: dict) -> float:
    if geometry.get("type") != "Polygon":
        return 0.0
    ring = (geometry.get("coordinates") or [[]])[0]
    if len(ring) < 4:
        return 0.0
    return abs(sum(
        float(ring[index][0]) * float(ring[(index + 1) % len(ring)][1])
        - float(ring[(index + 1) % len(ring)][0]) * float(ring[index][1])
        for index in range(len(ring))
    ) / 2.0)


def _rgb_change_geojson(before_path: Path, after_path: Path) -> dict:
    """Create a small set of broad qualitative change polygons from aligned RGB rasters."""
    with rasterio.open(before_path) as before, rasterio.open(after_path) as after:
        indexes_before = [1, 2, 3] if before.count >= 3 else [1]
        indexes_after = [1, 2, 3] if after.count >= 3 else [1]
        scale = min(1.0, 520 / max(before.width, before.height))
        out_width = max(1, int(round(before.width * scale)))
        out_height = max(1, int(round(before.height * scale)))
        before_data = before.read(
            indexes_before,
            out_shape=(len(indexes_before), out_height, out_width),
            resampling=rasterio.enums.Resampling.bilinear,
            masked=True,
        ).astype("float32")
        after_data = after.read(
            indexes_after,
            out_shape=(len(indexes_after), out_height, out_width),
            resampling=rasterio.enums.Resampling.bilinear,
            masked=True,
        ).astype("float32")
        if before_data.shape[0] == 1:
            before_data = np.repeat(before_data, 3, axis=0)
        if after_data.shape[0] == 1:
            after_data = np.repeat(after_data, 3, axis=0)
        before_mask = np.ma.getmaskarray(before_data).any(axis=0)
        after_mask = np.ma.getmaskarray(after_data).any(axis=0)
        before_data = np.ma.filled(before_data, np.nan)
        after_data = np.ma.filled(after_data, np.nan)
        valid = np.isfinite(before_data).all(axis=0) & np.isfinite(after_data).all(axis=0)
        valid &= ~before_mask & ~after_mask
        if not valid.any():
            raise ValueError("两期 RGB 影像没有共同有效像元")
        normalized: list[np.ndarray] = [np.zeros_like(before_data), np.zeros_like(after_data)]
        for channel_index in range(3):
            combined = np.concatenate((before_data[channel_index][valid], after_data[channel_index][valid]))
            low, high = np.percentile(combined, [2, 98])
            if high <= low:
                high = low + 1.0
            for data_index, data in enumerate((before_data, after_data)):
                normalized[data_index][channel_index] = np.clip((data[channel_index] - low) / (high - low), 0, 1)
        before_intensity = np.mean(normalized[0], axis=0)
        after_intensity = np.mean(normalized[1], axis=0)
        before_chroma = normalized[0] / np.maximum(np.sum(normalized[0], axis=0, keepdims=True), 0.08)
        after_chroma = normalized[1] / np.maximum(np.sum(normalized[1], axis=0, keepdims=True), 0.08)
        chroma_change = np.mean(np.abs(before_chroma - after_chroma), axis=0)
        intensity_change = np.abs(before_intensity - after_intensity)
        raw_change = chroma_change * 0.72 + intensity_change * 0.28
        change = _window_sum(np.where(valid, raw_change, 0.0), 2) / 25.0
        support = _window_sum(valid, 2)
        change = np.divide(change, np.maximum(support / 25.0, 0.4), out=np.zeros_like(change), where=support > 0)
        scores = change[valid]
        threshold = max(float(np.percentile(scores, 88)), float(scores.mean() + scores.std() * 0.85))
        classes = np.zeros(change.shape, dtype="uint8")
        classes[valid & (change >= threshold)] = 1
        border_y = max(3, int(out_height * 0.025))
        border_x = max(3, int(out_width * 0.025))
        classes[:border_y, :] = 0
        classes[-border_y:, :] = 0
        classes[:, :border_x] = 0
        classes[:, -border_x:] = 0
        classes = _binary_close_open(classes > 0).astype("uint8")
        minimum_pixels = max(120, int(classes.size * 0.0025))
        classes = sieve(classes, size=minimum_pixels, connectivity=8)
        analysis_transform = before.transform * Affine.scale(before.width / out_width, before.height / out_height)
        candidates: list[tuple[float, dict]] = []
        for shape, value in shapes(classes, mask=classes > 0, transform=analysis_transform):
            severity = int(value)
            if severity != 1:
                continue
            candidates.append((_polygon_area(shape), shape))
        candidates.sort(key=lambda item: item[0], reverse=True)
        largest_area = candidates[0][0] if candidates else 0.0
        selected = [item for item in candidates if item[0] >= largest_area * 0.08][:6]
        features: list[dict] = []
        for area, shape in selected:
            geometry = shape
            if before.crs and str(before.crs) != "EPSG:4326":
                geometry = transform_geom(before.crs, "EPSG:4326", geometry, precision=6)
            features.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "change_score": "qualitative_change",
                    "source": "rgb_pixel_change",
                    "relative_area": round(area / largest_area, 4) if largest_area else 0.0,
                },
            })
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "classification": "qualitative_rgb_change",
            "thresholds": {
                "change_percentile": 88,
                "minimum_component_pixels": minimum_pixels,
                "maximum_regions": 6,
            },
            "feature_count": len(features),
        },
    }


@router.post("/visual-assess")
async def assess_catalog_pair_with_qwen(payload: QwenImageryPairRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Compare existing RGB catalog imagery when no five-band change product exists."""
    settings = get_settings()
    key = settings.qwen_vl_api_key.get_secret_value()
    if not key:
        raise HTTPException(status_code=503, detail="QWEN_VL_API_KEY is not configured")
    rows = (await db.execute(select(ImageryAssetCatalogRecord).where(
        ImageryAssetCatalogRecord.event_id == payload.event_id,
        ImageryAssetCatalogRecord.asset_id.in_([payload.before_asset_id, payload.after_asset_id]),
    ))).scalars().all()
    by_id = {row.asset_id: row for row in rows}
    before = by_id.get(payload.before_asset_id)
    after = by_id.get(payload.after_asset_id)
    if before is None or after is None:
        raise HTTPException(status_code=404, detail="灾前或灾后影像不存在")
    overlap = _footprint_overlap_ratio(before, after)
    if overlap is None:
        raise HTTPException(status_code=422, detail="灾前、灾后影像缺少可用地理范围，无法进行对比")
    if overlap < 0.8:
        raise HTTPException(status_code=422, detail=f"灾前、灾后影像地理范围重合度仅 {overlap * 100:.1f}%，低于 80%，请重新选择同一区域影像")
    try:
        before_path = _catalog_asset_path(before)
        after_path = _catalog_asset_path(after)
        before_url = _catalog_preview_data_url(before_path)
        after_url = _catalog_preview_data_url(after_path)
        affected_area_geojson = _rgb_change_geojson(before_path, after_path)
        transport = HttpxQwenChatTransport(base_url=settings.qwen_vl_base_url, api_key=key, timeout_seconds=settings.qwen_vl_timeout_seconds)
        completion = await transport.complete({"model": settings.qwen_vl_model, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": [
            {"type": "text", "text": "请直接对比这两张灾前和灾后全景卫星影像。必须只返回 JSON，字段为 summary、affected_region、affected_features、reconstruction_advice、limitations。所有字段内容必须使用简体中文。affected_region 只需给出一个或多个大致受灾区域，用影像相对方位或可见地貌描述，不要区分高、中、低等级；不要虚构坐标、精确面积、损失金额或影像中不可见的设施损坏。只描述可见证据，并说明云、分辨率和时相造成的不确定性。"},
            {"type": "image_url", "image_url": {"url": before_url}},
            {"type": "image_url", "image_url": {"url": after_url}},
        ]}]})
        content = completion["choices"][0]["message"]["content"]
        assessment = QwenImageryPairAssessment.model_validate(json.loads(content)).model_dump()
    except (QwenProviderError, KeyError, IndexError, ValueError, TypeError, OSError) as exc:
        raise HTTPException(status_code=502, detail="Qwen imagery comparison failed: " + str(exc)) from exc
    return {"ok": True, "data": {"assessment": assessment, "model": settings.qwen_vl_model, "before_asset_id": before.asset_id, "after_asset_id": after.asset_id, "overlap_ratio": overlap, "affected_area_geojson": affected_area_geojson}}


@router.post("/assess/{analysis_id}")
async def assess_change_with_qwen(analysis_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    record = await db.scalar(select(RemoteSensingAnalysisRecord).where(RemoteSensingAnalysisRecord.analysis_id == analysis_id))
    if record is None or record.run_status != "succeeded" or record.is_simulated:
        raise HTTPException(status_code=422, detail="A completed real imagery analysis is required")
    result = dict(record.result_payload or {})
    if result.get("qwen_assessment"):
        return {"ok": True, "data": {"analysis_id": analysis_id, "assessment": result["qwen_assessment"], "model": result.get("qwen_model"), "reused": True}}
    outputs = result.get("output_uris") or {}
    if not outputs.get("before_rgb") or not outputs.get("after_rgb"):
        raise HTTPException(status_code=422, detail="The analysis has no before/after RGB artifacts")
    settings = get_settings()
    key = settings.qwen_vl_api_key.get_secret_value()
    if not key:
        raise HTTPException(status_code=503, detail="QWEN_VL_API_KEY is not configured")
    resolver = SafeImagePathResolver(settings.resolved_data_dir, settings.resolved_visual_output_dir)
    try:
        before_url = _image_data_url(resolver.resolve_output(str(outputs["before_rgb"])), max_bytes=settings.qwen_vl_max_image_bytes)
        after_url = _image_data_url(resolver.resolve_output(str(outputs["after_rgb"])), max_bytes=settings.qwen_vl_max_image_bytes)
        transport = HttpxQwenChatTransport(base_url=settings.qwen_vl_base_url, api_key=key, timeout_seconds=settings.qwen_vl_timeout_seconds)
        completion = await transport.complete({"model": settings.qwen_vl_model, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": [{"type": "text", "text": "请用简体中文比较灾前和灾后全景卫星影像。只返回 JSON，字段为 summary、affected_features、reconstruction_advice、limitations，所有字段值必须是中文。请指出一个或多个大致受灾区域和相对位置，不要区分高、中、低等级；只描述影像证据，不要虚构精确面积、坐标或不可见的损失，并说明云、时相和分辨率造成的不确定性。"}, {"type": "image_url", "image_url": {"url": before_url}}, {"type": "image_url", "image_url": {"url": after_url}}]}]})
        content = completion["choices"][0]["message"]["content"]
        assessment = QwenRecoveryAssessment.model_validate(json.loads(content)).model_dump()
    except (QwenProviderError, KeyError, IndexError, ValueError, TypeError, OSError) as exc:
        raise HTTPException(status_code=502, detail="Qwen assessment failed: " + str(exc)) from exc
    result["qwen_assessment"] = assessment
    result["qwen_model"] = settings.qwen_vl_model
    record.result_payload = result
    await db.commit()
    return {"ok": True, "data": {"analysis_id": analysis_id, "assessment": assessment, "model": settings.qwen_vl_model, "reused": False}}
