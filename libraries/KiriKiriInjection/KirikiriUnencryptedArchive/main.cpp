#include "stdafx.h"

BOOL WINAPI DllMain(HINSTANCE hInstance, DWORD reason, LPVOID reserved)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        Proxy::Init();
        Debugger::Log(L"KirikiriUnencryptedArchive attached");
        FontPatch::Init();

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
                    Patcher::PatchSignatureCheck(hDll);
            }
        );

        Debugger::PatchMessageBoxHooks();

        Kirikiri::Init(
            []
            {
                CompilerHelper::Init();
                Patcher::PatchXP3StreamCreation();
                Patcher::PatchPlacedPathLookup();
                Patcher::PatchIStreamCreation();
                Patcher::PatchTextStreamCreation();
                Patcher::PatchAutoPathExports();
                Patcher::PatchStorageMediaRegistration();
            }
        );
    }
    else if (reason == DLL_PROCESS_DETACH)
    {
        FontPatch::Shutdown();
    }

    return TRUE;
}
