#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dump_scripts_compact.py
Bez-argumentový dump jen skriptů (default), s volitelnými sekcemi řízenými makry níže.
"""

from pathlib import Path
from datetime import datetime
import fnmatch, hashlib, re
from collections import Counter

# ===================== MAKRA / NASTAVENÍ =====================

# Kořen projektu a výstupní soubor
ROOT_DIR = Path(r"C:\Users\volny\Documents\the last human\team02\The Last Human")
# Pokud None -> uloží do {root}/dump.txt. Může používat {project},{date},{ts}
OUTPUT_FILE = r"C:\Users\volny\Documents\the last human\dumps\dump_scripts.txt"

# Co zahrnout do dumpu
INCLUDE_SCRIPTS = True            # musí zůstat True (primární obsah)
INCLUDE_TREE = False              # limitovaný strom složek (rychlý přehled)
INCLUDE_SCENES_LIST = False       # seznam .unity v Assets
INCLUDE_BUILD_SETTINGS = False    # EditorBuildSettings.asset krátké info
INCLUDE_ASSET_SUMMARY = False     # top rozšíření
INCLUDE_LARGEST_FILES = False     # top největší soubory (po filtrech)
INCLUDE_UNITY_VERSION = True      # kratičký řádek s verzí Unity
INCLUDE_YAML_ASSETS = False       # přidej prefab/scény atd. do dumpu

# ⬇️ NOVÉ MAKRO: přepínač „divných/hlučných“ adresářů (shadery apod.)
# False = vyloučit shadery a příbuzné věci; True = zahrnout (původní chování).
INCLUDE_NOISY = False

# Limity výstupu (rozpočty)
# (lehce navýšené, ať se méně často ořezává)
MAX_TOTAL_LINES = 12000
MAX_TOTAL_CHARS = 2_000_000
MAX_SNIPPET_HEAD = 500
MAX_SNIPPET_TAIL = 500
MAX_SNIPPETS = 500
MAX_SCRIPT_BYTES = 200_000

# Malé soubory vytiskni celé
FULL_FILE_IF_UNDER_BYTES = 50_000

# Skriptové globy (co považujeme za "naše" skripty)
SCRIPTS_INCLUDE_GLOBS = {
    "Assets/**/*.cs", "Assets/**/*.js", "Assets/**/*.ts",
    "Assets/**/*.shader", "Assets/**/*.compute", "Assets/**/*.cginc"
}
SCRIPTS_EXCLUDE_GLOBS = {
    "Assets/**/Editor/**",
    "Assets/**/ThirdParty/**",
    "Assets/**/Plugins/**",
    "Assets/**/Generated/**",
    "Assets/**/External/**",
    "Packages/**",
}

# ⬇️ NOVÉ: další globa, které se APLIKUJÍ POUZE pokud INCLUDE_NOISY=False
NOISY_EXTRA_EXCLUDE_GLOBS = {
    # typické shader/graph soubory a pomocné soubory pro shadery
    "Assets/**/*.shader",
    "Assets/**/*.cginc",
    "Assets/**/*.hlsl",
    "Assets/**/*.glsl",
    "Assets/**/*.compute",
    # časté „hlučné“ složky
    "Assets/**/Shaders/**",
    "Assets/**/Shader Graphs/**",
    "Assets/**/Gizmos/**",
    "Assets/**/Editor Default Resources/**",
    # TMP bývá velké a generické
    "Assets/TextMesh Pro/Shaders/**",
    "Assets/TextMesh Pro/Resources/**",
    "Assets/TextMesh Pro/Fonts/**",
}

YAML_EXTS = {".unity", ".prefab", ".anim", ".controller", ".asset", ".mat"}

# Obecné excludy, ať je dump svižný
EXCLUDE_DIRS = {d.casefold() for d in {
    ".git", "node_modules", "__pycache__", "library", "logs", "temp", "obj", "build"
}}
EXCLUDE_FILES = {f.casefold() for f in {"dump.txt"}}
EXCLUDE_EXTS = {e.casefold() for e in {"dll", "pdb", "cache", "log", "meta"}}
EXCLUDE_GLOBS = {p.casefold() for p in {
    "**/Library/**", "**/Logs/**", "**/obj/**", "**/Temp/**", "**/Build/**",
    "**/*.dll", "**/*.pdb", "**/*.cache", "**/*.log"
}}
SCRIPT_EXTS = {"cs", "js", "ts", "shader", "compute", "cginc", "hlsl", "glsl"}

# Strom: max hloubka a max souborů na složku (pokud je INCLUDE_TREE True)
TREE_MAX_DEPTH = 3
TREE_MAX_FILES_PER_DIR = 12

# ===================== UTIL FUNKCE =====================

def norm_lower(s: str) -> str: return s.casefold()

def is_excluded(rel_path: Path) -> bool:
    for part in rel_path.parts:
        if norm_lower(part) in EXCLUDE_DIRS:
            return True
    if norm_lower(rel_path.name) in EXCLUDE_FILES:
        return True
    if rel_path.suffix and rel_path.suffix.lstrip(".").casefold() in EXCLUDE_EXTS:
            return True
    rel_posix = norm_lower(rel_path.as_posix())
    for pattern in EXCLUDE_GLOBS:
        if fnmatch.fnmatch(rel_posix, pattern):
            return True
    return False

def match_any_glob(rel_path: Path, patterns: set[str]) -> bool:
    rp_l = rel_path.as_posix().casefold()
    for pat in patterns:
        if fnmatch.fnmatch(rp_l, pat.casefold()):
            return True
    return False

def iter_all_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root)
            if not is_excluded(rel):
                yield rel

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

def is_included_asset(rel: Path) -> bool:
    if INCLUDE_YAML_ASSETS and rel.suffix.casefold() in YAML_EXTS:
        return rel.as_posix().startswith("Assets/")
    return False

class BudgetWriter:
    def __init__(self, stream, max_lines, max_chars):
        self.s = stream
        self.rem_lines = max_lines
        self.rem_chars = max_chars
        self.truncated = False
    def write(self, text: str):
        if self.truncated:
            return
        if len(text) > self.rem_chars:
            text = text[:self.rem_chars]
            self.truncated = True
        lines = text.count("\n")
        if lines > self.rem_lines:
            allowed = self.rem_lines
            parts = text.splitlines(keepends=True)
            text = "".join(parts[:allowed])
            self.truncated = True
            lines = allowed
        self.s.write(text)
        self.rem_lines -= lines
        self.rem_chars -= len(text)
    def has_budget(self) -> bool:
        return not self.truncated and self.rem_lines > 0 and self.rem_chars > 0

# Bezpečné zapsání celého kódového bloku (aby se neuřízl bez koncového fence)
def can_fit_block(out: BudgetWriter, text: str) -> bool:
    return (not out.truncated) and (out.rem_lines >= text.count("\n")) and (out.rem_chars >= len(text))

def write_code_block(out: BudgetWriter, lang: str, header: str, body: str) -> bool:
    block = f"{header}\n```{lang}\n{body}```\n\n"
    if can_fit_block(out, block):
        out.write(block)
        return True
    return False

# ===================== UNITY POMOCNÍCI =====================

def read_unity_version(root: Path) -> str | None:
    pv = root / "ProjectSettings" / "ProjectVersion.txt"
    if pv.exists():
        try:
            return pv.read_text(encoding="utf-8", errors="replace").strip()
        except:
            return None
    return None

def list_scenes(root: Path):
    scenes = []
    for p in (root / "Assets").rglob("*.unity"):
        try:
            rel = p.relative_to(root).as_posix()
        except Exception:
            continue
        scenes.append(rel)
    scenes.sort(key=str.casefold)
    return scenes

def scenes_in_build(root: Path):
    f = root / "ProjectSettings" / "EditorBuildSettings.asset"
    result = []
    if not f.exists():
        return result
    try:
        txt = f.read_text(encoding="utf-8", errors="replace")
        current = {}
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith("- "):
                if current:
                    result.append(current)
                current = {}
            if line.startswith("path:"):
                current["path"] = line.split("path:",1)[1].strip()
            if line.startswith("enabled:"):
                current["enabled"] = line.split("enabled:",1)[1].strip()
        if current:
            result.append(current)
    except:
        pass
    return [{"path": i.get("path",""), "enabled": i.get("enabled","")} for i in result if i.get("path")]

def asset_extension_summary(root: Path):
    cnt = Counter()
    total = 0
    for rel in iter_all_files(root):
        total += 1
        ext = rel.suffix.lstrip(".").casefold() if rel.suffix else ""
        cnt[ext] += 1
    return total, cnt.most_common(30)

def largest_files(root: Path, k=20):
    items = []
    for rel in iter_all_files(root):
        try:
            size = (root / rel).stat().st_size
        except:
            continue
        items.append((size, rel.as_posix()))
    items.sort(reverse=True)
    return items[:k]

# ===================== SKRIPTY: PARS/METRIKY =====================

RE_CLASS = re.compile(r'^\s*(?:public|internal|protected|private)?\s*(?:abstract\s+|static\s+|partial\s+)*class\s+([A-Za-z_]\w*)', re.MULTILINE)
RE_STRUCT = re.compile(r'^\s*(?:public|internal|protected|private)?\s*struct\s+([A-Za-z_]\w*)', re.MULTILINE)
RE_ENUM = re.compile(r'^\s*(?:public|internal|protected|private)?\s*enum\s+([A-Za-z_]\w*)', re.MULTILINE)
RE_INTERFACE = re.compile(r'^\s*(?:public|internal|protected|private)?\s*interface\s+([A-Za-z_]\w*)', re.MULTILINE)
RE_METHOD = re.compile(r'\b(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?[A-Za-z_\<\>\[\],\s]+\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE)
RE_MONO = re.compile(r'class\s+([A-Za-z_]\w*)\s*:\s*MonoBehaviour\b')
RE_SCRIPTABLE = re.compile(r'class\s+([A-Za-z_]\w*)\s*:\s*ScriptableObject\b')

def is_script(rel: Path) -> bool:
    return rel.suffix and rel.suffix.lstrip(".").casefold() in SCRIPT_EXTS

def is_included_script(rel: Path) -> bool:
    # musí být skript dle přípony
    if not is_script(rel):
        return False
    # musí odpovídat základním „include“ globům
    if not match_any_glob(rel, SCRIPTS_INCLUDE_GLOBS):
        return False
    # obecné skriptové excludy
    if match_any_glob(rel, SCRIPTS_EXCLUDE_GLOBS):
        return False
    # pokud je vypnuté NOISY, odfiltruj shadery a spol.
    if not INCLUDE_NOISY and match_any_glob(rel, NOISY_EXTRA_EXCLUDE_GLOBS):
        return False
    return True

def analyze_script_text(text: str):
    lines = text.splitlines()
    return {
        "lines": len(lines),
        "classes": RE_CLASS.findall(text),
        "structs": RE_STRUCT.findall(text),
        "enums": RE_ENUM.findall(text),
        "interfaces": RE_INTERFACE.findall(text),
        "methods": RE_METHOD.findall(text),
        "is_mono": bool(RE_MONO.search(text)),
        "is_scriptable": bool(RE_SCRIPTABLE.search(text)),
    }

def code_snippet(text: str, head=30, tail=10):
    lines = text.splitlines()
    if len(lines) <= head + tail + 2:
        return "\n".join(lines) + ("\n" if not text.endswith("\n") else "")
    return "\n".join(
        lines[:head] + ["// …", f"// … {len(lines)-(head+tail)} lines omitted …", "// …"] + lines[-tail:]
    ) + "\n"

# ===================== RENDER SEKCÍ =====================

def write_tree_limited(root: Path, out, max_depth, files_per_dir):
    def list_entries(d: Path):
        try:
            ents = [e for e in d.iterdir() if not is_excluded(e.relative_to(root))]
        except Exception:
            return []
        ents.sort(key=lambda e: (e.is_file(), e.name.casefold()))
        return ents

    def rec(d: Path, prefix: str, depth: int):
        if depth > max_depth:
            return
        entries = list_entries(d)
        dirs = [e for e in entries if e.is_dir()]
        files = [e for e in entries if e.is_file()][:files_per_dir]
        leftover = max(0, len(entries) - (len(dirs) + len(files)))
        all_for_print = dirs + files
        total = len(all_for_print)
        for i, e in enumerate(all_for_print):
            connector = "└── " if i == total - 1 and leftover == 0 else "├── "
            out.write(f"{prefix}{connector}{e.name}\n")
            if e.is_dir():
                extension = "    " if (i == total - 1 and leftover == 0) else "│   "
                rec(e, prefix + extension, depth + 1)
        if leftover > 0:
            out.write(f"{prefix}└── … +{leftover} dalších položek\n")

    out.write(f"{root.name}\n")
    rec(root, "", 1)

def write_scripts_section(root: Path, out: BudgetWriter):
    out.write("# Skripty (souhrn + ukázky)\n")
    included = [p for p in iter_all_files(root) if is_included_script(p)]
    included.sort(key=lambda p: p.as_posix().casefold())

    out.write(f"Celkem nalezených skriptů (po filtrech): {len(included)}\n\n")

    summaries = []
    total_lines = 0
    for rel in included:
        abs_path = root / rel
        try:
            txt = abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            summaries.append((rel.as_posix(), {"error": str(e)}))
            continue
        info = analyze_script_text(txt)
        total_lines += info["lines"]
        summaries.append((rel.as_posix(), info))

    for path, info in summaries[:200]:
        if "error" in info:
            out.write(f"- {path} :: ERROR: {info['error']}\n")
            continue
        flags = []
        if info["is_mono"]: flags.append("MonoBehaviour")
        if info["is_scriptable"]: flags.append("ScriptableObject")
        out.write(
            f"- {path} :: lines={info['lines']}, "
            f"classes={len(info['classes'])}, methods~={len(info['methods'])}, "
            f"enums={len(info['enums'])}, interfaces={len(info['interfaces'])}"
            + (f", {'/'.join(flags)}" if flags else "")
            + "\n"
        )
        if not out.has_budget(): break

    out.write(f"\nSouhrn řádků ve skriptech: ~{total_lines}\n\n")

    out.write("## Ukázky kódu (head/tail)\n")
    shown = 0
    for rel, info in summaries:
        if shown >= MAX_SNIPPETS or not out.has_budget():
            break
        abs_path = root / rel
        try:
            size = abs_path.stat().st_size
        except:
            size = None
        if size is None:
            continue
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except:
            continue

        # Plný výpis pro malé soubory, jinak snippet
        if size <= FULL_FILE_IF_UNDER_BYTES:
            body = text if text.endswith("\n") else text + "\n"
        elif size <= MAX_SCRIPT_BYTES:
            body = code_snippet(text, MAX_SNIPPET_HEAD, MAX_SNIPPET_TAIL)
        else:
            continue

        lang = Path(rel).suffix.lstrip(".") or ""
        header = f"### {rel}"
        if not write_code_block(out, lang, header, body):
            # fallback menší snippet, když se celý blok nevejde
            tiny = code_snippet(text, 20, 8)
            if not write_code_block(out, lang, header, tiny):
                break  # ani tiny se nevejde — končíme

        shown += 1

def write_yaml_assets_section(root: Path, out: BudgetWriter):
    out.write("## YAML Assets (.prefab/.unity/.anim/.controller/.asset/.mat)\n")
    assets = [p for p in iter_all_files(root) if is_included_asset(p)]
    assets.sort(key=lambda p: p.as_posix().casefold())
    for rel in assets:
        if not out.has_budget():
            break
        abs_path = root / rel
        try:
            txt = abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            out.write(f"- {rel.as_posix()} :: ERROR: {e}\n")
            continue

        # ukázka max ~400 řádků, ať je to čitelné
        lines = txt.splitlines()
        view = "\n".join(lines[:400]) + ("\n" if txt.endswith("\n") else "\n")
        header = f"### {rel.as_posix()}"
        if not write_code_block(out, "yaml", header, view):
            # ještě menší fallback
            tiny = "\n".join(lines[:120]) + "\n"
            if not write_code_block(out, "yaml", header, tiny):
                break

def sha1_of_paths(root: Path):
    h = hashlib.sha1()
    for rel in iter_all_files(root):
        h.update(rel.as_posix().encode("utf-8"))
        try:
            st = (root / rel).stat().st_size
        except:
            st = 0
        h.update(str(st).encode("ascii"))
    return h.hexdigest()

# ===================== MAIN =====================

def main():
    root = ROOT_DIR
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Chyba: '{root}' neexistuje nebo to není složka.")

    output = resolve_output_path(root)
    with output.open("w", encoding="utf-8", errors="replace") as f:
        out = BudgetWriter(f, MAX_TOTAL_LINES, MAX_TOTAL_CHARS)

        out.write("# Unified Project Dump (scripts-focused)\n")
        out.write(f"Kořenová složka: {root.resolve()}\n")
        out.write(f"Vygenerováno: {datetime.now().isoformat(timespec='seconds')}\n")
        out.write(f"Fingerprint (sha1 cest+velikostí): {sha1_of_paths(root)}\n\n")

        if INCLUDE_UNITY_VERSION:
            uv = read_unity_version(root) or "Neznámá"
            out.write("## Unity verze\n")
            out.write(uv + "\n\n")

        if INCLUDE_TREE:
            out.write("## Stromová hierarchie (limitovaná)\n")
            write_tree_limited(root, out, TREE_MAX_DEPTH, TREE_MAX_FILES_PER_DIR)
            out.write("\n")

        if INCLUDE_SCENES_LIST:
            out.write("## Scény (Assets)\n")
            sc = list_scenes(root)
            for s in sc[:100]:
                out.write(f"- {s}\n")
            if len(sc) > 100:
                out.write(f"- … +{len(sc)-100} dalších\n")
            out.write("\n")

        if INCLUDE_BUILD_SETTINGS:
            out.write("## Build Settings (EditorBuildSettings.asset)\n")
            bs = scenes_in_build(root)
            for i in bs[:100]:
                out.write(f"- {i.get('path','')}  enabled={i.get('enabled','')}\n")
            if len(bs) > 100:
                out.write(f"- … +{len(bs)-100} dalších\n")
            out.write("\n")

        if INCLUDE_ASSET_SUMMARY:
            out.write("## Souhrn assetů podle přípony\n")
            total, top = asset_extension_summary(root)
            out.write(f"Celkem souborů po filtrech: {total}\n")
            for ext, cnt in top:
                label = ext or "(bez přípony)"
                out.write(f"- {label}: {cnt}\n")
            out.write("\n")

        if INCLUDE_LARGEST_FILES:
            out.write("## Top největší soubory\n")
            for size, path in largest_files(root, 20):
                out.write(f"- {size:>10} B  {path}\n")
            out.write("\n")

        if INCLUDE_SCRIPTS:
            write_scripts_section(root, out)

        if INCLUDE_YAML_ASSETS and out.has_budget():
            write_yaml_assets_section(root, out)

        if not out.has_budget():
            out.write("\n[Poznámka] Výstup byl zkrácen (dosažen rozpočet).\n")

    print(f"Hotovo. Výstup zapsán do: {output.resolve()}")

if __name__ == "__main__":
    main()
