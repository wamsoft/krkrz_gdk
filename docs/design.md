# krkrz_gdk 構成検討 (ドラフト)

吉里吉里Z を Microsoft GDK (PC: Gaming.Desktop.x64 / Xbox: Gaming.Xbox.Scarlett.x64, Gaming.Xbox.XboxOne.x64)
向けにビルド・パッケージ化するための外枠リポジトリ。公開リポジトリとして運用する。

## 1. 位置づけ

既存の外枠 (krkrz_android / krkrz_web / krkrz_ios / krkrz_linux) と同じ **3 層分離** に揃える。

| 層 | 置き場所 | 内容 |
|---|---|---|
| エンジン | `${KRKRZ_BASE}/krkrz_dev` (**master**) | core (src/core) と全プラグイン (src/plugins/*) |
| 共通ビルドシステム | `krkrz_gdk` (本リポジトリ、公開) | CMake 外枠 / GDK アプリクラス / パッケージ化ツール / サンプル設定 |
| 案件 | `PROJECT_DIR` (非公開) | `gdk-config.json` 1 本 + 資材 (data / archive/*.xp3 / ロゴ等)。出力も `PROJECT_DIR/build/gdk/` |

```
PROJECT_DIR=/path/to/game make -C krkrz_gdk package TARGET=desktop
```

PROJECT_DIR 省略時は krkrz_gdk 同梱のサンプル設定 (コアデモ) をビルドする。

## 2. エンジン参照 (master 固定)

- `KRKRZ_BASE` = krkrz_dev を置いた親フォルダ (既定: krkrz_gdk の親)。他の外枠と同じ。
- krkrz_dev は **`git clone -b master --recursive`** で用意する前提。configure 時に
  krkrz_dev の現在ブランチを調べ、master 以外なら WARNING を出す
  (`KRKRZ_GDK_ALLOW_NON_MASTER=ON` で抑止。開発者が develop で試す用)。
- `make setup` で krkrz_dev が無ければ master を clone する補助を用意する。
- 注意: krkrz_dev の master はリリース用で develop より遅れる。GDK 用に core 側へ入れる修正
  (後述 §6) は develop → master のリリースに乗るまで GDK から使えない。
  初期開発中は develop で進め、公開時点で master に揃える運用が現実的。

## 3. ディレクトリ構成案

```
krkrz_gdk/
  CMakeLists.txt          外枠 (umbrella 相当。core を add_subdirectory)
  CMakePresets.json       VS2022 generator + Gaming.* platform の 3 preset (+ 比較用 win-x64)
  Makefile                薄いラッパー (PROJECT_DIR / TARGET / CONFIG)
  gdk-config.json         サンプル案件 (コアデモ)
  cmake/
    KrkrzGDK.cmake        platform 判定、KRKRZ_*_PLATFORM の設定、krkrz_platform_target_hook
    MicrosoftGame.config.in   1 本化 (TargetDeviceFamily / DesktopRegistration を変数で切替)
    triplets/             x64-xbox-{scarlett,xboxone}-staticcrt.cmake (事前検証構成から移植)
  src/
    gdkapp.cpp            GDKApplication : SDL3Application (InitPath / TempPath /
                          CreateUserStorageMedia / GetSystemLanguage / getPlatformTagSpec)
    gdkstorage.cpp        セーブ領域 (SDL_Storage = XGameSave 経由)
  plugins/                GDK 専用プラグイン置き場 (将来: 実績 / ユーザー / ストア等)
  tools/
    krkrz_gdk.py          gen / stage / build / package / deploy / run の全工程 (python 標準ライブラリのみ)
    stage.py              assetPack 実装 (krkrz_linux と共通仕様)
    gen_logos.py          1 枚の元画像 → Logo44/100/150/480 + SplashScreen
  resource/               既定ロゴ・アイコン
  docs/
```

## 4. ビルドの流れ

1. **gen** (`krkrz_gdk.py gen`) — `gdk-config.json` から
   `PROJECT_DIR/build/gdk/generated/` に以下を生成
   - `myapp.cmake` (`TVP_PLUGIN_FOLDERS` / `TVP_PLUGINS` / `TVP_PLUGINS_STATIC`。**全プラグイン static**)
   - `app.cmake` (identity / exe 名 / resource dir / gpushaders dir など)
   - `MicrosoftGame.config` (target ごと)、`PackageLayout.xml`、ロゴ一式、`<exe>.cf`
2. **configure / build** — `cmake --preset gdk-desktop|gxdk-scarlett|gxdk-xboxone -B PROJECT_DIR/build/gdk/<target>`
   - 外枠 CMakeLists の処理順 (iOS/Linux と同じ):
     myapp.cmake → `krkrz_merge_vcpkg_manifest` → `project()` → SDL3 (FetchContent, タグ固定)
     → CommonExternals → `KRKRZ_*_PLATFORM` 設定 → `add_subdirectory(krkrz_dev/src/core)`
   - **必ず `--preset` 経由**で build (XdkEditionTarget を伝えるため)
3. **stage** — layout ディレクトリ `PROJECT_DIR/build/gdk/<target>/layout/<config>/` を作る
   - 先勝ち順: エンジン exe + GDK ランタイム DLL (Desktop) → 生成物 (config / ロゴ / .cf) → 案件の assetPack
   - assetPack 書式は android / ios / linux と同一 (`mirror|flatten`, `from`, `to`, `include`, `exclude`)
4. **package** — `MakePkg pack /f PackageLayout.xml /d layout /pd package` (Desktop は `/pc`)
5. **deploy / run** — Desktop: `wdapp register layout` → `wdapp launch`、Xbox: `xbapp deploy layout` → `xbapp launch`

## 5. gdk-config.json スキーマ案

既存 (app-config / ios-config / linux-config) と `cmake` / `assetPack` を共通にし、
1 つの案件フォルダに並べて同じ data/ を使えるようにする。

```json
{
  "name": "Sample",
  "version": "1.0.0.0",
  "exeName": "krkrz",
  "orgName": "wamsoft",
  "appName": "krkrz_sample",
  "targets": ["desktop", "scarlett"],
  "identity": {
    "name": "Sample.Krkrz",
    "publisher": "CN=Publisher",
    "titleId": "FFFFFFFF",
    "msaAppId": "PleaseChangeMe",
    "storeId": ""
  },
  "displayName": "krkrz sample",
  "logo": "${PROJECT_DIR}/setup/gdk/logo.png",
  "splash": "${PROJECT_DIR}/setup/gdk/splash.png",
  "resourceDir": "",
  "gpuShaderDir": "",
  "config": { "options": [] },
  "cmake": {
    "pluginFolders": ["${BUILD_SYSTEM_DIR}/plugins", "${KRKRZ_BASE}/krkrz_dev/src/plugins"],
    "plugins": ["json", "csvParser", "KAGParserEx", "saveStruct", "scriptsEx"],
    "options": []
  },
  "assetPack": {
    "baseFolder": "${PROJECT_DIR}",
    "sources": [
      { "type": "mirror", "from": "data", "to": "data", "exclude": ["**/*.psd", "**/*.bak"] },
      { "type": "flatten", "from": "archive", "include": ["*.xp3"] }
    ]
  },
  "package": { "chunks": [] }
}
```

- `plugins` に書いたものは全部 static (GDK/Xbox は動的ロード前提にしない)。`staticPlugins` キーは無視。
- `identity` の実値は案件側にのみ置く (公開リポジトリには placeholder だけ)。
- `package.chunks`: 大きな xp3 を別 chunk に分ける拡張用 (初期は Launch chunk 1 本)。

## 6. core (krkrz_dev) 側に必要な修正

外枠だけでは解決できないもの。core に機種名を持ち込まない方針は維持し、汎用フックとして足す。

| 項目 | 内容 |
|---|---|
| stdapp.cpp 除外フック (Xbox で必要) | Desktop は stdapp.cpp のままで動作確認済み (P0)。Xbox も `WIN32` が真のため `sources.cmake` で `stdapp.cpp` / `winres.cpp` / `ThreadImpl.cpp` が自動追加され、独自 Application と重複する。`KRKRZ_APP_PLATFORM_OVERRIDE` (仮) で stdapp.cpp を外せるようにする |
| `KRKRZ_DESKTOP` | GDK も WIN32 なので desktop 扱いになる。Xbox では OFF にできるようにする |
| リソース埋め込み | `.rc` + FindResource 経路が Xbox で使えるか要確認。不可なら UNIX 同様の resource_table 方式を選べるようにする |
| SDL3 の差し替え | 既存の `if(NOT TARGET SDL3::SDL3)` で対応可 (修正不要) |
| 静的プラグイン登録 | `/WHOLEARCHIVE` 対応済み。GDK でも登録が落ちないことを確認する |
| miniaudio | `MA_WIN32_GDK` 相当の定義が必要か確認 |

## 7. 描画まわり (最大の論点)

- **Xbox では OpenGL / ANGLE が使えない**。Xbox ターゲットは
  `KRKRZ_USE_OPENGL=OFF` + `KRKRZ_CANVAS_GPU=ON` (SDL_GPU / D3D12) が前提になる。
- `gpushaderc.py` の現行出力は SPIR-V と PRIVATE の 2 形式。D3D12 用に
  SPIR-V → HLSL (spirv-cross) → DXIL (dxc) の経路を追加する必要がある (core 側ツールの拡張)。
- 案件スクリプトが使う ShaderProgram は `gpushaders/` に事前収集 (`-gpushadercollect`) してパック化する運用。
- Desktop は当面 OpenGL (WGL / ANGLE) でも可。ただし Xbox と挙動を揃えるなら Desktop も GPU 版に寄せる。

## 8. SDL3

- `https://github.com/wamsoft/SDL.git` の `gdk-cmake-support-3.4.18` (release-3.4.18 + GDK/GXDK CMake 対応 +
  下記修正) を外枠の FetchContent で固定して先に用意する (core の FetchContent(main) を使わない)。
- 3.4.8 で Desktop が無言終了していた件の原因は SDL 側の不具合: GameInput が名前 NULL のパッドを渡すと
  `HIDAPI_DriverSwitch_IsSupportedDevice` の `SDL_strcmp(NULL, ...)` で落ちる (Xbox 360 系パッド接続時)。
  上流 main と同じ `name &&` ガードを fork に追加して解消 (3.4.x ブランチには未反映)。
- XGameRuntime 初期化は SDL 側 (`SDL_sysmain_runapp.cpp`)。core の main.cpp は `SDL_MAIN_USE_CALLBACKS` なので相性は良い。
- Static CRT を全ターゲットで統一 (`CMAKE_MSVC_RUNTIME_LIBRARY` を FetchContent より前に設定)。

## 9. P0 で分かったこと

- Desktop は core 無改修で動く (stdapp.cpp の InitPath がそのまま使える。exe 隣の data/ を自動検出)。
- ビルドツリーのパスが長いと harfbuzz の取得 (テストデータのファイル名が長い) で失敗する。
  `KRKRZ_GDK_BUILD_ROOT` / `buildDir` で短い場所に逃がせるようにした。
- lineParser は静的リンク用のエントリ (`krkrz_plugin_<name>`) が無く static では使えない (プラグイン側の修正が必要)。
- PackageLayout.xml は stage 後の layout の実フォルダから生成する (FileGroup の Include はサブフォルダを辿らないため)。

## 10. P2 (Xbox) で分かったこと

- GAMES では wingdi.h の RGBQUAD / BITMAPINFO / LOGFONTW が無い (BITMAPINFOHEADER はある)。
  core / tp_stub の非 Windows 用定義を GAMES でも使うようにした。
- デスクトップ専用 API (コンソール / シェル / GDI / DirectWrite / Known Folder / EnumResourceNames 等) は
  core 側で `TVP_WIN32_DESKTOP` (= `_WIN32` かつ DESKTOP パーティション) 判定に切り替えた。
- vcpkg の freetype は UWP パッチで `generic` を置き換えて `#undef` するため harfbuzz の hb-ft.cc が壊れる → overlay port。
- Xbox の既定ライブラリに oldnames.lib が入らない (strdup / stricmp / fileno 等)。
- core が shell32 を常にリンクしていると、SDL が使う CommandLineToArgvW が SHELL32.dll から import され
  Xbox で起動できない → shell32 はデスクトップのみ。
- ThorVG が OpenMP を自動検出すると VCOMP140.DLL を import する → Xbox では検出を止める。
- 全画面表示: core の常時フルスクリーン環境 (1920x1080 論理面 + SDL_SetRenderLogicalPresentation) に
  SDL_PLATFORM_XBOXONE / XBOXSERIES を追加して対応。

- セーブ: SDL_GetPrefPath (XGameSaveFiles) は SCID のヒント (SDL_GDK_SERVICE_CONFIGURATION_ID) が無いと
  失敗し、user:// への書き込みはメモリ上だけで消える。SCID 指定時は XGameSaveFiles、無ければ
  PersistentLocalStorage/savedata/ を System.dataPath にする (devkit で再起動後の読み戻しを確認)。
  InitDataPath は OS のネイティブパス (R:\savedata\) で返す (file:// で返すと起動時の存在確認が失敗して
  "Data path does not exist ... failed" が出ていた)。PersistentLocalStorage のセーブは再デプロイ後も残る。
- Desktop: core の既定 dataPath は exe 隣の savedata で、インストールしたパッケージ (WindowsApps) では書けない。
  gen が .cf に datapath="$(appdatapath)/<org>/<app>" を出力するようにした。wdapp install した msixvc で
  再起動後の読み戻しを確認 (GDK のデスクトップパッケージは AppData が仮想化されず実フォルダに書かれる)。

- パッド入力: devkit (Xbox Series) でコアデモのギャラリー操作が一通り動くことを確認。
- GPU パーティクル (Canvas / ShaderProgram) のデモを開くと固まっていた。D3D12 用シェーダ (DXIL) が無く例外になるのは
  想定どおりで、固まる原因は core 側の未処理例外ダイアログの不具合だった (SDL 版共通):
  - 未処理例外の表示はシステムイベントを止めてから Elements のダイアログを出すが、停止中はイベント配送が丸ごと
    止まるため、ウィンドウ更新も入力も届かずダイアログが描画・操作されなかった
  - GPUDrawDevice の onInit がウィンドウ更新の配送中に即時発火されるため、そこで出たダイアログはウィンドウ更新の
    再入禁止の内側で回っていた
  core で修正し、例外ダイアログが表示され Ⓑ で閉じると終了することを devkit で確認。Ⓐ はボタンにフォーカスが
  無い状態では効かないことがある (要確認)。
- Xbox One: Scarlett と同じ構成のままビルド・パッケージ作成が通る (import は d3d12_x.dll に変わるだけ)。
  Xbox Series devkit 上の互換動作でコアデモの起動を確認 (Xbox One 実機は未確認)。
- Xbox One: Elements ダイアログ (システム情報) を開くとクラッシュした。SDL の D3D12 バックエンド (GPU / renderer) が
  バッファ→テクスチャ転送の行ピッチを 256 (D3D12_TEXTURE_DATA_PITCH_ALIGNMENT) で揃えていたが、Xbox One は 1024
  (D3D12XBOX_TEXTURE_DATA_PITCH_ALIGNMENT) が必要。SDL fork で修正 (上流 main も未修正)。Scarlett は 256 なので影響なし。

- Canvas の D3D12 対応: core の gpushaderc.py に --target dxil (SPIR-V → spirv-cross HLSL SM6.0 → dxc)、
  パック形式 DXIL、組み込みシェーダーの DXIL 版を追加。GLSL の書き換えで決めている set 番号が、そのまま SDL_GPU の
  D3D12 の register space になる。DXIL は Xbox と -gpudriver=direct3d12 のときだけ要求する (SDL は D3D12 を
  Vulkan より先に試すため)。devkit で GPU パーティクルが動作 (点は 1 ピクセル)。Xbox 用の事前コンパイル
  (Runtime Recompilation の警告を消す) は未対応。

## 11. 事前検証で分かっていること

- toolchain ファイルは使わず VS generator の platform 名 (`Gaming.*`) で GDK MSBuild 拡張を使う。
  vcpkg は `vcpkg.cmake` を直接 toolchain にし、chainload しない。
- `XdkEditionTarget` を preset の environment で固定。`cmake --build` は必ず `--preset` 経由。
- `find_package` は SDL の FetchContent より前。
- Xbox triplet の回避策: `unset(ENV{GameDKCoreLatest})`、`/DEFAULTLIB:onecore_apiset.lib`。
- Desktop の loose-run では `Microsoft.Xbox.Services.GDK.C.Thunks.dll` を手動コピー。
- Xbox ビルドが PC 用 DLL を import していないかを `dumpbin /dependents` で確認する。
- MakePkg は SplashScreenImage 必須、ロゴの実ファイルが layout に無いと 0x80070057。
- Desktop exe は msys2 / Git-Bash から直接起動すると DLL 解決に失敗する。

## 12. 段階計画

| 段階 | 内容 | 完了条件 |
|---|---|---|
| P0 | 外枠骨格 (完了) | gdk-desktop でコアデモが layout から起動 (確認済み) |
| P1 | gen / stage / package (完了)、wdapp register / launch (未検証) | 案件フォルダから msixvc が作れる (サンプルで確認済み) |
| P2 | Scarlett: ビルド・起動 (完了)。全画面表示・セーブ往復・パッド入力・Canvas の D3D12 (DXIL) シェーダ (完了) | devkit でコアデモ起動 (確認済み) |
| P3 | XboxOne (ビルド・パッケージ作成まで完了)、パッケージ chunk 分割、実績等の GDK 専用プラグイン | 必要に応じて |

## 13. 公開リポジトリとしての注意

- 案件名・タイトル・課題キーを書かない。identity 実値は案件側の gdk-config.json にだけ置く。
- 他機種のコンソール SDK 由来の情報は持ち込まない。Xbox 向けは
  公開 GDK と SDL 上流に既に出ている範囲 (platform 名、ライブラリ名) に留める。
