#!/usr/bin/env python3
"""
Tree dump s obsahem souborů
Ulož do C:/Users/volny/AndroidStudioProjects
Uprav makra níže a spusť
"""

from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime
import string
import binascii

# =========================
# KONFIGURACE
# =========================

# Kořenová složka pro skript
BASE_DIR = Path(__file__).resolve().parent

# Do jaké podsložky se ponořit
TARGET_SUBDIR = "Kniha_20"

# Výstupní soubor
AUTO_TIMESTAMP = False   #casove razitko
OUTPUT_BASENAME = "dump"
OUTPUT_DIR = BASE_DIR

# Filtry
EXCLUDE_DIRS = {
    ".git", ".gradle", ".idea", "build", ".cxx", ".externalNativeBuild",
    ".scannerwork", ".fleet", ".metadata"
}
EXCLUDE_FILE_NAMES = {
    "local.properties", ".DS_Store", "Thumbs.db"
}
EXCLUDE_EXTS = {
    ".iml", ".class", ".keystore", ".jks", ".apk", ".aab",
    ".zip", ".7z", ".rar", ".jar", ".aar", ".so", ".o", ".obj",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".mp4", ".mov", ".avi", ".mp3", ".wav", ".ogg"
}

# Obsah souborů
INCLUDE_FILE_CONTENTS = True              # zapnout výpis obsahu
CONTENT_MAX_BYTES = 200_000               # horní limit na soubor
CONTENT_ENCODING = "utf-8"               # pokus o dekódování textu
TEXT_DETECT_BYTES = 4096                  # kolik bajtů použít pro detekci textu
TEXT_MIN_PRINTABLE_RATIO = 0.85           # práh textovosti
INCLUDE_BINARY_PREVIEW = True             # pro binární soubory ukázka
BINARY_PREVIEW_BYTES = 1024               # kolik bajtů binárně ukázat
SHOW_LINE_NUMBERS = False                 # číslování řádků obsahu

# Výpis
INCLUDE_FILE_SIZE = True
INCLUDE_MTIME = True
INCLUDE_HIDDEN = False
RELATIVE_PATHS = True
MAX_DEPTH = None                          # None bez limitu

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


def is_probably_text(first_bytes: bytes) -> bool:
    if b"\x00" in first_bytes:
        return False
    if not first_bytes:
        return True
    # poměr tisknutelných znaků
    printable = set(bytes(string.printable, "ascii"))
    kept = sum(b in printable for b in first_bytes)
    ratio = kept / max(1, len(first_bytes))
    return ratio >= TEXT_MIN_PRINTABLE_RATIO


def read_text_preview(path: Path, limit: int) -> str:
    data = path.read_bytes()[:limit]
    return data.decode(CONTENT_ENCODING, errors="replace")


def read_binary_preview(path: Path, limit: int) -> str:
    data = path.read_bytes()[:limit]
    # hex s mezerami
    hexstr = binascii.hexlify(data).decode("ascii")
    grouped = " ".join(hexstr[i:i+2] for i in range(0, len(hexstr), 2))
    return grouped


def write_file_content_lines(lines: list[str], path: Path, max_bytes: int) -> None:
    try:
        size = path.stat().st_size
    except Exception:
        size = None

    try:
        head = path.read_bytes()[:TEXT_DETECT_BYTES]
    except Exception as e:
        lines.append(f"    [OBSAH] nelze číst  chyba {e}")
        return

    if is_probably_text(head):
        try:
            text = read_text_preview(path, min(max_bytes, size or max_bytes))
        except Exception as e:
            lines.append(f"    [OBSAH] nelze dekódovat  chyba {e}")
            return

        lines.append("    === ZAČÁTEK OBSAHU ===")
        if SHOW_LINE_NUMBERS:
            for i, line in enumerate(text.splitlines(), 1):
                lines.append(f"    {i:6d}  {line}")
        else:
            for line in text.splitlines():
                lines.append(f"    {line}")
        if size is not None and size > max_bytes:
            lines.append(f"    [ZKRÁCENO] vypsáno {max_bytes} bajtů z {size}")
        lines.append("    === KONEC OBSAHU ===")
    else:
        if not INCLUDE_BINARY_PREVIEW:
            lines.append("    [BINÁRNÍ SOUBOR] náhled vypnut")
            return
        try:
            hexpreview = read_binary_preview(path, BINARY_PREVIEW_BYTES)
        except Exception as e:
            lines.append(f"    [BINÁRNÍ SOUBOR] náhled nelze číst  chyba {e}")
            return
        lines.append("    === BINÁRNÍ NÁHLED HEX ===")
        lines.append(f"    {hexpreview}")
        if size is not None and size > BINARY_PREVIEW_BYTES:
            lines.append(f"    [ZKRÁCENO] vypsáno {BINARY_PREVIEW_BYTES} bajtů z {size}")
        lines.append("    === KONEC NÁHLEDU ===")


def dump_tree(target_dir: Path) -> Path:
    if not target_dir.exists():
        raise FileNotFoundError(f"Cesta neexistuje  {target_dir}")

    out_path = make_output_name(target_dir)
    lines: list[str] = []
    total_files = 0
    total_dirs = 0

    for current_root, dirnames, filenames in os.walk(target_dir):
        # hloubka
        rel = Path(current_root).relative_to(target_dir)
        depth = 0 if rel.as_posix() == "." else len(rel.parts)
        if MAX_DEPTH is not None and depth > MAX_DEPTH:
            dirnames[:] = []
            continue

        # filtrace a třídění
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        dirnames.sort(key=str.lower)
        filenames.sort(key=str.lower)

        folder_path = Path(current_root)
        show_path = folder_path.relative_to(target_dir) if RELATIVE_PATHS else folder_path
        lines.append(f"[DIR] {show_path.as_posix()}")
        total_dirs += 1

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

            if INCLUDE_FILE_CONTENTS:
                write_file_content_lines(lines, p, CONTENT_MAX_BYTES)

        lines.append("")

    lines.append("===== SHRNUTI =====")
    lines.append(f"Složka  {target_dir}")
    lines.append(f"Adresáře  {total_dirs}")
    lines.append(f"Soubory   {total_files}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    target_dir = (BASE_DIR / TARGET_SUBDIR).resolve()
    out_path = dump_tree(target_dir)
    print(f"Hotovo  uloženo do  {out_path}")


if __name__ == "__main__":
    main()
