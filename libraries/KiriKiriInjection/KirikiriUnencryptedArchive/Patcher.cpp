#include "stdafx.h"

#include <bcrypt.h>
#include <wincodec.h>

#pragma comment(lib, "bcrypt.lib")
#pragma comment(lib, "windowscodecs.lib")

using namespace std;

namespace
{
    bool g_loggedFirstLooseScenarioLine = false;
    constexpr BYTE kWarcTypeXorKey0 = 0x27;
    constexpr BYTE kWarcLengthXorKey[] = { 0x7d, 0x16, 0x9f, 0xf1 };
    constexpr BYTE kTlg5Magic[] = { 'T', 'L', 'G', '5', '.', '0', 0x00, 'r', 'a', 'w', 0x1a };
    constexpr wchar_t kEmbeddedWarcStart[] = L"<<<KANO2_EMBEDDED_WARC";
    constexpr wchar_t kEmbeddedWarcEnd[] = L"<<<END_KANO2_EMBEDDED_WARC";

    struct Tlg5Meta
    {
        BYTE Colors = 0;
        DWORD Width = 0;
        DWORD Height = 0;
        DWORD BlockHeight = 0;
    };

    struct DecodedBitmap
    {
        DWORD Width = 0;
        DWORD Height = 0;
        std::vector<BYTE> Bgra;
    };

    struct CachedFileHash
    {
        FILETIME LastWriteTime{};
        ULONGLONG Size = 0;
        std::wstring HashHex;
    };

    bool StartsWith(const std::wstring& value, const wchar_t* prefix)
    {
        const size_t prefixLength = wcslen(prefix);
        return value.size() >= prefixLength && value.compare(0, prefixLength, prefix) == 0;
    }

    bool EndsWith(const std::wstring& value, const wchar_t* suffix)
    {
        const size_t suffixLength = wcslen(suffix);
        return value.size() >= suffixLength && value.compare(value.size() - suffixLength, suffixLength, suffix) == 0;
    }

    template <class T>
    bool ContainsValue(const std::vector<T>& values, const T& value)
    {
        return std::find(values.begin(), values.end(), value) != values.end();
    }

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
    std::map<std::wstring, CachedFileHash> g_fileHashCache;
    std::set<std::wstring> g_failedTlgOverrideKeys;
    thread_local std::set<std::wstring> g_resolvingTlgOverrideKeys;

    int GetPatchPriority(const wstring& filePath);
    std::wstring UrlToFilePath(const std::wstring& url);
    std::wstring FilePathToStorageUrl(const std::wstring& filePath);
    std::wstring ReadTextFileForLogging(const std::wstring& filePath);
    std::vector<BYTE> ReadFileBytes(const std::wstring& filePath);
    std::wstring GetFileSha256HexOncePerSession(const std::wstring& filePath, const std::vector<BYTE>& fileBytes);
    bool IsCachedTlgFresh(const std::wstring& cachePath, const std::wstring& metaPath, const std::wstring& sourceHash);
    void WriteCacheMetadata(const std::wstring& metaPath, const std::wstring& archiveMemberPath, const std::wstring& sourcePngPath, const std::wstring& sourceHash);
    bool TryReadOriginalTlg5Meta(const std::wstring& archiveStoragePath, Tlg5Meta& meta);
    DecodedBitmap DecodePngAsBgra(const std::vector<BYTE>& pngData);
    std::vector<BYTE> EncodeBgraAsTlg5(const DecodedBitmap& bitmap, const Tlg5Meta& sourceMeta);

    std::wstring SanitizeFileNameFragment(const std::wstring& value)
    {
        std::wstring safe = value;
        for (wchar_t& ch : safe)
        {
            if (ch == L'/' || ch == L'\\' || ch == L':' || ch == L'*' || ch == L'?' || ch == L'"' || ch == L'<' || ch == L'>' || ch == L'|')
                ch = L'_';
        }
        return safe;
    }

    void AppendLe32(std::vector<BYTE>& out, DWORD value)
    {
        out.push_back(static_cast<BYTE>(value & 0xff));
        out.push_back(static_cast<BYTE>((value >> 8) & 0xff));
        out.push_back(static_cast<BYTE>((value >> 16) & 0xff));
        out.push_back(static_cast<BYTE>((value >> 24) & 0xff));
    }

    DWORD ReadLe32(const BYTE* data)
    {
        return static_cast<DWORD>(data[0]) |
            (static_cast<DWORD>(data[1]) << 8) |
            (static_cast<DWORD>(data[2]) << 16) |
            (static_cast<DWORD>(data[3]) << 24);
    }

    bool IsFileNewerOrSame(const std::wstring& lhsPath, const std::wstring& rhsPath)
    {
        WIN32_FILE_ATTRIBUTE_DATA lhsAttr{};
        WIN32_FILE_ATTRIBUTE_DATA rhsAttr{};
        if (!GetFileAttributesExW(lhsPath.c_str(), GetFileExInfoStandard, &lhsAttr))
            return false;
        if (!GetFileAttributesExW(rhsPath.c_str(), GetFileExInfoStandard, &rhsAttr))
            return false;

        return CompareFileTime(&lhsAttr.ftLastWriteTime, &rhsAttr.ftLastWriteTime) >= 0;
    }

    std::wstring FindFirstFileBySuffix(const std::wstring& rootPath, const std::wstring& suffix)
    {
        if (!filesystem::exists(rootPath))
            return L"";

        const std::wstring normalizedSuffix = StringUtil::ToLower(StringUtil::Replace(suffix, L'\\', L'/'));
        for (const auto& entry : filesystem::recursive_directory_iterator(rootPath))
        {
            if (!entry.is_regular_file())
                continue;

            const std::wstring path = entry.path().wstring();
            const std::wstring normalizedPath = StringUtil::ToLower(StringUtil::Replace(path, L'\\', L'/'));
            if (normalizedPath.size() >= normalizedSuffix.size() &&
                normalizedPath.compare(normalizedPath.size() - normalizedSuffix.size(), normalizedSuffix.size(), normalizedSuffix) == 0)
            {
                return path;
            }
        }

        return L"";
    }

    std::wstring GetStorageContainerUrl(const std::wstring& storageTarget)
    {
        size_t separator = storageTarget.find(L'>');
        if (separator == std::wstring::npos)
            return storageTarget;

        return storageTarget.substr(0, separator);
    }

    std::wstring CanonicalizeLooseImageArchiveMemberPath(const std::wstring& archiveMemberPath)
    {
        std::wstring normalized = StringUtil::ToLower(StringUtil::Replace<wchar_t>(archiveMemberPath, L'\\', L'/'));
        if (StartsWith(normalized, L"image/"))
            return normalized;

        const std::wstring extension = Path::GetExtension(normalized);
        size_t slashPos = normalized.find_last_of(L'/');
        const std::wstring fileName = slashPos == std::wstring::npos ? normalized : normalized.substr(slashPos + 1);
        const bool imageLike =
            normalized.find(L"/image/") != std::wstring::npos ||
            normalized.find(L"uipsd/") != std::wstring::npos ||
            fileName.find(L"window@") != std::wstring::npos ||
            StartsWith(fileName, L"xx2_");

        if (extension == L"tlg" || (extension.empty() && imageLike))
            return L"image/" + normalized;

        return normalized;
    }

    void AddArchiveExtractPath(std::vector<std::wstring>& archivePaths, const std::wstring& archivePath)
    {
        if (archivePath.empty())
            return;
        if (GetFileAttributesW(archivePath.c_str()) == INVALID_FILE_ATTRIBUTES)
            return;
        if (!ContainsValue(archivePaths, archivePath))
            archivePaths.push_back(archivePath);
    }

    std::vector<std::wstring> GetArchiveExtractPaths(const std::wstring& gameDir, const std::wstring& preferredArchiveUrl)
    {
        std::vector<std::wstring> archivePaths;

        std::wstring preferredArchivePath = UrlToFilePath(GetStorageContainerUrl(preferredArchiveUrl));
        AddArchiveExtractPath(archivePaths, preferredArchivePath);

        std::vector<std::wstring> discoveredArchives;
        for (const auto& entry : filesystem::directory_iterator(gameDir))
        {
            if (!entry.is_regular_file())
                continue;

            const std::wstring extension = StringUtil::ToLower(entry.path().extension().wstring());
            if (extension != L".xp3")
                continue;

            discoveredArchives.push_back(entry.path().wstring());
        }

        std::sort(
            discoveredArchives.begin(),
            discoveredArchives.end(),
            [](const std::wstring& left, const std::wstring& right)
            {
                const int leftPriority = GetPatchPriority(Path::GetFileName(left));
                const int rightPriority = GetPatchPriority(Path::GetFileName(right));
                if (leftPriority != rightPriority)
                    return leftPriority > rightPriority;

                return StringUtil::ToLower(Path::GetFileName(left)) < StringUtil::ToLower(Path::GetFileName(right));
            });

        for (const std::wstring& archivePath : discoveredArchives)
            AddArchiveExtractPath(archivePaths, archivePath);

        return archivePaths;
    }

    bool ReplaceJsonStringField(std::wstring& text, const std::wstring& fieldName, const std::wstring& newValue)
    {
        const std::wstring fieldToken = L"\"" + fieldName + L"\": \"";
        const size_t valueStart = text.find(fieldToken);
        if (valueStart == std::wstring::npos)
            return false;

        const size_t contentStart = valueStart + fieldToken.size();
        const size_t contentEnd = text.find(L'\"', contentStart);
        if (contentEnd == std::wstring::npos)
            return false;

        text.replace(contentStart, contentEnd - contentStart, newValue);
        return true;
    }

    bool WriteUtf8TextFile(const std::wstring& filePath, const std::wstring& text)
    {
        FILE* pFile = _wfopen(filePath.c_str(), L"wb");
        if (pFile == nullptr)
            return false;

        std::string utf8 = StringUtil::ToUTF8(text);
        const bool ok = fwrite(utf8.data(), 1, utf8.size(), pFile) == utf8.size();
        fclose(pFile);
        return ok;
    }

    bool RewriteExtractManifestForPngEdit(const std::wstring& manifestPath, const std::wstring& pngEditPath)
    {
        std::wstring manifestText = ReadTextFileForLogging(manifestPath);
        if (manifestText.empty())
            return false;

        if (!ReplaceJsonStringField(manifestText, L"kind", L"tlg5_image"))
            return false;
        if (!ReplaceJsonStringField(manifestText, L"edit_path", pngEditPath))
            return false;

        return WriteUtf8TextFile(manifestPath, manifestText);
    }

    bool TryBuildCachedTlgFromPng(const std::wstring& archiveMemberPath, const std::wstring& sourcePngPath, const std::wstring& preferredArchiveUrl, std::wstring& cachedTlgPath)
    {
        const std::wstring gameDir = Path::GetModuleFolderPath(nullptr);
        const std::wstring relativeArchivePath = StringUtil::Replace<wchar_t>(archiveMemberPath, L'\\', L'/');
        const std::wstring canonicalArchivePath = CanonicalizeLooseImageArchiveMemberPath(relativeArchivePath);
        const std::wstring cacheRoot = Path::Combine(gameDir, L"patch/__cherryai_tlg_cache");
        const std::wstring cachePath = Path::Combine(cacheRoot, StringUtil::Replace<wchar_t>(canonicalArchivePath, L'/', L'\\'));
        Debugger::Log(
            L"Resolving PNG image override member=%s canonical=%s source=%s preferredArchive=%s",
            archiveMemberPath.c_str(),
            canonicalArchivePath.c_str(),
            sourcePngPath.c_str(),
            preferredArchiveUrl.c_str());

        std::vector<BYTE> sourcePngBytes;
        try
        {
            sourcePngBytes = ReadFileBytes(sourcePngPath);
        }
        catch (const std::exception& ex)
        {
            Debugger::Log(L"Failed to read source PNG %s: %hs", sourcePngPath.c_str(), ex.what());
            return false;
        }

        if (sourcePngBytes.size() >= sizeof(kTlg5Magic) && memcmp(sourcePngBytes.data(), kTlg5Magic, sizeof(kTlg5Magic)) == 0)
        {
            cachedTlgPath = sourcePngPath;
            return true;
        }

        std::wstring sourceHash;
        try
        {
            sourceHash = GetFileSha256HexOncePerSession(sourcePngPath, sourcePngBytes);
        }
        catch (const std::exception& ex)
        {
            Debugger::Log(L"Failed to hash source PNG %s: %hs", sourcePngPath.c_str(), ex.what());
            return false;
        }

        const std::wstring cacheMetaPath = cachePath + L".cherryai-cache.json";
        if (IsCachedTlgFresh(cachePath, cacheMetaPath, sourceHash))
        {
            Debugger::Log(L"Reusing hash-validated cached TLG %s for source PNG %s", cachePath.c_str(), sourcePngPath.c_str());
            cachedTlgPath = cachePath;
            return true;
        }

        if (GetFileAttributesW(cachePath.c_str()) != INVALID_FILE_ATTRIBUTES && IsFileNewerOrSame(cachePath, sourcePngPath))
        {
            WriteCacheMetadata(cacheMetaPath, archiveMemberPath, sourcePngPath, sourceHash);
            Debugger::Log(L"Migrated existing cached TLG %s to hash metadata for source PNG %s", cachePath.c_str(), sourcePngPath.c_str());
            cachedTlgPath = cachePath;
            return true;
        }

        std::vector<std::wstring> sourceMemberPaths;
        sourceMemberPaths.push_back(canonicalArchivePath);
        if (StartsWith(canonicalArchivePath, L"image/"))
            sourceMemberPaths.push_back(canonicalArchivePath.substr(6));
        else if (canonicalArchivePath != relativeArchivePath)
            sourceMemberPaths.push_back(relativeArchivePath);

        Tlg5Meta sourceMeta;
        bool foundMeta = false;
        const std::vector<std::wstring> archivePaths = GetArchiveExtractPaths(gameDir, preferredArchiveUrl);
        for (const std::wstring& archivePath : archivePaths)
        {
            const std::wstring archiveUrl = FilePathToStorageUrl(archivePath);
            for (const std::wstring& memberPath : sourceMemberPaths)
            {
                const std::wstring archiveStoragePath = archiveUrl + L">" + memberPath;
                if (TryReadOriginalTlg5Meta(archiveStoragePath, sourceMeta))
                {
                    Debugger::Log(
                        L"Read original TLG5 metadata for %s from %s",
                        archiveMemberPath.c_str(),
                        archiveStoragePath.c_str());
                    foundMeta = true;
                    break;
                }
            }

            if (foundMeta)
                break;
        }

        if (!foundMeta)
        {
            Debugger::Log(L"Failed to locate original TLG5 metadata for %s", archiveMemberPath.c_str());
            return false;
        }

        try
        {
            DecodedBitmap bitmap = DecodePngAsBgra(sourcePngBytes);
            std::vector<BYTE> encoded = EncodeBgraAsTlg5(bitmap, sourceMeta);

            Directory::Create(Path::GetDirectoryName(cachePath));
            {
                FileStream stream(cachePath, L"wb");
                if (!encoded.empty())
                    stream.Write(encoded.data(), static_cast<int>(encoded.size()));
            }

            WriteCacheMetadata(cacheMetaPath, archiveMemberPath, sourcePngPath, sourceHash);
            Debugger::Log(L"Built in-process cached TLG %s from PNG %s", cachePath.c_str(), sourcePngPath.c_str());
            cachedTlgPath = cachePath;
            return true;
        }
        catch (const std::exception& ex)
        {
            Debugger::Log(L"In-process TLG encode failed for %s from %s: %hs", archiveMemberPath.c_str(), sourcePngPath.c_str(), ex.what());
            return false;
        }
        catch (...)
        {
            Debugger::Log(L"In-process TLG encode failed for %s from %s: unknown exception", archiveMemberPath.c_str(), sourcePngPath.c_str());
            return false;
        }
    }

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
        if (!StartsWith(url, prefix) || url.find(L'>') != std::wstring::npos)
            return L"";

        std::wstring path = url.substr(wcslen(prefix));
        path = StringUtil::Replace(path, L'/', L'\\');
        if (path.size() >= 2 && path[1] == L'\\')
            path.insert(1, L":");
        return path;
    }

    std::wstring FilePathToStorageUrl(const std::wstring& filePath)
    {
        std::wstring normalized = Path::GetFullPath(filePath);
        normalized = StringUtil::Replace(normalized, L'\\', L'/');

        if (normalized.size() >= 2 && normalized[1] == L':')
        {
            std::wstring url = L"file://./";
            url.push_back(static_cast<wchar_t>(towlower(normalized[0])));
            url.append(normalized.substr(2));
            return url;
        }

        return L"file://./" + normalized;
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
        const long long streamSize = stream.Size();
        if (streamSize < 0 || streamSize > INT_MAX)
            throw std::exception("file is too large to read into a single buffer");

        std::vector<BYTE> data;
        data.resize(static_cast<size_t>(streamSize));
        if (!data.empty())
            stream.ReadBytes(data.data(), static_cast<int>(data.size()));
        return data;
    }

    std::string BytesToHex(const BYTE* data, size_t size)
    {
        static constexpr char kHex[] = "0123456789abcdef";
        std::string out;
        out.reserve(size * 2);
        for (size_t index = 0; index < size; index++)
        {
            out.push_back(kHex[data[index] >> 4]);
            out.push_back(kHex[data[index] & 0x0f]);
        }
        return out;
    }

    std::wstring ToWideAscii(const std::string& value)
    {
        return std::wstring(value.begin(), value.end());
    }

    bool TryGetFileIdentity(const std::wstring& filePath, FILETIME& lastWriteTime, ULONGLONG& size)
    {
        WIN32_FILE_ATTRIBUTE_DATA attr{};
        if (!GetFileAttributesExW(filePath.c_str(), GetFileExInfoStandard, &attr))
            return false;

        ULARGE_INTEGER fileSize{};
        fileSize.HighPart = attr.nFileSizeHigh;
        fileSize.LowPart = attr.nFileSizeLow;
        lastWriteTime = attr.ftLastWriteTime;
        size = fileSize.QuadPart;
        return true;
    }

    std::wstring ComputeSha256Hex(const std::vector<BYTE>& data)
    {
        BCRYPT_ALG_HANDLE algorithm = nullptr;
        BCRYPT_HASH_HANDLE hash = nullptr;
        DWORD cbData = 0;
        DWORD objectLength = 0;
        DWORD hashLength = 0;
        std::vector<BYTE> hashObject;
        std::vector<BYTE> hashBytes;

        if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0)
            throw std::exception("BCryptOpenAlgorithmProvider(SHA256) failed");

        auto cleanup = [&]()
        {
            if (hash != nullptr)
                BCryptDestroyHash(hash);
            if (algorithm != nullptr)
                BCryptCloseAlgorithmProvider(algorithm, 0);
        };

        if (BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&objectLength), sizeof(objectLength), &cbData, 0) < 0 ||
            BCryptGetProperty(algorithm, BCRYPT_HASH_LENGTH, reinterpret_cast<PUCHAR>(&hashLength), sizeof(hashLength), &cbData, 0) < 0)
        {
            cleanup();
            throw std::exception("BCryptGetProperty(SHA256) failed");
        }

        hashObject.resize(objectLength);
        hashBytes.resize(hashLength);
        if (BCryptCreateHash(algorithm, &hash, hashObject.data(), objectLength, nullptr, 0, 0) < 0 ||
            (!data.empty() && BCryptHashData(hash, const_cast<PUCHAR>(data.data()), static_cast<ULONG>(data.size()), 0) < 0) ||
            BCryptFinishHash(hash, hashBytes.data(), hashLength, 0) < 0)
        {
            cleanup();
            throw std::exception("BCrypt SHA256 failed");
        }

        cleanup();
        return ToWideAscii(BytesToHex(hashBytes.data(), hashBytes.size()));
    }

    std::wstring GetFileSha256HexOncePerSession(const std::wstring& filePath, const std::vector<BYTE>& fileBytes)
    {
        FILETIME lastWriteTime{};
        ULONGLONG size = 0;
        if (!TryGetFileIdentity(filePath, lastWriteTime, size))
            return ComputeSha256Hex(fileBytes);

        const std::wstring cacheKey = StringUtil::ToLower(filePath);
        auto it = g_fileHashCache.find(cacheKey);
        if (it != g_fileHashCache.end() &&
            CompareFileTime(&it->second.LastWriteTime, &lastWriteTime) == 0 &&
            it->second.Size == size)
        {
            return it->second.HashHex;
        }

        CachedFileHash cached;
        cached.LastWriteTime = lastWriteTime;
        cached.Size = size;
        cached.HashHex = ComputeSha256Hex(fileBytes);
        g_fileHashCache[cacheKey] = cached;
        return cached.HashHex;
    }

    std::wstring ReadJsonStringField(const std::wstring& text, const std::wstring& fieldName)
    {
        const std::wstring fieldToken = L"\"" + fieldName + L"\": \"";
        const size_t valueStart = text.find(fieldToken);
        if (valueStart == std::wstring::npos)
            return L"";

        const size_t contentStart = valueStart + fieldToken.size();
        const size_t contentEnd = text.find(L'\"', contentStart);
        if (contentEnd == std::wstring::npos)
            return L"";

        return text.substr(contentStart, contentEnd - contentStart);
    }

    bool IsCachedTlgFresh(const std::wstring& cachePath, const std::wstring& metaPath, const std::wstring& sourceHash)
    {
        if (GetFileAttributesW(cachePath.c_str()) == INVALID_FILE_ATTRIBUTES ||
            GetFileAttributesW(metaPath.c_str()) == INVALID_FILE_ATTRIBUTES)
            return false;

        const std::wstring metadata = ReadTextFileForLogging(metaPath);
        return ReadJsonStringField(metadata, L"encoder") == L"cherryai-tlg5-raw-v1" &&
            ReadJsonStringField(metadata, L"source_sha256") == sourceHash;
    }

    void WriteCacheMetadata(const std::wstring& metaPath, const std::wstring& archiveMemberPath, const std::wstring& sourcePngPath, const std::wstring& sourceHash)
    {
        std::wstring metadata;
        metadata += L"{\n";
        metadata += L"  \"encoder\": \"cherryai-tlg5-raw-v1\",\n";
        metadata += L"  \"archive_member\": \"" + StringUtil::Replace(archiveMemberPath, L'\\', L'/') + L"\",\n";
        metadata += L"  \"source_png\": \"" + StringUtil::Replace(sourcePngPath, L'\\', L'/') + L"\",\n";
        metadata += L"  \"source_sha256\": \"" + sourceHash + L"\"\n";
        metadata += L"}\n";
        WriteUtf8TextFile(metaPath, metadata);
    }

    bool ReadTlg5Meta(const std::vector<BYTE>& data, Tlg5Meta& meta)
    {
        if (data.size() < sizeof(kTlg5Magic) + 13 || memcmp(data.data(), kTlg5Magic, sizeof(kTlg5Magic)) != 0)
            return false;

        const BYTE* header = data.data() + sizeof(kTlg5Magic);
        meta.Colors = header[0];
        meta.Width = ReadLe32(header + 1);
        meta.Height = ReadLe32(header + 5);
        meta.BlockHeight = ReadLe32(header + 9);
        return (meta.Colors == 3 || meta.Colors == 4) && meta.Width != 0 && meta.Height != 0 && meta.BlockHeight != 0;
    }

    bool TryReadOriginalTlg5Meta(const std::wstring& archiveStoragePath, Tlg5Meta& meta)
    {
        std::vector<BYTE> header;
        if (!Patcher::TryReadOriginalTlg5MetaForCache(archiveStoragePath, header))
            return false;

        return ReadTlg5Meta(header, meta);
    }

    DecodedBitmap DecodePngAsBgra(const std::vector<BYTE>& pngData)
    {
        if (pngData.size() < 8 || memcmp(pngData.data(), "\x89PNG\r\n\x1a\n", 8) != 0)
            throw std::exception("edited TLG image must be a PNG or TLG5 file");

        HRESULT comResult = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        const bool uninitializeCom = SUCCEEDED(comResult);
        if (FAILED(comResult) && comResult != RPC_E_CHANGED_MODE)
            throw std::exception("CoInitializeEx failed for WIC PNG decode");

        IWICImagingFactory* pFactory = nullptr;
        IWICStream* pStream = nullptr;
        IWICBitmapDecoder* pDecoder = nullptr;
        IWICBitmapFrameDecode* pFrame = nullptr;
        IWICFormatConverter* pConverter = nullptr;

        auto cleanup = [&]()
        {
            if (pConverter != nullptr) pConverter->Release();
            if (pFrame != nullptr) pFrame->Release();
            if (pDecoder != nullptr) pDecoder->Release();
            if (pStream != nullptr) pStream->Release();
            if (pFactory != nullptr) pFactory->Release();
            if (uninitializeCom)
                CoUninitialize();
        };

        HRESULT hr = CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&pFactory));
        if (SUCCEEDED(hr))
            hr = pFactory->CreateStream(&pStream);
        if (SUCCEEDED(hr))
            hr = pStream->InitializeFromMemory(const_cast<BYTE*>(pngData.data()), static_cast<DWORD>(pngData.size()));
        if (SUCCEEDED(hr))
            hr = pFactory->CreateDecoderFromStream(pStream, nullptr, WICDecodeMetadataCacheOnDemand, &pDecoder);
        if (SUCCEEDED(hr))
            hr = pDecoder->GetFrame(0, &pFrame);
        if (SUCCEEDED(hr))
            hr = pFactory->CreateFormatConverter(&pConverter);
        if (SUCCEEDED(hr))
            hr = pConverter->Initialize(pFrame, GUID_WICPixelFormat32bppBGRA, WICBitmapDitherTypeNone, nullptr, 0.0, WICBitmapPaletteTypeCustom);

        DecodedBitmap bitmap;
        if (SUCCEEDED(hr))
        {
            UINT width = 0;
            UINT height = 0;
            hr = pConverter->GetSize(&width, &height);
            bitmap.Width = width;
            bitmap.Height = height;
        }
        if (SUCCEEDED(hr) && (bitmap.Width == 0 || bitmap.Height == 0))
            hr = E_INVALIDARG;
        if (SUCCEEDED(hr))
        {
            const DWORD stride = bitmap.Width * 4;
            bitmap.Bgra.resize(static_cast<size_t>(stride) * bitmap.Height);
            hr = pConverter->CopyPixels(nullptr, stride, static_cast<UINT>(bitmap.Bgra.size()), bitmap.Bgra.data());
        }

        cleanup();
        if (FAILED(hr))
            throw std::exception("WIC PNG decode failed");

        return bitmap;
    }

    std::vector<BYTE> EncodeBgraAsTlg5(const DecodedBitmap& bitmap, const Tlg5Meta& sourceMeta)
    {
        const DWORD blockHeight = max<DWORD>(sourceMeta.BlockHeight, 1);
        bool hasAlpha = sourceMeta.Colors == 4;
        for (size_t offset = 3; !hasAlpha && offset < bitmap.Bgra.size(); offset += 4)
            hasAlpha = bitmap.Bgra[offset] != 0xff;

        const size_t colors = hasAlpha ? 4 : 3;
        const DWORD blockCount = (bitmap.Height - 1) / blockHeight + 1;
        std::vector<BYTE> out;
        out.reserve(sizeof(kTlg5Magic) + 13 + static_cast<size_t>(bitmap.Width) * bitmap.Height * colors + blockCount * colors * 5);
        out.insert(out.end(), std::begin(kTlg5Magic), std::end(kTlg5Magic));
        out.push_back(static_cast<BYTE>(colors));
        AppendLe32(out, bitmap.Width);
        AppendLe32(out, bitmap.Height);
        AppendLe32(out, blockHeight);
        for (DWORD index = 0; index < blockCount; index++)
            AppendLe32(out, 0);

        std::vector<BYTE> previousLine;
        const size_t width = bitmap.Width;
        for (DWORD yBlock = 0; yBlock < bitmap.Height; yBlock += blockHeight)
        {
            const DWORD yLimit = min<DWORD>(yBlock + blockHeight, bitmap.Height);
            const size_t rows = yLimit - yBlock;
            std::vector<std::vector<BYTE>> channels(colors);
            for (std::vector<BYTE>& channel : channels)
                channel.reserve(rows * width);

            for (DWORD y = yBlock; y < yLimit; y++)
            {
                BYTE leftB = 0;
                BYTE leftG = 0;
                BYTE leftR = 0;
                BYTE leftA = 0;
                std::vector<BYTE> line;
                line.reserve(width * 4);

                for (size_t x = 0; x < width; x++)
                {
                    const size_t src = (static_cast<size_t>(y) * width + x) * 4;
                    const BYTE b = bitmap.Bgra[src];
                    const BYTE g = bitmap.Bgra[src + 1];
                    const BYTE r = bitmap.Bgra[src + 2];
                    const BYTE a = bitmap.Bgra[src + 3];

                    const size_t upperOffset = x * 4;
                    const BYTE upperB = previousLine.empty() ? 0 : previousLine[upperOffset];
                    const BYTE upperG = previousLine.empty() ? 0 : previousLine[upperOffset + 1];
                    const BYTE upperR = previousLine.empty() ? 0 : previousLine[upperOffset + 2];
                    const BYTE upperA = previousLine.empty() ? 0 : previousLine[upperOffset + 3];

                    const BYTE residualB = static_cast<BYTE>(b - upperB);
                    const BYTE residualG = static_cast<BYTE>(g - upperG);
                    const BYTE residualR = static_cast<BYTE>(r - upperR);
                    const BYTE residualA = static_cast<BYTE>(a - upperA);
                    const BYTE deltaG = static_cast<BYTE>(residualG - leftG);
                    const BYTE deltaBPlusG = static_cast<BYTE>(residualB - leftB);
                    const BYTE deltaRPlusG = static_cast<BYTE>(residualR - leftR);

                    channels[0].push_back(static_cast<BYTE>(deltaBPlusG - deltaG));
                    channels[1].push_back(deltaG);
                    channels[2].push_back(static_cast<BYTE>(deltaRPlusG - deltaG));
                    if (colors == 4)
                        channels[3].push_back(static_cast<BYTE>(residualA - leftA));

                    leftB = residualB;
                    leftG = residualG;
                    leftR = residualR;
                    leftA = residualA;
                    line.insert(line.end(), { b, g, r, a });
                }

                previousLine = std::move(line);
            }

            for (const std::vector<BYTE>& channel : channels)
            {
                out.push_back(1);
                AppendLe32(out, static_cast<DWORD>(channel.size()));
                out.insert(out.end(), channel.begin(), channel.end());
            }
        }

        return out;
    }

    std::wstring FormatWin32ErrorMessage(DWORD error)
    {
        if (error == ERROR_SUCCESS)
            return L"success";

        wchar_t* pMessage = nullptr;
        const DWORD flags = FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS;
        DWORD length = FormatMessageW(flags, nullptr, error, 0, reinterpret_cast<wchar_t*>(&pMessage), 0, nullptr);
        std::wstring message;
        if (length != 0 && pMessage != nullptr)
        {
            message.assign(pMessage, pMessage + length);
            LocalFree(pMessage);
            return TrimAsciiWhitespace(message);
        }

        return StringUtil::Format(L"Win32 error %u", error);
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

    bool TryDecodeLooseTextBytes(const std::vector<BYTE>& data, std::wstring& text)
    {
        text.clear();
        if (data.empty())
            return false;

        if (data.size() >= 2 && data[0] == 0xFF && data[1] == 0xFE)
        {
            text.assign(reinterpret_cast<const wchar_t*>(data.data() + 2), (data.size() - 2) / sizeof(wchar_t));
        }
        else if (data.size() >= 2 && data[0] == 0xFE && data[1] == 0xFF)
        {
            text.reserve((data.size() - 2) / 2);
            for (size_t index = 2; index + 1 < data.size(); index += 2)
                text.push_back(static_cast<wchar_t>((data[index] << 8) | data[index + 1]));
        }
        else if (LooksLikeUtf16LeText(data))
        {
            text.assign(reinterpret_cast<const wchar_t*>(data.data()), data.size() / sizeof(wchar_t));
        }
        else
        {
            std::string utf8(reinterpret_cast<const char*>(data.data()), data.size());
            if (utf8.size() >= 3 && (BYTE)utf8[0] == 0xEF && (BYTE)utf8[1] == 0xBB && (BYTE)utf8[2] == 0xBF)
                utf8.erase(0, 3);

            int utf8Length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8.c_str(), static_cast<int>(utf8.size()), nullptr, 0);
            if (utf8Length > 0)
            {
                text.resize(utf8Length);
                MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), static_cast<int>(utf8.size()), text.data(), utf8Length);
            }
            else
            {
                int cp932Length = MultiByteToWideChar(932, 0, reinterpret_cast<const char*>(data.data()), static_cast<int>(data.size()), nullptr, 0);
                if (cp932Length <= 0)
                    return false;

                text.resize(cp932Length);
                MultiByteToWideChar(932, 0, reinterpret_cast<const char*>(data.data()), static_cast<int>(data.size()), text.data(), cp932Length);
            }
        }

        if (!text.empty() && text[0] == 0xFEFF)
            text.erase(text.begin());

        return !text.empty();
    }

    bool TryDecodeLooseMdatEditText(const std::vector<BYTE>& data, std::wstring& text)
    {
        if (!TryDecodeLooseTextBytes(data, text))
            return false;

        return text.find(L"(const)") != std::wstring::npos ||
            text.find(kEmbeddedWarcStart) != std::wstring::npos ||
            text.find(L"マップ名") != std::wstring::npos ||
            text.find(L"グレード名") != std::wstring::npos;
    }

    bool TryDecodeLooseCsvEditText(const std::vector<BYTE>& data, std::wstring& text)
    {
        return TryDecodeLooseTextBytes(data, text);
    }

    size_t ReplaceAllSubstring(std::wstring& text, const std::wstring& from, const std::wstring& to)
    {
        if (from.empty() || from == to)
            return 0;

        size_t replaced = 0;
        size_t searchFrom = 0;
        while (true)
        {
            const size_t found = text.find(from, searchFrom);
            if (found == std::wstring::npos)
                break;

            text.replace(found, from.size(), to);
            searchFrom = found + to.size();
            replaced++;
        }

        return replaced;
    }

    std::wstring NormalizeKnownLooseCsvAliases(const std::wstring& text, size_t& replacedAliases)
    {
        std::wstring normalized = text;
        replacedAliases = 0;

        replacedAliases += ReplaceAllSubstring(
            normalized,
            L"ST_\x30A2\x30EB\x30CF\x30A4\x30C8",
            L"ST_\x30A2\x30EB\x30D0\x30A4\x30C8");
        replacedAliases += ReplaceAllSubstring(
            normalized,
            L"H_\x30EA\x30D2\x30F3\x30AF",
            L"H_\x30EA\x30D3\x30F3\x30B0");

        return normalized;
    }

    std::wstring NormalizeCsvLineEndings(const std::wstring& text)
    {
        std::wstring out;
        out.reserve(text.size() + 8);

        for (size_t index = 0; index < text.size(); index++)
        {
            wchar_t ch = text[index];
            if (ch == L'\r')
            {
                out.push_back(L'\r');
                out.push_back(L'\n');
                if (index + 1 < text.size() && text[index + 1] == L'\n')
                    index++;
            }
            else if (ch == L'\n')
            {
                out.push_back(L'\r');
                out.push_back(L'\n');
            }
            else
            {
                out.push_back(ch);
            }
        }

        return out;
    }

    // This title's NEI CSV reader effectively treats commas as delimiters even inside quotes.
    // Replace quoted commas so translated strings do not shift subsequent columns.
    std::wstring SanitizeQuotedCsvCommasForKrkr(const std::wstring& text, size_t& replacedCount)
    {
        std::wstring out;
        out.reserve(text.size());
        replacedCount = 0;

        bool inQuotes = false;
        for (size_t index = 0; index < text.size(); index++)
        {
            const wchar_t ch = text[index];
            if (ch == L'"')
            {
                out.push_back(ch);

                if (inQuotes && (index + 1) < text.size() && text[index + 1] == L'"')
                {
                    out.push_back(text[index + 1]);
                    index++;
                    continue;
                }

                inQuotes = !inQuotes;
                continue;
            }

            if (inQuotes && ch == L',')
            {
                out.push_back(static_cast<wchar_t>(0xFF0C));
                replacedCount++;
                continue;
            }

            out.push_back(ch);
        }

        return out;
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
        if (StartsWith(result, L"\r\n"))
            result.erase(0, 2);
        else if (StartsWith(result, L"\n"))
            result.erase(0, 1);

        if (EndsWith(result, L"\r\n"))
            result.erase(result.size() - 2);
        else if (EndsWith(result, L"\n"))
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

    constexpr BYTE kNeiIv[16] = {
        0x03, 0x20, 0xD3, 0x92, 0x5F, 0x85, 0xFB, 0xDF,
        0x3A, 0xB7, 0xA2, 0x44, 0x82, 0x6B, 0x11, 0xBF,
    };

    DWORD NeiCrc32(const std::vector<BYTE>& data)
    {
        DWORD crc = 0xFFFFFFFFu;
        for (BYTE value : data)
        {
            crc ^= value;
            for (int bit = 0; bit < 8; bit++)
                crc = (crc & 1) ? (0xEDB88320u ^ (crc >> 1)) : (crc >> 1);
        }

        return ~crc;
    }

    std::vector<BYTE> NeiDeriveKey(const std::wstring& archivePath)
    {
        std::vector<BYTE> key(16, 0x40);
        std::wstring fileName = archivePath;
        size_t slashPos = fileName.find_last_of(L"/\\");
        if (slashPos != std::wstring::npos)
            fileName.erase(0, slashPos + 1);

        size_t dotPos = fileName.find_last_of(L'.');
        if (dotPos != std::wstring::npos)
            fileName.erase(dotPos);

        std::string stemUtf8 = StringUtil::ToUTF8(StringUtil::ToLower(fileName));
        for (size_t index = 0; index < stemUtf8.size(); index++)
            key[index & 15] ^= static_cast<BYTE>(stemUtf8[index]);

        return key;
    }

    bool NeiCtrXor(std::vector<BYTE>& data, const BYTE keyBytes[16])
    {
        BCRYPT_ALG_HANDLE algorithm = nullptr;
        BCRYPT_KEY_HANDLE key = nullptr;
        std::vector<BYTE> keyObject;
        DWORD objectLength = 0;
        DWORD bytesReturned = 0;
        NTSTATUS status = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_AES_ALGORITHM, nullptr, 0);
        if (status < 0)
            return false;

        status = BCryptSetProperty(
            algorithm,
            BCRYPT_CHAINING_MODE,
            reinterpret_cast<PUCHAR>(const_cast<wchar_t*>(BCRYPT_CHAIN_MODE_ECB)),
            static_cast<ULONG>(sizeof(BCRYPT_CHAIN_MODE_ECB)),
            0);
        if (status < 0)
            goto cleanup;

        status = BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&objectLength), sizeof(objectLength), &bytesReturned, 0);
        if (status < 0 || objectLength == 0)
            goto cleanup;

        keyObject.resize(objectLength);
        status = BCryptGenerateSymmetricKey(algorithm, &key, keyObject.data(), static_cast<ULONG>(keyObject.size()), const_cast<PUCHAR>(keyBytes), 16, 0);
        if (status < 0)
            goto cleanup;

        BYTE counter[16];
        memcpy(counter, kNeiIv, sizeof(counter));
        BYTE input[16];
        BYTE output[16];

        for (size_t offset = 0; offset < data.size(); offset += 16)
        {
            size_t chunkSize = min<size_t>(16, data.size() - offset);
            memcpy(input, counter, sizeof(input));
            ULONG bytesWritten = 0;
            status = BCryptEncrypt(key, input, sizeof(input), nullptr, nullptr, 0, output, sizeof(output), &bytesWritten, 0);
            if (status < 0 || bytesWritten != sizeof(output))
                goto cleanup;

            for (size_t index = 0; index < chunkSize; index++)
                data[offset + index] ^= output[index];

            for (int counterIndex = 15; counterIndex >= 0; counterIndex--)
            {
                counter[counterIndex] = static_cast<BYTE>(counter[counterIndex] + 1);
                if (counter[counterIndex] != 0)
                    break;
            }
        }

        status = 0;

    cleanup:
        if (key != nullptr)
            BCryptDestroyKey(key);
        if (algorithm != nullptr)
            BCryptCloseAlgorithmProvider(algorithm, 0);
        return status >= 0;
    }

    bool EncodeNeiCsvText(const std::wstring& editText, const std::wstring& archivePath, const std::vector<BYTE>& subheaderBytes, std::vector<BYTE>& encoded)
    {
        std::wstring text = editText;
        if (!text.empty() && text[0] == 0xFEFF)
            text.erase(text.begin());

        size_t replacedAliases = 0;
        text = NormalizeKnownLooseCsvAliases(text, replacedAliases);
        if (replacedAliases > 0)
        {
            Debugger::Log(
                L"Loose NEI CSV alias normalize: replaced %u known alias typo(s) in %s",
                static_cast<unsigned>(replacedAliases),
                archivePath.c_str());
        }

        text = NormalizeCsvLineEndings(text);
        size_t replacedCommas = 0;
        text = SanitizeQuotedCsvCommasForKrkr(text, replacedCommas);
        if (replacedCommas > 0)
        {
            Debugger::Log(
                L"Loose NEI CSV sanitize: replaced %u quoted comma(s) in %s",
                static_cast<unsigned>(replacedCommas),
                archivePath.c_str());
        }

        int bodyLength = WideCharToMultiByte(932, 0, text.c_str(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
        if (bodyLength <= 0 && !text.empty())
            return false;

        std::vector<BYTE> body;
        body.resize(bodyLength);
        BOOL usedDefaultChar = FALSE;
        WideCharToMultiByte(932, 0, text.c_str(), static_cast<int>(text.size()), reinterpret_cast<char*>(body.data()), bodyLength, nullptr, &usedDefaultChar);
        if (usedDefaultChar)
        {
            Debugger::Log(
                L"warning: %s: edited CSV contains characters not representable in Shift-JIS; they were replaced.",
                archivePath.c_str());
        }

        encoded.assign(20, 0);
        const BYTE defaultSubheader[10] = { '.', 'c', 's', 'v', 0, 0, 0, 0, 0, 0 };
        if (subheaderBytes.size() == sizeof(defaultSubheader))
            memcpy(encoded.data() + 10, subheaderBytes.data(), subheaderBytes.size());
        else
            memcpy(encoded.data() + 10, defaultSubheader, sizeof(defaultSubheader));
        encoded.insert(encoded.end(), body.begin(), body.end());

        DWORD crc = NeiCrc32(std::vector<BYTE>(encoded.begin() + 10, encoded.end()));
        char crcHex[9] = {};
        sprintf_s(crcHex, "%08x", crc);
        memcpy(encoded.data(), crcHex, 8);
        encoded[8] = 0;
        encoded[9] = 0;

        std::vector<BYTE> key = NeiDeriveKey(archivePath);
        return NeiCtrXor(encoded, key.data());
    }

    std::wstring GetArchiveMemberExtension(const wchar_t* pArchivePath)
    {
        return StringUtil::ToLower(Path::GetExtension(pArchivePath));
    }

    void TryLogFirstLooseScenarioLine(const std::wstring& requestedName, const std::wstring& url)
    {
        if (g_loggedFirstLooseScenarioLine)
            return;

        if (!EndsWith(StringUtil::ToLower(requestedName), L".ks"))
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
            if (StartsWith(line, L";") || StartsWith(line, L"*") || StartsWith(line, L"@") || StartsWith(line, L"["))
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

        if (!StartsWith(fileName, L"patch"))
            return 0;

        size_t suffixStart = 5;
        size_t suffixLength = EndsWith(fileName, L".xp3") ? fileName.size() - 9 : fileName.size() - 5;
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

    bool IsNestedPatchArtifactDirectoryName(const std::wstring& directoryName)
    {
        return false;
    }

    bool ShouldUseRecursiveOverrideCandidate(
        const std::wstring& searchRoot,
        const std::wstring& candidatePath);

    void AddFileOverrideUrl(vector<wstring>& urls, const wstring& filePath);

    bool ShouldUseRecursiveOverrideCandidate(
        const std::wstring& searchRoot,
        const std::wstring& candidatePath)
    {
        const std::wstring normalizedRoot = NormalizeStorageTarget(Path::GetFullPath(searchRoot));
        std::wstring normalizedCandidate = NormalizeStorageTarget(Path::GetFullPath(candidatePath));
        if (normalizedCandidate.compare(0, normalizedRoot.size(), normalizedRoot) != 0)
            return true;

        if (normalizedCandidate.size() <= normalizedRoot.size())
            return true;

        size_t relativeStart = normalizedRoot.size();
        if (normalizedCandidate[relativeStart] == L'/')
            relativeStart++;

        const std::wstring relativePath = normalizedCandidate.substr(relativeStart);
        if (relativePath.empty())
            return true;

        const std::vector<std::wstring> segments = StringUtil::Split(relativePath, std::wstring(L"/"));
        if (segments.size() <= 1)
            return true;

        for (size_t i = 0; i + 1 < segments.size(); i++)
        {
            if (IsNestedPatchArtifactDirectoryName(segments[i]))
                return false;
        }

        return true;
    }

    void AddOverrideUrl(vector<wstring>& urls, const wstring& url)
    {
        if (!ContainsValue(urls, url))
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

    void AddRecursiveFileNameOverrideUrls(
        vector<wstring>& urls,
        const wstring& searchRoot,
        const wstring& requestedFileName,
        bool matchStem)
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
            {
                if (!ShouldUseRecursiveOverrideCandidate(searchRoot, candidatePath))
                    continue;

                AddFileOverrideUrl(urls, candidatePath);
            }
        }

        if (!matchStem)
            return;

        auto stemIt = index.by_stem.find(requestedStem);
        if (stemIt != index.by_stem.end())
        {
            for (const std::wstring& candidatePath : stemIt->second)
            {
                if (!ShouldUseRecursiveOverrideCandidate(searchRoot, candidatePath))
                    continue;

                AddFileOverrideUrl(urls, candidatePath);
            }
        }
    }

    void AddPatchFolderOverrideUrls(vector<wstring>& urls, const wstring& patchFolderPath, const wchar_t* pInArchivePath)
    {
        wstring relativePath = StringUtil::Replace<wchar_t>(pInArchivePath, L'/', L'\\');

        const wstring patchSubfolderPath = Path::Combine(patchFolderPath, L"patch");
        const wstring patchDataPath = Path::Combine(patchFolderPath, L"data");
        const wstring patchDataCsvPath = Path::Combine(patchDataPath, L"csv");

        const std::vector<wstring> prioritizedRoots =
        {
            patchSubfolderPath,
            patchDataCsvPath,
            patchDataPath,
            patchFolderPath,
        };

        for (const wstring& root : prioritizedRoots)
        {
            wstring relativeFilePath = Path::Combine(root, relativePath);
            AddFileOverrideUrl(urls, relativeFilePath);
            AddStemMatchedFileOverrideUrls(urls, relativeFilePath);
        }

        const wchar_t* pFileName = wcsrchr(pInArchivePath, L'/');
        if (pFileName != nullptr && *(pFileName + 1) != 0)
        {
            for (const wstring& root : prioritizedRoots)
            {
                wstring fileNamePath = Path::Combine(root, pFileName + 1);
                AddFileOverrideUrl(urls, fileNamePath);
            }
        }

        const wstring requestedFileName = Path::GetFileName(relativePath);
        const bool matchStem = Path::GetExtension(requestedFileName).empty();
        AddRecursiveFileNameOverrideUrls(urls, patchSubfolderPath, requestedFileName, matchStem);
        AddRecursiveFileNameOverrideUrls(urls, patchDataCsvPath, requestedFileName, matchStem);
        AddRecursiveFileNameOverrideUrls(urls, patchDataPath, requestedFileName, matchStem);
        AddRecursiveFileNameOverrideUrls(urls, patchFolderPath, requestedFileName, matchStem);
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
        static bool loggedPatchFolders = false;

        vector<wstring> patchFolders;
        for (const auto& entry : filesystem::directory_iterator(folderPath))
        {
            if (!entry.is_directory())
                continue;

            wstring fileName = StringUtil::ToLower(entry.path().filename().wstring());
            if (GetPatchPriority(fileName) > 0)
                patchFolders.push_back(entry.path().wstring());
        }

        std::sort(
            patchFolders.begin(),
            patchFolders.end(),
            [](const wstring& left, const wstring& right)
            {
                return GetPatchPriority(left) > GetPatchPriority(right);
            });

        for (const wstring& patchFolder : patchFolders)
            AddPatchFolderOverrideUrls(urls, patchFolder, pInArchivePath);

        if (!loggedPatchFolders)
        {
            loggedPatchFolders = true;
            Debugger::Log(
                L"Patch override roots in %s: %u",
                folderPath.c_str(),
                static_cast<unsigned int>(patchFolders.size()));
            for (const wstring& patchFolder : patchFolders)
                Debugger::Log(L"Patch override root priority=%d path=%s", GetPatchPriority(patchFolder), patchFolder.c_str());
        }

        return urls;
    }
}

bool Patcher::TryReadOriginalNeiSubheader(const std::wstring& archivePath, std::vector<BYTE>& subheader)
{
    subheader.clear();

    void* pComStream = OriginalTVPCreateIStream(ttstr(archivePath.c_str()), 0);
    if (pComStream == nullptr)
        return false;

    tTJSBinaryStream* pStream = Kirikiri::TVPCreateBinaryStreamAdapter(pComStream);
    if (pStream == nullptr)
        return false;

    const tjs_uint64 size = pStream->GetSize();
    if (size < 20)
        return false;

    std::vector<BYTE> data;
    data.resize(20);
    pStream->Seek(0, SEEK_SET);
    if (pStream->Read(data.data(), static_cast<tjs_uint>(data.size())) != data.size())
        return false;

    subheader.assign(data.begin() + 10, data.begin() + 20);
    return true;
}

bool Patcher::TryReadOriginalTlg5MetaForCache(const std::wstring& archiveStoragePath, std::vector<BYTE>& header)
{
    header.clear();

    if (OriginalTVPCreateIStream == nullptr)
        return false;

    OriginalTlgMetaReadDepth++;
    void* pComStream = OriginalTVPCreateIStream(ttstr(archiveStoragePath.c_str()), 0);
    OriginalTlgMetaReadDepth--;
    if (pComStream == nullptr)
        return false;

    tTJSBinaryStream* pStream = Kirikiri::TVPCreateBinaryStreamAdapter(pComStream);
    if (pStream == nullptr || pStream->GetSize() < sizeof(kTlg5Magic) + 13)
        return false;

    header.resize(sizeof(kTlg5Magic) + 13);
    pStream->Seek(0, SEEK_SET);
    return pStream->Read(header.data(), static_cast<tjs_uint>(header.size())) == header.size();
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

tTJSBinaryStream* Patcher::CreateLooseEncodedNeiStream(const std::wstring& url, const std::wstring& archivePath)
{
    try
    {
        std::vector<BYTE> encoded;
        if (!TryBuildLooseEncodedNeiBytes(url, archivePath, encoded))
            return nullptr;

        Debugger::Log(L"Encoding loose NEI CSV override %s", UrlToFilePath(url).c_str());
        auto* pStream = new VectorBinaryStream(std::move(encoded));
        tTJSBinaryStream::ApplyWrappedVTable(pStream);
        return pStream;
    }
    catch (const std::exception& ex)
    {
        Debugger::Log(L"Loose NEI CSV encode failed for %s: %hs", url.c_str(), ex.what());
        return nullptr;
    }
    catch (...)
    {
        Debugger::Log(L"Loose NEI CSV encode failed for %s: unknown exception", url.c_str());
        return nullptr;
    }
}

bool Patcher::TryBuildLooseEncodedNeiBytes(const std::wstring& url, const std::wstring& archivePath, std::vector<BYTE>& encoded)
{
    encoded.clear();

    const std::wstring filePath = UrlToFilePath(url);
    if (filePath.empty())
    {
        Debugger::Log(L"Loose NEI CSV path decode failed for %s", url.c_str());
        return false;
    }

    if (GetFileAttributes(filePath.c_str()) == INVALID_FILE_ATTRIBUTES)
    {
        Debugger::Log(L"Loose NEI CSV missing for %s => %s", url.c_str(), filePath.c_str());
        return false;
    }

    std::vector<BYTE> fileBytes = ReadFileBytes(filePath);
    std::wstring decodedText;
    if (!TryDecodeLooseCsvEditText(fileBytes, decodedText))
    {
        Debugger::Log(L"Loose NEI CSV decode failed for %s", filePath.c_str());
        return false;
    }

    std::vector<BYTE> subheaderBytes;
    if (!TryReadOriginalNeiSubheader(archivePath, subheaderBytes))
    {
        Debugger::Log(L"Loose NEI CSV subheader READ FAILED for %s, using fallback", archivePath.c_str());
        subheaderBytes = { '.', 'c', 's', 'v', 0, 0, 0, 0, 0, 0 };
    }

    if (!EncodeNeiCsvText(decodedText, archivePath, subheaderBytes, encoded))
    {
        Debugger::Log(L"Loose NEI CSV encode frame failed for %s", filePath.c_str());
        return false;
    }

    return true;
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
    LONG result = DetourTransactionCommit();
    if (result != NO_ERROR)
        Debugger::Log(L"Failed to hook TVPGetPlacedPath() detour result=%ld", result);

    Debugger::Log(L"Hooked TVPGetPlacedPath()");
}

void Patcher::PatchIStreamCreation()
{
    Kirikiri::ResolveScriptExport(L"IStream * ::TVPCreateIStream(const ttstr &,tjs_uint32)", OriginalTVPCreateIStream);

    DetourTransactionBegin();
    DetourAttach((void**)&OriginalTVPCreateIStream, CustomTVPCreateIStream);
    LONG result = DetourTransactionCommit();
    if (result != NO_ERROR)
        Debugger::Log(L"Failed to hook TVPCreateIStream() detour result=%ld", result);

    Debugger::Log(L"Hooked TVPCreateIStream()");
}

void Patcher::PatchTextStreamCreation()
{
    Kirikiri::ResolveScriptExport(L"iTJSTextReadStream * ::TVPCreateTextStreamForRead(const ttstr &,const ttstr &)", OriginalTVPCreateTextStreamForRead);

    DetourTransactionBegin();
    DetourAttach((void**)&OriginalTVPCreateTextStreamForRead, CustomTVPCreateTextStreamForRead);
    LONG result = DetourTransactionCommit();
    if (result != NO_ERROR)
        Debugger::Log(L"Failed to hook TVPCreateTextStreamForRead() detour result=%ld", result);

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

wstring Patcher::GetLooseCsvSearchPath(const wstring& archiveMemberPath)
{
    if (StringUtil::ToLower(Path::GetExtension(archiveMemberPath)) == L"nei")
        return Path::ChangeExtension(archiveMemberPath, L"csv");

    return archiveMemberPath;
}

bool Patcher::IsLooseImageRequest(const std::wstring& archiveMemberPath)
{
    const std::wstring lowerPath = StringUtil::ToLower(archiveMemberPath);
    const std::wstring extension = Path::GetExtension(lowerPath);
    if (extension == L"tlg")
        return true;
    if (!extension.empty())
        return false;

    const std::wstring fileName = Path::GetFileName(lowerPath);
    return StartsWith(lowerPath, L"image/") ||
        lowerPath.find(L"/image/") != std::wstring::npos ||
        lowerPath.find(L"uipsd/") != std::wstring::npos ||
        fileName.find(L"window@") != std::wstring::npos ||
        StartsWith(fileName, L"xx2_");
}

vector<wstring> Patcher::GetLooseImageSearchPaths(const wstring& archiveMemberPath)
{
    vector<wstring> searchPaths;
    const std::wstring extension = StringUtil::ToLower(Path::GetExtension(archiveMemberPath));
    const bool hasExtension = !extension.empty();
    if (extension != L"tlg" && (hasExtension || !IsLooseImageRequest(archiveMemberPath)))
    {
        searchPaths.push_back(archiveMemberPath);
        return searchPaths;
    }

    auto addSearchPath = [&searchPaths](const std::wstring& candidate)
    {
        if (!ContainsValue(searchPaths, candidate))
            searchPaths.push_back(candidate);
    };

    if (extension == L"tlg")
    {
        addSearchPath(Path::ChangeExtension(archiveMemberPath, L"png"));
        addSearchPath(archiveMemberPath + L".png");
        addSearchPath(archiveMemberPath);
        return searchPaths;
    }

    addSearchPath(archiveMemberPath + L".png");
    addSearchPath(archiveMemberPath + L".tlg.png");
    addSearchPath(archiveMemberPath + L".tlg");
    addSearchPath(archiveMemberPath);

    return searchPaths;
}

bool Patcher::WouldRedirectToSelf(const std::wstring& candidateUrl, const std::wstring& currentTarget)
{
    if (candidateUrl.empty() || currentTarget.empty())
        return false;

    return NormalizeStorageTarget(candidateUrl) == NormalizeStorageTarget(currentTarget);
}

bool Patcher::IsRawPngStorageUrl(const std::wstring& url)
{
    const std::wstring filePath = UrlToFilePath(url);
    if (filePath.empty())
        return false;

    const std::wstring lowerUrl = StringUtil::ToLower(url);
        if (!EndsWith(lowerUrl, L".png") && !EndsWith(lowerUrl, L".tlg.png"))
        return false;

    try
    {
        const std::vector<BYTE> data = ReadFileBytes(filePath);
        constexpr BYTE pngHeader[] = { 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a };
        return data.size() >= sizeof(pngHeader) && memcmp(data.data(), pngHeader, sizeof(pngHeader)) == 0;
    }
    catch (...)
    {
        return false;
    }
}

bool Patcher::TryResolveTlgOverrideUrl(const std::wstring& candidateUrl, const std::wstring& archiveMemberPath, const std::wstring& sourceArchiveUrl, std::wstring& resolvedUrl)
{
    resolvedUrl = candidateUrl;
    const std::wstring canonicalArchiveMemberPath = CanonicalizeLooseImageArchiveMemberPath(archiveMemberPath);
    const std::wstring failureKey = NormalizeStorageTarget(canonicalArchiveMemberPath + L"|" + candidateUrl + L"|" + sourceArchiveUrl);
    const std::wstring resolutionKey = NormalizeStorageTarget(canonicalArchiveMemberPath + L"|" + candidateUrl);
    if (g_failedTlgOverrideKeys.find(failureKey) != g_failedTlgOverrideKeys.end())
        return false;

    const std::wstring filePath = UrlToFilePath(candidateUrl);
    if (filePath.empty())
    {
        Debugger::Log(L"Cannot resolve image override %s for %s: candidate is not a file URL", candidateUrl.c_str(), archiveMemberPath.c_str());
        g_failedTlgOverrideKeys.insert(failureKey);
        return false;
    }

    const std::wstring extension = StringUtil::ToLower(Path::GetExtension(filePath));
    if (extension != L"png" && extension != L"tlg")
    {
        Debugger::Log(L"Cannot resolve image override %s for %s: unsupported extension %s", candidateUrl.c_str(), archiveMemberPath.c_str(), extension.c_str());
        g_failedTlgOverrideKeys.insert(failureKey);
        return false;
    }

    if (extension != L"png")
        return true;

    std::wstring cachedTlgPath;
    bool cacheBuilt = false;
    if (g_resolvingTlgOverrideKeys.find(resolutionKey) != g_resolvingTlgOverrideKeys.end())
    {
        Debugger::Log(
            L"Suppressing recursive PNG image override resolution for %s from %s",
            archiveMemberPath.c_str(),
            filePath.c_str());
        return false;
    }

    g_resolvingTlgOverrideKeys.insert(resolutionKey);
    try
    {
        cacheBuilt = TryBuildCachedTlgFromPng(archiveMemberPath, filePath, sourceArchiveUrl, cachedTlgPath);
        g_resolvingTlgOverrideKeys.erase(resolutionKey);
    }
    catch (const std::exception& ex)
    {
        g_resolvingTlgOverrideKeys.erase(resolutionKey);
        Debugger::Log(
            L"Cannot resolve PNG image override %s for %s: cache build threw %hs",
            filePath.c_str(),
            archiveMemberPath.c_str(),
            ex.what());
        g_failedTlgOverrideKeys.insert(failureKey);
        return false;
    }
    catch (...)
    {
        g_resolvingTlgOverrideKeys.erase(resolutionKey);
        Debugger::Log(
            L"Cannot resolve PNG image override %s for %s: cache build threw unknown exception",
            filePath.c_str(),
            archiveMemberPath.c_str());
        g_failedTlgOverrideKeys.insert(failureKey);
        return false;
    }

    if (!cacheBuilt)
    {
        Debugger::Log(L"Cannot resolve PNG image override %s for %s: cache build failed", filePath.c_str(), archiveMemberPath.c_str());
        g_failedTlgOverrideKeys.insert(failureKey);
        return false;
    }

    resolvedUrl = FilePathToStorageUrl(cachedTlgPath);
    Debugger::Log(L"Using cached TLG for %s from PNG %s => %s", archiveMemberPath.c_str(), filePath.c_str(), resolvedUrl.c_str());
    return true;
}

ttstr Patcher::CustomTVPGetPlacedPath(const ttstr& name)
{
    ttstr placedPath = OriginalTVPGetPlacedPath(name);
    const std::wstring sourceArchiveUrl = GetStorageContainerUrl(placedPath.c_str());

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
    const bool isLooseImage = IsLooseImageRequest(pInArchivePath);
    if (extension == L"mdat" || extension == L"mdatb" || extension == L"nei")
        return placedPath;

    static wstring folderPath = Path::GetModuleFolderPath(nullptr);
    vector<wstring> urls;
    if (isLooseImage)
    {
        const vector<wstring> imageSearchPaths = GetLooseImageSearchPaths(pInArchivePath);
        for (const wstring& searchPath : imageSearchPaths)
        {
            vector<wstring> candidates = BuildOverrideUrls(folderPath, searchPath.c_str());
            for (const wstring& candidate : candidates)
                AddOverrideUrl(urls, candidate);
        }
    }
    else
    {
        urls = BuildOverrideUrls(folderPath, pInArchivePath);
    }

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

            std::wstring finalUrl = url;
            if (isLooseImage && !TryResolveTlgOverrideUrl(url, pInArchivePath, sourceArchiveUrl, finalUrl))
            {
                if (shouldLog)
                    Debugger::Log(L"Skipping unresolved image placed-path request %s -> %s", name.c_str(), url.c_str());
                continue;
            }

            Debugger::Log(L"Redirecting placed path %s to %s", name.c_str(), finalUrl.c_str());
            return ttstr(finalUrl.c_str());
        }
    }

    if (shouldLog)
        Debugger::Log(L"No override found for placed path %s", placedPath.c_str());

    return placedPath;
}

void* Patcher::CustomTVPCreateIStream(const ttstr& name, tjs_uint32 flags)
{
    ttstr placedPath = OriginalTVPGetPlacedPath(name);
    const std::wstring sourceArchiveUrl = GetStorageContainerUrl(placedPath.c_str());
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
        const bool isNei = extension == L"nei";
        const bool isLooseImage = IsLooseImageRequest(pInArchivePath);
        vector<wstring> urls;
        if (isNei)
        {
            const std::wstring csvSearchPath = GetLooseCsvSearchPath(pInArchivePath);
            urls = BuildOverrideUrls(folderPath, csvSearchPath.c_str());
        }
        else if (isLooseImage)
        {
            const vector<wstring> imageSearchPaths = GetLooseImageSearchPaths(pInArchivePath);
            for (const wstring& searchPath : imageSearchPaths)
            {
                vector<wstring> candidates = BuildOverrideUrls(folderPath, searchPath.c_str());
                for (const wstring& candidate : candidates)
                    AddOverrideUrl(urls, candidate);
            }
        }
        else
        {
            urls = BuildOverrideUrls(folderPath, pInArchivePath);
        }

        for (const wstring& url : urls)
        {
            bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
            if (shouldLog)
                Debugger::Log(L"Checked istream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

            if (!exists)
                continue;

            if (WouldRedirectToSelf(url, placedPath.c_str()) || WouldRedirectToSelf(url, name.c_str()))
            {
                if (shouldLog)
                    Debugger::Log(L"Skipping istream self-redirect %s", url.c_str());
                continue;
            }

            std::wstring finalUrl = url;
            if (isLooseImage && !TryResolveTlgOverrideUrl(url, pInArchivePath, sourceArchiveUrl, finalUrl))
            {
                if (shouldLog)
                    Debugger::Log(L"Skipping unresolved image istream request %s -> %s", name.c_str(), url.c_str());
                continue;
            }

            Debugger::Log(L"Redirecting istream %s to %s", name.c_str(), finalUrl.c_str());
            if (isNei)
            {
                if (shouldLog)
                    Debugger::Log(L"Attempting loose NEI CSV encode for %s", url.c_str());

                std::vector<BYTE> encoded;
                if (TryBuildLooseEncodedNeiBytes(url, pInArchivePath, encoded))
                {
                    const std::wstring moduleDir = Path::GetModuleFolderPath(nullptr);
                    const std::wstring tempFolder = Path::Combine(moduleDir, L"patch/__cherryai_nei_tmp");
                    const std::wstring tempFilePath = Path::Combine(tempFolder, Path::GetFileName(pInArchivePath));

                    Directory::Create(tempFolder);

                    try
                    {
                        {
                            FileStream stream(tempFilePath, L"wb");
                            if (!encoded.empty())
                                stream.Write(encoded.data(), static_cast<int>(encoded.size()));
                        }

                        const std::wstring tempUrl = FilePathToStorageUrl(tempFilePath);
                        if (void* pComStream = OriginalTVPCreateIStream(ttstr(tempUrl.c_str()), flags))
                        {
                            if (shouldLog)
                                Debugger::Log(L"Loose NEI CSV encode returned temp-file IStream for %s", url.c_str());
                            return pComStream;
                        }

                        DWORD error = GetLastError();
                        Debugger::Log(
                            L"OriginalTVPCreateIStream failed for temp NEI %s (error=%u: %s)",
                            tempUrl.c_str(),
                            error,
                            FormatWin32ErrorMessage(error).c_str());
                    }
                    catch (const std::exception& ex)
                    {
                        Debugger::Log(L"Failed to write temp NEI file %s: %hs", tempFilePath.c_str(), ex.what());
                    }
                }

                if (tTJSBinaryStream* pEncodedStream = CreateLooseEncodedNeiStream(url, pInArchivePath))
                {
                    if (shouldLog)
                        Debugger::Log(L"Loose NEI CSV encode returned binary stream fallback for %s", url.c_str());
                    return pEncodedStream;
                }

                if (shouldLog)
                    Debugger::Log(L"NEI encode failed for %s, trying raw NEI fallback", url.c_str());
                continue;
            }

            if (void* pComStream = OriginalTVPCreateIStream(finalUrl.c_str(), flags))
                return pComStream;

            DWORD error = GetLastError();
            Debugger::Log(
                L"OriginalTVPCreateIStream failed for %s (error=%u: %s)",
                finalUrl.c_str(),
                error,
                FormatWin32ErrorMessage(error).c_str());
            continue;
        }

        if (isNei)
        {
            vector<wstring> rawNeiUrls = BuildOverrideUrls(folderPath, pInArchivePath);

            for (const wstring& url : rawNeiUrls)
            {
                bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
                if (shouldLog)
                    Debugger::Log(L"Checked istream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

                if (!exists)
                    continue;

                if (WouldRedirectToSelf(url, placedPath.c_str()) || WouldRedirectToSelf(url, name.c_str()))
                {
                    if (shouldLog)
                        Debugger::Log(L"Skipping istream self-redirect %s", url.c_str());
                    continue;
                }

                Debugger::Log(L"Redirecting istream %s to %s", name.c_str(), url.c_str());
                if (void* pComStream = OriginalTVPCreateIStream(url.c_str(), flags))
                    return pComStream;

                DWORD error = GetLastError();
                Debugger::Log(
                    L"OriginalTVPCreateIStream failed for %s (error=%u: %s)",
                    url.c_str(),
                    error,
                    FormatWin32ErrorMessage(error).c_str());
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
    const std::wstring sourceArchiveUrl = GetStorageContainerUrl(placedPath.c_str());
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
    {
        EditMode::OnTextStreamOpened(name.c_str(), placedPath.c_str(), UrlToFilePath(placedPath.c_str()));
        return OriginalTVPCreateTextStreamForRead(name, mode);
    }

    pInArchivePath++;

    const std::wstring extension = GetArchiveMemberExtension(pInArchivePath);
    if (extension == L"mdat" || extension == L"mdatb")
        return OriginalTVPCreateTextStreamForRead(name, mode);

    static wstring folderPath = Path::GetModuleFolderPath(nullptr);
    const bool isNei = extension == L"nei";
    const bool isLooseImage = IsLooseImageRequest(pInArchivePath);
    vector<wstring> urls;
    if (isNei)
    {
        const std::wstring csvSearchPath = GetLooseCsvSearchPath(pInArchivePath);
        urls = BuildOverrideUrls(folderPath, csvSearchPath.c_str());
    }
    else if (isLooseImage)
    {
        const vector<wstring> imageSearchPaths = GetLooseImageSearchPaths(pInArchivePath);
        for (const wstring& searchPath : imageSearchPaths)
        {
            vector<wstring> candidates = BuildOverrideUrls(folderPath, searchPath.c_str());
            for (const wstring& candidate : candidates)
                AddOverrideUrl(urls, candidate);
        }
    }
    else
    {
        urls = BuildOverrideUrls(folderPath, pInArchivePath);
    }

    for (const wstring& url : urls)
    {
        bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
        if (shouldLog)
            Debugger::Log(L"Checked text-stream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

        if (!exists)
            continue;

        if (WouldRedirectToSelf(url, placedPath.c_str()) || WouldRedirectToSelf(url, name.c_str()))
        {
            if (shouldLog)
                Debugger::Log(L"Skipping text-stream self-redirect %s", url.c_str());
            continue;
        }

        std::wstring finalUrl = url;
        if (isLooseImage && !TryResolveTlgOverrideUrl(url, pInArchivePath, sourceArchiveUrl, finalUrl))
        {
            if (shouldLog)
                Debugger::Log(L"Skipping unresolved image text-stream request %s -> %s", name.c_str(), url.c_str());
            continue;
        }

        TryLogFirstLooseScenarioLine(name.c_str(), finalUrl);
        EditMode::OnTextStreamOpened(name.c_str(), placedPath.c_str(), UrlToFilePath(finalUrl));
        Debugger::Log(L"Redirecting text stream %s to %s", name.c_str(), finalUrl.c_str());
        if (void* pTextStream = OriginalTVPCreateTextStreamForRead(finalUrl.c_str(), mode))
            return pTextStream;

        DWORD error = GetLastError();
        Debugger::Log(
            L"OriginalTVPCreateTextStreamForRead failed for %s (error=%u: %s)",
            finalUrl.c_str(),
            error,
            FormatWin32ErrorMessage(error).c_str());
        continue;
    }

    if (isNei)
    {
        vector<wstring> rawNeiUrls = BuildOverrideUrls(folderPath, pInArchivePath);

        for (const wstring& url : rawNeiUrls)
        {
            bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
            if (shouldLog)
                Debugger::Log(L"Checked text-stream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

            if (!exists)
                continue;

            if (WouldRedirectToSelf(url, placedPath.c_str()) || WouldRedirectToSelf(url, name.c_str()))
            {
                if (shouldLog)
                    Debugger::Log(L"Skipping text-stream self-redirect %s", url.c_str());
                continue;
            }

            TryLogFirstLooseScenarioLine(name.c_str(), url);
            EditMode::OnTextStreamOpened(name.c_str(), placedPath.c_str(), UrlToFilePath(url));
            Debugger::Log(L"Redirecting text stream %s to %s", name.c_str(), url.c_str());
            if (void* pTextStream = OriginalTVPCreateTextStreamForRead(url.c_str(), mode))
                return pTextStream;

            DWORD error = GetLastError();
            Debugger::Log(
                L"OriginalTVPCreateTextStreamForRead failed for %s (error=%u: %s)",
                url.c_str(),
                error,
                FormatWin32ErrorMessage(error).c_str());
        }
    }

    if (shouldLog)
        Debugger::Log(L"No text-stream override found for %s", placedPath.c_str());

    EditMode::OnTextStreamOpened(name.c_str(), placedPath.c_str(), L"");
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

    const wchar_t* pFilePath = name.c_str();
    const wchar_t* pSlash = wcschr(name.c_str(), L'/');
    if (pSlash != nullptr && *(pSlash + 1) != 0)
        pFilePath = pSlash + 1;

    const std::wstring extension = GetArchiveMemberExtension(pFilePath);
    const bool isLooseImage = IsLooseImageRequest(pFilePath);
    if (extension == L"mdat" || extension == L"mdatb" || extension == L"nei")
        return OriginalStorageMediaOpen[pMedia](pMedia, name, flags);

    wstring looseFilePath = Path::Combine(Path::Combine(folderPath, L"unencrypted"), StringUtil::Replace<wchar_t>(pFilePath, L'/', L'\\'));
    vector<wstring> urls;
    if (isLooseImage)
    {
        const vector<wstring> imageSearchPaths = GetLooseImageSearchPaths(pFilePath);
        for (const wstring& searchPath : imageSearchPaths)
        {
            vector<wstring> candidates = BuildOverrideUrls(folderPath, searchPath.c_str());
            for (const wstring& candidate : candidates)
                AddOverrideUrl(urls, candidate);
        }
    }
    else
    {
        urls = BuildOverrideUrls(folderPath, pFilePath);
    }

    for (wstring& url : urls)
    {
        bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
        if (shouldLog)
            Debugger::Log(L"Checked binary-stream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

        if (exists)
        {
            std::wstring finalUrl = url;
            if (isLooseImage && !TryResolveTlgOverrideUrl(url, pFilePath, L"", finalUrl))
            {
                if (shouldLog)
                    Debugger::Log(L"Skipping unresolved image binary-stream request %s -> %s", name.c_str(), url.c_str());
                continue;
            }

            ttstr mediaName;
            pMedia->GetName(mediaName);
            Debugger::Log(L"Redirecting %s://%s to %s", mediaName.c_str(), name.c_str(), finalUrl.c_str());

            void* pComStream = Kirikiri::TVPCreateIStream(finalUrl.c_str(), flags);
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
    const tjs_uint64 streamSize = pStream->GetSize();
    if (streamSize > UINT_MAX)
        throw std::exception("stream is too large to write into a single buffer");

    vector<BYTE> data;
    data.resize(static_cast<size_t>(streamSize));
    if (!data.empty())
        pStream->Read(data.data(), static_cast<tjs_uint>(data.size()));
    pStream->Seek(0, SEEK_SET);

    Directory::Create(Path::GetDirectoryName(filePath));
    FileStream fileStream(filePath, L"wb+");
    fileStream.Write(data);
}

bool Patcher::CustomGetSignatureVerificationResult()
{
    return true;
}
