from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ImageSize(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(gt=0)
    height: int = Field(gt=0)


class PixelWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column_offset: int = Field(ge=0)
    row_offset: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ImageCropRequest(BaseModel):
    """One immutable request to prepare a candidate-centred model image."""

    model_config = ConfigDict(extra="forbid")

    visual_case_id: str = Field(min_length=1, max_length=180)
    source_asset_id: str = Field(min_length=1, max_length=120)
    source_uri: str = Field(min_length=1, max_length=1000)
    imagery_status: Literal["pending", "available", "unavailable"] = "available"
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    crop_radius_m: float = Field(default=1500.0, gt=0, le=50_000)
    source_kind: Literal["auto", "plain_image", "geotiff"] = "auto"
    band_indexes: list[int] | None = None
    output_format: Literal["jpeg", "png"] = "jpeg"
    max_dimension: int = Field(default=1536, ge=128, le=4096)
    thumbnail_dimension: int = Field(default=512, ge=64, le=1024)
    jpeg_quality: int = Field(default=90, ge=50, le=100)
    stretch_percentiles: tuple[float, float] = (2.0, 98.0)
    processing_purpose: Literal["model_input", "pipeline_test"] = "model_input"
    is_simulated: bool = False

    @field_validator("visual_case_id", "source_asset_id", "source_uri")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be blank")
        return stripped

    @field_validator("source_uri")
    @classmethod
    def reject_embedded_or_remote_data(cls, value: str) -> str:
        lowered = value.lower()
        if lowered.startswith("data:") and not lowered.startswith("data://"):
            raise ValueError("embedded data URIs are not accepted")
        if lowered.startswith(("http://", "https://", "ftp://")):
            raise ValueError("remote imagery must be downloaded by an asset provider first")
        return value

    @field_validator("band_indexes")
    @classmethod
    def validate_band_indexes(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if len(value) not in (1, 3):
            raise ValueError("band_indexes must contain exactly one or three bands")
        if any(index < 1 for index in value):
            raise ValueError("raster band indexes are one-based positive integers")
        if len(value) != len(set(value)):
            raise ValueError("band_indexes must be unique")
        return value

    @field_validator("stretch_percentiles")
    @classmethod
    def validate_stretch(cls, value: tuple[float, float]) -> tuple[float, float]:
        low, high = value
        if not 0 <= low < high <= 100:
            raise ValueError("stretch_percentiles must satisfy 0 <= low < high <= 100")
        return value

    @model_validator(mode="after")
    def require_available_imagery(self) -> "ImageCropRequest":
        if self.imagery_status != "available":
            raise ValueError("only available imagery can enter image processing")
        return self


class DerivativePreparationOptions(BaseModel):
    """Caller-controlled processing options; case and asset identity come from storage."""

    model_config = ConfigDict(extra="forbid")

    crop_radius_m: float = Field(default=1500.0, gt=0, le=50_000)
    source_kind: Literal["auto", "plain_image", "geotiff"] = "auto"
    band_indexes: list[int] | None = None
    output_format: Literal["jpeg", "png"] = "jpeg"
    max_dimension: int = Field(default=1536, ge=128, le=4096)
    thumbnail_dimension: int = Field(default=512, ge=64, le=1024)
    jpeg_quality: int = Field(default=90, ge=50, le=100)
    stretch_percentiles: tuple[float, float] = (2.0, 98.0)
    processing_purpose: Literal["model_input", "pipeline_test"] = "model_input"

    @field_validator("band_indexes")
    @classmethod
    def validate_band_indexes(cls, value: list[int] | None) -> list[int] | None:
        return ImageCropRequest.validate_band_indexes(value)

    @field_validator("stretch_percentiles")
    @classmethod
    def validate_stretch(cls, value: tuple[float, float]) -> tuple[float, float]:
        return ImageCropRequest.validate_stretch(value)


class VisualImageDerivativeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    derivative_id: str
    visual_case_id: str
    source_asset_id: str
    derivative_type: str
    file_uri: str
    preview_uri: str | None
    crs: str | None
    extent_geojson: dict[str, object] | None
    processing_parameters: dict[str, object]
    checksum_sha256: str | None
    is_simulated: bool
    created_at: datetime


class ImageProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["visual.image.derivative.v0.1"] = (
        "visual.image.derivative.v0.1"
    )
    derivative_id: str = Field(min_length=1, max_length=120)
    visual_case_id: str
    source_asset_id: str
    source_uri: str
    source_kind: Literal["plain_image", "geotiff"]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameter_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_uri: str
    preview_uri: str
    metadata_uri: str
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_size: ImageSize
    output_size: ImageSize
    preview_size: ImageSize
    output_format: Literal["jpeg", "png"]
    crs: str | None = None
    requested_extent_geojson: dict[str, object] | None = None
    actual_extent_geojson: dict[str, object] | None = None
    pixel_window: PixelWindow | None = None
    band_indexes: list[int] | None = None
    nodata_ratio: float | None = Field(default=None, ge=0, le=1)
    processing_parameters: dict[str, object]
    processing_purpose: Literal["model_input", "pipeline_test"]
    is_simulated: bool
    cache_hit: bool = False
    warnings: list[str] = Field(default_factory=list)
    completed_at: datetime
