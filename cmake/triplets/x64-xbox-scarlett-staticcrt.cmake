set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE static)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_XBOX_CONSOLE_TARGET scarlett)

# Workaround for vcpkg/scripts/toolchains/xbox.cmake on a machine that has
# October 2025+ Microsoft GDK installed.
#
# xbox.cmake takes the "No windows paths should be used for console targets"
# branch whenever ENV{GameDKCoreLatest} is defined, which intentionally skips
# adding the GRDK include/lib paths. But the GXDK branch further down still
# emits `xgameruntime.lib` into CMAKE_*_STANDARD_LIBRARIES, and that lib only
# exists under GRDK/gameKit/Lib/amd64/ — so the linker dies with LNK1104.
#
# Pretending GameDKCoreLatest is not set forces the April-2025-or-earlier path
# (ENV{GRDKLatest} branch), which adds the GRDK lib path so xgameruntime.lib
# is found. GRDKLatest itself still points at the 251002 install on this box
# and the layout is compatible — xgameruntime.lib exists at
# 251002/GRDK/gameKit/Lib/amd64/ as well.
unset(ENV{GameDKCoreLatest})

# vcpkg's xbox.cmake replaces _vcpkg_core_libs (originally onecore_apiset.lib)
# with `xgameplatform.lib xgameruntime.lib` once it detects the GXDK. That
# works for the official Dynamic-CRT triplet because ucrtbase.dll resolves
# Win32 console APIs (WriteConsoleW, SetConsoleCtrlHandler, ...) dynamically.
# With Static CRT (/MT) those symbols have to be satisfied at link time, and
# without onecore_apiset.lib in the default library set, libucrt fails with
# LNK2019 on kernel32 APIs. Reinjecting it via the linker flags fixes the
# port build without forking xbox.cmake.
set(VCPKG_LINKER_FLAGS "/DEFAULTLIB:onecore_apiset.lib")
