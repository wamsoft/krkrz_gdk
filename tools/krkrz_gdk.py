#!/usr/bin/env python3
"""krkrz_gdk: 吉里吉里Z を Microsoft GDK (PC / Xbox) 向けにビルド・パッケージ化する

使い方:
    python tools/krkrz_gdk.py [--project DIR] [--target desktop] [--config Release] <command>...

コマンド (複数並べると順に実行):
    gen        gdk-config.json から myapp.cmake / app.cmake / MicrosoftGame.config / ロゴ / .cf を生成
    configure  cmake configure (VS2022 generator + Gaming.* platform)
    build      エンジン exe をビルド
    stage      layout フォルダ (エンジン + 生成物 + assetPack) を作る
    package    MakePkg で msixvc / xvc を作る
    run        layout の exe を直接起動 (Desktop のみ)
    register   wdapp register で layout を登録 (Desktop)
    launch     wdapp / xbapp で起動
    deploy     xbapp deploy で layout を devkit へ送る (Xbox)
    all        gen configure build stage package
    vars       解決済みの設定を表示

PROJECT_DIR (= --project / 環境変数 PROJECT_DIR) 省略時は krkrz_gdk 自身のサンプル設定を使う。
python 標準ライブラリのみで動く。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage  # noqa: E402

BUILD_SYSTEM_DIR = Path(__file__).resolve().parent.parent
CONFIG_NAME = "gdk-config.json"
DEFAULT_EDITION = "250404"

TARGETS = {
    #  name       preset           platform                     device family  xbox
    "desktop":  ("gdk-desktop",   "Gaming.Desktop.x64",        "PC",          False),
    "scarlett": ("gxdk-scarlett", "Gaming.Xbox.Scarlett.x64",  "Scarlett",    True),
    "xboxone":  ("gxdk-xboxone",  "Gaming.Xbox.XboxOne.x64",   "XboxOne",     True),
}

LOGOS = [
    ("Logo44x44.png", 44, 44),
    ("Logo100x100.png", 100, 100),
    ("Logo150x150.png", 150, 150),
    ("Logo480x480.png", 480, 480),
    ("SplashScreenImage.png", 1920, 1080),
]

# エンジン exe のフォルダから layout に持ち込まないもの
ENGINE_EXCLUDE = ["*.pdb", "*.lib", "*.exp", "*.ilk", "*.iobj", "*.ipdb", "MicrosoftGame.config"]


class Error(Exception):
    pass


# ----------------------------------------------------------------------------
# 設定
# ----------------------------------------------------------------------------

class Context:
    def __init__(self, args):
        self.project_dir = Path(args.project or os.environ.get("PROJECT_DIR") or BUILD_SYSTEM_DIR).resolve()
        self.config_path = self.project_dir / CONFIG_NAME
        if not self.config_path.exists():
            raise Error(f"{CONFIG_NAME} not found: {self.config_path}")
        with open(self.config_path, encoding="utf-8") as f:
            self.cfg = json.load(f)

        self.krkrz_base = Path(os.environ.get("KRKRZ_BASE") or BUILD_SYSTEM_DIR.parent).resolve()
        self.vars = {
            "BUILD_SYSTEM_DIR": BUILD_SYSTEM_DIR.as_posix(),
            "PROJECT_DIR": self.project_dir.as_posix(),
            "KRKRZ_BASE": self.krkrz_base.as_posix(),
        }

        self.target = args.target or (self.cfg.get("targets") or ["desktop"])[0]
        if self.target not in TARGETS:
            raise Error(f"unknown target '{self.target}' (desktop / scarlett / xboxone)")
        self.preset, self.platform, self.device_family, self.is_xbox = TARGETS[self.target]
        self.build_config = args.config

        root = os.environ.get("KRKRZ_GDK_BUILD_ROOT") or self.cfg.get("buildDir")
        self.build_root = self.path(root) if root else self.project_dir / "build" / "gdk"
        self.generated_dir = self.build_root / "generated"
        self.cmake_dir = self.build_root / self.target
        self.layout_dir = self.cmake_dir / "layout" / self.build_config
        self.package_dir = self.cmake_dir / "package" / self.build_config

        self.edition = os.environ.get("XdkEditionTarget") or self.cfg.get("gdk", {}).get("edition") or DEFAULT_EDITION
        self.exe_name = self.cfg.get("exeName", "krkrz")

    def path(self, value: str, base: Path | None = None) -> Path:
        return stage.resolve_path(value, self.vars, base or self.project_dir)

    def env(self) -> dict:
        e = dict(os.environ)
        e["XdkEditionTarget"] = self.edition
        e.setdefault("KRKRZ_BASE", str(self.krkrz_base))
        return e


def find_cmake() -> str:
    exe = shutil.which("cmake")
    if exe:
        return exe
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if vswhere.exists():
        out = subprocess.run([str(vswhere), "-latest", "-version", "[17.0,18.0)", "-property", "installationPath"],
                             capture_output=True, text=True).stdout.strip()
        cand = Path(out) / "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
        if out and cand.exists():
            return str(cand)
    raise Error("cmake not found (install CMake or Visual Studio 2022 with the CMake component)")


def gdk_bin(name: str) -> str:
    gamedk = os.environ.get("GameDK")
    if gamedk:
        cand = Path(gamedk) / "bin" / name
        if cand.exists():
            return str(cand)
    exe = shutil.which(name)
    if exe:
        return exe
    raise Error(f"{name} not found (GameDK env / PATH)")


def run(cmd: list, ctx: Context | None = None, check: bool = True) -> int:
    print("+ " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], env=ctx.env() if ctx else None)
    if check and r.returncode != 0:
        raise Error(f"command failed ({r.returncode}): {cmd[0]}")
    return r.returncode


def write_if_changed(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8", newline="\n")


def cmake_quote(value) -> str:
    return '"' + str(value).replace("\\", "/").replace('"', '\\"') + '"'


# ----------------------------------------------------------------------------
# gen
# ----------------------------------------------------------------------------

def cmd_gen(ctx: Context) -> None:
    cfg = ctx.cfg
    gen = ctx.generated_dir
    print(f"[gen] {ctx.config_path} -> {gen}")

    # myapp.cmake (プラグイン)
    cm = cfg.get("cmake", {})
    folders = [ctx.path(p).as_posix() for p in cm.get("pluginFolders", [])]
    plugins = list(cm.get("plugins", []))
    lines = ["# generated by krkrz_gdk (tools/krkrz_gdk.py gen). Do not edit."]
    if folders:
        lines.append("LIST(APPEND TVP_PLUGIN_FOLDERS\n" + "".join(f"  {cmake_quote(p)}\n" for p in folders) + ")")
    if plugins:
        # GDK では全プラグインを静的リンクする
        lines.append("LIST(APPEND TVP_PLUGINS\n" + "".join(f"  {p}\n" for p in plugins) + ")")
        lines.append("LIST(APPEND TVP_PLUGINS_STATIC ${TVP_PLUGINS})")
    write_if_changed(gen / "myapp.cmake", "\n".join(lines) + "\n")

    # app.cmake (exe 名 / リソース / アイコン)
    lines = ["# generated by krkrz_gdk (tools/krkrz_gdk.py gen). Do not edit.",
             f"set(KRKRZ_EXE_NAME {cmake_quote(ctx.exe_name)} CACHE STRING \"\" FORCE)"]
    if cfg.get("resourceDir"):
        lines.append(f"set(KRKRZ_RESOURCE_DIR {cmake_quote(ctx.path(cfg['resourceDir']).as_posix())} CACHE PATH \"\" FORCE)")
    if cfg.get("icon"):
        lines.append(f"set(KRKRZ_WIN_ICON {cmake_quote(ctx.path(cfg['icon']).as_posix())} CACHE FILEPATH \"\" FORCE)")
    write_if_changed(gen / "app.cmake", "\n".join(lines) + "\n")

    # <exeName>.cf (exe 隣で読まれる起動オプション)
    cf = []
    if cfg.get("orgName"):
        cf.append(f'orgname="{cfg["orgName"]}"')
    if cfg.get("appName"):
        cf.append(f'appname="{cfg["appName"]}"')
    cf += cfg.get("config", {}).get("options", [])
    write_if_changed(gen / f"{ctx.exe_name}.cf", "\n".join(cf) + "\n")

    # MicrosoftGame.config (ターゲット別)
    tmpl = (BUILD_SYSTEM_DIR / "templates/MicrosoftGame.config.in").read_text(encoding="utf-8")
    ident = cfg.get("identity", {})
    shell = cfg.get("shellVisuals", {})
    display = cfg.get("displayName", cfg.get("name", "krkrz"))
    for name, (_, _, family, xbox) in TARGETS.items():
        desktop_reg = "" if xbox else (
            "\n\t<DesktopRegistration>\n\t\t<DependencyList>\n"
            "\t\t\t<KnownDependency Name=\"VC14\"/>\n\t\t</DependencyList>\n\t</DesktopRegistration>\n")
        store_id = f"\t<StoreId>{xml_escape(ident['storeId'])}</StoreId>\n" if ident.get("storeId") else ""
        values = {
            "IDENTITY_NAME": ident.get("name", "Sample.Krkrz"),
            "VERSION": cfg.get("version", "1.0.0.0"),
            "PUBLISHER": ident.get("publisher", "CN=Publisher"),
            "EXE_FILE": f"{ctx.exe_name}.exe",
            "TARGET_DEVICE_FAMILY": family,
            "MSA_APP_ID": ident.get("msaAppId", "PleaseChangeMe"),
            "TITLE_ID": ident.get("titleId", "FFFFFFFF"),
            "DISPLAY_NAME": display,
            "PUBLISHER_DISPLAY_NAME": shell.get("publisherDisplayName", display),
            "DESCRIPTION": shell.get("description", display),
            "FOREGROUND_TEXT": shell.get("foregroundText", "light"),
            "BACKGROUND_COLOR": shell.get("backgroundColor", "#1F1F1F"),
        }
        text = tmpl
        for k, v in values.items():
            text = text.replace(f"@{k}@", xml_escape(str(v), {'"': "&quot;"}))
        text = text.replace("@DESKTOP_REGISTRATION@", desktop_reg).replace("@STORE_ID@", store_id)
        write_if_changed(gen / f"MicrosoftGame.{name}.config", text)

    # ロゴ (案件の logoDir に同名ファイルがあればそれ、無ければ placeholder)
    logo_dir = ctx.path(cfg["logoDir"]) if cfg.get("logoDir") else None
    out = gen / "logos"
    out.mkdir(parents=True, exist_ok=True)
    for fname, w, h in LOGOS:
        dst = out / fname
        src = logo_dir / fname if logo_dir else None
        if src and src.exists():
            shutil.copy2(src, dst)
        else:
            if logo_dir:
                print(f"  warning: {fname} not found in {logo_dir}, using placeholder")
            if not dst.exists():
                write_placeholder_png(dst, w, h)


def write_placeholder_png(path: Path, width: int, height: int) -> None:
    """単色背景 + 中央の四角だけの PNG (Pillow 不要)"""
    bg, accent = (0x1F, 0x4D, 0x8C), (0xFF, 0xC4, 0x3D)
    size = max(2, min(width, height) // 3)
    x0, y0 = (width - size) // 2, (height - size) // 2
    bg_row = bytes(bg) * width
    ac_row = bytes(bg) * x0 + bytes(accent) * size + bytes(bg) * (width - x0 - size)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += ac_row if y0 <= y < y0 + size else bg_row

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                     + chunk(b"IEND", b""))


# ----------------------------------------------------------------------------
# configure / build
# ----------------------------------------------------------------------------

def cmd_configure(ctx: Context) -> None:
    cm = ctx.cfg.get("cmake", {})
    cmd = [find_cmake(), "-S", BUILD_SYSTEM_DIR, "--preset", ctx.preset, "-B", ctx.cmake_dir,
           f"-DKRKRZ_BASE={ctx.krkrz_base.as_posix()}",
           f"-DMYAPP_CMAKE_FILE={(ctx.generated_dir / 'myapp.cmake').as_posix()}",
           f"-DAPP_CMAKE_FILE={(ctx.generated_dir / 'app.cmake').as_posix()}"]
    cmd += [stage.expand(o, ctx.vars) for o in cm.get("options", [])]
    cmd += shlex_split(os.environ.get("CMAKEOPT", ""))
    print(f"[configure] {ctx.target} -> {ctx.cmake_dir}")
    # --preset は source dir の CMakePresets.json を読むため cwd を合わせる
    old = os.getcwd()
    os.chdir(BUILD_SYSTEM_DIR)
    try:
        run(cmd, ctx)
    finally:
        os.chdir(old)


def shlex_split(s: str) -> list[str]:
    import shlex
    return shlex.split(s, posix=False) if s else []


def cmd_build(ctx: Context) -> None:
    if not (ctx.cmake_dir / "CMakeCache.txt").exists():
        cmd_configure(ctx)
    print(f"[build] {ctx.target} {ctx.build_config}")
    run([find_cmake(), "--build", ctx.cmake_dir, "--config", ctx.build_config,
         "--target", "krkrz64", "--parallel"], ctx)


def engine_dir(ctx: Context) -> Path:
    d = ctx.cmake_dir / "krkrz" / ctx.build_config
    if not (d / f"{ctx.exe_name}.exe").exists():
        raise Error(f"engine exe not found: {d / (ctx.exe_name + '.exe')} (run build first)")
    return d


# ----------------------------------------------------------------------------
# stage / package
# ----------------------------------------------------------------------------

def cmd_stage(ctx: Context) -> None:
    print(f"[stage] -> {ctx.layout_dir}")
    gen = ctx.generated_dir
    if not (gen / f"MicrosoftGame.{ctx.target}.config").exists():
        cmd_gen(ctx)
    mapping: dict = {}
    # 先勝ち: エンジン → 生成物 → 案件 assetPack
    stage.collect(mapping, engine_dir(ctx), exclude=ENGINE_EXCLUDE)
    stage.collect(mapping, gen / f"MicrosoftGame.{ctx.target}.config", "", "flatten")
    mapping["microsoftgame.config"] = ("MicrosoftGame.config", mapping.pop(f"microsoftgame.{ctx.target}.config")[1])
    stage.collect(mapping, gen / "logos")
    stage.collect(mapping, gen / f"{ctx.exe_name}.cf", "", "flatten")
    if ctx.is_xbox:
        # Xbox はエンジンリソースを exe に埋め込まず resource/ に置く (KRKRZ_RESOURCE_EXTERNAL)。
        # システムフォントが無いので同梱フォントも全て含める
        if ctx.cfg.get("resourceDir"):
            res = ctx.path(ctx.cfg["resourceDir"])
        else:
            res = ctx.krkrz_base / "krkrz_dev/src/core/resource"
        stage.collect(mapping, res, "resource")
    ap = ctx.cfg.get("assetPack")
    if ap:
        stage.collect_asset_pack(mapping, ap, ctx.vars, ctx.project_dir)
    stage.sync(mapping, ctx.layout_dir, (ap or {}).get("transfer", "copy"))


def write_package_layout(ctx: Context) -> Path:
    """layout の実ファイルから MakePkg の mapping (PackageLayout.xml) を作る。
    FileGroup はフォルダ単位 (Include はサブフォルダを辿らない)"""
    dirs: dict[str, list[str]] = {}
    for dirpath, _, filenames in os.walk(ctx.layout_dir):
        rel = Path(dirpath).relative_to(ctx.layout_dir).as_posix()
        if filenames:
            dirs[rel] = sorted(filenames)
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             "<!-- generated by krkrz_gdk (tools/krkrz_gdk.py package). Do not edit. -->",
             "<Package>",
             '  <Chunk Id="1000" Marker="Launch">']
    for rel in sorted(dirs):
        d = "." if rel == "." else rel.replace("/", "\\")
        lines.append(f'    <FileGroup DestinationPath="{xml_escape(d)}" SourcePath="{xml_escape(d)}" Include="*" />')
    lines += ["  </Chunk>", "</Package>", ""]
    out = ctx.cmake_dir / f"PackageLayout.{ctx.build_config}.xml"
    write_if_changed(out, "\n".join(lines))
    return out


def cmd_package(ctx: Context) -> None:
    if not ctx.layout_dir.exists():
        raise Error(f"layout not found: {ctx.layout_dir} (run stage first)")
    layout_xml = write_package_layout(ctx)
    ctx.package_dir.mkdir(parents=True, exist_ok=True)
    print(f"[package] -> {ctx.package_dir}")
    cmd = [gdk_bin("MakePkg.exe"), "pack", "/f", layout_xml, "/d", ctx.layout_dir, "/pd", ctx.package_dir]
    if not ctx.is_xbox:
        cmd.append("/pc")
    run(cmd, ctx)


# ----------------------------------------------------------------------------
# run / register / deploy / launch
# ----------------------------------------------------------------------------

def aumid(ctx: Context) -> str:
    """登録済みパッケージの AUMID (<PackageFamilyName>!Game) を wdapp/xbapp list から探す"""
    tool = gdk_bin("xbapp.exe" if ctx.is_xbox else "wdapp.exe")
    # xbapp / wdapp はコンソールのコードページで出力する (日本語環境では cp932)
    out = subprocess.run([tool, "list"], capture_output=True, text=True, encoding="mbcs",
                         errors="replace", env=ctx.env()).stdout or ""
    name = ctx.cfg.get("identity", {}).get("name", "Sample.Krkrz")
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(name + "_") and "!" in line:
            return line.split()[0]
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(name + "_"):
            pfn = line.split()[0]
            parts = pfn.split("_")
            # PackageFullName → PackageFamilyName (Name_PublisherId)
            return f"{parts[0]}_{parts[-1]}!Game" if len(parts) > 2 else f"{pfn}!Game"
    raise Error(f"registered package '{name}' not found in `{Path(tool).name} list`")


def cmd_run(ctx: Context) -> None:
    if ctx.is_xbox:
        raise Error("run is Desktop only (use deploy + launch for Xbox)")
    exe = ctx.layout_dir / f"{ctx.exe_name}.exe"
    if not exe.exists():
        raise Error(f"{exe} not found (run stage first)")
    print(f"[run] {exe}")
    subprocess.Popen([str(exe)], cwd=ctx.layout_dir, env=ctx.env())


def cmd_register(ctx: Context) -> None:
    if ctx.is_xbox:
        raise Error("register is Desktop only (use deploy for Xbox)")
    run([gdk_bin("wdapp.exe"), "register", ctx.layout_dir], ctx)


def cmd_deploy(ctx: Context) -> None:
    if not ctx.is_xbox:
        raise Error("deploy is Xbox only (use register for Desktop)")
    run([gdk_bin("xbapp.exe"), "deploy", ctx.layout_dir], ctx)


def cmd_launch(ctx: Context) -> None:
    tool = gdk_bin("xbapp.exe" if ctx.is_xbox else "wdapp.exe")
    run([tool, "launch", aumid(ctx)], ctx)


def cmd_vars(ctx: Context) -> None:
    for k, v in [("BUILD_SYSTEM_DIR", BUILD_SYSTEM_DIR), ("PROJECT_DIR", ctx.project_dir),
                 ("KRKRZ_BASE", ctx.krkrz_base), ("target", ctx.target), ("preset", ctx.preset),
                 ("config", ctx.build_config), ("XdkEditionTarget", ctx.edition),
                 ("build_root", ctx.build_root), ("cmake_dir", ctx.cmake_dir),
                 ("layout_dir", ctx.layout_dir), ("package_dir", ctx.package_dir),
                 ("exeName", ctx.exe_name)]:
        print(f"{k:18s} {v}")


COMMANDS = {
    "gen": cmd_gen, "configure": cmd_configure, "build": cmd_build, "stage": cmd_stage,
    "package": cmd_package, "run": cmd_run, "register": cmd_register, "deploy": cmd_deploy,
    "launch": cmd_launch, "vars": cmd_vars,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="krkrz GDK build tool")
    ap.add_argument("--project", help="project folder containing gdk-config.json (default: $PROJECT_DIR or krkrz_gdk)")
    ap.add_argument("--target", choices=list(TARGETS), help="desktop / scarlett / xboxone (default: first of targets)")
    ap.add_argument("--config", default="Release", choices=["Debug", "Release"])
    ap.add_argument("commands", nargs="+", choices=list(COMMANDS) + ["all"])
    args = ap.parse_args()

    try:
        ctx = Context(args)
        cmds = []
        for c in args.commands:
            cmds += ["gen", "configure", "build", "stage", "package"] if c == "all" else [c]
        for c in cmds:
            COMMANDS[c](ctx)
    except Error as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
