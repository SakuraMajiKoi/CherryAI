#include "stdafx.h"

using namespace std;

CustomTVPXP3ArchiveStream::CustomTVPXP3ArchiveStream(const ttstr& archiveUrl, tjs_uint64 offset, tjs_uint64 originalSize, tjs_uint64 archiveSize, bool compressed)
{
	if (originalSize > UINT_MAX || archiveSize > INT_MAX)
		throw exception("XP3 segment is too large to load into a single buffer");

	_data.resize(static_cast<size_t>(originalSize));
	_position = 0;

	ttstr archivePath = archiveUrl;
	archivePath.Replace(L"file://./", L"", true);
	archivePath.Replace(L"/", L"\\", true);

	wstring archivePathStr(archivePath.c_str());
	archivePathStr.insert(1, L":");
	
	FileStream stream(archivePathStr, L"rb");
	stream.SetPosition(offset);
	if (compressed)
	{
		vector<BYTE> compressedData;
		compressedData.resize(static_cast<size_t>(archiveSize));
		stream.ReadBytes(compressedData.data(), static_cast<int>(compressedData.size()));

		int uncompressedSize = static_cast<int>(_data.size());
		Kirikiri::ZLIB_uncompress(_data.data(), &uncompressedSize, compressedData.data(), static_cast<int>(compressedData.size()));
	}
	else
	{
		stream.ReadBytes(_data.data(), static_cast<int>(_data.size()));
	}
}

CustomTVPXP3ArchiveStream::~CustomTVPXP3ArchiveStream()
{
}

tjs_uint64 CustomTVPXP3ArchiveStream::Seek(tjs_int64 offset, tjs_int whence)
{
	switch (whence)
	{
		case SEEK_SET:
			_position = offset < 0 ? 0 : static_cast<tjs_uint64>(offset);
			break;

		case SEEK_CUR:
			_position += offset;
			break;

		case SEEK_END:
			_position = _data.size() + offset;
			break;
	}

	return _position;
}

tjs_uint CustomTVPXP3ArchiveStream::Read(void* buffer, tjs_uint read_size)
{
	if (_position >= _data.size())
		return 0;

	const tjs_uint64 bytesAvailable = static_cast<tjs_uint64>(_data.size()) - _position;
	if (read_size > bytesAvailable)
		read_size = static_cast<tjs_uint>(bytesAvailable);

	memcpy(buffer, _data.data() + _position, read_size);
	_position += read_size;
	return read_size;
}

tjs_uint64 CustomTVPXP3ArchiveStream::GetSize()
{
	return _data.size();
}

tjs_uint CustomTVPXP3ArchiveStream::Write(const void* buffer, tjs_uint write_size)
{
	throw exception("Not implemented");
}

void CustomTVPXP3ArchiveStream::SetEndOfStorage()
{
	throw exception("Not implemented");
}
