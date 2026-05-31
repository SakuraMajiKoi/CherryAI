# version.dll Review

This review covers the code under `libraries/KiriKiriInjection/KirikiriUnencryptedArchive`, which is the source tree used to build `version.dll`.

## Build Surface

The DLL is built by `libraries/KiriKiriInjection/build_version_dll.py`, which finds a Visual Studio C++ setup script, runs `msbuild` on `KirikiriUnencryptedArchive.vcxproj`, and expects `Release/version.dll` as the output.

The DLL project compiles these implementation files:

- `main.cpp`
- `Proxy.cpp`
- `Debugger.cpp`
- `FontPatch.cpp`
- `Patcher.cpp`
- `ImportHooker.cpp`
- `CxdecHelper.cpp`
- `CustomTVPXP3ArchiveStream.cpp`
- `CompilerSpecific/CompilerHelper.cpp`
- `PE/PE.cpp`
- `Kirikiri/Kirikiri.cpp`
- `Kirikiri/ProxyFunctionExporter.cpp`
- `Kirikiri/tTJSString.cpp`
- `Kirikiri/tTJSVariant.cpp`
- `stdafx.cpp`

It links against the sibling `Detours` static library project, which compiles:

- `creatwth.cpp`
- `detours.cpp`
- `disasm.cpp`
- `disolarm.cpp`
- `disolarm64.cpp`
- `disolia64.cpp`
- `disolx64.cpp`
- `disolx86.cpp`
- `image.cpp`
- `modules.cpp`

## Function Summary

### `main.cpp`

- `DllMain` initializes the proxy layer, font patch, debugger hooks, and Kirikiri runtime hooks on attach.
- On detach it shuts the font patch down.

### `Proxy.cpp`

- `Proxy::Init` loads the original system `version.dll` from `%SystemRoot%\\System32` and resolves the version-export functions that the proxy forwards.
- The exported naked stubs jump directly into the resolved originals.

### `Kirikiri.cpp`

- `Kirikiri::Init` only activates on Kirikiri executables and registers the DLL-load callback.
- `IsKirikiriExe` checks the current executable's version resources for a Kirikiri copyright string.
- `HandleDllLoaded` watches for the engine exporter and patches `V2Link`.
- `HandleV2Link` resolves Kirikiri function exports, installs the proxy exporter, and triggers the deferred initialization callback.
- `CustomGetProcAddress` hides `GetSystemWow64DirectoryA` to avoid a broken proxy-kernel32 detection path.
- `CustomImageUnload` delays initialization until the game image is unloading if needed.
- `GetTrampoline` writes short jumps inside the engine's `.text` section so exported pointers stay engine-local.

### `Debugger.cpp`

- Provides logging, DLL-load callbacks, message-box hooks, and breakpoint helpers.
- `Log` appends UTF-8 text to the configured log file and also sends output to the debugger stream.
- `PatchMessageBoxHooks` installs one-time `MessageBoxA/W` hooks.
- `RegisterDllLoadHandler` installs the loader hooks used by the rest of the runtime.

### `FontPatch.cpp`

- `FontPatch::Init` loads font-patch configuration, registers bundled fonts, patches imports in the main module, and hooks future DLL loads.
- `FontPatch::Shutdown` unregisters fonts that were added with `AddFontResourceExW`.
- The font hooks adjust face selection, size, charset, quality, advance spacing, and text rendering behavior.
- The runtime config writer emits `patch/CherryAI.KiriKiriFontPatch.runtime.tjs`.

### `Patcher.cpp`

- Core archive/path override layer for loose files and archive members.
- `PatchSignatureCheck` disables the game signature verification path.
- `PatchXP3StreamCreation` swaps the XP3 stream factory so the DLL can serve loose overrides and unencrypted archive reads.
- `PatchPlacedPathLookup`, `PatchIStreamCreation`, and `PatchTextStreamCreation` redirect storage lookups to patch roots.
- `PatchAutoPathExports` and `PatchStorageMediaRegistration` wrap archive/media registration and unregistration.
- `CustomTVPGetPlacedPath`, `CustomTVPCreateIStream`, `CustomTVPCreateTextStreamForRead`, and `CustomStorageMediaOpen` implement the actual candidate search and redirection policy.
- `CreateLooseEncodedMdatStream` and `CreateLooseEncodedNeiStream` rebuild loose edits into the archive encodings expected by the game.
- `WriteStreamToFile` extracts archive data to disk when extraction is enabled.

### `CxdecHelper.cpp`

- Detects `archive://` cxdec URLs, converts them to local XP3 file paths, and checks whether an archive is cxdec-encoded.

### `CustomTVPXP3ArchiveStream.cpp`

- Exposes a binary stream wrapper for unencrypted XP3 segments by reading the backing archive file and returning the decompressed payload.

### `ImportHooker.cpp`

- Generic import-table patcher used to replace module imports with the DLL's hooks.

### `CompilerHelper.cpp`

- Detects the engine compiler flavor and locates vtables or adapts call conventions so the patch code can talk to either Borland or MSVC builds.

## Files Read, Written, or Required at Runtime

### Build-time requirements

- `libraries/KiriKiriInjection/KirikiriUnencryptedArchive/KirikiriUnencryptedArchive.vcxproj`
- `libraries/KiriKiriInjection/Detours/Detours.vcxproj`
- `libraries/KiriKiriInjection/build_version_dll.py`
- `libraries/KiriKiriInjection/KirikiriUnencryptedArchive/exports.def`
- All `.cpp` and `.h` files listed in the project files above

### Runtime reads and writes

- `Proxy::Init` reads the system `version.dll` from the Windows system directory.
- `Kirikiri::IsKirikiriExe` reads the current executable's version resources only.
- `Debugger::EnsureLogConfigLoaded` reads `kirikiri-patched.ini` from the module folder if present.
- `Debugger::Log` appends to the configured log file, defaulting to `kirikiri-patched.log` in the module folder.
- `FontPatch::LoadConfig` looks for configuration in this order:
  - `CherryAI.KiriKiriPatch.json`
  - `patch/CherryAI.KiriKiriPatch.json`
  - `CherryAI.KiriKiriFontPatch.json`
  - `patch/CherryAI.KiriKiriFontPatch.json`
- `FontPatch::LoadConfig` also reads any font files named in the config and writes `patch/CherryAI.KiriKiriFontPatch.runtime.tjs`.
- `Patcher::BuildOverrideUrlsForPath` and related helpers read the active patch tree under the module root, especially `patch/`, `patch/data/`, and `patch/data/csv/`.
- `Patcher::TryBuildCachedTlgFromPng` requires `kano2_tool.exe` beside the game, writes temporary work files under `patch/__cherryai_tlg_cache_work/`, and caches built `.tlg` files under `patch/__cherryai_tlg_cache/`.
- `Patcher::CustomTVPCreateIStream` may create temporary NEI data under `patch/__cherryai_nei_tmp/` before falling back to an in-memory stream.
- `Patcher::WriteStreamToFile` creates the destination directory tree before extracting a stream.
- If `extract-unencrypted.txt` exists beside the module, `Patcher::CustomStorageMediaOpen` writes extracted files under `unencrypted/`.

## Duplicate or Repeated Logic Hotspots

- `FontPatch::ReadFontPatchConfigText` repeats the same read/parse attempt across four fallback paths, with `GetModuleRoot()` recomputed for each branch.
- `FontPatch::CreateFontIndirectA/W` and `FontPatch::CreateFontA/W` duplicate almost the same face/size/charset adjustment logic.
- `FontPatch` also repeats the render-text normalization and logging pattern across `TextOutA/W`, `ExtTextOutA/W`, `DrawTextA/W`, and the extent/metrics hooks.
- `Patcher::CustomTVPGetPlacedPath`, `Patcher::CustomTVPCreateIStream`, `Patcher::CustomTVPCreateTextStreamForRead`, `Patcher::CustomStorageMediaOpen`, and the archive-index callback all re-run the same candidate URL generation and self-redirect checks with only small variations.
- `Patcher::CustomTVPAddAutoPath` and `Patcher::CustomTVPRemoveAutoPath` are near-identical cxdec URL remappers.
- `Patcher::AddPatchFolderOverrideUrls` repeats the same relative-path probe across `patch/`, `patch/data/csv/`, `patch/data/`, and the patch folder root.
- `TryBuildCachedTlgFromPng` repeatedly cleans and recreates the same work directories while trying different archive/selector combinations.
- `Debugger::Log` and `FontPatch::WriteRuntimeMessageLayerConfig` both resolve module-root-relative paths through repeated `Path::GetModuleFolderPath(nullptr)` calls.

## Smallest Plausible Footprint

If the goal is a runtime-only payload, keep only `version.dll` plus the configuration and content that the DLL actually consumes:

- `CherryAI.KiriKiriPatch.json` or `CherryAI.KiriKiriFontPatch.json`
- the font files referenced by that config
- optional `kirikiri-patched.ini` if logging is desired
- optional generated `patch/CherryAI.KiriKiriFontPatch.runtime.tjs`

Everything else in `libraries/KiriKiriInjection` is build or source material and can be dropped from a deployment package, including:

- the full `Detours/` source tree
- the `CompilerSpecific/`, `Kirikiri/`, `PE/`, and other helper source folders
- all `.vcxproj`, `.vcxproj.filters`, `.vcxproj.user`, `.tlog`, `.obj`, `.lib`, `.pdb`, and `build_output.txt` artifacts
- `build_version_dll.py` and the Visual Studio scaffolding files

If the requirement is to keep a rebuildable source tree instead, the minimum plausible set is the project files, `stdafx.*`, the core DLL sources listed above, and the complete Detours tree. The Detours sources are not optional for a clean rebuild.