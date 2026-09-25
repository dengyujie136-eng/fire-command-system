import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.models import VisualAnalysisRunRecord, VisualFindingRecord
from app.visual_verification.schemas import (
    FindingSupport,
    ObjectDetectionBox,
    ProfessionalDetection,
    ProfessionalDetectionResult,
)


class ProfessionalDetectorError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProfessionalDetectorClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def detect(
        self,
        images: list[tuple[str, Path]],
        *,
        confidence_threshold: float,
        image_size: int,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise ProfessionalDetectorError(
                "professional_detector_not_configured",
                "未配置外部目标检测服务地址 PROFESSIONAL_DETECTOR_API_URL",
                status_code=503,
            )
        files = []
        handles = []
        try:
            for image_id, path in images:
                handle = path.open("rb")
                handles.append(handle)
                files.append(("images", (image_id, handle, "image/jpeg")))
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/detect",
                    data={
                        "confidence_threshold": str(confidence_threshold),
                        "image_size": str(image_size),
                    },
                    files=files,
                )
        except (OSError, httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProfessionalDetectorError(
                "professional_detector_unavailable",
                "Professional detector service is unavailable",
                status_code=503,
            ) from exc
        finally:
            for handle in handles:
                handle.close()

        if response.status_code >= 400:
            raise ProfessionalDetectorError(
                "professional_detector_error",
                f"Professional detector returned HTTP {response.status_code}",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ProfessionalDetectorError(
                "professional_detector_invalid_output",
                "Professional detector returned invalid JSON",
            ) from exc


def _finding_id(run_id: str, image_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{run_id}:{image_id}:{index}".encode()).hexdigest()
    return f"det-{digest[:32]}"


async def persist_professional_detection(
    db: AsyncSession,
    *,
    visual_case_id: str,
    derivative_ids: list[str],
    payload: dict[str, Any],
    is_simulated: bool,
) -> ProfessionalDetectionResult:
    now = datetime.now(UTC)
    run_id = f"yolo_{uuid4().hex}"
    detections: list[ObjectDetectionBox] = []
    for index, raw in enumerate(payload.get("detections", [])):
        image_id = str(raw["image_id"])
        if image_id not in derivative_ids:
            raise ProfessionalDetectorError(
                "professional_detector_invalid_output",
                "Detector referenced an image outside the request",
            )
        evidence_id = _finding_id(run_id, image_id, index)
        detection = ObjectDetectionBox(
            evidence_id=evidence_id,
            image_id=image_id,
            class_id=raw["class_id"],
            class_name=raw["class_name"],
            confidence=raw["confidence"],
            bbox_xyxy=tuple(raw["bbox_xyxy"]),
        )
        detections.append(detection)

    max_confidence = max((item.confidence for item in detections), default=0.0)
    if detections:
        support = FindingSupport.SUPPORTS_FIRE
        professional_confidence = max_confidence
        summary = f"Detected {len(detections)} fire/smoke object(s)"
        evidence_ids = [item.evidence_id for item in detections]
    else:
        support = FindingSupport.AGAINST_FIRE
        professional_confidence = round(1 - float(payload["confidence_threshold"]), 4)
        summary = "No fire or smoke object exceeded the configured threshold"
        evidence_ids = derivative_ids

    professional = ProfessionalDetection(
        support=support,
        confidence=professional_confidence,
        evidence_ids=evidence_ids,
        summary=summary,
    )
    result = ProfessionalDetectionResult(
        detection_run_id=run_id,
        visual_case_id=visual_case_id,
        model_name=payload["model_name"],
        model_version=payload["model_version"],
        model_sha256=payload["model_sha256"],
        confidence_threshold=payload["confidence_threshold"],
        image_size=payload["image_size"],
        detections=detections,
        professional=professional,
        duration_ms=payload["duration_ms"],
        is_simulated=is_simulated,
    )
    db.add(VisualAnalysisRunRecord(
        analysis_run_id=run_id,
        visual_case_id=visual_case_id,
        provider="ultralytics-yolo",
        model_name=result.model_name,
        model_version=result.model_version,
        prompt_version="object-detection-v1",
        run_status="succeeded",
        started_at=now,
        finished_at=now,
        duration_ms=result.duration_ms,
        raw_response=result.model_dump(mode="json"),
        is_fallback=False,
    ))
    if detections:
        for item in detections:
            db.add(VisualFindingRecord(
                finding_id=item.evidence_id,
                analysis_run_id=run_id,
                finding_type=item.class_name,
                detected=True,
                confidence=item.confidence,
                geometry_geojson=None,
                attributes={"bbox_xyxy": item.bbox_xyxy, "image_id": item.image_id},
                evidence_source=item.image_id,
            ))
    else:
        for image_id in derivative_ids:
            db.add(VisualFindingRecord(
                finding_id=_finding_id(run_id, image_id, 0),
                analysis_run_id=run_id,
                finding_type="fire_or_smoke",
                detected=False,
                confidence=professional_confidence,
                geometry_geojson=None,
                attributes={"threshold": result.confidence_threshold},
                evidence_source=image_id,
            ))
    await db.flush()
    return result
