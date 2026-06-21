from rtbdi_assistant.knowledge import load_knowledge


def test_loads_report_map():
    km = load_knowledge()
    assert km.site.startswith("https://www.myrtpos.com")
    assert km.get("employee_conversion_ratio").columns
    assert km.get("inventory_report").tab == "Inventory Report"
