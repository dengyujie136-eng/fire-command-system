import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.routers.assistant import ChatRequest, chat


class AssistantRealtimeFocusTests(unittest.TestCase):
    def run_chat(self, message: str) -> dict:
        return asyncio.run(chat(ChatRequest(message=message, page="/realtime-monitor")))

    def test_usa_realtime_hotspots_use_usa_focus(self) -> None:
        result = self.run_chat("我想获得现在美国地区的实时火点")

        self.assertEqual("usa", result["data"]["navigate_query"]["focus"])

    def test_usa_analysis_keeps_showcase_fallback(self) -> None:
        result = self.run_chat("分析美国山火")

        self.assertEqual("structured", result["data"]["source_mode"])
        self.assertEqual("usa", result["data"]["navigate_query"]["focus"])

    def test_global_focus_requires_explicit_global_intent(self) -> None:
        regional = self.run_chat("查看实时火点")
        global_view = self.run_chat("查看全球实时火点")

        self.assertEqual("region", regional["data"]["navigate_query"]["focus"])
        self.assertEqual("global", global_view["data"]["navigate_query"]["focus"])

    def test_chongqing_analysis_returns_location_plan(self) -> None:
        tool_result = {
            "message": "已定位重庆并查询真实候选火点。",
            "source_mode": "tool_agent",
            "navigate_to": "/realtime-monitor",
            "navigate_query": {
                "region": "himawari_asia_pacific",
                "focus": "location",
                "lng": "106.55",
                "lat": "29.56",
            },
        }
        with patch(
            "app.routers.assistant.run_general_wildfire_agent",
            AsyncMock(return_value=tool_result),
        ):
            result = asyncio.run(
                chat(ChatRequest(message="我想分析重庆山火", page="/realtime-monitor"), db=AsyncMock())
            )

        self.assertEqual("tool_agent", result["data"]["source_mode"])
        self.assertEqual("himawari_asia_pacific", result["data"]["navigate_query"]["region"])
        self.assertEqual("location", result["data"]["navigate_query"]["focus"])
        self.assertIn("真实候选火点", result["data"]["message"])


if __name__ == "__main__":
    unittest.main()
