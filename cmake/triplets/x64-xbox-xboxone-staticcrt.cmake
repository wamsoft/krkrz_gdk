set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE static)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_XBOX_CONSOLE_TARGET xboxone)

# See cmake/triplets/x64-xbox-scarlett-staticcrt.cmake for the rationale.
unset(ENV{GameDKCoreLatest})
set(VCPKG_LINKER_FLAGS "/DEFAULTLIB:onecore_apiset.lib")
