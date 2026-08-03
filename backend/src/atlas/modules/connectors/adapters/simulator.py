from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType

from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorHealth,
    ConnectorInstance,
    InstanceLifecycle,
)


class SimulatorScenario(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    DENIED = "denied"
    TIMEOUT = "timeout"
    THROTTLED = "throttled"
    MALFORMED = "malformed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    VENDOR_ERROR = "vendor_error"


class ResultState(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    PARTIAL = "partial"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class SimulatorIsolationPolicy:
    network_access: bool = False
    secret_access: bool = False
    filesystem_access: bool = False
    subprocess_access: bool = False
    maximum_input_bytes: int = 65_536
    maximum_output_bytes: int = 65_536

    def __post_init__(self) -> None:
        if any(
            (
                self.network_access,
                self.secret_access,
                self.filesystem_access,
                self.subprocess_access,
            )
        ):
            raise ValueError("the foundation simulator cannot receive external access")
        if self.maximum_input_bytes < 1 or self.maximum_output_bytes < 1:
            raise ValueError("simulator input and output limits must be positive")


@dataclass(frozen=True, slots=True)
class SimulatorInvocationContext:
    invocation_id: str
    correlation_id: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    instance_id: str
    capability_id: str
    capability_version: str
    deadline: datetime
    attempt: int = 1

    def __post_init__(self) -> None:
        if self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware")
        if self.attempt < 1:
            raise ValueError("attempt must be positive")


@dataclass(frozen=True, slots=True)
class SimulatorFixture:
    scenario: SimulatorScenario
    output: Mapping[str, object]
    evidence_references: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", MappingProxyType(dict(self.output)))


@dataclass(frozen=True, slots=True)
class ConnectorInvocationResult:
    invocation_id: str
    state: ResultState
    output: Mapping[str, object]
    observed_at: datetime
    evidence_references: tuple[str, ...]
    warnings: tuple[str, ...]
    error_code: str | None
    retryable: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", MappingProxyType(dict(self.output)))
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.state is ResultState.SUCCEEDED and not self.evidence_references:
            raise ValueError("successful connector results require evidence")


class ConnectorSimulatorRunner:
    def __init__(
        self,
        *,
        policy: SimulatorIsolationPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.policy = policy or SimulatorIsolationPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        return ConnectorSelfTestResult(
            health=ConnectorHealth.HEALTHY,
            checked_at=self._clock(),
            code="simulator_isolation_verified",
        )

    async def invoke(
        self,
        *,
        instance: ConnectorInstance,
        capability: CapabilityManifest,
        context: SimulatorInvocationContext,
        parameters: Mapping[str, object],
        fixture: SimulatorFixture,
    ) -> ConnectorInvocationResult:
        now = self._clock()
        binding_error = self._binding_error(instance, capability, context)
        if binding_error is not None:
            return self._failure(context, now, binding_error, retryable=False)
        if now >= context.deadline:
            return self._result(
                context=context,
                now=now,
                state=ResultState.TIMED_OUT,
                error_code="deadline_expired",
                retryable=True,
            )
        if self._encoded_size(parameters) > self.policy.maximum_input_bytes:
            return self._failure(context, now, "input_limit_exceeded", retryable=False)
        if self._encoded_size(fixture.output) > self.policy.maximum_output_bytes:
            return self._failure(context, now, "output_limit_exceeded", retryable=False)

        scenario = fixture.scenario
        if scenario in {SimulatorScenario.SUCCESS, SimulatorScenario.EMPTY}:
            evidence = fixture.evidence_references or (
                f"simulator://{instance.instance_id}/{context.invocation_id}",
            )
            return self._result(
                context=context,
                now=now,
                state=ResultState.SUCCEEDED,
                output=fixture.output,
                evidence=evidence,
                warnings=fixture.warnings,
            )
        if scenario is SimulatorScenario.DENIED:
            return self._failure(context, now, "vendor_permission_denied", retryable=False)
        if scenario is SimulatorScenario.TIMEOUT:
            return self._result(
                context=context,
                now=now,
                state=ResultState.TIMED_OUT,
                error_code="target_timeout",
                retryable=True,
            )
        if scenario is SimulatorScenario.THROTTLED:
            return self._failure(context, now, "vendor_rate_limited", retryable=True)
        if scenario is SimulatorScenario.MALFORMED:
            return self._failure(context, now, "malformed_vendor_response", retryable=False)
        if scenario is SimulatorScenario.PARTIAL:
            return self._result(
                context=context,
                now=now,
                state=ResultState.PARTIAL,
                output=fixture.output,
                evidence=fixture.evidence_references,
                warnings=fixture.warnings or ("simulated_partial_result",),
                error_code="partial_result",
                retryable=False,
            )
        if scenario is SimulatorScenario.UNKNOWN:
            return self._result(
                context=context,
                now=now,
                state=ResultState.UNCERTAIN,
                warnings=fixture.warnings or ("simulated_outcome_uncertain",),
                error_code="outcome_uncertain",
                retryable=False,
            )
        return self._failure(context, now, "vendor_internal_error", retryable=False)

    @staticmethod
    def _binding_error(
        instance: ConnectorInstance,
        capability: CapabilityManifest,
        context: SimulatorInvocationContext,
    ) -> str | None:
        if instance.lifecycle is not InstanceLifecycle.ENABLED:
            return "instance_not_enabled"
        if capability.capability_id not in instance.enabled_capability_ids:
            return "capability_not_enabled"
        expected = (
            instance.organization_id,
            instance.environment_id,
            instance.site_id,
            instance.target_id,
            instance.instance_id,
        )
        actual = (
            context.organization_id,
            context.environment_id,
            context.site_id,
            context.target_id,
            context.instance_id,
        )
        if expected != actual:
            return "invocation_scope_mismatch"
        if (
            context.capability_id != capability.capability_id
            or context.capability_version != capability.version
        ):
            return "capability_contract_mismatch"
        return None

    @staticmethod
    def _encoded_size(value: Mapping[str, object]) -> int:
        try:
            encoded = json.dumps(
                dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError):
            return 2**31
        return len(encoded.encode("utf-8"))

    def _failure(
        self,
        context: SimulatorInvocationContext,
        now: datetime,
        error_code: str,
        *,
        retryable: bool,
    ) -> ConnectorInvocationResult:
        return self._result(
            context=context,
            now=now,
            state=ResultState.FAILED,
            error_code=error_code,
            retryable=retryable,
        )

    @staticmethod
    def _result(
        *,
        context: SimulatorInvocationContext,
        now: datetime,
        state: ResultState,
        output: Mapping[str, object] | None = None,
        evidence: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
        error_code: str | None = None,
        retryable: bool = False,
    ) -> ConnectorInvocationResult:
        return ConnectorInvocationResult(
            invocation_id=context.invocation_id,
            state=state,
            output=output or {},
            observed_at=now,
            evidence_references=evidence,
            warnings=warnings,
            error_code=error_code,
            retryable=retryable,
        )
