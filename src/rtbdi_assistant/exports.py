from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class SheetSummary:
    name: str
    rows: int
    header_row: int
    columns: tuple[str, ...]


@dataclass(frozen=True)
class ExportSummary:
    path: Path
    kind: str
    sheets: tuple[SheetSummary, ...]
    error: str | None = None


def _clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def infer_header(df: pd.DataFrame, max_scan_rows: int = 30) -> tuple[int, tuple[str, ...]]:
    best_index = 0
    best_score = -1.0
    for index, row in df.head(max_scan_rows).iterrows():
        values = [_clean(value) for value in row.tolist()]
        non_empty = [value for value in values if value and not value.casefold().startswith("unnamed:")]
        score = len(non_empty) + len(set(non_empty)) * 0.25
        if len(non_empty) >= 2 and score > best_score:
            best_index = int(index)
            best_score = score
    seen: dict[str, int] = {}
    columns: list[str] = []
    for value in [_clean(value) for value in df.iloc[best_index].tolist()]:
        if not value or value.casefold().startswith("unnamed:"):
            continue
        seen[value] = seen.get(value, 0) + 1
        columns.append(value if seen[value] == 1 else f"{value} ({seen[value]})")
    return best_index, tuple(columns)


def read_export(path: Path) -> dict[str, pd.DataFrame]:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return {"csv": pd.read_csv(path, header=None, dtype=str, encoding_errors="ignore")}
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(path, sheet_name=None, header=None, dtype=str, engine="openpyxl")
    if path.read_bytes()[:64].lstrip().startswith(b"<"):
        return {f"table_{i + 1}": table for i, table in enumerate(pd.read_html(path))}
    if suffix == ".xls":
        try:
            return pd.read_excel(path, sheet_name=None, header=None, dtype=str, engine="xlrd")
        except AssertionError:
            return {"raw_biff": read_raw_biff(path)}
    raise ValueError(f"Unsupported export type: {path}")


def read_raw_biff(path: Path) -> pd.DataFrame:
    """Read simple raw BIFF streams that are not wrapped in OLE.

    Some RT BDI legacy exports are raw BIFF records. `xlrd` rejects at least one
    of them with AssertionError, but the LABEL and NUMBER records are enough to
    reconstruct a useful table.
    """

    blob = path.read_bytes()
    cells: dict[tuple[int, int], object] = {}
    position = 0
    while position + 4 <= len(blob):
        opcode = int.from_bytes(blob[position : position + 2], "little")
        length = int.from_bytes(blob[position + 2 : position + 4], "little")
        payload = blob[position + 4 : position + 4 + length]
        if len(payload) < length:
            break
        if opcode == 0x0004 and length >= 8:
            row = int.from_bytes(payload[0:2], "little")
            col = int.from_bytes(payload[2:4], "little")
            text_len = payload[7]
            text = payload[8 : 8 + text_len].decode("latin1", errors="ignore")
            cells[(row, col)] = text
        elif opcode == 0x0003 and length >= 15:
            row = int.from_bytes(payload[0:2], "little")
            col = int.from_bytes(payload[2:4], "little")
            cells[(row, col)] = struct.unpack("<d", payload[7:15])[0]
        elif opcode == 0x0005 and length >= 8:
            row = int.from_bytes(payload[0:2], "little")
            col = int.from_bytes(payload[2:4], "little")
            cells[(row, col)] = payload[7]
        position += 4 + length

    if not cells:
        raise ValueError(f"No raw BIFF cells found in {path}")

    max_row = max(row for row, _ in cells)
    max_col = max(col for _, col in cells)
    rows = []
    for row in range(max_row + 1):
        rows.append([cells.get((row, col), "") for col in range(max_col + 1)])
    return pd.DataFrame(rows)


def summarize_export(path: Path) -> ExportSummary:
    try:
        sheets = []
        for name, df in read_export(path).items():
            header_index, columns = infer_header(df)
            sheets.append(SheetSummary(str(name), int(len(df)), header_index + 1, columns))
        return ExportSummary(path=path, kind=path.suffix.casefold(), sheets=tuple(sheets))
    except Exception as exc:  # pragma: no cover - retained for asset triage output
        return ExportSummary(path=path, kind=path.suffix.casefold(), sheets=(), error=repr(exc))


def iter_export_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if "__MACOSX" in path.parts or not path.is_file():
            continue
        if path.suffix.casefold() in {".csv", ".xls", ".xlsx", ".xlsm"}:
            yield path
