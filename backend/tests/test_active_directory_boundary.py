from __future__ import annotations

import re
from pathlib import Path

SOURCE_ROOT = Path(__file__).parents[1] / "src" / "atlas" / "modules"


def test_connector_platform_registers_no_active_directory_or_ldap_mcp() -> None:
    connector_source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for module in ("connectors", "mcp_builder")
        for path in (SOURCE_ROOT / module).rglob("*.py")
    )
    prohibited_capabilities = (
        "active_directory_mcp",
        "active-directory-mcp",
        "ldap_mcp",
        "ldap-connector",
        "directory.write",
        "directory.manage",
    )
    assert all(item not in connector_source for item in prohibited_capabilities)


def test_directory_adapter_exposes_no_directory_write_operation() -> None:
    source = (SOURCE_ROOT / "identity" / "adapters" / "directory.py").read_text(encoding="utf-8")
    assert re.search(r"\bconnection\.(add|delete|modify|modify_dn)\s*\(", source) is None
    assert "modify_password" not in source
    assert "extend.microsoft" not in source


def test_ai_and_conversation_modules_do_not_import_raw_directory_adapter() -> None:
    for module in ("ai", "conversations"):
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in (SOURCE_ROOT / module).rglob("*.py")
        )
        assert "atlas.modules.identity.adapters.directory" not in source
