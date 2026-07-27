import os
import ast

BASE_DIR = r"C:\Dev Projects 2026 Local\GIT\ai_qa_framework"


def extract_methods_from_node(node_body):
    """Helper to extract method names and signatures from an AST class or module body."""
    methods = []
    for item in node_body:
        if isinstance(item, ast.FunctionDef):
            args = [arg.arg for arg in item.args.args if arg.arg != "self"]
            methods.append(f"{item.name}({', '.join(args)})")
    return methods


def generate_pom_manifest():
    """
    UNBIASED CODEBASE GROUNDING HOOK:
    Parses pages, base structures, and utilities to expose a complete map
    of classes, locators, custom methods, and inherited capabilities.
    """
    pages_dir = os.path.join(BASE_DIR, "src", "pages")
    utils_dir = os.path.join(BASE_DIR, "src", "utils")

    manifest = {
        "infrastructure": {},
        "page_objects": {},
        "utilities": {}
    }

    # 1. Map Global Utilities if the directory exists
    if os.path.exists(utils_dir):
        for file in os.listdir(utils_dir):
            if file.endswith(".py") and file != "__init__.py":
                file_path = os.path.join(utils_dir, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        node = ast.parse(f.read(), filename=file)
                        manifest["utilities"][file] = extract_methods_from_node(node.body)
                    except SyntaxError:
                        continue

    # 2. Map Page Objects and Core Infrastructure
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
                    methods = extract_methods_from_node(item.body)
                    locators = []

                    # Parse out current string selectors inside __init__
                    for sub_item in item.body:
                        if isinstance(sub_item, ast.FunctionDef) and sub_item.name == "__init__":
                            for assign in sub_item.body:
                                if isinstance(assign, ast.Assign):
                                    for target in assign.targets:
                                        if isinstance(target, ast.Attribute) and isinstance(target.value,
                                                                                            ast.Name) and target.value.id == "self":
                                            locators.append(target.attr)

                    # Categorize base infrastructure vs domain pages
                    category = "infrastructure" if class_name in ["BasePage", "LoginPage"] else "page_objects"

                    manifest[category][class_name] = {
                        "file_path": f"src/pages/{file}",
                        "base_classes": [base.id for base in item.bases if isinstance(base, ast.Name)],
                        "locators": locators,
                        "methods": methods
                    }

    return manifest
