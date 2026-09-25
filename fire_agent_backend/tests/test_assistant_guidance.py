import unittest

from app.services.assistant_guidance_service import build_next_steps


class AssistantGuidanceTests(unittest.TestCase):
    def test_new_session_waits_for_a_user_request(self) -> None:
        guidance = build_next_steps("/realtime-monitor", {"event_id": "dixie_fire_2021"})

        self.assertEqual("idle", guidance["phase"])
        self.assertEqual([], guidance["choices"])

    def test_realtime_question_only_offers_realtime_choices(self) -> None:
        guidance = build_next_steps("/realtime-monitor", {
            "event_id": "dixie_fire_2021",
            "last_user_message": "我想查看现在美国地区的实时火点",
        })

        self.assertEqual("pre_fire", guidance["phase"])
        self.assertEqual("/realtime-monitor", guidance["choices"][0]["navigate_to"])
        self.assertNotIn("start_workflow", {(item.get("action") or {}).get("type") for item in guidance["choices"]})

    def test_agent_action_becomes_a_confirmation_choice(self) -> None:
        guidance = build_next_steps("/visual-verification", {
            "event_id": "dixie_fire_2021",
            "last_user_message": "执行完整火灾推演",
            "last_agent_result": {
                "message": "已经准备好完整工作流。",
                "source_mode": "structured",
                "navigate_to": "/visual-verification",
                "action": {"type": "start_workflow", "horizon_minutes": 240},
            },
        })

        self.assertEqual("user_action_confirmation", guidance["waiting_for"])
        self.assertEqual("start_workflow", guidance["choices"][0]["action"]["type"])

    def test_tool_result_drives_map_choice(self) -> None:
        guidance = build_next_steps("/realtime-monitor", {
            "event_id": "dixie_fire_2021",
            "last_user_message": "分析雅安山火",
            "last_agent_result": {
                "message": "已查询雅安附近真实候选点。",
                "source_mode": "tool_agent",
                "navigate_to": "/realtime-monitor",
                "navigate_query": {"focus": "location", "lng": "103.0", "lat": "29.9"},
            },
        })

        self.assertEqual("/realtime-monitor", guidance["choices"][0]["navigate_to"])
        self.assertEqual("location", guidance["choices"][0]["navigate_query"]["focus"])

    def test_verification_gate_requires_human_confirmation(self) -> None:
        guidance = build_next_steps("/visual-verification", {
            "workflow_run_id": "wf_1",
            "workflow_status": "WAITING_FOR_INPUT",
            "current_stage": "fire_verification",
            "last_user_message": "继续完成这次山火分析",
        })

        self.assertEqual("human_fire_confirmation", guidance["waiting_for"])
        self.assertEqual("/visual-verification", guidance["choices"][0]["navigate_to"])

    def test_active_workflow_gate_overrides_previous_query_result(self) -> None:
        guidance = build_next_steps("/realtime-monitor", {
            "event_id": "dixie_fire_2021",
            "workflow_run_id": "wf_1",
            "workflow_status": "WAITING_FOR_INPUT",
            "current_stage": "fire_verification",
            "last_user_message": "我想了解加州大火",
            "last_agent_result": {
                "message": "已聚焦加州。",
                "source_mode": "structured",
                "navigate_to": "/realtime-monitor",
                "navigate_query": {"focus": "california"},
            },
        })

        self.assertEqual("human_fire_confirmation", guidance["waiting_for"])
        self.assertEqual("open_verification", guidance["choices"][0]["id"])

    def test_scenario_gate_can_be_explicitly_confirmed(self) -> None:
        guidance = build_next_steps("/planning", {
            "workflow_run_id": "wf_1",
            "workflow_status": "WAITING_FOR_INPUT",
            "current_stage": "scenario",
            "last_user_message": "继续完成这次山火分析",
        })

        actions = [choice.get("action") or {} for choice in guidance["choices"]]
        self.assertIn("confirm_scenario", {action.get("type") for action in actions})

    def test_confirmed_fire_waits_for_spread_configuration(self) -> None:
        guidance = build_next_steps("/command-center", {
            "workflow_run_id": "wf_1",
            "workflow_status": "WAITING_FOR_INPUT",
            "current_stage": "situation",
            "confirmation_id": "confirm_1",
            "last_user_message": "继续分析",
        })

        self.assertEqual("spread_configuration", guidance["waiting_for"])
        actions = {(choice.get("action") or {}).get("type") for choice in guidance["choices"]}
        self.assertNotIn("resume_workflow", actions)
        self.assertEqual("configure_initial_spread", guidance["choices"][0]["id"])

    def test_verification_substage_guides_target_detection(self) -> None:
        guidance = build_next_steps("/visual-verification", {
            "workflow_run_id": "wf_1",
            "workflow_status": "WAITING_FOR_INPUT",
            "current_stage": "fire_verification",
            "workflow_metadata": {"verification_substage": "firms_candidates"},
            "last_user_message": "继续分析",
        })

        self.assertIn("目标检测", guidance["message"])

    def test_completed_workflow_offers_assessment_and_report(self) -> None:
        guidance = build_next_steps("/planning", {
            "workflow_run_id": "wf_1",
            "workflow_status": "COMPLETED",
            "current_stage": "commander",
            "last_user_message": "继续完成这次山火分析",
        })

        self.assertEqual("post_fire", guidance["phase"])
        action_types = {(choice.get("action") or {}).get("type") for choice in guidance["choices"]}
        self.assertIn("acquire_assessment_imagery", action_types)
        self.assertNotIn("generate_report", action_types)

    def test_completed_assessment_unlocks_full_report(self) -> None:
        guidance = build_next_steps("/disaster-assess", {
            "workflow_run_id": "wf_1",
            "workflow_status": "COMPLETED",
            "current_stage": "commander",
            "assessment_completed": True,
            "assessment": {"analysis_id": "analysis_1", "area_hectares": 12.5},
            "last_user_message": "继续分析",
        })

        self.assertEqual("report_generation", guidance["waiting_for"])
        self.assertEqual("generate_report", guidance["choices"][0]["action"]["type"])

    def test_generated_report_closes_the_workflow(self) -> None:
        guidance = build_next_steps("/disaster-assess", {
            "workflow_run_id": "wf_1",
            "workflow_status": "COMPLETED",
            "current_stage": "commander",
            "report_id": "rpt_1",
            "last_user_message": "生成完整报告",
        })

        self.assertEqual("report", guidance["phase"])
        self.assertEqual(100, guidance["progress"])


if __name__ == "__main__":
    unittest.main()
