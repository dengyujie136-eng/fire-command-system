from __future__ import annotations

import re
from typing import Any


def classify_intent(question: str) -> dict[str, Any]:
    question_lower = question.lower()

    time_patterns = {
        r"(\d+)\s*分钟": lambda m: f"{m.group(1)}m",
        r"(\d+)\s*小时": lambda m: f"{int(m.group(1)) * 60}m",
        r"(\d+)\s*m": lambda m: f"{m.group(1)}m",
        r"(\d+)\s*h": lambda m: f"{int(m.group(1)) * 60}m",
    }

    time_key = None
    for pattern, extractor in time_patterns.items():
        match = re.search(pattern, question_lower)
        if match:
            time_key = extractor(match)
            break

    intent = "general"
    if any(kw in question_lower for kw in ["蔓延", "到哪里", "范围", "覆盖"]):
        intent = "time_query"
    elif any(kw in question_lower for kw in ["危险", "风险", "威胁"]):
        intent = "risk_analysis"
    elif any(kw in question_lower for kw in ["无人机", "航线", "规划", "飞行"]):
        intent = "uav_route"
    elif any(kw in question_lower for kw in ["为什么", "原因", "解释"]):
        intent = "explanation"

    return {"intent": intent, "time_key": time_key, "entities": {"question": question}}
