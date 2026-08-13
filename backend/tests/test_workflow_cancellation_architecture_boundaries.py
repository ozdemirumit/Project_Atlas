from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).parents[1] / "src" / "atlas"
WORKFLOW_ROOT = SOURCE_ROOT / "modules" / "workflows"
APP_PATH = SOURCE_ROOT / "api" / "app.py"

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


def _python_sources() -> tuple[Path, ...]:
    sources = tuple(sorted(WORKFLOW_ROOT.rglob("*.py")))
    assert sources, "the workflow module must contain Python source files"
    return sources


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _imported_modules(tree: ast.AST) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def _prohibited_call(node: ast.Call) -> str | None:
    name = _qualified_name(node.func).lower()
    compact = name.replace("_", "")

    if name in {"os.system", "os.popen"} or name.startswith("subprocess."):
        return "shell execution"
    if "worker" in compact and "dispatch" in compact:
        return "worker dispatch"
    if "connector" in compact and any(
        verb in compact for verb in ("dispatch", "execute", "invoke")
    ):
        return "connector invocation"
    if "approval" in compact and any(verb in compact for verb in ("create", "issue", "request")):
        return "approval creation"
    if "itsm" in compact and any(
        verb in compact for verb in ("create", "delete", "mutate", "transition", "update")
    ):
        return "ITSM mutation"
    if "runbook" in compact and any(
        verb in compact for verb in ("dispatch", "execute", "invoke", "run")
    ):
        return "runbook execution"
    if "infrastructure" in compact and any(
        verb in compact for verb in ("apply", "change", "execute", "mutate")
    ):
        return "infrastructure change"
    return None


@pytest.mark.parametrize("source_file", _python_sources(), ids=lambda path: path.name)
def test_workflow_cancellation_has_no_operational_dependency_or_call(
    source_file: Path,
) -> None:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))

    for imported_module in _imported_modules(tree):
        assert not imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES), (
            f"{source_file.name} imports operational dependency {imported_module}"
        )

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if "cancel" not in node.name.lower():
            continue
        for nested in ast.walk(node):
            if not isinstance(nested, ast.Call):
                continue
            reason = _prohibited_call(nested)
            assert reason is None, f"{source_file.name}:{node.name} contains prohibited {reason}"


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    match = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name),
        None,
    )
    assert match is not None, f"workflow domain must define {name}"
    return match


def test_cancelled_plans_preserve_not_started_steps_and_false_authority() -> None:
    domain_path = WORKFLOW_ROOT / "domain" / "models.py"
    tree = ast.parse(domain_path.read_text(encoding="utf-8"), filename=str(domain_path))

    state_enum = _class(tree, "WorkflowPlanState")
    enum_values = {
        node.targets[0].id: node.value.value
        for node in state_enum.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert enum_values.get("CANCELLED") == "cancelled"

    step_model = _class(tree, "WorkflowPlanStep")
    step_defaults = [
        _qualified_name(node.value)
        for node in step_model.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "state"
        and node.value is not None
    ]
    assert step_defaults == ["WorkflowPlanStepState.NOT_STARTED"]

    authority_model = _class(tree, "WorkflowPlanAuthority")
    authority_defaults = [
        node.value.value
        for node in authority_model.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id.endswith("_authorized")
        and isinstance(node.value, ast.Constant)
    ]
    assert authority_defaults
    assert all(value is False for value in authority_defaults)

    cancellation_nodes = [
        node
        for source_file in _python_sources()
        for node in ast.walk(
            ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and "cancel" in node.name.lower()
    ]
    assert cancellation_nodes, "workflow cancellation must have an explicit transition path"
    for cancellation_node in cancellation_nodes:
        true_authority_assignments = [
            nested
            for nested in ast.walk(cancellation_node)
            if isinstance(nested, ast.keyword)
            and nested.arg is not None
            and nested.arg.endswith("_authorized")
            and isinstance(nested.value, ast.Constant)
            and nested.value.value is True
        ]
        assert not true_authority_assignments


def _is_production_expression(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Name) and node.id == "is_production":
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        nested = _is_production_expression(node.operand)
        return None if nested is None else not nested
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return None
    if _qualified_name(node.left) != "resolved_settings.environment":
        return None
    comparator = node.comparators[0]
    if not isinstance(comparator, ast.Constant) or comparator.value != "production":
        return None
    if isinstance(node.ops[0], ast.Eq):
        return True
    if isinstance(node.ops[0], ast.NotEq):
        return False
    return None


def _is_descendant(node: ast.AST, branch: ast.AST | list[ast.stmt]) -> bool:
    roots = branch if isinstance(branch, list) else [branch]
    return any(node is candidate for root in roots for candidate in ast.walk(root))


def _memory_call_is_nonproduction_guarded(
    call: ast.Call,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    current: ast.AST | None = call
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.IfExp):
            polarity = _is_production_expression(parent.test)
            if polarity is not None:
                in_body = _is_descendant(call, parent.body)
                return (polarity and not in_body) or (not polarity and in_body)
        elif isinstance(parent, ast.If):
            polarity = _is_production_expression(parent.test)
            if polarity is not None:
                in_body = _is_descendant(call, parent.body)
                in_else = _is_descendant(call, parent.orelse)
                return (polarity and in_else) or (not polarity and in_body)
        current = parent
    return False


def test_production_cancellation_wiring_cannot_fall_back_to_memory() -> None:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    repository_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and "workflow" in _qualified_name(node.func).lower()
        and "repository" in _qualified_name(node.func).lower()
    ]
    durable_calls = [
        call for call in repository_calls if "postgres" in _qualified_name(call.func).lower()
    ]
    memory_calls = [
        call for call in repository_calls if "memory" in _qualified_name(call.func).lower()
    ]

    assert durable_calls, "production workflow cancellation requires PostgreSQL persistence"
    assert memory_calls, "development workflow cancellation must use an explicitly labeled store"
    for call in memory_calls:
        assert _memory_call_is_nonproduction_guarded(call, parents), (
            f"{_qualified_name(call.func)} is not guarded by an explicit non-production branch"
        )
