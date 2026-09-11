from urllib.parse import urlparse

from app.core.config import Settings
from app.visual_verification.providers.qwen import (
    HttpxQwenChatTransport,
    QwenVisualProvider,
)


class QwenConfigurationError(RuntimeError):
    """Raised without exposing credentials when the Qwen runtime is unusable."""


def build_qwen_provider(settings: Settings) -> QwenVisualProvider:
    api_key = settings.qwen_vl_api_key.get_secret_value().strip()
    base_url = settings.qwen_vl_base_url.strip()
    model_name = settings.qwen_vl_model.strip()
    parsed_url = urlparse(base_url)

    if not api_key:
        raise QwenConfigurationError("Qwen-VL API key is not configured")
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise QwenConfigurationError("Qwen-VL Base URL must be a valid HTTPS URL")
    if not model_name:
        raise QwenConfigurationError("Qwen-VL model is not configured")

    transport = HttpxQwenChatTransport(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=settings.qwen_vl_timeout_seconds,
    )
    return QwenVisualProvider(
        transport=transport,
        source_root=settings.resolved_data_dir,
        output_root=settings.resolved_visual_output_dir,
        model_name=model_name,
        timeout_seconds=settings.qwen_vl_timeout_seconds,
        max_attempts=settings.qwen_vl_max_attempts,
        max_image_bytes=settings.qwen_vl_max_image_bytes,
    )
