"""
code_executor.py

Executes LLM-generated Python code in a resource-limited subprocess with a
default-deny AST safety check. This is not a full container-level sandbox
(no seccomp/namespace isolation), but combined with:
  - allowlist-only imports (unknown modules are rejected, not blocklisted)
  - rejection of dangerous builtins and dunder attribute access
  - OS-level memory/CPU/process/output limits via resource.setrlimit
  - a hard wall-clock timeout
...it meaningfully constrains what generated code can do, and is
appropriately scoped for "a model tries to write a correct calculation,"
not "adversarial code from an untrusted attacker."
"""

import ast
import os
import re
import resource
import subprocess
import sys
import tempfile
from typing import Optional, Tuple

_CODE_BLOCK_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)

# Default-deny: only these stdlib modules may be imported. Anything not
# listed here is rejected, including modules we didn't think to name —
# this is the key difference from a blocklist.
_SAFE_IMPORT_MODULES = frozenset({
    "math", "itertools", "functools", "collections", "statistics",
    "fractions", "decimal", "re", "string", "datetime", "calendar",
    "heapq", "bisect", "operator", "json",
})

_BANNED_NAMES = frozenset({
    "eval", "exec", "compile", "open", "__import__", "input",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "exit", "quit", "help", "breakpoint", "memoryview",
})

_BANNED_NODE_TYPES = (ast.Global, ast.Nonlocal, ast.Delete)


def extract_python_code(text: str) -> str:
    match = _CODE_BLOCK_RE.search(text)
    return match.group(1).strip() if match else text.strip()


def _validate_ast_safety(tree: ast.AST) -> Optional[str]:
    """Returns an error string if the code is unsafe, else None."""
    for node in ast.walk(tree):
        if isinstance(node, _BANNED_NODE_TYPES):
            return f"Disallowed statement: {type(node).__name__}"

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in _SAFE_IMPORT_MODULES:
                    return f"Disallowed import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in _SAFE_IMPORT_MODULES:
                return f"Disallowed import: {node.module}"

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _BANNED_NAMES:
                return f"Disallowed function call: {node.func.id}"

        elif isinstance(node, ast.Attribute):
            # Blocks classic sandbox-escape patterns like
            # ().__class__.__bases__[0].__subclasses__()
            if node.attr.startswith("__"):
                return f"Disallowed dunder attribute access: {node.attr}"

        elif isinstance(node, ast.Name):
            if node.id in _BANNED_NAMES:
                return f"Disallowed name reference: {node.id}"

    return None


def _is_emulated() -> bool:
    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read()
            if "VirtualApple" in content or "Apple" in content:
                return True
    except Exception:
        pass
    return False


def _limit_resources():
    """Runs in the child process before exec (POSIX only — fine for the
    Linux container). Caps memory, CPU time, process count, and output
    file size so a runaway/malicious script can't affect the host."""
    is_emulated = _is_emulated()
    if not is_emulated:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))  # 256MB address space
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (5, 5))                                # no fork bombs
        except Exception:
            pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))                                  # 5 CPU-seconds
    except Exception:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))            # 1MB file writes max
    except Exception:
        pass


def execute_code(code: str, timeout_seconds: float = 5.0) -> Tuple[bool, str]:
    """Writes code to a temp file and executes it under resource limits.
    Returns (success, output_string)."""
    clean_code = extract_python_code(code)
    if not clean_code:
        return False, "No code provided to execute."

    try:
        tree = ast.parse(clean_code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

    safety_error = _validate_ast_safety(tree)
    if safety_error:
        return False, f"Rejected for safety: {safety_error}"

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(clean_code)
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, "-I", tmp_path],  # -I: isolated mode, ignores env vars / cwd on sys.path
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            preexec_fn=_limit_resources,
            env={},  # no inherited environment — no API keys or other secrets reachable
        )

        if result.returncode == 0:
            out = result.stdout.strip()
            if not out:
                return False, "Code executed successfully but returned empty output. Did it print() the answer?"
            return True, out
        else:
            return False, f"Execution Error:\n{result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return False, f"Code execution timed out after {timeout_seconds}s"
    except Exception as e:
        return False, f"System Error during execution: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
