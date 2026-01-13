"""
Project / folder dumper
- Optimized for AI context: excludes redundancy and LaTeX noise.

USAGE:
1) Set ROOT_DIR below (absolute path to your cloned repo root).
2) Run: python folder_dump.py
3) It writes folder_dump.txt (by default into ROOT_DIR).
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import os
import sys

# =========================
# CONFIG (edit these only)
# =========================

# Root folder to dump (ABSOLUTE PATH).
# If None, the script auto-detects git repo root by searching for a ".git" folder upward from current working dir.
ROOT_DIR: str | None = r"C:\Users\volny\Desktop\skola\bachelor_thesis_document"

# Output file name (written either into ROOT_DIR or current working dir depending on EXPORT_TO_ROOT_DIR)
OUTPUT_FILENAME = "folder_dump.txt"

# If True, export the dump into ROOT_DIR (recommended).
# If False, export into the current working directory.
EXPORT_TO_ROOT_DIR = False

# 1) EXCLUDED DIRECTORIES (names)
EXCLUDED_DIR_NAMES = {
    ".git", ".idea", ".vscode", "__pycache__", "build", "dist", "node_modules",
    "venv",

    # Thesis-template assets that bloat context (adjust if you need them)
    "fig", "photos", "plots", "data", "sketch", "tikz",

    # Other thesis variants you don't need
    "phd_thesis",
    "master_thesis",
    # "bachelor_thesis",  # keep this ENABLED for your bachelor thesis repo (so DON'T exclude it)
}

# 2) EXCLUDED EXTENSIONS
EXCLUDED_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".pdf",
    ".aux", ".bbl", ".blg", ".log", ".out", ".toc", ".lof", ".lot",
    ".fdb_latexmk", ".fls", ".synctex.gz", ".glo", ".ist",
    ".bst", ".cls", ".sty", ".pyc", ".sh", ".sk", ".dvi", ".ps",
    ".exe", ".dll", ".zip", ".7z",
}

# 3) EXCLUDED SPECIFIC FILES (filenames)
EXCLUDED_FILES = {
    "folder_dump.txt",   # prevents dumping the dump
    "basic_dump.py",
    "basic_dump22.py",
    ".nojekyll",
    ".gitignore",
    "Makefile",
}

# Behavior
INCLUDE_TREE = True
INCLUDE_FILE_CONTENTS = True
MAX_FILE_SIZE_MB = 0.20  # 200KB default; adjust if needed
SKIP_BINARY_FILES = True
INCLUDE_DOTFILES = False  # hidden files starting with '.' (besides .git which is excluded anyway)
FILE_END_MARKER = "\n" + ("-" * 80) + "\n\n"


# =========================
# IMPLEMENTATION
# =========================

def normalize_rel_path(p: Path) -> str:
    return p.as_posix().lstrip("./")


def find_repo_root(start: Path) -> Path:
    """
    Walk upwards from 'start' until a directory containing '.git' is found.
    Falls back to 'start' if not found.
    """
    cur = start.resolve()
    for _ in range(100):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve()


def should_exclude_dir(dir_path: Path) -> bool:
    # skip dotdirs unless explicitly allowed
    if not INCLUDE_DOTFILES and dir_path.name.startswith(".") and dir_path.name not in {".git"}:
        return True
    return dir_path.name in EXCLUDED_DIR_NAMES


def should_exclude_file(file_path: Path) -> bool:
    if file_path.name in EXCLUDED_FILES:
        return True

    if (not INCLUDE_DOTFILES) and file_path.name.startswith("."):
        return True

    if file_path.suffix.lower() in {e.lower() for e in EXCLUDED_EXTS}:
        return True

    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return True
    except OSError:
        return True

    return False


def looks_binary(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = data.translate(None, text_chars)
    return (len(nontext) / max(1, len(data))) > 0.30


def build_tree_lines(root: Path) -> list[str]:
    lines: list[str] = [f"ROOT: {root.resolve()}", ""]
    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)

        # prune excluded directories in-place (important for os.walk)
        pruned = [d for d in list(dirnames) if should_exclude_dir(dir_path / d)]
        for d in pruned:
            dirnames.remove(d)

        rel_dir = dir_path.relative_to(root)
        depth = 0 if rel_dir == Path(".") else len(rel_dir.parts)
        indent = "  " * depth
        lines.append(f"{indent}[D] {normalize_rel_path(rel_dir) if rel_dir != Path('.') else '.'}")

        for fn in sorted(filenames, key=lambda x: x.lower()):
            fp = dir_path / fn
            if should_exclude_file(fp):
                continue
            lines.append(f"{indent}  [F] {fn}")

    return lines


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)

        pruned = [d for d in list(dirnames) if should_exclude_dir(dir_path / d)]
        for d in pruned:
            dirnames.remove(d)

        for fn in sorted(filenames, key=lambda x: x.lower()):
            fp = dir_path / fn
            if not should_exclude_file(fp):
                yield fp, fp.relative_to(root)


def read_text_safely(path: Path) -> tuple[str | None, str]:
    try:
        data = path.read_bytes()
        if SKIP_BINARY_FILES and looks_binary(data):
            return None, "SKIPPED (binary)"

        # try common encodings
        for enc in ("utf-8", sys.getdefaultencoding(), "cp1250", "latin-1"):
            try:
                return data.decode(enc), f"OK ({enc})"
            except Exception:
                pass

        return data.decode("utf-8", errors="replace"), "OK (replacement)"
    except Exception as e:
        return None, f"ERROR: {e}"


def main() -> None:
    start = Path.cwd()

    # Prefer explicit ROOT_DIR (macro), otherwise auto-detect git repo root
    if ROOT_DIR:
        root = Path(ROOT_DIR).expanduser().resolve()
    else:
        root = find_repo_root(start)

    if not root.exists() or not root.is_dir():
        raise SystemExit(f"ROOT_DIR does not exist or is not a directory: {root}")

    out_dir = root if EXPORT_TO_ROOT_DIR else start.resolve()
    out_path = out_dir / (OUTPUT_FILENAME if OUTPUT_FILENAME.endswith(".txt") else OUTPUT_FILENAME + ".txt")

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"FOLDER DUMP - {datetime.now()}\n{'=' * 80}\n")

        if INCLUDE_TREE:
            f.write("\nDIRECTORY TREE\n" + "-" * 20 + "\n")
            f.write("\n".join(build_tree_lines(root)) + f"\n{'=' * 80}\n")

        if INCLUDE_FILE_CONTENTS:
            for abs_path, rel_path in iter_files(root):
                f.write(f"FILE: {rel_path.as_posix()}\n" + "-" * 40 + "\n")
                text, note = read_text_safely(abs_path)
                f.write(text if text is not None else f"[{note}]")
                f.write(FILE_END_MARKER)

    print(f"Dump exported to: {out_path}")


if __name__ == "__main__":
    main()
