cmake_minimum_required(VERSION 3.25)

set(PROJECT_NAME krkrz_gdk)
set(PROJECT_VERSION 1.0)

# ----------------------------------------------------
# krkrz ソース参照先
#
# KRKRZ_BASE: krkrz_dev フォルダがあるディレクトリ。
# 環境変数 KRKRZ_BASE、なければこのリポジトリの親ディレクトリを仮定する
# (krkrz_dev と krkrz_gdk が同じ場所に clone されている構成)。
# ----------------------------------------------------

if(DEFINED KRKRZ_BASE)
    cmake_path(SET KRKRZ_BASE "${KRKRZ_BASE}")
elseif(DEFINED ENV{KRKRZ_BASE})
    cmake_path(SET KRKRZ_BASE "$ENV{KRKRZ_BASE}")
else()
    cmake_path(SET KRKRZ_BASE "${CMAKE_CURRENT_SOURCE_DIR}/..")
endif()

set(KRKRZ_DEV_DIR ${KRKRZ_BASE}/krkrz_dev)
set(KRKRZ_DIR ${KRKRZ_DEV_DIR}/src/core)
set(PLUGINS_DIR ${KRKRZ_DEV_DIR}/src/plugins)

if(NOT EXISTS "${KRKRZ_DIR}/CMakeLists.txt")
    message(FATAL_ERROR "krkrz core not found: ${KRKRZ_DIR} (set KRKRZ_BASE env)")
endif()

include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/KrkrzGDK.cmake)
krkrz_gdk_detect_target()
krkrz_gdk_check_engine_branch("${KRKRZ_DEV_DIR}")

# ----------------------------------------------------
# 組み込みプラグイン定義
#
# 案件の gdk-config.json から tools/krkrz_gdk.py が生成した myapp.cmake を読む。
# GDK / Xbox ではプラグインを動的ロードしない前提なので、TVP_PLUGINS は
# すべて TVP_PLUGINS_STATIC として静的リンクする。
# (pre-project で定義: vcpkg manifest マージ判定にも使われる)
# ----------------------------------------------------

set(MYAPP_CMAKE_FILE "" CACHE FILEPATH "generated myapp.cmake (plugins)")
set(APP_CMAKE_FILE "" CACHE FILEPATH "generated app.cmake (exe name / resource dir)")

list(APPEND TVP_PLUGIN_FOLDERS ${CMAKE_CURRENT_SOURCE_DIR}/plugins)
if(MYAPP_CMAKE_FILE)
    include(${MYAPP_CMAKE_FILE})
endif()
list(APPEND TVP_PLUGIN_FOLDERS ${PLUGINS_DIR})
list(REMOVE_DUPLICATES TVP_PLUGIN_FOLDERS)

list(APPEND TVP_PLUGINS_STATIC ${TVP_PLUGINS})
list(REMOVE_DUPLICATES TVP_PLUGINS_STATIC)
set(TVP_PLUGINS ${TVP_PLUGINS_STATIC})

set(TPSTUB_DIR ${PLUGINS_DIR}/tp_stub)
set(NCBIND_DIR ${PLUGINS_DIR}/ncbind)
set(SIMPLEBIND_DIR ${PLUGINS_DIR}/simplebinder)

if(APP_CMAKE_FILE)
    include(${APP_CMAKE_FILE})
endif()

# ----------------------------------------------------
# vcpkg マニフェスト統合 (project() より前で実行する必要あり)
#
# core の vcpkg.json を BASE に、movie-player と各プラグインの vcpkg.json を
# マージして ${CMAKE_BINARY_DIR}/manifest/vcpkg.json に書き出す。
# ----------------------------------------------------

include(${KRKRZ_DIR}/cmake/MergeVcpkgManifest.cmake)

set(_KRKRZ_GDK_VCPKG_SUBDIRS "${KRKRZ_DIR}/external/movie-player")
foreach(_plugin IN LISTS TVP_PLUGINS)
    foreach(_folder IN LISTS TVP_PLUGIN_FOLDERS)
        if(EXISTS "${_folder}/${_plugin}")
            list(APPEND _KRKRZ_GDK_VCPKG_SUBDIRS "${_folder}/${_plugin}")
            break()
        endif()
    endforeach()
endforeach()

set(_KRKRZ_GDK_MANIFEST_DIR "${CMAKE_BINARY_DIR}/manifest")
file(MAKE_DIRECTORY "${_KRKRZ_GDK_MANIFEST_DIR}")
krkrz_merge_vcpkg_manifest(
    BASE    "${KRKRZ_DIR}/vcpkg.json"
    OUTPUT  "${_KRKRZ_GDK_MANIFEST_DIR}/vcpkg.json"
    SUBDIRS ${_KRKRZ_GDK_VCPKG_SUBDIRS}
    EXCLUDE
        "movie-player:glew"
        "movie-player:glfw3"
)
set(VCPKG_MANIFEST_DIR "${_KRKRZ_GDK_MANIFEST_DIR}" CACHE PATH
    "vcpkg manifest directory (merged manifest written by krkrz_merge_vcpkg_manifest)" FORCE)

# Static CRT を全ターゲット (SDL / プラグイン / core) で統一する。
# Xbox の Game OS には VC++ ランタイム DLL が無いため必須。Desktop も揃える。
# FetchContent (SDL3) より前に設定しておく必要がある。
cmake_policy(SET CMP0091 NEW)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

project(${PROJECT_NAME} VERSION ${PROJECT_VERSION})

# ----------------------------------------------------
# SDL3 (GDK / GXDK 対応 fork をタグ固定で先に用意する)
#
# core は TARGET SDL3::SDL3 が無いときだけ libsdl-org/SDL の main を
# FetchContent するので、ここで先に定義して版を固定する。
# ローカルの clone を使う場合は -DFETCHCONTENT_SOURCE_DIR_SDL3=<path>。
# ----------------------------------------------------

set(KRKRZ_GDK_SDL_REPOSITORY "https://github.com/wamsoft/SDL.git" CACHE STRING "SDL3 (GDK fork) repository")
# gdk-cmake-support-3.4.18 ブランチ (SDL 3.4.18 + GDK/GXDK CMake 対応 + GameInput NULL 名修正 +
# Xbox One の D3D12 行ピッチ修正 + GPU レンダラーのシェーダーの Xbox 向け事前コンパイル)
# CACHE にすると既存のビルドツリーが古い値を持ち続けるので、-D で指定されたときだけ上書きする
if(NOT KRKRZ_GDK_SDL_GIT_TAG)
    set(KRKRZ_GDK_SDL_GIT_TAG "21148fa59242be6e4fa858424d4b124f47fd6586")
endif()

set(SDL_SHARED OFF CACHE BOOL "" FORCE)
set(SDL_STATIC ON CACHE BOOL "" FORCE)
set(SDL_TEST_LIBRARY OFF CACHE BOOL "" FORCE)
set(SDL_TESTS OFF CACHE BOOL "" FORCE)
set(SDL_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SDL_DISABLE_INSTALL ON CACHE BOOL "" FORCE)

include(FetchContent)
FetchContent_Declare(SDL3
    GIT_REPOSITORY ${KRKRZ_GDK_SDL_REPOSITORY}
    GIT_TAG ${KRKRZ_GDK_SDL_GIT_TAG}
)
FetchContent_MakeAvailable(SDL3)

# ----------------------------------------------------
# krkrz core オプション (GDK 構成)
# ----------------------------------------------------

krkrz_gdk_configure_core()

# ----------------------------------------------------
# 共通外部依存 (HarfBuzz / ICU)。プラグイン定義の後に include する
# ----------------------------------------------------
if(EXISTS "${KRKRZ_DEV_DIR}/cmake/CommonExternals.cmake")
    include(${KRKRZ_DEV_DIR}/cmake/CommonExternals.cmake)
endif()

add_subdirectory(${KRKRZ_DIR} ${CMAKE_BINARY_DIR}/krkrz)
