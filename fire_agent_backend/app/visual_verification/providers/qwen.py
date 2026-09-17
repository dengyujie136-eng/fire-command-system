import asyncio
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.visual_verification.image_processing.paths import SafeImagePathResolver
from app.visual_verification.qwen_prompt import QWEN_FIRE_PROMPT_VERSION, QWEN_FIRE_PROMPT
from app.visual_verification.schemas import (
    ImageAnalysisRequest,
    ImageQuality,
    SceneType,
    VisualAnalysisResult,
    VisualDecision,
)


class QwenProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.raw_response = raw_response


class QwenFireAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fire_detected: bool
    flame_detected: bool
    smoke_detected: bool
    burn_scar_detected: bool
    wildfire_likelihood: float = Field(ge=0, le=1)
    image_quality: ImageQuality
    scene_type: SceneType
    alternative_explanations: list[str] = Field(default_factory=list)
    decision: VisualDecision
    reasoning_summary: str = Field(min_length=1, max_length=2000)


class QwenChatTransport(Protocol):
    async def complete(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class HttpxQwenChatTransport:
    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: float) -> None:
        if not base_url.strip() or not api_key.strip():
            raise ValueError("Qwen base_url and api_key are required")
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise QwenProviderError("qwen_timeout", "Qwen request timed out", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code in {408, 429, 500, 502, 503, 504}
            raise QwenProviderError(
                "qwen_http_error",
                f"Qwen returned HTTP {exc.response.status_code}",
                retryable=retryable,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise QwenProviderError("qwen_transport_error", "Qwen transport failed", retryable=True) from exc


@dataclass(frozen=True)
class QwenAnalysisTrace:
    result: VisualAnalysisResult
    raw_response: dict[str, Any]


def _image_data_url(path: Path, *, max_bytes: int) -> str:
    size = path.stat().st_size
    if size <= 0 or size > max_bytes:
        raise QwenProviderError(
            "qwen_image_size_invalid",
            f"model image size must be between 1 and {max_bytes} bytes",
            retryable=False,
        )
    mime_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(
        path.suffix.lower()
    )
    if mime_type is None:
        raise QwenProviderError(
            "qwen_image_type_invalid",
            "Qwen model input must be JPEG or PNG",
            retryable=False,
        )
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def parse_qwen_response_content(response: dict[str, Any]) -> QwenFireAssessment:
    try:
        content = response["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("message content is not text")
        decoded = json.loads(content)
        return QwenFireAssessment.model_validate(decoded)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise QwenProviderError(
            "qwen_invalid_output",
            "Qwen response is not valid fire-assessment JSON",
            retryable=False,
            raw_response=response,
        ) from exc


class QwenVisualProvider:
    def __init__(
        self,
        *,
        transport: QwenChatTransport,
        source_root: Path,
        output_root: Path,
        model_name: str = "qwen3-vl-plus",
        timeout_seconds: float = 60,
        max_attempts: int = 2,
        max_image_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.transport = transport
        self.paths = SafeImagePathResolver(source_root, output_root)
        self.model_name = model_name
        self.prompt_version = QWEN_FIRE_PROMPT_VERSION
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, min(max_attempts, 3))
        self.max_image_bytes = max_image_bytes

    def build_payload(self, request: ImageAnalysisRequest) -> dict[str, Any]:
        if request.prompt_version != self.prompt_version:
            raise QwenProviderError(
                "qwen_prompt_version_unsupported",
                f"Qwen provider requires prompt version {self.prompt_version}",
                retryable=False,
            )
        if not request.image_uris:
            raise QwenProviderError(
                "qwen_image_uri_missing",
                "Qwen analysis requires visual-output image URIs",
                retryable=False,
            )
        content: list[dict[str, Any]] = []
        for evidence_id in request.image_asset_ids:
            path = self.paths.resolve_output(request.image_uris[evidence_id])
            label = request.image_labels.get(evidence_id)
            if label:
                content.append({"type": "text", "text": f"影像证据：{label}"})
            content.append({
                "type": "image_url",
                "image_url": {"url": _image_data_url(path, max_bytes=self.max_image_bytes)},
            })
        content.append({"type": "text", "text": QWEN_FIRE_PROMPT})
        return {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }

    async def analyze_with_trace(self, request: ImageAnalysisRequest) -> QwenAnalysisTrace:
        payload = self.build_payload(request)
        response: dict[str, Any] | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = await asyncio.wait_for(
                    self.transport.complete(payload),
                    timeout=self.timeout_seconds,
                )
                assessment = parse_qwen_response_content(response)
                try:
                    result = VisualAnalysisResult(
                        analysis_run_id=f"qwen_visual_{uuid4().hex}",
                        visual_case_id=request.visual_case_id,
                        used_evidence_ids=request.image_asset_ids,
                        model_name=self.model_name,
                        model_version=self.model_name,
                        prompt_version=self.prompt_version,
                        is_fallback=False,
                        **assessment.model_dump(),
                    )
                except ValidationError as exc:
                    raise QwenProviderError(
                        "qwen_invalid_output",
                        "Qwen fire assessment violates decision consistency rules",
                        retryable=False,
                        raw_response=response,
                    ) from exc
                return QwenAnalysisTrace(result=result, raw_response=response)
            except TimeoutError as exc:
                error = QwenProviderError(
                    "qwen_timeout", "Qwen request timed out", retryable=True
                )
                if attempt == self.max_attempts:
                    raise error from exc
            except QwenProviderError as exc:
                if not exc.retryable or attempt == self.max_attempts:
                    raise
            await asyncio.sleep(0.1 * attempt)
        raise QwenProviderError("qwen_provider_error", "Qwen analysis failed", retryable=True)

    async def analyze(self, request: ImageAnalysisRequest) -> VisualAnalysisResult:
        return (await self.analyze_with_trace(request)).result
