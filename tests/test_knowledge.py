import json

from rtbdi_assistant.knowledge import default_knowledge_path, load_knowledge


def test_loads_report_map():
    km = load_knowledge()
    assert km.site.startswith("https://www.myrtpos.com")
    assert km.get("employee_conversion_ratio").columns
    assert km.get("inventory_report").tab == "Inventory Report"


def test_default_knowledge_path_uses_env(monkeypatch, tmp_path):
    custom = tmp_path / "report_map.json"
    custom.write_text(json.dumps({"site": "https://example.test", "reports": []}), encoding="utf-8")
    monkeypatch.setenv("RTBDI_KNOWLEDGE_PATH", str(custom))

    assert default_knowledge_path() == custom
