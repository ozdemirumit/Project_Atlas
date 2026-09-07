"""ATLAS-035 SS12/SS24: the ten baseline detections, as portable specifications.

Each `DetectionContentContract` is data, not an executable rule for a specific vendor SIEM --
SS27's open question naming the first validated SIEM platform is still unresolved, and SS24's
MVP scope asks only for these use cases "as portable specifications."
"""

from __future__ import annotations

from atlas.modules.security_export.domain.detection_content import (
    DetectionContentContract,
    DetectionTestFixture,
    DetectionTestFixtureKind,
    DetectionUseCaseId,
)
from atlas.modules.security_export.domain.models import SecuritySeverity

_OWNER = "security-operations-integration-owner"
_SCHEMA_VERSIONS = ("atlas-security-event.v1",)
_EVIDENCE_LINK_KINDS = ("audit_ledger_reference", "atlas_investigation_view")
_REVIEW_INTERVAL_DAYS = 180


def _fixtures(
    *,
    positive: str,
    negative: str,
    duplicate: str,
    delayed: str,
    missing_field: str,
) -> tuple[DetectionTestFixture, ...]:
    return (
        DetectionTestFixture(
            kind=DetectionTestFixtureKind.POSITIVE, description=positive, expected_outcome="fires"
        ),
        DetectionTestFixture(
            kind=DetectionTestFixtureKind.NEGATIVE,
            description=negative,
            expected_outcome="does not fire",
        ),
        DetectionTestFixture(
            kind=DetectionTestFixtureKind.DUPLICATE,
            description=duplicate,
            expected_outcome="deduplicated on Atlas event ID, no repeat alert",
        ),
        DetectionTestFixture(
            kind=DetectionTestFixtureKind.DELAYED,
            description=delayed,
            expected_outcome="still correlated into the same detection window",
        ),
        DetectionTestFixture(
            kind=DetectionTestFixtureKind.MISSING_FIELD,
            description=missing_field,
            expected_outcome="excluded from evaluation and flagged as an unmapped-field warning",
        ),
    )


SIEM_UC_001 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_001,
    version="1.0.0",
    name="Repeated Authentication Failure",
    purpose="Surface likely credential-stuffing or brute-force activity against Atlas identities.",
    threat_or_compliance_hypothesis=(
        "A cluster of authentication failures for the same subject reference, source, or "
        "provider in a short window indicates an attacker attempting to guess or replay "
        "credentials."
    ),
    limitations=(
        "Provider-side rate limiting and provider outages both produce failure clusters that "
        "look identical to an attack; this detection cannot distinguish the two without "
        "provider-outage enrichment."
    ),
    required_event_types=("atlas.authentication.failed", "atlas.authentication.provider_outage"),
    required_fields=("subject_reference", "source", "provider", "occurred_at"),
    query_logic_summary=(
        "Count atlas.authentication.failed events grouped by subject reference, source, and "
        "provider within the time window; suppress when a concurrent provider-outage signal "
        "covers the same provider."
    ),
    time_window="15 minutes",
    thresholds="5 or more failures for the same subject reference and source",
    grouping="by subject reference, source, and provider",
    suppression_behavior="suppressed for the duration of an overlapping provider-outage signal",
    expected_false_positives="shared NAT egress, forgotten credentials, provider rate limiting",
    tuning_guidance=(
        "raise the threshold or widen the window for sources known to sit behind shared NAT"
    ),
    severity=SecuritySeverity.MEDIUM,
    escalation_recommendation="triage within one business day; escalate to high if paired with a "
    "subsequent successful authentication from a new source",
    investigation_steps=(
        "review the correlation chain for the subject reference",
        "check for a subsequent successful authentication from an unfamiliar source",
        "confirm whether a provider-outage signal overlaps the window",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="6 failures for the same subject reference and source within 15 minutes",
        negative="3 failures spread across unrelated subject references",
        duplicate="the same failure event ID replayed by a retried export",
        delayed="a 6th failure arriving 40 minutes late but timestamped inside the window",
        missing_field="a failure event without a source field",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_002 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_002,
    version="1.0.0",
    name="Privileged Access Change",
    purpose="Alert on role, scope, or elevation changes that expand what a subject can do.",
    threat_or_compliance_hypothesis=(
        "Privileged role assignment, wildcard scope grants, temporary elevation, elevation "
        "extension, or emergency access outside an expected change window indicates either "
        "compromise or an unreviewed privilege escalation."
    ),
    limitations=(
        "This detection cannot itself confirm whether a change window was approved; it flags "
        "activity outside the window for human review, not a confirmed violation."
    ),
    required_event_types=(
        "atlas.authorization.role_assignment",
        "atlas.authorization.scope_grant",
        "atlas.authorization.temporary_elevation",
        "atlas.authorization.emergency_access",
    ),
    required_fields=("subject_reference", "role_or_scope_reference", "change_window_reference"),
    query_logic_summary=(
        "Alert on any privileged role assignment, wildcard scope grant, temporary elevation, "
        "elevation extension, or emergency-access event; raise severity when the event falls "
        "outside a referenced change window."
    ),
    time_window="not applicable -- evaluated per event",
    thresholds="any matching event",
    grouping="by subject reference",
    suppression_behavior="none -- every matching event is significant",
    expected_false_positives="planned emergency access following the break-glass process",
    tuning_guidance="exclude a documented recurring window if repeatedly reviewed clean",
    severity=SecuritySeverity.HIGH,
    escalation_recommendation="triage within the current shift; escalate immediately if outside "
    "an expected change window",
    investigation_steps=(
        "confirm whether an approved change window covers the event",
        "review the requesting and approving subject references for separation of duties",
        "check for a subsequent use of the newly granted privilege",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="a wildcard scope grant issued outside any referenced change window",
        negative="a routine role assignment inside an approved change window",
        duplicate="the same role-assignment event ID exported twice after a retry",
        delayed="an emergency-access event arriving after the window closed but timestamped inside",
        missing_field="a scope-grant event without a change-window reference",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_003 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_003,
    version="1.0.0",
    name="Separation-of-Duties Conflict",
    purpose="Detect a subject acting as both requester and approver of the same sensitive action.",
    threat_or_compliance_hypothesis=(
        "A subject who both requests and approves the same sensitive action, or authors and "
        "publishes the same protected policy or connector artifact, has bypassed a "
        "separation-of-duties control."
    ),
    limitations=(
        "Legitimate emergency single-approver paths exist and are themselves audited; this "
        "detection surfaces every match for review rather than asserting a policy violation."
    ),
    required_event_types=(
        "atlas.approval.decision",
        "atlas.policy.publication",
        "atlas.connector.publication",
    ),
    required_fields=(
        "requesting_subject_reference",
        "deciding_subject_reference",
        "artifact_reference",
    ),
    query_logic_summary=(
        "Compare the requesting/authoring subject reference against the approving/publishing "
        "subject reference for the same artifact reference; alert on any match."
    ),
    time_window="not applicable -- evaluated per artifact lifecycle",
    thresholds="any matching subject reference on both sides",
    grouping="by artifact reference",
    suppression_behavior="none",
    expected_false_positives="a documented, separately-authorized emergency single-approver path",
    tuning_guidance="label known emergency-approval exceptions so investigators can filter them",
    severity=SecuritySeverity.HIGH,
    escalation_recommendation="triage within one business day; escalate if the artifact is "
    "production-facing",
    investigation_steps=(
        "confirm whether a documented emergency-approval exception covers the match",
        "review the artifact's downstream use since publication",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="the same subject reference both requests and approves a policy publication",
        negative="a request and approval by two distinct subject references",
        duplicate="the same approval-decision event ID exported twice",
        delayed="a matching approval event arriving late but correctly timestamped",
        missing_field="an approval-decision event without a deciding subject reference",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_004 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_004,
    version="1.0.0",
    name="Unsafe Connector Activity",
    purpose="Alert on connector activity that was denied, out-of-scope, untrusted, or high-risk.",
    threat_or_compliance_hypothesis=(
        "Denied, out-of-scope, unsigned, untrusted, or C3-C5 capability attempts, repeated "
        "parameter-validation failures, or ambiguous operational outcomes indicate either a "
        "misconfigured connector or an attempt to exceed its authorized capability."
    ),
    limitations=(
        "A single denied attempt is often benign (a misconfigured client); this detection is "
        "tuned to repeated or high-risk-capability patterns rather than any single denial."
    ),
    required_event_types=(
        "atlas.connector.invocation.denied",
        "atlas.connector.invocation.untrusted",
        "atlas.connector.invocation.ambiguous_outcome",
    ),
    required_fields=("connector_reference", "capability_class", "outcome"),
    query_logic_summary=(
        "Alert immediately on any unsigned or untrusted connector invocation attempt or any "
        "C3-C5 capability denial; alert on repeated parameter-validation failures or ambiguous "
        "outcomes above a threshold within the window."
    ),
    time_window="10 minutes for repeated-failure evaluation",
    thresholds="any untrusted/unsigned attempt, or 3+ parameter-validation failures",
    grouping="by connector reference and capability class",
    suppression_behavior="suppress repeat parameter-validation alerts for the same connector "
    "reference once a ticket is open",
    expected_false_positives="a connector under active development in a non-production environment",
    tuning_guidance="exclude connector references explicitly marked as in-development sandboxes",
    severity=SecuritySeverity.HIGH,
    escalation_recommendation="triage within the current shift for untrusted/unsigned attempts",
    investigation_steps=(
        "review the connector's trust and signing status",
        "check the capability class and declared authority against the attempted action",
        "review recent package validation and vulnerability findings for the connector",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="an unsigned connector package attempts a C4 capability invocation",
        negative="a trusted, signed connector's routine C1 capability invocation",
        duplicate="the same denied-invocation event ID exported twice after a retry",
        delayed="a denial event arriving after a transport retry but correctly timestamped",
        missing_field="an invocation-denied event without a capability class",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_005 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_005,
    version="1.0.0",
    name="Audit Pipeline or Integrity Failure",
    purpose="Alert on any condition threatening the completeness or integrity of the audit trail.",
    threat_or_compliance_hypothesis=(
        "Ingestion outage, missing lifecycle events, invalid signature or hash-chain, capacity "
        "risk, unauthorized audit access, or export backlog each threaten the authoritative "
        "audit ledger Atlas depends on for every other control."
    ),
    limitations=(
        "This detection observes the export pipeline's own health signals; it cannot itself "
        "repair a broken audit chain, only surface the condition for immediate response."
    ),
    required_event_types=(
        "atlas.audit.ingestion_outage",
        "atlas.audit.chain_verification_failed",
        "atlas.audit.unauthorized_access",
        "atlas.security_export.backlog_threshold_exceeded",
    ),
    required_fields=("component", "detail_reference"),
    query_logic_summary=(
        "Alert immediately on any ingestion outage, chain-verification failure, unauthorized "
        "audit access, or export backlog crossing its configured threshold."
    ),
    time_window="not applicable -- evaluated per event",
    thresholds="any matching event",
    grouping="by component",
    suppression_behavior="none -- every matching event is significant",
    expected_false_positives="a planned maintenance window on the audit storage component",
    tuning_guidance="exclude a specific, time-boxed, pre-announced maintenance window",
    severity=SecuritySeverity.CRITICAL,
    escalation_recommendation="page on-call immediately",
    investigation_steps=(
        "confirm whether a planned maintenance window covers the event",
        "check downstream detection coverage gaps for the affected time range",
        "verify export backlog age and destination health after remediation",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="a chain-verification-failed event with no covering maintenance window",
        negative="an ingestion-outage event fully inside an announced maintenance window",
        duplicate="the same integrity-failure event ID exported twice",
        delayed="a backlog-threshold event arriving late but timestamped inside the window",
        missing_field="an integrity-failure event without a component field",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_006 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_006,
    version="1.0.0",
    name="AI Guardrail or Prompt-Injection Signal",
    purpose="Detect repeated or high-severity attempts to bypass Atlas's AI safety controls.",
    threat_or_compliance_hypothesis=(
        "Repeated unsafe-tool requests, malicious-document findings, instruction-hierarchy "
        "violations, secret-seeking prompts, or disabled grounding controls indicate an "
        "attempt to manipulate Atlas's AI behavior or exfiltrate sensitive data through it."
    ),
    limitations=(
        "A single guardrail trigger is Atlas's control working as intended, not an incident by "
        "itself; this detection is tuned to repetition or disabled-control conditions."
    ),
    required_event_types=(
        "atlas.guardrails.unsafe_tool_request",
        "atlas.guardrails.malicious_document_detected",
        "atlas.guardrails.instruction_hierarchy_violation",
        "atlas.guardrails.secret_seeking_prompt",
        "atlas.guardrails.grounding_control_disabled",
    ),
    required_fields=("subject_reference", "guardrail_category"),
    query_logic_summary=(
        "Alert immediately on any grounding-control-disabled event; alert on 3+ unsafe-tool, "
        "malicious-document, instruction-hierarchy, or secret-seeking findings for the same "
        "subject reference within the window."
    ),
    time_window="30 minutes",
    thresholds="3 or more findings for the same subject reference, or any disabled control",
    grouping="by subject reference and guardrail category",
    suppression_behavior="suppress repeat alerts for the same subject reference once open",
    expected_false_positives="a security researcher deliberately red-teaming guardrails in a "
    "sanctioned test environment",
    tuning_guidance="exclude subject references explicitly marked as sanctioned red-team testers",
    severity=SecuritySeverity.HIGH,
    escalation_recommendation="triage within the current shift; escalate to critical if grounding "
    "controls were disabled outside a sanctioned test",
    investigation_steps=(
        "review the full prompt and tool-request correlation chain for the subject reference",
        "confirm whether the subject reference is a sanctioned red-team tester",
        "check for any subsequent successful unsafe-tool invocation",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="4 unsafe-tool-request findings for the same subject reference in 30 minutes",
        negative="a single unsafe-tool-request finding for an otherwise clean subject reference",
        duplicate="the same guardrail-finding event ID exported twice after a retry",
        delayed="a 4th finding arriving late but timestamped inside the window",
        missing_field="a guardrail finding without a guardrail category",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_007 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_007,
    version="1.0.0",
    name="Sensitive Data Export",
    purpose="Alert on unusual audit, knowledge, report, support-bundle, or topology exports.",
    threat_or_compliance_hypothesis=(
        "An export of audit data, knowledge content, reports, support bundles, or topology "
        "information that is unusual by actor, scope, volume, destination, or time indicates "
        "possible data exfiltration."
    ),
    limitations=(
        '"Unusual" is evaluated relative to the subject reference\'s own recent export '
        "history; a subject with no export history will trigger on their first legitimate "
        "large export."
    ),
    required_event_types=(
        "atlas.audit.export.requested",
        "atlas.knowledge.export.requested",
        "atlas.reports.export.requested",
        "atlas.support_bundle.export.requested",
        "atlas.graph.topology_export.requested",
    ),
    required_fields=("subject_reference", "export_scope", "export_volume", "destination"),
    query_logic_summary=(
        "Compare each export's volume, scope, destination, and time-of-day against the "
        "subject reference's trailing 30-day export baseline; alert when any dimension "
        "exceeds a configured deviation."
    ),
    time_window="30-day rolling baseline, evaluated per export",
    thresholds="export volume or scope exceeding the subject's baseline by a configured margin",
    grouping="by subject reference",
    suppression_behavior="none -- each qualifying export is evaluated independently",
    expected_false_positives="a legitimate one-time bulk export for an approved audit or migration",
    tuning_guidance="pre-register approved bulk-export windows to suppress expected spikes",
    severity=SecuritySeverity.HIGH,
    escalation_recommendation="triage within the current shift; escalate if the destination is "
    "outside the organization's known egress points",
    investigation_steps=(
        "confirm whether the export matches a pre-registered approved bulk-export window",
        "review the export destination against known egress points",
        "check the exported scope for restricted or hidden-topology content",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="a knowledge export ten times the subject's 30-day baseline volume",
        negative="an export within the subject's normal baseline range",
        duplicate="the same export-requested event ID exported twice after a retry",
        delayed="a qualifying export event arriving late but timestamped inside the window",
        missing_field="an export-requested event without a destination field",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_008 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_008,
    version="1.0.0",
    name="Security Configuration Change",
    purpose="Alert on changes to identity, trust, policy, redaction, retention, or export config.",
    threat_or_compliance_hypothesis=(
        "A change to identity-provider configuration, trust anchors, policy minimums, "
        "redaction rules, retention settings, or Syslog/SIEM/guardrail configuration weakens "
        "or reconfigures a security control and warrants review regardless of intent."
    ),
    limitations=(
        "Most matches are legitimate, reviewed administrative changes; this detection is a "
        "change-visibility control, not itself evidence of misconfiguration."
    ),
    required_event_types=(
        "atlas.identity.provider_configuration_changed",
        "atlas.trust.anchor_changed",
        "atlas.policy.minimum_changed",
        "atlas.observability.redaction_rule_changed",
        "atlas.observability.retention_policy_changed",
        "atlas.security_export.destination_configuration_changed",
    ),
    required_fields=("subject_reference", "configuration_area", "change_summary"),
    query_logic_summary="Alert on every matching configuration-change event.",
    time_window="not applicable -- evaluated per event",
    thresholds="any matching event",
    grouping="by configuration area",
    suppression_behavior="none",
    expected_false_positives="a routine, reviewed administrative change",
    tuning_guidance="none -- every change is expected to be reviewed, not suppressed",
    severity=SecuritySeverity.MEDIUM,
    escalation_recommendation="review within one business day; escalate to high if the change "
    "weakens redaction, retention, or trust-anchor requirements",
    investigation_steps=(
        "confirm the change matches an approved change record",
        "review whether the change weakens or strengthens the affected control",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="a redaction-rule change removing a mandatory field from the redaction set",
        negative="a routine, reviewed retention-policy extension",
        duplicate="the same configuration-change event ID exported twice",
        delayed="a configuration-change event arriving late but correctly timestamped",
        missing_field="a configuration-change event without a change summary",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_009 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_009,
    version="1.0.0",
    name="Credential or Certificate Risk",
    purpose="Detect failing secret access, unexpected credential validation, or expiring trust.",
    threat_or_compliance_hypothesis=(
        "Failed secret access, unexpected connector credential validation, certificate expiry, "
        "trust failure, or repeated service-authentication rejection each indicate either an "
        "attacker probing credentials or an operational risk of imminent service failure."
    ),
    limitations=(
        "Certificate expiry is a forward-looking operational risk, not an active attack "
        "indicator; it is included here because it directly threatens transport security "
        "controls this detection set otherwise protects."
    ),
    required_event_types=(
        "atlas.secret.access_failed",
        "atlas.connector.credential_validation_failed",
        "atlas.trust.certificate_expiring",
        "atlas.service.authentication_rejected",
    ),
    required_fields=("resource_reference", "failure_reason"),
    query_logic_summary=(
        "Alert on any certificate expiring within 30 days; alert on 3+ secret-access failures "
        "or service-authentication rejections for the same resource reference within the window."
    ),
    time_window="1 hour for repeated-failure evaluation",
    thresholds="3 or more failures for the same resource reference, or a 30-day certificate expiry",
    grouping="by resource reference",
    suppression_behavior="suppress repeat certificate-expiry alerts once a renewal ticket is open",
    expected_false_positives="a service restart causing a brief burst of authentication retries",
    tuning_guidance="exclude a known restart window for a specific service reference",
    severity=SecuritySeverity.MEDIUM,
    escalation_recommendation="escalate to high if certificate expiry is under 7 days or failures "
    "exceed 10 in the window",
    investigation_steps=(
        "review the resource reference's recent credential rotation history",
        "confirm whether a service restart explains a failure burst",
        "check certificate renewal ticket status if expiry-related",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="a certificate expiring in 5 days with no open renewal ticket",
        negative="a certificate expiring in 90 days",
        duplicate="the same secret-access-failed event ID exported twice",
        delayed="a certificate-expiring event arriving late but correctly timestamped",
        missing_field="a credential-validation-failed event without a failure reason",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

SIEM_UC_010 = DetectionContentContract(
    detection_id=DetectionUseCaseId.SIEM_UC_010,
    version="1.0.0",
    name="Control-Plane Degradation",
    purpose="Correlate health failures across controls that together reduce safe Atlas operation.",
    threat_or_compliance_hypothesis=(
        "Authentication, authorization, policy, approval, audit, connector isolation, or "
        "model-guardrail health failures occurring together indicate systemic control-plane "
        "degradation, even if no single failure alone would be critical."
    ),
    limitations=(
        "This detection depends on each contributing control's own health signal being "
        "correctly reported; it cannot detect degradation in a control whose health reporting "
        "has itself silently failed."
    ),
    required_event_types=(
        "atlas.authentication.health_degraded",
        "atlas.authorization.health_degraded",
        "atlas.policy.health_degraded",
        "atlas.approvals.health_degraded",
        "atlas.audit.health_degraded",
        "atlas.connectors.isolation_health_degraded",
        "atlas.guardrails.health_degraded",
    ),
    required_fields=("component", "health_state"),
    query_logic_summary=(
        "Alert when 2 or more distinct control-plane components report a degraded health "
        "state within the correlation window."
    ),
    time_window="10 minutes",
    thresholds="2 or more distinct degraded components",
    grouping="by correlation window across components",
    suppression_behavior="suppress renewed alerts while the same component set remains degraded",
    expected_false_positives="a coordinated, announced maintenance affecting multiple components",
    tuning_guidance="exclude a specific, time-boxed, pre-announced maintenance window",
    severity=SecuritySeverity.CRITICAL,
    escalation_recommendation="page on-call immediately",
    investigation_steps=(
        "confirm whether an announced maintenance window covers the affected components",
        "review each contributing component's own health detail",
        "check whether any consequential operation proceeded during the degraded window",
    ),
    evidence_link_kinds=_EVIDENCE_LINK_KINDS,
    test_fixtures=_fixtures(
        positive="authorization and audit both report degraded health within the same 10 minutes",
        negative="a single component reporting degraded health with no other component affected",
        duplicate="the same health-degraded event ID exported twice",
        delayed="a second component's degraded-health event arriving late but inside the window",
        missing_field="a health-degraded event without a health state",
    ),
    owner=_OWNER,
    review_interval_days=_REVIEW_INTERVAL_DAYS,
    supported_schema_versions=_SCHEMA_VERSIONS,
    change_history=("1.0.0: initial specification",),
)

BASELINE_DETECTION_CATALOG: tuple[DetectionContentContract, ...] = (
    SIEM_UC_001,
    SIEM_UC_002,
    SIEM_UC_003,
    SIEM_UC_004,
    SIEM_UC_005,
    SIEM_UC_006,
    SIEM_UC_007,
    SIEM_UC_008,
    SIEM_UC_009,
    SIEM_UC_010,
)


def detection_by_id(detection_id: DetectionUseCaseId) -> DetectionContentContract:
    for contract in BASELINE_DETECTION_CATALOG:
        if contract.detection_id is detection_id:
            return contract
    raise KeyError(detection_id)
