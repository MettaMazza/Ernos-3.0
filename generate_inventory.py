import os

def generate_inventory():
    base_dir = "/Users/mettamazza/Desktop/Ernos 3.0"
    target_dirs = ["src", "tests", "ErnosClaw", "visualiser", "scripts", "visualiser-deploy", "shared", "tools"]
    # Also include root level files
    
    exclude_dirs = {".venv", "__pycache__", "node_modules", ".git", ".pytest_cache", ".claude", "dummy_chrome_profile", "memory", "logs", ".voice_cache", "config"}
    exclude_exts = {".pyc", ".pyo", ".pyd", ".log", ".DS_Store", ".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".xml", ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg"}

    inventory = []

    # Process target directories
    for d in target_dirs:
        dir_path = os.path.join(base_dir, d)
        if not os.path.exists(dir_path):
            continue
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in exclude_exts and not file.startswith("."):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, base_dir)
                    inventory.append(rel_path)

    # Process root level files
    for root, dirs, files in os.walk(base_dir, topdown=True):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and d not in target_dirs]
        if root == base_dir:
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in exclude_exts and not file.startswith("."):
                    inventory.append(file)
        # Avoid traversing any deep nested generic root dirs if not needed, we already excluded targets

    inventory.sort()
    
    with open(os.path.join(base_dir, "audit_inventory.txt"), "w") as f:
        for item in inventory:
            f.write(f"{item}\n")
    
    print(f"Inventory saved: {len(inventory)} files found.")

if __name__ == "__main__":
    generate_inventory()
