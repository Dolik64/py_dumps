import os

# ==========================================
#              KONFIGURACE
# ==========================================

SOURCE_FOLDER = r"C:\Users\volny\source\repos\IUR_Task3_assignment_fixed"  # Tečka = aktuální složka. Můžete změnit na absolutní cestu.
OUTPUT_FILENAME = "wpf_project_dump_clean.txt"

# 1. HLAVNÍ FILTR SLOŽEK: Tyto složky skript úplně ignoruje a ani do nich nevstupuje.
IGNORE_DIRS = {
    'bin', 'obj',           # Build artifacty (největší zdroj balastu)
    '.git', '.vs', '.idea', # Verzovací a IDE složky
    'packages', '.nuget',   # Stažené balíčky
    'venv', '__pycache__'   # Pythoní věci (pro jistotu)
}

# 2. WHITELIST PŘÍPON: Skript vypíše obsah POUZE souborů s těmito příponami.
ALLOWED_EXTENSIONS = {
    '.cs',      # C# kód (logika)
    '.xaml',    # UI definice (design)
    '.csproj',  # Definice projektu (závislosti)
    '.sln',     # Řešení (struktura)
    '.config',  # App.config
    '.md'       # Readme
}

# 3. FILTR GENERKOVANÝCH SOUBORŮ: I když má soubor příponu .cs, ignorujeme ho, pokud:
IGNORE_FILES_SUFFIX = (
    '.g.cs',       # Generated code
    '.g.i.cs',     # Generated intermediate code
    '.designer.cs',# Často generovaný kód formulářů (pokud chcete vidět i WinForms designer, smažte tento řádek)
    'AssemblyAttributes.cs',
    'AssemblyInfo.cs' # Často jen metadata, pokud je chcete vidět, smažte tento řádek
)

# ==========================================
#              LOGIKA SKRIPTU
# ==========================================

def should_process_file(filename):
    """Rozhodne, zda je soubor důležitý pro výpis."""
    # 1. Kontrola přípony
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False
    
    # 2. Kontrola, zda nejde o generovaný balast (obsahuje .g.cs atd.)
    if filename.endswith(IGNORE_FILES_SUFFIX):
        return False

    # 3. Ignorovat samotný výstupní soubor
    if filename == OUTPUT_FILENAME:
        return False
        
    return True

def generate_tree(start_path, output_file):
    """Vykreslí strom, ale vynechá ignorované složky."""
    output_file.write("="*60 + "\n")
    output_file.write(f"STRUKTURA PROJEKTU (Bez bin/obj a balastu)\n")
    output_file.write("="*60 + "\n\n")

    for root, dirs, files in os.walk(start_path):
        # Modifikace seznamu 'dirs' in-place, aby os.walk nelezl do ignorovaných složek
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        level = root.replace(start_path, '').count(os.sep)
        indent = ' ' * 4 * (level)
        output_file.write(f"{indent}[{os.path.basename(root)}/]\n")
        
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if should_process_file(f):
                output_file.write(f"{subindent}{f}\n")
    
    output_file.write("\n" + "="*60 + "\n\n")

def dump_contents(start_path, output_file):
    """Vypíše obsah pouze povolených souborů."""
    output_file.write("OBSAH ZDROJOVÝCH KÓDŮ:\n\n")
    
    files_processed_count = 0

    for root, dirs, files in os.walk(start_path):
        # Důležité: Zamezí vstupu do bin/obj i v této fázi
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in files:
            if not should_process_file(filename):
                continue

            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, start_path)
            
            files_processed_count += 1
            
            output_file.write("-" * 80 + "\n")
            output_file.write(f"SOUBOR: {relative_path}\n")
            output_file.write("-" * 80 + "\n")
            
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f: # utf-8-sig řeší BOM u VS souborů
                    output_file.write(f.read() + "\n\n")
            except Exception as e:
                output_file.write(f"[CHYBA ČTENÍ: {e}]\n\n")

    if files_processed_count == 0:
        output_file.write("Nebyly nalezeny žádné relevantní soubory (.cs, .xaml) ve zvolené složce.\n")

def main():
    output_path = os.path.join(SOURCE_FOLDER, OUTPUT_FILENAME)
    print(f"Skenuji složku: {os.path.abspath(SOURCE_FOLDER)}")
    print("Ignoruji složky: bin, obj, .git, .vs a generované soubory.")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            generate_tree(SOURCE_FOLDER, f)
            dump_contents(SOURCE_FOLDER, f)
            
        print(f"HOTOVO! Vyčištěný dump uložen do: {output_path}")
    except Exception as e:
        print(f"Kritická chyba: {e}")

if __name__ == "__main__":
    main()