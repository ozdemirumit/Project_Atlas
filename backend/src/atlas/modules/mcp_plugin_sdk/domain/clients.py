"""ATLAS-021 SS15: safe target clients."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

_SAFE_HTTP_RETRY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class ClientKind(StrEnum):
    HTTP = "http"
    VENDOR_SDK = "vendor_sdk"
    CLI = "cli"
    FILE_AND_IMPORT = "file_and_import"


def cli_client_uses_shell_expansion() -> bool:
    """SS15.3: "argument arrays without shell expansion." Mirrors SS14's
    `HandlerRule.NEVER_CREATES_NESTED_SHELL_FOR_CLI_OPERATIONS`, applied to the client itself
    rather than the handler that calls it."""
    return False


@dataclass(frozen=True, slots=True)
class HttpClientPolicy:
    """SS15.1's declared elements."""

    approved_base_endpoint: str
    certificate_validation_enabled: bool
    target_allowlist: frozenset[str]
    redirect_allowlist: frozenset[str]
    timeout_seconds: float
    max_response_size_bytes: int
    proxy_policy: str
    safe_retry_methods: frozenset[str]

    def __post_init__(self) -> None:
        if not self.approved_base_endpoint.strip():
            raise ValueError("an HTTP client policy requires an approved base endpoint")
        if not self.certificate_validation_enabled:
            raise ValueError("SS15.1: certificate validation is required")
        if not self.target_allowlist:
            raise ValueError("an HTTP client policy requires a target allowlist")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_response_size_bytes < 1:
            raise ValueError("max_response_size_bytes must be positive")
        if not self.proxy_policy.strip():
            raise ValueError("an HTTP client policy requires a proxy policy")
        unsafe_methods = self.safe_retry_methods - _SAFE_HTTP_RETRY_METHODS
        if unsafe_methods:
            raise ValueError(
                "SS15.1: structured retry hooks are restricted to safe methods, got "
                f"{sorted(unsafe_methods)}"
            )


@dataclass(frozen=True, slots=True)
class VendorSdkClientPolicy:
    """SS15.2's declared elements."""

    pinned_sdk_version: str
    wraps_authentication: bool
    wraps_timeout: bool
    has_global_mutable_state: bool

    def __post_init__(self) -> None:
        if not self.pinned_sdk_version.strip():
            raise ValueError("a vendor SDK client policy requires a pinned SDK version")
        if not self.wraps_authentication:
            raise ValueError("SS15.2: authentication behavior must be wrapped")
        if not self.wraps_timeout:
            raise ValueError("SS15.2: timeout behavior must be wrapped")
        if self.has_global_mutable_state:
            raise ValueError("SS15.2: no global mutable client state across instances")


@dataclass(frozen=True, slots=True)
class CliClientPolicy:
    """SS15.3's declared elements."""

    executable_identity: str
    required_version: str
    allowlisted_subcommands: frozenset[str]
    allowlisted_flags: frozenset[str]
    working_directory: str
    environment_allowlist: frozenset[str]
    max_output_bytes: int
    max_duration_seconds: float
    max_process_tree_size: int
    locale: str
    encoding: str
    exit_code_mapping_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.executable_identity.strip():
            raise ValueError("a CLI client policy requires a fixed executable identity")
        if not self.required_version.strip():
            raise ValueError("a CLI client policy requires a required version")
        if not self.allowlisted_subcommands:
            raise ValueError("a CLI client policy requires allowlisted subcommands")
        if not self.working_directory.strip():
            raise ValueError("a CLI client policy requires a controlled working directory")
        if self.max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        if self.max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive")
        if self.max_process_tree_size < 1:
            raise ValueError("max_process_tree_size must be positive")
        if not self.locale.strip():
            raise ValueError("a CLI client policy requires a locale")
        if not self.encoding.strip():
            raise ValueError("a CLI client policy requires an encoding")
        if not self.exit_code_mapping_ids:
            raise ValueError("a CLI client policy requires exit-code mappings")


@dataclass(frozen=True, slots=True)
class FileClientPolicy:
    """SS15.4's declared elements. `allows_path_traversal`/`allows_symlink_escape` must be
    `False` to construct at all -- SS15.4's prohibitions as construction-time guarantees."""

    approved_mount_root: str
    allows_path_traversal: bool
    allows_symlink_escape: bool
    max_file_size_bytes: int
    allowed_file_types: frozenset[str]
    read_only_default: bool
    cleans_up_temporary_files: bool

    def __post_init__(self) -> None:
        if not self.approved_mount_root.strip():
            raise ValueError("a file client policy requires an approved mount root")
        if self.allows_path_traversal:
            raise ValueError("SS15.4: no path traversal")
        if self.allows_symlink_escape:
            raise ValueError("SS15.4: no symbolic-link escape")
        if self.max_file_size_bytes < 1:
            raise ValueError("max_file_size_bytes must be positive")
        if not self.allowed_file_types:
            raise ValueError("a file client policy requires allowed file types")
