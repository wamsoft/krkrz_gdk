# krkrz_gdk の構成

吉里吉里Z を Microsoft GDK (PC: Gaming.Desktop.x64 / Xbox: Gaming.Xbox.Scarlett.x64, Gaming.Xbox.XboxOne.x64)
向けにビルド・パッケージ化する外枠リポジトリの設計メモ。使い方は [README](../README.md)、
Xbox の実機での運用と分かったことは [xbox.md](xbox.md)。

本体側の汎用の口 (CMake 変数・判定マクロ・機種専用 Application) は本体のドキュメント
[PlatformPorting.md](https://github.com/wamsoft/krkrz/blob/master/doc/PlatformPorting.md) が SSOT。
このページは GDK 固有の決めごとだけを書く。

## 1. 位置づけ

既存の外枠 (krkrz_android / krkrz_web / krkrz_ios / krkrz_linux) と同じ **3 層分離**。

| 層 | 置き場所 | 内容 |
|---|---|---|
| エンジン | `${KRKRZ_BASE}/krkrz_dev` (**master**) | core (src/core) と全プラグイン (src/plugins/*) |
| 共通ビルドシステム | `krkrz_gdk` (本リポジトリ、公開・MIT) | CMake 外枠 / Xbox 用アプリクラス / パッケージ化ツール / サンプル設定 |
| 案件 | `PROJECT_DIR` (非公開) | `gdk-config.json` 1 本 + 資材。出力も `PROJECT_DIR/build/gdk/` |

PROJECT_DIR 省略時は krkrz_gdk 同梱のサンプル設定 (コアデモ) をビルドする。

## 2. エンジン参照 (master 固定)

- `KRKRZ_BASE` = krkrz_dev を置いた親フォルダ (既定: krkrz_gdk の親)。他の外枠と同じ。
- krkrz_dev は `git clone -b master --recursive` で用意する前提。configure 時に現在のブランチを調べ、
  master 以外なら警告する (`-DKRKRZ_GDK_ALLOW_NON_MASTER=ON` で抑止。develop で試す開発者用)。
- GDK のために本体へ入れた修正は develop → master のリリースに乗ってから使える。

## 3. ディレクトリ構成

```
krkrz_gdk/
  CMakeLists.txt          外枠 (core を add_subdirectory)
  CMakePresets.json       VS2022 generator + Gaming.* platform (gdk-desktop / gxdk-scarlett / gxdk-xboxone、比較用 win-x64)
  Makefile                tools/krkrz_gdk.py の薄いラッパー (PROJECT_DIR / TARGET / CONFIG)
  gdk-config.json         サンプル案件 (コアデモ)
  cmake/
    KrkrzGDK.cmake        ターゲット判定、Xbox 向けの core オプション、krkrz_platform_target_hook
    triplets/             x64-xbox-{scarlett,xboxone}-staticcrt.cmake
  templates/
    MicrosoftGame.config.in   1 本 (TargetDeviceFamily / DesktopRegistration / 保存領域を gen が差し込む)
  src/
    gdkapp.cpp            Xbox 用 Application (KRKRZ_APP_PLATFORM_OVERRIDE)
  plugins/                GDK 専用プラグイン置き場 (今は空。将来: 実績 / ユーザー / ストア等)
  tools/
    krkrz_gdk.py          gen / configure / build / stage / package / run / register / deploy / launch / vars
    stage.py              assetPack 実装 (android / ios / linux と同じ書式)
  vcpkg-ports/            vcpkg の overlay port (freetype)
  docs/
```

## 4. ビルドの流れ

1. **gen** — `gdk-config.json` から `build/gdk/generated/` に
   `myapp.cmake` (全プラグイン static) / `app.cmake` / `MicrosoftGame.config` (ターゲットごと) /
   ロゴ一式 (無いものは placeholder) / 起動オプションファイル を生成
2. **configure / build** — `cmake --preset <preset> -B build/gdk/<target>`。外枠 CMakeLists の処理順は
   myapp.cmake → vcpkg manifest のマージ → `project()` → SDL3 (FetchContent、コミット固定)
   → CommonExternals → core オプション設定 → `add_subdirectory(krkrz_dev/src/core)`。
   build は **必ず `--preset` 経由** (XdkEditionTarget を伝えるため)
3. **stage** — layout `build/gdk/<target>/layout/<config>/` を作る。先勝ち順:
   エンジン exe (+ Desktop は GDK のランタイム DLL) → 生成物 → assetPack。
   Xbox はさらにエンジンリソース (`resource/`) と、機種向けに事前コンパイルした Canvas シェーダー
   (`canvas_shaders.kzgs`) を置く
4. **package** — `MakePkg pack` (Desktop は `/pc`)。PackageLayout.xml は stage 後の実フォルダから生成する
   (FileGroup の Include はサブフォルダを辿らないため)
5. **register / deploy / launch** — Desktop: `wdapp register` → `wdapp launch`、Xbox: `xbapp deploy` → `xbapp launch`

## 5. 起動オプションファイル

本体は `<exe名>.cf` を**デスクトップでだけ**読み、どの機種でも exe と同じ場所の `config.cf` を読む。
そこで gen / stage は:

- Desktop: `<exe名>.cf` に `orgname` / `appname` / `datapath` / `config.options` を書く
- Xbox: 同じ内容を `config.cf` として layout に置く (`scid` もここに書く)

## 6. Xbox で core に渡すオプション (`cmake/KrkrzGDK.cmake`)

| 設定 | 理由 |
|---|---|
| `KRKRZ_DESKTOP=OFF` | WIN32 だがデスクトップではない (`.cf` の探索 / REPL 既定などが変わる) |
| `KRKRZ_APP_PLATFORM_OVERRIDE` + `KRKRZ_SRC_PLATFORM=src/gdkapp.cpp` | stdapp.cpp の代わりに Xbox 用 Application |
| `KRKRZ_RESOURCE_EXTERNAL` | `EnumResourceNames` が無いので、エンジンリソースは layout の `resource/` に置く |
| `KRKRZ_USE_OPENGL=OFF` / `KRKRZ_CANVAS_GPU=ON` | OpenGL / ANGLE が無い。Canvas は SDL_GPU (D3D12) |
| `KRKRZ_REPL=OFF` / `KRKRZ_REPL_FILE=OFF` / `KRKRZ_REPL_WEB=ON` + `BIND_ANY` | コンソールもファイル監視も無い。REPL は web だけ (外から繋ぐので 0.0.0.0 待受) |
| `KRKRZ_USE_A11Y=OFF` | Elements の読み上げ (AccessKit) は Win32 のウィンドウサブクラス前提 |
| `KRKRZ_USE_LOGCORE=OFF` | デスクトップ向けのログ機能 (ファイル出力・コンソール) |
| `CMAKE_DISABLE_FIND_PACKAGE_OpenMP` | ThorVG が OpenMP を見つけると VCOMP140.DLL を import して起動できない |
| リンクに `oldnames.lib` | Xbox の既定ライブラリに入っておらず `strdup` / `stricmp` / `fileno` 等が解決しない |
| 定義 `KRKRZ_GDK` / `KRKRZ_GDK_XBOX` / `KRKRZ_GDK_SCARLETT` / `KRKRZ_GDK_XBOXONE` / `KRKRZ_GDK_DESKTOP`、`KRKRZ_VARIANT_OPTION=_GDK` | 外枠・プラグインのソースでの判定用。`System.variant` は `SDL_GDK` |
| `MA_NO_RUNTIME_LINKING` | miniaudio が実行時に DLL を探しに行かない |

全ターゲットで `KRKRZ_ENABLE_DAP` / `KRKRZ_BUILD_TESTS` は OFF。
Desktop は core の既定 (stdapp.cpp / 埋め込みリソース / OpenGL) のまま。
`krkrz_platform_target_hook` で Desktop の loose 実行に要る `Microsoft.Xbox.Services.GDK.C.Thunks.dll` を出力先へコピーする。

## 7. Xbox 用 Application (`src/gdkapp.cpp`)

| 項目 | 内容 |
|---|---|
| データの場所 | exe と同じフォルダの `data.xp3` → exe 結合 xp3 → `data/startup.tjs` |
| リソース | `file://` で exe フォルダの `resource/` |
| 一時フォルダ | PersistentLocalStorage の下の `tmp/` |
| セーブ (`System.dataPath`) | `scid` あり: SDL のヒント `SDL_GDK_SERVICE_CONFIGURATION_ID` を立てて XGameSaveFiles (クラウド同期)。なし: PersistentLocalStorage の下の `savedata/` (開発用)。どちらも**ネイティブのパス**で返す |
| 機種タグ | `xbox;scarlett` / `xbox;xboxone` (`config_<tag>.cf` / `System.platformTag`) |

## 8. SDL3

`https://github.com/wamsoft/SDL.git` の `gdk-cmake-support-3.4.18` を、コミットを固定して FetchContent で使う
(core の FetchContent(main) は使わない)。release-3.4.18 に次を足したもの:

| 変更 | 内容 |
|---|---|
| GDK / GXDK の CMake 対応 | VS generator の `Gaming.*` platform でビルドできるようにする |
| HIDAPI の NULL ガード | GameInput が名前 NULL のパッドを渡すと `HIDAPI_DriverSwitch_IsSupportedDevice` の `SDL_strcmp(NULL, ...)` で落ちる (上流 main と同じ `name &&`)。Desktop で無言終了していた原因 |
| Xbox One の行ピッチ | D3D12 のバッファ→テクスチャ転送の行ピッチを 256 で揃えていたが、Xbox One は 1024 が必要 (`SDL_D3D12_TEXTURE_DATA_PITCH_ALIGNMENT`)。Elements のダイアログを開くとクラッシュしていた |
| GPU レンダラーのシェーダー事前コンパイル | SDL_Renderer (GPU) 自身の D3D12 シェーダーを、ビルド時に GXDK の dxc で機種向けにコンパイルする (`src/render/gpu/shaders/compile_shaders_xbox.cmake`) |

上流 SDL は AI 生成のコントリビューションを受け付けていないので、これらは fork に留める。

Static CRT を全ターゲットで統一する (`CMAKE_MSVC_RUNTIME_LIBRARY` を FetchContent より前に設定)。
XGameRuntime の初期化は SDL 側 (`SDL_sysmain_runapp.cpp`)。core の main は `SDL_MAIN_USE_CALLBACKS` なので相性が良い。

## 9. vcpkg

- toolchain ファイルは使わず VS generator の platform 名で GDK の MSBuild 拡張を使う。
  vcpkg は `vcpkg.cmake` を直接 toolchain にし、chainload しない
- Xbox の triplet (`cmake/triplets/`) は static CRT。`unset(ENV{GameDKCoreLatest})` (vcpkg の xbox.cmake を
  2025 年 4 月版以前の経路に通す) と `/DEFAULTLIB:onecore_apiset.lib` (無いと libucrt のリンクが失敗する) を入れる
- freetype は UWP 用パッチ (`generic` を置き換えて `#undef`) が harfbuzz の hb-ft.cc を壊すので、
  パッチを外した overlay port を使う ([vcpkg-ports/](../vcpkg-ports/README.md))
- `find_package` は SDL の FetchContent より前

## 10. 段階と今後

| 段階 | 内容 | 状況 |
|---|---|---|
| P0 | 外枠骨格 / Desktop | 完了 (layout から起動、msixvc を wdapp install してセーブ確認) |
| P1 | gen / stage / package | 完了 |
| P2 | Scarlett | 完了 (全画面・パッド・セーブ・Canvas (D3D12)・シェーダー事前コンパイル・YUV 動画) |
| P3 | Xbox One | ビルド・パッケージ作成と Series devkit の互換動作まで。Xbox One 実機は未確認 |
| P4 | パッケージの chunk 分割、実績 / ユーザー / ストアの GDK 専用プラグイン | 未着手 (必要に応じて) |

未解決は [xbox.md](xbox.md) の「既知の制限・未確認」。

## 11. 公開リポジトリとしての注意

- 案件名・タイトル・課題キーを書かない。identity の実値は案件側の gdk-config.json にだけ置く
- 他機種のコンソール SDK 由来の情報は持ち込まない。Xbox 向けは公開 GDK と SDL 上流に既に出ている範囲
  (platform 名、ライブラリ名、ツール名) に留める
