from __future__ import annotations

import io
import json
import stat
import zipfile
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any, cast

from atlas.modules.connectors.application.package_registration_ports import PackageRegistrationError
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationPolicySnapshot,
    ConnectorRegisteredCapability,
    ConnectorRegisteredManifestSnapshot,
)

_MANIFEST_KEYS = {
    "schema_version",
    "connector_id",
    "version",
    "status",
    "sdk_profile",
    "target_products",
    "network_destinations",
    "configuration_keys",
    "secret_reference_ids",
    "capabilities",
    "runtime_trust",
    "execution_authorized",
}
_CAPABILITY_KEYS = {"id", "class", "permission", "handler_status"}


class BoundedConnectorPackageManifestInspector:
    def inspect(
        self, *, content: bytes, policy: ConnectorPackageRegistrationPolicySnapshot
    ) -> ConnectorRegisteredManifestSnapshot:
        try:
            with zipfile.ZipFile(io.BytesIO(content), mode="r") as archive:
                entries = archive.infolist()
                self._verify_entries(entries, policy)
                manifest_entry = next(
                    item for item in entries if item.filename == policy.required_manifest_path
                )
                if manifest_entry.file_size > policy.maximum_manifest_bytes:
                    raise PackageRegistrationError("package_registration_manifest_oversized")
                manifest_bytes = archive.read(manifest_entry)
        except PackageRegistrationError:
            raise
        except (KeyError, OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
            raise PackageRegistrationError("package_registration_archive_invalid") from error

        if len(manifest_bytes) > policy.maximum_manifest_bytes:
            raise PackageRegistrationError("package_registration_manifest_oversized")
        try:
            raw = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PackageRegistrationError("package_registration_manifest_invalid") from error
        if not isinstance(raw, dict) or set(raw) != _MANIFEST_KEYS:
            raise PackageRegistrationError("package_registration_manifest_invalid")
        manifest = cast(dict[str, Any], raw)

        schema_version = self._string(manifest, "schema_version")
        connector_id = self._string(manifest, "connector_id")
        manifest_version = self._string(manifest, "version")
        status = self._string(manifest, "status")
        sdk_profile = self._string(manifest, "sdk_profile")
        if (
            schema_version != policy.required_manifest_schema
            or status != policy.required_manifest_status
            or sdk_profile != policy.required_sdk_profile
            or manifest.get("runtime_trust") is not False
            or manifest.get("execution_authorized") is not False
        ):
            raise PackageRegistrationError("package_registration_manifest_policy_rejected")

        target_products = self._string_list(
            manifest, "target_products", maximum=policy.maximum_target_products, allow_empty=False
        )
        network_destinations = self._string_list(
            manifest,
            "network_destinations",
            maximum=policy.maximum_network_destinations,
            allow_empty=True,
        )
        configuration_keys = self._string_list(
            manifest, "configuration_keys", maximum=100, allow_empty=True
        )
        secret_reference_ids = self._string_list(
            manifest, "secret_reference_ids", maximum=100, allow_empty=True
        )
        capabilities = self._capabilities(manifest, policy)
        return ConnectorRegisteredManifestSnapshot(
            schema_version=schema_version,
            connector_id=connector_id,
            manifest_version=manifest_version,
            release_version=f"version.{manifest_version}",
            source_status=status,
            sdk_profile=sdk_profile,
            target_products=target_products,
            network_destinations=network_destinations,
            configuration_key_count=len(configuration_keys),
            secret_reference_count=len(secret_reference_ids),
            capabilities=capabilities,
            manifest_digest=sha256(manifest_bytes).hexdigest(),
        )

    @staticmethod
    def _verify_entries(
        entries: list[zipfile.ZipInfo], policy: ConnectorPackageRegistrationPolicySnapshot
    ) -> None:
        names = [item.filename for item in entries]
        if (
            not entries
            or len(entries) > policy.maximum_archive_entries
            or len(names) != len(set(names))
            or names.count(policy.required_manifest_path) != 1
        ):
            raise PackageRegistrationError("package_registration_archive_invalid")
        for item in entries:
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (
                item.is_dir()
                or item.flag_bits & 0x1
                or item.compress_type != zipfile.ZIP_STORED
                or not item.filename
                or "\\" in item.filename
                or item.filename.startswith("/")
                or path.is_absolute()
                or any(part in {"", ".", ".."} for part in path.parts)
                or stat.S_ISLNK(mode)
                or stat.S_ISCHR(mode)
                or stat.S_ISBLK(mode)
            ):
                raise PackageRegistrationError("package_registration_archive_invalid")

    @staticmethod
    def _string(manifest: dict[str, Any], key: str) -> str:
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise PackageRegistrationError("package_registration_manifest_invalid")
        return value

    @classmethod
    def _string_list(
        cls, manifest: dict[str, Any], key: str, *, maximum: int, allow_empty: bool
    ) -> tuple[str, ...]:
        value = manifest.get(key)
        if not isinstance(value, list) or len(value) > maximum or (not allow_empty and not value):
            raise PackageRegistrationError("package_registration_manifest_invalid")
        items: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip() or len(item) > 253:
                raise PackageRegistrationError("package_registration_manifest_invalid")
            items.append(item)
        if len(items) != len(set(items)):
            raise PackageRegistrationError("package_registration_manifest_invalid")
        return tuple(items)

    @classmethod
    def _capabilities(
        cls,
        manifest: dict[str, Any],
        policy: ConnectorPackageRegistrationPolicySnapshot,
    ) -> tuple[ConnectorRegisteredCapability, ...]:
        value = manifest.get("capabilities")
        if not isinstance(value, list) or not 1 <= len(value) <= policy.maximum_capabilities:
            raise PackageRegistrationError("package_registration_manifest_invalid")
        capabilities: list[ConnectorRegisteredCapability] = []
        for raw in value:
            if not isinstance(raw, dict) or set(raw) != _CAPABILITY_KEYS:
                raise PackageRegistrationError("package_registration_manifest_invalid")
            item = cast(dict[str, Any], raw)
            capability_class = cls._string(item, "class")
            if (
                capability_class not in policy.allowed_capability_classes
                or cls._string(item, "handler_status") != "draft_fail_closed"
            ):
                raise PackageRegistrationError("package_registration_manifest_policy_rejected")
            try:
                capabilities.append(
                    ConnectorRegisteredCapability(
                        capability_id=cls._string(item, "id"),
                        capability_class=capability_class,
                        required_permission=cls._string(item, "permission"),
                    )
                )
            except ValueError as error:
                raise PackageRegistrationError("package_registration_manifest_invalid") from error
        if len({item.capability_id for item in capabilities}) != len(capabilities):
            raise PackageRegistrationError("package_registration_manifest_invalid")
        return tuple(capabilities)
