# krkrz_gdk: GDK / GXDK 向けの共通設定
#
# GDK の toolchain ファイルは使わず、Visual Studio generator の platform 名
# (Gaming.Desktop.x64 / Gaming.Xbox.Scarlett.x64 / Gaming.Xbox.XboxOne.x64) で
# GDK の MSBuild 拡張に任せる。

# krkrz_gdk リポジトリのルート (macro 内では CMAKE_CURRENT_LIST_DIR が呼び出し側になるため控えておく)
get_filename_component(KRKRZ_GDK_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)

# CMAKE_GENERATOR_PLATFORM から KRKRZ_GDK_TARGET (desktop / scarlett / xboxone / win) を決める
function(krkrz_gdk_detect_target)
    set(_platform "${CMAKE_GENERATOR_PLATFORM}")
    if(_platform STREQUAL "Gaming.Desktop.x64")
        set(_target desktop)
    elseif(_platform STREQUAL "Gaming.Xbox.Scarlett.x64")
        set(_target scarlett)
    elseif(_platform STREQUAL "Gaming.Xbox.XboxOne.x64")
        set(_target xboxone)
    else()
        # 比較用の通常 Win32 ビルド (GDK なし)
        set(_target win)
    endif()

    if(_target STREQUAL "desktop" OR _target STREQUAL "scarlett" OR _target STREQUAL "xboxone")
        if(NOT DEFINED ENV{GameDK})
            message(FATAL_ERROR "Microsoft GDK not found (GameDK env is not set)")
        endif()
        if(NOT DEFINED ENV{XdkEditionTarget} OR "$ENV{XdkEditionTarget}" STREQUAL "")
            message(FATAL_ERROR "XdkEditionTarget env is not set. Configure / build via CMakePresets or tools/krkrz_gdk.py")
        endif()
    endif()

    set(KRKRZ_GDK_TARGET ${_target} PARENT_SCOPE)
    if(_target STREQUAL "scarlett" OR _target STREQUAL "xboxone")
        set(KRKRZ_GDK_XBOX ON PARENT_SCOPE)
    else()
        set(KRKRZ_GDK_XBOX OFF PARENT_SCOPE)
    endif()
    message(STATUS "krkrz_gdk: target = ${_target} (platform '${_platform}', edition '$ENV{XdkEditionTarget}')")
endfunction()

# krkrz_dev の現在ブランチを確認する。公開構成は master を参照する前提。
function(krkrz_gdk_check_engine_branch DEV_DIR)
    option(KRKRZ_GDK_ALLOW_NON_MASTER "suppress the warning when krkrz_dev is not on master" OFF)
    find_package(Git QUIET)
    if(NOT GIT_FOUND OR NOT EXISTS "${DEV_DIR}/.git")
        return()
    endif()
    execute_process(
        COMMAND ${GIT_EXECUTABLE} -C "${DEV_DIR}" rev-parse --abbrev-ref HEAD
        OUTPUT_VARIABLE _branch OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE _res ERROR_QUIET)
    if(NOT _res EQUAL 0)
        return()
    endif()
    message(STATUS "krkrz_gdk: krkrz_dev branch = ${_branch}")
    if(NOT _branch STREQUAL "master" AND NOT KRKRZ_GDK_ALLOW_NON_MASTER)
        message(WARNING
            "krkrz_dev is on '${_branch}', not 'master'. krkrz_gdk is meant to be built "
            "against the master (release) branch. Pass -DKRKRZ_GDK_ALLOW_NON_MASTER=ON to silence.")
    endif()
endfunction()

# core に渡すオプションとプラットフォーム定義
macro(krkrz_gdk_configure_core)
    # プラグインは全て static (StaticPlugins.cpp で登録)
    # 端末・開発 PC 前提の機能は GDK では既定 OFF。必要なら -D で上書きする
    set(KRKRZ_ENABLE_DAP OFF CACHE BOOL "" FORCE)
    set(KRKRZ_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    if(KRKRZ_GDK_XBOX)
        # Xbox にはコンソールもファイル監視も無い。REPL は web のみ
        set(KRKRZ_USE_LOGCORE OFF CACHE BOOL "" FORCE)
        set(KRKRZ_REPL OFF CACHE BOOL "" FORCE)
        set(KRKRZ_REPL_FILE OFF CACHE BOOL "" FORCE)
        set(KRKRZ_REPL_WEB ON CACHE BOOL "" FORCE)
        set(KRKRZ_REPL_WEB_BIND_ANY ON CACHE BOOL "" FORCE)
        # OpenGL は Xbox に無い。Canvas は SDL_GPU (D3D12) 版を使う
        set(KRKRZ_USE_OPENGL OFF CACHE BOOL "" FORCE)
        set(KRKRZ_CANVAS_GPU ON CACHE BOOL "" FORCE)
        # Elements の読み上げ (AccessKit) は Win32 のウィンドウサブクラス前提
        set(KRKRZ_USE_A11Y OFF CACHE BOOL "" FORCE)
        # WIN32 は真だがデスクトップではない (.cf 探索規約 / REPL 既定などに影響)
        set(KRKRZ_DESKTOP OFF)
        # core の stdapp.cpp を外して src/gdkapp.cpp の Application を使う
        set(KRKRZ_APP_PLATFORM_OVERRIDE TRUE)
        list(APPEND KRKRZ_SRC_PLATFORM ${KRKRZ_GDK_ROOT}/src/gdkapp.cpp)
        # エンジンリソースは exe に埋め込まず layout/resource/ に置く (tools/krkrz_gdk.py stage)
        set(KRKRZ_RESOURCE_EXTERNAL TRUE)
        # Xbox の既定ライブラリには oldnames.lib (strdup / stricmp / fileno 等の
        # POSIX 互換名) が入らない。依存ライブラリ (bzip2 / libjpeg-turbo / ThorVG) が使う
        list(APPEND KRKRZ_LIB_PLATFORM oldnames.lib)
        # ThorVG が OpenMP を自動検出すると VCOMP140.DLL を import する。Static CRT 構成の
        # Xbox パッケージには入らないので検出ごと止める
        set(CMAKE_DISABLE_FIND_PACKAGE_OpenMP TRUE)
    endif()

    list(APPEND KRKRZ_DEFINES_PLATFORM
        # miniaudio のバックエンドを動的ロードしない
        MA_NO_RUNTIME_LINKING
        # System.buildVariantName の追加定義
        KRKRZ_VARIANT_OPTION=_GDK
        KRKRZ_GDK=1
    )
    if(KRKRZ_GDK_TARGET STREQUAL "desktop")
        list(APPEND KRKRZ_DEFINES_PLATFORM KRKRZ_GDK_DESKTOP=1)
    elseif(KRKRZ_GDK_TARGET STREQUAL "scarlett")
        list(APPEND KRKRZ_DEFINES_PLATFORM KRKRZ_GDK_XBOX=1 KRKRZ_GDK_SCARLETT=1)
    elseif(KRKRZ_GDK_TARGET STREQUAL "xboxone")
        list(APPEND KRKRZ_DEFINES_PLATFORM KRKRZ_GDK_XBOX=1 KRKRZ_GDK_XBOXONE=1)
    endif()
endmacro()

# core が exe ターゲットを定義した直後に呼ばれるフック (同一ディレクトリ内でしか
# add_custom_command(TARGET) できないため)
function(krkrz_platform_target_hook TARGET)
    if(KRKRZ_GDK_TARGET STREQUAL "win")
        return()
    endif()

    set_target_properties(${TARGET} PROPERTIES
        VS_GLOBAL_ExtractNativeManifest false)

    if(KRKRZ_GDK_TARGET STREQUAL "desktop")
        # Desktop の loose-run には Microsoft.Xbox.Services.GDK.C.Thunks.dll が要る。
        # XCurl.dll / libHttpClient.GDK.dll は MSBuild 拡張が自動コピーするが、
        # Thunks DLL は Lib/x64/<cfg> にあり自動コピーされない。
        set(_grdk_root "$ENV{GameDK}$ENV{XdkEditionTarget}/GRDK")
        set(_thunks_dir "${_grdk_root}/ExtensionLibraries/Xbox.Services.API.C/Lib/x64")
        if(NOT EXISTS "${_thunks_dir}/Release/Microsoft.Xbox.Services.GDK.C.Thunks.dll")
            message(WARNING "Thunks DLL not found under ${_thunks_dir}. Verify the GDK install / XdkEditionTarget.")
        else()
            add_custom_command(TARGET ${TARGET} POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    "${_thunks_dir}/$<IF:$<CONFIG:Debug>,Debug,Release>/Microsoft.Xbox.Services.GDK.C.Thunks.dll"
                    "$<TARGET_FILE_DIR:${TARGET}>/"
                COMMENT "Staging Microsoft.Xbox.Services.GDK.C.Thunks.dll")
        endif()
    endif()
endfunction()
