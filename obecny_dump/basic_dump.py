"""
Project / folder dumper
- Recursively walks ROOT_DIR (including subfolders)
- Exports a single .txt containing a directory tree + file contents
- Controlled ONLY by config constants below (no CLI args)
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import os
import sys

# =========================
# CONFIG (edit these only)
# =========================

# Root folder to dump
ROOT_DIR = r"C:\path\to\your\project"

# Output file name (".txt" will be appended if missing)
OUTPUT_FILENAME = "folder_dump.txt"

# Where to export the dump (ignored if EXPORT_TO_ROOT_DIR is True)
OUTPUT_DIR = r"C:\path\to\export"

# If True, export the dump into ROOT_DIR (overrides OUTPUT_DIR)
EXPORT_TO_ROOT_DIR = True

# Exclusions
EXCLUDED_DIR_NAMES = {
    ".git", ".idea", ".vscode", "__pycache__", "build", "dist", "node_modules",
    ".gradle", ".mypy_cache", ".pytest_cache", ".venv", "venv"
}

# Exclude by relative path (from ROOT_DIR), e.g. {"app/src/main/res/drawable-old"}
# Use forward slashes or backslashes; matching is normalized.
EXCLUDED_DIR_REL_PATHS = set()

# Exclude file extensions (case-insensitive, include the dot)
EXCLUDED_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico",
    ".mp4", ".mov", ".avi", ".mkv",
    ".zip", ".7z", ".rar", ".tar", ".gz",
    ".pdf",
    ".exe", ".dll", ".so", ".dylib",
    ".class", ".jar",
    ".keystore",
}

# Behavior
INCLUDE_TREE = True
INCLUDE_FILE_CONTENTS = True

# Skip very large files (to keep the dump manageable)
MAX_FILE_SIZE_MB = 2.0

# If True, try to detect binary files and skip them
SKIP_BINARY_FILES = True

# If True, include hidden files/folders (dotfiles). Windows "hidden" attribute is not checked.
INCLUDE_DOTFILES = True

# End of file marker per file
FILE_END_MARKER = "\n" + ("-" * 80) + "\n\n"

# =========================
# IMPLEMENTATION
# =========================


def normalize_rel_path(p: Path) -> str:
    # Convert path to a normalized posix-style relative string for matching
    return p.as_posix().lstrip("./")


def is_dotfile(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def should_exclude_dir(dir_path: Path, rel_dir: Path) -> bool:
    if dir_path.name in EXCLUDED_DIR_NAMES:
        return True

    rel_norm = normalize_rel_path(rel_dir)
    if rel_norm in {normalize_rel_path(Path(x)) for x in EXCLUDED_DIR_REL_PATHS}:
        return True

    if not INCLUDE_DOTFILES and is_dotfile(rel_dir):
        return True

    return False


def should_exclude_file(file_path: Path, rel_file: Path) -> bool:
    if file_path.suffix.lower() in {e.lower() for e in EXCLUDED_EXTS}:
        return True

    if not INCLUDE_DOTFILES and is_dotfile(rel_file):
        return True

    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return True
    except OSError:
        return True

    return False


def looks_binary(data: bytes) -> bool:
    # Simple heuristic: null bytes -> binary, or many non-text bytes
    if b"\x00" in data:
        return True
    # If it's mostly ASCII control chars (excluding common whitespace), treat as binary
    # This heuristic is intentionally conservative.
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = data.translate(None, text_chars)
    return (len(nontext) / max(1, len(data))) > 0.30


def build_tree_lines(root: Path) -> list[str]:
    lines: list[str] = []
    lines.append(f"ROOT: {root.resolve()}")
    lines.append("")

    # We'll walk with os.walk so we can prune directories in-place
    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)
        rel_dir = dir_path.relative_to(root)

        # Prune excluded directories
        pruned = []
        for d in list(dirnames):
            candidate = dir_path / d
            rel_candidate = candidate.relative_to(root)
            if should_exclude_dir(candidate, rel_candidate):
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)

        # Current directory line
        depth = 0 if rel_dir == Path(".") else len(rel_dir.parts)
        indent = "  " * depth
        display_dir = "." if rel_dir == Path(".") else normalize_rel_path(rel_dir)
        lines.append(f"{indent}[D] {display_dir}")

        # Files
        filenames_sorted = sorted(filenames, key=lambda x: x.lower())
        for fn in filenames_sorted:
            fp = dir_path / fn
            rel_file = fp.relative_to(root)
            if should_exclude_file(fp, rel_file):
                continue
            try:
                size = fp.stat().st_size
            except OSError:
                size = -1
            size_str = f"{size} B" if size >= 0 else "N/A"
            lines.append(f"{indent}  [F] {fn} ({size_str})")

    lines.append("")
    return lines


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)
        rel_dir = dir_path.relative_to(root)

        # Prune excluded directories
        pruned = []
        for d in list(dirnames):
            candidate = dir_path / d
            rel_candidate = candidate.relative_to(root)
            if should_exclude_dir(candidate, rel_candidate):
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)

        for fn in sorted(filenames, key=lambda x: x.lower()):
            fp = dir_path / fn
            rel_file = fp.relative_to(root)
            if should_exclude_file(fp, rel_file):
                continue
            yield fp, rel_file


def read_text_safely(path: Path) -> tuple[str | None, str]:
    """
    Returns (text_or_none, note)
    note is used in the dump to explain skips/errors.
    """
    try:
        data = path.read_bytes()
    except Exception as e:
        return None, f"ERROR reading bytes: {type(e).__name__}: {e}"

    if SKIP_BINARY_FILES and looks_binary(data):
        return None, "SKIPPED (binary detected)"

    # Try UTF-8 first, then fall back to system default, then latin-1
    for enc in ("utf-8", sys.getdefaultencoding(), "cp1250", "latin-1"):
        try:
            text = data.decode(enc)
            return text, f"OK (decoded as {enc})"
        except Exception:
            continue

    # Last resort: replace errors with UTF-8
    try:
        text = data.decode("utf-8", errors="replace")
        return text, "OK (utf-8 with replacement)"
    except Exception as e:
        return None, f"ERROR decoding: {type(e).__name__}: {e}"


def ensure_txt_suffix(name: str) -> str:
    return name if name.lower().endswith(".txt") else (name + ".txt")


def resolve_output_path(root: Path) -> Path:
    out_dir = root if EXPORT_TO_ROOT_DIR else Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / ensure_txt_suffix(OUTPUT_FILENAME)


def main() -> None:
    root = Path(ROOT_DIR).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"ROOT_DIR does not exist or is not a directory: {root}")

    out_path = resolve_output_path(root)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = [
        "FOLDER DUMP",
        f"Generated: {timestamp}",
        f"Root: {root}",
        f"Include tree: {INCLUDE_TREE}",
        f"Include file contents: {INCLUDE_FILE_CONTENTS}",
        f"Max file size: {MAX_FILE_SIZE_MB} MB",
        "",
        "=" * 80,
        "",
    ]

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(header))

        if INCLUDE_TREE:
            f.write("DIRECTORY TREE\n")
            f.write("=" * 80 + "\n\n")
            tree_lines = build_tree_lines(root)
            f.write("\n".join(tree_lines))
            f.write("\n" + "=" * 80 + "\n\n")

        if INCLUDE_FILE_CONTENTS:
            f.write("FILE CONTENTS\n")
            f.write("=" * 80 + "\n\n")

            for abs_path, rel_path in iter_files(root):
                f.write(f"FILE: {normalize_rel_path(rel_path)}\n")
                f.write(f"ABS:  {abs_path}\n")
                try:
                    size = abs_path.stat().st_size
                    f.write(f"SIZE: {size} B\n")
                except OSError:
                    f.write("SIZE: N/A\n")

                f.write("-" * 80 + "\n")

                text, note = read_text_safely(abs_path)
                if text is None:
                    f.write(f"[{note}]\n")
                else:
                    f.write(text)
                    if not text.endswith("\n"):
                        f.write("\n")
                    f.write(f"\n[{note}]\n")

                f.write(FILE_END_MARKER)

    print(f"Dump exported to: {out_path}")


if __name__ == "__main__":
    main()
