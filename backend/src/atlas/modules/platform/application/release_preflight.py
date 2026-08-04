from __future__ import annotations

import hmac
import json
import re
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.release_preflight_ports import (
    PreflightHostProbe,
    ReleaseArtifactInventory,
    ReleaseSignatureVerifier,
)
from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    ArtifactObservation,
    DeploymentProfile,
    HostSnapshot,
    PreflightCheck,
    PreflightState,
    ReleaseManifest,
    ReleasePreflightReport,
)


def canonical_manifest_payload(manifest: ReleaseManifest) -> bytes:
    payload = asdict(manifest)
    payload["supported_profiles"] = [item.value for item in manifest.supported_profiles]
    payload["published_at"] = manifest.published_at.isoformat()
    payload["signature"] = ""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class ReleasePreflightError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReleasePreflightService:
    def __init__(
        self,
        *,
        manifest: ReleaseManifest,
        signature_verifier: ReleaseSignatureVerifier,
        artifact_inventory: ReleaseArtifactInventory,
        host_probe: PreflightHostProbe,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._manifest = manifest
        self._signature_verifier = signature_verifier
        self._artifact_inventory = artifact_inventory
        self._host_probe = host_probe
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run(
        self,
        *,
        actor: AuthenticatedSubject,
        mode: AcquisitionMode,
        profile: DeploymentProfile,
        correlation_id: str,
    ) -> ReleasePreflightReport:
        payload = canonical_manifest_payload(self._manifest)
        manifest_digest = sha256(payload).hexdigest()
        checks: list[PreflightCheck] = []
        signature_valid = self._signature_verifier.verify(payload, self._manifest)
        checks.append(
            self._check(
                "release.signature.valid",
                "release",
                signature_valid,
                "Release manifest signature is valid.",
                f"{self._manifest.signature_algorithm}:{self._manifest.signing_key_reference}",
                "Obtain the unchanged manifest from an approved release source.",
            )
        )
        checks.append(
            self._check(
                "release.profile.supported",
                "compatibility",
                profile in self._manifest.supported_profiles,
                "Deployment profile is listed by the release.",
                profile.value,
                "Select a supported profile or a compatible Atlas release.",
            )
        )
        observations = await self._artifact_inventory.observations(mode)
        checks.extend(self._artifact_checks(mode, observations))
        host = await self._host_probe.snapshot()
        checks.extend(self._host_checks(profile, host))
        checks.extend(self._configuration_checks(host.configuration, host.secret_reference_ids))
        mandatory_failed = any(
            item.mandatory and item.state is PreflightState.FAILED for item in checks
        )
        warning = any(item.state is PreflightState.WARNING for item in checks)
        state = (
            PreflightState.FAILED
            if mandatory_failed
            else PreflightState.WARNING
            if warning
            else PreflightState.PASSED
        )
        report = ReleasePreflightReport(
            report_id=f"preflight.{uuid4().hex}",
            release_id=self._manifest.release_id,
            release_version=self._manifest.release_version,
            build_id=self._manifest.build_id,
            manifest_digest=manifest_digest,
            mode=mode,
            profile=profile,
            state=state,
            checks=tuple(checks),
            generated_at=self._clock(),
            correlation_id=correlation_id,
        )
        await self._audit(actor, report)
        return report

    def _artifact_checks(
        self, mode: AcquisitionMode, observations: tuple[ArtifactObservation, ...]
    ) -> tuple[PreflightCheck, ...]:
        expected = {item.relative_path: item for item in self._manifest.artifacts}
        observed = {item.relative_path: item for item in observations}
        duplicate_count = len(observations) - len(observed)
        checks: list[PreflightCheck] = [
            self._check(
                "artifacts.inventory.unique",
                "artifacts",
                duplicate_count == 0,
                "Artifact inventory paths are unique.",
                f"duplicates={duplicate_count}",
                "Remove duplicate bundle or mirror inventory entries.",
            )
        ]
        extras = sorted(set(observed) - set(expected))
        checks.append(
            self._check(
                "artifacts.inventory.exact",
                "artifacts",
                not extras,
                "Artifact inventory contains no unlisted files.",
                f"unexpected_count={len(extras)}",
                "Remove unlisted artifacts and reacquire the approved bundle.",
            )
        )
        for path, artifact in expected.items():
            observation = observed.get(path)
            present = observation is not None
            valid = bool(
                observation
                and observation.size_bytes == artifact.size_bytes
                and hmac.compare_digest(observation.sha256, artifact.sha256)
                and self._source_allowed(mode, observation.source)
            )
            mandatory = artifact.required
            state = (
                PreflightState.PASSED
                if valid
                else PreflightState.FAILED
                if mandatory
                else PreflightState.WARNING
            )
            checks.append(
                PreflightCheck(
                    code=f"artifact.{artifact.artifact_id}",
                    category="artifacts",
                    state=state,
                    mandatory=mandatory,
                    summary=(
                        "Artifact checksum and source are verified."
                        if valid
                        else "Artifact is missing, modified, or from an unapproved source."
                    ),
                    evidence=f"path={path};present={str(present).lower()}",
                    remediation=(
                        None
                        if valid
                        else "Acquire the exact immutable artifact through the selected mode."
                    ),
                )
            )
        return tuple(checks)

    def _host_checks(
        self, profile: DeploymentProfile, host: HostSnapshot
    ) -> tuple[PreflightCheck, ...]:
        operating_system = host.operating_system.casefold()
        os_valid = profile is DeploymentProfile.DEVELOPER or operating_system == "linux"
        architecture_valid = host.architecture.casefold() in {"amd64", "x86_64"}
        python_valid = self._version_tuple(host.python_version) >= self._version_tuple(
            self._manifest.minimum_python
        )
        resources_valid = (
            host.cpu_cores >= self._manifest.minimum_cpu_cores
            and host.memory_mb >= self._manifest.minimum_memory_mb
            and host.disk_available_mb >= self._manifest.minimum_disk_mb
        )
        missing_tools = sorted(set(self._manifest.required_tools) - set(host.available_tools))
        conflicts = sorted(set(self._manifest.required_ports) & set(host.busy_ports))
        return (
            self._check(
                "host.operating-system.supported",
                "host",
                os_valid,
                "Host operating system is supported by the selected profile.",
                operating_system,
                "Use a Linux host for the linux_lab profile.",
            ),
            self._check(
                "host.architecture.supported",
                "host",
                architecture_valid,
                "Host architecture is supported.",
                host.architecture,
                "Use an approved amd64/x86_64 host.",
            ),
            self._check(
                "host.python.compatible",
                "runtime",
                python_valid,
                "Python runtime meets the release minimum.",
                host.python_version,
                f"Install Python {self._manifest.minimum_python} or later.",
            ),
            self._check(
                "host.capacity.minimum",
                "capacity",
                resources_valid,
                "Host meets minimum CPU, memory, and disk requirements.",
                f"cpu={host.cpu_cores};memory_mb={host.memory_mb};disk_mb={host.disk_available_mb}",
                "Increase lab host capacity before deployment.",
            ),
            self._check(
                "host.tools.available",
                "runtime",
                not missing_tools,
                "Required administration tools are available.",
                f"missing_count={len(missing_tools)}",
                "Install the missing approved tools without changing Atlas state.",
            ),
            self._check(
                "host.ports.available",
                "network",
                not conflicts,
                "Required local ports are available.",
                f"conflict_count={len(conflicts)}",
                "Stop or reconfigure the conflicting service before deployment.",
            ),
        )

    def _configuration_checks(
        self,
        configuration: tuple[tuple[str, str], ...],
        secret_reference_ids: tuple[str, ...],
    ) -> tuple[PreflightCheck, ...]:
        keys = [key for key, _ in configuration]
        duplicates = len(keys) != len(set(keys))
        unsafe_bind = any(value in {"0.0.0.0", "::", "*"} for _, value in configuration)
        secret_like = re.compile(r"password|token|private[_-]?key|secret", re.IGNORECASE)
        plaintext = [
            key
            for key, value in configuration
            if secret_like.search(key) and value and not value.startswith("secret.")
        ]
        refs_valid = bool(secret_reference_ids) and all(
            item.startswith("secret.") for item in secret_reference_ids
        )
        valid = not duplicates and not unsafe_bind and not plaintext and refs_valid
        return (
            self._check(
                "configuration.safe",
                "configuration",
                valid,
                "Configuration is unique, privately bound, and secret-reference-only.",
                (
                    f"keys={len(keys)};duplicates={str(duplicates).lower()};"
                    f"unsafe_bind={str(unsafe_bind).lower()};plaintext_secret_count={len(plaintext)}"
                ),
                (
                    "Remove duplicate or plaintext secret values and use private binds and "
                    "secret references."
                ),
            ),
        )

    def _source_allowed(self, mode: AcquisitionMode, source: str) -> bool:
        if mode is AcquisitionMode.CONNECTED:
            return any(
                source.startswith(item) for item in self._manifest.approved_connected_sources
            )
        if mode is AcquisitionMode.MIRRORED:
            return source.startswith(
                self._manifest.approved_mirror_sources
            ) and not source.startswith(("http://", "https://"))
        return source.startswith("offline://bundle/") and not source.startswith(
            ("http://", "https://", "mirror://")
        )

    async def _audit(self, actor: AuthenticatedSubject, report: ReleasePreflightReport) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.platform.release-preflight.read",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=report.generated_at,
                correlation_id=report.correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.release-preflight.read",
                resource_type="resource.platform.release-preflight",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.platform/resource.platform.release-preflight/C0"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=f"release_preflight_{report.state.value}",
                target_metadata=(
                    ("release_id", report.release_id),
                    ("mode", report.mode.value),
                    ("profile", report.profile.value),
                    ("manifest_digest", report.manifest_digest),
                    ("check_count", str(len(report.checks))),
                ),
            )
        )

    @staticmethod
    def _check(
        code: str,
        category: str,
        passed: bool,
        success: str,
        evidence: str,
        remediation: str,
        *,
        mandatory: bool = True,
    ) -> PreflightCheck:
        return PreflightCheck(
            code=code,
            category=category,
            state=PreflightState.PASSED if passed else PreflightState.FAILED,
            mandatory=mandatory,
            summary=success if passed else remediation,
            evidence=evidence,
            remediation=None if passed else remediation,
        )

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...]:
        try:
            return tuple(int(item) for item in value.split("."))
        except ValueError:
            return ()
