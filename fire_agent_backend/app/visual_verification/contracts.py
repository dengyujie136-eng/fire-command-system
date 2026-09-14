from typing import Protocol

from app.visual_verification.schemas import ImageAnalysisRequest, VisualAnalysisResult


class VisualAnalysisProvider(Protocol):
    """Async contract shared by Qwen-VL and deterministic test providers."""

    async def analyze(self, request: ImageAnalysisRequest) -> VisualAnalysisResult:
        ...
