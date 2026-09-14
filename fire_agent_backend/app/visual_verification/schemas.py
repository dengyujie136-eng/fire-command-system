from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.visual_verification.states import AnalysisRunStatus, VisualCaseStatus


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")
    return value


def expected_firms_viirs_snpp_candidate_id(
    event_id: str,
    observed_at: datetime,
    latitude: float,
    longitude: float,
) -> str:
    quantizer = Decimal("0.000001")
    latitude_6 = Decimal(str(latitude)).quantize(quantizer, rounding=ROUND_HALF_UP)
    longitude_6 = Decimal(str(longitude)).quantize(quantizer, rounding=ROUND_HALF_UP)
    timestamp = observed_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return (
        f"{event_id}-firms-viirs_snpp-{timestamp}-"
        f"{latitude_6:.6f}-{longitude_6:.6f}"
    )


class ImageQuality(str, Enum):
    GOOD = "good"
    USABLE = "usable"
    POOR = "poor"
    INVALID = "invalid"


class VisualDecision(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


class SceneType(str, Enum):
    FOREST_WILDFIRE = "forest_wildfire"
    GRASS_FIRE = "grass_fire"
    INDUSTRIAL_HEAT = "industrial_heat"
    BUILDING_FIRE = "building_fire"
    BARE_GROUND = "bare_ground"
    CLOUD_OR_FOG = "cloud_or_fog"
    SMOKE_UNCERTAIN = "smoke_uncertain"
    UNKNOWN = "unknown"


class FindingSupport(str, Enum):
    SUPPORTS_FIRE = "supports_fire"
    AGAINST_FIRE = "against_fire"
    UNAVAILABLE = "unavailable"


class RemoteSensingAnalysisType(str, Enum):
    """Stable task names exposed to the multi-agent orchestration layer."""

    FIRE_CONFIRMATION = "fire_confirmation"
    TEMPORAL_CHANGE = "temporal_change"
    BURNED_AREA = "burned_area"


class UpstreamCandidateStatus(str, Enum):
    CANDIDATE = "candidate"
    UNDER_REVIEW = "under_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class UpstreamImageryStatus(str, Enum):
    PENDING = "pending"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CandidateIngestAction(str, Enum):
    CREATED = "created"
    DUPLICATE = "duplicate"
    VERSIONED = "versioned"


class ImageryMatchStatus(str, Enum):
    MATCHED = "matched"
    PARTIALLY_MATCHED = "partially_matched"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"
    INVALID_REFERENCE = "invalid_reference"


class GeoJsonPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "Point"
    coordinates: tuple[float, float]

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != "Point":
            raise ValueError("GeoJSON geometry must be a Point")
        return value

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: tuple[float, float]) -> tuple[float, float]:
        longitude, latitude = value
        if not -180 <= longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        if not -90 <= latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        return value


class HotspotLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    crs: Literal["EPSG:4326"] = "EPSG:4326"


class HotspotDataOwner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization: str = Field(min_length=1, max_length=160)
    source_product: str = Field(min_length=1, max_length=160)
    license: str = Field(min_length=1, max_length=300)
    attribution_required: bool


class HotspotImageryReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=200)
    uri: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=160)
    mime_type: str = Field(min_length=1, max_length=120)
    acquired_at: datetime | None = None

    @field_validator("uri")
    @classmethod
    def reject_embedded_image_data(cls, value: str) -> str:
        lowered = value.lstrip().lower()
        if lowered.startswith("data:") and not lowered.startswith("data://"):
            raise ValueError("imagery_refs must use an asset, path, or API reference, not data URI")
        return value

    @field_validator("acquired_at")
    @classmethod
    def require_imagery_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_utc(value, "imagery acquired_at")


class HotspotReplayMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_replay: bool
    replay_interval_minutes: int | None = Field(default=None, gt=0)
    replay_source: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def require_replay_details(self) -> "HotspotReplayMetadata":
        if self.is_replay and (
            self.replay_interval_minutes is None or self.replay_source is None
        ):
            raise ValueError("historical replay requires interval and source")
        return self


class HotspotCandidate(BaseModel):
    """Member A's fire.hotspot.candidate.v0.1 record."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fire.hotspot.candidate.v0.1"] = (
        "fire.hotspot.candidate.v0.1"
    )
    candidate_id: str = Field(min_length=1, max_length=240)
    event_id: str = Field(min_length=1, max_length=160)
    event_name: str = Field(min_length=1, max_length=240)
    location: HotspotLocation
    observed_at: datetime
    status: UpstreamCandidateStatus
    data_owner: HotspotDataOwner
    imagery_status: UpstreamImageryStatus
    imagery_refs: list[HotspotImageryReference] = Field(default_factory=list)
    is_simulated: bool
    replay: HotspotReplayMetadata
    product_fields: dict[str, object] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def require_observed_timezone(cls, value: datetime) -> datetime:
        return _require_utc(value, "observed_at")

    @model_validator(mode="after")
    def validate_imagery_state(self) -> "HotspotCandidate":
        asset_ids = [item.asset_id for item in self.imagery_refs]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("imagery_refs asset_id values must be unique")
        if self.imagery_status == UpstreamImageryStatus.AVAILABLE and not self.imagery_refs:
            raise ValueError("available imagery_status requires imagery_refs")
        if self.imagery_status != UpstreamImageryStatus.AVAILABLE and self.imagery_refs:
            raise ValueError("pending or unavailable imagery_status must not include imagery_refs")
        if self.data_owner.source_product == "VIIRS_SNPP_SP":
            expected_id = expected_firms_viirs_snpp_candidate_id(
                self.event_id,
                self.observed_at,
                self.location.latitude,
                self.location.longitude,
            )
            if self.candidate_id != expected_id:
                raise ValueError("FIRMS VIIRS-SNPP candidate_id does not match the fixed rule")
        return self


class HotspotCandidateEnvelope(BaseModel):
    """HTTP and MQTT batch envelope agreed with member A."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fire.hotspot.candidate.v0.1"]
    event_id: str = Field(min_length=1, max_length=160)
    generated_at: datetime
    candidates: list[HotspotCandidate]

    @field_validator("generated_at")
    @classmethod
    def require_generation_timezone(cls, value: datetime) -> datetime:
        return _require_utc(value, "generated_at")

    @model_validator(mode="after")
    def validate_batch_identity(self) -> "HotspotCandidateEnvelope":
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique within one envelope")
        if any(candidate.event_id != self.event_id for candidate in self.candidates):
            raise ValueError("candidate event_id must match envelope event_id")
        if any(candidate.schema_version != self.schema_version for candidate in self.candidates):
            raise ValueError("candidate schema_version must match envelope schema_version")
        return self


# Backward-compatible import name for the day-two fixture tests.
CandidateInputEnvelope = HotspotCandidateEnvelope


class ImageryAssetReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=120)
    candidate_id: str = Field(min_length=1, max_length=120)
    role: Literal["primary", "context", "comparison"]
    source_type: Literal[
        "satellite_natural_color",
        "satellite_false_color",
        "ground_reference",
        "geostationary_satellite",
    ]
    acquired_at: datetime | None = None
    local_fixture_path: str = Field(min_length=1, max_length=500)
    source_page: str = Field(min_length=1, max_length=1000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality: ImageQuality
    coverage_bbox: tuple[float, float, float, float] | None = None
    is_simulated: bool = True

    @field_validator("acquired_at")
    @classmethod
    def require_asset_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("acquired_at must include a timezone")
        return value

    @field_validator("coverage_bbox")
    @classmethod
    def validate_coverage_bbox(
        cls, value: tuple[float, float, float, float] | None
    ) -> tuple[float, float, float, float] | None:
        if value is None:
            return value
        west, south, east, north = value
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("coverage_bbox must be a valid WGS84 west,south,east,north box")
        return value


class ImageryAssetsEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["visual-imagery-v1"]
    event_id: str = Field(min_length=1, max_length=100)
    assets: list[ImageryAssetReference] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_asset_ids(self) -> "ImageryAssetsEnvelope":
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("asset_id values must be unique")
        return self


class VisualCase(BaseModel):
    """Member B's stable internal representation of an upstream candidate."""

    model_config = ConfigDict(extra="forbid")

    visual_case_id: str = Field(min_length=1, max_length=100)
    source_candidate_id: str = Field(min_length=1, max_length=240)
    event_id: str = Field(min_length=1, max_length=160)
    observed_at: datetime
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    source_asset_ids: list[str] = Field(default_factory=list)
    status: VisualCaseStatus = VisualCaseStatus.RECEIVED
    is_simulated: bool = True
    version: int = Field(default=1, ge=1)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @field_validator("source_asset_ids")
    @classmethod
    def unique_asset_ids(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("source_asset_ids cannot contain blank values")
        return list(dict.fromkeys(value))


class VisualCaseRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    visual_case_id: str
    source_candidate_id: str
    upstream_schema_version: str
    upstream_status: UpstreamCandidateStatus
    event_id: str
    event_name: str
    observed_at: datetime
    longitude: float
    latitude: float
    imagery_status: UpstreamImageryStatus
    status: VisualCaseStatus
    version: int
    is_simulated: bool


class VisualCaseAssetRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    source_asset_id: str
    asset_role: str
    source_type: str
    source_name: str | None
    mime_type: str | None
    acquired_at: datetime | None
    content_uri: str
    preview_uri: str | None
    quality_status: str
    checksum_sha256: str | None
    is_simulated: bool


class VisualCaseDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case: VisualCaseRead
    assets: list[VisualCaseAssetRead]


class CandidateIngestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: CandidateIngestAction
    case: VisualCaseRead
    asset_count: int = Field(ge=0)


class CandidateIngestBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    generated_at: datetime
    items: list[CandidateIngestItem]


class FirePointSelectionRequest(BaseModel):
    """Event-neutral controls for selecting representative hotspot candidates."""

    model_config = ConfigDict(extra="forbid")

    start_at: datetime | None = None
    end_at: datetime | None = None
    time_window_minutes: int = Field(default=10, ge=1, le=1440)
    spatial_radius_km: float = Field(default=2.0, gt=0, le=100)
    minimum_cluster_points: int = Field(default=2, ge=1, le=1000)
    max_results: int = Field(default=1, ge=1, le=20)
    candidate_limit: int = Field(default=50_000, ge=1, le=100_000)
    require_imagery: bool = True

    @field_validator("start_at", "end_at")
    @classmethod
    def require_selection_time_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_utc(value, "selection time")

    @model_validator(mode="after")
    def validate_selection_range(self) -> "FirePointSelectionRequest":
        if self.start_at is not None and self.end_at is not None and self.end_at < self.start_at:
            raise ValueError("end_at must be greater than or equal to start_at")
        return self


class SelectedFirePointCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visual_case_id: str
    source_candidate_id: str
    observed_at: datetime
    ignition_point: GeoJsonPoint
    cluster_start_at: datetime
    cluster_end_at: datetime
    cluster_point_count: int = Field(ge=1)
    cluster_mean_confidence: float | None = Field(default=None, ge=0, le=1)
    cluster_max_frp_mw: float | None = Field(default=None, ge=0)
    imagery_status: UpstreamImageryStatus
    selection_rank: int = Field(ge=1)
    selection_reason: str
    is_simulated: bool


class FirePointSelectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fire.point.selection.v1"] = "fire.point.selection.v1"
    event_id: str = Field(min_length=1, max_length=160)
    selection_method: Literal["earliest_spatiotemporal_cluster_v1"] = (
        "earliest_spatiotemporal_cluster_v1"
    )
    evaluated_candidate_count: int = Field(ge=0)
    eligible_cluster_count: int = Field(ge=0)
    used_singleton_fallback: bool
    selected: list[SelectedFirePointCandidate]


class ConfirmedFirePointRead(BaseModel):
    """Stable event-neutral record returned to spread and orchestration modules."""

    model_config = ConfigDict(extra="forbid")

    confirmation_id: str
    event_id: str
    source_candidate_id: str
    confirmed_at: datetime
    ignition_point: GeoJsonPoint
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str]
    confirmation_method: str
    rule_version: str
    is_simulated: bool


class ImageryMatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    match_status: ImageryMatchStatus
    primary_asset_ids: list[str] = Field(default_factory=list)
    context_asset_ids: list[str] = Field(default_factory=list)
    comparison_asset_ids: list[str] = Field(default_factory=list)
    rejected_asset_ids: list[str] = Field(default_factory=list)
    matching_method: Literal["explicit_reference"] = "explicit_reference"
    matching_score: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    is_simulated: bool


class ImageAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visual_case_id: str = Field(min_length=1, max_length=100)
    image_asset_ids: list[str] = Field(min_length=1)
    image_uris: dict[str, str] = Field(default_factory=dict)
    prompt_version: str = Field(default="visual-fire-v1", min_length=1, max_length=80)

    @field_validator("image_asset_ids")
    @classmethod
    def validate_assets(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("image_asset_ids cannot contain blank values")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_image_uris(self) -> "ImageAnalysisRequest":
        if self.image_uris and set(self.image_uris) != set(self.image_asset_ids):
            raise ValueError("image_uris keys must exactly match image_asset_ids")
        if any(not uri.startswith("visual-output://") for uri in self.image_uris.values()):
            raise ValueError("model image URIs must use visual-output://")
        return self


class VisualAnalysisStartRequest(BaseModel):
    """Public request: derivative URIs are always resolved from trusted records."""

    model_config = ConfigDict(extra="forbid")

    derivative_ids: list[str] = Field(min_length=1, max_length=8)

    @field_validator("derivative_ids")
    @classmethod
    def validate_derivative_ids(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("derivative_ids cannot contain blank values")
        unique = list(dict.fromkeys(value))
        if len(unique) != len(value):
            raise ValueError("derivative_ids cannot contain duplicates")
        return unique


class ProfessionalDetectionStartRequest(BaseModel):
    """Run the independently deployed fire/smoke detector on trusted derivatives."""

    model_config = ConfigDict(extra="forbid")

    derivative_ids: list[str] = Field(min_length=1, max_length=8)
    confidence_threshold: float | None = Field(default=None, ge=0.05, le=0.95)
    image_size: int = Field(default=640, ge=320, le=1280)

    @field_validator("derivative_ids")
    @classmethod
    def validate_professional_derivative_ids(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("derivative_ids cannot contain blank values")
        unique = list(dict.fromkeys(value))
        if len(unique) != len(value):
            raise ValueError("derivative_ids cannot contain duplicates")
        return unique


class ObjectDetectionBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=120)
    image_id: str = Field(min_length=1, max_length=120)
    class_id: int = Field(ge=0)
    class_name: Literal["fire", "smoke"]
    confidence: float = Field(ge=0, le=1)
    bbox_xyxy: tuple[float, float, float, float]


class VisualAnalysisResult(BaseModel):
    """Provider-neutral structured output for Qwen-VL or a deterministic stub."""

    model_config = ConfigDict(extra="forbid")

    analysis_run_id: str = Field(min_length=1, max_length=100)
    visual_case_id: str = Field(min_length=1, max_length=100)
    run_status: AnalysisRunStatus = AnalysisRunStatus.SUCCEEDED
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
    used_evidence_ids: list[str] = Field(min_length=1)
    model_name: str = Field(min_length=1, max_length=120)
    model_version: str = Field(min_length=1, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=80)
    is_fallback: bool = False

    @field_validator("used_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("used_evidence_ids cannot contain blank values")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_decision_consistency(self) -> "VisualAnalysisResult":
        if self.image_quality == ImageQuality.INVALID and self.decision != VisualDecision.UNCERTAIN:
            raise ValueError("invalid imagery must produce an uncertain visual decision")
        if self.decision == VisualDecision.CONFIRMED and not (
            self.fire_detected or self.flame_detected or self.smoke_detected
        ):
            raise ValueError("a confirmed decision must cite a visible fire or smoke finding")
        return self


class VisualAnalysisFailure(BaseModel):
    """Structured terminal failure kept separately from successful model output."""

    model_config = ConfigDict(extra="forbid")

    analysis_run_id: str = Field(min_length=1, max_length=100)
    visual_case_id: str = Field(min_length=1, max_length=100)
    run_status: Literal["timeout", "invalid_output", "provider_error", "cancelled"]
    error_code: str = Field(min_length=1, max_length=80)
    error_message: str = Field(min_length=1, max_length=2000)
    retryable: bool
    attempted_model_name: str = Field(min_length=1, max_length=120)
    attempted_model_version: str = Field(min_length=1, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=80)
    used_evidence_ids: list[str] = Field(min_length=1)
    is_fallback: bool = False


class ProfessionalDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    support: FindingSupport
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_supported_finding_details(self) -> "ProfessionalDetection":
        if self.support != FindingSupport.UNAVAILABLE:
            if self.confidence is None:
                raise ValueError("available professional detection requires confidence")
            if not self.evidence_ids:
                raise ValueError("available professional detection requires evidence_ids")
        return self


class ProfessionalDetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_run_id: str = Field(min_length=1, max_length=100)
    visual_case_id: str = Field(min_length=1, max_length=180)
    run_status: Literal["succeeded"] = "succeeded"
    model_name: str = Field(min_length=1, max_length=120)
    model_version: str = Field(min_length=1, max_length=120)
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    confidence_threshold: float = Field(ge=0.05, le=0.95)
    image_size: int = Field(ge=320, le=1280)
    detections: list[ObjectDetectionBox] = Field(default_factory=list)
    professional: ProfessionalDetection
    duration_ms: int = Field(ge=0)
    is_simulated: bool


class ConfirmationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VisualCaseStatus
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_terminal_status(self) -> "ConfirmationDecision":
        allowed = {
            VisualCaseStatus.CONFIRMED,
            VisualCaseStatus.REJECTED,
            VisualCaseStatus.UNCERTAIN,
            VisualCaseStatus.FAILED,
        }
        if self.status not in allowed:
            raise ValueError("confirmation decision must be a terminal analysis outcome")
        return self


class VisualReviewStartRequest(BaseModel):
    """One-click orchestration request using only registered derivative IDs."""

    model_config = ConfigDict(extra="forbid")

    derivative_ids: list[str] = Field(min_length=1, max_length=8)
    detector_confidence_threshold: float | None = Field(default=None, ge=0.05, le=0.95)
    detector_image_size: int = Field(default=640, ge=320, le=1280)

    @field_validator("derivative_ids")
    @classmethod
    def validate_review_derivative_ids(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("derivative_ids cannot contain blank values")
        unique = list(dict.fromkeys(value))
        if len(unique) != len(value):
            raise ValueError("derivative_ids cannot contain duplicates")
        return unique


class VisualReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visual_case_id: str = Field(min_length=1, max_length=180)
    visual: VisualAnalysisResult | VisualAnalysisFailure
    professional_run: ProfessionalDetectionResult | None
    professional: ProfessionalDetection
    confirmation: ConfirmationDecision
    confirmation_id: str = Field(min_length=1, max_length=100)
    warnings: list[str] = Field(default_factory=list)
    is_simulated: bool


class AutoConfirmFirePointsRequest(BaseModel):
    """One-call event-neutral selection, image preparation and Qwen review."""

    model_config = ConfigDict(extra="forbid")

    selection: FirePointSelectionRequest = Field(default_factory=FirePointSelectionRequest)
    crop_radius_m: float = Field(default=1500.0, gt=0, le=50_000)
    band_indexes: list[int] | None = None
    detector_confidence_threshold: float | None = Field(default=None, ge=0.05, le=0.95)
    detector_image_size: int = Field(default=640, ge=320, le=1280)

    @field_validator("band_indexes")
    @classmethod
    def validate_pipeline_band_indexes(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if len(value) not in (1, 3) or len(value) != len(set(value)):
            raise ValueError("band_indexes must contain one or three unique band numbers")
        if any(item < 1 for item in value):
            raise ValueError("band_indexes must use one-based positive values")
        return value


class AutoConfirmFirePointsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fire.point.auto-confirmation.v1"] = (
        "fire.point.auto-confirmation.v1"
    )
    event_id: str
    selection: FirePointSelectionResult
    reviews: list[VisualReviewResult]
    confirmed_fire_points: list[ConfirmedFirePointRead]


class GeoJsonAnalysisGeometry(BaseModel):
    """Small GeoJSON geometry contract used to locate an analysis request."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["Point", "Polygon", "MultiPolygon"]
    coordinates: list[object] = Field(min_length=1)


class RemoteSensingTimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def require_utc_time(cls, value: datetime) -> datetime:
        return _require_utc(value, "remote-sensing time range")

    @model_validator(mode="after")
    def require_positive_range(self) -> "RemoteSensingTimeRange":
        if self.end_at <= self.start_at:
            raise ValueError("time_range end_at must be later than start_at")
        return self


class RemoteSensingAnalysisRequest(BaseModel):
    """Event-neutral request accepted from the orchestration or data agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fire.remote_sensing.request.v1"] = (
        "fire.remote_sensing.request.v1"
    )
    event_id: str = Field(min_length=1, max_length=160)
    analysis_type: RemoteSensingAnalysisType
    target_time: datetime | None = None
    time_range: RemoteSensingTimeRange | None = None
    target_geometry: GeoJsonAnalysisGeometry | None = None
    asset_ids: list[str] = Field(min_length=1, max_length=8)
    hotspot_ids: list[str] = Field(default_factory=list, max_length=100)
    visual_case_id: str | None = Field(default=None, min_length=1, max_length=180)
    prepared_image_ids: list[str] = Field(default_factory=list, max_length=8)
    change_threshold: float | None = Field(default=None, ge=-1, le=2)
    minimum_region_pixels: int = Field(default=9, ge=1, le=100_000)

    @field_validator("target_time")
    @classmethod
    def require_target_time_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_utc(value, "target_time")

    @field_validator("asset_ids", "hotspot_ids", "prepared_image_ids")
    @classmethod
    def require_unique_nonblank_ids(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("identifier lists cannot contain blank values")
        if len(value) != len(set(value)):
            raise ValueError("identifier lists cannot contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_task_inputs(self) -> "RemoteSensingAnalysisRequest":
        if self.analysis_type == RemoteSensingAnalysisType.FIRE_CONFIRMATION:
            if self.target_time is None:
                raise ValueError("fire_confirmation requires target_time")
        else:
            if self.time_range is None:
                raise ValueError(
                    f"{self.analysis_type.value} requires a before/after time_range"
                )
            if len(self.asset_ids) != 2:
                raise ValueError(
                    f"{self.analysis_type.value} requires exactly two imagery assets "
                    "ordered as before and after"
                )
            if self.target_geometry is not None and self.target_geometry.type == "Point":
                raise ValueError(
                    f"{self.analysis_type.value} target_geometry must be a Polygon "
                    "or MultiPolygon"
                )
        return self


class RemoteSensingCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_type: RemoteSensingAnalysisType
    tool_name: Literal["analyze_fire_imagery", "analyze_temporal_change"]
    minimum_asset_count: int = Field(ge=1)
    execution_status: Literal["available", "planned_day_2"]
    output_summary: str


class RemoteSensingCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fire.remote_sensing.capabilities.v1"] = (
        "fire.remote_sensing.capabilities.v1"
    )
    capabilities: list[RemoteSensingCapability]


class RemoteSensingFireConfirmationResult(BaseModel):
    """Generic agent-facing wrapper around the existing one-click review."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fire.remote_sensing.analysis.v1"] = (
        "fire.remote_sensing.analysis.v1"
    )
    analysis_id: str = Field(min_length=1, max_length=120)
    event_id: str
    analysis_type: Literal[RemoteSensingAnalysisType.FIRE_CONFIRMATION]
    tool_name: Literal["analyze_fire_imagery"] = "analyze_fire_imagery"
    source_asset_ids: list[str]
    hotspot_ids: list[str]
    review: VisualReviewResult


class RemoteSensingChangeResult(BaseModel):
    """Georeferenced before/after change product returned to the agent layer."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fire.remote_sensing.analysis.v1"] = (
        "fire.remote_sensing.analysis.v1"
    )
    analysis_id: str = Field(min_length=1, max_length=120)
    event_id: str = Field(min_length=1, max_length=160)
    analysis_type: Literal[
        RemoteSensingAnalysisType.TEMPORAL_CHANGE,
        RemoteSensingAnalysisType.BURNED_AREA,
    ]
    tool_name: Literal["analyze_temporal_change"] = "analyze_temporal_change"
    before_asset_id: str
    after_asset_id: str
    method: Literal["dnbr_threshold_v1", "dndvi_threshold_v1"]
    threshold: float = Field(ge=-1, le=2)
    minimum_region_pixels: int = Field(ge=1)
    changed_pixel_count: int = Field(ge=0)
    valid_pixel_count: int = Field(ge=0)
    area_hectares: float = Field(ge=0)
    area_geometry_wgs84: dict[str, object]
    source_crs: str
    resolution_m: tuple[float, float]
    output_uris: dict[str, str]
    warnings: list[str] = Field(default_factory=list)
    is_simulated: bool


class RemoteSensingAnalysisRunRead(BaseModel):
    """Stable persisted run metadata used by the orchestration agent."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    analysis_id: str
    visual_case_id: str
    event_id: str
    analysis_type: RemoteSensingAnalysisType
    tool_name: Literal["analyze_fire_imagery", "analyze_temporal_change"]
    run_status: Literal["running", "succeeded", "failed"]
    source_asset_ids: list[str]
    request_payload: dict[str, object]
    result_payload: dict[str, object] | None
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None = Field(default=None, ge=0)
    is_simulated: bool
    created_at: datetime


class VisualVerificationOutcome(BaseModel):
    """B-to-orchestrator result; the orchestrator owns upstream status updates."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, max_length=240)
    analysis_run_id: str = Field(min_length=1, max_length=100)
    fire: bool | None
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(min_length=1)
    decision: VisualDecision
    recommended_upstream_status: Literal["confirmed", "rejected", "under_review"]
    is_simulated: bool

    @field_validator("evidence_refs")
    @classmethod
    def validate_outcome_evidence(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence_refs cannot contain blank values")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_status_recommendation(self) -> "VisualVerificationOutcome":
        expected = {
            VisualDecision.CONFIRMED: (True, "confirmed"),
            VisualDecision.REJECTED: (False, "rejected"),
            VisualDecision.UNCERTAIN: (None, "under_review"),
        }[self.decision]
        if (self.fire, self.recommended_upstream_status) != expected:
            raise ValueError("fire and recommended status must agree with visual decision")
        return self


class ConfirmedFirePoint(BaseModel):
    """Stable internal hand-off. Member C's DTO adapter is intentionally deferred."""

    model_config = ConfigDict(extra="forbid")

    confirmation_id: str = Field(min_length=1, max_length=100)
    event_id: str = Field(min_length=1, max_length=160)
    source_candidate_id: str = Field(min_length=1, max_length=240)
    confirmed_at: datetime
    ignition_point: GeoJsonPoint
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)
    confirmation_method: str = "visual_verification_v1"
    is_simulated: bool

    @field_validator("confirmed_at")
    @classmethod
    def require_confirmation_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at must include a timezone")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def validate_confirmation_evidence(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence_ids cannot contain blank values")
        return list(dict.fromkeys(value))
