import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.contracts import VisualAnalysisProvider
from app.visual_verification.models import VisualAnalysisRunRecord, VisualFindingRecord
from app.visual_verification.providers.qwen import QwenProviderError
from app.visual_verification.schemas import (
    ImageAnalysisRequest,
    VisualAnalysisFailure,
    VisualAnalysisResult,
)


def _finding_id(run_id: str, finding_type: str) -> str:
    digest = hashlib.sha256(f"{run_id}:{finding_type}".encode("utf-8")).hexdigest()
    return f"finding-{digest[:32]}"


async def execute_and_persist_visual_analysis(
    db: AsyncSession,
    *,
    provider: VisualAnalysisProvider,
    request: ImageAnalysisRequest,
) -> VisualAnalysisResult | VisualAnalysisFailure:
    started_at = datetime.now(UTC)
    try:
        trace_method = getattr(provider, "analyze_with_trace", None)
        if trace_method is None:
            result = await provider.analyze(request)
            raw_response: dict[str, Any] = result.model_dump(mode="json")
        else:
            trace = await trace_method(request)
            result = trace.result
            raw_response = trace.raw_response
    except QwenProviderError as exc:
        finished_at = datetime.now(UTC)
        run_id = f"qwen_failed_{hashlib.sha256(f'{request.visual_case_id}:{started_at.isoformat()}'.encode()).hexdigest()[:24]}"
        run_status = "timeout" if exc.code == "qwen_timeout" else (
            "invalid_output" if exc.code == "qwen_invalid_output" else "provider_error"
        )
        db.add(VisualAnalysisRunRecord(
            analysis_run_id=run_id,
            visual_case_id=request.visual_case_id,
            provider="qwen-vl",
            model_name=getattr(provider, "model_name", "qwen-vl"),
            model_version=getattr(provider, "model_name", "unknown"),
            prompt_version=getattr(provider, "prompt_version", request.prompt_version),
            run_status=run_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
            raw_response=exc.raw_response,
            error_code=exc.code,
            error_message=exc.message,
            is_fallback=False,
        ))
        await db.flush()
        return VisualAnalysisFailure(
            analysis_run_id=run_id,
            visual_case_id=request.visual_case_id,
            run_status=run_status,
            error_code=exc.code,
            error_message=exc.message,
            retryable=exc.retryable,
            attempted_model_name=getattr(provider, "model_name", "qwen-vl"),
            attempted_model_version=getattr(provider, "model_name", "unknown"),
            prompt_version=getattr(provider, "prompt_version", request.prompt_version),
            used_evidence_ids=request.image_asset_ids,
            is_fallback=False,
        )

    finished_at = datetime.now(UTC)
    db.add(VisualAnalysisRunRecord(
        analysis_run_id=result.analysis_run_id,
        visual_case_id=result.visual_case_id,
        provider="fallback" if result.is_fallback else "qwen-vl",
        model_name=result.model_name,
        model_version=result.model_version,
        prompt_version=result.prompt_version,
        run_status=result.run_status.value,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
        raw_response=raw_response,
        is_fallback=result.is_fallback,
    ))
    evidence_source = result.used_evidence_ids[0]
    finding_values = {
        "fire": result.fire_detected,
        "flame": result.flame_detected,
        "smoke": result.smoke_detected,
        "burn_scar": result.burn_scar_detected,
    }
    for finding_type, detected in finding_values.items():
        db.add(VisualFindingRecord(
            finding_id=_finding_id(result.analysis_run_id, finding_type),
            analysis_run_id=result.analysis_run_id,
            finding_type=finding_type,
            detected=detected,
            confidence=(result.wildfire_likelihood if finding_type == "fire" else None),
            attributes={
                "scene_type": result.scene_type.value,
                "image_quality": result.image_quality.value,
                "decision": result.decision.value,
                "all_evidence_ids": result.used_evidence_ids,
                "alternative_explanations": result.alternative_explanations,
            },
            evidence_source=evidence_source,
        ))
    await db.flush()
    return result
