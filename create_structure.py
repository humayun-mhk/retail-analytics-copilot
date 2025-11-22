import os

# Folder + file structure
structure = {
    "agent": {
        "graph_hybrid.py": "",
        "dspy_signatures.py": "",
        "rag": {
            "retrieval.py": ""
        },
        "tools": {
            "sqlite_tool.py": ""
        }
    },
    "data": {
        "northwind.sqlite": ""   # leave empty; you can replace with real DB later
    },
    "docs": {
        "marketing_calendar.md": "",
        "kpi_definitions.md": "",
        "catalog.md": "",
        "product_policy.md": ""
    },
    "sample_questions_hybrid_eval.jsonl": "",
    "run_agent_hybrid.py": "",
    "requirements.txt": "",
    "README.md": ""
}


def create_structure(base_path, tree):
    for name, content in tree.items():
        full_path = os.path.join(base_path, name)

        # If content is a dict → folder
        if isinstance(content, dict):
            os.makedirs(full_path, exist_ok=True)
            create_structure(full_path, content)

        else:
            # Create empty file
            with open(full_path, "w", encoding="utf-8") as f:
                if isinstance(content, str):
                    f.write(content)
            print(f"Created file: {full_path}")


if __name__ == "__main__":
    project_root = "."   # already inside your_project/
    create_structure(project_root, structure)
    print("\nProject structure created successfully!")
