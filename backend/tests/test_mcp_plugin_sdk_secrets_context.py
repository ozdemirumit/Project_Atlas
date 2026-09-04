from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.mcp_plugin_sdk.domain.secrets_context import (
    InvocationContext,
    SecretHandle,
    instance_can_read_another_instances_secret_path,
    is_cancelled,
    secret_can_be_passed_to_model_or_evidence_context,
    secret_handle_can_be_serialized,
    secret_object_can_be_logged_or_returned,
    secret_persists_after_invocation,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def secret_handle(**overrides: object) -> SecretHandle:
    defaults: dict[str, object] = {
        "handle_id": "secret-handle.example",
        "instance_id": "connector-instance.example",
        "resolved_value": "s3cr3t-token-value",
        "resolved_at": NOW,
        "expires_at": NOW + timedelta(minutes=5),
    }
    defaults.update(overrides)
    return SecretHandle(**defaults)  # type: ignore[arg-type]


def test_secret_handle_rejects_expiry_before_resolution() -> None:
    with pytest.raises(ValueError, match="expires_at must be after resolved_at"):
        secret_handle(expires_at=NOW - timedelta(minutes=1))


def test_secret_handle_repr_redacts_value() -> None:
    handle = secret_handle()
    assert "s3cr3t-token-value" not in repr(handle)
    assert "redacted" in repr(handle)


def test_secret_handle_str_redacts_value() -> None:
    handle = secret_handle()
    assert "s3cr3t-token-value" not in str(handle)


@pytest.mark.parametrize(
    "checker",
    [
        secret_handle_can_be_serialized,
        secret_object_can_be_logged_or_returned,
        secret_can_be_passed_to_model_or_evidence_context,
        instance_can_read_another_instances_secret_path,
        secret_persists_after_invocation,
    ],
)
def test_secret_prohibitions_are_always_false(checker: object) -> None:
    assert checker() is False  # type: ignore[operator]


def context(**overrides: object) -> InvocationContext:
    defaults: dict[str, object] = {
        "invocation_id": "invocation.example",
        "request_id": "request.example",
        "workflow_id": "workflow.example",
        "correlation_id": "correlation.example",
        "attempt": 1,
        "connector_version": "1.0.0",
        "package_version": "1.0.0",
        "instance_id": "connector-instance.example",
        "capability_version": "1.0.0",
        "organization_id": "organization.example",
        "environment_id": "environment.production",
        "site_id": "site.primary",
        "target_id": "target.controller-b",
        "deadline": NOW + timedelta(seconds=30),
        "idempotency_key": "idempotency.example",
        "cancellation_token": "cancellation.example",
        "approved_feature_flags": frozenset({"feature.batch_read"}),
        "compatibility_flags": frozenset(),
    }
    defaults.update(overrides)
    return InvocationContext(**defaults)  # type: ignore[arg-type]


def test_context_accepts_valid_state() -> None:
    assert context().invocation_id == "invocation.example"


def test_context_requires_positive_attempt() -> None:
    with pytest.raises(ValueError, match="positive, 1-based attempt"):
        context(attempt=0)


def test_context_requires_timezone_aware_deadline() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        context(deadline=datetime(2026, 9, 4, 12, 0))


def test_is_cancelled_true_when_token_present() -> None:
    assert (
        is_cancelled(
            cancellation_token="cancellation.example",
            cancelled_tokens=frozenset({"cancellation.example"}),
        )
        is True
    )


def test_is_cancelled_false_when_token_absent() -> None:
    assert (
        is_cancelled(cancellation_token="cancellation.example", cancelled_tokens=frozenset())
        is False
    )
