import os

def generate_codebase_file():
    with open('codebase.txt', 'w') as codebase_file:
        for root, dirs, files in os.walk('.'):
            # Skip __pycache__ directories
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            for file in files:
                file_path = os.path.join(root, file)
                # Write the file path as a header
                codebase_file.write(f"---- {file_path} ----\n")
                # Write the file content
                with open(file_path, 'r') as f:
                    codebase_file.write(f.read())
                # Separate files with a newline
                codebase_file.write("\n\n")

generate_codebase_file()
