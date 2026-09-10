import re
from pathlib import Path

from app.visual_verification.image_processing.errors import (
    SourceImageNotFoundError,
    UnsafeImagePathError,
)


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def safe_component(value: str, *, fallback: str) -> str:
    sanitized = _SAFE_COMPONENT.sub("-", value.strip()).strip(".-")
    return (sanitized or fallback)[:80]


class SafeImagePathResolver:
    """Resolve local image references without allowing traversal outside data_root."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root.resolve()

    def resolve_source(self, uri: str) -> Path:
        normalized = uri.strip().replace("\\", "/")
        if normalized.lower().startswith("data://"):
            normalized = normalized[7:]
        if normalized.lower().startswith("data/"):
            normalized = normalized[5:]

        candidate = Path(normalized)
        if not candidate.is_absolute():
            candidate = self.data_root / candidate

        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise SourceImageNotFoundError(f"source image does not exist: {uri}") from exc

        if not resolved.is_file():
            raise SourceImageNotFoundError(f"source image is not a file: {uri}")
        if not resolved.is_relative_to(self.data_root):
            raise UnsafeImagePathError("source image resolves outside the configured data directory")
        return resolved

    def output_directory(self, visual_case_id: str, source_asset_id: str) -> Path:
        output = (
            self.data_root
            / "processed"
            / "visual_verification"
            / safe_component(visual_case_id, fallback="case")
            / safe_component(source_asset_id, fallback="asset")
        ).resolve()
        if not output.is_relative_to(self.data_root):
            raise UnsafeImagePathError("derived image directory resolves outside data directory")
        output.mkdir(parents=True, exist_ok=True)
        return output

    def relative_uri(self, path: Path) -> str:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.data_root):
            raise UnsafeImagePathError("output path resolves outside data directory")
        return "data://" + resolved.relative_to(self.data_root).as_posix()
