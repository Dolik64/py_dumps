#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from datetime import datetime

# === Nastavení (změň podle potřeby) ==========================================
ROOT_DIR = Path(r"C:\Users\volny\Documents\the last human\the-last-human")   # <- sem nastav kořenovou složku
OUTPUT_FILE = None                             # None = dump.txt do ROOT_DIR
EXCLUDE_NAMES = {".git", "node_modules", "__pycache__"}  # volitelné výjimky
# ============================================================================

def is_excluded(p: Path) -> bool:
    """Vynechá položky, které mají některou část cesty v EXCLUDE_NAMES."""
    return any(part in EXCLUDE_NAMES for part in p.parts)

def iter_all_files(root: Path):
    """Vygeneruje relativní cesty všech souborů pod root (rekurzivně)."""
    for p in root.rglob("*"):
        if p.is_file() and not is_excluded(p.relative_to(root)):
            yield p.relative_to(root)

def write_tree(dir_path: Path, out, prefix: str = "", root: Path = None):
    """
    Zapíše stromovou hierarchii do souboru 'out'.
    prefix – aktuální odsazení (│  , ├──, └──)
    """
    if root is None:
        root = dir_path

    # Seřadit: nejdřív složky, pak soubory; abecedně (case-insensitive)
    entries = [e for e in dir_path.iterdir() if not is_excluded(e.relative_to(root))]
    entries.sort(key=lambda e: (e.is_file(), e.name.lower()))

    total = len(entries)
    for i, entry in enumerate(entries):
        connector = "└── " if i == total - 1 else "├── "
        line = f"{prefix}{connector}{entry.name}\n"
        out.write(line)

        if entry.is_dir():
            # Pro pokračování stromu: poslední větev má jiné odsazení
            extension = "    " if i == total - 1 else "│   "
            write_tree(entry, out, prefix + extension, root)

def main():
    root = ROOT_DIR
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Chyba: '{root}' neexistuje nebo to není složka.")

    output = OUTPUT_FILE if OUTPUT_FILE else root / "dump.txt"

    # Zápis do souboru
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
            f.write(str(rel_file).replace("\\", "/") + "\n")
            count += 1
        f.write(f"\nCelkem souborů: {count}\n\n")

        # Stromová hierarchie
        f.write("## Stromová hierarchie\n")
        f.write(f"{root.name}\n")
        write_tree(root, f)

    print(f"Hotovo. Výstup zapsán do: {output.resolve()}")

if __name__ == "__main__":
    main()
