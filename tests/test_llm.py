from rtbdi_assistant.llm import preview_interpreter_prompt


def test_prompt_preview_uses_deterministic_plan_without_api_key():
    preview = preview_interpreter_prompt("Top 5 employees by accessories last month")

    assert preview["deterministic_plan"]["date_range"]["label"] == "last month"
    assert "employee_performance_report" in preview["deterministic_plan"]["report_ids"]
    assert preview["messages"][0]["role"] == "system"
    assert "report_map" in preview["messages"][1]["content"]
