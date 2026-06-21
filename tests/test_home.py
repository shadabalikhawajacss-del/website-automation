from rtbdi_assistant.home import HomeSnapshot, _key_values_from_text, _rows_from_table_text, answer_home_question


def test_rows_from_home_table_text():
    rows = _rows_from_table_text(
        "Market\tStore ID\tStore Name\tAccessory\n"
        "HOUSTON\tPUREHOU034\tROCKON MAIN\t$13,221.17\n"
        "HOUSTON\tPUREHOU130\tROCKON NASA\t$8,537.17"
    )

    assert rows == [
        {"Market": "HOUSTON", "Store ID": "PUREHOU034", "Store Name": "ROCKON MAIN", "Accessory": "$13,221.17"},
        {"Market": "HOUSTON", "Store ID": "PUREHOU130", "Store Name": "ROCKON NASA", "Accessory": "$8,537.17"},
    ]


def test_key_values_from_home_snapshot_text():
    values = _key_values_from_text("Total Stores:\t\xa0\t45\tTotal Activation:\t\xa0\t17\tTotal Accessory:\t\xa0\t$772.00")

    assert values["Total Stores"] == "45"
    assert values["Total Activation"] == "17"
    assert values["Total Accessory"] == "$772.00"


def test_answer_home_dashboard_summary():
    snapshot = HomeSnapshot(
        url="https://example.test",
        top_stores=[
            {
                "Store Name": "ROCKON MAIN",
                "PPD (Tot Act)": "208",
                "Accessory": "$13,221.17",
                "Qpay Conv%": "97.7%",
            }
        ],
        period_summary=[
            {
                "Store Count": "45",
                "Total Activation": "4196",
                "Act. Per Door (PPD)": "93",
                "Accessory": "$194,432.54",
                "Qpay Count": "4615",
                "Conversion (CPD)": "90.9%",
            }
        ],
        today_snapshot={"Total Stores": "45", "Total Activation": "17"},
        previous_day_rows=[],
        chart_tables=[],
    )

    summary = answer_home_question("How are we doing?", snapshot)
    top = answer_home_question("Top stores right now", snapshot)

    assert "4196 activations" in summary.answer
    assert "ROCKON MAIN" in top.answer
    assert top.reports_used == ("home_dashboard",)
