from rtbdi_assistant.planner import plan_question


def test_complex_question_uses_multiple_reports():
    plan = plan_question("Top seller's plan mix, their store inventory, and gross profit vs #2 last month")
    assert "employee_ranking_by_box_sales" in plan.report_ids
    assert "employee_mrc_matrix_report" in plan.report_ids
    assert "inventory_report" in plan.report_ids
    assert "kpi_report_by_employee" in plan.report_ids
    assert plan.date_range.label == "last month"
    assert "username" in plan.joins


def test_conversion_question_routes_to_conversion_report():
    plan = plan_question("What's Natalie's conversion ratio?")
    assert plan.report_ids == ("employee_conversion_ratio",)
    assert plan.metrics[0].column == "ratio"
