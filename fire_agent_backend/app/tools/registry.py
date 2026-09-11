from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable

from app.tools.dynamic_fire_spread import (
    DYNAMIC_FIRE_SPREAD_TOOL_SCHEMA,
    TOOL_NAME,
    run_dynamic_fire_spread,
)


ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class AgentTool:
    name: str
    schema: dict[str, Any]
    handler: ToolHandler

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self.handler, **arguments),
        )


AGENT_TOOL_REGISTRY: dict[str, AgentTool] = {
    TOOL_NAME: AgentTool(
        name=TOOL_NAME,
        schema=DYNAMIC_FIRE_SPREAD_TOOL_SCHEMA,
        handler=run_dynamic_fire_spread,
    )
}


def list_agent_tool_schemas() -> list[dict[str, Any]]:
    return [tool.schema for tool in AGENT_TOOL_REGISTRY.values()]


async def invoke_agent_tool(
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    tool = AGENT_TOOL_REGISTRY.get(name)
    if not tool:
        available = ", ".join(sorted(AGENT_TOOL_REGISTRY)) or "none"
        raise KeyError(f"Unknown agent tool: {name}. Available tools: {available}")
    return await tool.invoke(arguments)
