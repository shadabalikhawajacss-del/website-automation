from pathlib import Path

from rtbdi_assistant.answers import answer_from_exports


def _write(path: Path, content: str) -> Path:
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def test_answers_conversion_ratio_from_export(tmp_path):
    export = _write(
        tmp_path / "conversion.csv",
        """
marketid,custno,company,username,name,lastname,totact,totqty,ratio
HOUSTON,PURE001,ROCKON MAIN,NAT12345,Natalie,Gonzalez,10,5,200.00
HOUSTON,PURE002,ROCKON NASA,NAT12345,Natalie,Gonzalez,5,5,100.00
""",
    )

    result = answer_from_exports("What is Natalie Gonzalez's conversion ratio?", {"employee_conversion_ratio": export})

    assert "Natalie Gonzalez" in result.answer
    assert "150.00%" in result.answer
    assert result.rows_used == 2


def test_answers_store_and_accessory_total_from_performance_export(tmp_path):
    export = _write(
        tmp_path / "performance.csv",
        """
marketid,custno,company,username,name,taxrate,boxes,newact,upgsor,reactact,newreactact,totact,totaccessory,totaccessoryqty,totaccessorycost,totpaymentqty,totpayment,hoursworked,boxperhour,aph
HOUSTON,PURE001,ROCKON NASA,AKA11111,Akash Kotak,0,0,0,0,0,0,4,100.25,1,50,0,0,8,0.5,12.53
HOUSTON,PURE001,ROCKON NASA,NAT12345,Natalie Gonzalez,0,0,0,0,0,0,6,200.75,2,75,0,0,9,0.6,22.31
""",
    )

    store = answer_from_exports("Which store does Akash Kotak work at?", {"employee_performance_report": export})
    total = answer_from_exports("Total accessory sales at ROCKON NASA.", {"employee_performance_report": export})

    assert "ROCKON NASA" in store.answer
    assert "$301.00" in total.answer
    assert total.rows_used == 2


def test_answers_employee_ranking_from_box_sales_export(tmp_path):
    ranking = _write(
        tmp_path / "ranking.csv",
        """
username,name,totact,totaccessory,totaccessoryprofit
AAA111,Alice,10,100.00,50.00
BBB222,Bob,20,250.00,120.00
CCC333,Cara,15,150.00,80.00
""",
    )

    result = answer_from_exports("Top 2 employees by accessory sales.", {"employee_ranking_by_box_sales": ranking})

    assert "Bob" in result.answer
    assert "$250.00" in result.answer
    assert "Alice" not in result.answer


def test_answers_multireport_top_seller_merge(tmp_path):
    ranking = _write(
        tmp_path / "ranking.csv",
        """
username,name,totact,totaccessory
AAA111,Alice,20,100.00
BBB222,Bob,10,50.00
""",
    )
    mrc = _write(
        tmp_path / "mrc.csv",
        """
marketid,username,name,lastname,hours,totact,plan50,plan60,secure5,tablet20
HOUSTON,AAA111,Alice,Smith,8,20,3,2,5,1
""",
    )
    kpi = _write(
        tmp_path / "kpi.csv",
        """
marketid,custno,company,username,name,grossprofit
HOUSTON,001,ROCKON MAIN,AAA111,Alice,300.00
HOUSTON,002,ROCKON NASA,BBB222,Bob,120.00
""",
    )
    inventory = _write(
        tmp_path / "inventory.csv",
        """
custno,company,item,itmdesc,qty,cost
001,ROCKON MAIN,ITEM1,Phone,4,100.00
001,ROCKON MAIN,ITEM2,Case,3,10.00
""",
    )

    result = answer_from_exports(
        "Top seller's plan mix, their store inventory, and gross profit vs #2.",
        {
            "employee_ranking_by_box_sales": ranking,
            "employee_mrc_matrix_report": mrc,
            "kpi_report_by_employee": kpi,
            "inventory_report": inventory,
        },
    )

    assert "Alice" in result.answer
    assert "plan50 3" in result.answer
    assert "ROCKON MAIN" in result.answer
    assert "$430.00" in result.answer
    assert result.reports_used == (
        "employee_ranking_by_box_sales",
        "employee_mrc_matrix_report",
        "kpi_report_by_employee",
        "inventory_report",
    )
