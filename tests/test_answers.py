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


def test_answers_finance_summary_and_kpi_join(tmp_path):
    finance = _write(
        tmp_path / "finance.csv",
        """
Market,StoreID,Store Name,Emp ID,Invoice #,Invoice Date,Application No,Finance Company,Invoice Amount,Approved Amount,Financed Amount,Non-Financed Amount
HOUSTON,001,ROCKON MAIN,AAA111,INV1,2026-06-01,APP1,Acme,$500.00,$450.00,$400.00,$100.00
HOUSTON,002,ROCKON NASA,BBB222,INV2,2026-06-01,APP2,Acme,$700.00,$650.00,$600.00,$100.00
HOUSTON,002,ROCKON NASA,BBB222,INV3,2026-06-02,APP3,Other,$300.00,$250.00,$200.00,$100.00
""",
    )
    kpi = _write(
        tmp_path / "kpi.csv",
        """
marketid,custno,company,username,name,grossprofit
HOUSTON,002,ROCKON NASA,BBB222,Bob,900.00
""",
    )

    total = answer_from_exports("Total financed amount.", {"finance_report": finance})
    joined = answer_from_exports("Which employee had the highest financed dollar amount and their gross profit?", {"finance_report": finance, "kpi_report_by_employee": kpi})

    assert "$1,200.00" in total.answer
    assert "Bob" in joined.answer
    assert "$900.00" in joined.answer


def test_answers_trade_inventory_and_phone_trend(tmp_path):
    trade = _write(
        tmp_path / "trade.csv",
        """
Store Name,Emp ID,Invoice #,Invoice Date,Offered,TI Applied,RMA,Serial,Carrier,Make,Model
ROCKON MAIN,AAA111,INV1,2026-06-01,100,80,RMA1,S1,T-Mobile,Apple,iPhone 13
ROCKON NASA,BBB222,INV2,2026-06-02,50,30,RMA2,S2,T-Mobile,Samsung,A16
""",
    )
    inventory = _write(
        tmp_path / "inventory.csv",
        """
custno,company,marketid,region,item,manufacturer,color,itmdesc,serialized,qty,cost
001,ROCKON MAIN,HOUSTON,HASSAN,IP13,Apple,Black,iPhone 13,Y,4,100.00
002,ROCKON NASA,HOUSTON,ASAD,A16,Samsung,Black,Samsung A16,N,3,50.00
""",
    )
    trend = _write(
        tmp_path / "trend.csv",
        """
marketid,custno,company,item,itmdesc,onhand,sale7,sale14,sale30
HOUSTON,001,ROCKON MAIN,A16,Samsung A16 5G,10,2,4,9
HOUSTON,002,ROCKON NASA,IP13,Apple iPhone 13,5,1,2,3
""",
    )

    by_carrier = answer_from_exports("How many trade-ins applied, by carrier?", {"trade_in_custom_report": trade})
    samsung = answer_from_exports("How many Samsung phones in stock?", {"inventory_report": inventory})
    sold = answer_from_exports("How many Samsung A16 5G sold in the last 7 days?", {"phone_trend_by_market": trend})

    assert "T-Mobile: 2" in by_carrier.answer
    assert "Samsung inventory quantity is 3" in samsung.answer
    assert "sale7 units" in sold.answer
    assert "2" in sold.answer


def test_answers_inventory_item_model_stock(tmp_path):
    inventory = _write(
        tmp_path / "inventory.csv",
        """
custno,company,marketid,region,item,manufacturer,color,itmdesc,serialized,qty,cost
001,ROCKON MAIN,HOUSTON,HASSAN,IP13,Apple,Black,Apple iPhone 13 128GB,Y,4,100.00
002,ROCKON NASA,HOUSTON,ASAD,IP13,Apple,Black,Apple iPhone 13 128GB,Y,3,110.00
003,ROCKON WALLER,HOUSTON,ASAD,A16,Samsung,Black,Samsung A16,N,5,50.00
""",
    )

    result = answer_from_exports("iphone 13 how many stocks", {"inventory_report": inventory})

    assert "Apple iPhone 13" in result.answer
    assert "is 7" in result.answer
    assert "$730.00" in result.answer


def test_answers_bill_payment_listing(tmp_path):
    bill = _write(
        tmp_path / "bill.csv",
        """
marketid,custno,company,prodline,category,username,invno,adddate,item,itmdesc,qty,price,cost,profit,pptax,taxamount,total
HOUSTON,001,ROCKON NASA,BILL,Bill Pay,AAA111,INV1,2026-06-01,ITEM,Payment,1,50,0,5,0,1,51
HOUSTON,001,ROCKON NASA,BILL,Bill Pay,BBB222,INV2,2026-06-02,ITEM,Payment,1,75,0,7,0,2,77
HOUSTON,002,ROCKON MAIN,BILL,Bill Pay,CCC333,INV3,2026-06-03,ITEM,Payment,1,100,0,10,0,3,103
""",
    )

    result = answer_from_exports("Total bill payment at ROCKON NASA.", {"bill_payment_listing": bill})

    assert "$128.00" in result.answer
    assert "2" in result.answer
    assert result.rows_used == 2
