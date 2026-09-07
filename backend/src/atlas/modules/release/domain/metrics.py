"""ATLAS-059 SS38: metrics."""

from __future__ import annotations

from enum import StrEnum


class ReleaseMetric(StrEnum):
    """SS38's ten release metric categories."""

    LEAD_TIME_CANDIDATE_COUNT_AND_RELEASE_FREQUENCY = (
        "lead_time_candidate_count_and_release_frequency"
    )
    GATE_FAILURE_AND_DEFECT_ESCAPE = "gate_failure_and_defect_escape"
    SECURITY_AND_AI_EVALUATION_REGRESSION = "security_and_ai_evaluation_regression"
    UPGRADE_ROLLBACK_AND_DEPLOYMENT_SUCCESS = "upgrade_rollback_and_deployment_success"
    BACKUP_AND_RESTORE_VALIDATION_AGE = "backup_and_restore_validation_age"
    OFFLINE_BUNDLE_BUILD_AND_IMPORT_SUCCESS = "offline_bundle_build_and_import_success"
    MEAN_TIME_TO_PATCH_CRITICAL_VULNERABILITIES = "mean_time_to_patch_critical_vulnerabilities"
    SUPPORT_INCIDENTS_BY_RELEASE_AND_COMPONENT = "support_incidents_by_release_and_component"
    ADOPTION_DEPRECATED_USAGE_AND_LTS_TRANSITION = "adoption_deprecated_usage_and_lts_transition"
    EXCEPTION_COUNT_AND_AGE = "exception_count_and_age"


def metrics_can_pressure_teams_to_approve_unsafe_releases() -> bool:
    """SS38: "metrics inform improvement and do not pressure teams to approve unsafe
    releases.\""""
    return False
