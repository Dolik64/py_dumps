from __future__ import annotations
from pathlib import Path
from datetime import datetime
import os
import sys

# =========================
# CONFIG (edit these only)
# =========================

# Root folder to dump
ROOT_DIR = Path("/Users/jirka/Downloads/halgy app/sta-builder")

# Output file name
OUTPUT_FILENAME = "folder_dump.txt"

# 1. EXCLUDED DIRECTORIES
EXCLUDED_DIR_NAMES = {
    "target", "node_modules", "build", "dist", "venv", "__pycache__", 
    "fig", "photos", "plots", "data", "sketch", "tikz"
}

# 2. EXCLUDED EXTENSIONS
EXCLUDED_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".pdf",
    ".class", ".jar", ".war", # Java build soubory
    ".aux", ".bbl", ".blg", ".log", ".out", ".toc", ".lof", ".lot", 
    ".fdb_latexmk", ".fls", ".synctex.gz", ".glo", ".ist",
    ".bst", ".cls", ".sty", ".pyc", ".sh", ".sk", ".dvi", ".ps",
    ".exe", ".dll", ".zip", ".7z"
}

# 3. EXCLUDED SPECIFIC FILES
EXCLUDED_FILES = {
    "folder_dump.txt",
    "basic_dump.py",
    "Makefile"
}

# Behavior
INCLUDE_TREE = True
INCLUDE_FILE_CONTENTS = True
MAX_FILE_SIZE_MB = 0.5 # 500 KB je dostatečné pro zdrojáky, vyřadí velké bloby
SKIP_BINARY_FILES = True
INCLUDE_DOTFILES = False # Automaticky vyřadí .git, .idea, .DS_Store atd.
FILE_END_MARKER = "\n" + ("-" * 80) + "\n\n"

# =========================
# IMPLEMENTATION
# =========================

def should_exclude_dir(dirname: str) -> bool:
    if not INCLUDE_DOTFILES and dirname.startswith("."):
        return True
    return dirname in EXCLUDED_DIR_NAMES

def should_exclude_file(filepath: Path) -> bool:
    if not INCLUDE_DOTFILES and filepath.name.startswith("."):
        return True
    if filepath.name in EXCLUDED_FILES:
        return True
    if filepath.suffix.lower() in EXCLUDED_EXTS:
        return True
    try:
        size_mb = filepath.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return True
    except OSError:
        return True
    return False

def looks_binary(data: bytes) -> bool:
    if b"\x00" in data: return True
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = data.translate(None, text_chars)
    return (len(nontext) / max(1, len(data))) > 0.30

def get_filtered_tree(root: Path):
    """Generates (dirpath, dirnames, filenames) but filters them in-place."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter directories in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]
        # Filter filenames
        filenames[:] = [f for f in filenames if not should_exclude_file(Path(dirpath) / f)]
        
        # Sort for deterministic output
        dirnames.sort(key=lambda x: x.lower())
        filenames.sort(key=lambda x: x.lower())
        
        yield Path(dirpath), dirnames, filenames

def build_tree_lines(root: Path) -> list[str]:
    lines: list[str] = [f"ROOT: {root.resolve()}", ""]
    for dirpath, dirnames, filenames in get_filtered_tree(root):
        rel_dir = dirpath.relative_to(root)
        depth = 0 if rel_dir == Path(".") else len(rel_dir.parts)
        indent = "  " * depth
        
        dir_label = "." if rel_dir == Path(".") else rel_dir.as_posix()
        lines.append(f"{indent}[D] {dir_label}")

        for fn in filenames:
            lines.append(f"{indent}  [F] {fn}")
    return lines

def read_text_safely(path: Path) -> tuple[str | None, str]:
    try:
        data = path.read_bytes()
        if SKIP_BINARY_FILES and looks_binary(data): return None, "SKIPPED (binary)"
        for enc in ("utf-8", sys.getdefaultencoding(), "cp1250", "latin-1"):
            try: return data.decode(enc), f"OK ({enc})"
            except: continue
        return data.decode("utf-8", errors="replace"), "OK (replacement)"
    except Exception as e:
        return None, f"ERROR: {e}"

def main() -> None:
    root = Path(ROOT_DIR).expanduser().resolve()
    out_path = root / OUTPUT_FILENAME

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"FOLDER DUMP - {datetime.now()}\n{'='*80}\n")
        
        if INCLUDE_TREE:
            f.write("\nDIRECTORY TREE\n" + "-"*20 + "\n")
            f.write("\n".join(build_tree_lines(root)) + f"\n{'='*80}\n")
        
        if INCLUDE_FILE_CONTENTS:
            for dirpath, _, filenames in get_filtered_tree(root):
                for fn in filenames:
                    abs_path = dirpath / fn
                    rel_path = abs_path.relative_to(root)
                    
                    f.write(f"FILE: {rel_path.as_posix()}\n" + "-"*40 + "\n")
                    text, note = read_text_safely(abs_path)
                    f.write(text if text else f"[{note}]\n")
                    f.write(FILE_END_MARKER)

    print(f"Dump exported to: {out_path}")

if __name__ == "__main__":
    main()