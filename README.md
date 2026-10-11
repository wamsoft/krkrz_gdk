# krkrz_gdk

吉里吉里Z (krkrz) を Microsoft GDK 向けにビルド・パッケージ化するための外枠リポジトリです。

| ターゲット | platform | 状況 |
|---|---|---|
| `desktop` | Gaming.Desktop.x64 (PC / Microsoft Store) | ビルド・起動確認済み |
| `scarlett` | Gaming.Xbox.Scarlett.x64 (Xbox Series X\|S) | 未対応 (描画の SDL_GPU 化が必要) |
| `xboxone` | Gaming.Xbox.XboxOne.x64 (Xbox One) | 未対応 |

エンジン本体は持たず、隣に置いた [krkrz_dev](https://github.com/wamsoft/krkrz_dev) (**master**) を参照します。
案件ごとの設定と資材は案件フォルダ (`PROJECT_DIR`) に置き、出力も案件フォルダに出します。
構成は krkrz_android / krkrz_web / krkrz_ios / krkrz_linux と同じ考え方です。

```
KRKRZ_BASE/
  krkrz_dev/     エンジン + プラグイン (git clone -b master --recursive)
  krkrz_gdk/     このリポジトリ (共通ビルドシステム)
PROJECT_DIR/     案件フォルダ: gdk-config.json + 資材。出力は PROJECT_DIR/build/gdk/
```

## 必要なもの

- Visual Studio 2022 (C++ / CMake) と Microsoft GDK (VS 統合済みのエディション。既定 `250404`)
  - Xbox ターゲットは GDKX (Xbox 拡張) も必要
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
| `identity` | `name` / `publisher` / `titleId` / `msaAppId` / `storeId` (Partner Center の値。実値は案件側にだけ置く) |
| `shellVisuals` | `publisherDisplayName` / `description` / `foregroundText` / `backgroundColor` |
| `logoDir` | `Logo44x44.png` / `Logo100x100.png` / `Logo150x150.png` / `Logo480x480.png` / `SplashScreenImage.png` を置いたフォルダ。無いものは placeholder を生成 |
| `icon` | exe に埋め込む .ico (`KRKRZ_WIN_ICON`) |
| `resourceDir` | エンジン埋め込みリソース (config.cf / messages.json / フォント) の差し替え (`KRKRZ_RESOURCE_DIR`) |
| `config.options` | `<exe>.cf` に追記する起動オプション |
| `cmake.pluginFolders` / `cmake.plugins` | 組み込むプラグイン。**GDK では全て静的リンク** (`staticPlugins` は不要) |
| `cmake.options` | configure に渡す追加の `-D` |
| `assetPack` | 資材の配置 (下記) |
| `gdk.edition` | `XdkEditionTarget` (環境変数が優先。既定 `250404`) |
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

`https://github.com/wamsoft/SDL.git` の `gdk-cmake-support-3.4.18` (SDL 3.4.18 + GDK / GXDK の CMake 対応) を
FetchContent で固定して使います。ローカルの clone を使うときは
`CMAKEOPT='-DFETCHCONTENT_SOURCE_DIR_SDL3=/path/to/SDL'` を指定します。

## 注意点

- `XdkEditionTarget` は VS に統合されている GDK エディションと一致させる必要があります。
  `cmake --build` を直接呼ぶときは環境変数を設定するか `--preset` 経由にしてください
- Desktop の exe を msys2 / Git-Bash から直接起動すると DLL 解決に失敗することがあります。PowerShell / cmd から起動してください
- MakePkg はロゴと SplashScreenImage が layout に無いと失敗します (`gen` が placeholder を作ります)
- krkrz_dev が master 以外のブランチだと configure 時に警告します (`-DKRKRZ_GDK_ALLOW_NON_MASTER=ON` で抑止)

## ライセンス

このリポジトリ (ビルドスクリプト・ツール・テンプレート) は [MIT License](LICENSE) です。

ビルド時に参照・取得する以下のものは、それぞれのライセンスに従います。このリポジトリのライセンスは及びません。

- 吉里吉里Z 本体とプラグイン (krkrz_dev 配下の各 submodule)
- SDL3 (zlib License) と、vcpkg / FetchContent で取得する依存ライブラリ
- Microsoft GDK (Microsoft のライセンス条項)

配布物に必要なライセンス表記は、使ったエンジン・プラグイン・ライブラリに合わせて案件側で同梱してください。
