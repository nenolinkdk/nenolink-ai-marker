import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_window_sets_exact_title_after_customtkinter_initialization():
    tree = ast.parse((ROOT / "nenolink_ai_marker" / "app.py").read_text(encoding="utf-8"))
    app_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MarkerApp")
    init = next(node for node in app_class.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    calls = []
    for index, node in enumerate(init.body):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if isinstance(call.func, ast.Attribute):
            owner = call.func.value.id if isinstance(call.func.value, ast.Name) else None
            if isinstance(call.func.value, ast.Call) and isinstance(call.func.value.func, ast.Name):
                owner = f"{call.func.value.func.id}()"
            calls.append((index, owner, call.func.attr, call.args))

    super_init = next(index for index, owner, name, _args in calls if owner == "super()" and name == "__init__")
    title_call = next((index, args) for index, owner, name, args in calls if owner == "self" and name == "title")
    assert title_call[0] > super_init
    assert len(title_call[1]) == 1
    assert isinstance(title_call[1][0], ast.Constant)
    assert title_call[1][0].value == "Nenolink AI-marker"


def test_only_central_shell_initialization_writes_main_window_title():
    production = ROOT / "nenolink_ai_marker"
    title_writes = []
    for path in production.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            if "self.title(" in line or "wm_title(" in line:
                title_writes.append((path.name, line_number, line.strip()))
    assert len(title_writes) == 1
    assert title_writes[0][0] == "app.py"
    assert title_writes[0][2] == 'self.title("Nenolink AI-marker")'
