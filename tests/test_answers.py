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
