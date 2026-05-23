#include "stdafx.h"

namespace
{
    constexpr wchar_t CONFIG_PATH_PRIMARY[] = L"patch\\CherryAI.KiriKiriPatch.json";
    constexpr wchar_t CONFIG_PATH_LEGACY[] = L"patch\\CherryAI.KiriKiriFontPatch.json";
    constexpr wchar_t RUNTIME_CONFIG_PATH[] = L"patch\\CherryAI.KiriKiriFontPatch.runtime.tjs";
    constexpr DWORD FONT_LOAD_FLAGS = FR_PRIVATE;

    struct FontPatchConfig
    {
        bool Enabled = false;
        bool LogFontCalls = true;
        bool ReplaceCjkFaces = false;
        int AdvancePercent = 100;
        int CharacterExtraPercent = 100;
        int CharacterExtraOffset = 0;
        int CharSet = DEFAULT_CHARSET;
        int Quality = DEFAULT_QUALITY;
        int HeightPercent = 100;
        int LineSpacingOffsetPixels = 0;
        int WrapRightPaddingPixels = 220;
        std::wstring WrapMode = L"pixel";
        int WidthPercent = 100;
        std::wstring DefaultFace;
        std::wstring RegularFontPath;
        std::wstring BoldFontPath;
        std::wstring LatinFace;
        std::wstring LatinRegularFontPath;
        std::wstring LatinBoldFontPath;
        int LatinCharSet = ANSI_CHARSET;
        std::vector<std::wstring> MatchFaces;
        std::vector<std::wstring> RegisteredFontPaths;
    };

    struct FontOverrideState
    {
        HGDIOBJ Previous = nullptr;
        HFONT Replacement = nullptr;
        bool UseLatin = false;
    };

    struct AnsiTraceState
    {
        bool CreateCompatibleDC = false;
        bool BitBlt = false;
        bool StretchBlt = false;
        bool GetStockObjectSystemFont = false;
        bool SelectObjectSystemFont = false;
        bool TextOutA = false;
        bool ExtTextOutA = false;
        bool DrawTextA = false;
        bool GetTextMetricsA = false;
        bool GetTextExtentPointA = false;
        bool GetTextExtentPoint32A = false;
        bool GetTextExtentExPointA = false;
        bool GetGlyphOutlineA = false;
        bool RefreshingMorning = false;
    };

    FontPatchConfig g_config;
    bool g_initialized = false;
    AnsiTraceState g_ansiTrace;

    HGDIOBJ g_systemFontHandle = nullptr;
    std::set<HDC> g_memoryDcs;

    std::wstring GetModuleRoot()
    {
        return Path::GetModuleFolderPath(nullptr);
    }

    std::wstring TrimAsciiWhitespace(const std::wstring& value)
    {
        size_t start = 0;
        while (start < value.size() && iswspace(value[start]))
            start++;

        size_t end = value.size();
        while (end > start && iswspace(value[end - 1]))
            end--;

        return value.substr(start, end - start);
    }

    std::wstring NormalizeFaceAlias(const std::wstring& value)
    {
        std::wstring normalized = StringUtil::ToLower(TrimAsciiWhitespace(StringUtil::Replace(value, L'\x3000', L' ')));
        if (normalized == L"meiryo" || normalized == L"\x30e1\x30a4\x30ea\x30aa")
            return L"meiryo";
        if (normalized == L"ms pgothic" || normalized == L"\xff4d\xff53 \xff50\x30b4\x30b7\x30c3\x30af" || normalized == L"ms p gothic")
            return L"ms pgothic";
        if (normalized == L"ms gothic" || normalized == L"\xff4d\xff53 \x30b4\x30b7\x30c3\x30af")
            return L"ms gothic";
        if (normalized == L"ms ui gothic" || normalized == L"\xff4d\xff53 \xff55\xff49 \x30b4\x30b7\x30c3\x30af")
            return L"ms ui gothic";
        if (normalized == L"yu gothic" || normalized == L"yu gothic ui" || normalized == L"yugothic")
            return L"yu gothic";
        return normalized;
    }

    bool ContainsNonAscii(const std::wstring& value)
    {
        for (wchar_t ch : value)
        {
            if (ch > 0x7F)
                return true;
        }
        return false;
    }

    bool IsCjkTextChar(wchar_t ch)
    {
        return (ch >= 0x3000 && ch <= 0x30FF)
            || (ch >= 0x31F0 && ch <= 0x31FF)
            || (ch >= 0x3400 && ch <= 0x4DBF)
            || (ch >= 0x4E00 && ch <= 0x9FFF)
            || (ch >= 0xF900 && ch <= 0xFAFF)
            || (ch >= 0xFF01 && ch <= 0xFFEE);
    }

    std::wstring PreviewText(const std::wstring& text)
    {
        if (text.empty())
            return L"<empty>";

        const size_t previewLength = std::min<size_t>(text.size(), 32);
        std::wstring preview;
        preview.reserve(previewLength + 3);
        for (size_t index = 0; index < previewLength; ++index)
        {
            wchar_t ch = text[index];
            if (ch == L'\r' || ch == L'\n' || ch == L'\t')
                ch = L' ';
            preview.push_back(ch);
        }
        if (text.size() > previewLength)
            preview += L"...";
        return preview;
    }

    bool IsCjkFaceRequest(const std::wstring& faceName)
    {
        const std::wstring normalized = NormalizeFaceAlias(faceName);
        if (normalized.empty())
            return false;
        if (ContainsNonAscii(normalized))
            return true;
        return normalized == L"meiryo"
            || normalized == L"ms pgothic"
            || normalized == L"ms gothic"
            || normalized == L"ms ui gothic"
            || normalized == L"yu gothic"
            || normalized == L"ms mincho"
            || normalized == L"ms pmincho";
    }

    bool ShouldSkipReplacement(const std::wstring& faceName, DWORD charSet)
    {
        if (g_config.ReplaceCjkFaces)
            return false;
        return charSet == SHIFTJIS_CHARSET || IsCjkFaceRequest(faceName);
    }

    std::wstring ReadUtf8TextFile(const std::wstring& filePath)
    {
        FILE* pFile = _wfopen(filePath.c_str(), L"rb");
        if (pFile == nullptr)
            return L"";

        fseek(pFile, 0, SEEK_END);
        long size = ftell(pFile);
        fseek(pFile, 0, SEEK_SET);
        std::string text;
        text.resize(size > 0 ? size : 0);
        if (!text.empty())
            fread(text.data(), 1, text.size(), pFile);
        fclose(pFile);

        if (text.size() >= 3 && (BYTE)text[0] == 0xEF && (BYTE)text[1] == 0xBB && (BYTE)text[2] == 0xBF)
            text.erase(0, 3);
        return StringUtil::ToUTF16(text);
    }

    void WriteUtf8TextFile(const std::wstring& filePath, const std::wstring& text)
    {
        FILE* pFile = _wfopen(filePath.c_str(), L"wb");
        if (pFile == nullptr)
            return;

        const std::string utf8 = StringUtil::ToUTF8(text);
        if (!utf8.empty())
            fwrite(utf8.data(), 1, utf8.size(), pFile);
        fclose(pFile);
    }

    void WriteRuntimeMessageLayerConfig(
        int lineSpacingOffsetPixels,
        int wrapRightPaddingPixels,
        const std::wstring& wrapMode)
    {
        int clampedWrapPadding = wrapRightPaddingPixels;
        if (clampedWrapPadding < 0)
            clampedWrapPadding = 0;

        std::wstring normalizedWrapMode = StringUtil::ToLower(TrimAsciiWhitespace(wrapMode));
        if (normalizedWrapMode != L"character")
            normalizedWrapMode = L"pixel";

        WriteUtf8TextFile(
            Path::Combine(GetModuleRoot(), RUNTIME_CONFIG_PATH),
            StringUtil::Format(
                L"%%[\r\n\tline_spacing_offset_pixels: %d,\r\n\twrap_right_padding_pixels: %d,\r\n\twrap_mode: \"%ls\",\r\n]\r\n",
                lineSpacingOffsetPixels,
                clampedWrapPadding,
                normalizedWrapMode.c_str()));
    }

    std::wstring WideFromText(LPCWSTR text, int count)
    {
        if (text == nullptr)
            return L"";
        if (count < 0)
            return std::wstring(text);
        if (count == 0)
            return L"";
        return std::wstring(text, text + count);
    }

    std::wstring PreviewDx(const INT* values, UINT count)
    {
        if (values == nullptr || count == 0)
            return L"[]";

        const UINT previewCount = std::min<UINT>(count, 6);
        std::wstring text = L"[";
        for (UINT index = 0; index < previewCount; ++index)
        {
            if (index > 0)
                text += L",";
            text += StringUtil::Format(L"%d", values[index]);
        }
        if (count > previewCount)
            text += L",...";
        text += L"]";
        return text;
    }

    std::wstring ExtractString(const std::wstring& text, const wchar_t* key)
    {
        std::wregex pattern(StringUtil::Format(L"\"%ls\"\\s*:\\s*\"([^\"]+)\"", key));
        std::wsmatch match;
        if (std::regex_search(text, match, pattern) && match.size() > 1)
            return match[1].str();
        return L"";
    }

    std::wstring ExtractNestedString(const std::wstring& text, const wchar_t* objectKey, const wchar_t* fieldKey)
    {
        std::wregex pattern(
            StringUtil::Format(
                L"\"%ls\"\\s*:\\s*\\{[^\\}]*\"%ls\"\\s*:\\s*\"([^\"]+)\"",
                objectKey,
                fieldKey));
        std::wsmatch match;
        if (std::regex_search(text, match, pattern) && match.size() > 1)
            return match[1].str();
        return L"";
    }

    int ExtractInt(const std::wstring& text, const wchar_t* key, int fallback)
    {
        std::wregex pattern(StringUtil::Format(L"\"%ls\"\\s*:\\s*(\\d+)", key));
        std::wsmatch match;
        if (!std::regex_search(text, match, pattern) || match.size() < 2)
            return fallback;
        return _wtoi(match[1].str().c_str());
    }

    int ExtractSignedInt(const std::wstring& text, const wchar_t* key, int fallback)
    {
        std::wregex pattern(StringUtil::Format(L"\"%ls\"\\s*:\\s*(-?\\d+)", key));
        std::wsmatch match;
        if (!std::regex_search(text, match, pattern) || match.size() < 2)
            return fallback;
        return _wtoi(match[1].str().c_str());
    }

    LONG AdjustSignedMetric(LONG value, int percent, int offsetPixels)
    {
        if (value == 0)
            return 0;

        LONG sign = value < 0 ? -1 : 1;
        LONG magnitude = labs(value);
        if (percent > 0 && percent != 100)
            magnitude = (magnitude * percent) / 100;
        magnitude += offsetPixels;
        if (magnitude < 1)
            magnitude = 1;
        return sign * magnitude;
    }

    bool ExtractBool(const std::wstring& text, const wchar_t* key, bool fallback)
    {
        std::wregex pattern(StringUtil::Format(L"\"%ls\"\\s*:\\s*(true|false)", key), std::regex_constants::icase);
        std::wsmatch match;
        if (!std::regex_search(text, match, pattern) || match.size() < 2)
            return fallback;
        return StringUtil::ToLower(match[1].str()) == L"true";
    }

    std::vector<std::wstring> ExtractStringArray(const std::wstring& text, const wchar_t* key)
    {
        std::wregex pattern(StringUtil::Format(L"\"%ls\"\\s*:\\s*\\[([^\\]]*)\\]", key));
        std::wsmatch match;
        if (!std::regex_search(text, match, pattern) || match.size() < 2)
            return {};

        std::vector<std::wstring> result;
        std::wregex entryPattern(L"\"([^\"]+)\"");
        auto begin = std::wsregex_iterator(match[1].first, match[1].second, entryPattern);
        auto end = std::wsregex_iterator();
        for (auto it = begin; it != end; ++it)
            result.push_back((*it)[1].str());
        return result;
    }

    std::wstring ResolveRelativePath(const std::wstring& value)
    {
        if (value.empty())
            return value;
        if (value.find(L":") != std::wstring::npos)
            return value;
        return Path::Combine(GetModuleRoot(), StringUtil::Replace(value, L'/', L'\\'));
    }

    std::wstring ReadFontPatchConfigText()
    {
        std::wstring configText = ReadUtf8TextFile(Path::Combine(GetModuleRoot(), CONFIG_PATH_PRIMARY));
        if (!configText.empty())
            return configText;
        return ReadUtf8TextFile(Path::Combine(GetModuleRoot(), CONFIG_PATH_LEGACY));
    }

    bool LoadConfig()
    {
        FontPatchConfig config;
        std::wstring configText = ReadFontPatchConfigText();
        if (configText.empty())
            return false;

        config.DefaultFace = ExtractString(configText, L"default_face");
        config.RegularFontPath = ResolveRelativePath(ExtractNestedString(configText, L"regular_font", L"file"));
        config.BoldFontPath = ResolveRelativePath(ExtractNestedString(configText, L"bold_font", L"file"));
        config.LatinFace = ExtractString(configText, L"latin_face");
        config.LatinRegularFontPath = ResolveRelativePath(ExtractNestedString(configText, L"latin_regular_font", L"file"));
        config.LatinBoldFontPath = ResolveRelativePath(ExtractNestedString(configText, L"latin_bold_font", L"file"));
        config.LogFontCalls = ExtractBool(configText, L"log_font_calls", true);
        config.ReplaceCjkFaces = ExtractBool(configText, L"replace_cjk_faces", false);
        config.AdvancePercent = ExtractInt(configText, L"advance_percent", 100);
        config.CharacterExtraPercent = ExtractInt(configText, L"character_extra_percent", 100);
        config.CharacterExtraOffset = ExtractInt(configText, L"character_extra_offset", 0);
        config.CharSet = ExtractInt(configText, L"charset", DEFAULT_CHARSET);
        config.LatinCharSet = ExtractInt(configText, L"latin_charset", ANSI_CHARSET);
        config.Quality = ExtractInt(configText, L"quality", DEFAULT_QUALITY);
        config.HeightPercent = ExtractInt(configText, L"height_percent", 100);
        config.LineSpacingOffsetPixels = ExtractSignedInt(configText, L"height_offset_pixels", 0);
        config.WrapRightPaddingPixels = ExtractSignedInt(
            configText,
            L"WrapRightPaddingPixels",
            ExtractSignedInt(configText, L"wrap_right_padding_pixels", 220));
        if (config.WrapRightPaddingPixels < 0)
            config.WrapRightPaddingPixels = 0;

        std::wstring wrapMode = ExtractString(configText, L"WrapMode");
        if (wrapMode.empty())
            wrapMode = ExtractString(configText, L"wrap_mode");
        wrapMode = StringUtil::ToLower(TrimAsciiWhitespace(wrapMode));
        config.WrapMode = wrapMode == L"character" ? L"character" : L"pixel";

        config.WidthPercent = ExtractInt(configText, L"width_percent", 100);
        config.MatchFaces = ExtractStringArray(configText, L"match_faces");
        if (config.MatchFaces.empty())
            config.MatchFaces.push_back(L"*");

        WriteRuntimeMessageLayerConfig(
            config.LineSpacingOffsetPixels,
            config.WrapRightPaddingPixels,
            config.WrapMode);

        config.Enabled = !config.DefaultFace.empty() && !config.RegularFontPath.empty();
        if (!config.Enabled)
            return false;

        g_config = config;
        return true;
    }

    bool MatchesFace(const std::wstring& faceName)
    {
        if (g_config.MatchFaces.empty())
            return true;
        std::wstring requested = NormalizeFaceAlias(faceName);
        if (requested.empty())
            return true;
        for (const std::wstring& entry : g_config.MatchFaces)
        {
            std::wstring lowered = NormalizeFaceAlias(entry);
            if (lowered == L"*" || lowered == requested)
                return true;
        }
        return false;
    }

    bool HasLatinVariant()
    {
        return !g_config.LatinFace.empty() && !g_config.LatinRegularFontPath.empty();
    }

    bool ContainsTextNeedleInsensitive(const std::wstring& text, const wchar_t* needle)
    {
        if (text.empty() || needle == nullptr || needle[0] == L'\0')
            return false;
        return StringUtil::ToLower(text).find(StringUtil::ToLower(std::wstring(needle))) != std::wstring::npos;
    }

    bool IsManagedFace(const std::wstring& faceName)
    {
        const std::wstring normalized = NormalizeFaceAlias(faceName);
        if (normalized.empty())
            return false;
        if (normalized == NormalizeFaceAlias(g_config.DefaultFace))
            return true;
        if (HasLatinVariant() && normalized == NormalizeFaceAlias(g_config.LatinFace))
            return true;
        return false;
    }

    bool ShouldUseLatinVariant(const std::wstring& text)
    {
        if (!HasLatinVariant())
            return false;

        bool sawVisible = false;
        for (wchar_t ch : text)
        {
            if (iswspace(ch))
                continue;
            sawVisible = true;
            if (IsCjkTextChar(ch))
                return false;
        }
        return sawVisible;
    }

    bool GetCurrentLogFont(HDC hdc, LOGFONTW& font)
    {
        HGDIOBJ current = GetCurrentObject(hdc, OBJ_FONT);
        if (current == nullptr)
            return false;
        return GetObjectW(current, sizeof(font), &font) > 0;
    }

    HGDIOBJ GetSystemFontHandle()
    {
        if (g_systemFontHandle == nullptr)
            g_systemFontHandle = ::GetStockObject(SYSTEM_FONT);
        return g_systemFontHandle;
    }

    void TraceStockFontSelection(const wchar_t* apiName, HDC hdc, HGDIOBJ handle, HGDIOBJ previous)
    {
        if (!g_config.LogFontCalls || g_ansiTrace.SelectObjectSystemFont)
            return;

        const HGDIOBJ systemFont = GetSystemFontHandle();
        if (handle != systemFont && previous != systemFont)
            return;

        g_ansiTrace.SelectObjectSystemFont = true;
        LOGFONTW font = {};
        const bool hasFont = GetCurrentLogFont(hdc, font);
        const std::wstring currentFace = hasFont ? std::wstring(font.lfFaceName) : L"";
        Debugger::Log(
            L"FontPatch stock-font trace api=%ls selectedSystem=%d previousSystem=%d currentFace=%ls charset=%u",
            apiName,
            handle == systemFont ? 1 : 0,
            previous == systemFont ? 1 : 0,
            hasFont && !currentFace.empty() ? currentFace.c_str() : L"<none>",
            hasFont ? font.lfCharSet : 0);
    }

    void RegisterMemoryDc(HDC hdc)
    {
        if (hdc != nullptr)
            g_memoryDcs.insert(hdc);
    }

    bool IsTrackedMemoryDc(HDC hdc)
    {
        return hdc != nullptr && g_memoryDcs.contains(hdc);
    }

    void TraceCompatibleDcHit(HDC hdcNew, HDC hdcSource)
    {
        if (!g_config.LogFontCalls || g_ansiTrace.CreateCompatibleDC)
            return;

        g_ansiTrace.CreateCompatibleDC = true;
        Debugger::Log(
            L"FontPatch offscreen trace api=CreateCompatibleDC new=%p source=%p trackedSource=%d",
            hdcNew,
            hdcSource,
            IsTrackedMemoryDc(hdcSource) ? 1 : 0);
    }

    void TraceBltHit(
        bool* alreadyTraced,
        const wchar_t* apiName,
        HDC hdcDest,
        HDC hdcSrc,
        int width,
        int height,
        DWORD rop)
    {
        if (!g_config.LogFontCalls || alreadyTraced == nullptr || *alreadyTraced)
            return;
        if (!IsTrackedMemoryDc(hdcDest) && !IsTrackedMemoryDc(hdcSrc))
            return;

        *alreadyTraced = true;
        Debugger::Log(
            L"FontPatch offscreen trace api=%ls dest=%p src=%p destTracked=%d srcTracked=%d size=%dx%d rop=0x%X",
            apiName,
            hdcDest,
            hdcSrc,
            IsTrackedMemoryDc(hdcDest) ? 1 : 0,
            IsTrackedMemoryDc(hdcSrc) ? 1 : 0,
            width,
            height,
            rop);
    }

    void TraceAnsiTextHit(bool* alreadyTraced, const wchar_t* apiName, HDC hdc, const std::wstring& text)
    {
        if (!g_config.LogFontCalls || alreadyTraced == nullptr || *alreadyTraced)
            return;

        *alreadyTraced = true;
        LOGFONTW font = {};
        const bool hasFont = GetCurrentLogFont(hdc, font);
        const std::wstring currentFace = hasFont ? std::wstring(font.lfFaceName) : L"";
        const bool matchesManagedFace = hasFont && IsManagedFace(currentFace);
        const bool matchesConfiguredFace = hasFont && MatchesFace(currentFace);
        const bool useLatin = ShouldUseLatinVariant(text);
        Debugger::Log(
            L"FontPatch ANSI first-hit api=%ls text=%ls face=%ls charset=%u managed=%d matched=%d latin=%d len=%u",
            apiName,
            PreviewText(text).c_str(),
            hasFont && !currentFace.empty() ? currentFace.c_str() : L"<none>",
            hasFont ? font.lfCharSet : 0,
            matchesManagedFace ? 1 : 0,
            matchesConfiguredFace ? 1 : 0,
            useLatin ? 1 : 0,
            (UINT)text.size());
    }

    void TraceRefreshingMorningHit(const wchar_t* apiName, HDC hdc, const std::wstring& text)
    {
        if (!g_config.LogFontCalls || g_ansiTrace.RefreshingMorning)
            return;
        if (!ContainsTextNeedleInsensitive(text, L"refreshing morning"))
            return;

        g_ansiTrace.RefreshingMorning = true;
        LOGFONTW font = {};
        const bool hasFont = GetCurrentLogFont(hdc, font);
        const std::wstring currentFace = hasFont ? std::wstring(font.lfFaceName) : L"";
        Debugger::Log(
            L"FontPatch ANSI target-hit api=%ls text=%ls face=%ls charset=%u latin=%d",
            apiName,
            PreviewText(text).c_str(),
            hasFont && !currentFace.empty() ? currentFace.c_str() : L"<none>",
            hasFont ? font.lfCharSet : 0,
            ShouldUseLatinVariant(text) ? 1 : 0);
    }

    void TraceAnsiMetricHit(bool* alreadyTraced, const wchar_t* apiName, HDC hdc)
    {
        if (!g_config.LogFontCalls || alreadyTraced == nullptr || *alreadyTraced)
            return;

        *alreadyTraced = true;
        LOGFONTW font = {};
        const bool hasFont = GetCurrentLogFont(hdc, font);
        const std::wstring currentFace = hasFont ? std::wstring(font.lfFaceName) : L"";
        Debugger::Log(
            L"FontPatch ANSI first-hit api=%ls face=%ls charset=%u managed=%d matched=%d",
            apiName,
            hasFont && !currentFace.empty() ? currentFace.c_str() : L"<none>",
            hasFont ? font.lfCharSet : 0,
            hasFont && IsManagedFace(currentFace) ? 1 : 0,
            hasFont && MatchesFace(currentFace) ? 1 : 0);
    }

    void TraceAnsiGlyphHit(bool* alreadyTraced, const wchar_t* apiName, HDC hdc, UINT uChar, UINT format)
    {
        if (!g_config.LogFontCalls || alreadyTraced == nullptr || *alreadyTraced)
            return;

        *alreadyTraced = true;
        LOGFONTW font = {};
        const bool hasFont = GetCurrentLogFont(hdc, font);
        const std::wstring currentFace = hasFont ? std::wstring(font.lfFaceName) : L"";
        Debugger::Log(
            L"FontPatch ANSI first-hit api=%ls char=0x%X format=0x%X face=%ls charset=%u managed=%d matched=%d",
            apiName,
            uChar,
            format,
            hasFont && !currentFace.empty() ? currentFace.c_str() : L"<none>",
            hasFont ? font.lfCharSet : 0,
            hasFont && IsManagedFace(currentFace) ? 1 : 0,
            hasFont && MatchesFace(currentFace) ? 1 : 0);
    }

    FontOverrideState ApplyTextFontOverride(HDC hdc, const std::wstring& text, const wchar_t* apiName)
    {
        FontOverrideState state;
        // Keep script routing consistent even when engines draw one glyph at a
        // time; mixed per-glyph fallback creates visible face flipping.
        state.UseLatin = ShouldUseLatinVariant(text);
        if (!HasLatinVariant())
            return state;

        LOGFONTW font = {};
        if (!GetCurrentLogFont(hdc, font))
            return state;

        const std::wstring currentFace(font.lfFaceName);
        if (!IsManagedFace(currentFace) && !MatchesFace(currentFace))
            return state;

        const std::wstring& targetFace = state.UseLatin ? g_config.LatinFace : g_config.DefaultFace;
        const BYTE targetCharSet = (BYTE)(state.UseLatin ? g_config.LatinCharSet : g_config.CharSet);
        if (targetFace.empty())
            return state;

        if (NormalizeFaceAlias(currentFace) == NormalizeFaceAlias(targetFace)
            && font.lfCharSet == targetCharSet
            && font.lfQuality == g_config.Quality)
        {
            return state;
        }

        wcsncpy_s(font.lfFaceName, targetFace.c_str(), LF_FACESIZE - 1);
        font.lfFaceName[LF_FACESIZE - 1] = L'\0';
        font.lfCharSet = targetCharSet;
        font.lfQuality = (BYTE)g_config.Quality;
        state.Replacement = ::CreateFontIndirectW(&font);
        if (state.Replacement == nullptr)
            return state;

        state.Previous = SelectObject(hdc, state.Replacement);
        if (g_config.LogFontCalls)
        {
            Debugger::Log(
                L"FontPatch %ls script=%ls %ls -> %ls text=%ls",
                apiName,
                state.UseLatin ? L"latin" : L"cjk",
                currentFace.empty() ? L"<default>" : currentFace.c_str(),
                targetFace.c_str(),
                PreviewText(text).c_str());
        }
        return state;
    }

    void RestoreTextFontOverride(HDC hdc, const FontOverrideState& state)
    {
        if (state.Previous != nullptr)
            SelectObject(hdc, state.Previous);
        if (state.Replacement != nullptr)
            DeleteObject(state.Replacement);
    }

    void RegisterFontPath(const std::wstring& fontPath)
    {
        if (fontPath.empty())
            return;
        if (AddFontResourceExW(fontPath.c_str(), FONT_LOAD_FLAGS, nullptr) > 0)
        {
            g_config.RegisteredFontPaths.push_back(fontPath);
            if (g_config.LogFontCalls)
                Debugger::Log(L"FontPatch registered %ls", fontPath.c_str());
        }
        else if (g_config.LogFontCalls)
        {
            Debugger::Log(L"FontPatch failed to register %ls (error=%u)", fontPath.c_str(), GetLastError());
        }
    }

    void ApplyToLogFont(LOGFONTW& font)
    {
        std::wstring originalFace(font.lfFaceName);
        if (!MatchesFace(originalFace) || ShouldSkipReplacement(originalFace, font.lfCharSet))
        {
            if (g_config.LogFontCalls)
            {
                Debugger::Log(
                    L"FontPatch saw %ls height=%ld weight=%ld charset=%u quality=%u (pass-through)",
                    originalFace.empty() ? L"<default>" : originalFace.c_str(),
                    font.lfHeight,
                    font.lfWeight,
                    font.lfCharSet,
                    font.lfQuality);
            }
            return;
        }

        if (!g_config.DefaultFace.empty())
        {
            wcsncpy_s(font.lfFaceName, g_config.DefaultFace.c_str(), LF_FACESIZE - 1);
            font.lfFaceName[LF_FACESIZE - 1] = L'\0';
        }
        font.lfCharSet = (BYTE)g_config.CharSet;
        font.lfQuality = (BYTE)g_config.Quality;
        font.lfHeight = AdjustSignedMetric(font.lfHeight, g_config.HeightPercent, 0);
        if (g_config.WidthPercent > 0 && g_config.WidthPercent != 100)
        {
            if (font.lfWidth != 0)
                font.lfWidth = (font.lfWidth * g_config.WidthPercent) / 100;
            else if (font.lfHeight != 0)
                font.lfWidth = max(1L, (labs(font.lfHeight) * g_config.WidthPercent) / 100);
        }

        if (g_config.LogFontCalls)
        {
            Debugger::Log(
                L"FontPatch %ls -> %ls height=%ld width=%ld weight=%ld charset=%u quality=%u",
                originalFace.empty() ? L"<default>" : originalFace.c_str(),
                font.lfFaceName,
                font.lfHeight,
                font.lfWidth,
                font.lfWeight,
                font.lfCharSet,
                font.lfQuality);
        }
    }

    std::wstring AnsiToWide(const char* text)
    {
        if (text == nullptr || text[0] == '\0')
            return L"";
        int length = MultiByteToWideChar(CP_ACP, 0, text, -1, nullptr, 0);
        std::wstring result;
        result.resize(length > 0 ? length - 1 : 0);
        if (length > 1)
            MultiByteToWideChar(CP_ACP, 0, text, -1, result.data(), length);
        return result;
    }

    std::wstring AnsiToWide(const char* text, int count)
    {
        if (text == nullptr)
            return L"";
        if (count < 0)
            return AnsiToWide(text);
        if (count == 0)
            return L"";

        int length = MultiByteToWideChar(CP_ACP, 0, text, count, nullptr, 0);
        std::wstring result;
        result.resize(length > 0 ? length : 0);
        if (length > 0)
            MultiByteToWideChar(CP_ACP, 0, text, count, result.data(), length);
        return result;
    }

    std::string WideToAnsi(const std::wstring& text)
    {
        if (text.empty())
            return "";
        int length = WideCharToMultiByte(CP_ACP, 0, text.c_str(), -1, nullptr, 0, nullptr, nullptr);
        std::string result;
        result.resize(length > 0 ? length - 1 : 0);
        if (length > 1)
            WideCharToMultiByte(CP_ACP, 0, text.c_str(), -1, result.data(), length, nullptr, nullptr);
        return result;
    }

    HFONT WINAPI CreateFontIndirectWHook(const LOGFONTW* pLogFont)
    {
        if (pLogFont == nullptr)
            return ::CreateFontIndirectW(nullptr);
        LOGFONTW font = *pLogFont;
        ApplyToLogFont(font);
        return ::CreateFontIndirectW(&font);
    }

    HFONT WINAPI CreateFontIndirectAHook(const LOGFONTA* pLogFont)
    {
        if (pLogFont == nullptr)
            return ::CreateFontIndirectA(nullptr);
        LOGFONTA font = *pLogFont;
        std::wstring originalFace = AnsiToWide(font.lfFaceName);
        if (MatchesFace(originalFace) && !ShouldSkipReplacement(originalFace, font.lfCharSet))
        {
            std::string replacement = WideToAnsi(g_config.DefaultFace);
            if (!replacement.empty())
            {
                strncpy_s(font.lfFaceName, replacement.c_str(), LF_FACESIZE - 1);
                font.lfFaceName[LF_FACESIZE - 1] = '\0';
            }
            font.lfCharSet = (BYTE)g_config.CharSet;
            font.lfQuality = (BYTE)g_config.Quality;
            font.lfHeight = AdjustSignedMetric(font.lfHeight, g_config.HeightPercent, 0);
            if (g_config.WidthPercent > 0 && g_config.WidthPercent != 100)
            {
                if (font.lfWidth != 0)
                    font.lfWidth = (font.lfWidth * g_config.WidthPercent) / 100;
                else if (font.lfHeight != 0)
                    font.lfWidth = max(1L, (labs(font.lfHeight) * g_config.WidthPercent) / 100);
            }
            if (g_config.LogFontCalls)
                Debugger::Log(L"FontPatch %ls -> %ls height=%ld width=%ld weight=%ld charset=%u quality=%u", originalFace.c_str(), g_config.DefaultFace.c_str(), font.lfHeight, font.lfWidth, font.lfWeight, font.lfCharSet, font.lfQuality);
        }
        else if (g_config.LogFontCalls)
        {
            Debugger::Log(L"FontPatch saw %ls height=%ld weight=%ld charset=%u quality=%u (pass-through)", originalFace.c_str(), font.lfHeight, font.lfWeight, font.lfCharSet, font.lfQuality);
        }
        return ::CreateFontIndirectA(&font);
    }

    HFONT WINAPI CreateFontWHook(
        int height,
        int width,
        int escapement,
        int orientation,
        int weight,
        DWORD italic,
        DWORD underline,
        DWORD strikeOut,
        DWORD charSet,
        DWORD outputPrecision,
        DWORD clipPrecision,
        DWORD quality,
        DWORD pitchAndFamily,
        LPCWSTR faceName)
    {
        std::wstring requested = faceName != nullptr ? faceName : L"";
        if (MatchesFace(requested) && !ShouldSkipReplacement(requested, charSet))
        {
            height = (int)AdjustSignedMetric(height, g_config.HeightPercent, 0);
            if (g_config.WidthPercent > 0 && g_config.WidthPercent != 100)
            {
                if (width != 0)
                    width = (width * g_config.WidthPercent) / 100;
                else if (height != 0)
                    width = max(1, (int)((labs(height) * g_config.WidthPercent) / 100));
            }
            charSet = g_config.CharSet;
            quality = g_config.Quality;
            faceName = g_config.DefaultFace.c_str();
            if (g_config.LogFontCalls)
                Debugger::Log(L"FontPatch %ls -> %ls height=%d width=%d weight=%d charset=%u quality=%u", requested.empty() ? L"<default>" : requested.c_str(), faceName, height, width, weight, charSet, quality);
        }
            else if (g_config.LogFontCalls)
            {
                Debugger::Log(L"FontPatch saw %ls height=%d weight=%d charset=%u quality=%u (pass-through)", requested.empty() ? L"<default>" : requested.c_str(), height, weight, charSet, quality);
            }

        return ::CreateFontW(height, width, escapement, orientation, weight, italic, underline, strikeOut, charSet, outputPrecision, clipPrecision, quality, pitchAndFamily, faceName);
    }

    HFONT WINAPI CreateFontAHook(
        int height,
        int width,
        int escapement,
        int orientation,
        int weight,
        DWORD italic,
        DWORD underline,
        DWORD strikeOut,
        DWORD charSet,
        DWORD outputPrecision,
        DWORD clipPrecision,
        DWORD quality,
        DWORD pitchAndFamily,
        LPCSTR faceName)
    {
        std::wstring requested = AnsiToWide(faceName);
        if (MatchesFace(requested) && !ShouldSkipReplacement(requested, charSet))
        {
            height = (int)AdjustSignedMetric(height, g_config.HeightPercent, 0);
            if (g_config.WidthPercent > 0 && g_config.WidthPercent != 100)
            {
                if (width != 0)
                    width = (width * g_config.WidthPercent) / 100;
                else if (height != 0)
                    width = max(1, (int)((labs(height) * g_config.WidthPercent) / 100));
            }
            charSet = g_config.CharSet;
            quality = g_config.Quality;
            std::string replacement = WideToAnsi(g_config.DefaultFace);
            faceName = replacement.c_str();
            if (g_config.LogFontCalls)
                Debugger::Log(L"FontPatch %ls -> %ls height=%d width=%d weight=%d charset=%u quality=%u", requested.empty() ? L"<default>" : requested.c_str(), g_config.DefaultFace.c_str(), height, width, weight, charSet, quality);
            return ::CreateFontA(height, width, escapement, orientation, weight, italic, underline, strikeOut, charSet, outputPrecision, clipPrecision, quality, pitchAndFamily, faceName);
        }
        else if (g_config.LogFontCalls)
        {
            Debugger::Log(L"FontPatch saw %ls height=%d weight=%d charset=%u quality=%u (pass-through)", requested.empty() ? L"<default>" : requested.c_str(), height, weight, charSet, quality);
        }

        return ::CreateFontA(height, width, escapement, orientation, weight, italic, underline, strikeOut, charSet, outputPrecision, clipPrecision, quality, pitchAndFamily, faceName);
    }

    int WINAPI SetTextCharacterExtraHook(HDC hdc, int extra)
    {
        int adjusted = extra;
        if (g_config.CharacterExtraPercent != 100 || g_config.CharacterExtraOffset != 0)
            adjusted = (extra * g_config.CharacterExtraPercent) / 100 + g_config.CharacterExtraOffset;

        if (g_config.LogFontCalls)
        {
            Debugger::Log(
                L"FontPatch character extra %d -> %d (percent=%d offset=%d)",
                extra,
                adjusted,
                g_config.CharacterExtraPercent,
                g_config.CharacterExtraOffset);
        }

        return ::SetTextCharacterExtra(hdc, adjusted);
    }

    HGDIOBJ WINAPI GetStockObjectHook(int i)
    {
        HGDIOBJ result = ::GetStockObject(i);
        if (i == SYSTEM_FONT)
        {
            g_systemFontHandle = result;
            if (g_config.LogFontCalls && !g_ansiTrace.GetStockObjectSystemFont)
            {
                g_ansiTrace.GetStockObjectSystemFont = true;
                Debugger::Log(L"FontPatch stock-font trace api=GetStockObject type=SYSTEM_FONT handle=%p", result);
            }
        }
        return result;
    }

    HGDIOBJ WINAPI SelectObjectHook(HDC hdc, HGDIOBJ h)
    {
        HGDIOBJ previous = ::SelectObject(hdc, h);
        if (GetObjectType(h) == OBJ_FONT || previous == GetSystemFontHandle())
            TraceStockFontSelection(L"SelectObject", hdc, h, previous);
        return previous;
    }

    HDC WINAPI CreateCompatibleDCHook(HDC hdc)
    {
        HDC result = ::CreateCompatibleDC(hdc);
        if (result != nullptr)
        {
            RegisterMemoryDc(result);
            TraceCompatibleDcHit(result, hdc);
        }
        return result;
    }

    BOOL WINAPI DeleteDCHook(HDC hdc)
    {
        g_memoryDcs.erase(hdc);
        return ::DeleteDC(hdc);
    }

    BOOL WINAPI DeleteObjectHook(HGDIOBJ ho)
    {
        if (GetObjectType(ho) == OBJ_DC)
            g_memoryDcs.erase((HDC)ho);
        return ::DeleteObject(ho);
    }

    BOOL WINAPI BitBltHook(HDC hdc, int x, int y, int cx, int cy, HDC hdcSrc, int x1, int y1, DWORD rop)
    {
        TraceBltHit(&g_ansiTrace.BitBlt, L"BitBlt", hdc, hdcSrc, cx, cy, rop);
        return ::BitBlt(hdc, x, y, cx, cy, hdcSrc, x1, y1, rop);
    }

    BOOL WINAPI StretchBltHook(HDC hdcDest, int xDest, int yDest, int wDest, int hDest, HDC hdcSrc, int xSrc, int ySrc, int wSrc, int hSrc, DWORD rop)
    {
        TraceBltHit(&g_ansiTrace.StretchBlt, L"StretchBlt", hdcDest, hdcSrc, wDest, hDest, rop);
        return ::StretchBlt(hdcDest, xDest, yDest, wDest, hDest, hdcSrc, xSrc, ySrc, wSrc, hSrc, rop);
    }

    BOOL WINAPI TextOutWHook(HDC hdc, int x, int y, LPCWSTR lpString, int c)
    {
        const std::wstring text = WideFromText(lpString, c);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"TextOutW");
        const BOOL result = ::TextOutW(hdc, x, y, lpString, c);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    BOOL WINAPI TextOutAHook(HDC hdc, int x, int y, LPCSTR lpString, int c)
    {
        const std::wstring text = AnsiToWide(lpString, c);
        TraceAnsiTextHit(&g_ansiTrace.TextOutA, L"TextOutA", hdc, text);
        TraceRefreshingMorningHit(L"TextOutA", hdc, text);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"TextOutA");
        const BOOL result = ::TextOutA(hdc, x, y, lpString, c);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    BOOL WINAPI ExtTextOutWHook(HDC hdc, int x, int y, UINT options, const RECT* lprect, LPCWSTR lpString, UINT c, const INT* lpDx)
    {
        const std::wstring text = WideFromText(lpString, (int)c);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"ExtTextOutW");
        const INT* adjustedDx = lpDx;
        std::vector<INT> scaledDx;
        if (lpDx != nullptr && c > 0 && g_config.AdvancePercent != 100)
        {
            scaledDx.assign(lpDx, lpDx + c);
            for (INT& value : scaledDx)
                value = (value * g_config.AdvancePercent) / 100;
            adjustedDx = scaledDx.data();
        }

        if (g_config.LogFontCalls && lpDx != nullptr && c > 1)
        {
            Debugger::Log(
                L"FontPatch ExtTextOutW count=%u advancePercent=%d dx=%ls -> %ls",
                c,
                g_config.AdvancePercent,
                PreviewDx(lpDx, c).c_str(),
                PreviewDx(adjustedDx, c).c_str());
        }

        const BOOL result = ::ExtTextOutW(hdc, x, y, options, lprect, lpString, c, adjustedDx);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    BOOL WINAPI ExtTextOutAHook(HDC hdc, int x, int y, UINT options, const RECT* lprect, LPCSTR lpString, UINT c, const INT* lpDx)
    {
        const std::wstring text = AnsiToWide(lpString, (int)c);
        TraceAnsiTextHit(&g_ansiTrace.ExtTextOutA, L"ExtTextOutA", hdc, text);
        TraceRefreshingMorningHit(L"ExtTextOutA", hdc, text);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"ExtTextOutA");
        const INT* adjustedDx = lpDx;
        std::vector<INT> scaledDx;
        if (lpDx != nullptr && c > 0 && g_config.AdvancePercent != 100)
        {
            scaledDx.assign(lpDx, lpDx + c);
            for (INT& value : scaledDx)
                value = (value * g_config.AdvancePercent) / 100;
            adjustedDx = scaledDx.data();
        }

        if (g_config.LogFontCalls && lpDx != nullptr && c > 1)
        {
            Debugger::Log(
                L"FontPatch ExtTextOutA count=%u advancePercent=%d dx=%ls -> %ls",
                c,
                g_config.AdvancePercent,
                PreviewDx(lpDx, c).c_str(),
                PreviewDx(adjustedDx, c).c_str());
        }

        const BOOL result = ::ExtTextOutA(hdc, x, y, options, lprect, lpString, c, adjustedDx);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    BOOL WINAPI GetTextExtentPointAHook(HDC hdc, LPCSTR lpString, int c, LPSIZE lpSize)
    {
        const std::wstring text = AnsiToWide(lpString, c);
        TraceAnsiTextHit(&g_ansiTrace.GetTextExtentPointA, L"GetTextExtentPointA", hdc, text);
        TraceRefreshingMorningHit(L"GetTextExtentPointA", hdc, text);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"GetTextExtentPointA");
        const BOOL result = ::GetTextExtentPointA(hdc, lpString, c, lpSize);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    BOOL WINAPI GetTextMetricsAHook(HDC hdc, LPTEXTMETRICA lptm)
    {
        TraceAnsiMetricHit(&g_ansiTrace.GetTextMetricsA, L"GetTextMetricsA", hdc);
        return ::GetTextMetricsA(hdc, lptm);
    }

    BOOL WINAPI GetTextExtentPoint32WHook(HDC hdc, LPCWSTR lpString, int c, LPSIZE lpSize)
    {
        const std::wstring text = WideFromText(lpString, c);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"GetTextExtentPoint32W");
        const BOOL result = ::GetTextExtentPoint32W(hdc, lpString, c, lpSize);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    BOOL WINAPI GetTextExtentPoint32AHook(HDC hdc, LPCSTR lpString, int c, LPSIZE lpSize)
    {
        const std::wstring text = AnsiToWide(lpString, c);
        TraceAnsiTextHit(&g_ansiTrace.GetTextExtentPoint32A, L"GetTextExtentPoint32A", hdc, text);
        TraceRefreshingMorningHit(L"GetTextExtentPoint32A", hdc, text);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"GetTextExtentPoint32A");
        const BOOL result = ::GetTextExtentPoint32A(hdc, lpString, c, lpSize);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    BOOL WINAPI GetTextExtentExPointWHook(HDC hdc, LPCWSTR lpszStr, int cchString, int nMaxExtent, LPINT lpnFit, LPINT alpDx, LPSIZE lpSize)
    {
        const std::wstring text = WideFromText(lpszStr, cchString);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"GetTextExtentExPointW");
        const BOOL result = ::GetTextExtentExPointW(hdc, lpszStr, cchString, nMaxExtent, lpnFit, alpDx, lpSize);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    BOOL WINAPI GetTextExtentExPointAHook(HDC hdc, LPCSTR lpszStr, int cchString, int nMaxExtent, LPINT lpnFit, LPINT alpDx, LPSIZE lpSize)
    {
        const std::wstring text = AnsiToWide(lpszStr, cchString);
        TraceAnsiTextHit(&g_ansiTrace.GetTextExtentExPointA, L"GetTextExtentExPointA", hdc, text);
        TraceRefreshingMorningHit(L"GetTextExtentExPointA", hdc, text);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"GetTextExtentExPointA");
        const BOOL result = ::GetTextExtentExPointA(hdc, lpszStr, cchString, nMaxExtent, lpnFit, alpDx, lpSize);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    int WINAPI DrawTextWHook(HDC hdc, LPCWSTR lpchText, int cchText, LPRECT lprc, UINT format)
    {
        const std::wstring text = WideFromText(lpchText, cchText);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"DrawTextW");
        const int result = ::DrawTextW(hdc, lpchText, cchText, lprc, format);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    int WINAPI DrawTextAHook(HDC hdc, LPCSTR lpchText, int cchText, LPRECT lprc, UINT format)
    {
        const std::wstring text = AnsiToWide(lpchText, cchText);
        TraceAnsiTextHit(&g_ansiTrace.DrawTextA, L"DrawTextA", hdc, text);
        TraceRefreshingMorningHit(L"DrawTextA", hdc, text);
        const FontOverrideState state = ApplyTextFontOverride(hdc, text, L"DrawTextA");
        const int result = ::DrawTextA(hdc, lpchText, cchText, lprc, format);
        RestoreTextFontOverride(hdc, state);
        return result;
    }

    DWORD WINAPI GetGlyphOutlineAHook(HDC hdc, UINT uChar, UINT fuFormat, LPGLYPHMETRICS lpgm, DWORD cjBuffer, LPVOID pvBuffer, const MAT2* lpmat2)
    {
        TraceAnsiGlyphHit(&g_ansiTrace.GetGlyphOutlineA, L"GetGlyphOutlineA", hdc, uChar, fuFormat);
        return ::GetGlyphOutlineA(hdc, uChar, fuFormat, lpgm, cjBuffer, pvBuffer, lpmat2);
    }

    bool PatchModuleImports(HMODULE hModule)
    {
        bool patched = false;
        patched = ImportHooker::Hook(hModule, "CreateCompatibleDC", (void*)CreateCompatibleDCHook) || patched;
        patched = ImportHooker::Hook(hModule, "DeleteDC", (void*)DeleteDCHook) || patched;
        patched = ImportHooker::Hook(hModule, "DeleteObject", (void*)DeleteObjectHook) || patched;
        patched = ImportHooker::Hook(hModule, "BitBlt", (void*)BitBltHook) || patched;
        patched = ImportHooker::Hook(hModule, "StretchBlt", (void*)StretchBltHook) || patched;
        patched = ImportHooker::Hook(hModule, "CreateFontA", (void*)CreateFontAHook) || patched;
        patched = ImportHooker::Hook(hModule, "CreateFontW", (void*)CreateFontWHook) || patched;
        patched = ImportHooker::Hook(hModule, "CreateFontIndirectA", (void*)CreateFontIndirectAHook) || patched;
        patched = ImportHooker::Hook(hModule, "CreateFontIndirectW", (void*)CreateFontIndirectWHook) || patched;
        patched = ImportHooker::Hook(hModule, "GetStockObject", (void*)GetStockObjectHook) || patched;
        patched = ImportHooker::Hook(hModule, "SelectObject", (void*)SelectObjectHook) || patched;
        patched = ImportHooker::Hook(hModule, "TextOutA", (void*)TextOutAHook) || patched;
        patched = ImportHooker::Hook(hModule, "TextOutW", (void*)TextOutWHook) || patched;
        patched = ImportHooker::Hook(hModule, "ExtTextOutA", (void*)ExtTextOutAHook) || patched;
        patched = ImportHooker::Hook(hModule, "ExtTextOutW", (void*)ExtTextOutWHook) || patched;
        patched = ImportHooker::Hook(hModule, "GetGlyphOutlineA", (void*)GetGlyphOutlineAHook) || patched;
        patched = ImportHooker::Hook(hModule, "GetTextExtentPointA", (void*)GetTextExtentPointAHook) || patched;
        patched = ImportHooker::Hook(hModule, "GetTextExtentPoint32A", (void*)GetTextExtentPoint32AHook) || patched;
        patched = ImportHooker::Hook(hModule, "GetTextExtentPoint32W", (void*)GetTextExtentPoint32WHook) || patched;
        patched = ImportHooker::Hook(hModule, "GetTextExtentExPointA", (void*)GetTextExtentExPointAHook) || patched;
        patched = ImportHooker::Hook(hModule, "GetTextExtentExPointW", (void*)GetTextExtentExPointWHook) || patched;
        patched = ImportHooker::Hook(hModule, "GetTextMetricsA", (void*)GetTextMetricsAHook) || patched;
        patched = ImportHooker::Hook(hModule, "DrawTextA", (void*)DrawTextAHook) || patched;
        patched = ImportHooker::Hook(hModule, "DrawTextW", (void*)DrawTextWHook) || patched;
        patched = ImportHooker::Hook(hModule, "SetTextCharacterExtra", (void*)SetTextCharacterExtraHook) || patched;
        if (patched && g_config.LogFontCalls)
            Debugger::Log(L"FontPatch hooked imports in %ls", Path::GetModuleFilePath(hModule).c_str());
        return patched;
    }
}

void FontPatch::Init()
{
    if (g_initialized)
        return;
    g_initialized = true;

    if (!LoadConfig())
        return;

    RegisterFontPath(g_config.RegularFontPath);
    RegisterFontPath(g_config.BoldFontPath);
    RegisterFontPath(g_config.LatinRegularFontPath);
    RegisterFontPath(g_config.LatinBoldFontPath);
    PatchModuleImports(GetModuleHandle(nullptr));
    Debugger::RegisterDllLoadHandler(
        [](const wchar_t* pwszDllPath, HMODULE hDll)
        {
            PatchModuleImports(hDll);
        });
    if (g_config.LogFontCalls)
        Debugger::Log(
            L"FontPatch active with cjk=%ls latin=%ls heightPercent=%d widthPercent=%d lineSpacingOffset=%d",
            g_config.DefaultFace.c_str(),
            HasLatinVariant() ? g_config.LatinFace.c_str() : L"<none>",
            g_config.HeightPercent,
            g_config.WidthPercent,
            g_config.LineSpacingOffsetPixels);
}

void FontPatch::Shutdown()
{
    for (const std::wstring& fontPath : g_config.RegisteredFontPaths)
        RemoveFontResourceExW(fontPath.c_str(), FONT_LOAD_FLAGS, nullptr);
    g_config = FontPatchConfig();
    g_initialized = false;
}