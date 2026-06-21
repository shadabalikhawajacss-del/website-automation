from rtbdi_assistant.intent import ConversationMemory, canonicalize_question, select_live_reports


def test_canonicalizes_casual_metric_words():
    intent = select_live_reports("who's number one in phone sales?")

    assert "top 1" in intent.canonical_question.casefold()
    assert "activations" in intent.canonical_question.casefold()
    assert intent.report_ids == ("employee_ranking_by_box_sales",)


def test_selects_inventory_for_stock_words():
    intent = select_live_reports("how many samsung handsets are on hand?")

    assert "phones" in intent.canonical_question.casefold()
    assert "inventory" in intent.canonical_question.casefold()
    assert intent.report_ids == ("inventory_report",)


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
