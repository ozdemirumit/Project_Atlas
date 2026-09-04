from __future__ import annotations

import pytest

from atlas.modules.mcp_plugin_sdk.domain.clients import (
    CliClientPolicy,
    FileClientPolicy,
    HttpClientPolicy,
    VendorSdkClientPolicy,
    cli_client_uses_shell_expansion,
)


def http_policy(**overrides: object) -> HttpClientPolicy:
    defaults: dict[str, object] = {
        "approved_base_endpoint": "https://api.example-storage.vendor.com",
        "certificate_validation_enabled": True,
        "target_allowlist": frozenset({"api.example-storage.vendor.com"}),
        "redirect_allowlist": frozenset(),
        "timeout_seconds": 10.0,
        "max_response_size_bytes": 5_000_000,
        "proxy_policy": "no_proxy",
        "safe_retry_methods": frozenset({"GET"}),
    }
    defaults.update(overrides)
    return HttpClientPolicy(**defaults)  # type: ignore[arg-type]


def test_http_policy_requires_certificate_validation() -> None:
    with pytest.raises(ValueError, match="certificate validation is required"):
        http_policy(certificate_validation_enabled=False)


def test_http_policy_rejects_unsafe_retry_methods() -> None:
    with pytest.raises(ValueError, match="restricted to safe methods"):
        http_policy(safe_retry_methods=frozenset({"POST"}))


def test_http_policy_accepts_valid_state() -> None:
    assert http_policy().timeout_seconds == 10.0


def vendor_sdk_policy(**overrides: object) -> VendorSdkClientPolicy:
    defaults: dict[str, object] = {
        "pinned_sdk_version": "3.2.1",
        "wraps_authentication": True,
        "wraps_timeout": True,
        "has_global_mutable_state": False,
    }
    defaults.update(overrides)
    return VendorSdkClientPolicy(**defaults)  # type: ignore[arg-type]


def test_vendor_sdk_policy_rejects_global_mutable_state() -> None:
    with pytest.raises(ValueError, match="no global mutable client state"):
        vendor_sdk_policy(has_global_mutable_state=True)


def test_vendor_sdk_policy_requires_wrapped_authentication() -> None:
    with pytest.raises(ValueError, match="authentication behavior must be wrapped"):
        vendor_sdk_policy(wraps_authentication=False)


def cli_policy(**overrides: object) -> CliClientPolicy:
    defaults: dict[str, object] = {
        "executable_identity": "vendor-cli",
        "required_version": "2.4.0",
        "allowlisted_subcommands": frozenset({"inventory", "status"}),
        "allowlisted_flags": frozenset({"--json"}),
        "working_directory": "/var/run/atlas/connector-sandboxes/example",
        "environment_allowlist": frozenset({"LANG"}),
        "max_output_bytes": 1_000_000,
        "max_duration_seconds": 30.0,
        "max_process_tree_size": 2,
        "locale": "C.UTF-8",
        "encoding": "utf-8",
        "exit_code_mapping_ids": ("exit-code-mapping.vendor-cli",),
    }
    defaults.update(overrides)
    return CliClientPolicy(**defaults)  # type: ignore[arg-type]


def test_cli_policy_requires_allowlisted_subcommands() -> None:
    with pytest.raises(ValueError, match="allowlisted subcommands"):
        cli_policy(allowlisted_subcommands=frozenset())


def test_cli_policy_requires_exit_code_mappings() -> None:
    with pytest.raises(ValueError, match="exit-code mappings"):
        cli_policy(exit_code_mapping_ids=())


def test_cli_client_never_uses_shell_expansion() -> None:
    assert cli_client_uses_shell_expansion() is False


def file_policy(**overrides: object) -> FileClientPolicy:
    defaults: dict[str, object] = {
        "approved_mount_root": "/var/run/atlas/connector-mounts/example",
        "allows_path_traversal": False,
        "allows_symlink_escape": False,
        "max_file_size_bytes": 10_000_000,
        "allowed_file_types": frozenset({"application/json"}),
        "read_only_default": True,
        "cleans_up_temporary_files": True,
    }
    defaults.update(overrides)
    return FileClientPolicy(**defaults)  # type: ignore[arg-type]


def test_file_policy_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="no path traversal"):
        file_policy(allows_path_traversal=True)


def test_file_policy_rejects_symlink_escape() -> None:
    with pytest.raises(ValueError, match="no symbolic-link escape"):
        file_policy(allows_symlink_escape=True)


def test_file_policy_accepts_valid_state() -> None:
    assert file_policy().read_only_default is True
