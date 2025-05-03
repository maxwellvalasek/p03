import os

def combine_code_files(output_filename="codebase.txt", root_dir="."):
    """
    Combines all Python code files (.py) in the specified directory and its
    subdirectories into a single text file, excluding __pycache__ directories.

    Args:
        output_filename (str): The name of the file to save the combined code.
        root_dir (str): The root directory to start searching from.
    """
    combined_code = []
    separator_template = "==== {file_path} ====\n"

    print(f"Starting code combination from root directory: {os.path.abspath(root_dir)}")
    found_files_count = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # --- Exclude __pycache__ directories ---
        # Method 1: Skip processing if the current dirpath is __pycache__ or inside one
        if "__pycache__" in dirpath.split(os.sep):
            continue
        # Method 2: Modify dirnames in-place to prevent os.walk from descending into __pycache__
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        # --- ---

        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                # Use relative path in the separator for better readability
                relative_path = os.path.relpath(file_path, root_dir)
                print(f"Processing: {relative_path}")
                try:
                    # Use utf-8 encoding, but ignore errors for potentially mixed encodings
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                        content = infile.read()
                        combined_code.append(separator_template.format(file_path=relative_path))
                        combined_code.append(content)
                        # Add a couple of newlines for separation between file contents
                        combined_code.append("\n\n")
                        found_files_count += 1
                except Exception as e:
                    print(f"  Error reading file {file_path}: {e}")

    if not combined_code:
        print("No Python files found (excluding __pycache__).")
        return

    try:
        output_path = os.path.join(root_dir, output_filename) # Save in the root dir
        with open(output_path, 'w', encoding='utf-8') as outfile:
            outfile.write("".join(combined_code))
        print(f"\nSuccessfully combined {found_files_count} Python files into {output_path}")
    except Exception as e:
        print(f"\nError writing to output file {output_path}: {e}")

# --- Script Execution ---
if __name__ == "__main__":
    # You can change the root directory if needed, e.g., combine_code_files(root_dir="../project_folder")
    combine_code_files(output_filename="codebase.txt", root_dir=".")
