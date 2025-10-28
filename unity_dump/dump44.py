#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from datetime import datetime
import fnmatch
import hashlib
import json
import re
import zipfile

# === Nastavení (změň podle potřeby) ==========================================
ROOT_DIR = Path(r"C:\Users\volny\Documents\unity tutorial\Prvni_hra")
ROOT_DIR = Path(r"C:\Users\volny\Documents\the last human\team02\The Last Human")

# OUTPUT_FILE:
#  - None => root/dump.txt
#  - "C:\\path\\dump_{project}_{ts}.txt" => použij placeholders
#  - "C:\\path\\folder" (bez přípony) => uvnitř vytvoří dump_{project}_{ts}.txt
OUTPUT_FILE = r"C:\Users\volny\Documents\the last human\dump44.txt"

# Volitelně vytvořit ZIP “minimal repro” vedle dumpu
CREATE_MIN_ZIP = True
ZIP_NAME_TEMPLATE = "repro_44.zip"

# Výběr souborů do ZIPu (relativně k ROOT_DIR)
ZIP_INCLUDE = [
    "Assets",
    "Packages",
    "ProjectSettings",
    "ProjectSettings/ProjectVersion.txt",
]

# 1) Ignorované složky (dle JEDNOTLIVÝCH částí cesty)
EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__",
    # Unity typicky:
    "library", "logs", "temp", "obj", "build",
}

# 2) Ignorované přesné názvy souborů (bez cest)
EXCLUDE_FILES = {
    "dump.txt",
}

# 3) Ignorované přípony (bez tečky)
EXCLUDE_EXTS = {"dll", "pdb", "cache", "log"}

# 4) Glob vzory (matchují relativní cestu vůči rootu)
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

# 5) Jaké přípony považovat za "skripty" a zda omezit velikost při výpisu
SCRIPT_EXTS = {"cs", "js", "ts", "shader", "compute", "cginc"}
MAX_SCRIPT_BYTES = 2_000_000  # bezpečnostní limit na čtení obsahu
# ============================================================================

GUID_RE = re.compile(r"guid:\s*([0-9a-fA-F]{32})")
SCRIPT_GUID_RE = re.compile(r"m_Script:\s*\{[^}]*guid:\s*([0-9a-fA-F]{32})", re.MULTILINE)

def norm_lower(s: str) -> str:
    return s.casefold()

def is_excluded(rel_path: Path) -> bool:
    for part in rel_path.parts:
        if norm_lower(part) in EXCLUDE_DIRS:
            return True
    name_lower = norm_lower(rel_path.name)
    if name_lower in EXCLUDE_FILES:
        return True
    if rel_path.suffix:
        ext = norm_lower(rel_path.suffix.lstrip("."))
        if ext in EXCLUDE_EXTS:
            return True
    rel_as_posix = norm_lower(rel_path.as_posix())
    for pattern in EXCLUDE_GLOBS:
        if fnmatch.fnmatch(rel_as_posix, norm_lower(pattern)):
            return True
    return False

def iter_all_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root)
            if not is_excluded(rel):
                yield rel

def is_script(rel_path: Path) -> bool:
    return rel_path.suffix and rel_path.suffix.lstrip(".").casefold() in SCRIPT_EXTS

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_tree(dir_path: Path, out, prefix: str = "", root: Path = None):
    if root is None:
        root = dir_path
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

def write_scripts_section(root: Path, out):
    out.write("## Skripty a jejich obsah\n")
    scripts = [p for p in iter_all_files(root) if is_script(p)]
    total_lines = 0
    out.write(f"Celkem skriptů: {len(scripts)}\n\n")
    for rel in sorted(scripts, key=lambda p: p.as_posix().lower()):
        abs_path = root / rel
        try:
            size = abs_path.stat().st_size
        except OSError:
            size = None
        header = f"### {rel.as_posix()}\n"
        out.write(header)
        # NEW: hash
        try:
            h = sha256_file(abs_path)
            out.write(f"(SHA256: {h})\n")
        except Exception as e:
            out.write(f"(SHA256 error: {e})\n")
        if size is not None and size > MAX_SCRIPT_BYTES:
            out.write(f"(Soubor přesáhl limit {MAX_SCRIPT_BYTES} B, obsah nevypsán.)\n\n")
            continue
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            out.write(f"(Nelze přečíst soubor: {e})\n\n")
            continue
        lines = text.count("\n") + (0 if text.endswith("\n") else 1 if text else 0)
        total_lines += lines
        out.write("```" + rel.suffix.lstrip(".") + "\n")
        out.write(text)
        if not text.endswith("\n"):
            out.write("\n")
        out.write("```\n\n")
    out.write(f"Souhrn řádků ve skriptech: {total_lines}\n\n")

# NEW: verze Unity
def write_unity_version(root: Path, out):
    pv = root / "ProjectSettings" / "ProjectVersion.txt"
    out.write("## Unity verze\n")
    if pv.exists():
        try:
            txt = pv.read_text(encoding="utf-8", errors="replace")
            out.write(txt.strip() + "\n\n")
        except Exception as e:
            out.write(f"(Nelze přečíst ProjectVersion.txt: {e})\n\n")
    else:
        out.write("(ProjectVersion.txt nenalezen)\n\n")

# NEW: balíčky z manifestů
def write_packages(root: Path, out):
    out.write("## Packages (manifest.json)\n")
    man = root / "Packages" / "manifest.json"
    if man.exists():
        try:
            data = json.loads(man.read_text(encoding="utf-8", errors="replace"))
            deps = data.get("dependencies", {})
            for k in sorted(deps):
                out.write(f"- {k}: {deps[k]}\n")
            out.write("\n")
        except Exception as e:
            out.write(f"(Nelze číst manifest.json: {e})\n\n")
    else:
        out.write("(manifest.json nenalezen)\n\n")

    out.write("## Packages (packages-lock.json)\n")
    lock = root / "Packages" / "packages-lock.json"
    if lock.exists():
        try:
            data = json.loads(lock.read_text(encoding="utf-8", errors="replace"))
            deps = data.get("dependencies", {})
            for k in sorted(deps):
                v = deps[k].get("version")
                src = deps[k].get("source")
                out.write(f"- {k}: {v} ({src})\n")
            out.write("\n")
        except Exception as e:
            out.write(f"(Nelze číst packages-lock.json: {e})\n\n")
    else:
        out.write("(packages-lock.json nenalezen)\n\n")

# NEW: scény v buildu
def write_build_scenes(root: Path, out):
    out.write("## Scény v build nastavení\n")
    ebs = root / "ProjectSettings" / "EditorBuildSettings.asset"
    if not ebs.exists():
        out.write("(EditorBuildSettings.asset nenalezen)\n\n")
        return
    try:
        txt = ebs.read_text(encoding="utf-8", errors="replace")
        # velmi jednoduchý parser
        scenes = []
        current = {}
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith("- path:"):
                current = {"path": line.split(":", 1)[1].strip()}
                scenes.append(current)
            elif line.startswith("enabled:") and current is not None:
                current["enabled"] = line.split(":", 1)[1].strip()
        if scenes:
            for i, s in enumerate(scenes):
                out.write(f"{i:02d}. {s.get('path')} (enabled={s.get('enabled')})\n")
            out.write("\n")
        else:
            out.write("(V EditorBuildSettings.asset nebyly nalezeny scény)\n\n")
    except Exception as e:
        out.write(f"(Chyba při čtení EditorBuildSettings.asset: {e})\n\n")

# NEW: GUID mapa skriptů
def build_guid_map_for_scripts(root: Path):
    guid_to_script = {}
    for rel in iter_all_files(root):
        if rel.suffix == ".meta" and rel.as_posix().lower().endswith(".cs.meta"):
            abs_meta = root / rel
            try:
                txt = abs_meta.read_text(encoding="utf-8", errors="replace")
                m = GUID_RE.search(txt)
                if m:
                    guid = m.group(1).lower()
                    script_path = rel.with_suffix("").with_suffix("")  # .cs.meta -> .cs
                    # Pozn.: .with_suffix("") odstraní ".meta", druhé odstraní ".cs"
                    # Bezpečněji:
                    script_path = Path(rel.as_posix()[:-5])  # odříznout ".meta"
                    guid_to_script[guid] = script_path.as_posix()[:-3] + ".cs"
            except Exception:
                pass
    return guid_to_script

# NEW: Rozbor prefabů a scén -> jaké skripty jsou připojené
def write_asset_script_references(root: Path, out, guid_map):
    def list_refs(rel_paths, title):
        out.write(title + "\n")
        count = 0
        for rel in sorted(rel_paths, key=lambda p: p.as_posix().lower()):
            abs_path = root / rel
            try:
                txt = abs_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                out.write(f"- {rel.as_posix()} (nelze číst: {e})\n")
                continue
            guids = set(SCRIPT_GUID_RE.findall(txt))
            if not guids:
                continue
            count += 1
            out.write(f"### {rel.as_posix()}\n")
            for g in sorted(guids):
                path = guid_map.get(g.lower(), "(neznámý skript GUID)")
                out.write(f"- script GUID {g} -> {path}\n")
            out.write("\n")
        if count == 0:
            out.write("(Nenalezeny žádné odkazy na MonoBehaviour skripty)\n\n")

    prefabs = [p for p in iter_all_files(root) if p.suffix.lower() == ".prefab"]
    scenes  = [p for p in iter_all_files(root) if p.suffix.lower() == ".unity"]

    list_refs(prefabs, "## Prefaby → připojené skripty")
    list_refs(scenes,  "## Scény → připojené skripty")

# NEW: Heuristiky pro TMP/UI
def write_ui_tmp_checks(root: Path, out):
    out.write("## UI/TMP kontroly (heuristické)\n")
    # 1) balíček TMP v manifestu
    man = root / "Packages" / "manifest.json"
    has_tmp_pkg = False
    if man.exists():
        try:
            deps = json.loads(man.read_text(encoding="utf-8", errors="replace")).get("dependencies", {})
            has_tmp_pkg = "com.unity.textmeshpro" in deps
        except Exception:
            pass
    out.write(f"- com.unity.textmeshpro v manifestu: {'ANO' if has_tmp_pkg else 'NEBO NEZJIŠTĚNO'}\n")

    # 2) existuje složka TextMesh Pro?
    has_tmp_folder = (root / "Assets" / "TextMesh Pro").exists()
    out.write(f"- Assets/TextMesh Pro složka existuje: {'ANO' if has_tmp_folder else 'NE'}\n")

    # 3) grep klíčových tokenů v scénách/prefabech
    tokens = ["TextMeshProUGUI", "TextMeshPro", "Canvas"]
    occurrences = {t: 0 for t in tokens}
    for rel in iter_all_files(root):
        if rel.suffix.lower() in {".unity", ".prefab"}:
            try:
                txt = (root / rel).read_text(encoding="utf-8", errors="replace")
                for t in tokens:
                    if t in txt:
                        occurrences[t] += 1
            except Exception:
                pass
    for t in tokens:
        out.write(f"- Výskyt „{t}“ ve scénách/prefabech: {occurrences[t]}\n")
    out.write("\n")

# NEW: Hash a velikosti důležitých souborů
def write_key_files_hashes(root: Path, out):
    out.write("## Kontrolní součty klíčových souborů\n")
    key_globs = [
        "ProjectSettings/ProjectVersion.txt",
        "ProjectSettings/ProjectSettings.asset",
        "ProjectSettings/EditorBuildSettings.asset",
        "Packages/manifest.json",
        "Packages/packages-lock.json",
        "Assets/**/*.unity",
        "Assets/**/*.prefab",
    ]
    matched = set()
    for pattern in key_globs:
        for p in root.glob(pattern):
            if p.is_file():
                matched.add(p)
    for p in sorted(matched, key=lambda x: x.as_posix().lower()):
        try:
            h = sha256_file(p)
            size = p.stat().st_size
            out.write(f"- {p.relative_to(root).as_posix()} | {size} B | SHA256 {h}\n")
        except Exception as e:
            out.write(f"- {p.relative_to(root).as_posix()} | error: {e}\n")
    out.write("\n")

def resolve_output_path(root: Path) -> Path:
    if OUTPUT_FILE is None:
        p = root / "dump.txt"
    else:
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d_%H-%M-%S")
        fmt = str(OUTPUT_FILE).format(project=root.name, date=now.date(), ts=ts)
        p = Path(fmt)
        if p.exists() and p.is_dir():
            p = p / f"dump_{root.name}_{ts}.txt"
        elif not p.suffix:
            p = p / f"dump_{root.name}_{ts}.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

# NEW: vytvoření ZIPu minimálního repro
def create_min_zip(root: Path, dump_path: Path):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_name = ZIP_NAME_TEMPLATE.format(project=root.name, ts=now)
    zip_path = dump_path.parent / zip_name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for item in ZIP_INCLUDE:
            p = root / item
            if p.is_file():
                z.write(p, p.relative_to(root).as_posix())
            elif p.is_dir():
                for file in p.rglob("*"):
                    if file.is_file():
                        rel = file.relative_to(root).as_posix()
                        # nepřidávej Library atp., pro jistotu filtr:
                        if not is_excluded(Path(rel)):
                            z.write(file, rel)
    return zip_path

def main():
    root = ROOT_DIR
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Chyba: '{root}' neexistuje nebo to není složka.")
    output = resolve_output_path(root)

    with output.open("w", encoding="utf-8", errors="replace") as f:
        # Hlavička
        f.write("# DUMP souborů a hierarchie\n")
        f.write(f"Kořenová složka: {root.resolve()}\n")
        f.write(f"Vygenerováno: {datetime.now().isoformat(timespec='seconds')}\n\n")

        # Unity verze
        write_unity_version(root, f)

        # Packages
        write_packages(root, f)

        # Scény v buildu
        write_build_scenes(root, f)

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
        f.write("\n")

        # Výpis skriptů + obsah
        write_scripts_section(root, f)

        # GUID mapa a reference v prefabech/scénách
        guid_map = build_guid_map_for_scripts(root)
        write_asset_script_references(root, f, guid_map)

        # Heuristiky pro TMP/UI
        write_ui_tmp_checks(root, f)

        # Hash vybraných souborů
        write_key_files_hashes(root, f)

    print(f"Hotovo. Výstup zapsán do: {output.resolve()}")

    if CREATE_MIN_ZIP:
        zip_path = create_min_zip(root, output)
        print(f"Vytvořen ZIP s minimálním repro: {zip_path.resolve()}")

if __name__ == "__main__":
    main()
