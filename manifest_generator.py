import os
import ast

BASE_DIR = r"C:\Dev Projects 2026 Local\GIT\ai_qa_framework"


def generate_pom_manifest():
    """
    PROGRAMMATIC CODEBASE GROUNDING HOOK:
    Parses the pages directory to map out an absolute, non-hallucinated
    inventory of files, classes, locators, and method signatures.
    """
    pages_dir = os.path.join(BASE_DIR, "src", "pages")
    manifest = {}

    if not os.path.exists(pages_dir):
        return manifest

    for file in os.listdir(pages_dir):
        if file.endswith(".py") and file != "__init__.py":
            file_path = os.path.join(pages_dir, file)
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    node = ast.parse(f.read(), filename=file)
                except SyntaxError:
                    continue

            for item in node.body:
                if isinstance(item, ast.ClassDef):
                    class_name = item.name
                    methods = []
                    locators = []

                    for sub_item in item.body:
                        if isinstance(sub_item, ast.FunctionDef):
                            args = [arg.arg for arg in sub_item.args.args if arg.arg != "self"]
                            methods.append(f"{sub_item.name}({', '.join(args)})")

                        if isinstance(sub_item, ast.FunctionDef) and sub_item.name == "__init__":
                            for assign in sub_item.body:
                                if isinstance(assign, ast.Assign):
                                    for target in assign.targets:
                                        if isinstance(target, ast.Attribute) and isinstance(target.value,
                                                                                            ast.Name) and target.value.id == "self":
                                            locators.append(target.attr)

                    manifest[class_name] = {
                        "file_path": f"src/pages/{file}",
                        "locators": locators,
                        "methods": methods
                    }
    return manifest
