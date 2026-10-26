"""Static preflight for SkillSwap: checks frontend files and API route alignment.
Run from the backend directory: python3 check_setup.py
This does not modify files or connect to Oracle.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
FRONTEND = ROOT / "frontend"
REQUIRED_FILES = (FRONTEND / "index.html", FRONTEND / "style.css", FRONTEND / "app.js")
REQUIRED_ROUTES = {
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("GET", "/api/health"),
    ("GET", "/api/categories"),
    ("GET", "/api/skills"),
    ("GET", "/api/offerings"),
    ("GET", "/api/requests"),
    ("GET", "/api/dashboard"),
    ("GET", "/api/my/offerings"), ("POST", "/api/my/offerings"),
    ("DELETE", "/api/my/offerings/<int:offering_id>"),
    ("GET", "/api/my/requests"), ("POST", "/api/my/requests"),
    ("DELETE", "/api/my/requests/<int:request_id>"),
    ("GET", "/api/my/matches"), ("GET", "/api/match-suggestions"),
    ("POST", "/api/matches"), ("PUT", "/api/matches/<int:match_id>/status"),
    ("GET", "/api/my/sessions"), ("POST", "/api/my/sessions"),
    ("PUT", "/api/my/sessions/<int:session_id>/status"),
    ("GET", "/api/my/reviews"), ("POST", "/api/my/reviews"),
    ("GET", "/api/my/profile"), ("PATCH", "/api/my/profile"),
    ("PUT", "/api/my/preferences"),
    ("GET", "/api/my/availability"), ("POST", "/api/my/availability"),
    ("DELETE", "/api/my/availability/<int:availability_id>"),
    ("GET", "/api/users/<int:user_id>/rating"),
}

errors = []
if not APP.is_file():
    errors.append("Missing app.py")
else:
    source = APP.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(APP))
    except SyntaxError as exc:
        errors.append(f"Python syntax error at line {exc.lineno}: {exc.msg}")
    routes = set()
    try:
        tree = ast.parse(source, filename=str(APP))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                    continue
                if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "app":
                    continue
                method = dec.func.attr.upper()
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "ROUTE"}:
                    continue
                if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                    route = dec.args[0].value
                    if method == "ROUTE":
                        methods = {"GET"}
                        for kw in dec.keywords:
                            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
                                methods = {x.value.upper() for x in kw.value.elts if isinstance(x, ast.Constant) and isinstance(x.value, str)}
                        routes.update((m, route) for m in methods)
                    else:
                        routes.add((method, route))
    except Exception as exc:
        errors.append(f"Could not inspect Flask routes: {exc}")
    for method, route in sorted(REQUIRED_ROUTES - routes):
        errors.append(f"Missing backend route: {method} {route}")

for file in REQUIRED_FILES:
    if not file.is_file():
        errors.append(f"Missing frontend file: {file.relative_to(ROOT)}")

if REQUIRED_FILES[0].is_file():
    html = REQUIRED_FILES[0].read_text(encoding="utf-8")
    if '/style.css' not in html:
        errors.append("index.html does not link /style.css")
    if '/app.js' not in html:
        errors.append("index.html does not load /app.js")

if errors:
    print("SKILLSWAP PREFLIGHT: FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("SKILLSWAP PREFLIGHT: PASSED")
print(f" - Backend Python syntax: OK")
print(f" - Required API routes: {len(REQUIRED_ROUTES)} checked")
print(" - Frontend index.html, style.css, app.js: present")
print(" - Frontend asset links: OK")
print("Note: this static check does not test Oracle credentials, live SQL, or browser flows.")
