from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).parents[1] / "src" / "atlas"
APP_PATH = SOURCE_ROOT / "api" / "app.py"
WORKFLOW_ROOT_CANDIDATES = (
    SOURCE_ROOT / "modules" / "workflow",
    SOURCE_ROOT / "modules" / "workflows",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "atlas.modules.connectors",
    "atlas.modules.itsm",
    "atlas.modules.runbook",
    "subprocess",
)
FORBIDDEN_CAPABILITY_VALUES = frozenset({"C3", "C4", "C5"})


def _workflow_root() -> Path:
    existing = [candidate for candidate in WORKFLOW_ROOT_CANDIDATES if candidate.is_dir()]
    assert len(existing) == 1, (
        "exactly one workflow module must exist under atlas.modules as workflow or workflows"
    )
    return existing[0]


def _python_sources() -> tuple[Path, ...]:
    sources = tuple(sorted(_workflow_root().rglob("*.py")))
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


def _dangerous_call_reason(node: ast.Call) -> str | None:
    name = _qualified_name(node.func).lower()
    compact = name.replace("_", "")

    if name in {"os.system", "os.popen"} or name.startswith("subprocess."):
        return "shell execution"
    if any(
        keyword.arg == "shell"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in node.keywords
    ):
        return "shell execution"
    if "connector" in compact and any(
        verb in compact for verb in ("invoke", "invocation", "dispatch", "execute")
    ):
        return "connector invocation"
    if "itsm" in compact and any(
        verb in compact for verb in ("create", "update", "delete", "mutate", "close", "transition")
    ):
        return "ITSM mutation"
    if "runbook" in compact and any(
        verb in compact for verb in ("execute", "run", "invoke", "dispatch")
    ):
        return "runbook execution"
    return None


@pytest.mark.parametrize("source_file", _python_sources(), ids=lambda path: path.name)
def test_workflow_module_has_no_operational_execution_dependencies(source_file: Path) -> None:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))

    for imported_module in _imported_modules(tree):
        assert not imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES), (
            f"{source_file.name} imports operational dependency {imported_module}"
        )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        reason = _dangerous_call_reason(node)
        assert reason is None, f"{source_file.name} contains prohibited {reason} call"


@pytest.mark.parametrize("source_file", _python_sources(), ids=lambda path: path.name)
def test_workflow_module_exposes_only_c0_to_c2_capability_values(source_file: Path) -> None:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))

    string_values = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    attribute_values = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    assert string_values.isdisjoint(FORBIDDEN_CAPABILITY_VALUES)
    assert attribute_values.isdisjoint(FORBIDDEN_CAPABILITY_VALUES)


def _is_production_expression(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Name) and node.id == "is_production":
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        nested = _is_production_expression(node.operand)
        return None if nested is None else not nested
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return None

    left = _qualified_name(node.left)
    comparator = node.comparators[0]
    if left != "resolved_settings.environment":
        return None
    if not isinstance(comparator, ast.Constant) or comparator.value != "production":
        return None
    if isinstance(node.ops[0], ast.Eq):
        return True
    if isinstance(node.ops[0], ast.NotEq):
        return False
    return None


def _is_descendant(node: ast.AST, branch: ast.AST | list[ast.stmt]) -> bool:
    branch_nodes = branch if isinstance(branch, list) else [branch]
    return any(node is candidate for root in branch_nodes for candidate in ast.walk(root))


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


def test_production_app_wiring_cannot_silently_use_memory_for_workflows() -> None:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    repository_calls = [
        call
        for call in calls
        if "workflow" in _qualified_name(call.func).lower()
        and "repository" in _qualified_name(call.func).lower()
    ]
    durable_calls = [
        call for call in repository_calls if "postgres" in _qualified_name(call.func).lower()
    ]
    memory_calls = [
        call for call in repository_calls if "memory" in _qualified_name(call.func).lower()
    ]

    assert durable_calls, "production workflow wiring must include a PostgreSQL repository"
    assert memory_calls, "development workflow wiring must be explicitly labeled as memory-backed"
    for call in memory_calls:
        assert _memory_call_is_nonproduction_guarded(call, parents), (
            f"{_qualified_name(call.func)} is not guarded by an explicit non-production branch"
        )
