#include "stdafx.h"

BOOL WINAPI DllMain(HINSTANCE hInstance, DWORD reason, LPVOID reserved)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        Debugger::Log(L"KirikiriUnencryptedArchive attach begin");
        Proxy::Init();
        Debugger::Log(L"KirikiriUnencryptedArchive proxy initialized");
        EditMode::Init();
        Debugger::Log(L"KirikiriUnencryptedArchive edit mode initialized");
        FontPatch::Init();
        Debugger::Log(L"KirikiriUnencryptedArchive font patch initialized");

        Debugger::RegisterDllLoadHandler(
            [](const wchar_t* pwszDllPath, HMODULE hDll)
            {
                if (pwszDllPath != nullptr)
                {
                    std::wstring dllName = StringUtil::ToLower(Path::GetFileName(pwszDllPath));
                    if (dllName == L"user32.dll")
                        Debugger::PatchMessageBoxHooks();
                }

                if (Debugger::FindExport(hDll, "V2Link") != nullptr)
                {
                    Debugger::Log(L"V2Link export found in %ls", pwszDllPath != nullptr ? pwszDllPath : L"<memory module>");
                    Patcher::PatchSignatureCheck(hDll);
                }
            }
        );

        Debugger::PatchMessageBoxHooks();

        Kirikiri::Init(
            []
            {
                Debugger::Log(L"Kirikiri initialization callback begin");
                CompilerHelper::Init();
                Patcher::PatchXP3StreamCreation();
                Patcher::PatchPlacedPathLookup();
                Patcher::PatchIStreamCreation();
                Patcher::PatchTextStreamCreation();
                Patcher::PatchAutoPathExports();
                Patcher::PatchStorageMediaRegistration();
                Debugger::Log(L"Kirikiri initialization callback end");
            }
        );
    }
    else if (reason == DLL_PROCESS_DETACH)
    {
        FontPatch::Shutdown();
        EditMode::Shutdown();
    }

    return TRUE;
}
