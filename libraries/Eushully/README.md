# Eushully Parser Notes

## Scope

This folder tracks practical references for Eushully AGE-era resources and parser patch targets.

Current parser target in CherryAI:
- Loose `.BIN` script resources in extracted game folders (for example Himegari Dungeon Meister).

## Online Tools And Source References

Primary open-source references (with source code):
- GARbro repository:
  - https://github.com/morkt/GARbro
- GARbro Eushully ALF archive reader:
  - https://raw.githubusercontent.com/morkt/GARbro/master/ArcFormats/Eushully/ArcALF.cs
- GARbro Eushully legacy archives (GPC/SNR index logic):
  - https://raw.githubusercontent.com/morkt/GARbro/master/ArcFormats/Eushully/ArcGPC.cs
- GARbro Eushully AGF image decoder:
  - https://raw.githubusercontent.com/morkt/GARbro/master/ArcFormats/Eushully/ImageAGF.cs
- GARbro Eushully AOG audio wrapper:
  - https://raw.githubusercontent.com/morkt/GARbro/master/ArcFormats/Eushully/AudioAOG.cs
- arc_unpacker (archived, decoder-focused extraction tool):
  - https://github.com/vn-tools/arc_unpacker

Observed useful Eushully format hints from those sources:
- `ALF`: main resource archive with index loaded from `sys4ini.bin` / `sys3ini.bin` / `.AAI`.
- `SNR`: old script archive family identified in GARbro as `Eushully script archive`.
- `AGF`: image format (`ACGF`/`AGF`) with optional alpha substream (`ACIF`).
- `AOG/SYS3`: OGG-backed audio payload wrapper.

## Wordwrap, Font, Spacing Patch Checklist

Future parser-owned or parser-adjacent patch points to verify per title:
- Wordwrap:
  - Runtime line-break token for message windows.
  - Per-UI-surface width limits (main dialogue, choices, backlog, status/help windows).
  - Overflow behavior (truncate, new page, scroll, split boxes).
- Font:
  - Font file lookup path and fallback order.
  - Default face and size by surface (dialogue/UI labels/system menus).
  - Full-width/half-width rendering consistency.
- Spacing:
  - CJK + Latin mixed spacing behavior.
  - Punctuation hanging rules and quote handling.
  - Baseline alignment and fixed-pitch assumptions in menu grids.

## Text String Coverage Plan

The parser should preserve every discoverable translatable payload class, even when a specific sample game does not expose all of them:
- Dialogue and narration payloads.
- Choice/menu labels.
- System UI labels.
- Battle/tutorial/help strings.
- Item/skill/location names and descriptions.
- Save/load labels and metadata text.
- Event condition and confirmation prompts.
- Map/object captions.
- Any encoded literal string tables embedded in script bytecode.

Current implementation strategy for `.BIN`:
- Shift-JIS printable-run extraction from bytecode for broad string-table coverage.
- Fixed-length in-place reinjection to keep binary layout stable for pack/roundtrip checks.

## Testing Targets

- Extraction volume on `dev/Himegari Dungeon Meister`: exceed 10,000 extracted lines.
- Injection/pack safety: identity reinjection over all `.BIN` files should succeed with zero mismatches.
- Manual verification remains required for:
  - Runtime translation quality.
  - Crash-free progression across game flow.
