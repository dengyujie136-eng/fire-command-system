from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import get_settings


@dataclass
class LLMResult:
    provider: str
    model: str
    content: str
    used_remote: bool


class LLMProvider(Protocol):
    provider_name: str
    model: str

    async def generate(self, system_prompt: str, user_payload: dict[str, Any]) -> LLMResult:
        ...


class StructuredFallbackProvider:
    provider_name = "structured"

    def __init__(self, model: str = "structured-command-rules") -> None:
        self.model = model

    async def generate(self, system_prompt: str, user_payload: dict[str, Any]) -> LLMResult:
        summary = user_payload.get("input_summary", {})
        content = (
            f"基于结构化态势数据生成指挥建议：过火面积约 {summary.get('final_area_km2', '--')} km2，"
            f"风险等级 {summary.get('risk_level', '--')}，建议优先保护下风向目标、部署无人机复核火线、"
            "并保持主撤离路线与备用路线同步可用。"
        )
        return LLMResult(self.provider_name, self.model, content, False)


class ZhipuGLMProvider:
    provider_name = "zhipu"

    def __init__(self, model: str, api_key: str, base_url: str = "") -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url or "https://open.bigmodel.cn/api/paas/v4"

    async def generate(self, system_prompt: str, user_payload: dict[str, Any]) -> LLMResult:
        if not self.api_key:
            fallback = StructuredFallbackProvider(self.model)
            result = await fallback.generate(system_prompt, user_payload)
            return LLMResult(self.provider_name, self.model, result.content, False)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": str(user_payload)},
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResult(self.provider_name, self.model, content, True)


class MimoProvider:
    provider_name = "mimo"

    def __init__(self, model: str, api_key: str, base_url: str = "") -> None:
        self.model = model or "mimo"
        self.api_key = api_key
        self.base_url = base_url or "https://api.mimo.example/v1"

    async def generate(self, system_prompt: str, user_payload: dict[str, Any]) -> LLMResult:
        if not self.api_key:
            fallback = StructuredFallbackProvider(self.model)
            result = await fallback.generate(system_prompt, user_payload)
            return LLMResult(self.provider_name, self.model, result.content, False)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": str(user_payload)},
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResult(self.provider_name, self.model, content, True)


def get_llm_provider(force_provider: str | None = None) -> LLMProvider:
    settings = get_settings()
    provider = (force_provider or settings.llm_provider or "zhipu").lower()
    if provider == "mimo":
        return MimoProvider(settings.llm_model if settings.llm_provider == "mimo" else "mimo", settings.llm_api_key, settings.llm_base_url)
    if provider == "structured":
        return StructuredFallbackProvider()
    return ZhipuGLMProvider(settings.llm_model or "glm-4.6", settings.llm_api_key, settings.llm_base_url)
