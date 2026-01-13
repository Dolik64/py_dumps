"""
Repo / folder dumper (AI-friendly)
- Finds git repo root automatically (folder with .git), even when run from subfolders
- Writes: directory tree + contents of selected text files
- Excludes common build/cache/binary noise
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os
import sys


# =========================
# CONFIG
# =========================

@dataclass(frozen=True)
class DumpConfig:
    # Output filename (written into repo root by default)
    output_filename: str = "folder_dump.txt"

    # If True: write output into repo root, otherwise into current working directory
    export_to_repo_root: bool = True

    # What to include
    include_tree: bool = True
    include_file_contents: bool = True

    # Limits / safety
    max_file_size_kb: int = 64  # text files bigger than this will be skipped
    skip_binary_files: bool = True
    include_dotfiles: bool = False  # e.g. ".env", ".gitignore" (you can still whitelist via extensions)

    # Directories to exclude (name-based)
    excluded_dir_names: set[str] = None  # filled in __post_init__ style below

    # Extensions to exclude (binary + latex build noise)
    excluded_exts: set[str] = None

    # Specific files to exclude (name-based)
    excluded_files: set[str] = None

    # If you want to dump only certain extensions, fill this set. Leave empty to dump all text-like files.
    allowed_exts: set[str] = None


DEFAULT_CONFIG = DumpConfig(
    excluded_dir_names={
        ".git", ".idea", ".vscode", "__pycache__", ".pytest_cache",
        "build", "dist", "out", ".gradle", ".cache", "node_modules",
        "venv", ".venv", ".mypy_cache",

        # LaTeX aux/build outputs (if you build locally)
        "bachelor_thesis/build", "master_thesis/build", "phd_thesis/build",
        "builds", "latexmk",

        # Big asset folders you usually don't want to paste into AI context
        # (leave them here; you can remove if you want)
        "fig", "photos", "plots", "data", "sketch", "tikz",
        "old", "old-assets", "old_assets", "backup", "backups",
    },
    excluded_exts={
        # images / binaries
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".pdf", ".psd",
        ".zip", ".7z", ".rar", ".tar", ".gz",
        ".exe", ".dll", ".so", ".dylib",

        # LaTeX build noise
        ".aux", ".bbl", ".blg", ".log", ".out", ".toc", ".lof", ".lot",
        ".fdb_latexmk", ".fls", ".synctex.gz", ".glo", ".gls", ".ist", ".acn", ".acr", ".alg",

        # misc
        ".pyc", ".class", ".o", ".obj", ".dvi",
    },
    excluded_files={
        "folder_dump.txt",
        "repo_dump.txt",
    },
    allowed_exts=set(),  # empty = allow all text-like files (filtered by binary detection + size)
)


# =========================
# IMPLEMENTATION
# =========================

TEXTY_EXT_HINTS = {
    ".tex", ".bib", ".md", ".txt", ".rst",
    ".csv", ".tsv",
    ".json", ".yaml", ".yml",
    ".xml", ".html", ".css",
    ".kt", ".java", ".py", ".js", ".ts",
    ".gradle", ".properties",
    ".ini", ".cfg",
}


def find_repo_root(start: Path) -> Path:
    """
    Find git repo root by walking upwards until a .git directory is found.
    If not found, returns the start directory.
    """
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur


def normalize_rel_path(p: Path) -> str:
    return p.as_posix().lstrip("./")


def should_exclude_dir(dir_path: Path, root: Path, cfg: DumpConfig) -> bool:
    name = dir_path.name
    if name in cfg.excluded_dir_names:
        return True

    # Also exclude if the *relative path* matches any excluded_dir_names entry like "bachelor_thesis/build"
    try:
        rel = dir_path.relative_to(root).as_posix()
        if rel in cfg.excluded_dir_names:
            return True
    except Exception:
        pass

    if not cfg.include_dotfiles and name.startswith("."):
        return True

    return False


def should_exclude_file(file_path: Path, root: Path, cfg: DumpConfig) -> bool:
    if file_path.name in cfg.excluded_files:
        return True

    # dotfiles control
    if not cfg.include_dotfiles and file_path.name.startswith("."):
        # allow some dotfiles if they look useful (gitignore, etc.) by extension/known names
        if file_path.name not in {".gitignore", ".gitattributes"}:
            return True

    # extension exclusions (handle .synctex.gz etc.)
    lower_name = file_path.name.lower()
    for ext in cfg.excluded_exts:
        if lower_name.endswith(ext):
            return True

    # allowed extensions (if set)
    if cfg.allowed_exts:
        if file_path.suffix.lower() not in {e.lower() for e in cfg.allowed_exts}:
            return True

    # size limit
    try:
        size_kb = file_path.stat().st_size / 1024.0
        if size_kb > cfg.max_file_size_kb:
            return True
    except OSError:
        return True

    return False


def looks_binary(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return True
    # Heuristic: count non-text bytes
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = data.translate(None, text_chars)
    return (len(nontext) / max(1, len(data))) > 0.30


def read_text_safely(path: Path, cfg: DumpConfig) -> tuple[str | None, str]:
    try:
        data = path.read_bytes()
        if cfg.skip_binary_files and looks_binary(data):
            return None, "SKIPPED (binary)"

        # Try a few encodings typical for CZ + UTF
        for enc in ("utf-8", "utf-8-sig", sys.getdefaultencoding(), "cp1250", "cp852", "latin-1"):
            try:
                return data.decode(enc), f"OK ({enc})"
            except Exception:
                continue

        return data.decode("utf-8", errors="replace"), "OK (replacement)"
    except Exception as e:
        return None, f"ERROR: {e}"


def build_tree_lines(root: Path, cfg: DumpConfig) -> list[str]:
    lines: list[str] = [f"ROOT: {root.resolve()}", ""]
    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)

        # prune dirs
        pruned = []
        for d in list(dirnames):
            cand = dir_path / d
            if should_exclude_dir(cand, root, cfg):
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)

        rel_dir = dir_path.relative_to(root)
        depth = 0 if rel_dir == Path(".") else len(rel_dir.parts)
        indent = "  " * depth
        lines.append(f"{indent}[D] {normalize_rel_path(rel_dir) if rel_dir != Path('.') else '.'}")

        for fn in sorted(filenames, key=lambda x: x.lower()):
            fp = dir_path / fn
            if should_exclude_file(fp, root, cfg):
                continue
            lines.append(f"{indent}  [F] {fn}")

    return lines


def iter_files(root: Path, cfg: DumpConfig):
    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)

        # prune dirs
        pruned = []
        for d in list(dirnames):
            cand = dir_path / d
            if should_exclude_dir(cand, root, cfg):
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)

        for fn in sorted(filenames, key=lambda x: x.lower()):
            fp = dir_path / fn
            if not should_exclude_file(fp, root, cfg):
                yield fp, fp.relative_to(root)


def main() -> None:
    cfg = DEFAULT_CONFIG

    start = Path.cwd()
    repo_root = find_repo_root(start)

    out_dir = repo_root if cfg.export_to_repo_root else start
    out_path = out_dir / cfg.output_filename

    file_end_marker = "\n" + ("-" * 80) + "\n\n"

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"FOLDER DUMP - {datetime.now().isoformat(sep=' ', timespec='seconds')}\n")
        f.write("=" * 80 + "\n\n")

        if cfg.include_tree:
            f.write("DIRECTORY TREE\n")
            f.write("-" * 20 + "\n")
            f.write("\n".join(build_tree_lines(repo_root, cfg)))
            f.write("\n\n" + ("=" * 80) + "\n\n")

        if cfg.include_file_contents:
            for abs_path, rel_path in iter_files(repo_root, cfg):
                f.write(f"FILE: {rel_path.as_posix()}\n")
                f.write("-" * 40 + "\n")
                text, note = read_text_safely(abs_path, cfg)
                if text is None:
                    f.write(f"[{note}]")
                else:
                    f.write(text)
                f.write(file_end_marker)

    print(f"Dump exported to: {out_path}")


if __name__ == "__main__":
    main()
