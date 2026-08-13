from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).parents[1] / "src" / "atlas"
WORKFLOW_ROOT = SOURCE_ROOT / "modules" / "workflows"
DOMAIN_PATH = WORKFLOW_ROOT / "domain" / "models.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "atlas.modules.approval",
    "atlas.modules.approvals",
    "atlas.modules.connectors",
    "atlas.modules.itsm",
    "atlas.modules.runbook",
    "atlas.modules.runbooks",
    "atlas.modules.workers",
    "subprocess",
)


def _sources() -> tuple[Path, ...]:
    result = tuple(sorted(WORKFLOW_ROOT.rglob("*.py")))
    assert result
    return result


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _forbidden_call(call: ast.Call) -> str | None:
    name = _name(call.func).lower()
    compact = name.replace("_", "")
    if name in {"os.system", "os.popen"} or name.startswith("subprocess."):
        return "shell execution"
    if "worker" in compact and "dispatch" in compact:
        return "worker dispatch"
    if "connector" in compact and any(word in compact for word in ("invoke", "execute")):
        return "connector invocation"
    if "approval" in compact and any(word in compact for word in ("create", "request")):
        return "approval creation"
    if "itsm" in compact and any(word in compact for word in ("create", "update", "mutate")):
        return "ITSM mutation"
    if "runbook" in compact and any(word in compact for word in ("invoke", "execute", "run")):
        return "runbook execution"
    if "infrastructure" in compact and any(
        word in compact for word in ("apply", "change", "execute", "mutate")
    ):
        return "infrastructure change"
    return None


@pytest.mark.parametrize("source_file", _sources(), ids=lambda path: path.name)
def test_orchestration_lease_paths_have_no_operational_dependency_or_call(
    source_file: Path,
) -> None:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    imports = (
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert not any(module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    lease_functions = (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(word in node.name.lower() for word in ("lease", "heartbeat"))
    )
    for function in lease_functions:
        for nested in ast.walk(function):
            if isinstance(nested, ast.Call):
                assert _forbidden_call(nested) is None, (
                    f"{source_file.name}:{function.name} contains {_forbidden_call(nested)}"
                )


def test_lease_foundation_does_not_expand_plan_state_or_execution_authority() -> None:
    tree = ast.parse(DOMAIN_PATH.read_text(encoding="utf-8"), filename=str(DOMAIN_PATH))
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    state = classes["WorkflowPlanState"]
    values = {
        node.value.value
        for node in state.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
    }
    assert values == {"planned", "cancelled"}

    authority = classes["WorkflowPlanAuthority"]
    defaults = [
        node.value.value
        for node in authority.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id.endswith("_authorized")
        and isinstance(node.value, ast.Constant)
    ]
    assert defaults
    assert all(value is False for value in defaults)
