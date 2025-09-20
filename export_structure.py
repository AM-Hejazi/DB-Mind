import os

# Directories to ignore in the output
IGNORED_DIRS = {'.git', '.venv', '__pycache__', '.idea', '.gradio'}

# File extensions to include (None = include all)
INCLUDE_EXTS = None  # or e.g., {'.py', '.txt'}

def should_include(file_or_dir):
    return file_or_dir not in IGNORED_DIRS

def export_structure(root_path='.', prefix=''):
    for item in sorted(os.listdir(root_path)):
        item_path = os.path.join(root_path, item)
        if os.path.isdir(item_path):
            if should_include(item):
                print(f"{prefix}├── {item}/")
                export_structure(item_path, prefix + "│   ")
        else:
            if INCLUDE_EXTS is None or os.path.splitext(item)[1] in INCLUDE_EXTS:
                print(f"{prefix}└── {item}")

if __name__ == "__main__":
    print("RAGMABOT/")
    export_structure(".")
