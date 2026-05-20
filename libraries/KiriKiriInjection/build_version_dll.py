from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parent / "KirikiriUnencryptedArchive"
PROJECT_FILE = PROJECT_ROOT / "KirikiriUnencryptedArchive.vcxproj"


def _candidate_setup_scripts() -> list[Path]:
    candidates: list[Path] = []
    program_files = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    ]
    for base in program_files:
        vs_root = base / "Microsoft Visual Studio"
        if not vs_root.is_dir():
            continue
        candidates.extend(vs_root.glob("**/Common7/Tools/VsDevCmd.bat"))
        candidates.extend(vs_root.glob("**/VC/Auxiliary/Build/vcvarsall.bat"))
    return sorted({path.resolve() for path in candidates if path.is_file()})


def _prompt_missing_visual_studio() -> int:
    message = (
        "Visual Studio with Desktop development for C++ was not found.\n"
        "Install Visual Studio Build Tools or Visual Studio, then rerun this script."
    )
    print(message)
    if sys.stdin.isatty():
        try:
            input("Press Enter to exit...")
        except EOFError:
            pass
    return 1


def _build_command(setup_script: Path) -> str:
    quoted_setup = str(setup_script)
    quoted_project = str(PROJECT_FILE)
    if setup_script.name.lower() == "vcvarsall.bat":
        setup = f'call "{quoted_setup}" x86'
    else:
        setup = f'call "{quoted_setup}" -arch=x86 -host_arch=x64'
    build = (
        f'msbuild "{quoted_project}" /m /p:Configuration=Release /p:Platform=Win32 '
        f"/p:OutDir=Release\\"
    )
    return f"{setup} && {build}"


def main() -> int:
    if not PROJECT_FILE.is_file():
        print(f"Missing project file: {PROJECT_FILE}")
        return 1

    setup_scripts = _candidate_setup_scripts()
    if not setup_scripts:
        return _prompt_missing_visual_studio()

    command = _build_command(setup_scripts[0])
    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        check=False,
        shell=True,
    )
    if completed.returncode != 0:
        return completed.returncode

    output_path = PROJECT_ROOT / "Release" / "version.dll"
    if output_path.is_file():
        print(f"Built {output_path}")
        return 0

    print("Build finished but Release/version.dll was not produced.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())