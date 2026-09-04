"""ATLAS-021 SS29/SS30: developer workflow and generated connector support.

`GeneratedProjectProvenance` applies to a `connectors.domain.models.ConnectorPackageManifest`
built with `generated=True` -- that field already exists on the runtime manifest type; this adds
only the provenance record SS30 asks for (generator identity/version, source specification), not
a second package-shape. ATLAS-022's own MCP Builder pipeline (candidate handoff, design/domain/
security review, lab validation) is the real producer of these packages and is not modeled here --
this module only defines what the SDK contract requires of a generated package's own metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class DeveloperWorkflowStep(StrEnum):
    """SS29's twelve ordered steps."""

    SELECT_APPROVED_LANGUAGE_PROFILE = "select_approved_language_profile"
    GENERATE_PROJECT_SCAFFOLD = "generate_project_scaffold"
    COMPLETE_CONNECTOR_AND_CONFIGURATION_MANIFEST = "complete_connector_and_configuration_manifest"
    DEFINE_TARGET_PERMISSIONS_AND_NETWORK_FLOWS = "define_target_permissions_and_network_flows"
    DEFINE_ONE_CAPABILITY_AT_A_TIME = "define_one_capability_at_a_time"
    IMPLEMENT_WITH_APPROVED_CLIENTS = "implement_with_approved_clients"
    ADD_REQUIRED_TESTS = "add_required_tests"
    GENERATE_DOCUMENTATION = "generate_documentation"
    BUILD_REPRODUCIBLE_PACKAGE = "build_reproducible_package"
    RUN_CONNECTOR_VALIDATOR = "run_connector_validator"
    REVIEW_VALIDATION_RISK_CLASS_AND_PERMISSIONS = "review_validation_risk_class_and_permissions"
    SUBMIT_PACKAGE_DIGEST_FOR_ENVIRONMENT_APPROVAL = (
        "submit_package_digest_for_environment_approval"
    )


DEVELOPER_WORKFLOW_ORDER: tuple[DeveloperWorkflowStep, ...] = (
    DeveloperWorkflowStep.SELECT_APPROVED_LANGUAGE_PROFILE,
    DeveloperWorkflowStep.GENERATE_PROJECT_SCAFFOLD,
    DeveloperWorkflowStep.COMPLETE_CONNECTOR_AND_CONFIGURATION_MANIFEST,
    DeveloperWorkflowStep.DEFINE_TARGET_PERMISSIONS_AND_NETWORK_FLOWS,
    DeveloperWorkflowStep.DEFINE_ONE_CAPABILITY_AT_A_TIME,
    DeveloperWorkflowStep.IMPLEMENT_WITH_APPROVED_CLIENTS,
    DeveloperWorkflowStep.ADD_REQUIRED_TESTS,
    DeveloperWorkflowStep.GENERATE_DOCUMENTATION,
    DeveloperWorkflowStep.BUILD_REPRODUCIBLE_PACKAGE,
    DeveloperWorkflowStep.RUN_CONNECTOR_VALIDATOR,
    DeveloperWorkflowStep.REVIEW_VALIDATION_RISK_CLASS_AND_PERMISSIONS,
    DeveloperWorkflowStep.SUBMIT_PACKAGE_DIGEST_FOR_ENVIRONMENT_APPROVAL,
)


def is_valid_next_step(
    *, completed_steps: tuple[DeveloperWorkflowStep, ...], candidate: DeveloperWorkflowStep
) -> bool:
    """SS29's workflow is a fixed, ordered sequence -- `candidate` is valid only if it is exactly
    the step after everything already completed, in that same fixed order."""
    if len(completed_steps) >= len(DEVELOPER_WORKFLOW_ORDER):
        return False
    return candidate is DEVELOPER_WORKFLOW_ORDER[len(completed_steps)]


def generated_connector_receives_reduced_review_path() -> bool:
    """SS30: "generated code receives no reduced review path.\""""
    return False


@dataclass(frozen=True, slots=True)
class GeneratedProjectProvenance:
    """SS30: "MCP Builder output uses a generated-project marker and provenance metadata.\""""

    package_reference: str
    generator_id: str
    generator_version: str
    source_specification_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.package_reference, "package_reference")
        validate_stable_identifier(self.generator_id, "generator_id")
        if not self.generator_version.strip():
            raise ValueError("generated project provenance requires a generator version")
        if not self.source_specification_reference.strip():
            raise ValueError(
                "generated project provenance requires a source specification reference"
            )
