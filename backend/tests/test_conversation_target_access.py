from __future__ import annotations

import pytest

from atlas.modules.conversations.adapters.targets import (
    DevelopmentConversationTargetAccessSource,
    EmptyConversationTargetAccessSource,
)
from atlas.modules.conversations.application.ports import ConversationTargetAccessRequest
from atlas.modules.conversations.domain.models import (
    AuthorizedConversationTarget,
    ConversationScope,
)

SCOPE = ConversationScope("organization.development", "environment.development", "site.local")
TARGET = AuthorizedConversationTarget(
    target_id="asset.storage.lab.vsp-g400",
    display_name="VSP G400 Lab",
    description="Authorized synthetic enterprise storage target.",
)


def request(
    *,
    subject_id: str = "subject.development.operator",
    principal_ids: frozenset[str] = frozenset({"role.development.operator"}),
    scope: ConversationScope = SCOPE,
) -> ConversationTargetAccessRequest:
    return ConversationTargetAccessRequest(
        subject_id=subject_id,
        principal_ids=principal_ids,
        scope=scope,
    )


@pytest.mark.asyncio
async def test_development_targets_require_exact_subject_scope_and_principal() -> None:
    source = DevelopmentConversationTargetAccessSource(
        subject_id="subject.development.operator",
        required_principal_ids=frozenset({"role.development.operator"}),
        scope=SCOPE,
        targets=(TARGET,),
    )

    assert await source.authorized_storage_targets(request()) == (TARGET,)
    assert await source.authorized_storage_targets(request(subject_id="subject.other")) == ()
    assert (
        await source.authorized_storage_targets(request(principal_ids=frozenset({"role.other"})))
        == ()
    )
    assert (
        await source.authorized_storage_targets(
            request(
                scope=ConversationScope(
                    "organization.development", "environment.development", "site.other"
                )
            )
        )
        == ()
    )


@pytest.mark.asyncio
async def test_empty_source_grants_no_production_target_fallback() -> None:
    assert await EmptyConversationTargetAccessSource().authorized_storage_targets(request()) == ()
