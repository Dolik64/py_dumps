from pathlib import Path
import zipfile, io, re

AAR = Path(r"C:/Users/volny/AndroidStudioProjects/Kniha_20/app/libs/pagecurl-release.aar")

with zipfile.ZipFile(AAR, "r") as aar:
    cj = aar.read("classes.jar")
    z = zipfile.ZipFile(io.BytesIO(cj), "r")
    classes = [n for n in z.namelist() if n.endswith(".class") and n.startswith("eu/wewox/pagecurl")]
    print("== TŘÍDY V balíčku eu.wewox.pagecurl ==")
    for n in sorted(classes):
        print(n.replace("/", "."))
    print("\n== Souborové Kt třídy (top-level funkce) ==")
    kt = [c for c in classes if c.endswith("Kt.class")]
    for n in sorted(kt):
        print(n.replace("/", "."))
    print("\n== Hledám řetězce 'next' a 'previous' v bytekódu ==")
    hits = {}
    for n in classes:
        b = z.read(n)
        found = []
        if b"next" in b: found.append("next")
        if b"previous" in b: found.append("previous")
        if found:
            hits[n] = found
    for n, f in hits.items():
        print(f"{n.replace('/', '.')} -> {', '.join(f)}")
