#pragma once

class EditMode
{
public:
    static void Init();
    static void Shutdown();
    static void OnTextStreamOpened(const std::wstring& requestedName, const std::wstring& placedPath, const std::wstring& editableFilePath);
    static void OnRenderedText(const std::wstring& text);
    static void OnScriptCurrentText(const std::wstring& text);
};
