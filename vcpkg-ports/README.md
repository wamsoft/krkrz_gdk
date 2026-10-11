# vcpkg overlay ports

| port | 元 | 変更 |
|---|---|---|
| freetype | microsoft/vcpkg `ceaa2404` (core の builtin-baseline) の ports/freetype (2.13.3) | `0003-Fix-UWP.patch` を外した |

`0003-Fix-UWP.patch` は WINAPI_FAMILY がデスクトップ以外のとき `FT_FaceRec::generic` などを
`GenericFromFreeTypeLibrary` に置き換え、構造体定義の後で `#undef generic` する。
UWP (C++/CX では `generic` が予約語) 向けの回避策だが、Xbox (WINAPI_FAMILY_GAMES) でも有効になり、
`->generic` を参照する harfbuzz (hb-ft.cc) などがビルドできなくなる。GDK では C++/CX を使わないので外す。

core の builtin-baseline を更新したら、この port も同じ版に揃えること。
