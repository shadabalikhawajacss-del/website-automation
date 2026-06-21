import struct

from rtbdi_assistant.exports import read_raw_biff


def _label(row: int, col: int, value: str) -> bytes:
    encoded = value.encode("latin1")
    payload = row.to_bytes(2, "little") + col.to_bytes(2, "little") + b"\x40\x00\x00" + bytes([len(encoded)]) + encoded
    return b"\x04\x00" + len(payload).to_bytes(2, "little") + payload


def _number(row: int, col: int, value: float) -> bytes:
    payload = row.to_bytes(2, "little") + col.to_bytes(2, "little") + b"\x40\x00\x00" + struct.pack("<d", value)
    return b"\x03\x00" + len(payload).to_bytes(2, "little") + payload


def test_read_raw_biff_label_and_number(tmp_path):
    path = tmp_path / "raw.xls"
    path.write_bytes(
        b"\x09\x00\x04\x00\x02\x00\x10\x00"
        + _label(0, 0, "marketid")
        + _label(0, 1, "cost")
        + _label(1, 0, "HOUSTON")
        + _number(1, 1, 618.99)
    )

    df = read_raw_biff(path)

    assert df.iloc[0, 0] == "marketid"
    assert df.iloc[1, 0] == "HOUSTON"
    assert df.iloc[1, 1] == 618.99
