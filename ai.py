import ast
import os
from typing import Dict, List, Any

IGNORED_DIRS = {'.git', '.idea', '__pycache__', 'venv', 'env'}
IGNORED_FILES = {'.env', '.gitignore', 'README.md', 'test.py'}
OUTPUT_FILE = 'project_structure.txt'


def parse_file(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r', encoding='utf-8') as file:
        try:
            tree = ast.parse(file.read())
        except SyntaxError as e:
            print(f"Syntax error in file {file_path}: {e}")
            return {'file_path': file_path, 'error': str(e)}

    file_info = {
        'file_path': file_path,
        'classes': [],
        'functions': [],
        'imports': [],
        'global_vars': [],
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_info = {
                'name': node.name,
                'methods': [],
                'bases': [ast.unparse(base) for base in node.bases]
            }
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    class_info['methods'].append(parse_function(item))
            file_info['classes'].append(class_info)
        elif isinstance(node, ast.FunctionDef):
            file_info['functions'].append(parse_function(node))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            file_info['imports'].extend(parse_import(node))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    file_info['global_vars'].append(target.id)

    return file_info


def parse_function(node: ast.FunctionDef) -> Dict[str, Any]:
    return {
        'name': node.name,
        'arguments': [arg.arg for arg in node.args.args],
        'decorators': [ast.unparse(d) for d in node.decorator_list],
        'is_async': isinstance(node, ast.AsyncFunctionDef),
        'return_type': ast.unparse(node.returns) if node.returns else None,
    }


def parse_import(node: ast.Import | ast.ImportFrom) -> List[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    else:
        return [f"{node.module}.{alias.name}" for alias in node.names]


def scan_project(project_path: str) -> List[Dict[str, Any]]:
    project_info = []
    for item in os.listdir(project_path):
        item_path = os.path.join(project_path, item)
        if os.path.isdir(item_path):
            for file in os.listdir(item_path):
                if file.endswith('.py') and file not in IGNORED_FILES:
                    file_path = os.path.join(item_path, file)
                    rel_path = os.path.relpath(file_path, project_path)
                    file_info = parse_file(file_path)
                    file_info['file_path'] = rel_path
                    project_info.append(file_info)
    return project_info


def write_project_info(project_info: List[Dict[str, Any]], output_file: str):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("PyQT 6 version.")
        for file_info in project_info:
            f.write(f" {file_info['file_path']}:")

            if 'error' in file_info:
                f.write(f" Error: {file_info['error']}")
                continue

            if file_info['imports']:
                f.write(f" Imports: {', '.join(file_info['imports'])}")

            if file_info['global_vars']:
                f.write(f" Global vars: {', '.join(file_info['global_vars'])}")

            if file_info['classes']:
                for class_info in file_info['classes']:
                    f.write(f" Class: {class_info['name']}(bases: {', '.join(class_info['bases'])})")
                    for method in class_info['methods']:
                        decorators = f"@{' @'.join(method['decorators'])} " if method['decorators'] else ""
                        async_prefix = "async " if method['is_async'] else ""
                        return_type = f" -> {method['return_type']}" if method['return_type'] else ""
                        f.write(
                            f" - {decorators}{async_prefix}{method['name']}({', '.join(method['arguments'])}){return_type}")

            if file_info['functions']:
                for func in file_info['functions']:
                    decorators = f"@{' @'.join(func['decorators'])} " if func['decorators'] else ""
                    async_prefix = "async " if func['is_async'] else ""
                    return_type = f" -> {func['return_type']}" if func['return_type'] else ""
                    f.write(
                        f" Function: {decorators}{async_prefix}{func['name']}({', '.join(func['arguments'])}){return_type}")


def main():
    project_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    if not os.path.exists(project_path):
        print(f"Error: {project_path} does not exist.")
        return
    project_info = scan_project(project_path)
    write_project_info(project_info, OUTPUT_FILE)
    print(f"Project structure has been saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
