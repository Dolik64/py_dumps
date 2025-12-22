import os

# ==========================================
#              CONFIGURATION
# ==========================================

SOURCE_FOLDER = r"C:\Users\volny\Desktop\skola\5 semestr\IUR\semestralka\app"

# Output directory setting.
# If left empty "", the file is saved directly inside SOURCE_FOLDER.
# If a path is provided, the file is saved there (folder is created if it doesn't exist).
OUTPUT_FOLDER = r"C:\Users\volny\Desktop\skola\5 semestr\IUR\semestralka\dumps"

OUTPUT_FILENAME = "wpf_project_dump_clean.txt"

# 1. DIRECTORY FILTER: These folders are completely ignored.
IGNORE_DIRS = {
    'bin', 'obj',           # Build artifacts (major source of clutter)
    '.git', '.vs', '.idea', # Version control and IDE folders
    'packages', '.nuget',   # Downloaded packages
    'venv', '__pycache__'   # Python artifacts (just in case)
}

# 2. EXTENSION WHITELIST: Only files with these extensions are processed.
ALLOWED_EXTENSIONS = {
    '.cs',      # C# code (logic)
    '.xaml',    # UI definitions (design)
    '.csproj',  # Project definitions
    '.sln',     # Solution file
    '.config',  # App.config
    '.md'       # Readme
}

# 3. GENERATED FILES FILTER: Even if it has .cs, ignore if it ends with:
IGNORE_FILES_SUFFIX = (
    '.g.cs',       # Generated code
    '.g.i.cs',     # Generated intermediate code
    '.designer.cs',# Windows Forms designer code
    'AssemblyAttributes.cs',
    'AssemblyInfo.cs'
)

# ==========================================
#              SCRIPT LOGIC
# ==========================================

def should_process_file(filename):
    """Decides whether the file is relevant for the dump."""
    # 1. Check extension
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False
    
    # 2. Check for generated file suffixes
    if filename.endswith(IGNORE_FILES_SUFFIX):
        return False

    # 3. Ignore the output file itself
    if filename == OUTPUT_FILENAME:
        return False
        
    return True

def generate_tree(start_path, output_file):
    """Writes the directory tree, skipping ignored folders."""
    output_file.write("="*60 + "\n")
    output_file.write(f"PROJECT STRUCTURE (Excluding bin/obj and artifacts)\n")
    output_file.write("="*60 + "\n\n")

    for root, dirs, files in os.walk(start_path):
        # Modify 'dirs' in-place so os.walk doesn't enter ignored directories
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
    """Dumps the content of allowed files only."""
    output_file.write("SOURCE CODE CONTENTS:\n\n")
    
    files_processed_count = 0

    for root, dirs, files in os.walk(start_path):
        # Prevent entering ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in files:
            if not should_process_file(filename):
                continue

            file_path = os.path.join(root, filename)
            # Relative path is calculated from SOURCE_FOLDER for readability
            relative_path = os.path.relpath(file_path, start_path)
            
            files_processed_count += 1
            
            output_file.write("-" * 80 + "\n")
            output_file.write(f"FILE: {relative_path}\n")
            output_file.write("-" * 80 + "\n")
            
            try:
                # utf-8-sig handles the BOM often found in Visual Studio files
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    output_file.write(f.read() + "\n\n")
            except Exception as e:
                output_file.write(f"[READ ERROR: {e}]\n\n")

    if files_processed_count == 0:
        output_file.write("No relevant files (.cs, .xaml) found in the selected folder.\n")

def main():
    # Determine the final output directory
    final_output_dir = OUTPUT_FOLDER if OUTPUT_FOLDER else SOURCE_FOLDER

    # Try to create the directory if it doesn't exist
    if final_output_dir and not os.path.exists(final_output_dir):
        try:
            os.makedirs(final_output_dir)
            print(f"Created output directory: {final_output_dir}")
        except Exception as e:
            print(f"Critical Error: Cannot create directory '{final_output_dir}'.\n{e}")
            return

    output_path = os.path.join(final_output_dir, OUTPUT_FILENAME)

    print(f"Scanning folder: {os.path.abspath(SOURCE_FOLDER)}")
    print(f"Ignoring folders: {', '.join(IGNORE_DIRS)}")
    print(f"Target file: {output_path}")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            generate_tree(SOURCE_FOLDER, f)
            dump_contents(SOURCE_FOLDER, f)
            
        print(f"DONE! Clean dump saved successfully.")
    except Exception as e:
        print(f"Critical error while writing file: {e}")

if __name__ == "__main__":
    main()