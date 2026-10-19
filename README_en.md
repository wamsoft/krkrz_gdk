<!-- source_hash: b12c8e42e675 -->
# krkrz_gdk — Kirikiri Z for Microsoft GDK (PC / Xbox)

[日本語](README.md) | English

A wrapper repository for **building and packaging Kirikiri Z (krkrz) for the Microsoft GDK (PC / Xbox)**.
It is based on SDL3, and every plugin is linked statically.

- The engine and plugin sources come from [krkrz_dev](https://github.com/wamsoft/krkrz_dev) (**master**),
  placed next to this repository, through `KRKRZ_BASE`. This repository holds only the GDK-specific build
  definitions and packaging, and does not modify the engine or the plugins
- The per-title settings (`gdk-config.json`) and assets live in the project folder (`PROJECT_DIR`), and the
  output also goes into the project folder. This repository can also be built on its own as the bundled
  sample (the core demos)
- `cmake` (plugin configuration) and `assetPack` (asset collection) share their format with
  krkrz_android / krkrz_ios / krkrz_linux / krkrz_web

| Target | platform | Status |
|---|---|---|
| `desktop` | Gaming.Desktop.x64 (PC / Microsoft Store) | Build and launch, msixvc installation and saving confirmed |
| `scarlett` | Gaming.Xbox.Scarlett.x64 (Xbox Series X\|S) | Launch, gamepad input, saving, Canvas (D3D12) and movies confirmed on a devkit |
| `xboxone` | Gaming.Xbox.XboxOne.x64 (Xbox One) | Launch confirmed on an Xbox Series devkit (compatibility mode). Not checked on actual Xbox One hardware |
| `win` | x64 (no GDK, plain Win32) | A PC build with the same rendering setup as Xbox (SDL_GPU / D3D12). For checking during development |

## Requirements

- Visual Studio 2022 (C++ / CMake) and the Microsoft GDK (an edition integrated into VS; default `250404`)
  - The Xbox targets also need the GDKX (Xbox extensions) and a devkit (this requires a developer agreement with Microsoft)
  - The Xbox targets also use the Vulkan SDK (glslangValidator / spirv-cross) to convert Canvas shaders
- [vcpkg](https://github.com/microsoft/vcpkg) — set the environment variable `VCPKG_ROOT` to where it is installed
- Python 3.9 or later (standard library only)
- git (network access is needed, since SDL3 and others are fetched at configure time)

## Setup

Clone krkrz_dev and this repository into the same folder.

```bash
cd $KRKRZ_BASE
git clone -b master --recursive https://github.com/wamsoft/krkrz_dev.git
git clone https://github.com/wamsoft/krkrz_gdk.git
```

```
KRKRZ_BASE/
  krkrz_dev/     engine + plugins (git clone -b master --recursive)
  krkrz_gdk/     this repository (shared build system)
PROJECT_DIR/     project folder: gdk-config.json + assets. Output goes to PROJECT_DIR/build/gdk/
```

When the `KRKRZ_BASE` environment variable is not set, the parent folder of krkrz_gdk is used.

## Building and running

```bash
# Build the sample (core demos) for Desktop → create the layout → create the msixvc
python tools/krkrz_gdk.py all

# Specify a project folder
python tools/krkrz_gdk.py --project /path/to/game --target desktop all

# Start the exe in the layout directly (Desktop)
python tools/krkrz_gdk.py --project /path/to/game run
```

`make PROJECT_DIR=/path/to/game TARGET=desktop all` does the same (the Makefile is a thin wrapper).
`all` runs `gen` → `configure` → `build` → `stage` → `package` in order.

| Command | Description |
|---|---|
| `gen` | Generate myapp.cmake / app.cmake / MicrosoftGame.config / logos / `<exe>.cf` from gdk-config.json |
| `configure` | cmake configure (VS2022 generator + `Gaming.*` platform) |
| `build` | Build the engine exe (`--config Release|Debug`) |
| `stage` | Create the layout folder (engine → generated files → assetPack, first one wins) |
| `package` | Create the msixvc (Desktop) / xvc (Xbox) with MakePkg |
| `run` | Start the exe in the layout directly (Desktop) |
| `register` / `launch` | Register the layout with wdapp and start it (Desktop) |
| `deploy` / `launch` | Send it to the devkit with xbapp and start it (Xbox) |
| `vars` | Show the resolved paths and so on |

## Project folder (PROJECT_DIR)

This repository is a shared build system; the settings and assets of the title you build can live
in a separate folder.

| Variable | Meaning |
|---|---|
| `BUILD_SYSTEM_DIR` | The root of this repository. The tool determines it automatically |
| `PROJECT_DIR` | The project folder (`--project` or the environment variable `PROJECT_DIR`). `${PROJECT_DIR}/gdk-config.json` is read. When not set, this repository itself (the sample) |
| `KRKRZ_BASE` | The parent folder of krkrz_dev. When not set, the parent folder of krkrz_gdk |

Output:

```
PROJECT_DIR/build/gdk/
  generated/                 output of gen
  <target>/                  cmake build tree
  <target>/layout/<config>/  layout (for loose execution and the source of the package)
  <target>/package/<config>/ msixvc / xvc
```

If the build tree path is long, fetching the dependency libraries fails (the Windows path length limit).
If the project folder is deep, move the output to a short location with the `KRKRZ_GDK_BUILD_ROOT`
environment variable or `buildDir` in gdk-config.json.

## gdk-config.json

The sample is [gdk-config.json](gdk-config.json) at the root of this repository.
The `cmake` and `assetPack` formats are shared with the other wrappers, so you can put the settings
files for each platform side by side in one project folder and reuse the same data/.

| Key | Description |
|---|---|
| `name` / `displayName` / `version` | Display name and package version (`x.y.z.w`) |
| `exeName` | Executable name (without extension) |
| `orgName` / `appName` | orgname / appname written to `<exe>.cf` (identifies the save location) |
| `targets` | Target list. The first one is the default when `--target` is omitted |
| `identity` | `name` / `publisher` / `titleId` / `msaAppId` / `storeId` / `scid` (values from Partner Center. Keep the real values only in the project folder) |
| `shellVisuals` | `publisherDisplayName` / `description` / `foregroundText` / `backgroundColor` |
| `logoDir` | Folder holding `Logo44x44.png` / `Logo100x100.png` / `Logo150x150.png` / `Logo480x480.png` / `SplashScreenImage.png`. Placeholders are generated for missing ones |
| `icon` | .ico embedded in the exe (`KRKRZ_WIN_ICON`) |
| `gpuShaderDir` | Folder of shaders for Canvas ShaderProgram (pairs of `<key>.vs` / `<key>.fs` written at run time with `-gpushadercollect`). On Xbox, `stage` combines them with the Canvas built-in shaders into `canvas_shaders.kzgs` for D3D12 (DXIL) and puts it next to the exe |
| `resourceDir` | Replacement for the engine's embedded resources (config.cf / messages.json / fonts) (`KRKRZ_RESOURCE_DIR`) |
| `dataPath` | Save location on Desktop (`datapath` in `<exe>.cf`). Default `$(appdatapath)/<orgName>/<appName>`. Use `/` as the separator |
| `config.options` | Command-line options. Written to `<exe>.cf` on Desktop and to `config.cf` in the app folder on Xbox (`datapath=` written here takes priority over `dataPath`) |
| `cmake.pluginFolders` / `cmake.plugins` | Plugins to build in. **On GDK, all are linked statically** (`staticPlugins` is not needed) |
| `cmake.options` | Additional `-D` passed to configure |
| `assetPack` | Asset placement (below) |
| `gdk.edition` | `XdkEditionTarget` (the environment variable takes priority; default `250404`) |
| `gdk.persistentLocalStorageMB` | PersistentLocalStorage size in MicrosoftGame.config (default 256; 0 omits it) |
| `buildDir` | Output root (default `${PROJECT_DIR}/build/gdk`) |

For the format of `cmake` / `assetPack` / `${...}` path expansion (`${PROJECT_DIR}` / `${BUILD_SYSTEM_DIR}` /
`${KRKRZ_BASE}` and environment variables; relative paths are based on PROJECT_DIR), see
[Shared settings of the platform wrappers](https://wamsoft.github.io/krkrz_dev/en/topics/core/platform_config/)
on the documentation site.

### assetPack (behaviour on GDK)

- Assets are placed relative to the folder of the exe in the layout. `transfer` supports `copy` (default) and `hardlink`
- The engine files and the generated files are placed before assetPack (a file of the same name cannot be overwritten through assetPack)
- At startup the engine looks for `data.xp3` in the exe's folder → an xp3 appended to the exe → `data/startup.tjs`, in that order
- This repository does not create xp3 files. Bring in the ones made on the title side with `flatten`

## SDL3

The `gdk-cmake-support-3.4.18` branch of `https://github.com/wamsoft/SDL.git` (SDL 3.4.18 + CMake support
for GDK / GXDK and fixes for Xbox) is used through FetchContent, pinned to a commit. To use a different
version, specify `-DKRKRZ_GDK_SDL_GIT_TAG=<tag>`; to use a local clone, specify
`CMAKEOPT='-DFETCHCONTENT_SOURCE_DIR_SDL3=/path/to/SDL'`.

## Notes

- `XdkEditionTarget` must match the GDK edition integrated into VS.
  When calling `cmake --build` directly, set the environment variable or go through `--preset`
- Starting the Desktop exe directly from msys2 / Git-Bash can fail to resolve DLLs. Start it from PowerShell / cmd
- MakePkg fails if the logos and SplashScreenImage are not in the layout (`gen` creates placeholders)
- configure warns when krkrz_dev is on a branch other than master (suppress with `-DKRKRZ_GDK_ALLOW_NON_MASTER=ON`)

## Save location on Desktop

The core default (`savedata` next to the exe) cannot be written to in an installed package
(`C:\Program Files\WindowsApps\...`). `gen` writes `datapath="$(appdatapath)/<orgName>/<appName>"` to
`<exe>.cf`, so data is saved in Roaming AppData (`%APPDATA%\<orgName>\<appName>\`).
`$(personalpath)` / `$(savedgamespath)` / `$(exepath)` can also be used.

## WIN build (running the Xbox setup on a PC)

`--target win` is a plain Win32 build that does not use the GDK. It uses the same plugins, assets and
command-line options as Xbox, and renders with the same SDL_GPU (the GPU version of Canvas, D3D12) as Xbox.
Use it to check behaviour on a PC without a devkit, or to investigate with desktop development features
such as the REPL. The GDK does not need to be installed.

```bash
python tools/krkrz_gdk.py --project /path/to/game --target win build stage run
# Add command-line options
RUNOPT="-replfile=C:/tmp/ch" make PROJECT_DIR=/path/to/game TARGET=win run
```

- `stage` adds `gpudriver=direct3d12` to `<exe>.cf` (`gpudriver=` in `config.options` takes priority;
  `vulkan` for Vulkan)
- The shaders in `gpuShaderDir` are converted to DXIL with the general-purpose dxc (Vulkan SDK) and put next to the exe as `canvas_shaders.kzgs`
- `package` zips the layout as is
- For an OpenGL build, use `CMAKEOPT='-DKRKRZ_USE_OPENGL=ON -DKRKRZ_CANVAS_GPU=OFF'`

**Collecting script shaders**: Xbox and the WIN build cannot compile shaders at run time, so the
ShaderProgram sources must be packed in advance. Run the WIN build with `-gpushadercollect=<folder>` and go
through the relevant screens; shaders missing from the pack are written out as `<key>.vs` / `<key>.fs`.
Set that folder as `gpuShaderDir` in gdk-config.json, and `stage` puts them into the pack for both the
WIN build and Xbox.

## Running on Xbox

```bash
python tools/krkrz_gdk.py --project /path/to/game --target scarlett build stage deploy launch
```

`deploy` / `launch` use the GDK's `xbapp` to send the layout to the default devkit (set with `xbconnect`)
and start it. Logs are available with `xbdbgmon /t` and screenshots with `xbcapture`. The procedure and
notes are in [docs/xbox.md](docs/xbox.md) (in Japanese).

Main differences from Desktop:

- The Application uses [src/gdkapp.cpp](src/gdkapp.cpp) instead of core's stdapp.cpp
- The engine resources (config.cf / messages.json / fonts) are not embedded in the exe but placed in
  `resource/` in the layout. When `resourceDir` is not specified, the resource set bundled with core
  (including the bundled fonts) is used
- Command-line options are written to `config.cf` instead of `<exe>.cf`. Per-console files are
  `config_xbox.cf` / `config_scarlett.cf` / `config_xboxone.cf` (`System.platformTag`)
- The screen is fixed to a 1920x1080 logical surface and scaled to fit the actual screen
- Saving (`System.dataPath`) uses XGameSaveFiles (cloud sync) when `identity.scid` is set; otherwise
  `savedata/` under PersistentLocalStorage (for development)
- Rendering uses SDL_GPU (D3D12). `stage` precompiles the Canvas shaders with the GXDK's dxc and bundles them

## Feature status

| Feature | Desktop | win | Xbox |
|---|---|---|---|
| Launch and full screen | ○ | ○ | ○ (1920x1080 logical surface) |
| Gamepad input | ○ | ○ | ○ |
| Mouse / keyboard | ○ | ○ | △ read from GameInput with `gameinput=yes` (off by default). Mouse movement from remote control is not received / USB mice not checked / the cursor is not shown |
| Saving (`System.dataPath`) | ○ `%APPDATA%\<orgName>\<appName>\` | ○ same as left | ○ XGameSaveFiles (when SCID is set) / PersistentLocalStorage |
| Rendering | OpenGL (default) | SDL_GPU (D3D12) | SDL_GPU (D3D12) |
| Canvas / ShaderProgram | ○ OpenGL version | ○ SDL_GPU version | ○ SDL_GPU version |
| Movies (VideoOverlay) | WebM / MPEG-1 | same as left | same as left. None of the overlay modes honour `setPos` / `setSize`; the movie covers the whole screen (a limitation shared by the SDL builds) |
| Elements dialogs | ○ | ○ | ○ |
| Static plugins | ○ | ○ | ○ |
| REPL | ○ console / `-replfile` / `-replweb` | ○ same as left | `-replweb` only (use over the devkit not checked) |
| Screen reader (AccessKit) / LogCore | ○ | ○ | × |

The SDL_GPU version can only use ShaderProgram shaders converted in advance (`gpuShaderDir`). Point sprites
are drawn as quads, since D3D12 has no point size.

For known limitations and unchecked items, see [docs/xbox.md](docs/xbox.md#既知の制限未確認) (in Japanese).

## Documentation

The documents under `docs/` and the linked engine documents are in Japanese.

| Document | Contents |
|---|---|
| [docs/design.md](docs/design.md) | Architecture (three-layer separation / build flow / options passed to core on Xbox / changes in the SDL fork / vcpkg) |
| [docs/xbox.md](docs/xbox.md) | Working with a devkit, saving, shader precompilation, findings on actual hardware, known limitations |
| [vcpkg-ports/README.md](vcpkg-ports/README.md) | vcpkg overlay port (freetype) |
| [plugins/README.md](plugins/README.md) | Location for GDK-only plugins |
| Engine [PlatformPorting.md](https://github.com/wamsoft/krkrz/blob/master/doc/PlatformPorting.md) | The interface for building the engine into a wrapper (shared) |
| Engine [CanvasGPU.md](https://github.com/wamsoft/krkrz/blob/master/doc/CanvasGPU.md) | The SDL_GPU version of Canvas / shader conversion (including DXIL) |

The documentation for Kirikiri Z itself is on the [documentation site](https://wamsoft.github.io/krkrz_dev/en/).

## License

This repository (build scripts, tools and templates) is under the [MIT License](LICENSE).

The following, referenced or fetched at build time, follow their own licenses; the license of this
repository does not extend to them.

- The Kirikiri Z engine and plugins (each submodule under krkrz_dev)
- SDL3 (zlib License) and the dependency libraries fetched through vcpkg / FetchContent
- The Microsoft GDK (Microsoft's license terms)

Include the license notices required in your distribution on the title side, according to the engine,
plugins and libraries you use.
