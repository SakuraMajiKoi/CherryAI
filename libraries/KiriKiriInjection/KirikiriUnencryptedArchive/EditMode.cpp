#include "stdafx.h"

using namespace std;

namespace
{
    constexpr wchar_t kIniName[] = L"kirikiri-patched.ini";
    constexpr wchar_t kEditModeSection[] = L"[editmode]";
    constexpr int kDialogWidth = 620;
    constexpr int kDialogHeight = 255;
    constexpr int kDialogMinHeight = 255;
    constexpr int kDialogEditLeft = 12;
    constexpr int kDialogEditTop = 66;
    constexpr int kDialogEditWidth = 580;
    constexpr int kDialogButtonYFromBottom = 55;
    constexpr int kDialogCurrentLabelHeight = 42;
    constexpr int kDialogCurrentLabelGap = 8;
    constexpr int kEditControlId = 1001;
    constexpr int kSaveButtonId = 1002;
    constexpr int kCancelButtonId = 1003;
    constexpr int kPrevButtonId = 1004;
    constexpr int kNextButtonId = 1005;
    constexpr int kInfoLabelId = 1006;
    constexpr int kCurrentLabelId = 1007;
    constexpr size_t kMaxHistoryEntries = 64;
    constexpr wchar_t kWildcardChar = 0x001F;
    constexpr wchar_t kHistorySeparator = 0x001E;
    constexpr wchar_t kHistorySeparatorText[] = L"<<<CherryAI.EditHistorySeparator>>>";
    constexpr wchar_t kLegacyEscapedHistorySeparatorText[] = L"\\u001e";
    constexpr UINT kOpenEditMessage = WM_APP + 0x432;
    constexpr wchar_t kDebugTextPrefix[] = L"[CherryAI.EditText] ";
    constexpr char kDebugTextPrefixA[] = "[CherryAI.EditText] ";

    struct EditConfig
    {
        bool loaded = false;
        bool enabled = false;
        wchar_t key = L'e';
        int virtualKey = 'E';
        bool hasWindowPosition = false;
        int windowX = CW_USEDEFAULT;
        int windowY = CW_USEDEFAULT;
        std::wstring iniPath;
    };

    struct HistoryEntry
    {
        std::wstring filePath;
        std::wstring displayPath;
        std::wstring renderedText;
        std::wstring lineText;
        size_t lineIndex = 0;
        size_t lineCount = 1;
        bool canEdit = false;
    };

    struct ScenarioState
    {
        std::wstring requestedName;
        std::wstring placedPath;
        std::wstring editableFilePath;
        std::wstring renderedText;
        std::wstring matchedFilePath;
        std::wstring matchedRenderedText;
        std::wstring matchedLineText;
        size_t matchedLineIndex = 0;
        size_t matchedLineCount = 1;
        bool hasMatchedLine = false;
        std::vector<HistoryEntry> history;
        DWORD lastHotkeyTick = 0;
        bool keyWasDown = false;
        bool dialogOpen = false;
        bool openRequestPending = false;
        HWND dialogHwnd = nullptr;
    };

    struct LineCache
    {
        std::wstring filePath;
        FILETIME lastWriteTime{};
        ULONGLONG size = 0;
        std::vector<std::wstring> lines;
    };

    struct LineMatch
    {
        bool found = false;
        size_t lineIndex = 0;
        size_t lineCount = 1;
        std::wstring lineText;
    };

    enum class TextEncoding
    {
        Utf8,
        Utf8Bom,
        Utf16Le,
        Cp932,
    };

    struct TextFileContent
    {
        std::wstring text;
        TextEncoding encoding = TextEncoding::Utf8;
    };

    EditConfig g_config;
    ScenarioState g_state;
    LineCache g_lineCache;
    std::mutex g_mutex;
    HANDLE g_shutdownEvent = nullptr;
    HANDLE g_hotkeyThread = nullptr;
    void (WINAPI* g_originalOutputDebugStringW)(LPCWSTR) = nullptr;
    void (WINAPI* g_originalOutputDebugStringA)(LPCSTR) = nullptr;
    bool g_debugHooksInstalled = false;
    HWND g_subclassedOwner = nullptr;
    WNDPROC g_originalOwnerWndProc = nullptr;

    std::wstring GetPatchRelativePath(const std::wstring& filePath);
    bool IsWritableFile(const std::wstring& filePath);
    bool IsEditableScenarioLine(const std::wstring& line);
    std::vector<std::wstring> SplitLinesPreserve(const std::wstring& text);

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

    bool StartsWithInsensitive(const std::wstring& value, const wchar_t* prefix)
    {
        const std::wstring lower = StringUtil::ToLower(value);
        const size_t prefixLength = wcslen(prefix);
        return lower.size() >= prefixLength && lower.compare(0, prefixLength, prefix) == 0;
    }

    bool IsKsName(const std::wstring& value)
    {
        const std::wstring lower = StringUtil::ToLower(value);
        return lower.size() >= 3 && lower.compare(lower.size() - 3, 3, L".ks") == 0;
    }

    std::wstring DecodeBytes(const BYTE* bytes, int length, UINT codePage, DWORD flags)
    {
        if (bytes == nullptr || length <= 0)
            return L"";

        int wideLength = MultiByteToWideChar(codePage, flags, reinterpret_cast<LPCCH>(bytes), length, nullptr, 0);
        if (wideLength <= 0)
            return L"";

        std::wstring result(wideLength, L'\0');
        MultiByteToWideChar(codePage, flags, reinterpret_cast<LPCCH>(bytes), length, result.data(), wideLength);
        return result;
    }

    std::string EncodeBytes(const std::wstring& text, UINT codePage)
    {
        if (text.empty())
            return "";

        int byteLength = WideCharToMultiByte(codePage, 0, text.c_str(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
        if (byteLength <= 0)
            return "";

        std::string result(byteLength, '\0');
        WideCharToMultiByte(codePage, 0, text.c_str(), static_cast<int>(text.size()), result.data(), byteLength, nullptr, nullptr);
        return result;
    }

    TextFileContent ReadTextFileWithEncoding(const std::wstring& filePath)
    {
        FILE* pFile = _wfopen(filePath.c_str(), L"rb");
        if (pFile == nullptr)
            return {};

        fseek(pFile, 0, SEEK_END);
        long size = ftell(pFile);
        fseek(pFile, 0, SEEK_SET);
        std::vector<BYTE> bytes(size > 0 ? size : 0);
        if (!bytes.empty())
            fread(bytes.data(), 1, bytes.size(), pFile);
        fclose(pFile);

        if (bytes.size() >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
            return { std::wstring(reinterpret_cast<const wchar_t*>(bytes.data() + 2), (bytes.size() - 2) / sizeof(wchar_t)), TextEncoding::Utf16Le };

        const bool hasUtf8Bom = bytes.size() >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF;
        const BYTE* payload = bytes.data() + (hasUtf8Bom ? 3 : 0);
        const int payloadLength = static_cast<int>(bytes.size() - (hasUtf8Bom ? 3 : 0));
        std::wstring utf8 = DecodeBytes(payload, payloadLength, CP_UTF8, MB_ERR_INVALID_CHARS);
        if (!utf8.empty() || payloadLength == 0)
            return { utf8, hasUtf8Bom ? TextEncoding::Utf8Bom : TextEncoding::Utf8 };

        return { DecodeBytes(bytes.data(), static_cast<int>(bytes.size()), 932, 0), TextEncoding::Cp932 };
    }

    std::wstring ReadTextFile(const std::wstring& filePath)
    {
        return ReadTextFileWithEncoding(filePath).text;
    }

    bool WriteTextFile(const std::wstring& filePath, const std::wstring& text)
    {
        FILE* pFile = _wfopen(filePath.c_str(), L"wb");
        if (pFile == nullptr)
            return false;

        const std::string utf8 = StringUtil::ToUTF8(text);
        const bool ok = utf8.empty() || fwrite(utf8.data(), 1, utf8.size(), pFile) == utf8.size();
        fclose(pFile);
        return ok;
    }

    bool WriteTextFileWithEncoding(const std::wstring& filePath, const std::wstring& text, TextEncoding encoding)
    {
        FILE* pFile = _wfopen(filePath.c_str(), L"wb");
        if (pFile == nullptr)
            return false;

        bool ok = true;
        if (encoding == TextEncoding::Utf16Le)
        {
            const BYTE bom[] = { 0xFF, 0xFE };
            ok = fwrite(bom, 1, sizeof(bom), pFile) == sizeof(bom);
            if (ok && !text.empty())
                ok = fwrite(text.data(), sizeof(wchar_t), text.size(), pFile) == text.size();
        }
        else
        {
            std::string bytes = EncodeBytes(text, encoding == TextEncoding::Cp932 ? 932 : CP_UTF8);
            if (encoding == TextEncoding::Utf8Bom)
            {
                const BYTE bom[] = { 0xEF, 0xBB, 0xBF };
                ok = fwrite(bom, 1, sizeof(bom), pFile) == sizeof(bom);
            }
            if (ok && !bytes.empty())
                ok = fwrite(bytes.data(), 1, bytes.size(), pFile) == bytes.size();
        }

        fclose(pFile);
        return ok;
    }

    std::wstring ReadIniText(const std::wstring& iniPath)
    {
        std::wstring text = ReadTextFile(iniPath);
        return text;
    }

    void EnsureEditModeIniSection(const std::wstring& iniPath)
    {
        std::wstring text = ReadIniText(iniPath);
        if (text.find(kEditModeSection) != std::wstring::npos || text.find(L"[EditMode]") != std::wstring::npos)
            return;

        if (!text.empty() && text.back() != L'\n')
            text += L"\n";
        text += L"\n[editmode]\n";
        text += L"enabled = false\n";
        text += L"key = e\n";
        WriteTextFile(iniPath, text);
    }

    std::wstring ReadIniValue(const std::wstring& text, const std::wstring& section, const std::wstring& key, const std::wstring& fallback)
    {
        std::wistringstream stream(text);
        std::wstring line;
        bool inSection = false;
        const std::wstring targetSection = StringUtil::ToLower(section);
        const std::wstring targetKey = StringUtil::ToLower(key);

        while (std::getline(stream, line))
        {
            std::wstring trimmed = TrimAsciiWhitespace(line);
            if (trimmed.empty() || trimmed[0] == L';' || trimmed[0] == L'#')
                continue;

            if (trimmed.front() == L'[' && trimmed.back() == L']')
            {
                inSection = StringUtil::ToLower(trimmed.substr(1, trimmed.size() - 2)) == targetSection;
                continue;
            }

            if (!inSection)
                continue;

            size_t equals = trimmed.find(L'=');
            if (equals == std::wstring::npos)
                continue;

            std::wstring name = StringUtil::ToLower(TrimAsciiWhitespace(trimmed.substr(0, equals)));
            if (name != targetKey)
                continue;

            return TrimAsciiWhitespace(trimmed.substr(equals + 1));
        }

        return fallback;
    }

    std::wstring GetWritableEditModeIniPath(const std::wstring& moduleRoot)
    {
        const std::wstring patchIniPath = Path::Combine(Path::Combine(moduleRoot, L"patch"), kIniName);
        if (!ReadTextFile(patchIniPath).empty())
            return patchIniPath;
        return Path::Combine(moduleRoot, kIniName);
    }

    void WriteIniValue(const std::wstring& iniPath, const std::wstring& section, const std::wstring& key, const std::wstring& value)
    {
        std::wstring text = ReadIniText(iniPath);
        std::vector<std::wstring> lines = SplitLinesPreserve(text);
        const std::wstring targetSection = StringUtil::ToLower(section);
        const std::wstring targetKey = StringUtil::ToLower(key);
        bool inSection = false;
        bool foundSection = false;
        bool wroteKey = false;
        size_t insertIndex = lines.size();

        for (size_t i = 0; i < lines.size(); i++)
        {
            std::wstring trimmed = TrimAsciiWhitespace(lines[i]);
            if (trimmed.size() >= 2 && trimmed.front() == L'[' && trimmed.back() == L']')
            {
                if (inSection && !wroteKey)
                    insertIndex = i;
                inSection = StringUtil::ToLower(trimmed.substr(1, trimmed.size() - 2)) == targetSection;
                foundSection = foundSection || inSection;
                continue;
            }

            if (!inSection)
                continue;

            size_t equals = trimmed.find(L'=');
            if (equals == std::wstring::npos)
                continue;

            if (StringUtil::ToLower(TrimAsciiWhitespace(trimmed.substr(0, equals))) == targetKey)
            {
                lines[i] = key + L" = " + value + L"\n";
                wroteKey = true;
                break;
            }
        }

        if (!wroteKey)
        {
            if (!foundSection)
            {
                if (!lines.empty() && !lines.back().empty() && lines.back().back() != L'\n')
                    lines.back() += L"\n";
                lines.push_back(L"\n[editmode]\n");
                insertIndex = lines.size();
            }
            else if (insertIndex == lines.size() && !lines.empty() && !lines.back().empty() && lines.back().back() != L'\n')
            {
                lines.back() += L"\n";
            }
            lines.insert(lines.begin() + insertIndex, key + L" = " + value + L"\n");
        }

        std::wstring updated;
        for (const std::wstring& line : lines)
            updated += line;
        WriteTextFile(iniPath, updated);
    }

    int KeyToVirtualKey(const std::wstring& value)
    {
        if (value.empty())
            return 'E';

        wchar_t ch = value[0];
        if (ch >= L'a' && ch <= L'z')
            ch = static_cast<wchar_t>(towupper(ch));
        if ((ch >= L'A' && ch <= L'Z') || (ch >= L'0' && ch <= L'9'))
            return static_cast<int>(ch);

        return VkKeyScanW(ch) & 0xff;
    }

    std::wstring AnsiToWide(const char* text)
    {
        if (text == nullptr)
            return L"";

        int length = static_cast<int>(strlen(text));
        if (length <= 0)
            return L"";

        int wideLength = MultiByteToWideChar(CP_ACP, 0, text, length, nullptr, 0);
        if (wideLength <= 0)
            return StringUtil::ToUTF16(text);

        std::wstring result(wideLength, L'\0');
        MultiByteToWideChar(CP_ACP, 0, text, length, result.data(), wideLength);
        return result;
    }

    std::wstring PreferPatchIniText(const std::wstring& moduleRoot)
    {
        const std::wstring patchIniPath = Path::Combine(Path::Combine(moduleRoot, L"patch"), kIniName);
        std::wstring patchText = ReadIniText(patchIniPath);
        if (!patchText.empty())
            return patchText;

        return ReadIniText(Path::Combine(moduleRoot, kIniName));
    }

    void LoadConfig()
    {
        if (g_config.loaded)
            return;

        g_config.loaded = true;
        const std::wstring moduleRoot = Path::GetModuleFolderPath(nullptr);
        EnsureEditModeIniSection(Path::Combine(moduleRoot, kIniName));
        EnsureEditModeIniSection(Path::Combine(Path::Combine(moduleRoot, L"patch"), kIniName));
        g_config.iniPath = GetWritableEditModeIniPath(moduleRoot);
        const std::wstring text = PreferPatchIniText(moduleRoot);

        const std::wstring enabled = StringUtil::ToLower(ReadIniValue(text, L"editmode", L"enabled", L"false"));
        const std::wstring key = ReadIniValue(text, L"editmode", L"key", L"e");
        const std::wstring windowX = ReadIniValue(text, L"editmode", L"window_x", L"");
        const std::wstring windowY = ReadIniValue(text, L"editmode", L"window_y", L"");
        g_config.enabled = enabled == L"true" || enabled == L"1" || enabled == L"yes" || enabled == L"on";
        g_config.key = key.empty() ? L'e' : key[0];
        g_config.virtualKey = KeyToVirtualKey(key);
        if (!windowX.empty() && !windowY.empty())
        {
            g_config.windowX = _wtoi(windowX.c_str());
            g_config.windowY = _wtoi(windowY.c_str());
            g_config.hasWindowPosition = true;
        }
        Debugger::Log(L"EditMode config enabled=%s key=%c vk=%d", g_config.enabled ? L"true" : L"false", g_config.key, g_config.virtualKey);
    }

    bool IsZeroWidthOrControl(wchar_t ch)
    {
        return ch < 0x20 ||
            ch == 0x200B ||
            ch == 0x200C ||
            ch == 0x200D ||
            ch == 0x2060 ||
            ch == 0xFEFF;
    }

    bool IsPlaceholderName(const std::wstring& token)
    {
        if (token.empty() || token.size() > 16)
            return false;

        bool hasLetter = false;
        for (wchar_t ch : token)
        {
            if (ch >= L'A' && ch <= L'Z')
            {
                hasLetter = true;
                continue;
            }
            if (ch >= L'0' && ch <= L'9')
                continue;
            if (ch == L'_')
                continue;
            return false;
        }
        return hasLetter;
    }

    void AppendNormalizedSpace(std::wstring& out, bool& previousSpace)
    {
        if (!previousSpace && !out.empty())
            out.push_back(L' ');
        previousSpace = true;
    }

    std::wstring NormalizeSearchText(const std::wstring& value, bool scriptPattern)
    {
        std::wstring out;
        out.reserve(value.size());
        bool previousSpace = false;

        for (size_t i = 0; i < value.size(); i++)
        {
            wchar_t ch = value[i];
            if (IsZeroWidthOrControl(ch))
                continue;

            if (ch == L'[')
            {
                size_t close = value.find(L']', i + 1);
                if (close != std::wstring::npos)
                {
                    std::wstring token = value.substr(i + 1, close - i - 1);
                    if (scriptPattern && IsPlaceholderName(token))
                    {
                        AppendNormalizedSpace(out, previousSpace);
                        out.push_back(kWildcardChar);
                        previousSpace = false;
                        AppendNormalizedSpace(out, previousSpace);
                    }
                    i = close;
                    continue;
                }
            }

            if (ch == 0x2018 || ch == 0x2019 || ch == 0x02BC || ch == 0xFF07)
                ch = L'\'';
            else if (ch == 0x201C || ch == 0x201D || ch == L'"')
                continue;

            if (iswspace(ch))
            {
                AppendNormalizedSpace(out, previousSpace);
                continue;
            }
            previousSpace = false;
            out.push_back(ch);
        }

        return StringUtil::ToLower(TrimAsciiWhitespace(out));
    }

    std::vector<std::wstring> SplitWildcardPattern(const std::wstring& pattern)
    {
        std::vector<std::wstring> parts;
        size_t start = 0;
        while (start <= pattern.size())
        {
            size_t pos = pattern.find(kWildcardChar, start);
            std::wstring part = TrimAsciiWhitespace(pattern.substr(start, pos == std::wstring::npos ? std::wstring::npos : pos - start));
            if (!part.empty())
                parts.push_back(part);
            if (pos == std::wstring::npos)
                break;
            start = pos + 1;
        }
        return parts;
    }

    bool WildcardPatternMatches(const std::wstring& pattern, const std::wstring& rendered)
    {
        if (pattern.find(kWildcardChar) == std::wstring::npos)
            return pattern == rendered;

        const std::vector<std::wstring> parts = SplitWildcardPattern(pattern);
        if (parts.empty())
            return false;

        size_t pos = 0;
        for (size_t i = 0; i < parts.size(); i++)
        {
            size_t found = rendered.find(parts[i], pos);
            if (found == std::wstring::npos)
                return false;
            if (i == 0 && pattern.front() != kWildcardChar && found != 0)
                return false;
            pos = found + parts[i].size();
        }

        if (pattern.back() != kWildcardChar && pos != rendered.size())
            return false;
        return true;
    }

    std::vector<std::wstring> SplitLinesPreserve(const std::wstring& text)
    {
        std::vector<std::wstring> lines;
        size_t start = 0;
        while (start <= text.size())
        {
            size_t end = text.find(L'\n', start);
            if (end == std::wstring::npos)
            {
                lines.push_back(text.substr(start));
                break;
            }
            lines.push_back(text.substr(start, end - start + 1));
            start = end + 1;
        }
        return lines;
    }

    bool GetFileStamp(const std::wstring& filePath, FILETIME& lastWriteTime, ULONGLONG& size)
    {
        WIN32_FILE_ATTRIBUTE_DATA attrs{};
        if (!GetFileAttributesExW(filePath.c_str(), GetFileExInfoStandard, &attrs))
            return false;

        lastWriteTime = attrs.ftLastWriteTime;
        ULARGE_INTEGER fileSize{};
        fileSize.HighPart = attrs.nFileSizeHigh;
        fileSize.LowPart = attrs.nFileSizeLow;
        size = fileSize.QuadPart;
        return true;
    }

    const std::vector<std::wstring>& GetCachedLines(const std::wstring& filePath)
    {
        FILETIME lastWriteTime{};
        ULONGLONG size = 0;
        if (!GetFileStamp(filePath, lastWriteTime, size))
        {
            g_lineCache = LineCache();
            return g_lineCache.lines;
        }

        if (g_lineCache.filePath == filePath &&
            CompareFileTime(&g_lineCache.lastWriteTime, &lastWriteTime) == 0 &&
            g_lineCache.size == size)
        {
            return g_lineCache.lines;
        }

        g_lineCache.filePath = filePath;
        g_lineCache.lastWriteTime = lastWriteTime;
        g_lineCache.size = size;
        g_lineCache.lines = SplitLinesPreserve(ReadTextFile(filePath));
        return g_lineCache.lines;
    }

    LineMatch FindLine(const std::vector<std::wstring>& lines, const std::wstring& renderedText)
    {
        const std::wstring needle = NormalizeSearchText(renderedText, false);
        if (needle.empty())
            return {};

        for (size_t i = 0; i < lines.size(); i++)
        {
            const std::wstring normalizedLine = NormalizeSearchText(lines[i], true);
            if (normalizedLine.empty())
                continue;
            if (WildcardPatternMatches(normalizedLine, needle))
                return { true, i, 1, TrimAsciiWhitespace(lines[i]) };
        }

        constexpr size_t maxJoinedLines = 8;
        for (size_t i = 0; i < lines.size(); i++)
        {
            if (!IsEditableScenarioLine(lines[i]))
                continue;

            std::wstring joined;
            std::wstring original;
            for (size_t count = 1; count <= maxJoinedLines && i + count - 1 < lines.size(); count++)
            {
                const std::wstring& line = lines[i + count - 1];
                if (!IsEditableScenarioLine(line))
                    break;

                if (!joined.empty())
                    joined += L"\n";
                if (!original.empty())
                    original += L"\r\n";
                joined += line;
                original += TrimAsciiWhitespace(line);

                if (WildcardPatternMatches(NormalizeSearchText(joined, true), needle))
                    return { true, i, count, original };
            }
        }

        return {};
    }

    bool IsEditableScenarioLine(const std::wstring& line)
    {
        std::wstring trimmed = TrimAsciiWhitespace(line);
        if (trimmed.empty())
            return false;

        const wchar_t first = trimmed[0];
        return first != L';' && first != L'*' && first != L'@' && first != L'[';
    }

    LineMatch FindFirstEditableLine(const std::vector<std::wstring>& lines)
    {
        for (size_t i = 0; i < lines.size(); i++)
        {
            if (IsEditableScenarioLine(lines[i]))
                return { true, i, 1, TrimAsciiWhitespace(lines[i]) };
        }

        return {};
    }

    bool IsDialogueScriptPath(const std::wstring& filePath)
    {
        const std::wstring normalized = StringUtil::ToLower(StringUtil::Replace(filePath, L'\\', L'/'));
        return normalized.find(L"/kano2scr/") != std::wstring::npos;
    }

    HistoryEntry MakeHistoryEntry(const std::wstring& filePath, const std::wstring& renderedText, const LineMatch& match)
    {
        HistoryEntry entry;
        entry.filePath = filePath;
        entry.displayPath = GetPatchRelativePath(filePath);
        entry.renderedText = renderedText;
        entry.lineText = match.lineText;
        entry.lineIndex = match.lineIndex;
        entry.lineCount = match.lineCount;
        entry.canEdit = IsWritableFile(filePath);
        return entry;
    }

    void PushHistoryEntry(const HistoryEntry& entry)
    {
        if (entry.filePath.empty() || entry.lineText.empty())
            return;

        auto sameLine = [&](const HistoryEntry& existing)
        {
            return existing.filePath == entry.filePath && existing.lineIndex == entry.lineIndex;
        };

        if (!g_state.history.empty() && sameLine(g_state.history.back()))
        {
            g_state.history.back() = entry;
            return;
        }

        g_state.history.erase(
            std::remove_if(g_state.history.begin(), g_state.history.end(), sameLine),
            g_state.history.end());
        g_state.history.push_back(entry);

        if (g_state.history.size() > kMaxHistoryEntries)
            g_state.history.erase(g_state.history.begin(), g_state.history.begin() + (g_state.history.size() - kMaxHistoryEntries));
    }

    void SetFallbackMatchedLine(const std::wstring& filePath)
    {
        if (filePath.empty() || !IsDialogueScriptPath(filePath))
            return;

        LineMatch match;
        {
            lock_guard<mutex> lock(g_mutex);
            match = FindFirstEditableLine(GetCachedLines(filePath));
            if (!match.found)
                return;

            g_state.matchedFilePath = filePath;
            g_state.matchedRenderedText = match.lineText;
            g_state.matchedLineText = match.lineText;
            g_state.matchedLineIndex = match.lineIndex;
            g_state.matchedLineCount = match.lineCount;
            g_state.hasMatchedLine = true;
        }

        Debugger::Log(
            L"EditMode fallback line file=%s line=%u text=%s",
            filePath.c_str(),
            static_cast<unsigned>(match.lineIndex + 1),
            match.lineText.c_str());
    }

    bool TryUpdateMatchedLine(const std::wstring& renderedText)
    {
        std::wstring filePath;
        {
            lock_guard<mutex> lock(g_mutex);
            filePath = g_state.editableFilePath;
        }

        if (filePath.empty() || renderedText.empty())
            return false;

        LineMatch match;
        bool changed = false;
        {
            lock_guard<mutex> lock(g_mutex);
            match = FindLine(GetCachedLines(filePath), renderedText);
            if (!match.found)
                return false;

            changed =
                !g_state.hasMatchedLine ||
                g_state.matchedFilePath != filePath ||
                g_state.matchedLineIndex != match.lineIndex ||
                g_state.matchedLineCount != match.lineCount ||
                g_state.matchedLineText != match.lineText;
            g_state.matchedFilePath = filePath;
            g_state.matchedRenderedText = renderedText;
            g_state.matchedLineText = match.lineText;
            g_state.matchedLineIndex = match.lineIndex;
            g_state.matchedLineCount = match.lineCount;
            g_state.hasMatchedLine = true;
            PushHistoryEntry(MakeHistoryEntry(filePath, renderedText, match));
        }

        if (changed)
        {
            Debugger::Log(
                L"EditMode current line file=%s line=%u rendered=%s text=%s",
                filePath.c_str(),
                static_cast<unsigned>(match.lineIndex + 1),
                renderedText.c_str(),
                match.lineText.c_str());
        }

        return true;
    }

    void UpdateCurrentTextFromScript(const std::wstring& text)
    {
        const std::wstring trimmed = TrimAsciiWhitespace(text);
        if (trimmed.empty())
            return;

        {
            lock_guard<mutex> lock(g_mutex);
            g_state.renderedText = trimmed;
        }

        TryUpdateMatchedLine(trimmed);
    }

    std::wstring QueryScriptCurrentText()
    {
        if (Kirikiri::TVPExecuteExpression == nullptr)
            return L"";

        try
        {
            tTJSVariant result;
            Kirikiri::TVPExecuteExpression(
                ttstr(L"(global.CherryAIEditCurrentText !== void) ? global.CherryAIEditCurrentText : \"\""),
                &result);
            return TrimAsciiWhitespace(result.AsString());
        }
        catch (...)
        {
            Debugger::Log(L"EditMode failed to query global.CherryAIEditCurrentText");
            return L"";
        }
    }

    struct HistorySeparatorMatch
    {
        size_t pos = std::wstring::npos;
        size_t length = 0;
    };

    void ConsiderHistorySeparator(const std::wstring& text, size_t start, const std::wstring& separator, HistorySeparatorMatch& best)
    {
        if (separator.empty())
            return;

        const size_t pos = text.find(separator, start);
        if (pos != std::wstring::npos && (best.pos == std::wstring::npos || pos < best.pos))
        {
            best.pos = pos;
            best.length = separator.size();
        }
    }

    HistorySeparatorMatch FindNextHistorySeparator(const std::wstring& text, size_t start)
    {
        HistorySeparatorMatch best;
        ConsiderHistorySeparator(text, start, std::wstring(1, kHistorySeparator), best);
        ConsiderHistorySeparator(text, start, kHistorySeparatorText, best);
        ConsiderHistorySeparator(text, start, kLegacyEscapedHistorySeparatorText, best);
        return best;
    }

    std::vector<std::wstring> SplitHistoryText(const std::wstring& text)
    {
        std::vector<std::wstring> entries;
        size_t start = 0;
        while (start <= text.size())
        {
            const HistorySeparatorMatch separator = FindNextHistorySeparator(text, start);
            std::wstring entry = TrimAsciiWhitespace(text.substr(start, separator.pos == std::wstring::npos ? std::wstring::npos : separator.pos - start));
            if (!entry.empty())
                entries.push_back(entry);
            if (separator.pos == std::wstring::npos)
                break;
            start = separator.pos + separator.length;
        }
        return entries;
    }

    std::vector<std::wstring> QueryScriptTextHistory()
    {
        if (Kirikiri::TVPExecuteExpression == nullptr)
            return {};

        try
        {
            tTJSVariant result;
            Kirikiri::TVPExecuteExpression(
                ttstr(L"(global.CherryAIEditTextHistory !== void) ? global.CherryAIEditTextHistory : \"\""),
                &result);
            return SplitHistoryText(result.AsString());
        }
        catch (...)
        {
            Debugger::Log(L"EditMode failed to query global.CherryAIEditTextHistory");
            return {};
        }
    }

    void RefreshHistoryFromScriptGlobal()
    {
        const std::vector<std::wstring> entries = QueryScriptTextHistory();
        size_t matched = 0;
        for (const std::wstring& text : entries)
        {
            if (TryUpdateMatchedLine(text))
                matched++;
        }

        if (!entries.empty())
        {
            size_t total = 0;
            {
                lock_guard<mutex> lock(g_mutex);
                total = g_state.history.size();
            }
            Debugger::Log(
                L"EditMode imported script history entries=%u matched=%u total=%u",
                static_cast<unsigned>(entries.size()),
                static_cast<unsigned>(matched),
                static_cast<unsigned>(total));
        }
    }

    void RefreshCurrentTextFromScriptGlobal()
    {
        const std::wstring text = QueryScriptCurrentText();
        if (!text.empty())
            UpdateCurrentTextFromScript(text);
    }

    void BackfillHistoryBeforeMatchedLine()
    {
        constexpr size_t kBackfillEntries = 24;
        std::vector<HistoryEntry> previousEntries;
        HistoryEntry currentEntry;
        bool hasCurrent = false;
        size_t total = 0;

        {
            lock_guard<mutex> lock(g_mutex);
            if (!g_state.hasMatchedLine || g_state.matchedFilePath.empty())
                return;

            const std::vector<std::wstring>& lines = GetCachedLines(g_state.matchedFilePath);
            if (g_state.matchedLineIndex >= lines.size())
                return;

            LineMatch currentMatch;
            currentMatch.found = true;
            currentMatch.lineIndex = g_state.matchedLineIndex;
            currentMatch.lineCount = g_state.matchedLineCount;
            currentMatch.lineText = g_state.matchedLineText;
            currentEntry = MakeHistoryEntry(g_state.matchedFilePath, g_state.matchedRenderedText, currentMatch);
            hasCurrent = true;

            for (size_t i = g_state.matchedLineIndex; i > 0 && previousEntries.size() < kBackfillEntries;)
            {
                i--;
                if (!IsEditableScenarioLine(lines[i]))
                    continue;

                LineMatch match;
                match.found = true;
                match.lineIndex = i;
                match.lineCount = 1;
                match.lineText = TrimAsciiWhitespace(lines[i]);
                previousEntries.push_back(MakeHistoryEntry(g_state.matchedFilePath, match.lineText, match));
            }

            for (auto it = previousEntries.rbegin(); it != previousEntries.rend(); ++it)
                PushHistoryEntry(*it);
            if (hasCurrent)
                PushHistoryEntry(currentEntry);
            total = g_state.history.size();
        }

        if (!previousEntries.empty())
        {
            Debugger::Log(
                L"EditMode backfilled nearby history entries=%u total=%u",
                static_cast<unsigned>(previousEntries.size()),
                static_cast<unsigned>(total));
        }
    }

    bool HasEditableDialogueScenario()
    {
        lock_guard<mutex> lock(g_mutex);
        return IsDialogueScriptPath(g_state.editableFilePath);
    }

    void WINAPI OutputDebugStringWHook(LPCWSTR text)
    {
        if (text != nullptr)
        {
            std::wstring message(text);
            if (message.rfind(kDebugTextPrefix, 0) == 0)
                UpdateCurrentTextFromScript(message.substr(wcslen(kDebugTextPrefix)));
        }

        if (g_originalOutputDebugStringW != nullptr)
            g_originalOutputDebugStringW(text);
    }

    void WINAPI OutputDebugStringAHook(LPCSTR text)
    {
        if (text != nullptr && strncmp(text, kDebugTextPrefixA, strlen(kDebugTextPrefixA)) == 0)
            UpdateCurrentTextFromScript(AnsiToWide(text + strlen(kDebugTextPrefixA)));

        if (g_originalOutputDebugStringA != nullptr)
            g_originalOutputDebugStringA(text);
    }

    void InstallDebugStringHooks()
    {
        if (g_debugHooksInstalled)
            return;

        HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
        if (kernel32 == nullptr)
            return;

        g_originalOutputDebugStringW = reinterpret_cast<decltype(g_originalOutputDebugStringW)>(GetProcAddress(kernel32, "OutputDebugStringW"));
        g_originalOutputDebugStringA = reinterpret_cast<decltype(g_originalOutputDebugStringA)>(GetProcAddress(kernel32, "OutputDebugStringA"));

        DetourTransactionBegin();
        if (g_originalOutputDebugStringW != nullptr)
            DetourAttach(reinterpret_cast<void**>(&g_originalOutputDebugStringW), OutputDebugStringWHook);
        if (g_originalOutputDebugStringA != nullptr)
            DetourAttach(reinterpret_cast<void**>(&g_originalOutputDebugStringA), OutputDebugStringAHook);
        LONG result = DetourTransactionCommit();
        g_debugHooksInstalled = result == NO_ERROR;
        Debugger::Log(L"EditMode OutputDebugString hooks result=%ld", result);
    }

    std::wstring GetPatchRelativePath(const std::wstring& filePath)
    {
        if (filePath.empty())
            return L"";

        const std::wstring patchRoot = Path::GetFullPath(Path::Combine(Path::GetModuleFolderPath(nullptr), L"patch"));
        const std::wstring fullPath = Path::GetFullPath(filePath);
        const std::wstring lowerRoot = StringUtil::ToLower(StringUtil::Replace(patchRoot, L'/', L'\\'));
        const std::wstring lowerPath = StringUtil::ToLower(StringUtil::Replace(fullPath, L'/', L'\\'));

        if (lowerPath.size() > lowerRoot.size() &&
            lowerPath.compare(0, lowerRoot.size(), lowerRoot) == 0 &&
            (lowerPath[lowerRoot.size()] == L'\\' || lowerPath[lowerRoot.size()] == L'/'))
        {
            return L"\\" + fullPath.substr(patchRoot.size() + 1);
        }

        return fullPath;
    }

    bool IsWritableFile(const std::wstring& filePath)
    {
        DWORD attrs = GetFileAttributesW(filePath.c_str());
        if (attrs == INVALID_FILE_ATTRIBUTES || (attrs & FILE_ATTRIBUTE_DIRECTORY) != 0 || (attrs & FILE_ATTRIBUTE_READONLY) != 0)
            return false;

        HANDLE hFile = CreateFileW(filePath.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (hFile == INVALID_HANDLE_VALUE)
            return false;
        CloseHandle(hFile);
        return true;
    }

    HWND FindOwnerWindow()
    {
        HWND foreground = GetForegroundWindow();
        if (foreground != nullptr)
        {
            DWORD foregroundProcessId = 0;
            GetWindowThreadProcessId(foreground, &foregroundProcessId);
            if (foregroundProcessId == GetCurrentProcessId() && IsWindowVisible(foreground))
                return foreground;
        }

        HWND found = nullptr;
        EnumWindows(
            [](HWND hwnd, LPARAM param) -> BOOL
            {
                DWORD windowProcessId = 0;
                GetWindowThreadProcessId(hwnd, &windowProcessId);
                if (windowProcessId == GetCurrentProcessId() && IsWindowVisible(hwnd))
                {
                    *reinterpret_cast<HWND*>(param) = hwnd;
                    return FALSE;
                }
                return TRUE;
            },
            reinterpret_cast<LPARAM>(&found));
        return found;
    }

    void OpenDialog();

    LRESULT CALLBACK OwnerWindowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam)
    {
        if (message == kOpenEditMessage)
        {
            {
                lock_guard<mutex> lock(g_mutex);
                g_state.openRequestPending = false;
            }
            Debugger::Log(L"EditMode open request received on owner window");
            OpenDialog();
            return 0;
        }

        return CallWindowProcW(g_originalOwnerWndProc, hwnd, message, wParam, lParam);
    }

    bool EnsureOwnerSubclass(HWND hwnd)
    {
        if (hwnd == nullptr)
            return false;

        if (g_subclassedOwner == hwnd && g_originalOwnerWndProc != nullptr)
            return true;

        if (g_subclassedOwner != nullptr && g_originalOwnerWndProc != nullptr && IsWindow(g_subclassedOwner))
            SetWindowLongPtrW(g_subclassedOwner, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(g_originalOwnerWndProc));

        g_originalOwnerWndProc = reinterpret_cast<WNDPROC>(SetWindowLongPtrW(hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(OwnerWindowProc)));
        g_subclassedOwner = g_originalOwnerWndProc != nullptr ? hwnd : nullptr;
        Debugger::Log(L"EditMode owner subclass hwnd=%p original=%p", hwnd, g_originalOwnerWndProc);
        return g_originalOwnerWndProc != nullptr;
    }

    void RequestOpenDialogOnOwnerThread()
    {
        HWND owner = FindOwnerWindow();
        if (owner == nullptr)
        {
            Debugger::Log(L"EditMode open request ignored: no owner window");
            return;
        }

        {
            lock_guard<mutex> lock(g_mutex);
            if (g_state.dialogOpen || g_state.openRequestPending)
                return;
            g_state.openRequestPending = true;
        }

        if (!EnsureOwnerSubclass(owner) || !PostMessageW(owner, kOpenEditMessage, 0, 0))
        {
            lock_guard<mutex> lock(g_mutex);
            g_state.openRequestPending = false;
            Debugger::Log(L"EditMode open request failed hwnd=%p", owner);
        }
    }

    struct DialogContext
    {
        std::wstring filePath;
        std::wstring requestedName;
        std::wstring placedPath;
        std::wstring renderedText;
        std::wstring originalLine;
        size_t lineIndex = 0;
        size_t lineCount = 1;
        bool canEdit = false;
        bool saved = false;
        bool useMatchedLine = false;
        std::wstring status;
        std::wstring displayPath;
        std::vector<HistoryEntry> history;
        size_t historyIndex = 0;
    };

    std::wstring BuildDialogInfo(const DialogContext* context)
    {
        std::wstring info = L"File: " + (context->displayPath.empty() ? context->placedPath : context->displayPath);
        if (!context->status.empty())
            info += L"\r\n" + context->status;
        else
        {
            info += L"\r\nLine: " + std::to_wstring(context->lineIndex + 1);
            if (context->lineCount > 1)
                info += L"-" + std::to_wstring(context->lineIndex + context->lineCount);
        }

        if (!context->history.empty())
            info += L"  (" + std::to_wstring(context->historyIndex + 1) + L"/" + std::to_wstring(context->history.size()) + L")";
        return info;
    }

    void ApplyHistoryEntry(DialogContext* context, size_t index)
    {
        if (context == nullptr || index >= context->history.size())
            return;

        const HistoryEntry& entry = context->history[index];
        context->historyIndex = index;
        context->filePath = entry.filePath;
        context->displayPath = entry.displayPath;
        context->renderedText = entry.renderedText;
        context->originalLine = entry.lineText;
        context->lineIndex = entry.lineIndex;
        context->lineCount = entry.lineCount;
        context->canEdit = entry.canEdit;
        context->status.clear();
    }

    void RefreshDialogControls(HWND hwnd, DialogContext* context)
    {
        if (context == nullptr)
            return;

        SetWindowTextW(GetDlgItem(hwnd, kInfoLabelId), BuildDialogInfo(context).c_str());
        SetWindowTextW(GetDlgItem(hwnd, kEditControlId), context->originalLine.c_str());
        SetWindowTextW(GetDlgItem(hwnd, kCurrentLabelId), (L"Current: " + context->renderedText).c_str());
        EnableWindow(GetDlgItem(hwnd, kEditControlId), context->canEdit);
        EnableWindow(GetDlgItem(hwnd, kSaveButtonId), context->canEdit);
        EnableWindow(GetDlgItem(hwnd, kPrevButtonId), !context->history.empty() && context->historyIndex > 0);
        EnableWindow(GetDlgItem(hwnd, kNextButtonId), !context->history.empty() && context->historyIndex + 1 < context->history.size());
    }

    bool SaveDialogCurrentLine(HWND hwnd, DialogContext* context)
    {
        if (context == nullptr || !context->canEdit)
            return false;

        HWND edit = GetDlgItem(hwnd, kEditControlId);
        int length = GetWindowTextLengthW(edit);
        std::wstring replacement(length + 1, L'\0');
        GetWindowTextW(edit, replacement.data(), length + 1);
        replacement.resize(length);

        TextFileContent file = ReadTextFileWithEncoding(context->filePath);
        std::vector<std::wstring> lines = SplitLinesPreserve(file.text);
        if (context->lineIndex >= lines.size())
            return false;

        const size_t availableLines = lines.size() - context->lineIndex;
        const size_t replaceCount = context->lineCount < availableLines ? context->lineCount : availableLines;
        const bool hadNewline = !lines[context->lineIndex + replaceCount - 1].empty() && lines[context->lineIndex + replaceCount - 1].back() == L'\n';
        std::vector<std::wstring> replacementLines = SplitLinesPreserve(replacement);
        if (replacementLines.empty())
            replacementLines.push_back(L"");
        if (replacementLines.size() > 1 && replacementLines.back().empty())
            replacementLines.pop_back();
        if (hadNewline && !replacementLines.back().empty() && replacementLines.back().back() != L'\n')
            replacementLines.back() += L"\n";

        lines.erase(lines.begin() + context->lineIndex, lines.begin() + context->lineIndex + replaceCount);
        lines.insert(lines.begin() + context->lineIndex, replacementLines.begin(), replacementLines.end());
        std::wstring updated;
        for (const std::wstring& line : lines)
            updated += line;

        if (!WriteTextFileWithEncoding(context->filePath, updated, file.encoding))
            return false;

        context->saved = true;
        context->originalLine = replacement;
        context->lineCount = replacementLines.size();
        context->status = L"Saved.";
        if (!context->history.empty() && context->historyIndex < context->history.size())
        {
            context->history[context->historyIndex].lineText = replacement;
            context->history[context->historyIndex].lineCount = context->lineCount;
        }

        {
            lock_guard<mutex> lock(g_mutex);
            for (HistoryEntry& entry : g_state.history)
            {
                if (entry.filePath == context->filePath && entry.lineIndex == context->lineIndex)
                {
                    entry.lineText = replacement;
                    entry.lineCount = context->lineCount;
                }
            }
            if (g_state.matchedFilePath == context->filePath && g_state.matchedLineIndex == context->lineIndex)
            {
                g_state.matchedLineText = replacement;
                g_state.matchedLineCount = context->lineCount;
            }
            g_lineCache = LineCache();
        }

        Debugger::Log(L"EditMode saved file=%s line=%u text=%s", context->filePath.c_str(), static_cast<unsigned>(context->lineIndex + 1), replacement.c_str());
        return true;
    }

    void SetDialogFont(HWND hwnd, HWND child)
    {
        HFONT font = reinterpret_cast<HFONT>(SendMessageW(hwnd, WM_GETFONT, 0, 0));
        if (font != nullptr)
            SendMessageW(child, WM_SETFONT, reinterpret_cast<WPARAM>(font), TRUE);
    }

    POINT ClampDialogPositionToMonitor(int x, int y)
    {
        POINT point{ x, y };
        HMONITOR monitor = MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST);
        MONITORINFO info{};
        info.cbSize = sizeof(info);
        if (monitor != nullptr && GetMonitorInfoW(monitor, &info))
        {
            const RECT& work = info.rcWork;
            if (point.x < work.left)
                point.x = work.left;
            if (point.y < work.top)
                point.y = work.top;
            if (point.x + kDialogWidth > work.right)
                point.x = max(work.left, work.right - kDialogWidth);
            if (point.y + kDialogMinHeight > work.bottom)
                point.y = max(work.top, work.bottom - kDialogMinHeight);
        }
        return point;
    }

    void SaveDialogWindowPosition(HWND hwnd)
    {
        RECT rect{};
        if (hwnd == nullptr || !GetWindowRect(hwnd, &rect))
            return;

        const int x = rect.left;
        const int y = rect.top;
        std::wstring iniPath;
        {
            lock_guard<mutex> lock(g_mutex);
            g_config.windowX = x;
            g_config.windowY = y;
            g_config.hasWindowPosition = true;
            iniPath = g_config.iniPath;
        }

        if (!iniPath.empty())
        {
            WriteIniValue(iniPath, L"editmode", L"window_x", std::to_wstring(x));
            WriteIniValue(iniPath, L"editmode", L"window_y", std::to_wstring(y));
        }
        Debugger::Log(L"EditMode saved dialog position x=%d y=%d", x, y);
    }

    void LayoutDialogControls(HWND hwnd)
    {
        RECT rect{};
        if (!GetClientRect(hwnd, &rect))
            return;

        const int buttonY = max(172, rect.bottom - kDialogButtonYFromBottom);
        const int currentY = max(132, buttonY - kDialogCurrentLabelGap - kDialogCurrentLabelHeight);
        const int editHeight = max(58, currentY - kDialogCurrentLabelGap - kDialogEditTop);

        MoveWindow(GetDlgItem(hwnd, kInfoLabelId), 12, 12, 580, 42, TRUE);
        MoveWindow(GetDlgItem(hwnd, kEditControlId), kDialogEditLeft, kDialogEditTop, kDialogEditWidth, editHeight, TRUE);
        MoveWindow(GetDlgItem(hwnd, kCurrentLabelId), 12, currentY, 580, kDialogCurrentLabelHeight, TRUE);
        MoveWindow(GetDlgItem(hwnd, kPrevButtonId), 308, buttonY, 40, 28, TRUE);
        MoveWindow(GetDlgItem(hwnd, kSaveButtonId), 356, buttonY, 88, 28, TRUE);
        MoveWindow(GetDlgItem(hwnd, kNextButtonId), 452, buttonY, 40, 28, TRUE);
        MoveWindow(GetDlgItem(hwnd, kCancelButtonId), 504, buttonY, 88, 28, TRUE);
    }

    LRESULT CALLBACK EditDialogProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam)
    {
        DialogContext* context = reinterpret_cast<DialogContext*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));

        switch (message)
        {
        case WM_CREATE:
        {
            auto* create = reinterpret_cast<CREATESTRUCTW*>(lParam);
            context = reinterpret_cast<DialogContext*>(create->lpCreateParams);
            SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(context));

            HWND infoLabel = CreateWindowExW(0, L"STATIC", BuildDialogInfo(context).c_str(), WS_CHILD | WS_VISIBLE, 12, 12, 580, 42, hwnd, reinterpret_cast<HMENU>(kInfoLabelId), nullptr, nullptr);
            HWND edit = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", context->originalLine.c_str(), WS_CHILD | WS_VISIBLE | WS_TABSTOP | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_WANTRETURN, 12, 66, 580, 58, hwnd, reinterpret_cast<HMENU>(kEditControlId), nullptr, nullptr);
            HWND rendered = CreateWindowExW(0, L"STATIC", (L"Current: " + context->renderedText).c_str(), WS_CHILD | WS_VISIBLE, 12, 132, 580, 42, hwnd, reinterpret_cast<HMENU>(kCurrentLabelId), nullptr, nullptr);
            HWND prev = CreateWindowExW(0, L"BUTTON", L"<", WS_CHILD | WS_VISIBLE | WS_TABSTOP, 308, 172, 40, 28, hwnd, reinterpret_cast<HMENU>(kPrevButtonId), nullptr, nullptr);
            HWND save = CreateWindowExW(0, L"BUTTON", L"Edit", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON, 356, 172, 88, 28, hwnd, reinterpret_cast<HMENU>(kSaveButtonId), nullptr, nullptr);
            HWND next = CreateWindowExW(0, L"BUTTON", L">", WS_CHILD | WS_VISIBLE | WS_TABSTOP, 452, 172, 40, 28, hwnd, reinterpret_cast<HMENU>(kNextButtonId), nullptr, nullptr);
            HWND cancel = CreateWindowExW(0, L"BUTTON", L"Cancel", WS_CHILD | WS_VISIBLE | WS_TABSTOP, 504, 172, 88, 28, hwnd, reinterpret_cast<HMENU>(kCancelButtonId), nullptr, nullptr);
            SetDialogFont(hwnd, infoLabel);
            SetDialogFont(hwnd, edit);
            SetDialogFont(hwnd, rendered);
            SetDialogFont(hwnd, prev);
            SetDialogFont(hwnd, save);
            SetDialogFont(hwnd, next);
            SetDialogFont(hwnd, cancel);
            LayoutDialogControls(hwnd);
            RefreshDialogControls(hwnd, context);
            SetFocus(context->canEdit ? edit : cancel);
            return 0;
        }
        case WM_GETMINMAXINFO:
        {
            auto* info = reinterpret_cast<MINMAXINFO*>(lParam);
            info->ptMinTrackSize.x = kDialogWidth;
            info->ptMaxTrackSize.x = kDialogWidth;
            info->ptMinTrackSize.y = kDialogMinHeight;
            return 0;
        }
        case WM_SIZE:
            LayoutDialogControls(hwnd);
            return 0;
        case WM_COMMAND:
            if (LOWORD(wParam) == kCancelButtonId)
            {
                SaveDialogWindowPosition(hwnd);
                DestroyWindow(hwnd);
                return 0;
            }
            if (LOWORD(wParam) == kSaveButtonId && context != nullptr && context->canEdit)
            {
                if (!SaveDialogCurrentLine(hwnd, context))
                    context->status = L"Save failed.";
                RefreshDialogControls(hwnd, context);
                SetFocus(GetDlgItem(hwnd, kEditControlId));
                return 0;
            }
            if (LOWORD(wParam) == kPrevButtonId && context != nullptr && context->historyIndex > 0)
            {
                ApplyHistoryEntry(context, context->historyIndex - 1);
                RefreshDialogControls(hwnd, context);
                SetFocus(GetDlgItem(hwnd, kEditControlId));
                return 0;
            }
            if (LOWORD(wParam) == kNextButtonId && context != nullptr && context->historyIndex + 1 < context->history.size())
            {
                ApplyHistoryEntry(context, context->historyIndex + 1);
                RefreshDialogControls(hwnd, context);
                SetFocus(GetDlgItem(hwnd, kEditControlId));
                return 0;
            }
            break;

        case WM_CLOSE:
            SaveDialogWindowPosition(hwnd);
            DestroyWindow(hwnd);
            return 0;

        case WM_DESTROY:
            PostQuitMessage(0);
            return 0;
        }

        return DefWindowProcW(hwnd, message, wParam, lParam);
    }

    DWORD WINAPI DialogThreadProc(LPVOID param)
    {
        unique_ptr<DialogContext> context(reinterpret_cast<DialogContext*>(param));
        HINSTANCE instance = reinterpret_cast<HINSTANCE>(GetModuleHandleW(nullptr));

        WNDCLASSW wc{};
        wc.lpfnWndProc = EditDialogProc;
        wc.hInstance = instance;
        wc.lpszClassName = L"CherryAIKirikiriEditModeWindow";
        wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
        wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_BTNFACE + 1);
        RegisterClassW(&wc);

        HWND owner = FindOwnerWindow();
        RECT ownerRect{};
        if (owner != nullptr)
            GetClientRect(owner, &ownerRect);

        POINT origin{};
        if (owner != nullptr)
            ClientToScreen(owner, &origin);

        int x = CW_USEDEFAULT;
        int y = CW_USEDEFAULT;
        bool hasStoredPosition = false;
        {
            lock_guard<mutex> lock(g_mutex);
            hasStoredPosition = g_config.hasWindowPosition;
            if (hasStoredPosition)
            {
                x = g_config.windowX;
                y = g_config.windowY;
            }
        }

        if (hasStoredPosition)
        {
            POINT clamped = ClampDialogPositionToMonitor(x, y);
            x = clamped.x;
            y = clamped.y;
        }
        else if (owner != nullptr && ownerRect.right > 0 && ownerRect.bottom > 0)
        {
            x = origin.x + max(8, (ownerRect.right - kDialogWidth) / 2);
            y = origin.y + max(8, ownerRect.bottom - kDialogHeight - 24);
        }

        HWND hwnd = CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_TOPMOST,
            wc.lpszClassName,
            L"CherryAI Direct Edit",
            WS_POPUP | WS_CAPTION | WS_SYSMENU | WS_BORDER | WS_THICKFRAME,
            x,
            y,
            kDialogWidth,
            kDialogHeight,
            nullptr,
            nullptr,
            instance,
            context.get());

        if (hwnd == nullptr)
        {
            Debugger::Log(L"EditMode failed to create edit dialog");
        }
        else
        {
            {
                lock_guard<mutex> lock(g_mutex);
                g_state.dialogHwnd = hwnd;
            }
            ShowWindow(hwnd, SW_SHOW);
            SetWindowPos(hwnd, HWND_TOPMOST, x, y, kDialogWidth, kDialogHeight, SWP_SHOWWINDOW);
            BringWindowToTop(hwnd);
            SetForegroundWindow(hwnd);
            UpdateWindow(hwnd);
            MSG msg{};
            while (GetMessageW(&msg, nullptr, 0, 0) > 0)
            {
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
        }

        Debugger::Log(
            L"EditMode dialog closed saved=%s file=%s line=%u",
            context->saved ? L"true" : L"false",
            context->filePath.c_str(),
            static_cast<unsigned>(context->lineIndex + 1));

        {
            lock_guard<mutex> lock(g_mutex);
            g_state.dialogOpen = false;
            g_state.dialogHwnd = nullptr;
        }
        return 0;
    }

    void OpenDialog()
    {
        if (HasEditableDialogueScenario())
        {
            RefreshHistoryFromScriptGlobal();
            RefreshCurrentTextFromScriptGlobal();
            BackfillHistoryBeforeMatchedLine();
        }

        auto context = make_unique<DialogContext>();
        {
            lock_guard<mutex> lock(g_mutex);
            if (g_state.dialogOpen)
                return;
            g_state.dialogOpen = true;
            context->filePath = g_state.editableFilePath;
            context->requestedName = g_state.requestedName;
            context->placedPath = g_state.placedPath;
            context->renderedText = g_state.renderedText;
            context->history = g_state.history;
            if (!context->history.empty())
            {
                ApplyHistoryEntry(context.get(), context->history.size() - 1);
                context->useMatchedLine = true;
            }
            else if (g_state.hasMatchedLine && !g_state.renderedText.empty())
            {
                context->filePath = g_state.matchedFilePath;
                context->renderedText = g_state.matchedRenderedText;
                context->originalLine = g_state.matchedLineText;
                context->lineIndex = g_state.matchedLineIndex;
                context->lineCount = g_state.matchedLineCount;
                context->useMatchedLine = true;
            }
        }
        if (context->history.empty() && !IsDialogueScriptPath(context->filePath))
            context->filePath.clear();
        context->displayPath = GetPatchRelativePath(context->filePath);

        if (context->filePath.empty())
        {
            context->status = context->renderedText.empty()
                ? L"No current dialogue text is available yet."
                : L"Current scenario is not a resolved loose file; archive-backed scripts cannot be edited in place.";
            Debugger::Log(L"EditMode open: not editable requested=%s placed=%s rendered=%s", context->requestedName.c_str(), context->placedPath.c_str(), context->renderedText.c_str());
        }
        else
        {
            LineMatch match;
            if (!context->useMatchedLine)
            {
                lock_guard<mutex> lock(g_mutex);
                match = FindLine(GetCachedLines(context->filePath), context->renderedText);
            }

            if (!context->useMatchedLine && !match.found)
            {
                context->status = L"Rendered text was not found in the current .ks file.";
                Debugger::Log(L"EditMode no match file=%s rendered=%s", context->filePath.c_str(), context->renderedText.c_str());
            }
            else
            {
                if (!context->useMatchedLine)
                {
                    context->lineIndex = match.lineIndex;
                    context->lineCount = match.lineCount;
                    context->originalLine = match.lineText;
                }
                context->canEdit = IsWritableFile(context->filePath);
                if (!context->canEdit)
                    context->status = L"Matched line, but the file is read-only or locked by the engine.";
                Debugger::Log(L"EditMode matched file=%s line=%u writable=%s text=%s", context->filePath.c_str(), static_cast<unsigned>(context->lineIndex + 1), context->canEdit ? L"true" : L"false", context->originalLine.c_str());
            }
        }

        if (context->originalLine.empty())
            context->originalLine = context->renderedText;

        HANDLE thread = CreateThread(nullptr, 0, DialogThreadProc, context.release(), 0, nullptr);
        if (thread != nullptr)
            CloseHandle(thread);
        else
        {
            lock_guard<mutex> lock(g_mutex);
            g_state.dialogOpen = false;
        }
    }

    void PollHotkey()
    {
        if (!g_config.enabled)
            return;

        HWND foreground = GetForegroundWindow();
        if (foreground == nullptr)
            return;

        DWORD foregroundProcessId = 0;
        GetWindowThreadProcessId(foreground, &foregroundProcessId);
        if (foregroundProcessId != GetCurrentProcessId())
            return;

        DWORD now = GetTickCount();
        {
            lock_guard<mutex> lock(g_mutex);
            if (g_state.dialogOpen)
                return;
            const bool isDown = (GetAsyncKeyState(g_config.virtualKey) & 0x8000) != 0;
            if (!isDown)
            {
                g_state.keyWasDown = false;
                return;
            }
            if (g_state.keyWasDown)
                return;
            g_state.keyWasDown = true;
            if (now - g_state.lastHotkeyTick < 350)
                return;
            g_state.lastHotkeyTick = now;
        }
        Debugger::Log(L"EditMode hotkey pressed key=%c", g_config.key);
        RequestOpenDialogOnOwnerThread();
    }

    DWORD WINAPI HotkeyThreadProc(LPVOID)
    {
        Debugger::Log(L"EditMode hotkey thread started");
        {
            lock_guard<mutex> lock(g_mutex);
            g_state.keyWasDown = (GetAsyncKeyState(g_config.virtualKey) & 0x8000) != 0;
        }

        while (g_shutdownEvent == nullptr || WaitForSingleObject(g_shutdownEvent, 25) == WAIT_TIMEOUT)
            PollHotkey();

        Debugger::Log(L"EditMode hotkey thread stopped");
        return 0;
    }

    void StartHotkeyThread()
    {
        if (!g_config.enabled || g_hotkeyThread != nullptr)
            return;

        g_shutdownEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
        g_hotkeyThread = CreateThread(nullptr, 0, HotkeyThreadProc, nullptr, 0, nullptr);
        if (g_hotkeyThread != nullptr)
            CloseHandle(g_hotkeyThread);
    }
}

void EditMode::Init()
{
    LoadConfig();
    InstallDebugStringHooks();
    StartHotkeyThread();
}

void EditMode::Shutdown()
{
    if (g_shutdownEvent != nullptr)
        SetEvent(g_shutdownEvent);

    if (g_subclassedOwner != nullptr && g_originalOwnerWndProc != nullptr && IsWindow(g_subclassedOwner))
    {
        SetWindowLongPtrW(g_subclassedOwner, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(g_originalOwnerWndProc));
        g_subclassedOwner = nullptr;
        g_originalOwnerWndProc = nullptr;
    }
}

void EditMode::OnTextStreamOpened(const std::wstring& requestedName, const std::wstring& placedPath, const std::wstring& editableFilePath)
{
    LoadConfig();
    if (!g_config.enabled)
        return;

    if (!IsKsName(requestedName) && !IsKsName(placedPath))
        return;

    {
        lock_guard<mutex> lock(g_mutex);
        g_state.requestedName = requestedName;
        g_state.placedPath = placedPath;
        g_state.editableFilePath = editableFilePath;
        g_state.hasMatchedLine = false;
    }

    Debugger::Log(
        L"EditMode scenario request=%s placed=%s editable=%s",
        requestedName.c_str(),
        placedPath.c_str(),
        editableFilePath.empty() ? L"<none>" : editableFilePath.c_str());

    SetFallbackMatchedLine(editableFilePath);
}

void EditMode::OnRenderedText(const std::wstring& text)
{
    LoadConfig();
    if (!g_config.enabled)
        return;

    std::wstring trimmed = TrimAsciiWhitespace(text);
    if (trimmed.size() >= 2)
    {
        lock_guard<mutex> lock(g_mutex);
        g_state.renderedText = trimmed;
    }

    TryUpdateMatchedLine(trimmed);
}

void EditMode::OnScriptCurrentText(const std::wstring& text)
{
    LoadConfig();
    if (!g_config.enabled)
        return;

    UpdateCurrentTextFromScript(text);
}
