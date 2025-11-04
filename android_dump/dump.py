#!/usr/bin/env python3
"""
Jednoduchý tree dump pro AndroidStudioProjects

Použití
• ulož tento soubor do C:/Users/volny/AndroidStudioProjects
• uprav makra v části KONFIGURACE
• spusť pythonem
"""

from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime

# =========================
# KONFIGURACE  vše zde nastavíš
# =========================

# Složka, kde skript leží a odkud se bude počítat cesta
BASE_DIR = Path(__file__).resolve().parent

# Do které složky se má skript “zabořit”
# příklad "Kniha_20" nebo "PageFlip" nebo "EasyFlip"
TARGET_SUBDIR = "Kniha_20"

# Název výstupního souboru
AUTO_TIMESTAMP = True
OUTPUT_BASENAME = "dump"  # prefix názvu
OUTPUT_DIR = BASE_DIR     # kam uložit .txt

# Filtry
EXCLUDE_DIRS = {
    ".git", ".gradle", ".idea", "build", ".cxx", ".scannerwork", ".externalNativeBuild"
}
EXCLUDE_FILE_NAMES = {
    "local.properties", ".DS_Store", "Thumbs.db"
}
EXCLUDE_EXTS = {
    ".iml", ".class", ".keystore", ".jks", ".apk", ".aab", ".zip", ".jar", ".aar"
}

# Volby zápisu
INCLUDE_FILE_SIZE = True
INCLUDE_MTIME = True
INCLUDE_HIDDEN = False   # pokud False, skryté věci jako .git se přesto zahodí přes EXCLUDE_DIRS
RELATIVE_PATHS = True    # tiskne cesty relativně k TARGET_DIR
MAX_DEPTH = None         # None bez omezení, jinak číslo jako 5

# =========================
# KONEC KONFIGURACE
# =========================


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    s = float(n)
    for u in units:
        if s < 1024.0 or u == units[-1]:
            return f"{s:.1f} {u}"
        s /= 1024.0
    return f"{n} B"


def format_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "n/a"


def should_skip_dir(name: str) -> bool:
    if not INCLUDE_HIDDEN and name.startswith("."):
        return True
    return name in EXCLUDE_DIRS


def should_skip_file(p: Path) -> bool:
    if not INCLUDE_HIDDEN and p.name.startswith("."):
        return True
    if p.name in EXCLUDE_FILE_NAMES:
        return True
    if p.suffix.lower() in EXCLUDE_EXTS:
        return True
    return False


def make_output_name(target_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S") if AUTO_TIMESTAMP else ""
    middle = f"{target_dir.name}"
    parts = [OUTPUT_BASENAME, middle, ts]
    name = "_".join([x for x in parts if x]) + ".txt"
    return OUTPUT_DIR / name


def dump_tree(target_dir: Path) -> Path:
    if not target_dir.exists():
        raise FileNotFoundError(f"Cesta neexistuje: {target_dir}")

    out_path = make_output_name(target_dir)
    lines: list[str] = []
    total_files = 0
    total_dirs = 0

    root_len = len(str(target_dir)) + 1 if RELATIVE_PATHS else len(str(target_dir.anchor))

    for current_root, dirnames, filenames in os.walk(target_dir):
        # hloubka
        rel = Path(current_root).relative_to(target_dir)
        depth = 0 if rel.as_posix() == "." else len(rel.parts)
        if MAX_DEPTH is not None and depth > MAX_DEPTH:
            # neprocházet dále
            dirnames[:] = []
            continue

        # filtrace adresářů in place
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        # třídění
        dirnames.sort(key=str.lower)
        filenames.sort(key=str.lower)

        # tisk hlavičky složky
        folder_path = Path(current_root)
        show_path = folder_path.relative_to(target_dir) if RELATIVE_PATHS else folder_path
        lines.append(f"[DIR] {show_path.as_posix()}")
        total_dirs += 1

        # soubory
        for fname in filenames:
            p = folder_path / fname
            if should_skip_file(p):
                continue
            info = []
            if INCLUDE_FILE_SIZE:
                try:
                    info.append(human_size(p.stat().st_size))
                except Exception:
                    info.append("n/a")
            if INCLUDE_MTIME:
                info.append(format_mtime(p))
            suffix = f"  [{' | '.join(info)}]" if info else ""
            rel_file = p.relative_to(target_dir) if RELATIVE_PATHS else p
            lines.append(f"  {rel_file.as_posix()}{suffix}")
            total_files += 1

        # prázdný řádek mezi složkami
        lines.append("")

    # shrnutí
    lines.append("===== SHRNUTI =====")
    lines.append(f"Slozka: {target_dir}")
    lines.append(f"Adresare: {total_dirs}")
    lines.append(f"Soubory:  {total_files}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    target_dir = (BASE_DIR / TARGET_SUBDIR).resolve()
    out_path = dump_tree(target_dir)
    print(f"Hotovo  ulozeno do: {out_path}")


if __name__ == "__main__":
    main()
