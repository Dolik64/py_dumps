#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from datetime import datetime
import fnmatch

# === Nastavení (změň podle potřeby) ==========================================
# ROOT_DIR = Path(r"C:\Users\volny\Documents\the last human\the-last-human")   # <- kořenová složka
ROOT_DIR = Path(r"C:\Users\volny\Documents\unity tutorial\Prvni_hra")   # <- kořenová složka
OUTPUT_FILE = None                             # None = dump.txt do ROOT_DIR

# 1) Ignorované složky (dle JEDNOTLIVÝCH částí cesty)
EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__",
    # Unity typicky:
    "library", "logs", "temp", "obj", "build"
}

# 2) Ignorované přesné názvy souborů (bez cest)
EXCLUDE_FILES = {
    "dump.txt",  # ať se nezacyklíš
    # přidej dle potřeby:
    # "thumbs.db", "desktop.ini",
}

# 3) Ignorované přípony (bez tečky)
EXCLUDE_EXTS = {
    # Unity/kompiláty/logy atd.:
    "dll", "pdb", "cache", "log"
}

# 4) Glob vzory (matchují relativní cestu vůči rootu)
#    Pár rozumných defaultů pro Unity projekty:
EXCLUDE_GLOBS = {
    "**/Library/**",
    "**/Logs/**",
    "**/obj/**",
    "**/Temp/**",
    "**/Build/**",
    "**/*.dll",
    "**/*.pdb",
    "**/*.cache",
    "**/*.log",
}
# ============================================================================

def norm_lower(s: str) -> str:
    return s.casefold()

def is_excluded(rel_path: Path) -> bool:
    """
    Vrátí True, pokud by se měla položka vynechat.
    Kontroluje:
    - některou část cesty (složku) v EXCLUDE_DIRS
    - přesný název souboru v EXCLUDE_FILES
    - příponu souboru v EXCLUDE_EXTS
    - glob vzory v EXCLUDE_GLOBS (vůči relativní cestě)
    """
    # 1) části cesty (složky) – case-insensitive
    for part in rel_path.parts:
        if norm_lower(part) in EXCLUDE_DIRS:
            return True

    # 2) přesný název souboru
    name_lower = norm_lower(rel_path.name)
    if name_lower in EXCLUDE_FILES:
        return True

    # 3) přípona (bez tečky)
    if rel_path.suffix:
        ext = norm_lower(rel_path.suffix.lstrip("."))
        if ext in EXCLUDE_EXTS:
            return True

    # 4) glob vzory
    #   Path.match je case-sensitive na *některých* platformách; proto srovnáme
    #   s POSIX-like stringem a použijeme fnmatch (case-insensitive).
    rel_as_posix = norm_lower(rel_path.as_posix())
    for pattern in EXCLUDE_GLOBS:
        if fnmatch.fnmatch(rel_as_posix, norm_lower(pattern)):
            return True

    return False

def iter_all_files(root: Path):
    """Vygeneruje relativní cesty všech souborů pod root (rekurzivně) s ignorováním."""
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root)
            if not is_excluded(rel):
                yield rel

def write_tree(dir_path: Path, out, prefix: str = "", root: Path = None):
    """
    Zapíše stromovou hierarchii do souboru 'out'.
    prefix – aktuální odsazení (│  , ├──, └──)
    """
    if root is None:
        root = dir_path

    # Seřadit: nejdřív složky, pak soubory; abecedně (case-insensitive)
    entries = []
    for e in dir_path.iterdir():
        rel = e.relative_to(root)
        if not is_excluded(rel):
            entries.append(e)

    entries.sort(key=lambda e: (e.is_file(), e.name.lower()))

    total = len(entries)
    for i, entry in enumerate(entries):
        connector = "└── " if i == total - 1 else "├── "
        line = f"{prefix}{connector}{entry.name}\n"
        out.write(line)

        if entry.is_dir():
            extension = "    " if i == total - 1 else "│   "
            write_tree(entry, out, prefix + extension, root)

def main():
    root = ROOT_DIR
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Chyba: '{root}' neexistuje nebo to není složka.")

    output = OUTPUT_FILE if OUTPUT_FILE else root / "dump.txt"

    with output.open("w", encoding="utf-8", errors="replace") as f:
        # Hlavička
        f.write("# DUMP souborů a hierarchie\n")
        f.write(f"Kořenová složka: {root.resolve()}\n")
        f.write(f"Vygenerováno: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write("\n")

        # Plochý seznam souborů
        f.write("## Seznam souborů (relativní cesty)\n")
        count = 0
        for rel_file in iter_all_files(root):
            f.write(rel_file.as_posix() + "\n")
            count += 1
        f.write(f"\nCelkem souborů: {count}\n\n")

        # Stromová hierarchie
        f.write("## Stromová hierarchie\n")
        f.write(f"{root.name}\n")
        write_tree(root, f)

    print(f"Hotovo. Výstup zapsán do: {output.resolve()}")

if __name__ == "__main__":
    main()
