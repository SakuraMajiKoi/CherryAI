"""Simple format handlers for CherryAI.

This module provides format handlers for basic text and table formats:
- txt: Plain text files (one line per line)
- csv: Comma-separated values
- tsv: Tab-separated values
- json: JSON files (array of strings or array of [original, translated] pairs)
- xlsx: Excel files (column A = original, column B = translated)

Each handler supports:
- extract(): Read text lines from a file
- inject(): Write text lines to a file (optionally with original lines)
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import FormatHandler


__all__ = [
    "TxtHandler",
    "CsvHandler",
    "TsvHandler",
    "JsonHandler",
    "XlsxHandler",
    "get_handlers",
]


class TxtHandler(FormatHandler):
    """Plain text file handler.
    
    Reads and writes text files with one line per line.
    Does not support storing original lines alongside translations.
    """
    
    format_id = "txt"
    extensions = (".txt",)
    description = "Plain text files (one line per line)"
    supports_pairs = False
    
    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract lines from a text file.
        
        Args:
            path: Path to the text file.
            encoding: Text encoding.
            
        Returns:
            List of text lines (without trailing newlines).
        """
        content = path.read_text(encoding=encoding)
        # Split on newlines, preserving empty lines
        lines = content.splitlines()
        return lines
    
    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8"
    ) -> None:
        """Write lines to a text file.
        
        Args:
            path: Path to write the file.
            lines: Lines to write.
            original_lines: Ignored (txt doesn't support pairs).
            encoding: Text encoding.
        """
        content = "\n".join(lines)
        path.write_text(content, encoding=encoding, newline="")


class CsvHandler(FormatHandler):
    """CSV file handler.
    
    Reads from column A (or first column).
    Writes to column A (translated) and optionally column B (original).
    """
    
    format_id = "csv"
    extensions = (".csv",)
    description = "Comma-separated values (column A = text, column B = original)"
    supports_pairs = True
    
    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract text from column A of a CSV file.
        
        Args:
            path: Path to the CSV file.
            encoding: Text encoding.
            
        Returns:
            List of text values from column A.
        """
        lines = []
        with path.open("r", encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    lines.append(row[0])
                else:
                    lines.append("")
        return lines
    
    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8"
    ) -> None:
        """Write text to a CSV file.
        
        Args:
            path: Path to write the file.
            lines: Translated lines for column A.
            original_lines: Optional original lines for column B.
            encoding: Text encoding.
        """
        with path.open("w", encoding=encoding, newline="") as f:
            writer = csv.writer(f)
            for i, line in enumerate(lines):
                if original_lines and i < len(original_lines):
                    writer.writerow([line, original_lines[i]])
                else:
                    writer.writerow([line])


class TsvHandler(FormatHandler):
    """TSV file handler.
    
    Reads from column A (or first column).
    Writes to column A (translated) and optionally column B (original).
    """
    
    format_id = "tsv"
    extensions = (".tsv",)
    description = "Tab-separated values (column A = text, column B = original)"
    supports_pairs = True
    
    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract text from column A of a TSV file.
        
        Args:
            path: Path to the TSV file.
            encoding: Text encoding.
            
        Returns:
            List of text values from column A.
        """
        lines = []
        with path.open("r", encoding=encoding, newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if row:
                    lines.append(row[0])
                else:
                    lines.append("")
        return lines
    
    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8"
    ) -> None:
        """Write text to a TSV file.
        
        Args:
            path: Path to write the file.
            lines: Translated lines for column A.
            original_lines: Optional original lines for column B.
            encoding: Text encoding.
        """
        with path.open("w", encoding=encoding, newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            for i, line in enumerate(lines):
                if original_lines and i < len(original_lines):
                    writer.writerow([line, original_lines[i]])
                else:
                    writer.writerow([line])


class JsonHandler(FormatHandler):
    """JSON file handler.
    
    Supports multiple JSON structures:
    - Array of strings: ["line1", "line2", ...]
    - Array of pairs: [["original1", "translated1"], ...]
    - Array of objects: [{"original": "...", "translated": "..."}, ...]
    - Dictionary: {"original1": "translated1", "original2": "translated2", ...}
      Keys are original text, values are translations
    
    When injecting with original_lines, outputs array of objects with
    both original and translated fields.
    """
    
    format_id = "json"
    extensions = (".json",)
    description = "JSON files (array of strings, pairs, or key-value dictionary)"
    supports_pairs = True
    
    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract text from a JSON file.
        
        Supports:
        - Array of strings
        - Array of [original, translated] pairs (extracts original)
        - Array of {"original": ..., "translated": ...} objects
        - Dictionary where keys are original text, values are translations
        
        Args:
            path: Path to the JSON file.
            encoding: Text encoding.
            
        Returns:
            List of text strings.
        """
        content = path.read_text(encoding=encoding)
        data = json.loads(content)
        
        lines = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    lines.append(item)
                elif isinstance(item, list) and len(item) >= 1:
                    # [original, translated] or just [text]
                    lines.append(str(item[0]))
                elif isinstance(item, dict):
                    # {"original": ..., "translated": ...}
                    if "original" in item:
                        lines.append(str(item["original"]))
                    elif "text" in item:
                        lines.append(str(item["text"]))
                    else:
                        # Take first string value
                        for v in item.values():
                            if isinstance(v, str):
                                lines.append(v)
                                break
                        else:
                            lines.append("")
        elif isinstance(data, dict):
            # Dictionary format: {"original_text": "translated_text", ...}
            # Keys are original text, values are translations (may be empty)
            for key in data.keys():
                if isinstance(key, str):
                    lines.append(key)
        
        return lines
    
    def extract_with_translations(
        self,
        path: Path,
        encoding: str = "utf-8"
    ) -> List[Tuple[str, str]]:
        """Extract text with existing translations from a JSON file.
        
        For dictionary format where keys are original and values are translations.
        
        Args:
            path: Path to the JSON file.
            encoding: Text encoding.
            
        Returns:
            List of (original, translated) tuples.
        """
        content = path.read_text(encoding=encoding)
        data = json.loads(content)
        
        pairs: List[Tuple[str, str]] = []
        if isinstance(data, dict):
            # Dictionary format: {"original": "translated", ...}
            for key, value in data.items():
                if isinstance(key, str):
                    translated = str(value) if value else ""
                    pairs.append((key, translated))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, list) and len(item) >= 2:
                    pairs.append((str(item[0]), str(item[1])))
                elif isinstance(item, dict):
                    orig = item.get("original", item.get("text", ""))
                    trans = item.get("translated", item.get("translation", ""))
                    pairs.append((str(orig), str(trans)))
                elif isinstance(item, str):
                    pairs.append((item, ""))
        
        return pairs
    
    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8",
        preserve_format: bool = False
    ) -> None:
        """Write text to a JSON file.
        
        If preserve_format is True and original file was a dictionary,
        writes back as dictionary format.
        
        If original_lines is provided (without preserve_format), writes 
        array of objects: [{"original": "...", "translated": "..."}, ...]
        
        Otherwise writes simple array of strings.
        
        Args:
            path: Path to write the file.
            lines: Translated lines.
            original_lines: Optional original lines.
            encoding: Text encoding.
            preserve_format: If True, try to preserve original file format.
        """
        data: Any
        
        # Check if we should preserve dictionary format
        if preserve_format and original_lines and path.exists():
            try:
                existing = json.loads(path.read_text(encoding=encoding))
                if isinstance(existing, dict):
                    # Preserve dictionary format: {"original": "translated"}
                    result: Dict[str, str] = {}
                    for i, orig in enumerate(original_lines):
                        trans = lines[i] if i < len(lines) else ""
                        result[orig] = trans
                    data = result
                    content = json.dumps(data, ensure_ascii=False, indent=2)
                    path.write_text(content, encoding=encoding)
                    return
            except Exception:
                pass  # Fall through to default handling
        
        if original_lines:
            # Write as array of objects with both original and translated
            entries: List[Dict[str, str]] = []
            for i, line in enumerate(lines):
                entry: Dict[str, str] = {"translated": line}
                if i < len(original_lines):
                    entry["original"] = original_lines[i]
                entries.append(entry)
            data = entries
        else:
            # Write as simple array of strings
            data = lines
        
        content = json.dumps(data, ensure_ascii=False, indent=2)
        path.write_text(content, encoding=encoding)
    
    def inject_dict(
        self,
        path: Path,
        translations: Dict[str, str],
        encoding: str = "utf-8"
    ) -> None:
        """Write translations to a JSON file in dictionary format.
        
        Args:
            path: Path to write the file.
            translations: Dictionary mapping original text to translations.
            encoding: Text encoding.
        """
        content = json.dumps(translations, ensure_ascii=False, indent=2)
        path.write_text(content, encoding=encoding)
    
    def get_metadata(self, path: Path) -> Dict[str, Any]:
        """Get JSON file metadata including structure type."""
        metadata = super().get_metadata(path)
        
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
                data = json.loads(content)
                
                if isinstance(data, dict):
                    # Dictionary format: {"original": "translated", ...}
                    metadata["structure"] = "dictionary"
                    metadata["line_count"] = len(data)
                    # Check if it has any translations filled in
                    filled = sum(1 for v in data.values() if v)
                    metadata["translated_count"] = filled
                elif isinstance(data, list) and data:
                    first = data[0]
                    if isinstance(first, str):
                        metadata["structure"] = "array_of_strings"
                    elif isinstance(first, list):
                        metadata["structure"] = "array_of_pairs"
                    elif isinstance(first, dict):
                        metadata["structure"] = "array_of_objects"
                        metadata["keys"] = list(first.keys())
                    
                    metadata["line_count"] = len(data)
            except Exception as e:
                metadata["error"] = str(e)
        
        return metadata


class XlsxHandler(FormatHandler):
    """Excel (xlsx) file handler.
    
    Reads from column A.
    Writes to column A (translated) and optionally column B (original).
    
    Requires openpyxl package.
    """
    
    format_id = "xlsx"
    extensions = (".xlsx",)
    description = "Excel files (column A = text, column B = original)"
    supports_pairs = True
    
    def _check_openpyxl(self) -> bool:
        """Check if openpyxl is available."""
        try:
            import openpyxl  # type: ignore[import-untyped]  # noqa: F401
            return True
        except ImportError:
            return False
    
    def extract(self, path: Path, encoding: str = "utf-8") -> List[str]:
        """Extract text from column A of an Excel file.
        
        Args:
            path: Path to the Excel file.
            encoding: Ignored (xlsx uses internal encoding).
            
        Returns:
            List of text values from column A.
        """
        if not self._check_openpyxl():
            logging.error("openpyxl not installed. Install with: pip install openpyxl")
            return []
        
        import openpyxl
        
        wb = openpyxl.load_workbook(path)
        ws = wb.active
        if ws is None:
            return []
        
        lines = []
        for row in ws.iter_rows(values_only=True):
            cell_value = row[0] if row else None
            if cell_value is None:
                lines.append("")
            else:
                lines.append(str(cell_value))
        
        return lines
    
    def inject(
        self,
        path: Path,
        lines: List[str],
        original_lines: Optional[List[str]] = None,
        encoding: str = "utf-8"
    ) -> None:
        """Write text to an Excel file.
        
        Args:
            path: Path to write the file.
            lines: Translated lines for column A.
            original_lines: Optional original lines for column B.
            encoding: Ignored (xlsx uses internal encoding).
        """
        if not self._check_openpyxl():
            logging.error("openpyxl not installed. Install with: pip install openpyxl")
            return
        
        import openpyxl
        
        wb = openpyxl.Workbook()
        ws = wb.active
        if ws is None:
            ws = wb.create_sheet()
        
        for i, line in enumerate(lines):
            if original_lines and i < len(original_lines):
                ws.append([line, original_lines[i]])
            else:
                ws.append([line])
        
        wb.save(path)


def get_handlers() -> List[FormatHandler]:
    """Get all simple format handlers.
    
    Returns:
        List of FormatHandler instances.
    """
    return [
        TxtHandler(),
        CsvHandler(),
        TsvHandler(),
        JsonHandler(),
        XlsxHandler(),
    ]
