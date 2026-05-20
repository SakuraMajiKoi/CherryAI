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
                if (Debugger::FindExport(hDll, "V2Link") != nullptr)
                    Patcher::PatchSignatureCheck(hDll);
            }
        );

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
