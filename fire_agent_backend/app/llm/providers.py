from dataclasses import dataclass
import json
from typing import Any, Protocol

import httpx

from app.core.config import get_settings


@dataclass
class LLMResult:
    provider: str
    model: str
    content: str
    used_remote: bool


@dataclass
class LLMToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMToolResult:
    provider: str
    model: str
    content: str
    used_remote: bool
    tool_calls: list[LLMToolCall]
    assistant_message: dict[str, Any]


class LLMProvider(Protocol):
    provider_name: str
    model: str

    async def generate(self, system_prompt: str, user_payload: dict[str, Any]) -> LLMResult:
        ...

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMToolResult:
        ...


def _tool_result(provider: str, model: str, data: dict[str, Any], used_remote: bool) -> LLMToolResult:
    message = data.get("choices", [{}])[0].get("message", {}) or {}
    calls = []
    for index, item in enumerate(message.get("tool_calls") or []):
        function = item.get("function") or {}
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
        except (TypeError, ValueError, json.JSONDecodeError):
            arguments = {}
        calls.append(
            LLMToolCall(
                call_id=str(item.get("id") or f"tool_call_{index}"),
                name=str(function.get("name") or ""),
                arguments=arguments,
            )
        )
    return LLMToolResult(
        provider=provider,
        model=model,
        content=str(message.get("content") or ""),
        used_remote=used_remote,
        tool_calls=calls,
        assistant_message={
            "role": "assistant",
            "content": message.get("content"),
            **({"tool_calls": message.get("tool_calls")} if message.get("tool_calls") else {}),
        },
    )


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

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMToolResult:
        return LLMToolResult(self.provider_name, self.model, "", False, [], {"role": "assistant", "content": ""})


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

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMToolResult:
        if not self.api_key:
            return LLMToolResult(self.provider_name, self.model, "", False, [], {"role": "assistant", "content": ""})
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()
        return _tool_result(self.provider_name, self.model, data, True)


class QwenTextProvider(ZhipuGLMProvider):
    provider_name = "qwen"

    def __init__(self, model: str, api_key: str, base_url: str = "") -> None:
        super().__init__(
            model or "qwen-plus",
            api_key,
            base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )


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

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMToolResult:
        if not self.api_key:
            return LLMToolResult(self.provider_name, self.model, "", False, [], {"role": "assistant", "content": ""})
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()
        return _tool_result(self.provider_name, self.model, data, True)


def get_llm_provider(force_provider: str | None = None) -> LLMProvider:
    settings = get_settings()
    provider = (force_provider or settings.llm_provider or "zhipu").lower()
    if provider == "mimo":
        return MimoProvider(settings.llm_model if settings.llm_provider == "mimo" else "mimo", settings.llm_api_key, settings.llm_base_url)
    if provider == "structured":
        return StructuredFallbackProvider()
    if provider == "qwen":
        return QwenTextProvider(settings.llm_model, settings.llm_api_key, settings.llm_base_url)
    return ZhipuGLMProvider(settings.llm_model or "glm-4.6", settings.llm_api_key, settings.llm_base_url)
