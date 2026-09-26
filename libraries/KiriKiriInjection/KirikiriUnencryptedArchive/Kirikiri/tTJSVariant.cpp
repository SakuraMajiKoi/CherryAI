#include "stdafx.h"

void (__stdcall *tTJSVariant::Ctor)(tTJSVariant* pThis);
void (__stdcall *tTJSVariant::Dtor)(tTJSVariant* pThis);

void tTJSVariant::Init()
{
    Kirikiri::ResolveScriptExport(L"tTJSVariant::tTJSVariant()", Ctor);
    Kirikiri::ResolveScriptExport(L"tTJSVariant::~ tTJSVariant()", Dtor);
}

tTJSVariant::tTJSVariant()
{
    Ctor(this);
}

tTJSVariant::~tTJSVariant()
{
    Dtor(this);
}

std::wstring tTJSVariant::AsString() const
{
    if (vt != tvtString || String == nullptr)
        return L"";

    return std::wstring(static_cast<const tjs_char*>(*String), String->Length);
}
