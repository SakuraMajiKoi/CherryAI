"""Shared staging helpers for the KiriKiri Step 9 font patch workflow."""

from __future__ import annotations

import codecs
import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, TYPE_CHECKING


if TYPE_CHECKING:
    import tkinter as tk

    from CherryAI.functions.apply_patches import DiscoveredParserPatch, PatchApplicationResult
    from CherryAI.functions.manifest_manager import ManifestManager


logger = logging.getLogger(__name__)


DEFAULT_PATCH_DIR_NAME = "patch"
DEFAULT_FONTS_DIR_NAME = "fonts"
DEFAULT_CONFIG_NAME = "CherryAI.KiriKiriPatch.json"
LEGACY_CONFIG_NAMES: tuple[str, ...] = ("CherryAI.KiriKiriFontPatch.json",)
DEFAULT_DLL_NAME = "version.dll"
DEFAULT_LOG_FILE_NAME = "kirikiri-patched.log"
DEFAULT_LOG_INI_NAME = "kirikiri-patched.ini"
DEFAULT_RUNTIME_CONFIG_NAME = "CherryAI.KiriKiriFontPatch.runtime.tjs"
DEFAULT_WRAP_RIGHT_PADDING_PIXELS = 220
DEFAULT_WRAP_MODE = "pixel"
WRAP_MODES: tuple[str, ...] = ("pixel", "character")
DEFAULT_SYSTEM_PATCH_TEMPLATE_DIR_NAME = "SystemPatchTemplates"
DEFAULT_STANDARD_UI_TRANSLATION_DIR_NAME = "StandardUiTranslations"
DEFAULT_STANDARD_UI_TRANSLATION_SPEC_NAME = "CherryAI.KiriKiriStandardUiPatch.json"
SYSTEM_PATCH_TEMPLATE_SOURCE_ENCODINGS: tuple[str, ...] = (
    "utf-8-sig",
    "utf-8",
    "cp932",
    "shift_jis",
)
SYSTEM_PATCH_TEMPLATE_OUTPUT_ENCODING = "cp932"
SYSTEM_PATCH_TEMPLATE_NAMES: tuple[str, ...] = (
    "AffineLayer.tjs",
    "ButtonLayer.tjs",
    "MessageLayer.tjs",
)
ANSI_CHARSET = 0
SHIFTJIS_CHARSET = 128
DEFAULT_MATCH_FACES: tuple[str, ...] = (
    "MS UI Gothic",
    "MS PGothic",
    "ＭＳ Ｐゴシック",
    "MS Gothic",
    "ＭＳ ゴシック",
    "Meiryo",
    "メイリオ",
    "Segoe UI",
    "Segoe UI Variable",
    "Yu Gothic",
    "Yu Gothic UI",
    "YuGothic",
    "TakaoGothic",
    "Arial",
)
CJK_MATCH_FACES: tuple[str, ...] = (
    "MS UI Gothic",
    "MS PGothic",
    "ＭＳ Ｐゴシック",
    "MS Gothic",
    "ＭＳ ゴシック",
    "Meiryo",
    "メイリオ",
    "Yu Gothic",
    "Yu Gothic UI",
    "YuGothic",
    "TakaoGothic",
)


def get_font_patch_resource_root(project_root: Path) -> Path:
    libraries_root = project_root / "libraries"
    if libraries_root.is_dir():
        return project_root
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class FontBundleSpec:
    bundle_id: str
    display_name: str
    face_name: str
    regular_file: str
    bold_file: Optional[str]
    license_file: str
    supports_cjk: bool = False
    default_replace_cjk_faces: bool = False
    default_charset: int = 1
    default_width_percent: int = 100
    default_match_faces: tuple[str, ...] = DEFAULT_MATCH_FACES
    default_latin_bundle_id: Optional[str] = None


@dataclass(frozen=True)
class FontPatchSelection:
    bundle_id: str
    regular_file: str
    bold_file: Optional[str] = None
    match_faces: tuple[str, ...] = DEFAULT_MATCH_FACES
    replace_cjk_faces: bool = False
    charset: int = 1
    quality: int = 5
    height_percent: int = 100
    height_offset_pixels: int = 0
    width_percent: int = 100
    log_font_calls: bool = True


@dataclass(frozen=True)
class FontPatchPaths:
    project_root: Path
    libraries_root: Path
    injection_root: Path
    fonts_library_root: Path
    translated_root: Path
    patch_dir: Path
    fonts_dir: Path
    config_path: Path
    runtime_config_path: Path
    dll_output_path: Path
    log_ini_path: Path
    log_path: Path


@dataclass(frozen=True)
class FontPatchStagingResult:
    paths: FontPatchPaths
    copied_font_paths: tuple[Path, ...]
    copied_system_patch_paths: tuple[Path, ...]
    copied_license_path: Path
    copied_dll: bool


@dataclass(frozen=True)
class KiriKiriUiTranslationStagingResult:
    """Outcome of staging the standard KiriKiri UI translation overlay."""

    spec_path: Path
    staged_paths: tuple[Path, ...]
    skipped_paths: tuple[Path, ...]
    missing_paths: tuple[Path, ...]


FONT_BUNDLE_SPECS: tuple[FontBundleSpec, ...] = (
    FontBundleSpec(
        bundle_id="inter",
        display_name="Inter",
        face_name="Inter",
        regular_file="Inter-Regular.ttf",
        bold_file="Inter-SemiBold.ttf",
        license_file="LICENSE.txt",
    ),
    FontBundleSpec(
        bundle_id="noto_sans",
        display_name="Noto Sans",
        face_name="Noto Sans",
        regular_file="NotoSans-Regular.ttf",
        bold_file="NotoSans-SemiBold.ttf",
        license_file="LICENSE.txt",
    ),
    FontBundleSpec(
        bundle_id="liberation_sans",
        display_name="Liberation Sans",
        face_name="Liberation Sans",
        regular_file="LiberationSans-Regular.ttf",
        bold_file="LiberationSans-Bold.ttf",
        license_file="LICENSE.txt",
    ),
    FontBundleSpec(
        bundle_id="open_sans",
        display_name="Open Sans",
        face_name="Open Sans",
        regular_file="OpenSans-Regular.ttf",
        bold_file="OpenSans-SemiBold.ttf",
        license_file="OFL.txt",
    ),
    FontBundleSpec(
        bundle_id="noto_sans_jp",
        display_name="Noto Sans JP",
        face_name="Noto Sans CJK JP",
        regular_file="NotoSansCJKjp-Regular.otf",
        bold_file="NotoSansCJKjp-Medium.otf",
        license_file="LICENSE.txt",
        supports_cjk=True,
        default_replace_cjk_faces=True,
        default_charset=SHIFTJIS_CHARSET,
        default_width_percent=90,
        default_match_faces=CJK_MATCH_FACES,
        default_latin_bundle_id="inter",
    ),
)


def get_font_bundle_spec(bundle_id: str) -> FontBundleSpec:
    normalized = bundle_id.strip().lower()
    for spec in FONT_BUNDLE_SPECS:
        if spec.bundle_id == normalized:
            return spec
    raise KeyError(f"Unknown font bundle: {bundle_id}")


def get_font_patch_paths(
    project_root: Path,
    translated_root: Path,
    *,
    patch_dir_name: str = DEFAULT_PATCH_DIR_NAME,
    fonts_dir_name: str = DEFAULT_FONTS_DIR_NAME,
    config_name: str = DEFAULT_CONFIG_NAME,
    dll_name: str = DEFAULT_DLL_NAME,
) -> FontPatchPaths:
    libraries_root = project_root / "libraries"
    injection_root = libraries_root / "KiriKiriInjection"
    fonts_library_root = libraries_root / "Fonts"
    patch_dir = translated_root / patch_dir_name
    fonts_dir = translated_root / fonts_dir_name
    return FontPatchPaths(
        project_root=project_root,
        libraries_root=libraries_root,
        injection_root=injection_root,
        fonts_library_root=fonts_library_root,
        translated_root=translated_root,
        patch_dir=patch_dir,
        fonts_dir=fonts_dir,
        config_path=patch_dir / config_name,
        runtime_config_path=patch_dir / DEFAULT_RUNTIME_CONFIG_NAME,
        dll_output_path=translated_root / dll_name,
        log_ini_path=translated_root / DEFAULT_LOG_INI_NAME,
        log_path=translated_root / DEFAULT_LOG_FILE_NAME,
    )


def list_available_font_bundles(fonts_library_root: Path) -> list[FontBundleSpec]:
    available: list[FontBundleSpec] = []
    for spec in FONT_BUNDLE_SPECS:
        bundle_root = fonts_library_root / spec.display_name
        if not bundle_root.is_dir():
            continue
        required = [bundle_root / spec.regular_file, bundle_root / spec.license_file]
        if spec.bold_file:
            required.append(bundle_root / spec.bold_file)
        if all(path.is_file() for path in required):
            available.append(spec)
    return available


def load_existing_font_patch_selection(config_path: Path) -> Optional[FontPatchSelection]:
    if not config_path.is_file():
        return None
    data = json.loads(config_path.read_text(encoding="utf-8"))
    try:
        bundle_id = str(data["bundle_id"])
        regular_file = Path(str(data["regular_font"]["file"])).name
    except (KeyError, TypeError, ValueError):
        return None
    bold_file = None
    bold_font = data.get("bold_font")
    if isinstance(bold_font, dict):
        raw_bold_file = Path(str(bold_font.get("file", "")).strip()).name
        bold_file = raw_bold_file or None
    raw_faces = data.get("match_faces")
    match_faces = tuple(str(item).strip() for item in raw_faces if str(item).strip()) if isinstance(raw_faces, list) else DEFAULT_MATCH_FACES
    return FontPatchSelection(
        bundle_id=bundle_id,
        regular_file=regular_file,
        bold_file=bold_file,
        match_faces=match_faces,
        replace_cjk_faces=bool(data.get("replace_cjk_faces", False)),
        charset=int(data.get("charset", 1)),
        quality=int(data.get("quality", 5)),
        height_percent=int(data.get("height_percent", 100)),
        height_offset_pixels=int(data.get("height_offset_pixels", 0)),
        width_percent=int(data.get("width_percent", 100)),
        log_font_calls=bool(data.get("log_font_calls", True)),
    )


def build_font_patch_config(
    spec: FontBundleSpec,
    selection: FontPatchSelection,
    *,
    latin_spec: Optional[FontBundleSpec] = None,
) -> dict:
    regular_relative = f"{DEFAULT_FONTS_DIR_NAME}/{selection.regular_file}"
    config = {
        "schema": 1,
        "bundle_id": spec.bundle_id,
        "bundle_name": spec.display_name,
        "default_face": spec.face_name,
        "fonts_directory": DEFAULT_FONTS_DIR_NAME,
        "log_font_calls": selection.log_font_calls,
        "replace_cjk_faces": selection.replace_cjk_faces,
        "charset": selection.charset,
        "quality": selection.quality,
        "height_percent": selection.height_percent,
        "height_offset_pixels": selection.height_offset_pixels,
        "width_percent": selection.width_percent,
        "match_faces": list(selection.match_faces),
        "regular_font": {
            "face": spec.face_name,
            "file": regular_relative,
        },
    }
    if selection.bold_file:
        config["bold_font"] = {
            "face": spec.face_name,
            "file": f"{DEFAULT_FONTS_DIR_NAME}/{selection.bold_file}",
        }
    if latin_spec is not None:
        config["latin_bundle_id"] = latin_spec.bundle_id
        config["latin_bundle_name"] = latin_spec.display_name
        config["latin_face"] = latin_spec.face_name
        config["latin_charset"] = ANSI_CHARSET
        config["latin_regular_font"] = {
            "face": latin_spec.face_name,
            "file": f"{DEFAULT_FONTS_DIR_NAME}/{latin_spec.regular_file}",
        }
        if latin_spec.bold_file:
            config["latin_bold_font"] = {
                "face": latin_spec.face_name,
                "file": f"{DEFAULT_FONTS_DIR_NAME}/{latin_spec.bold_file}",
            }
    return config


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _bundle_is_available(fonts_library_root: Path, spec: FontBundleSpec) -> bool:
    bundle_root = fonts_library_root / spec.display_name
    required = [bundle_root / spec.regular_file, bundle_root / spec.license_file]
    if spec.bold_file:
        required.append(bundle_root / spec.bold_file)
    return all(path.is_file() for path in required)


def _get_default_latin_bundle(
    fonts_library_root: Path,
    spec: FontBundleSpec,
) -> Optional[FontBundleSpec]:
    if spec.default_latin_bundle_id is None:
        return None
    latin_spec = get_font_bundle_spec(spec.default_latin_bundle_id)
    if not _bundle_is_available(fonts_library_root, latin_spec):
        return None
    return latin_spec


def _copy_bundle_assets(
    bundle_root: Path,
    fonts_dir: Path,
    *,
    regular_file: str,
    bold_file: Optional[str],
) -> list[Path]:
    copied_paths: list[Path] = []

    regular_source = bundle_root / regular_file
    if not regular_source.is_file():
        raise FileNotFoundError(f"Missing bundled font file: {regular_source}")
    regular_target = fonts_dir / regular_file
    _copy_file(regular_source, regular_target)
    copied_paths.append(regular_target)

    if bold_file:
        bold_source = bundle_root / bold_file
        if not bold_source.is_file():
            raise FileNotFoundError(f"Missing bundled font file: {bold_source}")
        bold_target = fonts_dir / bold_file
        _copy_file(bold_source, bold_target)
        copied_paths.append(bold_target)

    return copied_paths


def _resolve_source_version_dll(injection_root: Path) -> Optional[Path]:
    candidates = (
        injection_root / "KirikiriUnencryptedArchive" / "Release" / "version.dll",
        injection_root / "KirikiriUnencryptedArchive" / "Kirikiri.68FD9BD1" / "Release" / "version.dll",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _resolve_system_patch_template_dir(injection_root: Path) -> Path:
    return injection_root / DEFAULT_SYSTEM_PATCH_TEMPLATE_DIR_NAME


def _read_system_patch_template_text(source: Path) -> str:
    last_error: Optional[UnicodeDecodeError] = None
    for encoding in SYSTEM_PATCH_TEMPLATE_SOURCE_ENCODINGS:
        try:
            return source.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return source.read_text()


def _copy_system_patch_templates(template_dir: Path, patch_dir: Path) -> list[Path]:
    return _copy_system_patch_templates_with_overrides(
        template_dir,
        patch_dir,
        message_layer_overrides=None,
        template_names=SYSTEM_PATCH_TEMPLATE_NAMES,
    )


def _coerce_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _escape_tjs_string(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', r'\"')


def _load_existing_font_patch_config(config_path: Path) -> dict[str, object]:
    paths_to_try = [config_path]
    if config_path.name == DEFAULT_CONFIG_NAME:
        for legacy_name in LEGACY_CONFIG_NAMES:
            paths_to_try.append(config_path.with_name(legacy_name))

    for candidate in paths_to_try:
        if not candidate.is_file():
            continue
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(raw, dict):
            return raw
    return {}


def _normalize_wrap_mode(value: object, fallback: str = DEFAULT_WRAP_MODE) -> str:
    candidate = str(value).strip().lower()
    if candidate in WRAP_MODES:
        return candidate
    return fallback


def _resolve_wrap_mode(
    config: dict[str, object],
    existing_config: Optional[dict[str, object]] = None,
) -> str:
    for key in ("WrapMode", "wrap_mode"):
        if key in config:
            return _normalize_wrap_mode(config[key])
    if existing_config:
        for key in ("WrapMode", "wrap_mode"):
            if key in existing_config:
                return _normalize_wrap_mode(existing_config[key])
    return DEFAULT_WRAP_MODE


def _write_legacy_config_mirrors(config_path: Path, config: dict[str, object]) -> None:
    if config_path.name != DEFAULT_CONFIG_NAME:
        return
    payload = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    for legacy_name in LEGACY_CONFIG_NAMES:
        config_path.with_name(legacy_name).write_text(payload, encoding="utf-8")


def _resolve_wrap_right_padding_pixels(
    config: dict[str, object],
    existing_config: Optional[dict[str, object]] = None,
) -> int:
    candidates: list[object] = []
    for key in ("WrapRightPaddingPixels", "wrap_right_padding_pixels"):
        if key in config:
            candidates.append(config[key])
    if existing_config:
        for key in ("WrapRightPaddingPixels", "wrap_right_padding_pixels"):
            if key in existing_config:
                candidates.append(existing_config[key])
    for candidate in candidates:
        value = _coerce_int(candidate, DEFAULT_WRAP_RIGHT_PADDING_PIXELS)
        if value >= 0:
            return value
    return DEFAULT_WRAP_RIGHT_PADDING_PIXELS


def _build_message_layer_overrides(config: dict[str, object]) -> dict[str, object]:
    latin_face = str(config.get("latin_face", "")).strip()
    if not latin_face:
        latin_face = str(config.get("default_face", "Inter")).strip() or "Inter"
    return {
        "line_spacing_offset_pixels": _coerce_int(config.get("height_offset_pixels", 0), 0),
        "latin_face": latin_face,
        "wrap_right_padding_pixels": _resolve_wrap_right_padding_pixels(config),
        "wrap_mode": _resolve_wrap_mode(config),
    }


def _apply_message_layer_overrides(text: str, overrides: dict[str, object]) -> str:
    patched = text

    line_spacing = _coerce_int(overrides.get("line_spacing_offset_pixels", 0), 0)
    patched = re.sub(
        r"var\s+__CherryAILineSpacingOffsetPixels\s*=\s*-?\d+;",
        f"var __CherryAILineSpacingOffsetPixels = {line_spacing};",
        patched,
    )

    latin_face = _escape_tjs_string(overrides.get("latin_face", "Inter"))
    patched = re.sub(
        r'var\s+__CherryAILatinFace\s*=\s*"[^"]*";',
        f'var __CherryAILatinFace = "{latin_face}";',
        patched,
    )

    wrap_padding = _coerce_int(
        overrides.get("wrap_right_padding_pixels", DEFAULT_WRAP_RIGHT_PADDING_PIXELS),
        DEFAULT_WRAP_RIGHT_PADDING_PIXELS,
    )
    patched = re.sub(
        r"var\s+__CherryAIWrapRightPaddingPixels\s*=\s*-?\d+;",
        f"var __CherryAIWrapRightPaddingPixels = {wrap_padding};",
        patched,
    )

    wrap_mode = _normalize_wrap_mode(overrides.get("wrap_mode", DEFAULT_WRAP_MODE))
    patched = re.sub(
        r'var\s+__CherryAIWrapMode\s*=\s*"[^"]*";',
        f'var __CherryAIWrapMode = "{wrap_mode}";',
        patched,
    )

    return patched


def _copy_system_patch_templates_with_overrides(
    template_dir: Path,
    patch_dir: Path,
    *,
    message_layer_overrides: Optional[dict[str, object]],
    template_names: Sequence[str],
) -> list[Path]:
    copied_paths: list[Path] = []
    system_patch_dir = patch_dir / "data" / "system"
    for template_name in template_names:
        source = template_dir / template_name
        if not source.is_file():
            raise FileNotFoundError(f"Missing system patch template: {source}")
        target = system_patch_dir / template_name
        target.parent.mkdir(parents=True, exist_ok=True)
        output_text = _read_system_patch_template_text(source)
        if (
            template_name == "MessageLayer.tjs"
            and message_layer_overrides is not None
        ):
            output_text = _apply_message_layer_overrides(output_text, message_layer_overrides)
        target.write_text(output_text, encoding=SYSTEM_PATCH_TEMPLATE_OUTPUT_ENCODING, newline="")
        copied_paths.append(target)
    return copied_paths


def _build_logging_ini_text() -> str:
    return "".join(
        (
            "[logging]\n",
            f"enabled = false\n",
            f"file = {DEFAULT_LOG_FILE_NAME}\n",
        )
    )


_RUNTIME_CONFIG_ENTRY_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*,?\s*$")


def _parse_runtime_scalar(raw_value: str) -> Optional[object]:
    value = raw_value.strip()
    if not value:
        return None

    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        inner = value[1:-1]
        inner = inner.replace(r"\\", "\\").replace(r'\"', '"')
        return inner

    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    if re.fullmatch(r"-?\d+", value):
        return int(value)

    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)

    return None


def _load_existing_runtime_config(runtime_config_path: Path) -> dict[str, object]:
    if not runtime_config_path.is_file():
        return {}

    text = runtime_config_path.read_text(encoding="utf-8", errors="ignore")
    parsed: dict[str, object] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped in {"%[", "]"}:
            continue
        if stripped.startswith("//") or stripped.startswith("#"):
            continue

        match = _RUNTIME_CONFIG_ENTRY_PATTERN.match(line)
        if match is None:
            continue

        key = match.group(1)
        value = _parse_runtime_scalar(match.group(2))
        if value is not None:
            parsed[key] = value

    return parsed


def _serialize_runtime_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', r'\"')
    return f'"{escaped}"'


def _build_runtime_config_text(
    config: dict,
    *,
    existing_runtime_config: Optional[dict[str, object]] = None,
) -> str:
    runtime_config: dict[str, object] = {}
    if existing_runtime_config:
        runtime_config.update(existing_runtime_config)

    lines = ["%[\n"]
    line_spacing_offset = int(config.get("height_offset_pixels", 0))
    runtime_config["line_spacing_offset_pixels"] = line_spacing_offset

    latin_face = str(config.get("latin_face", "")).strip()
    if latin_face:
        runtime_config["latin_face"] = latin_face

    ordered_keys: list[str] = []
    for key in (
        "line_spacing_offset_pixels",
        "latin_face",
        "wrap_right_padding_pixels",
    ):
        if key in runtime_config:
            ordered_keys.append(key)

    for key in sorted(runtime_config.keys()):
        if key not in ordered_keys:
            ordered_keys.append(key)

    for key in ordered_keys:
        value = runtime_config[key]
        if key == "latin_face" and not str(value).strip():
            continue
        lines.append(f"\t{key}: {_serialize_runtime_scalar(value)},\n")

    lines.append("]\n")
    return "".join(lines)


def stage_font_patch_assets(
    project_root: Path,
    translated_root: Path,
    selection: FontPatchSelection,
    *,
    patch_dir_name: str = DEFAULT_PATCH_DIR_NAME,
    fonts_dir_name: str = DEFAULT_FONTS_DIR_NAME,
    config_name: str = DEFAULT_CONFIG_NAME,
    dll_name: str = DEFAULT_DLL_NAME,
) -> FontPatchStagingResult:
    paths = get_font_patch_paths(
        project_root,
        translated_root,
        patch_dir_name=patch_dir_name,
        fonts_dir_name=fonts_dir_name,
        config_name=config_name,
        dll_name=dll_name,
    )
    spec = get_font_bundle_spec(selection.bundle_id)
    bundle_root = paths.fonts_library_root / spec.display_name
    latin_spec = _get_default_latin_bundle(paths.fonts_library_root, spec)

    copied_font_paths = _copy_bundle_assets(
        bundle_root,
        paths.fonts_dir,
        regular_file=selection.regular_file,
        bold_file=selection.bold_file,
    )
    if latin_spec is not None:
        copied_font_paths.extend(
            _copy_bundle_assets(
                paths.fonts_library_root / latin_spec.display_name,
                paths.fonts_dir,
                regular_file=latin_spec.regular_file,
                bold_file=latin_spec.bold_file,
            )
        )

    license_source = bundle_root / spec.license_file
    if not license_source.is_file():
        raise FileNotFoundError(f"Missing bundled font license: {license_source}")
    copied_license_path = paths.fonts_dir / spec.license_file
    _copy_file(license_source, copied_license_path)
    if latin_spec is not None:
        latin_license_source = paths.fonts_library_root / latin_spec.display_name / latin_spec.license_file
        if latin_license_source.is_file():
            _copy_file(
                latin_license_source,
                paths.fonts_dir / f"{latin_spec.display_name}-{latin_spec.license_file}",
            )

    paths.patch_dir.mkdir(parents=True, exist_ok=True)

    existing_config = _load_existing_font_patch_config(paths.config_path)
    config = build_font_patch_config(spec, selection, latin_spec=latin_spec)
    config["WrapRightPaddingPixels"] = _resolve_wrap_right_padding_pixels(
        config,
        existing_config=existing_config,
    )
    config["WrapMode"] = _resolve_wrap_mode({}, existing_config=existing_config)

    copied_system_patch_paths = _copy_system_patch_templates_with_overrides(
        _resolve_system_patch_template_dir(paths.injection_root),
        paths.patch_dir,
        message_layer_overrides=_build_message_layer_overrides(config),
        template_names=SYSTEM_PATCH_TEMPLATE_NAMES,
    )

    paths.config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_legacy_config_mirrors(paths.config_path, config)
    if paths.runtime_config_path.exists():
        paths.runtime_config_path.unlink()

    if not paths.log_ini_path.exists():
        paths.log_ini_path.write_text(_build_logging_ini_text(), encoding="utf-8")

    dll_source = _resolve_source_version_dll(paths.injection_root)
    copied_dll = False
    if dll_source is not None:
        _copy_file(dll_source, paths.dll_output_path)
        copied_dll = True

    return FontPatchStagingResult(
        paths=paths,
        copied_font_paths=tuple(copied_font_paths),
        copied_system_patch_paths=tuple(copied_system_patch_paths),
        copied_license_path=copied_license_path,
        copied_dll=copied_dll,
    )


def stage_kirikiri_message_layer_template(
    project_root: Path,
    translated_root: Path,
    *,
    patch_dir_name: str = DEFAULT_PATCH_DIR_NAME,
    config_name: str = DEFAULT_CONFIG_NAME,
) -> Path:
    """Stage MessageLayer.tjs using the current JSON config values."""
    paths = get_font_patch_paths(
        project_root,
        translated_root,
        patch_dir_name=patch_dir_name,
        config_name=config_name,
    )
    existing_config = _load_existing_font_patch_config(paths.config_path)
    config = dict(existing_config)
    if "WrapRightPaddingPixels" not in config:
        config["WrapRightPaddingPixels"] = _resolve_wrap_right_padding_pixels(config)
    config["WrapMode"] = _resolve_wrap_mode(config)

    copied = _copy_system_patch_templates_with_overrides(
        _resolve_system_patch_template_dir(paths.injection_root),
        paths.patch_dir,
        message_layer_overrides=_build_message_layer_overrides(config),
        template_names=("MessageLayer.tjs",),
    )
    if not copied:
        raise FileNotFoundError("MessageLayer.tjs template staging returned no output")
    return copied[0]


def get_default_font_selection(fonts_library_root: Path) -> Optional[FontPatchSelection]:
    available = list_available_font_bundles(fonts_library_root)
    if not available:
        return None
    spec = available[0]
    return FontPatchSelection(
        bundle_id=spec.bundle_id,
        regular_file=spec.regular_file,
        bold_file=spec.bold_file,
        match_faces=spec.default_match_faces,
        replace_cjk_faces=spec.default_replace_cjk_faces,
        charset=spec.default_charset,
        height_offset_pixels=0,
        width_percent=spec.default_width_percent,
    )


def get_build_script_path(project_root: Path) -> Path:
    return project_root / "libraries" / "KiriKiriInjection" / "build_version_dll.py"


def describe_copied_fonts(font_paths: Sequence[Path]) -> str:
    names = [path.name for path in font_paths]
    return ", ".join(names)


def _get_standard_ui_translation_spec_path(project_root: Path) -> Path:
    resource_root = get_font_patch_resource_root(project_root)
    return (
        resource_root
        / "libraries"
        / "KiriKiriInjection"
        / DEFAULT_STANDARD_UI_TRANSLATION_DIR_NAME
        / DEFAULT_STANDARD_UI_TRANSLATION_SPEC_NAME
    )


def _read_text_with_bom(path: Path) -> tuple[str, str, bytes]:
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF16_LE):
        return (
            data[len(codecs.BOM_UTF16_LE):].decode("utf-16-le"),
            "utf-16-le",
            codecs.BOM_UTF16_LE,
        )
    if data.startswith(codecs.BOM_UTF16_BE):
        return (
            data[len(codecs.BOM_UTF16_BE):].decode("utf-16-be"),
            "utf-16-be",
            codecs.BOM_UTF16_BE,
        )
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8"), "utf-8", codecs.BOM_UTF8
    for encoding in ("cp932", "utf-8", "utf-16-le", "utf-16-be"):
        try:
            return data.decode(encoding), encoding, b""
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8", b""


def _write_text_with_bom(path: Path, text: str, encoding: str, bom: bytes) -> None:
    payload = text.encode(encoding)
    if bom:
        payload = bom + payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _find_relative_file_in_root(root: Path, relative_path: Path) -> Optional[Path]:
    exact = root / relative_path
    if exact.is_file():
        return exact
    if not root.is_dir():
        return None
    try:
        matches = sorted(
            root.rglob(relative_path.name),
            key=lambda path: (len(path.parts), path.as_posix().lower()),
        )
    except OSError:
        return None

    parts = relative_path.parts
    for match in matches:
        if match.is_file() and len(match.parts) >= len(parts):
            if match.parts[-len(parts):] == parts:
                return match
    for match in matches:
        if match.is_file():
            return match
    return None


def _resolve_ui_source_path(relative_path: Path, source_roots: Sequence[Path]) -> Optional[Path]:
    for root in source_roots:
        source_path = _find_relative_file_in_root(root, relative_path)
        if source_path is not None:
            return source_path
    return None


def _apply_ui_translation_replacements(
    text: str,
    replacements: Sequence[dict],
) -> tuple[str, int]:
    patched = text
    total_replacements = 0
    for entry in replacements:
        replacement_text = str(entry.get("replace", ""))
        if bool(entry.get("regex", False)):
            pattern = str(entry.get("find", ""))
            patched, count = re.subn(pattern, replacement_text, patched)
        else:
            search_text = str(entry.get("find", ""))
            if not search_text:
                continue
            count = patched.count(search_text)
            if count:
                patched = patched.replace(search_text, replacement_text)
        total_replacements += count
    return patched, total_replacements


def stage_kirikiri_standard_ui_translation_patch(
    project_root: Path,
    translated_root: Path,
    *,
    source_roots: Sequence[Path],
    spec_path: Optional[Path] = None,
    patch_dir_name: str = DEFAULT_PATCH_DIR_NAME,
) -> KiriKiriUiTranslationStagingResult:
    """Stage translated KiriKiri standard UI files under the patch overlay tree."""

    resolved_spec_path = spec_path or _get_standard_ui_translation_spec_path(project_root)
    spec_data = json.loads(resolved_spec_path.read_text(encoding="utf-8"))
    patch_root = translated_root / patch_dir_name

    staged_paths: list[Path] = []
    skipped_paths: list[Path] = []
    missing_paths: list[Path] = []

    for raw_file in spec_data.get("files", []):
        relative_path = Path(str(raw_file["relative_path"]))
        source_path = _resolve_ui_source_path(relative_path, source_roots)
        if source_path is None:
            missing_paths.append(relative_path)
            continue

        text, encoding, bom = _read_text_with_bom(source_path)
        patched, replacement_count = _apply_ui_translation_replacements(
            text,
            raw_file.get("replacements", []),
        )
        if replacement_count == 0 or patched == text:
            skipped_paths.append(relative_path)
            continue

        target_path = patch_root / relative_path
        _write_text_with_bom(target_path, patched, encoding, bom)
        staged_paths.append(target_path)

    return KiriKiriUiTranslationStagingResult(
        spec_path=resolved_spec_path,
        staged_paths=tuple(staged_paths),
        skipped_paths=tuple(skipped_paths),
        missing_paths=tuple(missing_paths),
    )


def _prompt_standard_ui_lookup_dir(
    mgr: "ManifestManager",
    patch_info: "DiscoveredParserPatch",
    parent: Optional["tk.Misc"],
) -> Optional[Path]:
    if parent is None:
        return None

    from tkinter import filedialog

    from CherryAI.functions.apply_patches import (
        get_saved_patch_lookup_dir,
        set_saved_patch_lookup_dir,
    )

    saved_lookup = get_saved_patch_lookup_dir(mgr, patch_info.storage_key)
    if saved_lookup is not None and saved_lookup.is_dir():
        initialdir = str(saved_lookup)
    else:
        initialdir = str(mgr.get_project_dir())

    selected = filedialog.askdirectory(
        parent=parent,
        title=f"Select Folder For {patch_info.patch.name}",
        initialdir=initialdir,
        mustexist=True,
    )
    if not selected:
        return None

    folder = Path(selected)
    set_saved_patch_lookup_dir(mgr, patch_info.storage_key, folder)
    return folder


def run_kirikiri_standard_ui_translation_patch_workflow(
    mgr: "ManifestManager",
    patch_info: "DiscoveredParserPatch",
    parent: Optional["tk.Misc"],
    log,
) -> "PatchApplicationResult":
    """Stage the standard KiriKiri menu and utility UI translation overlay."""

    from CherryAI.functions.apply_patches import PatchApplicationResult, get_saved_patch_lookup_dir

    project_root = mgr.get_project_dir()
    translated_root = mgr.get_translated_dir()
    source_roots = [translated_root, mgr.get_original_dir()]

    saved_lookup = get_saved_patch_lookup_dir(mgr, patch_info.storage_key)
    if saved_lookup is not None and saved_lookup.is_dir():
        source_roots.append(saved_lookup)

    try:
        staged = stage_kirikiri_standard_ui_translation_patch(
            project_root,
            translated_root,
            source_roots=tuple(source_roots),
        )
    except FileNotFoundError as exc:
        return PatchApplicationResult(
            status="failed",
            message=f"{patch_info.patch.name} failed: {exc}",
        )

    if not staged.staged_paths and staged.missing_paths:
        selected_lookup = _prompt_standard_ui_lookup_dir(mgr, patch_info, parent)
        if selected_lookup is None:
            return PatchApplicationResult(
                status="cancelled",
                message=f"Cancelled {patch_info.patch.name}.",
            )

        staged = stage_kirikiri_standard_ui_translation_patch(
            project_root,
            translated_root,
            source_roots=tuple([*source_roots, selected_lookup]),
        )

    if not staged.staged_paths:
        if staged.missing_paths:
            missing_summary = ", ".join(path.as_posix() for path in staged.missing_paths)
            return PatchApplicationResult(
                status="failed",
                message=(
                    f"Could not find the standard UI source files for {patch_info.patch.name}: "
                    f"{missing_summary}"
                ),
            )
        return PatchApplicationResult(
            status="unchanged",
            message="No standard KiriKiri UI replacements were needed.",
        )

    staged_names = ", ".join(path.as_posix() for path in staged.staged_paths)
    message = f"Staged {patch_info.patch.name}: {staged_names}."
    if staged.skipped_paths:
        skipped_summary = ", ".join(path.as_posix() for path in staged.skipped_paths)
        message += f" No matching replacements were needed for: {skipped_summary}."
    if staged.missing_paths:
        missing_summary = ", ".join(path.as_posix() for path in staged.missing_paths)
        message += f" Missing source files: {missing_summary}."

    return PatchApplicationResult(
        status="applied",
        message=message,
        target_path=staged.staged_paths[0],
    )


def run_kirikiri_font_patch_workflow(
    mgr: "ManifestManager",
    patch_info: "DiscoveredParserPatch",
    parent: Optional["tk.Misc"],
    log,
) -> "PatchApplicationResult":
    from CherryAI.functions.apply_patches import PatchApplicationResult
    from CherryAI.gui.dialogs.kirikiri_font_patch_dialog import choose_kirikiri_font_patch_selection

    project_root = mgr.get_project_dir()
    resource_root = get_font_patch_resource_root(project_root)
    translated_root = mgr.get_translated_dir()
    paths = get_font_patch_paths(resource_root, translated_root)
    available = list_available_font_bundles(paths.fonts_library_root)
    if not available:
        return PatchApplicationResult(
            status="failed",
            message=(
                "No bundled font families are available under "
                f"{paths.fonts_library_root}."
            ),
        )

    existing = load_existing_font_patch_selection(paths.config_path)
    default_selection = existing or get_default_font_selection(paths.fonts_library_root)
    if default_selection is None:
        return PatchApplicationResult(
            status="failed",
            message="No default bundled font selection is available.",
        )

    selection = choose_kirikiri_font_patch_selection(
        parent,
        available,
        default_selection,
        current_selection=existing,
    )
    if selection is None:
        return PatchApplicationResult(
            status="cancelled",
            message=f"Cancelled {patch_info.patch.name}.",
        )

    staged = stage_font_patch_assets(resource_root, translated_root, selection)
    copied_fonts = describe_copied_fonts(staged.copied_font_paths)
    copied_system_patches = describe_copied_fonts(staged.copied_system_patch_paths)
    build_script_path = get_build_script_path(resource_root)
    message = (
        f"Staged {patch_info.patch.name}: {copied_fonts}. "
        f"System patches: {copied_system_patches}. "
        f"Config: {staged.paths.config_path}. "
        f"Build script: {build_script_path}."
    )
    if not staged.copied_dll:
        message += " No prebuilt version.dll was available; build one with the packaged script."

    return PatchApplicationResult(
        status="applied",
        message=message,
        target_path=staged.paths.config_path,
    )