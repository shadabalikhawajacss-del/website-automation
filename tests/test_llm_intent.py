from rtbdi_assistant.config import AssistantConfig
from rtbdi_assistant.intent import LiveIntent
from rtbdi_assistant.llm import reconcile_live_intent, select_live_intent


def test_select_live_intent_falls_back_without_openai_key():
    config = AssistantConfig(openai_api_key=None)

    intent = select_live_intent("who is number one in phone sales?", config=config)

    assert intent.report_ids == ("employee_ranking_by_box_sales",)
    assert "top 1" in intent.canonical_question.casefold()


def test_reconcile_keeps_specific_deterministic_route_over_default_employee():
    deterministic = LiveIntent("iphone 13 how many stocks", "iphone 13 how many inventory", ("inventory_report",), confidence=0.99)
    llm_intent = LiveIntent("iphone 13 how many stocks", "iphone 13 how many stocks", ("employee_performance_report",))

    result = reconcile_live_intent(deterministic, llm_intent)

    assert result.report_ids == ("inventory_report",)
    assert result.canonical_question == "iphone 13 how many inventory"
