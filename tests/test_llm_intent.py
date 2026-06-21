from rtbdi_assistant.config import AssistantConfig
from rtbdi_assistant.llm import select_live_intent


def test_select_live_intent_falls_back_without_openai_key():
    config = AssistantConfig(openai_api_key=None)

    intent = select_live_intent("who is number one in phone sales?", config=config)

    assert intent.report_ids == ("employee_ranking_by_box_sales",)
    assert "top 1" in intent.canonical_question.casefold()
