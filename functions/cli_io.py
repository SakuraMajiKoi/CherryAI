"""CLI IO adapter for CherryAI.

This module bridges the CLI to the formats module, providing consistent
file reading and writing operations using format handlers.

All CLI file operations should go through this module to avoid duplication
with the formats/ handlers.
"""

from pathlib import Path
from typing import Any, List, Optional, Tuple

from CherryAI.formats import get_handler, SIMPLE_FORMATS as FORMAT_EXTENSIONS


__all__ = [
    "read_text_via_handler",
    "write_text_via_handler", 
    "read_table_via_handler",
    "write_table_via_handler",
    "get_supported_extensions",
    "is_supported_format",
]


def get_supported_extensions() -> set:
    """Return the set of supported file extensions for CLI.
    
    Returns:
        Set of extensions like {'.txt', '.csv', '.tsv', '.json', '.xlsx'}.
    """
    return FORMAT_EXTENSIONS


def is_supported_format(path: Path) -> bool:
    """Check if a file has a supported format based on extension.
    
    Args:
        path: File path to check.
        
    Returns:
        True if format is supported, False otherwise.
    """
    return path.suffix.lower() in FORMAT_EXTENSIONS


def read_text_via_handler(path: Path, encoding: str = "utf-8") -> str:
    """Read text content from a file using format handler.
    
    For txt files, returns the full text content.
    For table files (csv, tsv, xlsx), returns column A joined by newlines.
    For json files, returns values joined by newlines.
    
    Args:
        path: Path to the file to read.
        encoding: Text encoding (default: utf-8).
        
    Returns:
        Text content as a single string.
        
    Raises:
        ValueError: If no handler found for the file format.
    """
    handler = get_handler(path.suffix)
    if handler is None:
        raise ValueError(f"No handler found for format: {path.suffix}")
    
    lines = handler.extract(path, encoding=encoding)
    return "\n".join(lines)


def write_text_via_handler(
    path: Path,
    content: str,
    original_lines: Optional[List[str]] = None,
    encoding: str = "utf-8",
) -> None:
    """Write text content to a file using format handler.
    
    Args:
        path: Path to write the file.
        content: Text content to write (lines separated by newlines).
        original_lines: Optional original lines for pair formats.
        encoding: Text encoding (default: utf-8).
        
    Raises:
        ValueError: If no handler found for the file format.
    """
    handler = get_handler(path.suffix)
    if handler is None:
        raise ValueError(f"No handler found for format: {path.suffix}")
    
    lines = content.split("\n") if content else []
    handler.inject(path, lines, original_lines=original_lines, encoding=encoding)


def read_table_via_handler(path: Path, encoding: str = "utf-8") -> Tuple[List[List[str]], str]:
    """Read tabular data from a file using format handler.
    
    This function reads data from CSV, TSV, or XLSX files and returns
    the data as rows with a delimiter indicator.
    
    Args:
        path: Path to the file to read.
        encoding: Text encoding (default: utf-8).
        
    Returns:
        Tuple of (rows, delimiter) where:
        - rows: List of rows, each row is a list of cell values.
        - delimiter: The detected delimiter (',' for csv, '\\t' for tsv, None for xlsx).
        
    Raises:
        ValueError: If no handler found for the file format.
    """
    handler = get_handler(path.suffix)
    if handler is None:
        raise ValueError(f"No handler found for format: {path.suffix}")
    
    # For table formats, we need the raw rows not joined text
    # The handler.extract() returns lines (column A values)
    # We need to re-read as table to get full rows
    ext = path.suffix.lower()
    
    if ext == ".txt":
        # txt is not a table format - wrap each line as a single-column row
        lines = handler.extract(path, encoding=encoding)
        return [[line] for line in lines], "\n"
    
    # For csv, tsv, xlsx we need full row access
    # Re-use the handler but access the underlying table data
    if ext in (".csv", ".tsv"):
        import csv as csv_module
        delim = "\t" if ext == ".tsv" else ","
        rows: List[List[str]] = []
        with path.open("r", encoding=encoding, newline="") as f:
            reader = csv_module.reader(f, delimiter=delim)
            for row in reader:
                rows.append(list(row))
        return rows, delim
    
    if ext == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path)
            ws = wb.active
            if ws is None:
                return [], ""
            rows = []
            for xlsx_row in ws.iter_rows(values_only=True):
                rows.append([str(cell) if cell is not None else "" for cell in xlsx_row])
            return rows, ""  # xlsx doesn't have a text delimiter
        except ImportError:
            raise ValueError("openpyxl required for xlsx files")
    
    if ext == ".json":
        import json
        content = path.read_text(encoding=encoding)
        data = json.loads(content)
        if isinstance(data, list):
            # Array of strings or pairs
            rows = []
            for item in data:
                if isinstance(item, str):
                    rows.append([item])
                elif isinstance(item, list) and len(item) >= 1:
                    rows.append([str(x) for x in item])
                elif isinstance(item, dict):
                    # Object with original/translated keys
                    orig = item.get("original", item.get("source", ""))
                    trans = item.get("translated", item.get("target", ""))
                    rows.append([str(trans), str(orig)])
            return rows, ""
        return [], ""
    
    # Fallback: treat as single-column
    lines = handler.extract(path, encoding=encoding)
    return [[line] for line in lines], ""


def write_table_via_handler(
    path: Path,
    rows: List[List[str]],
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> None:
    """Write tabular data to a file using format handler.
    
    Args:
        path: Path to write the file.
        rows: List of rows, each row is a list of cell values.
        delimiter: Delimiter for csv/tsv (',' or '\\t'). Ignored for xlsx/json.
        encoding: Text encoding (default: utf-8).
        
    Raises:
        ValueError: If no handler found for the file format.
    """
    handler = get_handler(path.suffix)
    if handler is None:
        raise ValueError(f"No handler found for format: {path.suffix}")
    
    ext = path.suffix.lower()
    
    if ext == ".txt":
        # For txt, write only the first column of each row
        lines = [row[0] if row else "" for row in rows]
        handler.inject(path, lines, encoding=encoding)
        return
    
    if ext in (".csv", ".tsv"):
        import csv as csv_module
        actual_delim = "\t" if ext == ".tsv" else ","
        with path.open("w", encoding=encoding, newline="") as f:
            writer = csv_module.writer(f, delimiter=actual_delim)
            writer.writerows(rows)
        return
    
    if ext == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            if ws is not None:
                for row_idx, row in enumerate(rows, 1):
                    for col_idx, value in enumerate(row, 1):
                        ws.cell(row=row_idx, column=col_idx, value=value)
            wb.save(path)
            return
        except ImportError:
            raise ValueError("openpyxl required for xlsx files")
    
    if ext == ".json":
        import json
        # Write as array of rows
        output: list[Any] = []
        for row in rows:
            if len(row) == 1:
                output.append(row[0])
            elif len(row) >= 2:
                output.append({"translated": row[0], "original": row[1]})
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding=encoding)
        return
    
    # Fallback: write first column as lines
    lines = [row[0] if row else "" for row in rows]
    handler.inject(path, lines, encoding=encoding)


def detect_delimiter_from_extension(path: Path) -> str:
    """Detect the appropriate delimiter based on file extension.
    
    Args:
        path: File path to check.
        
    Returns:
        Delimiter string (',' for csv, '\\t' for tsv, '' for others).
    """
    ext = path.suffix.lower()
    if ext == ".tsv":
        return "\t"
    if ext == ".csv":
        return ","
    return ""
