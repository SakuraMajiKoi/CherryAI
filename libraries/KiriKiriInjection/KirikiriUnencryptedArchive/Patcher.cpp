#include "stdafx.h"

using namespace std;

namespace
{
    bool g_loggedFirstLooseScenarioLine = false;
    constexpr BYTE kWarcTypeXorKey0 = 0x27;
    constexpr BYTE kWarcLengthXorKey[] = { 0x7d, 0x16, 0x9f, 0xf1 };
    constexpr wchar_t kEmbeddedWarcStart[] = L"<<<KANO2_EMBEDDED_WARC";
    constexpr wchar_t kEmbeddedWarcEnd[] = L"<<<END_KANO2_EMBEDDED_WARC";

    class VectorBinaryStream : public tTJSBinaryStream
    {
    public:
        explicit VectorBinaryStream(std::vector<BYTE> data)
            : _data(std::move(data))
        {
        }

        tjs_uint64 TJS_INTF_METHOD Seek(tjs_int64 offset, tjs_int whence) override
        {
            switch (whence)
            {
            case SEEK_SET:
                _position = offset < 0 ? 0 : static_cast<tjs_uint64>(offset);
                break;

            case SEEK_CUR:
                if (offset < 0 && static_cast<tjs_uint64>(-offset) > _position)
                    _position = 0;
                else
                    _position += offset;
                break;

            case SEEK_END:
                if (offset < 0 && static_cast<tjs_uint64>(-offset) > _data.size())
                    _position = 0;
                else
                    _position = static_cast<tjs_uint64>(_data.size()) + offset;
                break;
            }

            if (_position > _data.size())
                _position = _data.size();

            return _position;
        }

        tjs_uint TJS_INTF_METHOD Read(void* buffer, tjs_uint read_size) override
        {
            if (_position >= _data.size())
                return 0;

            read_size = min<tjs_uint>(read_size, static_cast<tjs_uint>(_data.size() - _position));
            memcpy(buffer, _data.data() + _position, read_size);
            _position += read_size;
            return read_size;
        }

        tjs_uint TJS_INTF_METHOD Write(const void* buffer, tjs_uint write_size) override
        {
            throw exception("Not implemented");
        }

        void TJS_INTF_METHOD SetEndOfStorage() override
        {
            throw exception("Not implemented");
        }

        tjs_uint64 TJS_INTF_METHOD GetSize() override
        {
            return _data.size();
        }

    private:
        std::vector<BYTE> _data;
        tjs_uint64 _position = 0;
    };

    struct RecursiveFileIndex
    {
        std::map<std::wstring, std::vector<std::wstring>> by_name;
        std::map<std::wstring, std::vector<std::wstring>> by_stem;
    };

    std::map<std::wstring, RecursiveFileIndex> g_recursiveFileIndexes;

    std::wstring NormalizeStorageTarget(const std::wstring& value)
    {
        return StringUtil::ToLower(StringUtil::Replace(value, L'\\', L'/'));
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

    const RecursiveFileIndex& GetRecursiveFileIndex(const std::wstring& searchRoot)
    {
        const std::wstring normalizedRoot = NormalizeStorageTarget(Path::GetFullPath(searchRoot));
        auto existing = g_recursiveFileIndexes.find(normalizedRoot);
        if (existing != g_recursiveFileIndexes.end())
            return existing->second;

        RecursiveFileIndex index;
        if (GetFileAttributes(searchRoot.c_str()) != INVALID_FILE_ATTRIBUTES)
        {
            for (const auto& entry : filesystem::recursive_directory_iterator(searchRoot))
            {
                if (!entry.is_regular_file())
                    continue;

                const std::wstring candidatePath = entry.path().wstring();
                const std::wstring candidateName = StringUtil::ToLower(Path::GetFileName(candidatePath));
                const std::wstring candidateStem = StringUtil::ToLower(Path::GetFileNameWithoutExtension(candidatePath));
                index.by_name[candidateName].push_back(candidatePath);
                index.by_stem[candidateStem].push_back(candidatePath);
            }
        }

        return g_recursiveFileIndexes.emplace(normalizedRoot, std::move(index)).first->second;
    }

    std::wstring UrlToFilePath(const std::wstring& url)
    {
        constexpr wchar_t prefix[] = L"file://./";
        if (!url.starts_with(prefix) || url.find(L'>') != std::wstring::npos)
            return L"";

        std::wstring path = url.substr(wcslen(prefix));
        path = StringUtil::Replace(path, L'/', L'\\');
        if (path.size() >= 2 && path[1] == L'\\')
            path.insert(1, L":");
        return path;
    }

    std::wstring ReadTextFileForLogging(const std::wstring& filePath)
    {
        FILE* pFile = _wfopen(filePath.c_str(), L"rb");
        if (pFile == nullptr)
            return L"";

        fseek(pFile, 0, SEEK_END);
        long size = ftell(pFile);
        fseek(pFile, 0, SEEK_SET);
        std::vector<BYTE> bytes;
        bytes.resize(size > 0 ? size : 0);
        if (!bytes.empty())
            fread(bytes.data(), 1, bytes.size(), pFile);
        fclose(pFile);

        if (bytes.size() >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
            return std::wstring(reinterpret_cast<const wchar_t*>(bytes.data() + 2), (bytes.size() - 2) / sizeof(wchar_t));

        if (bytes.size() >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF)
        {
            std::wstring result;
            result.reserve((bytes.size() - 2) / 2);
            for (size_t i = 2; i + 1 < bytes.size(); i += 2)
                result.push_back((wchar_t)((bytes[i] << 8) | bytes[i + 1]));
            return result;
        }

        std::string utf8(reinterpret_cast<const char*>(bytes.data()), bytes.size());
        if (utf8.size() >= 3 && (BYTE)utf8[0] == 0xEF && (BYTE)utf8[1] == 0xBB && (BYTE)utf8[2] == 0xBF)
            utf8.erase(0, 3);
        return StringUtil::ToUTF16(utf8);
    }

    std::vector<BYTE> ReadFileBytes(const std::wstring& filePath)
    {
        FileStream stream(filePath, L"rb");
        std::vector<BYTE> data;
        data.resize(stream.Size());
        if (!data.empty())
            stream.ReadBytes(data.data(), static_cast<int>(data.size()));
        return data;
    }

    bool StartsWithBytes(const std::vector<BYTE>& data, const char* text)
    {
        size_t length = strlen(text);
        return data.size() >= length && memcmp(data.data(), text, length) == 0;
    }

    bool LooksLikeUtf16LeText(const std::vector<BYTE>& data)
    {
        if (data.size() < 8 || (data.size() & 1) != 0)
            return false;

        if (data.size() >= 2 && data[0] == 0xFF && data[1] == 0xFE)
            return true;

        size_t zeroCount = 0;
        size_t samplePairs = min<size_t>(data.size() / 2, 32);
        for (size_t index = 0; index < samplePairs; index++)
        {
            if (data[index * 2 + 1] == 0)
                zeroCount++;
        }

        return zeroCount >= samplePairs * 3 / 4;
    }

    bool TryDecodeLooseMdatEditText(const std::vector<BYTE>& data, std::wstring& text)
    {
        if (LooksLikeUtf16LeText(data))
        {
            size_t start = data.size() >= 2 && data[0] == 0xFF && data[1] == 0xFE ? 2 : 0;
            text.assign(reinterpret_cast<const wchar_t*>(data.data() + start), (data.size() - start) / sizeof(wchar_t));
        }
        else if (StartsWithBytes(data, "(const)") || StartsWithBytes(data, "<<<KANO2_EMBEDDED_WARC") || StartsWithBytes(data, "<%"))
        {
            std::string utf8(reinterpret_cast<const char*>(data.data()), data.size());
            if (utf8.size() >= 3 && (BYTE)utf8[0] == 0xEF && (BYTE)utf8[1] == 0xBB && (BYTE)utf8[2] == 0xBF)
                utf8.erase(0, 3);
            text = StringUtil::ToUTF16(utf8);
        }
        else
        {
            return false;
        }

        if (!text.empty() && text[0] == 0xFEFF)
            text.erase(text.begin());

        return text.find(L"(const)") != std::wstring::npos ||
            text.find(kEmbeddedWarcStart) != std::wstring::npos ||
            text.find(L"マップ名") != std::wstring::npos ||
            text.find(L"グレード名") != std::wstring::npos;
    }

    std::vector<BYTE> Utf16LeBytes(const std::wstring& text)
    {
        std::vector<BYTE> data;
        data.reserve(text.size() * sizeof(wchar_t));
        for (wchar_t ch : text)
        {
            data.push_back(static_cast<BYTE>(ch & 0xFF));
            data.push_back(static_cast<BYTE>((ch >> 8) & 0xFF));
        }
        return data;
    }

    DWORD Adler32(const std::vector<BYTE>& data)
    {
        constexpr DWORD kModAdler = 65521;
        DWORD a = 1;
        DWORD b = 0;
        for (BYTE value : data)
        {
            a = (a + value) % kModAdler;
            b = (b + a) % kModAdler;
        }
        return (b << 16) | a;
    }

    std::vector<BYTE> ZlibStoreCompress(const std::vector<BYTE>& data)
    {
        std::vector<BYTE> output;
        output.reserve(data.size() + (data.size() / 65535 + 1) * 5 + 6);
        output.push_back(0x78);
        output.push_back(0x01);

        size_t offset = 0;
        while (offset < data.size())
        {
            size_t chunkSize = min<size_t>(65535, data.size() - offset);
            BYTE finalBlock = offset + chunkSize >= data.size() ? 1 : 0;
            output.push_back(finalBlock);

            WORD len = static_cast<WORD>(chunkSize);
            WORD nlen = static_cast<WORD>(~len);
            output.push_back(static_cast<BYTE>(len & 0xFF));
            output.push_back(static_cast<BYTE>((len >> 8) & 0xFF));
            output.push_back(static_cast<BYTE>(nlen & 0xFF));
            output.push_back(static_cast<BYTE>((nlen >> 8) & 0xFF));
            output.insert(output.end(), data.begin() + offset, data.begin() + offset + chunkSize);
            offset += chunkSize;
        }

        DWORD checksum = Adler32(data);
        output.push_back(static_cast<BYTE>((checksum >> 24) & 0xFF));
        output.push_back(static_cast<BYTE>((checksum >> 16) & 0xFF));
        output.push_back(static_cast<BYTE>((checksum >> 8) & 0xFF));
        output.push_back(static_cast<BYTE>(checksum & 0xFF));
        return output;
    }

    bool TryHexDecode(const std::wstring& text, std::vector<BYTE>& bytes)
    {
        auto HexValue = [](wchar_t ch) -> int
        {
            if (ch >= L'0' && ch <= L'9')
                return ch - L'0';
            if (ch >= L'a' && ch <= L'f')
                return 10 + ch - L'a';
            if (ch >= L'A' && ch <= L'F')
                return 10 + ch - L'A';
            return -1;
        };

        std::wstring compact;
        compact.reserve(text.size());
        for (wchar_t ch : text)
        {
            if (!iswspace(ch))
                compact.push_back(ch);
        }

        if ((compact.size() & 1) != 0)
            return false;

        bytes.clear();
        bytes.reserve(compact.size() / 2);
        for (size_t index = 0; index < compact.size(); index += 2)
        {
            int high = HexValue(compact[index]);
            int low = HexValue(compact[index + 1]);
            if (high < 0 || low < 0)
                return false;
            bytes.push_back(static_cast<BYTE>((high << 4) | low));
        }

        return true;
    }

    std::wstring HexEncodeSpacedLower(const std::vector<BYTE>& bytes)
    {
        static constexpr wchar_t digits[] = L"0123456789abcdef";
        std::wstring text;
        text.reserve(bytes.size() * 3);
        for (size_t index = 0; index < bytes.size(); index++)
        {
            if (index > 0)
                text.push_back(L' ');

            BYTE value = bytes[index];
            text.push_back(digits[value >> 4]);
            text.push_back(digits[value & 0x0F]);
        }
        return text;
    }

    std::wstring StripMarkerPadding(const std::wstring& text)
    {
        std::wstring result = text;
        if (result.starts_with(L"\r\n"))
            result.erase(0, 2);
        else if (result.starts_with(L"\n"))
            result.erase(0, 1);

        if (result.ends_with(L"\r\n"))
            result.erase(result.size() - 2);
        else if (result.ends_with(L"\n"))
            result.erase(result.size() - 1);

        return result;
    }

    bool TryGetMarkerValue(const std::wstring& marker, const std::wstring& key, std::wstring& value)
    {
        size_t start = marker.find(key);
        if (start == std::wstring::npos)
            return false;

        start += key.size();
        size_t end = start;
        while (end < marker.size() && !iswspace(marker[end]) && marker[end] != L'>')
            end++;

        value = marker.substr(start, end - start);
        return !value.empty();
    }

    std::vector<BYTE> UpdateWarcHeader(std::vector<BYTE> header, size_t payloadLength)
    {
        if (header.size() != 11 || memcmp(header.data(), "warc", 4) != 0)
            return header;

        DWORD payload = static_cast<DWORD>(payloadLength);
        BYTE typeFirst = header[4] ^ kWarcTypeXorKey0;
        BYTE lengthBytes[4] = {
            static_cast<BYTE>(payload & 0xFF),
            static_cast<BYTE>((payload >> 8) & 0xFF),
            static_cast<BYTE>((payload >> 16) & 0xFF),
            static_cast<BYTE>((payload >> 24) & 0xFF),
        };

        for (int index = 0; index < 4; index++)
            header[7 + index] = lengthBytes[index] ^ (kWarcLengthXorKey[index] ^ typeFirst);

        return header;
    }

    std::vector<BYTE> EncodeWarcText(const std::wstring& text, const std::vector<BYTE>& headerTemplate)
    {
        std::vector<BYTE> payload = Utf16LeBytes(text);
        std::vector<BYTE> header = UpdateWarcHeader(headerTemplate, payload.size());
        std::vector<BYTE> compressed = ZlibStoreCompress(payload);
        header.insert(header.end(), compressed.begin(), compressed.end());
        return header;
    }

    bool CollapseEmbeddedWarcTextBlobs(const std::wstring& text, std::wstring& collapsed)
    {
        collapsed.clear();
        collapsed.reserve(text.size());
        size_t searchFrom = 0;
        bool foundAny = false;

        while (true)
        {
            size_t markerStart = text.find(kEmbeddedWarcStart, searchFrom);
            if (markerStart == std::wstring::npos)
                break;

            size_t startClose = text.find(L">>>", markerStart);
            if (startClose == std::wstring::npos)
                return false;

            std::wstring headerHex;
            if (!TryGetMarkerValue(text.substr(markerStart, startClose + 3 - markerStart), L"header=", headerHex))
                return false;

            size_t contentStart = startClose + 3;
            size_t endStart = text.find(kEmbeddedWarcEnd, contentStart);
            if (endStart == std::wstring::npos)
                return false;

            size_t endClose = text.find(L">>>", endStart);
            if (endClose == std::wstring::npos)
                return false;

            std::vector<BYTE> nestedHeader;
            if (!TryHexDecode(headerHex, nestedHeader))
                return false;

            std::wstring embeddedText = StripMarkerPadding(text.substr(contentStart, endStart - contentStart));
            std::vector<BYTE> encoded = EncodeWarcText(embeddedText, nestedHeader);

            collapsed.append(text.substr(searchFrom, markerStart - searchFrom));
            collapsed.append(L"<% ");
            collapsed.append(HexEncodeSpacedLower(encoded));
            collapsed.append(L" %>");
            searchFrom = endClose + 3;
            foundAny = true;
        }

        collapsed.append(text.substr(searchFrom));
        return foundAny || text.find(kEmbeddedWarcStart) == std::wstring::npos;
    }

    std::wstring GetArchiveMemberExtension(const wchar_t* pArchivePath)
    {
        return StringUtil::ToLower(Path::GetExtension(pArchivePath));
    }

    void TryLogFirstLooseScenarioLine(const std::wstring& requestedName, const std::wstring& url)
    {
        if (g_loggedFirstLooseScenarioLine)
            return;

        if (!StringUtil::ToLower(requestedName).ends_with(L".ks"))
            return;

        std::wstring filePath = UrlToFilePath(url);
        if (filePath.empty())
            return;

        std::wstring normalizedPath = NormalizeStorageTarget(filePath);
        if (normalizedPath.find(L"/patch/data/kano2scr/") == std::wstring::npos)
            return;

        std::wstring text = ReadTextFileForLogging(filePath);
        if (text.empty())
            return;

        std::vector<std::wstring> lines = StringUtil::Split(text, std::wstring(L"\n"));
        for (size_t i = 0; i < lines.size(); i++)
        {
            std::wstring line = TrimAsciiWhitespace(lines[i]);
            if (line.empty())
                continue;
            if (line.starts_with(L";") || line.starts_with(L"*") || line.starts_with(L"@") || line.starts_with(L"["))
                continue;

            Debugger::Log(
                L"FirstScenarioLine request=%ls override=%ls line=%u text=%ls",
                requestedName.c_str(),
                filePath.c_str(),
                static_cast<unsigned>(i + 1),
                line.c_str());
            g_loggedFirstLooseScenarioLine = true;
            return;
        }
    }

    int GetPatchPriority(const wstring& filePath)
    {
        wstring fileName = StringUtil::ToLower(Path::GetFileName(filePath));
        if (fileName == L"patch" || fileName == L"patch.xp3")
            return 1;

        if (!fileName.starts_with(L"patch"))
            return 0;

        size_t suffixStart = 5;
        size_t suffixLength = fileName.ends_with(L".xp3") ? fileName.size() - 9 : fileName.size() - 5;
        wstring suffix = fileName.substr(suffixStart, suffixLength);
        if (suffix.empty())
            return 1;

        for (wchar_t c : suffix)
        {
            if (c < L'0' || c > L'9')
                return 0;
        }

        return stoi(suffix);
    }

    void AddOverrideUrl(vector<wstring>& urls, const wstring& url)
    {
        if (ranges::find(urls, url) == urls.end())
            urls.push_back(url);
    }

    void AddFileOverrideUrl(vector<wstring>& urls, const wstring& filePath)
    {
        if (GetFileAttributes(filePath.c_str()) == INVALID_FILE_ATTRIBUTES)
            return;

        AddOverrideUrl(urls, Kirikiri::FilePathToUrl(filePath));
    }

    void AddStemMatchedFileOverrideUrls(vector<wstring>& urls, const wstring& requestedFilePath)
    {
        wstring directoryPath = Path::GetDirectoryName(requestedFilePath);
        if (directoryPath.empty() || GetFileAttributes(directoryPath.c_str()) == INVALID_FILE_ATTRIBUTES)
            return;

        wstring requestedStem = StringUtil::ToLower(Path::GetFileNameWithoutExtension(requestedFilePath));
        for (const auto& entry : filesystem::directory_iterator(directoryPath))
        {
            if (!entry.is_regular_file())
                continue;

            wstring candidatePath = entry.path().wstring();
            if (StringUtil::ToLower(Path::GetFileNameWithoutExtension(candidatePath)) != requestedStem)
                continue;

            AddFileOverrideUrl(urls, candidatePath);
        }
    }

    void AddRecursiveFileNameOverrideUrls(vector<wstring>& urls, const wstring& searchRoot, const wstring& requestedFileName, bool matchStem)
    {
        if (searchRoot.empty() || GetFileAttributes(searchRoot.c_str()) == INVALID_FILE_ATTRIBUTES)
            return;

        const wstring requestedName = StringUtil::ToLower(requestedFileName);
        const wstring requestedStem = StringUtil::ToLower(Path::GetFileNameWithoutExtension(requestedFileName));

        const RecursiveFileIndex& index = GetRecursiveFileIndex(searchRoot);
        auto nameIt = index.by_name.find(requestedName);
        if (nameIt != index.by_name.end())
        {
            for (const std::wstring& candidatePath : nameIt->second)
                AddFileOverrideUrl(urls, candidatePath);
        }

        if (!matchStem)
            return;

        auto stemIt = index.by_stem.find(requestedStem);
        if (stemIt != index.by_stem.end())
        {
            for (const std::wstring& candidatePath : stemIt->second)
                AddFileOverrideUrl(urls, candidatePath);
        }
    }

    void AddPatchFolderOverrideUrls(vector<wstring>& urls, const wstring& patchFolderPath, const wchar_t* pInArchivePath)
    {
        wstring relativePath = StringUtil::Replace<wchar_t>(pInArchivePath, L'/', L'\\');
        wstring relativeFilePath = Path::Combine(patchFolderPath, relativePath);
        AddFileOverrideUrl(urls, relativeFilePath);
        AddStemMatchedFileOverrideUrls(urls, relativeFilePath);

        wstring dataRelativeFilePath = Path::Combine(Path::Combine(patchFolderPath, L"data"), relativePath);
        AddFileOverrideUrl(urls, dataRelativeFilePath);
        AddStemMatchedFileOverrideUrls(urls, dataRelativeFilePath);

        const wchar_t* pFileName = wcsrchr(pInArchivePath, L'/');
        if (pFileName != nullptr && *(pFileName + 1) != 0)
        {
            wstring fileNamePath = Path::Combine(patchFolderPath, pFileName + 1);
            AddFileOverrideUrl(urls, fileNamePath);

            wstring dataFileNamePath = Path::Combine(Path::Combine(patchFolderPath, L"data"), pFileName + 1);
            AddFileOverrideUrl(urls, dataFileNamePath);
        }

        const wstring requestedFileName = Path::GetFileName(relativePath);
        const bool matchStem = Path::GetExtension(requestedFileName).empty();
        AddRecursiveFileNameOverrideUrls(urls, patchFolderPath, requestedFileName, matchStem);

        const wstring patchDataPath = Path::Combine(patchFolderPath, L"data");
        AddRecursiveFileNameOverrideUrls(urls, patchDataPath, requestedFileName, matchStem);
    }

    void AddArchiveOverrideUrls(vector<wstring>& urls, const wstring& archivePath, const wchar_t* pInArchivePath)
    {
        if (GetFileAttributes(archivePath.c_str()) == INVALID_FILE_ATTRIBUTES)
            return;

        wstring archiveUrl = Kirikiri::FilePathToUrl(archivePath);
        AddOverrideUrl(urls, archiveUrl + L">" + pInArchivePath);

        const wchar_t* pFileName = wcsrchr(pInArchivePath, L'/');
        if (pFileName != nullptr && *(pFileName + 1) != 0)
            AddOverrideUrl(urls, archiveUrl + L">" + (pFileName + 1));
    }

    vector<wstring> BuildOverrideUrls(const wstring& folderPath, const wchar_t* pInArchivePath)
    {
        vector<wstring> urls;

        vector<wstring> patchFolders;
        for (const auto& entry : filesystem::directory_iterator(folderPath))
        {
            if (!entry.is_directory())
                continue;

            wstring fileName = StringUtil::ToLower(entry.path().filename().wstring());
            if (GetPatchPriority(fileName) > 0)
                patchFolders.push_back(entry.path().wstring());
        }

        ranges::sort(
            patchFolders,
            [](const wstring& left, const wstring& right)
            {
                return GetPatchPriority(left) > GetPatchPriority(right);
            }
        );

        for (const wstring& patchFolder : patchFolders)
            AddPatchFolderOverrideUrls(urls, patchFolder, pInArchivePath);

        return urls;
    }
}

tTJSBinaryStream* Patcher::CreateLooseEncodedMdatStream(const std::wstring& url, const std::vector<BYTE>& originalHeader)
{
    try
    {
        if (originalHeader.size() != 11 || memcmp(originalHeader.data(), "warc", 4) != 0)
            return nullptr;

        const std::wstring filePath = UrlToFilePath(url);
        if (filePath.empty() || GetFileAttributes(filePath.c_str()) == INVALID_FILE_ATTRIBUTES)
            return nullptr;

        std::vector<BYTE> fileBytes = ReadFileBytes(filePath);

        std::wstring decodedText;
        if (!TryDecodeLooseMdatEditText(fileBytes, decodedText))
            return nullptr;

        std::wstring collapsedText;
        if (!CollapseEmbeddedWarcTextBlobs(decodedText, collapsedText))
            return nullptr;

        Debugger::Log(L"Encoding loose MDAT override %s", filePath.c_str());
        auto* pStream = new VectorBinaryStream(EncodeWarcText(collapsedText, originalHeader));
        tTJSBinaryStream::ApplyWrappedVTable(pStream);
        return pStream;
    }
    catch (const std::exception& ex)
    {
        Debugger::Log(L"Loose MDAT encode failed for %s: %hs", url.c_str(), ex.what());
        return nullptr;
    }
    catch (...)
    {
        Debugger::Log(L"Loose MDAT encode failed for %s: unknown exception", url.c_str());
        return nullptr;
    }
}

bool Patcher::PatchSignatureCheck(HMODULE hModule)
{
    void** pVerifierVTable = CompilerHelper::FindVTable(hModule, CompilerType::Msvc, "KrkrSign::VerifierImpl");
    if (pVerifierVTable == nullptr)
        return false;

    Debugger::Log(L"Patching KrkrSign::VerifierImpl");
    MemoryUtil::WritePointer(pVerifierVTable + 4, CustomGetSignatureVerificationResult);
    return true;
}

void Patcher::PatchXP3StreamCreation()
{
    void** pXP3ArchiveVTable = CompilerHelper::FindVTable("tTVPXP3Archive");
    if (pXP3ArchiveVTable == nullptr)
    {
        Debugger::Log(L"Failed to find tTVPXP3Archive vtable");
        return;
    }

    Debugger::Log(L"Located tTVPXP3Archive vtable (%08X - %s)", pXP3ArchiveVTable, CompilerHelper::CompilerType == CompilerType::Borland ? L"Borland" : L"MSVC");
    OriginalCreateStreamByIndex = pXP3ArchiveVTable[3];

    MemoryUtil::WritePointer(pXP3ArchiveVTable + 3, CompilerHelper::WrapAsInstanceMethod<CustomCreateStreamByIndex>());
}

void Patcher::PatchPlacedPathLookup()
{
    Kirikiri::ResolveScriptExport(L"ttstr ::TVPGetPlacedPath(const ttstr &)", OriginalTVPGetPlacedPath);

    DetourTransactionBegin();
    DetourAttach((void**)&OriginalTVPGetPlacedPath, CustomTVPGetPlacedPath);
    DetourTransactionCommit();

    Debugger::Log(L"Hooked TVPGetPlacedPath()");
}

void Patcher::PatchIStreamCreation()
{
    Kirikiri::ResolveScriptExport(L"IStream * ::TVPCreateIStream(const ttstr &,tjs_uint32)", OriginalTVPCreateIStream);

    DetourTransactionBegin();
    DetourAttach((void**)&OriginalTVPCreateIStream, CustomTVPCreateIStream);
    DetourTransactionCommit();

    Debugger::Log(L"Hooked TVPCreateIStream()");
}

void Patcher::PatchTextStreamCreation()
{
    Kirikiri::ResolveScriptExport(L"iTJSTextReadStream * ::TVPCreateTextStreamForRead(const ttstr &,const ttstr &)", OriginalTVPCreateTextStreamForRead);

    DetourTransactionBegin();
    DetourAttach((void**)&OriginalTVPCreateTextStreamForRead, CustomTVPCreateTextStreamForRead);
    DetourTransactionCommit();

    Debugger::Log(L"Hooked TVPCreateTextStreamForRead()");
}

void Patcher::PatchAutoPathExports()
{
    Kirikiri::HookScriptExport(L"void ::TVPAddAutoPath(const ttstr &)", &OriginalTVPAddAutoPath, CustomTVPAddAutoPath);
    Kirikiri::HookScriptExport(L"void ::TVPRemoveAutoPath(const ttstr &)", &OriginalTVPRemoveAutoPath, CustomTVPRemoveAutoPath);
}

void Patcher::PatchStorageMediaRegistration()
{
    Kirikiri::HookScriptExport(L"void ::TVPRegisterStorageMedia(iTVPStorageMedia *)", &OriginalTVPRegisterStorageMedia, CustomTVPRegisterStorageMedia);
    Kirikiri::HookScriptExport(L"void ::TVPUnregisterStorageMedia(iTVPStorageMedia *)", &OriginalTVPUnregisterStorageMedia, CustomTVPUnregisterStorageMedia);
}

vector<wstring> Patcher::BuildOverrideUrlsForPath(const wchar_t* pInArchivePath)
{
    static wstring folderPath = Path::GetModuleFolderPath(nullptr);
    return BuildOverrideUrls(folderPath, pInArchivePath);
}

bool Patcher::WouldRedirectToSelf(const std::wstring& candidateUrl, const std::wstring& currentTarget)
{
    if (candidateUrl.empty() || currentTarget.empty())
        return false;

    return NormalizeStorageTarget(candidateUrl) == NormalizeStorageTarget(currentTarget);
}

ttstr Patcher::CustomTVPGetPlacedPath(const ttstr& name)
{
    ttstr placedPath = OriginalTVPGetPlacedPath(name);

    bool shouldLog =
        wcsstr(name.c_str(), L"scenario/") != nullptr ||
        wcsstr(name.c_str(), L".ks") != nullptr ||
        wcsstr(name.c_str(), L"uipsd/") != nullptr ||
        wcsstr(name.c_str(), L"window@") != nullptr ||
        wcsstr(placedPath.c_str(), L"uipsd/") != nullptr ||
        wcsstr(placedPath.c_str(), L"window@") != nullptr ||
        wcsstr(placedPath.c_str(), L">") != nullptr;

    if (shouldLog)
        Debugger::Log(L"TVPGetPlacedPath(%s) => %s", name.c_str(), placedPath.c_str());

    const wchar_t* pInArchivePath = wcsrchr(placedPath.c_str(), L'>');
    if (pInArchivePath == nullptr || *(pInArchivePath + 1) == 0)
        return placedPath;

    pInArchivePath++;

    const std::wstring extension = GetArchiveMemberExtension(pInArchivePath);
    if (extension == L"mdat" || extension == L"mdatb")
        return placedPath;

    static wstring folderPath = Path::GetModuleFolderPath(nullptr);
    vector<wstring> urls = BuildOverrideUrls(folderPath, pInArchivePath);

    for (const wstring& url : urls)
    {
        bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
        if (shouldLog)
            Debugger::Log(L"Checked override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

        if (exists)
        {
            if (WouldRedirectToSelf(url, placedPath.c_str()))
            {
                if (shouldLog)
                    Debugger::Log(L"Skipping placed-path self-redirect %s", url.c_str());
                continue;
            }

            Debugger::Log(L"Redirecting placed path %s to %s", name.c_str(), url.c_str());
            return ttstr(url.c_str());
        }
    }

    if (shouldLog)
        Debugger::Log(L"No override found for placed path %s", placedPath.c_str());

    return placedPath;
}

void* Patcher::CustomTVPCreateIStream(const ttstr& name, tjs_uint32 flags)
{
    ttstr placedPath = OriginalTVPGetPlacedPath(name);
    bool shouldLog =
        wcsstr(name.c_str(), L"uipsd/") != nullptr ||
        wcsstr(name.c_str(), L"window@") != nullptr ||
        wcsstr(placedPath.c_str(), L"uipsd/") != nullptr ||
        wcsstr(placedPath.c_str(), L"window@") != nullptr ||
        wcsstr(placedPath.c_str(), L">") != nullptr;

    if (shouldLog)
        Debugger::Log(L"TVPCreateIStream(%s, %u) => placed %s", name.c_str(), flags, placedPath.c_str());

    const wchar_t* pInArchivePath = wcsrchr(placedPath.c_str(), L'>');
    if (pInArchivePath != nullptr && *(pInArchivePath + 1) != 0)
    {
        pInArchivePath++;

        const std::wstring extension = GetArchiveMemberExtension(pInArchivePath);
        if (extension == L"mdat" || extension == L"mdatb")
            return OriginalTVPCreateIStream(name, flags);

        static wstring folderPath = Path::GetModuleFolderPath(nullptr);
        vector<wstring> urls = BuildOverrideUrls(folderPath, pInArchivePath);

        for (const wstring& url : urls)
        {
            bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
            if (shouldLog)
                Debugger::Log(L"Checked istream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

            if (exists)
            {
                if (WouldRedirectToSelf(url, placedPath.c_str()) || WouldRedirectToSelf(url, name.c_str()))
                {
                    if (shouldLog)
                        Debugger::Log(L"Skipping istream self-redirect %s", url.c_str());
                    continue;
                }

                Debugger::Log(L"Redirecting istream %s to %s", name.c_str(), url.c_str());
                return OriginalTVPCreateIStream(url.c_str(), flags);
            }
        }
    }

    if (shouldLog)
        Debugger::Log(L"No istream override found for %s", placedPath.c_str());

    return OriginalTVPCreateIStream(name, flags);
}

void* Patcher::CustomTVPCreateTextStreamForRead(const ttstr& name, const ttstr& mode)
{
    ttstr placedPath = OriginalTVPGetPlacedPath(name);
    bool shouldLog =
        wcsstr(name.c_str(), L"scenario/") != nullptr ||
        wcsstr(name.c_str(), L"first.ks") != nullptr ||
        wcsstr(name.c_str(), L"startup.tjs") != nullptr ||
        wcsstr(name.c_str(), L".ks") != nullptr ||
        wcsstr(name.c_str(), L"uipsd/") != nullptr ||
        wcsstr(name.c_str(), L"window@") != nullptr ||
        wcsstr(placedPath.c_str(), L"uipsd/") != nullptr ||
        wcsstr(placedPath.c_str(), L"window@") != nullptr ||
        wcsstr(placedPath.c_str(), L">") != nullptr;

    if (shouldLog)
        Debugger::Log(L"TVPCreateTextStreamForRead(%s, %s) => placed %s", name.c_str(), mode.c_str(), placedPath.c_str());

    const wchar_t* pInArchivePath = wcsrchr(placedPath.c_str(), L'>');
    if (pInArchivePath == nullptr || *(pInArchivePath + 1) == 0)
        return OriginalTVPCreateTextStreamForRead(name, mode);

    pInArchivePath++;

    const std::wstring extension = GetArchiveMemberExtension(pInArchivePath);
    if (extension == L"mdat" || extension == L"mdatb")
        return OriginalTVPCreateTextStreamForRead(name, mode);

    static wstring folderPath = Path::GetModuleFolderPath(nullptr);
    vector<wstring> urls = BuildOverrideUrls(folderPath, pInArchivePath);

    for (const wstring& url : urls)
    {
        bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
        if (shouldLog)
            Debugger::Log(L"Checked text-stream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

        if (exists)
        {
            if (WouldRedirectToSelf(url, placedPath.c_str()) || WouldRedirectToSelf(url, name.c_str()))
            {
                if (shouldLog)
                    Debugger::Log(L"Skipping text-stream self-redirect %s", url.c_str());
                continue;
            }

                TryLogFirstLooseScenarioLine(name.c_str(), url);
            Debugger::Log(L"Redirecting text stream %s to %s", name.c_str(), url.c_str());
            return OriginalTVPCreateTextStreamForRead(url.c_str(), mode);
        }
    }

    if (shouldLog)
        Debugger::Log(L"No text-stream override found for %s", placedPath.c_str());

    return OriginalTVPCreateTextStreamForRead(name, mode);
}

void Patcher::CustomTVPAddAutoPath(const ttstr& url)
{
    if (&url == nullptr)
        return;

    if (!CxdecHelper::IsCxdecUrl(url))
    {
        OriginalTVPAddAutoPath(url);
        return;
    }

    ttstr filePath = CxdecHelper::CxdecUrlToXp3FilePath(url);
    if (CxdecHelper::IsCxdecArchive(filePath))
    {
        OriginalTVPAddAutoPath(url);
    }
    else
    {
        Debugger::Log(L"CustomTVPAddAutoPath(): Changing Cxdec URL %s to %s", url.c_str(), filePath.c_str());
        OriginalTVPAddAutoPath(filePath + L">");
    }
}

void Patcher::CustomTVPRemoveAutoPath(const ttstr& url)
{
    if (&url == nullptr)
        return;

    if (!CxdecHelper::IsCxdecUrl(url))
    {
        OriginalTVPRemoveAutoPath(url);
        return;
    }

    ttstr filePath = CxdecHelper::CxdecUrlToXp3FilePath(url);
    if (CxdecHelper::IsCxdecArchive(filePath))
    {
        OriginalTVPRemoveAutoPath(url);
    }
    else
    {
        Debugger::Log(L"CustomTVPRemoveAutoPath(): Changing Cxdec URL %s to %s", url.c_str(), filePath.c_str());
        OriginalTVPRemoveAutoPath(filePath + L">");
    }
}

void Patcher::CustomTVPRegisterStorageMedia(iTVPStorageMedia* pMedia)
{
    ttstr mediaName;
    pMedia->GetName(mediaName);

    if (mediaName != ttstr(L"steam")) {
        Debugger::Log(L"Hooking storage media \"%s\"", mediaName.c_str());

        void** pVtable = *(void***)pMedia;
        OriginalStorageMediaOpen[pMedia] = (decltype(CustomStorageMediaOpen)*)pVtable[6];
        MemoryUtil::WritePointer(&pVtable[6], CustomStorageMediaOpen);
    }

    OriginalTVPRegisterStorageMedia(pMedia);
}

void Patcher::CustomTVPUnregisterStorageMedia(iTVPStorageMedia* pMedia)
{
    auto it = OriginalStorageMediaOpen.find(pMedia);
    if (it != OriginalStorageMediaOpen.end())
    {
        void** pVtable = *(void***)pMedia;
        MemoryUtil::WritePointer(&pVtable[6], it->second);

        OriginalStorageMediaOpen.erase(it);
    }

    OriginalTVPUnregisterStorageMedia(pMedia);
}

tTJSBinaryStream* Patcher::CustomStorageMediaOpen(iTVPStorageMedia* pMedia, const ttstr& name, tjs_uint32 flags)
{
    static wstring folderPath = Path::GetModuleFolderPath(nullptr);
    bool shouldLog =
        wcsstr(name.c_str(), L"uipsd/") != nullptr ||
        wcsstr(name.c_str(), L"window@") != nullptr;

    const wchar_t* pFilePath = wcschr(name.c_str(), L'/') + 1;
    const std::wstring extension = GetArchiveMemberExtension(pFilePath);
    if (extension == L"mdat" || extension == L"mdatb")
        return OriginalStorageMediaOpen[pMedia](pMedia, name, flags);

    wstring looseFilePath = Path::Combine(Path::Combine(folderPath, L"unencrypted"), StringUtil::Replace<wchar_t>(pFilePath, L'/', L'\\'));
    vector<wstring> urls = BuildOverrideUrls(folderPath, pFilePath);

    for (wstring& url : urls)
    {
        bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
        if (shouldLog)
            Debugger::Log(L"Checked binary-stream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

        if (exists)
        {
            ttstr mediaName;
            pMedia->GetName(mediaName);
            Debugger::Log(L"Redirecting %s://%s to %s", mediaName.c_str(), name.c_str(), url.c_str());

            void* pComStream = Kirikiri::TVPCreateIStream(url.c_str(), flags);
            return Kirikiri::TVPCreateBinaryStreamAdapter(pComStream);
        }
    }

    if (shouldLog)
        Debugger::Log(L"No binary-stream override found for %s", name.c_str());

    tTJSBinaryStream* pStream = OriginalStorageMediaOpen[pMedia](pMedia, name, flags);

    static bool extractionRequested = GetFileAttributes(Path::Combine(folderPath, L"extract-unencrypted.txt").c_str()) != INVALID_FILE_ATTRIBUTES;
    if (pStream != nullptr && extractionRequested)
    {
        Debugger::Log(L"Extracting %s", pFilePath);
        WriteStreamToFile(pStream, looseFilePath);
    }

    return pStream;
}

void Patcher::WriteStreamToFile(tTJSBinaryStream* pStream, const std::wstring& filePath)
{
    vector<BYTE> data;
    data.resize(pStream->GetSize());
    pStream->Read(data.data(), data.size());
    pStream->Seek(0, SEEK_SET);

    Directory::Create(Path::GetDirectoryName(filePath));
    FileStream fileStream(filePath, L"wb+");
    fileStream.Write(data);
}

bool Patcher::CustomGetSignatureVerificationResult()
{
    return true;
}
