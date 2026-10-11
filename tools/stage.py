"""assetPack の解決と layout フォルダへの同期 (python 標準ライブラリのみ)

書式は krkrz_android (app-config.json) / krkrz_ios / krkrz_linux と共通:

    "assetPack": {
      "baseFolder": "${PROJECT_DIR}",
      "transfer": "copy" | "hardlink",
      "sources": [
        { "type": "mirror",  "from": "data",    "to": "data",
          "include": ["**/*"], "exclude": ["**/*.psd"] },
        { "type": "flatten", "from": "archive", "include": ["*.xp3"] }
      ]
    }

- mirror  : from 以下の相対パスを保ったまま to へ置く
- flatten : ファイル名だけで to 直下へ置く
- include / exclude は Ant 風グロブ (** = 0 個以上のフォルダ, * / ? はフォルダ区切りを跨がない)
- 同じ配置先は「先に書いたものが勝つ」
- 同期は差分コピー (サイズ + 更新時刻)。マッピングに無いファイルは layout から消す
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand(value: str, variables: dict[str, str]) -> str:
    """${VAR} を variables → 環境変数の順で展開する。未定義は空文字"""
    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name in variables:
            return str(variables[name])
        return os.environ.get(name, "")
    return _VAR_RE.sub(repl, value)


def resolve_path(value: str, variables: dict[str, str], base: Path) -> Path:
    p = Path(expand(value, variables))
    if not p.is_absolute():
        p = base / p
    return p


def _glob_to_regex(pattern: str) -> re.Pattern:
    pattern = pattern.replace("\\", "/")
    if pattern.endswith("/"):
        pattern += "**"
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


class _Matcher:
    def __init__(self, include: list[str] | None, exclude: list[str] | None):
        self.include = [_glob_to_regex(p) for p in (include or ["**"])]
        self.exclude = [_glob_to_regex(p) for p in (exclude or [])]

    def __call__(self, rel: str) -> bool:
        if not any(r.match(rel) for r in self.include):
            return False
        return not any(r.match(rel) for r in self.exclude)


def _as_list(v) -> list[str] | None:
    if v is None:
        return None
    if isinstance(v, str):
        return [v]
    return list(v)


def collect(mapping: dict[str, Path], src_root: Path, to: str = "",
            kind: str = "mirror", include=None, exclude=None) -> int:
    """src_root 以下を mapping (配置先相対パス → 元ファイル) に先勝ちで追加する。
    src_root がファイルなら単体で追加する。追加した件数を返す"""
    if not src_root.exists():
        raise FileNotFoundError(f"assetPack source not found: {src_root}")
    to = to.replace("\\", "/").strip("/")
    match = _Matcher(_as_list(include), _as_list(exclude))
    added = 0

    if src_root.is_file():
        files = [(src_root.name, src_root)]
    else:
        files = []
        for dirpath, dirnames, filenames in os.walk(src_root):
            dirnames.sort()
            for name in sorted(filenames):
                full = Path(dirpath) / name
                files.append((full.relative_to(src_root).as_posix(), full))

    for rel, full in files:
        if not match(rel):
            continue
        name = rel if kind == "mirror" else rel.rsplit("/", 1)[-1]
        dest = f"{to}/{name}" if to else name
        key = dest.lower()  # Windows / Xbox のファイルシステムは大文字小文字を区別しない
        if key in mapping:
            continue
        mapping[key] = (dest, full)
        added += 1
    return added


def collect_asset_pack(mapping: dict, asset_pack: dict, variables: dict[str, str],
                       project_dir: Path) -> None:
    base = resolve_path(asset_pack.get("baseFolder", "${PROJECT_DIR}"), variables, project_dir)
    for src in asset_pack.get("sources", []):
        kind = src.get("type", "mirror")
        if kind not in ("mirror", "flatten"):
            raise ValueError(f"assetPack: unknown type '{kind}'")
        root = resolve_path(src["from"], variables, base)
        n = collect(mapping, root, expand(src.get("to", ""), variables), kind,
                    src.get("include"), src.get("exclude"))
        print(f"  assetPack {kind:7s} {root} -> /{src.get('to', '')} ({n} files)")


def _same(src: Path, dst: Path) -> bool:
    try:
        s, d = src.stat(), dst.stat()
    except FileNotFoundError:
        return False
    return s.st_size == d.st_size and int(s.st_mtime) == int(d.st_mtime)


def sync(mapping: dict, out_dir: Path, transfer: str = "copy") -> None:
    """mapping の内容で out_dir を同期する (差分コピー + 残骸削除)"""
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = set()
    copied = 0
    for dest, src in mapping.values():
        dst = out_dir / dest
        wanted.add(os.path.normcase(str(dst)))
        if _same(src, dst):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        if transfer == "hardlink":
            try:
                os.link(src, dst)
                copied += 1
                continue
            except OSError:
                pass
        shutil.copy2(src, dst)
        copied += 1

    removed = 0
    for dirpath, dirnames, filenames in os.walk(out_dir, topdown=False):
        for name in filenames:
            full = Path(dirpath) / name
            if os.path.normcase(str(full)) not in wanted:
                full.unlink()
                removed += 1
        if Path(dirpath) != out_dir and not os.listdir(dirpath):
            os.rmdir(dirpath)
    print(f"  staged {len(mapping)} files into {out_dir} (updated {copied}, removed {removed})")
