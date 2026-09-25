import unittest

from app.llm.providers import _tool_result
from app.services.assistant_tool_service import extract_location_hint, select_region_for_point


class AssistantToolServiceTests(unittest.TestCase):
    def test_extracts_arbitrary_chinese_location(self) -> None:
        self.assertEqual("四川雅安", extract_location_hint("我想分析四川雅安山火"))

    def test_selects_supported_asia_region_from_coordinates(self) -> None:
        result = select_region_for_point(103.0, 29.98)

        self.assertTrue(result["ok"])
        self.assertTrue(result["supported"])
        self.assertEqual("himawari_asia_pacific", result["region_id"])

    def test_reports_known_but_unsupported_region(self) -> None:
        result = select_region_for_point(10.0, 50.0)

        self.assertTrue(result["ok"])
        self.assertFalse(result["supported"])
        self.assertEqual("meteosat_europe_africa", result["region_id"])

    def test_parses_openai_compatible_tool_calls(self) -> None:
        result = _tool_result(
            "qwen",
            "qwen-plus",
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "geocode_location",
                                        "arguments": '{"location":"四川雅安"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            True,
        )

        self.assertEqual("geocode_location", result.tool_calls[0].name)
        self.assertEqual("四川雅安", result.tool_calls[0].arguments["location"])


if __name__ == "__main__":
    unittest.main()
