from uuid import uuid4

from app.visual_verification.schemas import (
    ImageAnalysisRequest,
    ImageQuality,
    SceneType,
    VisualAnalysisResult,
    VisualDecision,
)


class SimulatedVisualProvider:
    """Deterministic provider for local tests; outputs are always marked fallback."""

    def __init__(self, scenario: str = "confirmed") -> None:
        if scenario not in {"confirmed", "rejected", "uncertain", "poor_quality"}:
            raise ValueError(f"Unsupported simulated visual scenario: {scenario}")
        self.scenario = scenario

    async def analyze(self, request: ImageAnalysisRequest) -> VisualAnalysisResult:
        common = {
            "analysis_run_id": f"sim_visual_{uuid4().hex}",
            "visual_case_id": request.visual_case_id,
            "used_evidence_ids": request.image_asset_ids,
            "model_name": "simulated-visual-provider",
            "model_version": "1",
            "prompt_version": request.prompt_version,
            "is_fallback": True,
        }

        if self.scenario == "confirmed":
            return VisualAnalysisResult(
                **common,
                fire_detected=True,
                flame_detected=True,
                smoke_detected=True,
                burn_scar_detected=False,
                wildfire_likelihood=0.92,
                image_quality=ImageQuality.GOOD,
                scene_type=SceneType.FOREST_WILDFIRE,
                decision=VisualDecision.CONFIRMED,
                reasoning_summary="Simulated flame and rising smoke findings support wildfire.",
            )

        if self.scenario == "rejected":
            return VisualAnalysisResult(
                **common,
                fire_detected=False,
                flame_detected=False,
                smoke_detected=False,
                burn_scar_detected=False,
                wildfire_likelihood=0.08,
                image_quality=ImageQuality.GOOD,
                scene_type=SceneType.BARE_GROUND,
                alternative_explanations=["sun-heated bare ground"],
                decision=VisualDecision.REJECTED,
                reasoning_summary="Simulated evidence indicates bare ground without flame or smoke.",
            )

        if self.scenario == "poor_quality":
            return VisualAnalysisResult(
                **common,
                fire_detected=False,
                flame_detected=False,
                smoke_detected=True,
                burn_scar_detected=False,
                wildfire_likelihood=0.52,
                image_quality=ImageQuality.POOR,
                scene_type=SceneType.SMOKE_UNCERTAIN,
                alternative_explanations=["cloud or compression artifact"],
                decision=VisualDecision.UNCERTAIN,
                reasoning_summary="Simulated image quality is too poor for automatic confirmation.",
            )

        return VisualAnalysisResult(
            **common,
            fire_detected=False,
            flame_detected=False,
            smoke_detected=True,
            burn_scar_detected=False,
            wildfire_likelihood=0.55,
            image_quality=ImageQuality.USABLE,
            scene_type=SceneType.SMOKE_UNCERTAIN,
            alternative_explanations=["industrial smoke", "thin cloud"],
            decision=VisualDecision.UNCERTAIN,
            reasoning_summary="Simulated smoke-like feature requires additional evidence.",
        )
