#!/usr/bin/env python3
"""
Smart Tree Dump v2 — pro AI kontext

Hierarchie na začátku obsahuje VŠECHNY soubory (žádné excludy).
Obsah souborů se vypisuje ve 3 úrovních:
  FULL    – celý obsah (zdrojáky, konfigurace, manifesty…)
  SUMMARY – stručný popis (velké XML drawables, binárky, generované soubory…)
  SKIP    – jen v hierarchii, žádný výpis v sekci obsahu

Ulož vedle projektu a spusť:  python dump_v2.py
"""

from __future__ import annotations
import os
import re
import string
import binascii
from pathlib import Path
from datetime import datetime
from typing import Literal

# ══════════════════════════════════════════════
# KONFIGURACE
# ══════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent
TARGET_SUBDIR = "BookCreator"

# Výstup
OUTPUT_BASENAME = "dump"
AUTO_TIMESTAMP = False
OUTPUT_DIR = BASE_DIR

# Hierarchie — tyto složky se ÚPLNĚ přeskočí (ani v hierarchii)
HIERARCHY_EXCLUDE_DIRS = {
    ".git", ".gradle", ".idea", "build", ".cxx",
    ".externalNativeBuild", ".scannerwork", ".fleet", ".metadata",
}

# Maximální hloubka (None = bez limitu)
MAX_DEPTH = None

# Encoding
CONTENT_ENCODING = "utf-8"

# ── Pravidla pro úroveň detailu ──────────────

# SKIP: v hierarchii ano, obsah ne (ani summary)
SKIP_FILE_NAMES = {
    "local.properties", ".DS_Store", "Thumbs.db",
    "gradlew", "gradlew.bat", "gradle-wrapper.properties",
}
SKIP_EXTENSIONS = {
    ".iml", ".class", ".keystore", ".jks", ".apk", ".aab",
    ".zip", ".7z", ".rar", ".jar", ".so", ".o", ".obj",
    ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".mp4", ".mov", ".avi", ".mp3", ".wav", ".ogg", ".svg",
    ".png", ".bmp", ".tiff",
}
# Soubory které přeskočit obsah pokud jsou větší než X bajtů
SKIP_IF_LARGER_THAN: dict[str, int] = {}  # např. {".xml": 50_000}

# SUMMARY: vypíše se jen stručný popis (typ, velikost, první řádky…)
SUMMARY_EXTENSIONS = {
    ".aar", ".ttf", ".otf", ".woff", ".woff2",
}
SUMMARY_MAX_FIRST_LINES = 5  # kolik řádků ukázat u SUMMARY textových souborů

# FULL: plný obsah — všechno co není SKIP ani SUMMARY
FULL_MAX_BYTES = 200_000  # oříznutí velkých souborů

# ── Speciální pravidla ────────────────────────
# Vector drawable XML — pokud soubor je XML s <vector ...>, vypíše se jen SUMMARY
VECTOR_DRAWABLE_SUMMARY = True
# Práh pro vector drawable: pokud XML s <vector> je větší než toto → SUMMARY
VECTOR_DRAWABLE_SIZE_THRESHOLD = 2_000  # bajty

# Gradle wrapper skripty — SKIP (jsou generované a dlouhé)
SKIP_GRADLE_WRAPPER = True

# Proguard rules — SUMMARY (typicky jen komentáře)
PROGUARD_SUMMARY = True

# Test soubory — FULL ale s poznámkou
# (žádná speciální logika, jen info)

# ══════════════════════════════════════════════
# KONEC KONFIGURACE
# ══════════════════════════════════════════════

ContentLevel = Literal["FULL", "SUMMARY", "SKIP"]


def human_size(n: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or u == "TB":
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024.0
    return f"{n} B"


def format_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def is_probably_text(head: bytes) -> bool:
    if not head:
        return True
    if b"\x00" in head:
        return False
    printable = set(bytes(string.printable, "ascii"))
    ratio = sum(b in printable for b in head) / max(1, len(head))
    return ratio >= 0.85


def is_vector_drawable_xml(path: Path) -> bool:
    """Detekuje Android vector drawable XML."""
    if path.suffix.lower() != ".xml":
        return False
    try:
        head = path.read_bytes()[:500].decode("utf-8", errors="replace")
        return "<vector" in head.lower() and "android:" in head.lower()
    except Exception:
        return False


def extract_vector_dimensions(path: Path) -> str:
    """Vytáhne rozměry a počet <path> elementů z vector XML."""
    try:
        content = path.read_text(CONTENT_ENCODING, errors="replace")
        width = re.search(r'android:width="([^"]+)"', content)
        height = re.search(r'android:height="([^"]+)"', content)
        path_count = len(re.findall(r"<path\b", content))

        dims = ""
        if width and height:
            dims = f"{width.group(1)} × {height.group(1)}"
        return f"Android Vector Drawable | {dims} | {path_count} path(s)"
    except Exception:
        return "Android Vector Drawable (nelze parsovat)"


def classify_file(path: Path) -> ContentLevel:
    """Rozhodne úroveň detailu pro soubor."""
    name = path.name
    ext = path.suffix.lower()

    # SKIP pravidla
    if name in SKIP_FILE_NAMES:
        return "SKIP"
    if ext in SKIP_EXTENSIONS:
        return "SKIP"
    if SKIP_GRADLE_WRAPPER and name in ("gradlew", "gradlew.bat"):
        return "SKIP"

    # SUMMARY pravidla
    if ext in SUMMARY_EXTENSIONS:
        return "SUMMARY"
    if PROGUARD_SUMMARY and "proguard" in name.lower():
        return "SUMMARY"

    # Vector drawable detekce
    if VECTOR_DRAWABLE_SUMMARY and ext == ".xml":
        try:
            size = path.stat().st_size
            if size > VECTOR_DRAWABLE_SIZE_THRESHOLD and is_vector_drawable_xml(path):
                return "SUMMARY"
        except Exception:
            pass

    # Velké soubory
    for pattern_ext, max_size in SKIP_IF_LARGER_THAN.items():
        if ext == pattern_ext:
            try:
                if path.stat().st_size > max_size:
                    return "SUMMARY"
            except Exception:
                pass

    return "FULL"


def write_full_content(lines: list[str], path: Path) -> None:
    """Vypíše plný obsah souboru."""
    try:
        size = path.stat().st_size
    except Exception:
        lines.append("  [chyba čtení]")
        return

    try:
        head = path.read_bytes()[:4096]
    except Exception as e:
        lines.append(f"  [chyba: {e}]")
        return

    if is_probably_text(head):
        try:
            limit = min(FULL_MAX_BYTES, size)
            text = path.read_bytes()[:limit].decode(CONTENT_ENCODING, errors="replace")
        except Exception as e:
            lines.append(f"  [chyba dekódování: {e}]")
            return

        lines.append("    === OBSAH ===")
        for line in text.splitlines():
            lines.append(f"    {line}")
        if size > FULL_MAX_BYTES:
            lines.append(f"    [ZKRÁCENO – {human_size(FULL_MAX_BYTES)} z {human_size(size)}]")
        lines.append("    === KONEC ===")
    else:
        hex_preview = binascii.hexlify(path.read_bytes()[:64]).decode("ascii")
        grouped = " ".join(hex_preview[i:i + 2] for i in range(0, len(hex_preview), 2))
        lines.append(f"    [BINÁRNÍ] {human_size(size)} | hex: {grouped[:80]}…")


def write_summary_content(lines: list[str], path: Path) -> None:
    """Vypíše stručné summary souboru."""
    try:
        size = path.stat().st_size
    except Exception:
        size = 0

    ext = path.suffix.lower()

    # Vector drawable
    if ext == ".xml" and is_vector_drawable_xml(path):
        desc = extract_vector_dimensions(path)
        lines.append(f"    [SUMMARY] {desc} | {human_size(size)}")
        return

    # Binární soubory
    try:
        head = path.read_bytes()[:4096]
    except Exception:
        lines.append(f"    [SUMMARY] binární soubor | {human_size(size)}")
        return

    if not is_probably_text(head):
        lines.append(f"    [SUMMARY] binární soubor | {human_size(size)}")
        return

    # Textový soubor — ukázat prvních pár řádků
    try:
        text = path.read_bytes()[:2000].decode(CONTENT_ENCODING, errors="replace")
        first_lines = text.splitlines()[:SUMMARY_MAX_FIRST_LINES]
        lines.append(f"    [SUMMARY] textový soubor | {human_size(size)} | prvních {len(first_lines)} řádků:")
        for fl in first_lines:
            lines.append(f"      {fl}")
        if len(text.splitlines()) > SUMMARY_MAX_FIRST_LINES:
            lines.append(f"      … (celkem ~{len(text.splitlines())}+ řádků)")
    except Exception:
        lines.append(f"    [SUMMARY] textový soubor | {human_size(size)}")


# ── Hierarchie (KOMPLETNÍ, bez filtrů na soubory) ──

def should_exclude_dir_from_hierarchy(name: str) -> bool:
    return name in HIERARCHY_EXCLUDE_DIRS


def build_full_hierarchy(root: Path) -> list[str]:
    """Kompletní strom — všechny soubory a adresáře (kromě HIERARCHY_EXCLUDE_DIRS)."""
    out: list[str] = ["."]

    branch = "├── "
    last_branch = "└── "
    pipe = "│   "
    space = "    "

    def recurse(cur: Path, prefix: str, depth: int):
        if MAX_DEPTH is not None and depth > MAX_DEPTH:
            return
        try:
            entries = list(cur.iterdir())
        except Exception:
            return

        dirs = sorted(
            [e for e in entries if e.is_dir() and not should_exclude_dir_from_hierarchy(e.name)],
            key=lambda p: p.name.lower(),
        )
        files = sorted(
            [e for e in entries if e.is_file()],
            key=lambda p: p.name.lower(),
        )

        children = dirs + files
        for idx, child in enumerate(children):
            is_last = idx == len(children) - 1
            connector = last_branch if is_last else branch

            # Přidat anotaci úrovně pro soubory
            suffix = ""
            if child.is_file():
                level = classify_file(child)
                try:
                    size = child.stat().st_size
                    suffix = f"  ({human_size(size)})"
                except Exception:
                    pass
                if level == "SKIP":
                    suffix += "  [—]"
                elif level == "SUMMARY":
                    suffix += "  [S]"
                # FULL nemá žádnou značku (default)

            out.append(f"{prefix}{connector}{child.name}{suffix}")

            if child.is_dir():
                new_prefix = prefix + (space if is_last else pipe)
                recurse(child, new_prefix, depth + 1)

    recurse(root, "", 0)
    return out


# ── Hlavní dump ──

def dump_tree(target_dir: Path) -> Path:
    if not target_dir.exists():
        raise FileNotFoundError(f"Cesta neexistuje: {target_dir}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S") if AUTO_TIMESTAMP else ""
    parts = [OUTPUT_BASENAME, target_dir.name, ts]
    out_name = "_".join(p for p in parts if p) + ".txt"
    out_path = OUTPUT_DIR / out_name

    lines: list[str] = []

    # ── Legenda ──
    lines.append("===== LEGENDA =====")
    lines.append("[—] = obsah přeskočen (binárka, generovaný soubor, asset…)")
    lines.append("[S] = jen stručné summary (velké XML drawables, proguard…)")
    lines.append("(bez značky) = plný obsah v sekci níže")
    lines.append("")

    # ── Kompletní hierarchie ──
    lines.append("===== HIERARCHIE =====")
    lines.extend(build_full_hierarchy(target_dir))
    lines.append("")

    # ── Obsah souborů ──
    lines.append("===== OBSAH SOUBORŮ =====")
    lines.append("")

    total_files = 0
    full_count = 0
    summary_count = 0
    skip_count = 0

    for current_root, dirnames, filenames in os.walk(target_dir):
        rel = Path(current_root).relative_to(target_dir)
        depth = 0 if rel.as_posix() == "." else len(rel.parts)
        if MAX_DEPTH is not None and depth > MAX_DEPTH:
            dirnames[:] = []
            continue

        dirnames[:] = [d for d in dirnames if not should_exclude_dir_from_hierarchy(d)]
        dirnames.sort(key=str.lower)
        filenames.sort(key=str.lower)

        folder_path = Path(current_root)

        for fname in sorted(filenames, key=str.lower):
            p = folder_path / fname
            total_files += 1
            level = classify_file(p)

            if level == "SKIP":
                skip_count += 1
                continue

            rel_file = p.relative_to(target_dir)
            meta_parts = []
            try:
                meta_parts.append(human_size(p.stat().st_size))
            except Exception:
                pass
            mt = format_mtime(p)
            if mt:
                meta_parts.append(mt)
            meta = f"  [{' | '.join(meta_parts)}]" if meta_parts else ""

            lines.append(f"── {rel_file.as_posix()}{meta}")

            if level == "FULL":
                write_full_content(lines, p)
                full_count += 1
            elif level == "SUMMARY":
                write_summary_content(lines, p)
                summary_count += 1

            lines.append("")

    # ── Statistiky ──
    lines.append("===== STATISTIKY =====")
    lines.append(f"Projekt:       {target_dir}")
    lines.append(f"Souborů celkem: {total_files}")
    lines.append(f"  FULL obsah:   {full_count}")
    lines.append(f"  SUMMARY:      {summary_count}")
    lines.append(f"  SKIP:         {skip_count}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    target_dir = (BASE_DIR / TARGET_SUBDIR).resolve()
    out_path = dump_tree(target_dir)
    print(f"Hotovo — uloženo do: {out_path}")
    # Ukázat velikost výstupu
    print(f"Velikost: {human_size(out_path.stat().st_size)}")


if __name__ == "__main__":
    main()