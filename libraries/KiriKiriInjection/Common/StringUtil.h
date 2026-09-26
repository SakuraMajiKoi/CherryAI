#pragma once

class StringUtil
{
private:
    struct CFunctions
    {
        static char ToLower(char c)
        {
            return (char)tolower(c);
        }

        static wchar_t ToLower(wchar_t c)
        {
            return (wchar_t)towlower(c);
        }

        static char ToUpper(char c)
        {
            return (char)toupper(c);
        }

        static wchar_t ToUpper(wchar_t c)
        {
            return (wchar_t)towupper(c);
        }

        static int StringPrintf(char* pBuffer, int bufferSize, const char* pFormat, va_list args)
        {
            return vsnprintf(pBuffer, bufferSize, pFormat, args);
        }

        static int StringPrintf(wchar_t* pBuffer, int bufferSize, const wchar_t* pFormat, va_list args)
        {
            return _vsnwprintf(pBuffer, bufferSize, pFormat, args);
        }

        static int StringLength(const char* pFormat, va_list args)
        {
            return _vscprintf(pFormat, args);
        }

        static int StringLength(const wchar_t* pFormat, va_list args)
        {
            return _vscwprintf(pFormat, args);
        }
    };

public:
    static std::wstring         ToUTF16         (const std::string& str);
    static std::string          ToUTF8          (const std::wstring& wstr);

    template<typename TChar>
    static std::basic_string<TChar> Format(const TChar* pFormat, va_list args)
    {
        va_list argsForLength;
        va_copy(argsForLength, args);
        int length = CFunctions::StringLength(pFormat, argsForLength);
        va_end(argsForLength);
        if (length <= 0)
            return std::basic_string<TChar>();

        va_list argsForText;
        va_copy(argsForText, args);
        std::basic_string<TChar> result;
        result.resize(static_cast<size_t>(length) + 1);
        CFunctions::StringPrintf(result.data(), length + 1, pFormat, argsForText);
        result.resize(static_cast<size_t>(length));
        va_end(argsForText);

        return result;
    }

    template<typename TChar>
    static std::basic_string<TChar> Format(const TChar* pFormat, ...)
    {
        va_list args;
        va_start(args, pFormat);
        return Format(pFormat, args);
    }

    template<typename TChar>
    static std::basic_string<TChar> ToLower(const std::basic_string<TChar>& str)
    {
        std::basic_string<TChar> result;
        result.resize(str.size());
        std::ranges::transform(str, result.begin(), [](TChar c) { return CFunctions::ToLower(c); });
        return result;
    }

    template<typename TChar>
    static std::basic_string<TChar> ToUpper(const std::basic_string<TChar>& str)
    {
        std::basic_string<TChar> result;
        result.resize(str.size());
        std::ranges::transform(str, result.begin(), [](TChar c) { return CFunctions::ToUpper(c); });
        return result;
    }

    template<typename TChar>
    static std::vector<std::basic_string<TChar>> Split(const std::basic_string<TChar>& str, const std::basic_string<TChar>& delimiter)
    {
        std::vector<std::basic_string<TChar>> result;
        if (delimiter.empty())
        {
            result.push_back(str);
            return result;
        }

        size_t start = 0;
        while (start < str.size())
        {
            size_t end = str.find(delimiter, start);
            if (end == std::basic_string<TChar>::npos)
                end = str.size();

            result.push_back(str.substr(start, end - start));
            start = end + delimiter.size();
        }
        return result;
    }

    template<typename TChar>
    static std::basic_string<TChar> Join(const std::vector<std::basic_string<TChar>>& elements, const std::basic_string<TChar>& delimiter)
    {
        std::basic_string<TChar> result;
        for (size_t i = 0; i < elements.size(); i++)
        {
            if (i > 0)
                result += delimiter;

            result += elements[i];
        }
        return result;
    }

    template<typename TChar>
    static std::basic_string<TChar> Replace(const std::basic_string<TChar>& str, TChar oldChar, TChar newChar)
    {
        std::basic_string<TChar> result(str);
        std::ranges::replace(result, oldChar, newChar);
        return result;
    }
};
