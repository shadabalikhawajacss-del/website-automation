from rtbdi_assistant.planner import plan_question


def test_complex_question_uses_multiple_reports():
    plan = plan_question("Top seller's plan mix, their store inventory, and gross profit vs #2 last month")
    assert "employee_ranking_by_box_sales" in plan.report_ids
    assert "employee_mrc_matrix_report" in plan.report_ids
    assert "inventory_report" in plan.report_ids
    assert "kpi_report_by_employee" in plan.report_ids
    assert plan.date_range.label == "last month"
    assert "username" in plan.joins
    assert "store_text" not in plan.filters


def test_conversion_question_routes_to_conversion_report():
    plan = plan_question("What's Natalie's conversion ratio?")
    assert plan.report_ids == ("employee_conversion_ratio",)
    assert plan.metrics[0].column == "ratio"


def test_question_bank_employee_hours_routes_to_performance():
    plan = plan_question("How many hours did RUBAB work?")
    assert "employee_performance_report" in plan.report_ids
    assert any(metric.column == "hoursworked" for metric in plan.metrics)
    assert plan.needs_clarification is None


def test_question_bank_plan_and_device_routes_to_mrc_matrix():
    plan = plan_question("How many $60 plans did RUBAB sell?")
    assert "employee_mrc_matrix_report" in plan.report_ids
    assert any(metric.column == "plan60" for metric in plan.metrics)

    tablet_plan = plan_question("How many tablets sold at ROCKON MAIN?")
    assert "employee_mrc_matrix_report" in tablet_plan.report_ids
    assert any(metric.column == "tablet20" for metric in tablet_plan.metrics)


def test_question_bank_inventory_trend_routes_to_phone_trend():
    plan = plan_question("How many Samsung A16 5G sold in the last 7 days?")
    assert "phone_trend_by_market" in plan.report_ids
    assert any(metric.column == "sale7" for metric in plan.metrics)


def test_question_bank_inventory_operations_route_to_specific_reports():
    audit = plan_question("Show audit variance (scanned vs system) for tangible items.")
    assert "inventory_tangible_audit_log" in audit.report_ids
    assert any(metric.column == "varianceqty" for metric in audit.metrics)

    transfer = plan_question("Total transfer cost between stores last month.")
    assert "inventory_transfer_listing" in transfer.report_ids
    assert any(metric.column == "cost" for metric in transfer.metrics)


def test_question_bank_ambiguous_requests_ask_for_clarification():
    assert plan_question("Show me the ranking.").needs_clarification
    assert plan_question("Best employee?").needs_clarification
    assert plan_question("Compare the two stores.").needs_clarification
