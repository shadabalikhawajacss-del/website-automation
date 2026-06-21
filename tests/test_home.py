from rtbdi_assistant.home import _key_values_from_text, _rows_from_table_text


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
