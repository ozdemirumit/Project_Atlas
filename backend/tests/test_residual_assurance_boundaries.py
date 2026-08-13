from __future__ import annotations

import ast
from pathlib import Path

ROUTES_ROOT = Path(__file__).parents[1] / "src" / "atlas" / "api" / "routes"
MODULES_ROOT = Path(__file__).parents[1] / "src" / "atlas" / "modules"
LEGACY_APPLICATION_ROOTS = (
    MODULES_ROOT / "approvals" / "application",
    MODULES_ROOT / "change_review" / "application",
    MODULES_ROOT / "reports" / "application",
)


def test_routes_do_not_reference_removed_mfa_errors() -> None:
    offenders = [
        path.relative_to(ROUTES_ROOT).as_posix()
        for path in ROUTES_ROOT.rglob("*.py")
        if "mfa_required" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_legacy_application_assurance_sets_include_development() -> None:
    offenders: list[str] = []

    for root in LEGACY_APPLICATION_ROOTS:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Set, ast.List, ast.Tuple)):
                    continue
                values = {ast.unparse(element) for element in node.elts}
                if not values.intersection(
                    {
                        "AssuranceLevel.SINGLE_FACTOR",
                        "AssuranceLevel.MULTI_FACTOR",
                        "AssuranceLevel.HARDWARE_BACKED",
                        "'single_factor'",
                        "'multi_factor'",
                        "'hardware_backed'",
                        '"single_factor"',
                        '"multi_factor"',
                        '"hardware_backed"',
                    }
                ):
                    continue
                if not values.intersection(
                    {
                        "AssuranceLevel.DEVELOPMENT",
                        "'development'",
                        '"development"',
                    }
                ):
                    offenders.append(f"{path.relative_to(MODULES_ROOT).as_posix()}:{node.lineno}")

    assert offenders == []
