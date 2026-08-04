from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class DirectoryEndpoint:
    endpoint_id: str
    uri: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.endpoint_id, "endpoint_id")
        parsed = urlparse(self.uri)
        if parsed.scheme != "ldaps" or not parsed.hostname:
            raise ValueError("directory endpoints must use ldaps with a hostname")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("directory endpoint URI contains unsupported components")
        if parsed.path not in {"", "/"}:
            raise ValueError("directory endpoint URI must not contain a path")
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("directory endpoint port is invalid")

    @property
    def hostname(self) -> str:
        parsed = urlparse(self.uri)
        assert parsed.hostname is not None
        return parsed.hostname

    @property
    def port(self) -> int:
        return urlparse(self.uri).port or 636


@dataclass(frozen=True, slots=True)
class DirectoryGroupMapping:
    directory_group: str = field(repr=False)
    atlas_group_id: str = ""
    role_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.directory_group.strip() or any(
            ord(character) < 32 for character in self.directory_group
        ):
            raise ValueError("directory group mapping key is invalid")
        validate_stable_identifier(self.atlas_group_id, "atlas_group_id")
        if not self.role_ids:
            raise ValueError("directory group mapping must declare at least one role")
        for role_id in self.role_ids:
            validate_stable_identifier(role_id, "role_id")


@dataclass(frozen=True, slots=True)
class DirectoryProviderProfile:
    provider_id: str
    organization_id: str
    endpoints: tuple[DirectoryEndpoint, ...]
    ca_certificate_file: Path
    user_principal_template: str
    user_search_base: str = field(repr=False)
    user_search_filter: str = field(repr=False)
    stable_id_attribute: str = "objectGUID"
    display_name_attribute: str = "displayName"
    group_attribute: str = "memberOf"
    group_mappings: tuple[DirectoryGroupMapping, ...] = ()
    max_groups: int = 100
    nested_group_depth: int = 0
    connect_timeout_seconds: float = 3.0
    response_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        validate_stable_identifier(self.provider_id, "provider_id")
        validate_stable_identifier(self.organization_id, "organization_id")
        if not self.endpoints:
            raise ValueError("directory profile requires at least one endpoint")
        if len({item.endpoint_id for item in self.endpoints}) != len(self.endpoints):
            raise ValueError("directory endpoint identifiers must be unique")
        if not str(self.ca_certificate_file).strip():
            raise ValueError("directory profile requires a CA certificate file")
        self._validate_template(self.user_principal_template, "user principal")
        self._validate_template(self.user_search_filter, "user search filter")
        if not self.user_search_base.strip():
            raise ValueError("directory user search base is required")
        for value, name in (
            (self.stable_id_attribute, "stable ID attribute"),
            (self.display_name_attribute, "display-name attribute"),
            (self.group_attribute, "group attribute"),
        ):
            if not value.isidentifier():
                raise ValueError(f"directory {name} is invalid")
        if not 1 <= self.max_groups <= 500:
            raise ValueError("directory group limit is outside platform bounds")
        if not 0 <= self.nested_group_depth <= 5:
            raise ValueError("directory nested-group depth is outside platform bounds")
        if self.nested_group_depth != 0:
            raise ValueError("nested directory groups are not supported in this slice")
        if not 0.1 <= self.connect_timeout_seconds <= 15:
            raise ValueError("directory connection timeout is outside platform bounds")
        if not 0.1 <= self.response_timeout_seconds <= 30:
            raise ValueError("directory response timeout is outside platform bounds")
        mapping_keys = [item.directory_group.casefold() for item in self.group_mappings]
        if len(set(mapping_keys)) != len(mapping_keys):
            raise ValueError("directory group mappings must be unique")

    @staticmethod
    def _validate_template(value: str, label: str) -> None:
        if value.count("{username}") != 1:
            raise ValueError(f"directory {label} template requires one username placeholder")
        remainder = value.replace("{username}", "")
        if "{" in remainder or "}" in remainder or any(ord(item) < 32 for item in value):
            raise ValueError(f"directory {label} template is invalid")


@dataclass(frozen=True, slots=True)
class DirectoryUserRecord:
    stable_external_id: str = field(repr=False)
    display_name: str
    directory_groups: tuple[str, ...] = field(default=(), repr=False)
    endpoint_id: str = ""

    def __post_init__(self) -> None:
        if not self.stable_external_id.strip() or len(self.stable_external_id) > 512:
            raise ValueError("directory stable identity is invalid")
        if not self.display_name.strip() or len(self.display_name) > 256:
            raise ValueError("directory display name is invalid")
        if any(ord(character) < 32 for character in self.display_name):
            raise ValueError("directory display name contains control characters")
        validate_stable_identifier(self.endpoint_id, "endpoint_id")
