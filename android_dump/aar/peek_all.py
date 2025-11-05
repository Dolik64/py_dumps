#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kompletní peek AAR:
- SHA256 a MD5
- Seznam položek v AAR (velikost, komprese)
- Pokud je v AAR classes.jar, vypíše kompletní obsah JARu
- Všechny .class rozparsuje přímo v Pythonu (bez javap):
  - jméno třídy, přístupové příznaky, parent, rozhraní
  - pole s příznaky a deskriptorem
  - metody s příznaky a deskriptorem
- Na začátku vygeneruje přehled veřejného API
Poznámka: JVM deskriptory tisknu surově. Je to přesné a nezávislé.
"""

import sys
import os
import io
import zipfile
import hashlib
from datetime import datetime
from typing import List, Dict, Any
import struct
from glob import glob

# =========================
# CONFIG  nastavení v kódu
# =========================
# a) Zadej konkrétní soubory AAR sem, nebo nech prázdné pro autodetekci přes AAR_GLOB
# a) pokud zadáš explicitní soubor sem, GLOB se ignoruje
AAR_PATHS: list[str] = [
    r"C:\Users\volny\AndroidStudioProjects\Kniha_20\app\libs\pagecurl-release.aar"
]

# b) GLOB se použije jen když AAR_PATHS necháš prázdné
AAR_GLOB: str = r"C:\Users\volny\AndroidStudioProjects\Kniha_20\app\libs\*.aar"

# c) výstupní adresář
OUTPUT_DIR: str = r"C:\Users\volny\AndroidStudioProjects\Kniha_20\app\libs"

# d) prefix názvu výstupního souboru
OUTPUT_PREFIX: str = "aar_dump_"

# e) Zapnout tisk jednotlivých sekcí
PRINT_CLASSES_JAR_LIST: bool = True
PRINT_PACKAGE_OVERVIEW: bool = True
PRINT_SYMBOL_SEARCH: bool = True
PRINT_PUBLIC_API: bool = True
PRINT_FULL_DETAIL: bool = True

# -------------------------
# Utility
# -------------------------
def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    s = float(n)
    for u in units:
        if s < 1024.0 or u == units[-1]:
            return f"{s:.1f} {u}"
        s /= 1024.0
    return f"{n} B"

def sha256_md5(path: str) -> tuple[str, str]:
    h1 = hashlib.sha256()
    h2 = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h1.update(chunk)
            h2.update(chunk)
    return h1.hexdigest(), h2.hexdigest()

# -------------------------
# ClassFile parser
# -------------------------
ACC_FLAGS = {
    "class": [
        (0x0001, "public"), (0x0010, "final"), (0x0020, "super"),
        (0x0200, "interface"), (0x0400, "abstract"),
        (0x1000, "synthetic"), (0x2000, "annotation"), (0x4000, "enum"),
        (0x8000, "module"),
    ],
    "field": [
        (0x0001, "public"), (0x0002, "private"), (0x0004, "protected"),
        (0x0008, "static"), (0x0010, "final"), (0x0040, "volatile"),
        (0x0080, "transient"), (0x1000, "synthetic"), (0x4000, "enum"),
    ],
    "method": [
        (0x0001, "public"), (0x0002, "private"), (0x0004, "protected"),
        (0x0008, "static"), (0x0010, "final"), (0x0020, "synchronized"),
        (0x0040, "bridge"), (0x0080, "varargs"), (0x0100, "native"),
        (0x0400, "abstract"), (0x0800, "strict"), (0x1000, "synthetic"),
    ],
}

def flags_to_str(kind: str, flags: int) -> str:
    out = [name for bit, name in ACC_FLAGS[kind] if flags & bit]
    return " ".join(out) if out else "package"

# Constant pool tags
CONSTANT_Utf8 = 1
CONSTANT_Integer = 3
CONSTANT_Float = 4
CONSTANT_Long = 5
CONSTANT_Double = 6
CONSTANT_Class = 7
CONSTANT_String = 8
CONSTANT_Fieldref = 9
CONSTANT_Methodref = 10
CONSTANT_InterfaceMethodref = 11
CONSTANT_NameAndType = 12
CONSTANT_MethodHandle = 15
CONSTANT_MethodType = 16
CONSTANT_Dynamic = 17
CONSTANT_InvokeDynamic = 18
CONSTANT_Module = 19
CONSTANT_Package = 20

class ClassFile:
    def __init__(self, data: bytes):
        self.data = data
        self.cp = [None]
        self.pos = 0
        self.this_class = None
        self.super_class = None
        self.access_flags = 0
        self.interfaces: List[int] = []
        self.fields: List[Dict[str, Any]] = []
        self.methods: List[Dict[str, Any]] = []
        self.parse()

    def u1(self):
        v = self.data[self.pos]
        self.pos += 1
        return v

    def u2(self):
        v = struct.unpack_from(">H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def u4(self):
        v = struct.unpack_from(">I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def read(self, n):
        b = self.data[self.pos:self.pos+n]
        self.pos += n
        return b

    def cp_utf8(self, idx):
        tag, val = self.cp[idx]
        if tag != CONSTANT_Utf8:
            return ""
        return val

    def cp_class_name(self, idx):
        tag, name_index = self.cp[idx]
        if tag != CONSTANT_Class:
            return ""
        return self.cp_utf8(name_index)

    def parse(self):
        magic = self.u4()
        if magic != 0xCAFEBABE:
            raise ValueError("Not a class file")
        _minor = self.u2()
        _major = self.u2()
        cp_count = self.u2()
        self.cp = [None] * cp_count
        i = 1
        while i < cp_count:
            tag = self.u1()
            if tag == CONSTANT_Utf8:
                ln = self.u2()
                s = self.read(ln).decode("utf-8", errors="replace")
                self.cp[i] = (tag, s)
            elif tag in (CONSTANT_Integer, CONSTANT_Float, CONSTANT_Fieldref, CONSTANT_Methodref,
                         CONSTANT_InterfaceMethodref, CONSTANT_NameAndType, CONSTANT_MethodType,
                         CONSTANT_Dynamic, CONSTANT_InvokeDynamic, CONSTANT_Module, CONSTANT_Package,
                         CONSTANT_String, CONSTANT_Class, CONSTANT_MethodHandle):
                if tag in (CONSTANT_Integer, CONSTANT_Float, CONSTANT_MethodType, CONSTANT_Package, CONSTANT_Module):
                    bcount = {CONSTANT_Integer:4, CONSTANT_Float:4, CONSTANT_MethodType:2,
                              CONSTANT_Package:2, CONSTANT_Module:2}[tag]
                    start = self.pos
                    self.read(bcount)
                    if tag in (CONSTANT_MethodType, CONSTANT_Package, CONSTANT_Module):
                        self.cp[i] = (tag, struct.unpack_from(">H", self.data, start)[0])
                    else:
                        self.cp[i] = (tag, None)
                elif tag in (CONSTANT_String, CONSTANT_Class, CONSTANT_MethodHandle):
                    if tag == CONSTANT_MethodHandle:
                        self.read(1)
                        idx = self.u2()
                        self.cp[i] = (tag, idx)
                    else:
                        idx = self.u2()
                        self.cp[i] = (tag, idx)
                else:
                    b = self.read(4)
                    a, b2 = struct.unpack(">HH", b)
                    self.cp[i] = (tag, (a, b2))
            elif tag in (CONSTANT_Long, CONSTANT_Double):
                self.read(8)
                self.cp[i] = (tag, None)
                i += 1
            else:
                raise ValueError(f"Unknown CP tag {tag}")
            i += 1

        self.access_flags = self.u2()
        self.this_class = self.u2()
        self.super_class = self.u2()

        ic = self.u2()
        self.interfaces = [self.u2() for _ in range(ic)]

        fc = self.u2()
        for _ in range(fc):
            f_flags = self.u2()
            f_name_idx = self.u2()
            f_desc_idx = self.u2()
            ac = self.u2()
            for __ in range(ac):
                _an = self.u2()
                _len = self.u4()
                self.read(_len)
            self.fields.append({
                "flags": f_flags,
                "name": self.cp_utf8(f_name_idx),
                "desc": self.cp_utf8(f_desc_idx),
            })

        mc = self.u2()
        for _ in range(mc):
            m_flags = self.u2()
            m_name_idx = self.u2()
            m_desc_idx = self.u2()
            ac = self.u2()
            for __ in range(ac):
                _an = self.u2()
                _len = self.u4()
                self.read(_len)
            self.methods.append({
                "flags": m_flags,
                "name": self.cp_utf8(m_name_idx),
                "desc": self.cp_utf8(m_desc_idx),
            })

    def fqcn(self) -> str:
        return self.cp_class_name(self.this_class).replace('/', '.')

    def super_name(self) -> str:
        if self.super_class == 0:
            return ""
        return self.cp_class_name(self.super_class).replace('/', '.')

    def interface_names(self) -> List[str]:
        return [self.cp_class_name(i).replace('/', '.') for i in self.interfaces]

# -------------------------
# AAR zpracování
# -------------------------
def dump_aar(aar_path: str, out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as out:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        out.write(f"== AAR DUMP ==\n")
        out.write(f"Soubor: {aar_path}\n")
        out.write(f"Čas: {now}\n")
        size = os.path.getsize(aar_path)
        out.write(f"Velikost: {human_size(size)} ({size} B)\n")
        sha256, md5 = sha256_md5(aar_path)
        out.write(f"SHA256: {sha256}\n")
        out.write(f"MD5:    {md5}\n\n")

        with zipfile.ZipFile(aar_path, "r") as z:
            out.write("== Obsah AAR ==\n")
            for zi in z.infolist():
                comp = "stored" if zi.compress_type == 0 else "deflated"
                out.write(f"{zi.filename}  {human_size(zi.file_size)}  comp={comp}\n")
            out.write("\n")

            if "classes.jar" not in z.namelist():
                out.write("classes.jar nenalezen v AAR. Končím.\n")
                return

            jar_bytes = z.read("classes.jar")
            with zipfile.ZipFile(io.BytesIO(jar_bytes), "r") as j:
                class_entries = [e for e in j.namelist() if e.endswith(".class")]

                if PRINT_CLASSES_JAR_LIST:
                    out.write("== classes.jar: seznam položek ==\n")
                    for name in j.namelist():
                        zi = j.getinfo(name)
                        comp = "stored" if zi.compress_type == 0 else "deflated"
                        out.write(f"{name}  {human_size(zi.file_size)}  comp={comp}\n")
                    out.write("\n")

                api: Dict[str, Any] = {}
                for ce in class_entries:
                    data = j.read(ce)
                    try:
                        cf = ClassFile(data)
                    except Exception as e:
                        out.write(f"[CHYBA] {ce}: {e}\n")
                        continue
                    cls_name = cf.fqcn()
                    api[cls_name] = {
                        "flags": cf.access_flags,
                        "flags_str": flags_to_str("class", cf.access_flags),
                        "super": cf.super_name(),
                        "ifaces": cf.interface_names(),
                        "fields": [{
                            "flags": f["flags"],
                            "flags_str": flags_to_str("field", f["flags"]),
                            "name": f["name"],
                            "desc": f["desc"],
                        } for f in cf.fields],
                        "methods": [{
                            "flags": m["flags"],
                            "flags_str": flags_to_str("method", m["flags"]),
                            "name": m["name"],
                            "desc": m["desc"],
                        } for m in cf.methods],
                    }

                packages: Dict[str, int] = {}
                for cls in api.keys():
                    pkg = ".".join(cls.split(".")[:-1])
                    packages[pkg] = packages.get(pkg, 0) + 1

                if PRINT_PACKAGE_OVERVIEW:
                    out.write("== Přehled balíčků ==\n")
                    for pkg, count in sorted(packages.items(), key=lambda x: (-x[1], x[0])):
                        out.write(f"{pkg or '<root>'}: {count} tříd\n")
                    out.write("\n")

                if PRINT_SYMBOL_SEARCH:
                    out.write("== Vyhledání symbolů 'next' a 'prev' ==\n")
                    for cls, info in sorted(api.items()):
                        names = {m["name"] for m in info["methods"]}
                        hit = []
                        if "next" in names:
                            hit.append("next")
                        if "prev" in names:
                            hit.append("prev")
                        if hit:
                            out.write(f"{cls}: {', '.join(hit)}\n")
                    out.write("\n")

                if PRINT_PUBLIC_API:
                    out.write("== Veřejné API (třídy a jejich public metody a pole) ==\n")
                    for cls, info in sorted(api.items()):
                        if "public" not in info["flags_str"]:
                            continue
                        out.write(f"[CLASS] {cls}  [{info['flags_str']}]\n")
                        if info["super"]:
                            out.write(f"  extends {info['super']}\n")
                        if info["ifaces"]:
                            out.write(f"  implements {', '.join(info['ifaces'])}\n")
                        for f in info["fields"]:
                            if "public" in f["flags_str"]:
                                out.write(f"  [FIELD] {f['flags_str']:>20}  {f['name']}  {f['desc']}\n")
                        for m in info["methods"]:
                            if "public" in m["flags_str"]:
                                out.write(f"  [METH ] {m['flags_str']:>20}  {m['name']}{m['desc']}\n")
                        out.write("\n")

                if PRINT_FULL_DETAIL:
                    out.write("== Kompletní detail všech tříd ==\n")
                    for cls, info in sorted(api.items()):
                        out.write(f"[CLASS] {cls}\n")
                        out.write(f"  FLAGS:   {info['flags_str']} ({hex(info['flags'])})\n")
                        out.write(f"  SUPER:   {info['super'] or '<none>'}\n")
                        out.write(f"  IFACES:  {', '.join(info['ifaces']) if info['ifaces'] else '<none>'}\n")
                        out.write("  FIELDS:\n")
                        if not info["fields"]:
                            out.write("    <none>\n")
                        else:
                            for f in info["fields"]:
                                out.write(f"    {f['flags_str']:>20}  {f['name']}  {f['desc']}\n")
                        out.write("  METHODS:\n")
                        if not info["methods"]:
                            out.write("    <none>\n")
                        else:
                            for m in info["methods"]:
                                out.write(f"    {m['flags_str']:>20}  {m['name']}{m['desc']}\n")
                        out.write("\n")

def resolve_input_paths() -> List[str]:
    # 1) pokud jsou v CONFIG explicitní cesty, použij je
    if AAR_PATHS:
        return [p for p in AAR_PATHS if os.path.isfile(p)]
    # 2) jinak vezmi z příkazové řádky pokud existují
    if len(sys.argv) > 1:
        return [p for p in sys.argv[1:] if os.path.isfile(p)]
    # 3) jinak autodetekce podle globu v aktuálním adresáři
    found = sorted(glob(AAR_GLOB))
    return [p for p in found if os.path.isfile(p)]

def main():
    paths = resolve_input_paths()
    if not paths:
        print("Nebyl nalezen žádný AAR. Nastav AAR_PATHS v CONFIG nebo vlož soubory podle AAR_GLOB.")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for aar_path in paths:
        base = os.path.basename(aar_path)
        name, _ = os.path.splitext(base)
        out_path = os.path.join(OUTPUT_DIR, f"{OUTPUT_PREFIX}{name}.txt")
        dump_aar(aar_path, out_path)
        print(f"Hotovo  uloženo do  {os.path.abspath(out_path)}")

if __name__ == "__main__":
    main()
