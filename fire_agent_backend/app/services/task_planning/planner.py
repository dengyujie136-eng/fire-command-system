"""Natural-language task planner for capability selection only."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping

from app.services.task_planning.models import NaturalLanguageTaskRequest, TaskPlan, TaskStep
from app.services.task_planning.registry import CapabilityRegistry, default_registry

_CAPABILITY_ORDER = (
    "situation_analysis",
    "spread_forecast",
    "risk_assessment",
    "route_planning",
    "resource_dispatch",
    "route_resource_planning",
    "command_synthesis",
)
_OPERATIONAL_FACT_KEYS = {
    "eta",
    "eta_minutes",
    "route_geometry",
    "geometry",
    "risk_score",
    "resource_count",
    "resource_quantity",
    "resource_shortage",
    "shortage",
    "fire_spread_result",
    "capability_execution_result",
}


class NaturalLanguageTaskPlanner:
    """Builds a validated TaskPlan without executing professional capabilities."""

    def __init__(self, registry: CapabilityRegistry | None = None, llm_provider: Any | None = None) -> None:
        self.registry = registry or default_registry()
        self.llm_provider = llm_provider

    async def plan(
        self,
        request: NaturalLanguageTaskRequest,
        *,
        force_provider: str | None = None,
    ) -> TaskPlan:
        warnings: list[str] = []
        if self.llm_provider is not None or force_provider:
            try:
                suggestion, llm_warnings = await self._llm_suggestion(request, force_provider=force_provider)
                warnings.extend(llm_warnings)
                selected = self._validated_capabilities(suggestion.get("capabilities") or [])
                return self._build_plan(
                    request,
                    intent=str(suggestion.get("intent") or "general_task"),
                    requested_outputs=tuple(str(item) for item in suggestion.get("requested_outputs") or []),
                    selected_capabilities=selected,
                    planner_source="llm",
                    warnings=warnings,
                    fallback_used=False,
                    metadata={"llm_used": True},
                )
            except Exception as exc:
                warnings.append(f"LLM planner output was rejected; deterministic fallback used: {exc}")
                return self._deterministic_plan(request, warnings=warnings, planner_source="llm_fallback")
        return self._deterministic_plan(request, warnings=warnings, planner_source="deterministic")

    async def _llm_suggestion(
        self,
        request: NaturalLanguageTaskRequest,
        *,
        force_provider: str | None,
    ) -> tuple[dict[str, Any], list[str]]:
        provider = self.llm_provider
        if provider is None:
            from app.llm.providers import get_llm_provider

            provider = get_llm_provider(force_provider)
        result = await provider.generate(_planner_prompt(self.registry), _planner_payload(request, self.registry))
        content = getattr(result, "content", "")
        parsed = _parse_json_object(content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM did not return a JSON object.")
        warnings = _operational_fact_warnings(parsed)
        return parsed, warnings

    def _deterministic_plan(
        self,
        request: NaturalLanguageTaskRequest,
        *,
        warnings: Iterable[str],
        planner_source: str,
    ) -> TaskPlan:
        suggestion = _deterministic_suggestion(request.query)
        return self._build_plan(
            request,
            intent=suggestion["intent"],
            requested_outputs=tuple(suggestion["requested_outputs"]),
            selected_capabilities=tuple(suggestion["capabilities"]),
            planner_source=planner_source,
            warnings=list(warnings),
            fallback_used=planner_source == "llm_fallback",
            metadata={"llm_used": False},
        )

    def _validated_capabilities(self, capability_ids: Iterable[str]) -> tuple[str, ...]:
        return self.registry.apply_subsumption(_ordered_unique(self._expand_dependencies(capability_ids)))

    def _expand_dependencies(self, capability_ids: Iterable[str]) -> tuple[str, ...]:
        expanded: list[str] = []

        def visit(capability_id: str) -> None:
            capability = self.registry.get(capability_id)
            for dependency in capability.dependencies:
                visit(dependency)
            if capability.capability_id not in expanded:
                expanded.append(capability.capability_id)

        for capability_id in capability_ids:
            visit(str(capability_id))
        return tuple(expanded)

    def _build_plan(
        self,
        request: NaturalLanguageTaskRequest,
        *,
        intent: str,
        requested_outputs: tuple[str, ...],
        selected_capabilities: tuple[str, ...],
        planner_source: str,
        warnings: list[str],
        fallback_used: bool,
        metadata: Mapping[str, Any],
    ) -> TaskPlan:
        selected = self._validated_capabilities(selected_capabilities)
        if not selected:
            selected = ("situation_analysis",)
            warnings.append("No known capability was selected; defaulted to situation analysis.")
        steps: list[TaskStep] = []
        blocked_capabilities: set[str] = set()
        required_inputs: list[str] = []
        missing_inputs: list[str] = []
        capability_reasons = _capability_reasons(selected, intent)
        dependencies: dict[str, tuple[str, ...]] = {}

        for capability_id in selected:
            capability = self.registry.get(capability_id)
            _extend_unique(required_inputs, capability.required_inputs)
            direct_missing = tuple(item for item in capability.required_inputs if not request.has_input(item))
            step_dependencies = _step_dependencies(capability_id, selected, self.registry)
            dependency_blocked = tuple(item for item in step_dependencies if item in blocked_capabilities)
            status = "blocked" if direct_missing or dependency_blocked else "ready"
            blocked_reason = None
            if direct_missing:
                blocked_reason = "Missing required inputs: " + ", ".join(direct_missing)
            elif dependency_blocked:
                blocked_reason = "Blocked by dependencies: " + ", ".join(dependency_blocked)
            if status == "blocked":
                blocked_capabilities.add(capability_id)
                _extend_unique(missing_inputs, direct_missing)
            dependencies[capability_id] = step_dependencies
            steps.append(
                TaskStep(
                    step_id=f"step_{len(steps) + 1}_{capability_id}",
                    capability_id=capability_id,
                    name=capability.name,
                    provider=capability.provider,
                    depends_on=step_dependencies,
                    required_inputs=capability.required_inputs,
                    missing_inputs=direct_missing,
                    status=status,  # type: ignore[arg-type]
                    blocked_reason=blocked_reason,
                    execution_role=capability.execution_role,
                )
            )

        ready_steps = [step for step in steps if step.status == "ready"]
        executable = len(ready_steps) == len(steps)
        if executable:
            status = "ready"
        elif ready_steps:
            status = "partial"
        else:
            status = "blocked"
        if "route_resource_planning" in blocked_capabilities and "command_synthesis" in selected:
            warnings.append("Planning requested but required planning inputs are unavailable; command synthesis can only be partial after execution support is added.")
        warnings.append("Task Planner only creates a TaskPlan; it does not execute agents or generate operational facts.")

        return TaskPlan(
            original_query=request.query,
            intent=intent,
            requested_outputs=requested_outputs,
            selected_capabilities=selected,
            execution_steps=tuple(steps),
            dependencies=dependencies,
            required_inputs=tuple(required_inputs),
            missing_inputs=tuple(missing_inputs),
            executable=executable,
            status=status,  # type: ignore[arg-type]
            warnings=tuple(_ordered_unique(warnings)),
            planner_source=planner_source,  # type: ignore[arg-type]
            metadata={
                **dict(metadata),
                "available_inputs": dict(request.available_inputs),
                "synthetic_defaults_used": False,
            },
            capability_reasons=capability_reasons,
            blocked_steps=tuple(step.capability_id for step in steps if step.status == "blocked"),
            fallback_used=fallback_used,
        )


def plan_task_sync(request: NaturalLanguageTaskRequest, *, planner: NaturalLanguageTaskPlanner | None = None) -> TaskPlan:
    import asyncio

    return asyncio.run((planner or NaturalLanguageTaskPlanner()).plan(request))


def _planner_prompt(registry: CapabilityRegistry) -> str:
    return (
        "Return strict JSON only with keys intent, requested_outputs, capabilities. "
        "Capabilities must be selected only from this whitelist: "
        f"{list(registry.selectable_ids())}. "
        "Do not invent capability names. Do not generate operational facts, numeric calculations, routes, resources, or execution results."
    )


def _planner_payload(request: NaturalLanguageTaskRequest, registry: CapabilityRegistry) -> dict[str, Any]:
    return {
        "query": request.query,
        "language": request.language,
        "available_inputs": dict(request.available_inputs),
        "capability_registry": registry.to_dict(),
    }


def _parse_json_object(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _operational_fact_warnings(parsed: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    present = sorted(key for key in parsed if key in _OPERATIONAL_FACT_KEYS)
    if present:
        warnings.append("LLM operational fact fields were ignored: " + ", ".join(present))
    return warnings


def _deterministic_suggestion(query: str) -> dict[str, Any]:
    q = query.lower()
    capabilities: list[str] = []
    outputs: list[str] = []

    wants_spread = _has_any(q, "蔓延", "扩散", "预测", "未来", "趋势", "forecast", "spread", "next three hours", "next 3 hours")
    wants_risk = _has_any(q, "风险", "最高", "高危", "risk", "hazard")
    wants_route = _has_any(q, "路线", "路径", "最快", "救援路", "route", "path")
    wants_resource = _has_any(q, "资源", "消防员", "调度", "派", "dispatch", "resource", "firefighter")
    wants_command = _has_any(q, "方案", "指挥", "建议", "完整", "救援方案", "command", "plan", "recommendation")
    wants_situation = _has_any(q, "现在", "当前", "火势", "情况", "怎么样", "current", "situation", "status")

    if wants_situation or not any((wants_spread, wants_risk, wants_route, wants_resource, wants_command)):
        capabilities.append("situation_analysis")
        outputs.append("current fire situation")
    if wants_spread:
        capabilities.extend(["situation_analysis", "spread_forecast"])
        outputs.append("spread forecast")
    if wants_risk:
        capabilities.extend(["situation_analysis", "spread_forecast", "risk_assessment"])
        outputs.append("risk assessment")
    if wants_route and wants_resource:
        if wants_spread:
            capabilities.extend(["situation_analysis", "spread_forecast", "risk_assessment"])
            outputs.append("risk assessment")
        capabilities.append("route_resource_planning")
        outputs.append("route-resource planning")
    elif wants_route:
        capabilities.append("route_planning")
        outputs.append("route planning")
    elif wants_resource:
        capabilities.append("resource_dispatch")
        outputs.append("resource dispatch")
    if wants_command or (wants_spread and wants_route and wants_resource):
        capabilities.append("command_synthesis")
        outputs.append("command synthesis")

    intent = _intent_from_flags(wants_situation, wants_spread, wants_risk, wants_route, wants_resource, wants_command)
    return {
        "intent": intent,
        "requested_outputs": _ordered_unique(outputs),
        "capabilities": _ordered_unique(capabilities),
    }


def _intent_from_flags(
    wants_situation: bool,
    wants_spread: bool,
    wants_risk: bool,
    wants_route: bool,
    wants_resource: bool,
    wants_command: bool,
) -> str:
    if wants_spread and wants_route and wants_resource:
        return "full_emergency_planning"
    if wants_route and wants_resource:
        return "route_resource_planning"
    if wants_resource:
        return "resource_dispatch"
    if wants_route:
        return "route_planning"
    if wants_risk:
        return "risk_assessment"
    if wants_spread:
        return "spread_forecast"
    if wants_command:
        return "command_synthesis"
    if wants_situation:
        return "situation_analysis"
    return "general_fire_task"


def _step_dependencies(capability_id: str, selected: tuple[str, ...], registry: CapabilityRegistry) -> tuple[str, ...]:
    if capability_id == "command_synthesis":
        return tuple(item for item in selected if item != "command_synthesis")
    dependencies = tuple(item for item in registry.get(capability_id).dependencies if item in selected)
    return dependencies


def _capability_reasons(selected: tuple[str, ...], intent: str) -> dict[str, str]:
    return {capability_id: f"Selected for intent {intent}." for capability_id in selected}


def _has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _extend_unique(values: list[str], additions: Iterable[str]) -> None:
    for value in additions:
        if value not in values:
            values.append(value)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        value = str(value)
        if value not in result:
            result.append(value)
    return tuple(sorted(result, key=lambda item: _CAPABILITY_ORDER.index(item) if item in _CAPABILITY_ORDER else 999))
