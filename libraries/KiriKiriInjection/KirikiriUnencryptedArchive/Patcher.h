#pragma once

class Patcher
{
    friend CompilerHelper;

public:
    static bool                 PatchSignatureCheck                     (HMODULE hModule);

    static void                 PatchXP3StreamCreation                  ();
    static void                 PatchPlacedPathLookup                   ();
    static void                 PatchIStreamCreation                    ();
    static void                 PatchTextStreamCreation                 ();
    static void                 PatchAutoPathExports                    ();
    static void                 PatchStorageMediaRegistration           ();

private:
    static tTJSBinaryStream*    CreateLooseEncodedMdatStream           (const std::wstring& url, const std::vector<BYTE>& originalHeader);
    static tTJSBinaryStream*    CreateLooseEncodedNeiStream            (const std::wstring& url, const std::wstring& archivePath);
    static bool                 TryBuildLooseEncodedNeiBytes           (const std::wstring& url, const std::wstring& archivePath, std::vector<BYTE>& encoded);
    static bool                 TryReadOriginalNeiSubheader            (const std::wstring& archivePath, std::vector<BYTE>& subheader);
    static bool                 IsLooseImageRequest                    (const std::wstring& archiveMemberPath);
    static bool                 IsRawPngStorageUrl                      (const std::wstring& url);
    static bool                 TryResolveTlgOverrideUrl                (const std::wstring& candidateUrl, const std::wstring& archiveMemberPath, const std::wstring& sourceArchiveUrl, std::wstring& resolvedUrl);
    static bool                 WouldRedirectToSelf                    (const std::wstring& candidateUrl, const std::wstring& currentTarget);
    static std::wstring         GetLooseCsvSearchPath                  (const std::wstring& archiveMemberPath);
    static std::vector<std::wstring> GetLooseImageSearchPaths          (const std::wstring& archiveMemberPath);
    static ttstr __stdcall      CustomTVPGetPlacedPath                  (const ttstr& name);
    static void* __stdcall      CustomTVPCreateIStream                  (const ttstr& name, tjs_uint32 flags);
    static void* __stdcall      CustomTVPCreateTextStreamForRead        (const ttstr& name, const ttstr& mode);
    static void __stdcall       CustomTVPAddAutoPath                    (const ttstr& url);
    static void __stdcall       CustomTVPRemoveAutoPath                 (const ttstr& url);

    static void __stdcall       CustomTVPRegisterStorageMedia           (iTVPStorageMedia* pMedia);
    static void __stdcall       CustomTVPUnregisterStorageMedia         (iTVPStorageMedia* pMedia);
    static tTJSBinaryStream*    CustomStorageMediaOpen                  (iTVPStorageMedia* pMedia, const ttstr& name, tjs_uint32 flags);
    static void                 WriteStreamToFile                       (tTJSBinaryStream* pStream, const std::wstring& filePath);
    static std::vector<std::wstring> BuildOverrideUrlsForPath           (const wchar_t* pInArchivePath);

    static bool                 CustomGetSignatureVerificationResult    ();

    template<CompilerType TCompilerType>
    class CustomCreateStreamByIndex
    {
    public:
        static tTJSBinaryStream* Call(tTVPXP3Archive<TCompilerType>* pArchive, tjs_uint idx)
        {
            int itemSize = ((BYTE*)pArchive->ItemVector.end() - (BYTE*)pArchive->ItemVector.begin()) / pArchive->Count;
            auto* pItem = (typename tTVPXP3Archive<TCompilerType>::tArchiveItem*)((BYTE*)pArchive->ItemVector.begin() + idx * itemSize);
            if (pArchive->Name.StartsWith(L"file://"))
            {
                const std::wstring extension = StringUtil::ToLower(Path::GetExtension(pItem->Name.c_str()));
                const bool isNei = extension == L"nei";
                const bool isTlg = extension == L"tlg";
                const bool isLooseImage = IsLooseImageRequest(pItem->Name.c_str());
                
                // NEI files should be handled by CustomTVPCreateIStream instead
                if (isNei)
                    goto archive_default;
                
                const std::wstring csvSearchPath = pItem->Name.c_str();

                const bool shouldLog =
                    wcsstr(pItem->Name.c_str(), L"uipsd/") != nullptr ||
                    wcsstr(pItem->Name.c_str(), L"window@") != nullptr ||
                    wcsstr(pItem->Name.c_str(), L".png") != nullptr ||
                    wcsstr(pItem->Name.c_str(), L".tlg") != nullptr;

                std::vector<std::wstring> urls;
                if (isLooseImage)
                {
                    const std::vector<std::wstring> imageSearchPaths = GetLooseImageSearchPaths(pItem->Name.c_str());
                    for (const std::wstring& searchPath : imageSearchPaths)
                    {
                        std::vector<std::wstring> imageUrls = BuildOverrideUrlsForPath(searchPath.c_str());
                        urls.insert(urls.end(), imageUrls.begin(), imageUrls.end());
                    }
                }
                else
                {
                    urls = BuildOverrideUrlsForPath(csvSearchPath.c_str());
                }
                for (const std::wstring& url : urls)
                {
                    bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
                    if (shouldLog)
                        Debugger::Log(L"Checked archive-stream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

                    if (!exists)
                        continue;

                    const std::wstring currentTarget = std::wstring(pArchive->Name.c_str()) + L">" + pItem->Name.c_str();
                    if (WouldRedirectToSelf(url, currentTarget))
                    {
                        if (shouldLog)
                            Debugger::Log(L"Skipping archive-stream self-redirect %s", url.c_str());
                        continue;
                    }

                    std::wstring finalUrl = url;
                    if (isLooseImage && !TryResolveTlgOverrideUrl(url, pItem->Name.c_str(), pArchive->Name.c_str(), finalUrl))
                    {
                        if (shouldLog)
                            Debugger::Log(L"Skipping unresolved image archive-stream override %s -> %s", pItem->Name.c_str(), url.c_str());
                        continue;
                    }

                    Debugger::Log(L"Redirecting archive stream %s to %s ext=%s", pItem->Name.c_str(), finalUrl.c_str(), extension.c_str());
                    if (extension == L"mdat" || extension == L"mdatb")
                    {
                        std::vector<BYTE> originalHeader = { 'w', 'a', 'r', 'c', 'f', 0xe0, 0x23, 0x00, 0x00, 0x00, 0x00 };

                        if (tTJSBinaryStream* pEncodedStream = CreateLooseEncodedMdatStream(finalUrl, originalHeader))
                            return pEncodedStream;
                    }

                    if (extension == L"nei")
                    {
                        if (tTJSBinaryStream* pEncodedStream = CreateLooseEncodedNeiStream(url, pItem->Name.c_str()))
                            return pEncodedStream;

                        if (shouldLog)
                            Debugger::Log(L"NEI encode failed for %s, trying raw NEI fallback", pItem->Name.c_str());

                        continue;
                    }

                    void* pComStream = Kirikiri::TVPCreateIStream(finalUrl.c_str(), 0);
                    return Kirikiri::TVPCreateBinaryStreamAdapter(pComStream);
                }

                if (isNei)
                {
                    std::vector<std::wstring> rawUrls = BuildOverrideUrlsForPath(pItem->Name.c_str());

                    for (const std::wstring& url : rawUrls)
                    {
                        bool exists = Kirikiri::TVPIsExistentStorageNoSearchNoNormalize(url.c_str());
                        if (shouldLog)
                            Debugger::Log(L"Checked archive-stream override candidate %s => %s", url.c_str(), exists ? L"found" : L"missing");

                        if (!exists)
                            continue;

                        const std::wstring currentTarget = std::wstring(pArchive->Name.c_str()) + L">" + pItem->Name.c_str();
                        if (WouldRedirectToSelf(url, currentTarget))
                        {
                            if (shouldLog)
                                Debugger::Log(L"Skipping archive-stream self-redirect %s", url.c_str());
                            continue;
                        }

                        Debugger::Log(L"Redirecting archive stream %s to %s", pItem->Name.c_str(), url.c_str());
                        void* pComStream = Kirikiri::TVPCreateIStream(url.c_str(), 0);
                        return Kirikiri::TVPCreateBinaryStreamAdapter(pComStream);
                    }
                }

                if (pItem->FileHash == 0)
                {
                    Debugger::Log(L"Creating unencrypted XP3 stream for %s", pItem->Name.c_str());
                    tTVPXP3ArchiveSegment* pSegment = pItem->Segments.begin();
                    auto* pStream = new CustomTVPXP3ArchiveStream(pArchive->Name, pSegment->Start, pSegment->OrgSize, pSegment->ArcSize, pSegment->IsCompressed);
                    tTJSBinaryStream::ApplyWrappedVTable(pStream);
                    return pStream;
                }

                if (shouldLog)
                    Debugger::Log(L"No archive-stream override found for %s", pItem->Name.c_str());
            }

            archive_default:
            return CompilerHelper::CallInstanceMethod<tTJSBinaryStream*, &OriginalCreateStreamByIndex, tTVPXP3Archive<TCompilerType>*, tjs_uint>(pArchive, idx);
        }
    };

    static inline void* OriginalCreateStreamByIndex{};

    static inline ttstr (__stdcall* OriginalTVPGetPlacedPath)(const ttstr& name){};
    static inline void* (__stdcall* OriginalTVPCreateIStream)(const ttstr& name, tjs_uint32 flags){};
    static inline void* (__stdcall* OriginalTVPCreateTextStreamForRead)(const ttstr& name, const ttstr& mode){};
    static inline void (__stdcall* OriginalTVPAddAutoPath)(const ttstr& path){};
    static inline void (__stdcall* OriginalTVPRemoveAutoPath)(const ttstr& path){};
    static inline void (__stdcall* OriginalTVPRegisterStorageMedia)(iTVPStorageMedia* pMedia){};
    static inline void (__stdcall* OriginalTVPUnregisterStorageMedia)(iTVPStorageMedia* pMedia){};
    static inline std::map<iTVPStorageMedia*, tTJSBinaryStream* (*)(iTVPStorageMedia* pMedia, const ttstr& name, tjs_uint32 flags)> OriginalStorageMediaOpen{};
};
