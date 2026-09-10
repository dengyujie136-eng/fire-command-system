"""Shared interfaces for decision agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from app.agents.context import DecisionContext


class AgentResult(TypedDict):
    agent_name: str
    status: str
    output: dict[str, Any]
    reasoning: list[str]


class BaseAgent(ABC):
    """Base class for synchronous rule-based decision agents."""

    agent_name: str

    @abstractmethod
    def run(
        self,
        context: DecisionContext,
        prior_results: Mapping[str, AgentResult] | None = None,
    ) -> AgentResult:
        """Analyze the decision context and return a standard agent result."""


def agent_result(
    agent_name: str,
    status: str = "success",
    output: dict[str, Any] | None = None,
    reasoning: list[str] | None = None,
) -> AgentResult:
    return {
        "agent_name": agent_name,
        "status": status,
        "output": output or {},
        "reasoning": reasoning or [],
    }
