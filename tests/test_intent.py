from rtbdi_assistant.intent import ConversationMemory, canonicalize_question, live_intent_from_llm_payload, select_live_reports


def test_canonicalizes_casual_metric_words():
    intent = select_live_reports("who's number one in phone sales?")

    assert "top 1" in intent.canonical_question.casefold()
    assert "activations" in intent.canonical_question.casefold()
    assert intent.report_ids == ("employee_ranking_by_box_sales",)


def test_dashboard_questions_route_to_home():
    intent = select_live_reports("How are we doing today on the dashboard?")

    assert intent.report_ids == ("home_dashboard",)


def test_selects_inventory_for_stock_words():
    intent = select_live_reports("how many samsung handsets are on hand?")

    assert "phones" in intent.canonical_question.casefold()
    assert "inventory" in intent.canonical_question.casefold()
    assert intent.report_ids == ("inventory_report",)


def test_iphone_stock_routes_to_inventory():
    intent = select_live_reports("iphone 13 how many stocks")

    assert intent.report_ids == ("inventory_report",)
    assert "inventory" in intent.canonical_question.casefold()
    assert intent.confidence >= 0.95


def test_product_stock_and_trend_routes_to_two_reports():
    intent = select_live_reports("iphone 13 stock and 30 day sales")

    assert intent.report_ids == ("inventory_report", "phone_trend_by_market")
    assert "product stock plus sales trend" in (intent.reasoning or "")


def test_profit_synonyms_do_not_double_gross_profit():
    intent = select_live_reports("how much did the top acc seller make us and where?")

    assert "gross gross" not in intent.canonical_question.casefold()
    assert "gross profit" in intent.canonical_question.casefold()
    assert intent.report_ids == ("employee_ranking_by_box_sales", "kpi_report_by_employee")


def test_memory_resolves_pronouns():
    memory = ConversationMemory(last_employee={"username": "AAA111", "name": "Alice"}, last_stores=["ROCKON MAIN"])

    canonical, used = canonicalize_question("what are their accessories?", memory)

    assert used is True
    assert "AAA111" in canonical


def test_memory_round_trips(tmp_path):
    path = tmp_path / "memory.json"
    memory = ConversationMemory()
    memory.update({"last_employee": {"username": "AAA111", "name": "Alice"}, "last_stores": ["ROCKON MAIN"]})
    memory.save(path)

    loaded = ConversationMemory.load(path)

    assert loaded.last_employee == {"username": "AAA111", "name": "Alice"}
    assert loaded.last_stores == ["ROCKON MAIN"]


def test_live_intent_from_llm_payload_filters_unknown_reports():
    intent = live_intent_from_llm_payload(
        "show me the dashboard",
        {
            "canonical_question": "How are we doing on the dashboard?",
            "report_ids": ["home_dashboard", "made_up_report"],
            "reasoning": "dashboard question",
        },
    )

    assert intent is not None
    assert intent.report_ids == ("home_dashboard",)
    assert intent.reasoning == "dashboard question"
