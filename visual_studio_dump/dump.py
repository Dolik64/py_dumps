import os

# ==========================================
#              KONFIGURACE (MAKRA)
# ==========================================

# Cesta ke složce, kterou chcete skenovat. 
# Můžete použít absolutní cestu (např. r"C:\Projekty\MujWeb") 
# nebo tečku r"." pro aktuální složku, kde leží tento skript.
SOURCE_FOLDER = r"C:\Users\volny\source\repos\IUR_Task3_assignment_fixed" 

# Název výstupního souboru, který se vytvoří
OUTPUT_FILENAME = "project_dump.txt"

# Seznam složek, které má skript ignorovat (aby se nevypisoval git, venv atd.)
IGNORE_DIRS = {'.git', '__pycache__', 'venv', 'env', 'node_modules', '.idea', '.vscode'}

# Seznam souborů, které ignorovat (včetně samotného výstupu, aby se nezacyklil)
IGNORE_FILES = {OUTPUT_FILENAME, '.DS_Store'}

# Přípony souborů, které chceme číst (necháme prázdné pro "všechny textové", 
# nebo např. {'.py', '.js', '.html'} pro specifické)
ALLOWED_EXTENSIONS = set() 

# ==========================================
#              LOGIKA SKRIPTU
# ==========================================

def is_text_file(file_path):
    """Zkusí přečíst začátek souboru, aby zjistil, zda jde o text nebo binárku."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)
            return True
    except (UnicodeDecodeError, IOError):
        return False

def generate_tree(start_path, output_file):
    """Zapíše vizuální stromovou strukturu do souboru."""
    output_file.write("="*50 + "\n")
    output_file.write(f"STRUKTURA ADRESÁŘE: {os.path.abspath(start_path)}\n")
    output_file.write("="*50 + "\n\n")

    for root, dirs, files in os.walk(start_path):
        # Filtrace ignorovaných složek
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        level = root.replace(start_path, '').count(os.sep)
        indent = ' ' * 4 * (level)
        output_file.write(f"{indent}[{os.path.basename(root)}/]\n")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if f not in IGNORE_FILES:
                output_file.write(f"{subindent}{f}\n")
    
    output_file.write("\n" + "="*50 + "\n\n")

def dump_contents(start_path, output_file):
    """Projiteruje soubory a vypíše jejich obsah."""
    output_file.write("OBSAH SOUBORŮ:\n\n")
    
    for root, dirs, files in os.walk(start_path):
        # Filtrace ignorovaných složek
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in files:
            if filename in IGNORE_FILES:
                continue

            # Kontrola přípony (pokud je definována)
            if ALLOWED_EXTENSIONS:
                _, ext = os.path.splitext(filename)
                if ext not in ALLOWED_EXTENSIONS:
                    continue

            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, start_path)

            # Zápis obsahu
            if is_text_file(file_path):
                output_file.write("-" * 80 + "\n")
                output_file.write(f"SOUBOR: {relative_path}\n")
                output_file.write("-" * 80 + "\n")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        output_file.write(content + "\n\n")
                except Exception as e:
                    output_file.write(f"[CHYBA PŘI ČTENÍ SOUBORU: {e}]\n\n")
            else:
                # Pokud je to binární soubor (obrázek, exe), jen ho zmíníme
                output_file.write(f"SOUBOR: {relative_path} (BINÁRNÍ - OBSAH VYNECHÁN)\n\n")

def main():
    # Absolutní cesta k výstupnímu souboru
    output_path = os.path.join(SOURCE_FOLDER, OUTPUT_FILENAME)
    
    print(f"Zahajuji dump složky: {os.path.abspath(SOURCE_FOLDER)}")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # 1. Krok: Vykreslení hierarchie
            generate_tree(SOURCE_FOLDER, f)
            
            # 2. Krok: Dump obsahu souborů
            dump_contents(SOURCE_FOLDER, f)
            
        print(f"HOTOVO! Výstup byl uložen do: {output_path}")
    except Exception as e:
        print(f"Došlo k chybě: {e}")

if __name__ == "__main__":
    main()