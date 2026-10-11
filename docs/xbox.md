# Xbox (devkit) での運用と分かったこと

Xbox ターゲット (`scarlett` / `xboxone`) を devkit で動かすときの手順と、実機で分かったことのまとめ。
構成は [design.md](design.md)、本体側の共通事項は本体ドキュメント
([PlatformPorting.md](https://github.com/wamsoft/krkrz/blob/master/doc/PlatformPorting.md) /
[CanvasGPU.md](https://github.com/wamsoft/krkrz/blob/master/doc/CanvasGPU.md))。

## 必要なもの

- Microsoft GDK と GDKX (Xbox 拡張)。Xbox 向けの開発には Microsoft との開発者契約が要る
- devkit (Xbox Series X|S。Xbox One 版も Series の devkit で互換動作として動かせる)
- Vulkan SDK (glslangValidator / spirv-cross / dxc)。Canvas のシェーダー変換に使う

## devkit へ送って起動する

```bash
xbconnect <devkit の IP>          # 既定の devkit を設定 (GDK のコマンドプロンプトで一度)
python tools/krkrz_gdk.py --project /path/to/game --target scarlett build stage deploy launch
```

- `deploy` は `xbapp deploy <layout>` で loose のまま送る (パッケージ化不要)
- `launch` は `xbapp launch <PFN>!Game`
- ログ (`OutputDebugString` に出るエンジンのログ): `xbdbgmon /t` で PC 側に流せる
- 画面: `xbcapture <file>.png` で devkit の画面を撮れる
- `-replweb` はビルドに入っている (0.0.0.0 で待ち受け)。`config.options` に `-replweb=<port>` を書けば
  起動するが、devkit のネットワーク越しに繋ぐ運用はまだ確かめていない

## 起動オプションと機種別の設定

- Xbox では `<exe名>.cf` は読まれない (デスクトップだけ)。stage が `config.cf` として layout に置く
  (`orgname` / `appname` / `scid` / gdk-config.json の `config.options`)
- 機種別の差分は `config_xbox.cf` / `config_scarlett.cf` / `config_xboxone.cf` に書ける
  (機種タグは「一般 → 具体」の順に `xbox;scarlett` / `xbox;xboxone`)

## セーブ

| 条件 | 保存先 | 備考 |
|---|---|---|
| `identity.scid` あり | XGameSaveFiles (SDL の user storage) | クラウド同期。MicrosoftGame.config に `SaveGameStorage/SCID`、`config.cf` に `scid=` を出す |
| `scid` なし | PersistentLocalStorage の下の `savedata/` | 本体ローカルのみ (開発用)。再起動・再デプロイでも残る |

- SDL の `SDL_GetPrefPath` (XGameSaveFiles) は SCID のヒント (`SDL_GDK_SERVICE_CONFIGURATION_ID`) が無いと失敗し、
  そのまま `user://` に書くとメモリ上だけで消える。だから SCID が無いときは PersistentLocalStorage を使う
- PersistentLocalStorage の大きさは `gdk.persistentLocalStorageMB` (既定 256 MB)
- `System.dataPath` は OS のネイティブパス (`R:\savedata\` など) で返す (`file://` だと起動時の存在確認で
  「Data path does not exist」の警告が出る)

## 描画 (SDL_GPU / D3D12)

- OpenGL が無いので Canvas は SDL_GPU 版 (`KRKRZ_CANVAS_GPU`) で D3D12 (DXIL) を使う。通常の描画は SDL_Renderer の
  GPU レンダラー
- 画面は 1920x1080 の論理面に固定し、実画面に合わせて拡大表示する (本体の常時全画面環境)
- **シェーダーの事前コンパイル**: 汎用の dxc で作った DXIL は、Xbox が読み込み時に機種のコードへ
  再コンパイルする (`XBSC W1003` 警告が出て時間がかかる)。GXDK の `bin/<Scarlett|XboxOne>/dxc.exe` で
  コンパイルすると機種のコードが入る。
  - Canvas: stage が組み込みシェーダーと `gpuShaderDir` のシェーダーを機種の dxc で `canvas_shaders.kzgs` に
    まとめ、exe の隣に置く (エンジン内蔵の汎用 DXIL より優先される)
  - SDL_Renderer 自身のシェーダー: SDL fork がビルド時に機種の dxc でコンパイルする
  - 機種向けのコンパイルにはシェーダーにルートシグネチャが要る。SDL_GPU の D3D12 がパイプラインごとに作るものと
    同じものを埋め込んでいる (Canvas は gpushaderc.py、SDL 側は `compile_shaders_xbox.cmake`)
  - コアデモのギャラリー・GPU パーティクル・YUV 動画 (WebM / MPEG-1)・線の描画 (memoverlay) で W1003 は 0 件
- **点スプライト**: D3D12 には点の大きさが無いので、`gl_PointSize` を書くシェーダーは変換時に「点を四角形に広げる」
  形へ書き換え、エンジンが四角形のインスタンス描画にする (`gl_PointCoord` も効く)。PC (Vulkan) と同じ粒の大きさ・
  ぼかしで出ることを確認
- **スクリプトの ShaderProgram**: WIN 版 (`--target win`) を `-gpushadercollect=<フォルダ>` 付きで動かし、書き出された
  `<key>.vs` / `<key>.fs` の組のフォルダを `gpuShaderDir` に指定する。パックに無いシェーダーは Xbox では作れない
  (実行時にソースからコンパイルする手段が無い)。WIN 版も同じ D3D12 なので、WIN 版で動けば Xbox でも同じパックで動く

## 実機で分かったこと (トラブルの記録)

| 症状 | 原因 / 対処 |
|---|---|
| Xbox で起動できない (DLL 不足) | core が shell32 を常にリンクしていて、SDL の `CommandLineToArgvW` が SHELL32.dll から import されていた → shell32 はデスクトップだけ (core)。ThorVG の OpenMP 検出で VCOMP140.DLL が入る → 検出を止める。Xbox ビルドが PC 用 DLL を import していないかは `dumpbin /dependents` で確かめる |
| コンパイルエラー (RGBQUAD / BITMAPINFO / LOGFONTW / コンソール API など) | `WINAPI_FAMILY_GAMES` には無い → core を `TVP_WIN32_DESKTOP` で分けた |
| harfbuzz の hb-ft.cc が壊れる | vcpkg の freetype の UWP パッチ → overlay port |
| `strdup` / `stricmp` / `fileno` が未解決 | Xbox の既定ライブラリに oldnames.lib が無い → リンクに追加 |
| 全画面表示にならない | core の全画面固定の判定に `SDL_PLATFORM_XBOXONE` / `SDL_PLATFORM_XBOXSERIES` を追加 |
| セーブが再起動で消える | SCID 無しで XGameSaveFiles を使っていた → PersistentLocalStorage へ |
| GPU パーティクルを開くと固まる | 未処理例外のダイアログが描かれず入力も届かなかった (システムイベント停止中の配送 / ウィンドウ更新の再入) → core で修正 (SDL 版共通) |
| Xbox One で Elements のダイアログを開くとクラッシュ | D3D12 の転送の行ピッチ (Xbox One は 1024) → SDL fork で修正 |
| SDL レンダラーの事前コンパイル版で描画が落ちる | 頂点入力のセマンティクスが SDL の D3D12 の宣言 (`TEXCOORD<n>`) と違った → 入力を改名してコンパイル |
| `config.options` が効かない | `<exe名>.cf` はデスクトップだけ → `config.cf` で置く |

## 既知の制限・未確認

- **エラーダイアログを Ⓐ で閉じられないことがある** (Ⓑ では閉じる)。ボタンにフォーカスが無い状態が疑わしい。未調査
- **動画の再生矩形**: `vomOverlay` / `vomMixer` の `setPos` / `setSize` が効かず画面全体に出る (SDL 版共通の制限。
  本体側で実装予定 → 本体 `MovieMFMigration.md` 「SDL 版 overlay 動画の表示位置・大きさ」)
- **インデックス付きの点の描画** (`drawMesh` に index を渡す点) は四角形化しておらず点のまま
- Xbox One 実機は未確認 (Series devkit の互換動作のみ)
- PC の D3D12 は WIN 版で確認済み (2026-10-11: Canvas の各ページ・カスタムシェーダー・GPU パーティクル・線描画・Elements)。
  Desktop (GDK) の既定は OpenGL のまま
- devkit のネットワーク越しの `-replweb`、パッケージ (xvc) の chunk 分割、実績 / ユーザー / ストアは未着手
