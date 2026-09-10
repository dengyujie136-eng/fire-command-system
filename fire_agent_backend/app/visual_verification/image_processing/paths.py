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
    """Keep immutable source imagery and writable derivatives in separate roots."""

    def __init__(self, source_root: Path, output_root: Path | None = None) -> None:
        self.source_root = source_root.resolve()
        self.output_root = (
            output_root or self.source_root / "processed" / "visual_verification"
        ).resolve()

    def resolve_source(self, uri: str) -> Path:
        normalized = uri.strip().replace("\\", "/")
        if normalized.lower().startswith("data://"):
            normalized = normalized[7:]
        if normalized.lower().startswith("data/"):
            normalized = normalized[5:]

        candidate = Path(normalized)
        if not candidate.is_absolute():
            candidate = self.source_root / candidate

        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise SourceImageNotFoundError(f"source image does not exist: {uri}") from exc

        if not resolved.is_file():
            raise SourceImageNotFoundError(f"source image is not a file: {uri}")
        if not resolved.is_relative_to(self.source_root):
            raise UnsafeImagePathError("source image resolves outside the configured data directory")
        return resolved

    def output_directory(self, visual_case_id: str, source_asset_id: str) -> Path:
        output = (
            self.output_root
            / safe_component(visual_case_id, fallback="case")
            / safe_component(source_asset_id, fallback="asset")
        ).resolve()
        if not output.is_relative_to(self.output_root):
            raise UnsafeImagePathError("derived image directory resolves outside output directory")
        output.mkdir(parents=True, exist_ok=True)
        return output

    def output_uri(self, path: Path) -> str:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.output_root):
            raise UnsafeImagePathError("output path resolves outside output directory")
        return "visual-output://" + resolved.relative_to(self.output_root).as_posix()

    def resolve_output(self, uri: str) -> Path:
        normalized = uri.strip().replace("\\", "/")
        if not normalized.lower().startswith("visual-output://"):
            raise UnsafeImagePathError("derived image URI must use visual-output://")
        candidate = self.output_root / normalized[len("visual-output://"):]
        unresolved = candidate.resolve(strict=False)
        if not unresolved.is_relative_to(self.output_root):
            raise UnsafeImagePathError("derived image resolves outside output directory")
        try:
            resolved = unresolved.resolve(strict=True)
        except FileNotFoundError as exc:
            raise SourceImageNotFoundError(f"derived image does not exist: {uri}") from exc
        if not resolved.is_file() or not resolved.is_relative_to(self.output_root):
            raise UnsafeImagePathError("derived image resolves outside output directory")
        return resolved
