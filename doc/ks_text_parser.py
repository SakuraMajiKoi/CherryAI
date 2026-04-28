from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

ENCODING = "cp932"
KANJI_CLASS = r"\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF々〆ヵヶ"
HIRAGANA_CLASS = r"\u3041-\u3096\u309D-\u309F"
KATAKANA_CLASS = r"\u30A1-\u30FA\u30FD-\u30FF\u31F0-\u31FF\uFF66-\uFF9Fー"
JAPANESE_RE = re.compile(rf"[{KANJI_CLASS}{HIRAGANA_CLASS}{KATAKANA_CLASS}]")
COMMENT_RE = re.compile(r"^\s*;")
LABEL_RE = re.compile(r"^\s*\*")
AT_COMMAND_RE = re.compile(r"^\s*@")
TAG_RE = re.compile(r"^\s*\[[^\]]*\]\s*$")
BRACE_COMMAND_RE = re.compile(r"^\s*\{[^{}]*\}\s*$")
SPEAKER_RE = re.compile(r"^\s*【(?P<speaker>[^】]+)】(?:\[(?P<voice_id>[^\]]+)\])?\s*$")

SOFT_BRIDGE_KINDS = {"tag", "brace_command", "at_command"}
HARD_BREAK_KINDS = {"blank", "comment", "label"}


@dataclass(slots=True)
class ClassifiedLine:
    number: int
    text: str
    newline: str
    kind: str
    speaker: str | None = None
    voice_id: str | None = None


@dataclass(slots=True)
class TextBlock:
    block_id: str
    file: str
    block_kind: str
    start_line: int
    end_line: int
    speaker: str | None
    voice_id: str | None
    text_line_numbers: list[int] = field(default_factory=list)
    source_text_lines: list[str] = field(default_factory=list)
    bridge_code_lines: list[dict[str, object]] = field(default_factory=list)
    joined_text: str = ""


@dataclass(slots=True)
class PendingSpeaker:
    speaker: str
    voice_id: str | None
    bridge_code_lines: list[dict[str, object]] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract visible KS text blocks and preserve enough structure for later reinjection. "
            "Files are decoded as cp932 because the corpus is not UTF-8."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    extract_parser = subparsers.add_parser("extract", help="Extract visible text blocks.")
    add_common_extract_args(extract_parser)

    verify_parser = subparsers.add_parser("verify", help="Extract and run bleed checks.")
    add_common_extract_args(verify_parser)

    inject_parser = subparsers.add_parser("inject", help="Inject translated text back into KS files.")
    inject_parser.add_argument("translation_json", type=Path, help="JSON produced from extracted blocks.")
    inject_parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root directory containing the original KS files.",
    )

    parser.set_defaults(command="extract")
    return parser.parse_args()


def add_common_extract_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to parse. Defaults to the current directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON file for extracted text blocks.",
    )


def iter_ks_files(paths: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.ks")))
        elif path.suffix.lower() == ".ks":
            files.append(path)
    return sorted({path.resolve() for path in files})


def read_lines_preserve_newlines(path: Path) -> list[str]:
    with path.open("r", encoding=ENCODING, newline="") as handle:
        return handle.readlines()


def split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def classify_line(number: int, raw_line: str) -> ClassifiedLine:
    text, newline = split_line_ending(raw_line)
    stripped = text.strip()
    speaker_match = SPEAKER_RE.match(stripped)
    if not stripped:
        kind = "blank"
        return ClassifiedLine(number=number, text=text, newline=newline, kind=kind)
    if speaker_match:
        return ClassifiedLine(
            number=number,
            text=text,
            newline=newline,
            kind="speaker",
            speaker=speaker_match.group("speaker"),
            voice_id=speaker_match.group("voice_id"),
        )
    if COMMENT_RE.match(stripped):
        kind = "comment"
    elif LABEL_RE.match(stripped):
        kind = "label"
    elif AT_COMMAND_RE.match(stripped):
        kind = "at_command"
    elif TAG_RE.match(stripped):
        kind = "tag"
    elif BRACE_COMMAND_RE.match(stripped):
        kind = "brace_command"
    else:
        kind = "text"
    return ClassifiedLine(number=number, text=text, newline=newline, kind=kind)


def next_significant_kind(lines: list[ClassifiedLine], start_index: int) -> str | None:
    for index in range(start_index, len(lines)):
        kind = lines[index].kind
        if kind in {"comment"}:
            continue
        return kind
    return None


def should_keep_as_bridge(
    line: ClassifiedLine,
    lines: list[ClassifiedLine],
    index: int,
    has_open_block: bool,
    pending_speaker: PendingSpeaker | None,
) -> bool:
    if line.kind not in SOFT_BRIDGE_KINDS:
        return False
    if not has_open_block and pending_speaker is None:
        return False
    next_kind = next_significant_kind(lines, index + 1)
    return next_kind == "text"


def new_block(
    file_path: str,
    block_number: int,
    initial_line: ClassifiedLine,
    pending_speaker: PendingSpeaker | None,
) -> TextBlock:
    bridge_code_lines = list(pending_speaker.bridge_code_lines) if pending_speaker else []
    speaker = pending_speaker.speaker if pending_speaker else None
    voice_id = pending_speaker.voice_id if pending_speaker else None
    return TextBlock(
        block_id=f"{file_path}:{block_number:05d}",
        file=file_path,
        block_kind="dialogue" if speaker else "narration",
        start_line=initial_line.number,
        end_line=initial_line.number,
        speaker=speaker,
        voice_id=voice_id,
        bridge_code_lines=bridge_code_lines,
    )


def finalize_block(block: TextBlock | None) -> TextBlock | None:
    if block is None:
        return None
    block.joined_text = "\n".join(block.source_text_lines)
    return block


def extract_blocks_from_file(path: Path, root: Path) -> list[TextBlock]:
    raw_lines = read_lines_preserve_newlines(path)
    lines = [classify_line(index + 1, raw_line) for index, raw_line in enumerate(raw_lines)]
    file_path = path.relative_to(root).as_posix()

    blocks: list[TextBlock] = []
    current: TextBlock | None = None
    pending_speaker: PendingSpeaker | None = None
    block_number = 0

    for index, line in enumerate(lines):
        if line.kind == "speaker":
            finished = finalize_block(current)
            if finished is not None:
                blocks.append(finished)
            current = None
            pending_speaker = PendingSpeaker(speaker=line.speaker or "", voice_id=line.voice_id)
            continue

        if line.kind == "text":
            if current is None:
                block_number += 1
                current = new_block(file_path, block_number, line, pending_speaker)
                pending_speaker = None
            current.text_line_numbers.append(line.number)
            current.source_text_lines.append(line.text)
            current.end_line = line.number
            continue

        if should_keep_as_bridge(
            line=line,
            lines=lines,
            index=index,
            has_open_block=current is not None,
            pending_speaker=pending_speaker,
        ):
            bridge_entry = {"line_number": line.number, "text": line.text, "kind": line.kind}
            if current is not None:
                current.bridge_code_lines.append(bridge_entry)
            elif pending_speaker is not None:
                pending_speaker.bridge_code_lines.append(bridge_entry)
            continue

        if line.kind in HARD_BREAK_KINDS or line.kind in SOFT_BRIDGE_KINDS:
            finished = finalize_block(current)
            if finished is not None:
                blocks.append(finished)
            current = None
            if line.kind in HARD_BREAK_KINDS:
                pending_speaker = None
            continue

        finished = finalize_block(current)
        if finished is not None:
            blocks.append(finished)
        current = None

    finished = finalize_block(current)
    if finished is not None:
        blocks.append(finished)

    return [block for block in blocks if block.joined_text and JAPANESE_RE.search(block.joined_text)]


def extract_blocks(files: list[Path], root: Path) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for path in files:
        blocks.extend(extract_blocks_from_file(path, root))
    return blocks


def print_extract_summary(blocks: list[TextBlock]) -> None:
    dialogue = sum(1 for block in blocks if block.block_kind == "dialogue")
    narration = len(blocks) - dialogue
    bridged = sum(1 for block in blocks if block.bridge_code_lines)
    print(f"Extracted blocks: {len(blocks)}")
    print(f"Dialogue blocks: {dialogue}")
    print(f"Narration blocks: {narration}")
    print(f"Blocks with ignored bridge code: {bridged}")


def run_verification(blocks: list[TextBlock]) -> int:
    problems: list[str] = []
    for block in blocks:
        if not block.joined_text.strip():
            problems.append(f"Empty block: {block.block_id}")
        if TAG_RE.match(block.joined_text.strip()):
            problems.append(f"Code bled into joined text: {block.block_id}")
        if BRACE_COMMAND_RE.match(block.joined_text.strip()):
            problems.append(f"Brace command bled into joined text: {block.block_id}")
        if SPEAKER_RE.match(block.joined_text.strip()):
            problems.append(f"Speaker marker extracted as text body: {block.block_id}")

    if problems:
        print("Verification failed:")
        for problem in problems[:30]:
            print(f"  {problem}")
        if len(problems) > 30:
            print(f"  ... and {len(problems) - 30} more")
        return 1

    print("Verification passed: no command bleed detected in extracted text blocks.")
    return 0


def write_extract_output(blocks: list[TextBlock], output: Path) -> None:
    payload = {
        "encoding": ENCODING,
        "blocks": [asdict(block) for block in blocks],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote extracted blocks to {output.as_posix()}")


def load_translation_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_translated_lines(block: dict[str, object]) -> list[str] | None:
    translated_lines = block.get("translated_lines")
    if isinstance(translated_lines, list):
        return [str(item) for item in translated_lines]

    translated_text = block.get("translated_text")
    if isinstance(translated_text, str):
        return translated_text.split("\n")

    return None


def inject_translations(payload: dict[str, object], root: Path) -> int:
    raw_blocks = payload.get("blocks")
    if not isinstance(raw_blocks, list):
        print("Translation JSON does not contain a blocks list.")
        return 1

    blocks_by_file: dict[str, list[dict[str, object]]] = {}
    for block in raw_blocks:
        if not isinstance(block, dict):
            continue
        translated_lines = normalize_translated_lines(block)
        if translated_lines is None:
            continue
        file_path = block.get("file")
        if not isinstance(file_path, str):
            continue
        blocks_by_file.setdefault(file_path, []).append(block)

    for relative_path, file_blocks in blocks_by_file.items():
        path = root / relative_path
        raw_lines = read_lines_preserve_newlines(path)
        replacements: dict[int, str] = {}

        for block in file_blocks:
            translated_lines = normalize_translated_lines(block)
            text_line_numbers = block.get("text_line_numbers")
            if not isinstance(text_line_numbers, list) or translated_lines is None:
                continue
            if len(translated_lines) != len(text_line_numbers):
                raise ValueError(
                    f"Block {block.get('block_id')} has {len(text_line_numbers)} source lines but "
                    f"{len(translated_lines)} translated lines."
                )
            for line_number, translated_line in zip(text_line_numbers, translated_lines, strict=True):
                original_line = raw_lines[int(line_number) - 1]
                _, newline = split_line_ending(original_line)
                replacements[int(line_number)] = translated_line + newline

        for line_number, replacement in replacements.items():
            raw_lines[line_number - 1] = replacement

        path.write_text("".join(raw_lines), encoding=ENCODING, newline="")
        print(f"Injected translations into {relative_path}")

    return 0


def main() -> int:
    args = parse_args()

    if args.command == "inject":
        payload = load_translation_payload(args.translation_json)
        return inject_translations(payload, args.root.resolve())

    files = iter_ks_files(args.paths)
    if not files:
        print("No .ks files found.")
        return 1

    root = Path.cwd().resolve()
    blocks = extract_blocks(files, root)
    print_extract_summary(blocks)

    if args.output:
        write_extract_output(blocks, args.output)

    if args.command == "verify":
        return run_verification(blocks)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())