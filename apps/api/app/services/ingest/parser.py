import csv
import io
import logging
from pathlib import Path
from typing import Any

import openpyxl

from app.models.database import SessionLocal
from app.models.entities import ColumnModel, Dataset, DatasetVersion, RowModel

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000


def deduplicate_headers(raw_headers: list[str]) -> list[str]:
    """Clean and deduplicate column header names with suffix _2, _3 etc."""
    seen: dict[str, int] = {}
    normalized: list[str] = []

    for idx, header in enumerate(raw_headers):
        clean_name = str(header).strip().lstrip("\ufeff") if header is not None else ""
        if not clean_name:
            clean_name = f"column_{idx + 1}"

        if clean_name in seen:
            seen[clean_name] += 1
            normalized.append(f"{clean_name}_{seen[clean_name]}")
        else:
            seen[clean_name] = 1
            normalized.append(clean_name)

    return normalized


def detect_encoding(raw_bytes: bytes) -> str:
    """Detect text encoding trying UTF-8, then UTF-8-BOM, then charset-normalizer."""
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"

    try:
        raw_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    try:
        import charset_normalizer

        match = charset_normalizer.from_bytes(raw_bytes).best()
        if match and match.encoding:
            return match.encoding
    except Exception as exc:
        logger.warning("charset-normalizer detection failed: %s", exc)

    return "latin-1"


def detect_delimiter(sample_text: str) -> str:
    """Detect CSV/TSV delimiter from text sample."""
    delimiters = [",", "\t", ";", "|"]
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=delimiters)
        if dialect.delimiter in delimiters:
            return dialect.delimiter
    except Exception:
        pass

    lines = [line for line in sample_text.splitlines() if line.strip()][:10]
    if not lines:
        return ","

    best_delim = ","
    best_score = -1
    for delim in delimiters:
        counts = [line.count(delim) for line in lines]
        if counts and counts[0] > 0 and len(set(counts)) == 1:
            return delim
        total = sum(counts)
        if total > best_score:
            best_score = total
            best_delim = delim

    return best_delim


def parse_csv_content(raw_bytes: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV/TSV bytes into headers and string rows."""
    encoding = detect_encoding(raw_bytes)
    decoded_text = raw_bytes.decode(encoding, errors="replace")

    sample = decoded_text[:4096]
    delimiter = detect_delimiter(sample)

    reader = csv.reader(io.StringIO(decoded_text), delimiter=delimiter)

    raw_headers = None
    for row in reader:
        if any(cell.strip() for cell in row):
            raw_headers = row
            break

    if not raw_headers:
        return [], []

    headers = deduplicate_headers(raw_headers)
    num_cols = len(headers)

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        # Skip completely empty trailing lines
        if not any(cell.strip() for cell in raw_row):
            continue

        # Handle ragged rows (pad if short, trim if long)
        padded = list(raw_row)
        if len(padded) < num_cols:
            padded.extend([""] * (num_cols - len(padded)))
        elif len(padded) > num_cols:
            padded = padded[:num_cols]

        row_dict = {headers[i]: padded[i] for i in range(num_cols)}
        rows.append(row_dict)

    return headers, rows


def detect_excel_header_row(ws: openpyxl.worksheet.worksheet.Worksheet) -> int:
    """Detect the real header row in an Excel worksheet, skipping top banner titles."""
    max_scan = min(15, ws.max_row or 1)
    best_row = 1
    best_score = -1

    for r in range(1, max_scan + 1):
        row_vals = [ws.cell(r, c).value for c in range(1, (ws.max_column or 1) + 1)]
        non_empty = [v for v in row_vals if v is not None and str(v).strip() != ""]
        if not non_empty:
            continue

        score = len(non_empty)
        if all(isinstance(v, str) for v in non_empty):
            score += 2

        if score > best_score:
            best_score = score
            best_row = r

    return best_row


def inspect_xlsx_sheets(raw_bytes: bytes) -> list[str]:
    """Inspect and return all sheet names in an Excel workbook."""
    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True)
    sheets = list(wb.sheetnames)
    wb.close()
    return sheets


def parse_xlsx_sheet(
    raw_bytes: bytes, sheet_name: str | None = None
) -> tuple[list[str], list[dict[str, str]]]:
    """Parse a single Excel worksheet into headers and string rows with merged-cell forward filling."""
    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
    if sheet_name and sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.active

    # Forward-fill merged cells
    merged_ranges = list(ws.merged_cells.ranges)
    merged_values: dict[tuple[int, int], Any] = {}
    for m_range in merged_ranges:
        top_left_val = ws.cell(m_range.min_row, m_range.min_col).value
        for r in range(m_range.min_row, m_range.max_row + 1):
            for c in range(m_range.min_col, m_range.max_col + 1):
                merged_values[(r, c)] = top_left_val

    header_row_idx = detect_excel_header_row(ws)
    max_col = ws.max_column or 1
    max_row = ws.max_row or 1

    # Extract headers
    raw_headers = []
    for c in range(1, max_col + 1):
        val = merged_values.get((header_row_idx, c), ws.cell(header_row_idx, c).value)
        raw_headers.append(str(val) if val is not None else "")

    headers = deduplicate_headers(raw_headers)
    num_cols = len(headers)

    # Extract data rows starting from the row after header
    rows: list[dict[str, str]] = []
    for r in range(header_row_idx + 1, max_row + 1):
        row_vals = []
        for c in range(1, max_col + 1):
            val = merged_values.get((r, c), ws.cell(r, c).value)
            if val is None:
                row_vals.append("")
            else:
                row_vals.append(str(val).strip())

        # Skip rows where all cells are blank
        if not any(row_vals):
            continue

        if len(row_vals) < num_cols:
            row_vals.extend([""] * (num_cols - len(row_vals)))
        elif len(row_vals) > num_cols:
            row_vals = row_vals[:num_cols]

        row_dict = {headers[i]: row_vals[i] for i in range(num_cols)}
        rows.append(row_dict)

    wb.close()
    return headers, rows


def parse_and_persist_dataset(
    dataset_id: str,
    file_path: str,
    created_by: str | None = None,
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """Parse the raw file and persist columns and rows into the database."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Source file not found at: {file_path}")

    raw_bytes = path.read_bytes()
    suffix = path.suffix.lower()

    if suffix in (".csv", ".tsv"):
        headers, rows = parse_csv_content(raw_bytes)
    elif suffix in (".xlsx", ".xlsm"):
        headers, rows = parse_xlsx_sheet(raw_bytes, sheet_name=sheet_name)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter_by(id=dataset_id).first()
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        # 1. Insert ColumnModel records with position
        cols = [
            ColumnModel(
                dataset_id=dataset.id,
                name=col_name,
                position=pos,
            )
            for pos, col_name in enumerate(headers)
        ]
        db.add_all(cols)
        db.flush()

        # 2. Insert RowModel records in batches
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            row_objs = [
                RowModel(
                    dataset_id=dataset.id,
                    row_index=i + offset,
                    raw_json=row_dict,
                )
                for offset, row_dict in enumerate(batch)
            ]
            db.add_all(row_objs)
            db.flush()

        # 3. Create DatasetVersion 1
        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=1,
            created_by=created_by,
            note="Original import",
        )
        db.add(version)

        # 4. Mark dataset as ready
        dataset.status = "ready"
        dataset.error_message = None
        db.commit()

        logger.info(
            "Successfully parsed dataset %s: %d columns, %d rows",
            dataset_id,
            len(headers),
            len(rows),
        )
        return {
            "dataset_id": dataset.id,
            "columns": len(headers),
            "rows": len(rows),
            "status": "ready",
        }

    except Exception as exc:
        db.rollback()
        try:
            dataset = db.query(Dataset).filter_by(id=dataset_id).first()
            if dataset:
                dataset.status = "failed"
                dataset.error_message = str(exc)
                db.commit()
        except Exception as update_err:
            logger.error("Failed to update dataset failure status: %s", update_err)
        logger.error("Dataset parsing failed for %s: %s", dataset_id, exc, exc_info=True)
        raise
    finally:
        db.close()
