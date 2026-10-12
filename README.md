# krkrz_gdk

吉里吉里Z (krkrz) を **Microsoft GDK (PC / Xbox) 向けにビルド・パッケージ化する**ための外枠リポジトリです。
SDL3 ベースで、プラグインは全て静的リンクします。

| ターゲット | platform | 状況 |
|---|---|---|
| `desktop` | Gaming.Desktop.x64 (PC / Microsoft Store) | ビルド・起動、msixvc のインストールとセーブを確認済み |
| `scarlett` | Gaming.Xbox.Scarlett.x64 (Xbox Series X\|S) | devkit で起動・パッド入力・セーブ・Canvas (D3D12)・動画を確認済み |
| `xboxone` | Gaming.Xbox.XboxOne.x64 (Xbox One) | Xbox Series devkit (互換動作) で起動を確認。Xbox One 実機は未確認 |
| `win` | x64 (GDK なし、通常の Win32) | Xbox と同じ描画構成 (SDL_GPU / D3D12) の PC 版。開発中の確認用 |

エンジン本体は持たず、隣に置いた [krkrz_dev](https://github.com/wamsoft/krkrz_dev) (**master**) を参照します。
案件ごとの設定と資材は案件フォルダ (`PROJECT_DIR`) に置き、出力も案件フォルダに出します。
構成は krkrz_android / krkrz_web / krkrz_ios / krkrz_linux と同じ外枠方式です (このリポジトリは「ガワ」のみ。
エンジン本体・プラグインには手を入れず、GDK 固有のビルド定義・パッケージングだけを持ちます)。

```
KRKRZ_BASE/
  krkrz_dev/     エンジン + プラグイン (git clone -b master --recursive)
  krkrz_gdk/     このリポジトリ (共通ビルドシステム)
PROJECT_DIR/     案件フォルダ: gdk-config.json + 資材。出力は PROJECT_DIR/build/gdk/
```

## 必要なもの

- Visual Studio 2022 (C++ / CMake) と Microsoft GDK (VS 統合済みのエディション。既定 `250404`)
  - Xbox ターゲットは GDKX (Xbox 拡張) と devkit も必要 (Microsoft との開発者契約が要ります)
  - Xbox ターゲットは Canvas のシェーダー変換に Vulkan SDK (glslangValidator / spirv-cross) も使います
- vcpkg (`VCPKG_ROOT`)
- Python 3.9 以降 (標準ライブラリのみ使用)
- git (configure 時に SDL3 などを取得するためネットワークが必要)

## 準備

```bash
cd $KRKRZ_BASE
git clone -b master --recursive https://github.com/wamsoft/krkrz_dev.git
git clone https://github.com/wamsoft/krkrz_gdk.git
```

`KRKRZ_BASE` 環境変数を設定しない場合は krkrz_gdk の親フォルダを使います。

## ビルド

```bash
# サンプル (コアデモ) を Desktop 向けにビルド → layout 作成 → msixvc 作成
python tools/krkrz_gdk.py all

# 案件を指定
python tools/krkrz_gdk.py --project /path/to/game --target desktop all

# layout の exe を直接起動 (Desktop)
python tools/krkrz_gdk.py --project /path/to/game run
```

`make PROJECT_DIR=/path/to/game TARGET=desktop all` でも同じです (Makefile は薄いラッパー)。

| コマンド | 内容 |
|---|---|
| `gen` | gdk-config.json から myapp.cmake / app.cmake / MicrosoftGame.config / ロゴ / `<exe>.cf` を生成 |
| `configure` | cmake configure (VS2022 generator + `Gaming.*` platform) |
| `build` | エンジン exe をビルド (`--config Release|Debug`) |
| `stage` | layout フォルダを作る (エンジン → 生成物 → assetPack の先勝ち) |
| `package` | MakePkg で msixvc (Desktop) / xvc (Xbox) を作る |
| `run` | layout の exe を直接起動 (Desktop) |
| `register` / `launch` | wdapp で layout を登録して起動 (Desktop) |
| `deploy` / `launch` | xbapp で devkit に送って起動 (Xbox) |
| `vars` | 解決済みのパスなどを表示 |

出力先:

```
PROJECT_DIR/build/gdk/
  generated/                 gen の生成物
  <target>/                  cmake ビルドツリー
  <target>/layout/<config>/  layout (loose 実行・パッケージの元)
  <target>/package/<config>/ msixvc / xvc
```

ビルドツリーのパスが長いと依存ライブラリの取得に失敗します (Windows のパス長制限)。
案件フォルダが深い場合は `KRKRZ_GDK_BUILD_ROOT` 環境変数か gdk-config.json の `buildDir` で短い場所に移してください。

## gdk-config.json

サンプルはこのリポジトリ直下の [gdk-config.json](gdk-config.json) です。
`cmake` と `assetPack` の書式は krkrz_android の app-config.json / krkrz_ios / krkrz_linux と共通なので、
1 つの案件フォルダに並べて同じ data/ を使い回せます。

| キー | 内容 |
|---|---|
| `name` / `displayName` / `version` | 表示名とパッケージバージョン (`x.y.z.w`) |
| `exeName` | 実行ファイル名 (拡張子なし) |
| `orgName` / `appName` | `<exe>.cf` に書く orgname / appname (セーブ先の識別) |
| `targets` | 対象ターゲット。先頭が `--target` 省略時の既定 |
| `identity` | `name` / `publisher` / `titleId` / `msaAppId` / `storeId` / `scid` (Partner Center の値。実値は案件側にだけ置く) |
| `shellVisuals` | `publisherDisplayName` / `description` / `foregroundText` / `backgroundColor` |
| `logoDir` | `Logo44x44.png` / `Logo100x100.png` / `Logo150x150.png` / `Logo480x480.png` / `SplashScreenImage.png` を置いたフォルダ。無いものは placeholder を生成 |
| `icon` | exe に埋め込む .ico (`KRKRZ_WIN_ICON`) |
| `gpuShaderDir` | Canvas の ShaderProgram 用シェーダー (実行時に `-gpushadercollect` で書き出した `<key>.vs` / `<key>.fs` の組) のフォルダ。Xbox では `stage` が Canvas の組み込みシェーダーと合わせて D3D12 用 (DXIL) の `canvas_shaders.kzgs` にして exe の隣に置く |
| `resourceDir` | エンジン埋め込みリソース (config.cf / messages.json / フォント) の差し替え (`KRKRZ_RESOURCE_DIR`) |
| `dataPath` | Desktop のセーブ先 (`<exe>.cf` の `datapath`)。既定 `$(appdatapath)/<orgName>/<appName>`。区切りは `/` |
| `config.options` | 起動オプション。Desktop は `<exe>.cf`、Xbox はアプリフォルダの `config.cf` に書く (`datapath=` を書くと `dataPath` より優先) |
| `cmake.pluginFolders` / `cmake.plugins` | 組み込むプラグイン。**GDK では全て静的リンク** (`staticPlugins` は不要) |
| `cmake.options` | configure に渡す追加の `-D` |
| `assetPack` | 資材の配置 (下記) |
| `gdk.edition` | `XdkEditionTarget` (環境変数が優先。既定 `250404`) |
| `gdk.persistentLocalStorageMB` | MicrosoftGame.config の PersistentLocalStorage サイズ (既定 256。0 で出力しない) |
| `buildDir` | 出力ルート (既定 `${PROJECT_DIR}/build/gdk`) |

`${PROJECT_DIR}` / `${BUILD_SYSTEM_DIR}` / `${KRKRZ_BASE}` と環境変数を展開します。相対パスは PROJECT_DIR 基準です。

### assetPack

```json
"assetPack": {
  "baseFolder": "${PROJECT_DIR}",
  "transfer": "copy",
  "sources": [
    { "type": "mirror",  "from": "data",    "to": "data", "exclude": ["**/*.psd", "**/*.bak"] },
    { "type": "flatten", "from": "archive", "include": ["*.xp3"] }
  ]
}
```

- `mirror` はフォルダ構成を保って `to` へ、`flatten` はファイル名だけで `to` 直下へ置きます
- `include` / `exclude` は Ant 風グロブ (`**` は 0 個以上のフォルダ)
- 同じ配置先は先に書いたものが勝ちます。エンジン一式と生成物は assetPack より先に置かれます
- エンジンは起動時に exe と同じフォルダの `data.xp3` → exe 結合 xp3 → `data/startup.tjs` の順で探します
- xp3 はこのリポジトリでは作りません。案件側で作ったものを `flatten` で取り込みます

## SDL3

`https://github.com/wamsoft/SDL.git` の `gdk-cmake-support-3.4.18` (SDL 3.4.18 + GDK / GXDK の CMake 対応と
Xbox 向けの修正) を、コミットを固定して FetchContent で使います。別の版を使うときは `-DKRKRZ_GDK_SDL_GIT_TAG=<tag>`、ローカルの clone を使うときは `CMAKEOPT='-DFETCHCONTENT_SOURCE_DIR_SDL3=/path/to/SDL'` を指定します。

## 注意点

- `XdkEditionTarget` は VS に統合されている GDK エディションと一致させる必要があります。
  `cmake --build` を直接呼ぶときは環境変数を設定するか `--preset` 経由にしてください
- Desktop の exe を msys2 / Git-Bash から直接起動すると DLL 解決に失敗することがあります。PowerShell / cmd から起動してください
- MakePkg はロゴと SplashScreenImage が layout に無いと失敗します (`gen` が placeholder を作ります)
- krkrz_dev が master 以外のブランチだと configure 時に警告します (`-DKRKRZ_GDK_ALLOW_NON_MASTER=ON` で抑止)

## Desktop のセーブ先

core の既定 (exe 隣の `savedata`) は、インストールしたパッケージ (`C:\Program Files\WindowsApps\...`) では
書き込めません。`gen` は `<exe>.cf` に `datapath="$(appdatapath)/<orgName>/<appName>"` を出力し、
Roaming AppData (`%APPDATA%\<orgName>\<appName>\`) に保存します。
`$(personalpath)` / `$(savedgamespath)` / `$(exepath)` も使えます。

## WIN 版 (Xbox と同じ構成を PC で動かす)

`--target win` は GDK を使わない通常の Win32 版です。プラグイン・資材・起動オプションは Xbox と同じものを使い、
描画も Xbox と同じ SDL_GPU (Canvas の GPU 版、D3D12) にします。devkit を使わずに PC で動作を確かめたり、
REPL などデスクトップの開発機能で調べたりするのに使います。GDK のインストールは要りません。

```bash
python tools/krkrz_gdk.py --project /path/to/game --target win build stage run
# 起動オプションを足す
RUNOPT="-replfile=C:/tmp/ch" make PROJECT_DIR=/path/to/game TARGET=win run
```

- `stage` は `<exe>.cf` に `gpudriver=direct3d12` を足します (`config.options` に `gpudriver=` を書けばそちらが優先。
  `vulkan` で Vulkan)
- `gpuShaderDir` のシェーダーは汎用の dxc (Vulkan SDK) で DXIL にして `canvas_shaders.kzgs` として exe の隣に置きます
- `package` は layout をそのまま zip にします
- OpenGL 版にしたいときは `CMAKEOPT='-DKRKRZ_USE_OPENGL=ON -DKRKRZ_CANVAS_GPU=OFF'`

**スクリプトのシェーダーを集める**: Xbox と WIN 版は実行時にシェーダーをコンパイルできないので、ShaderProgram の
ソースは事前にパックにしておく必要があります。WIN 版を `-gpushadercollect=<フォルダ>` 付きで動かして該当の画面を
一通り開くと、パックに無いシェーダーが `<key>.vs` / `<key>.fs` として書き出されます。そのフォルダを
gdk-config.json の `gpuShaderDir` に指定すると、WIN 版・Xbox とも `stage` でパックに入ります。

## Xbox で動かす

```bash
python tools/krkrz_gdk.py --project /path/to/game --target scarlett build stage deploy launch
```

`deploy` / `launch` は GDK の `xbapp` で、既定の devkit (`xbconnect` で設定) に layout を送って起動します。
ログは `xbdbgmon /t`、画面は `xbcapture` で取れます。手順と注意は [docs/xbox.md](docs/xbox.md) にまとめています。

Desktop との主な違い:

- Application は core の stdapp.cpp ではなく [src/gdkapp.cpp](src/gdkapp.cpp) を使います
- エンジンリソース (config.cf / messages.json / フォント) は exe に埋め込まず layout の `resource/` に置きます。
  `resourceDir` 未指定時は core 同梱のリソース一式 (同梱フォント含む) を使います
- 起動オプションは `<exe>.cf` ではなく `config.cf` に書きます。機種別は `config_xbox.cf` / `config_scarlett.cf` /
  `config_xboxone.cf` (`System.platformTag`)
- 画面は 1920x1080 の論理面に固定し、実画面に合わせて拡大表示します
- セーブ (`System.dataPath`) は `identity.scid` があれば XGameSaveFiles (クラウド同期)、無ければ
  PersistentLocalStorage の下の `savedata/` (開発用)
- 描画は SDL_GPU (D3D12)。Canvas のシェーダーは `stage` が GXDK の dxc で事前コンパイルして同梱します

## 機能の対応状況

| 機能 | Desktop | win | Xbox |
|---|---|---|---|
| 起動・全画面表示 | ○ | ○ | ○ (1920x1080 論理面) |
| パッド入力 | ○ | ○ | ○ |
| マウス / キーボード | ○ | ○ | △ `gameinput=yes` で GameInput から読む (既定 off)。リモート制御のマウス移動は取れない / USB マウスは未確認 / カーソルは表示されない |
| セーブ (`System.dataPath`) | ○ `%APPDATA%\<orgName>\<appName>\` | ○ 同左 | ○ XGameSaveFiles (SCID 指定時) / PersistentLocalStorage |
| 描画 | OpenGL (既定) | SDL_GPU (D3D12) | SDL_GPU (D3D12) |
| Canvas / ShaderProgram | ○ OpenGL 版 | ○ SDL_GPU 版 | ○ SDL_GPU 版 |
| 動画 (VideoOverlay) | WebM / MPEG-1 | 同左 | 同左。overlay 系の `setPos` / `setSize` はどれも効かず画面全体に出る (SDL 版共通の制限) |
| Elements ダイアログ | ○ | ○ | ○ |
| 静的プラグイン | ○ | ○ | ○ |
| REPL | ○ console / `-replfile` / `-replweb` | ○ 同左 | `-replweb` のみ (devkit 越しの利用は未確認) |
| 読み上げ (AccessKit) / LogCore | ○ | ○ | × |

SDL_GPU 版では ShaderProgram のシェーダーを事前変換したもの (`gpuShaderDir`) しか使えません。点スプライトは
D3D12 に点の大きさが無いので四角形で代用しています。

既知の制限と未確認の項目は [docs/xbox.md](docs/xbox.md#既知の制限未確認) を見てください。

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| [docs/design.md](docs/design.md) | 構成 (3 層分離 / ビルドの流れ / Xbox で core に渡すオプション / SDL fork の変更点 / vcpkg) |
| [docs/xbox.md](docs/xbox.md) | devkit での運用、セーブ、シェーダーの事前コンパイル、実機で分かったこと、既知の制限 |
| [vcpkg-ports/README.md](vcpkg-ports/README.md) | vcpkg の overlay port (freetype) |
| [plugins/README.md](plugins/README.md) | GDK 専用プラグイン置き場 |
| 本体 [PlatformPorting.md](https://github.com/wamsoft/krkrz/blob/master/doc/PlatformPorting.md) | 外枠から本体を組み込む口 (共通) |
| 本体 [CanvasGPU.md](https://github.com/wamsoft/krkrz/blob/master/doc/CanvasGPU.md) | Canvas の SDL_GPU 版 / シェーダー変換 (DXIL を含む) |

## ライセンス

このリポジトリ (ビルドスクリプト・ツール・テンプレート) は [MIT License](LICENSE) です。

ビルド時に参照・取得する以下のものは、それぞれのライセンスに従います。このリポジトリのライセンスは及びません。

- 吉里吉里Z 本体とプラグイン (krkrz_dev 配下の各 submodule)
- SDL3 (zlib License) と、vcpkg / FetchContent で取得する依存ライブラリ
- Microsoft GDK (Microsoft のライセンス条項)

配布物に必要なライセンス表記は、使ったエンジン・プラグイン・ライブラリに合わせて案件側で同梱してください。
