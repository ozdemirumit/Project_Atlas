from __future__ import annotations

from atlas.modules.change_impact.domain.security_privacy import (
    contains_secret,
    generated_graph_edges_simulations_and_plans_are_trusted_before_validation,
)


def test_contains_secret_true_for_aws_key() -> None:
    assert contains_secret("api_key: AKIAABCDEFGHIJKLMNOP") is True


def test_contains_secret_false_for_ordinary_text() -> None:
    assert contains_secret("Controller B fails over to controller A within 5 minutes.") is False


def test_generated_content_never_trusted_before_validation() -> None:
    assert generated_graph_edges_simulations_and_plans_are_trusted_before_validation() is False
