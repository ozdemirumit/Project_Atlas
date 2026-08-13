import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Clock3,
  Database,
  FileKey2,
  FlaskConical,
  Link2,
  LogIn,
  Plus,
  Settings2,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import {
  assessItsmSandboxConformance,
  createItsmIntegrationProfile,
  getLatestItsmSandboxConformance,
  getItsmIntegrationProfiles,
  getItsmSandboxOnboardingReadiness,
  retireItsmIntegrationProfile,
  type CreateItsmIntegrationInput,
  type ItsmIntegrationProfile,
  type ItsmLifecycle,
  type ItsmProviderFamily,
  type ItsmSandboxConformanceAssessment,
} from "../../api/itsmIntegrations";

const PROVIDERS: Record<ItsmProviderFamily, string> = {
  service_now: "ServiceNow",
  jira_service_management: "Jira Service Management",
  generic_rest: "Generic REST",
};

const CHECK_LABELS: Record<string, string> = {
  "itsm.readiness.ownership": "Accountable owner",
  "itsm.readiness.network-trust": "Network and trust",
  "itsm.readiness.credential-reference": "Credential reference",
  "itsm.readiness.mapping": "Field mapping",
  "itsm.readiness.sandbox-validation": "Sandbox evidence",
  "itsm.readiness.audit": "Audit binding",
};

const ONBOARDING_LABELS: Record<string, string> = {
  "itsm.sandbox-onboarding.profile-current": "Active profile binding",
  "itsm.sandbox-onboarding.conformance-current": "Current conformance",
  "itsm.sandbox-onboarding.adapter-registered": "Adapter registration",
  "itsm.sandbox-onboarding.adapter-sandbox-approved": "Sandbox adapter approval",
  "itsm.sandbox-onboarding.workload-identity": "Workload identity",
  "itsm.sandbox-onboarding.credential-ownership": "Credential ownership",
  "itsm.sandbox-onboarding.network-trust": "Network and trust approval",
  "itsm.sandbox-onboarding.mapping-change-control": "Mapping change control",
  "itsm.sandbox-onboarding.rate-backpressure": "Rate limit and backpressure",
  "itsm.sandbox-onboarding.audit-routing": "Audit routing",
  "itsm.sandbox-onboarding.availability-recovery": "Availability and recovery",
  "itsm.sandbox-onboarding.owner-approvals": "Security and deployment approvals",
};

type LifecycleFilter = ItsmLifecycle | "all";

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

function CreateProfileDialog({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (input: CreateItsmIntegrationInput) => void;
}) {
  const [input, setInput] = useState<CreateItsmIntegrationInput>({
    profileKey: "",
    displayName: "",
    providerFamily: "generic_rest",
    instanceReference: "",
    ownerId: "",
    purpose: "",
    endpointOrigin: "",
    trustBoundaryReference: "",
    credentialReferenceId: "",
    auditProfileId: "",
    sandboxValidationReference: "",
    sandboxValidationDigest: "",
  });
  const [acknowledged, setAcknowledged] = useState(false);
  const stable = /^[a-z][a-z0-9_.:-]{2,127}$/;
  const sandboxPair =
    (!input.sandboxValidationReference && !input.sandboxValidationDigest) ||
    (stable.test(input.sandboxValidationReference) &&
      /^[a-f0-9]{64}$/.test(input.sandboxValidationDigest));
  const valid =
    stable.test(input.profileKey) &&
    input.displayName.trim().length >= 3 &&
    stable.test(input.instanceReference) &&
    stable.test(input.ownerId) &&
    input.purpose.trim().length >= 20 &&
    /^https:\/\/[^/?#]+\/?$/.test(input.endpointOrigin.trim()) &&
    stable.test(input.trustBoundaryReference) &&
    /^secret\.[a-z0-9_.:-]{2,120}$/.test(input.credentialReferenceId) &&
    stable.test(input.auditProfileId) &&
    sandboxPair &&
    acknowledged;

  function update<K extends keyof CreateItsmIntegrationInput>(
    key: K,
    value: CreateItsmIntegrationInput[K],
  ) {
    setInput((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !pending) onSubmit(input);
  }

  return (
    <div
      className="inventory-device-dialog itsm-profile-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-itsm-profile-title"
    >
      <form onSubmit={submit}>
        <div className="inventory-device-dialog-heading">
          <div>
            <p className="eyebrow">CONFIGURATION PROFILE</p>
            <h3 id="add-itsm-profile-title">Register ITSM sandbox profile</h3>
          </div>
          <button className="icon-button" type="button" aria-label="Close profile form" onClick={onCancel}>
            <X size={17} />
          </button>
        </div>
        <div className="inventory-device-form-grid">
          <label>
            Profile key
            <input autoFocus required value={input.profileKey} placeholder="itsm.sandbox.primary" onChange={(event) => update("profileKey", event.target.value.toLowerCase())} />
          </label>
          <label>
            Display name
            <input required maxLength={160} value={input.displayName} onChange={(event) => update("displayName", event.target.value)} />
          </label>
          <label>
            Provider family
            <select value={input.providerFamily} onChange={(event) => update("providerFamily", event.target.value as ItsmProviderFamily)}>
              {Object.entries(PROVIDERS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>
            Instance reference
            <input required value={input.instanceReference} placeholder="itsm-instance.sandbox.primary" onChange={(event) => update("instanceReference", event.target.value.toLowerCase())} />
          </label>
          <label>
            Accountable owner
            <input required value={input.ownerId} placeholder="team.service-management" onChange={(event) => update("ownerId", event.target.value.toLowerCase())} />
          </label>
          <label>
            Trust boundary
            <input required value={input.trustBoundaryReference} placeholder="trust-boundary.itsm.sandbox" onChange={(event) => update("trustBoundaryReference", event.target.value.toLowerCase())} />
          </label>
          <label className="inventory-device-form-wide">
            HTTPS endpoint origin
            <input required type="url" value={input.endpointOrigin} placeholder="https://itsm-sandbox.example.net" onChange={(event) => update("endpointOrigin", event.target.value)} />
          </label>
          <label>
            Credential broker reference
            <input required value={input.credentialReferenceId} placeholder="secret.itsm.sandbox.writer" onChange={(event) => update("credentialReferenceId", event.target.value.toLowerCase())} />
          </label>
          <label>
            Audit profile
            <input required value={input.auditProfileId} placeholder="audit-profile.itsm.sandbox" onChange={(event) => update("auditProfileId", event.target.value.toLowerCase())} />
          </label>
          <label>
            Sandbox evidence reference
            <input value={input.sandboxValidationReference} placeholder="validation.itsm.sandbox.001" onChange={(event) => update("sandboxValidationReference", event.target.value.toLowerCase())} />
          </label>
          <label>
            Sandbox evidence SHA-256
            <input value={input.sandboxValidationDigest} maxLength={64} placeholder="64 lowercase hex characters" onChange={(event) => update("sandboxValidationDigest", event.target.value.toLowerCase())} />
          </label>
          <label className="inventory-device-form-wide">
            Configuration purpose
            <textarea required rows={3} minLength={20} maxLength={1000} value={input.purpose} onChange={(event) => update("purpose", event.target.value)} />
          </label>
        </div>
        <div className="itsm-fixed-mapping-note">
          <Settings2 size={16} />
          <span>Atlas registers the approved append-only work notes and report/review reference mapping set.</span>
        </div>
        <label className="inventory-device-acknowledgement">
          <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
          <span>This stores configuration only. It does not contact the endpoint, mutate a ticket, or authorize dispatch.</span>
        </label>
        <div className="inventory-device-dialog-actions">
          <button type="button" disabled={pending} onClick={onCancel}>Cancel</button>
          <button className="inventory-device-primary" type="submit" disabled={!valid || pending}>
            {pending ? <Clock3 size={15} /> : <Plus size={15} />} Register profile
          </button>
        </div>
      </form>
    </div>
  );
}

function RetireProfileDialog({
  profile,
  pending,
  onCancel,
  onSubmit,
}: {
  profile: ItsmIntegrationProfile;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const valid = reason.trim().length >= 20 && acknowledged;
  return (
    <div className="inventory-device-dialog retirement" role="dialog" aria-modal="true" aria-labelledby="retire-itsm-profile-title">
      <form onSubmit={(event) => { event.preventDefault(); if (valid && !pending) onSubmit(reason); }}>
        <div className="inventory-device-dialog-heading">
          <div><p className="eyebrow">PROFILE LIFECYCLE</p><h3 id="retire-itsm-profile-title">Retire {profile.display_name}</h3></div>
          <button className="icon-button" type="button" aria-label="Close retirement form" onClick={onCancel}><X size={17} /></button>
        </div>
        <div className="inventory-device-retirement-impact"><Archive size={18} /><p>The profile remains auditable and stops participating in readiness inventory. No external ITSM record is changed.</p></div>
        <label>Retirement reason<textarea autoFocus rows={4} minLength={20} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <label className="inventory-device-acknowledgement"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>Preserve profile history and confirm that no dispatch capability exists.</span></label>
        <div className="inventory-device-dialog-actions"><button type="button" disabled={pending} onClick={onCancel}>Cancel</button><button className="inventory-device-retire" type="submit" disabled={!valid || pending}>{pending ? <Clock3 size={15} /> : <Archive size={15} />} Retire profile</button></div>
      </form>
    </div>
  );
}

function SandboxConformanceDialog({
  profile,
  pending,
  onCancel,
  onSubmit,
}: {
  profile: ItsmIntegrationProfile;
  pending: boolean;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  return (
    <div className="inventory-device-dialog" role="dialog" aria-modal="true" aria-labelledby="assess-itsm-sandbox-title">
      <form onSubmit={(event) => { event.preventDefault(); if (acknowledged && !pending) onSubmit(); }}>
        <div className="inventory-device-dialog-heading">
          <div><p className="eyebrow">BOUNDED DIAGNOSTIC</p><h3 id="assess-itsm-sandbox-title">Assess {profile.display_name}</h3></div>
          <button className="icon-button" type="button" aria-label="Close sandbox assessment" onClick={onCancel}><X size={17} /></button>
        </div>
        <div className="inventory-device-retirement-impact"><FlaskConical size={18} /><p>The fixed diagnostic is bound to profile version {profile.version}. Endpoint overrides, custom payloads, ticket writes, and dispatch are unavailable.</p></div>
        <label className="inventory-device-acknowledgement"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>This assessment is diagnostic evidence only and grants no production, dispatch, workflow, or execution authority.</span></label>
        <div className="inventory-device-dialog-actions"><button type="button" disabled={pending} onClick={onCancel}>Cancel</button><button className="inventory-device-primary" type="submit" disabled={!acknowledged || pending}>{pending ? <Clock3 size={15} /> : <FlaskConical size={15} />} Run diagnostic</button></div>
      </form>
    </div>
  );
}

export default function ItsmIntegrationReadinessWorkspace({
  governedSessionAvailable = true,
  onRequestEnterpriseLogin,
}: {
  governedSessionAvailable?: boolean;
  onRequestEnterpriseLogin?: () => void;
}) {
  const queryClient = useQueryClient();
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("active");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [retiring, setRetiring] = useState<ItsmIntegrationProfile | null>(null);
  const [assessing, setAssessing] = useState<ItsmIntegrationProfile | null>(null);
  const inventoryQuery = useQuery({
    queryKey: ["itsm-integration-profiles", lifecycle],
    queryFn: () => getItsmIntegrationProfiles(lifecycle),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["itsm-integration-profiles"] });
  const createMutation = useMutation({
    mutationFn: createItsmIntegrationProfile,
    onSuccess: async (profile) => { setCreating(false); setLifecycle("active"); setSelectedId(profile.profile_id); await refresh(); },
  });
  const retireMutation = useMutation({
    mutationFn: ({ profile, reason }: { profile: ItsmIntegrationProfile; reason: string }) => retireItsmIntegrationProfile({ profile, reason }),
    onSuccess: async () => { setRetiring(null); await refresh(); },
  });
  const inventory = inventoryQuery.data;
  const selected = inventory?.profiles.find((profile) => profile.profile_id === selectedId) ?? inventory?.profiles[0];
  const conformanceQuery = useQuery({
    queryKey: ["itsm-sandbox-conformance", selected?.profile_id],
    queryFn: () => getLatestItsmSandboxConformance(selected!.profile_id),
    enabled: Boolean(selected),
  });
  const conformanceMutation = useMutation({
    mutationFn: assessItsmSandboxConformance,
    onSuccess: (assessment: ItsmSandboxConformanceAssessment) => {
      queryClient.setQueryData(
        ["itsm-sandbox-conformance", assessment.profile_id],
        assessment,
      );
      void queryClient.invalidateQueries({
        queryKey: ["itsm-sandbox-onboarding", assessment.profile_id],
      });
      setAssessing(null);
    },
  });
  const onboardingQuery = useQuery({
    queryKey: ["itsm-sandbox-onboarding", selected?.profile_id],
    queryFn: () => getItsmSandboxOnboardingReadiness(selected!.profile_id),
    enabled: Boolean(selected),
  });

  return (
    <section className="workspace-section itsm-readiness-workspace" aria-labelledby="itsm-readiness-title">
      <div className="section-heading inventory-device-heading">
        <div><p className="eyebrow">ITSM ADAPTER READINESS</p><h2 id="itsm-readiness-title">Sandbox integration profiles</h2><p>Provider-neutral configuration, mappings, and deterministic readiness blockers.</p></div>
        <div className="inventory-device-heading-actions">
          {inventory && <span className={`inventory-persistence ${inventory.durable ? "durable" : "memory"}`}><Database size={14} /> {inventory.durable ? "Durable store" : "Development memory"}</span>}
          <button type="button" disabled={!governedSessionAvailable} title={governedSessionAvailable ? "Register ITSM profile" : "Signed browser session required"} onClick={() => { createMutation.reset(); setCreating(true); }}><Plus size={15} /> Add profile</button>
        </div>
      </div>

      <div className="inventory-device-toolbar">
        <div className="inventory-device-segments" role="group" aria-label="ITSM profile lifecycle filter">
          {(["active", "retired", "all"] as const).map((value) => <button key={value} type="button" aria-pressed={lifecycle === value} onClick={() => { setLifecycle(value); setSelectedId(null); }}>{value === "all" ? "All" : value.charAt(0).toUpperCase() + value.slice(1)}</button>)}
        </div>
        <div className="itsm-authority-boundary"><ShieldCheck size={15} /><span>Configuration only</span></div>
      </div>

      {!governedSessionAvailable && <div className="inventory-device-status enterprise-login-required" role="status"><LogIn size={17} /><div><strong>Signed browser session required for profile lifecycle changes</strong><span>Readiness remains visible; registration and retirement stay protected.</span></div>{onRequestEnterpriseLogin && <button type="button" onClick={onRequestEnterpriseLogin}><LogIn size={15} /> Sign in to manage</button>}</div>}
      {inventoryQuery.isLoading && <div className="inventory-device-status"><Clock3 size={17} /> Loading ITSM profile inventory</div>}
      {inventoryQuery.isError && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> ITSM integration inventory is unavailable.</div>}
      {createMutation.isError && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> Profile registration failed. Review identifiers, sandbox evidence, and the unique profile key.</div>}
      {retireMutation.isError && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> Profile retirement failed. Refresh and review the current version.</div>}
      {conformanceQuery.isError && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> Sandbox conformance evidence is unavailable.</div>}
      {conformanceMutation.isError && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> The bounded sandbox diagnostic could not be completed.</div>}
      {onboardingQuery.isError && <div className="inventory-device-status error-state" role="alert"><AlertTriangle size={17} /> Sandbox adapter onboarding readiness is unavailable.</div>}

      {inventory?.profiles.length === 0 && <div className="inventory-device-empty"><Link2 size={20} /><div><strong>No ITSM profiles in this lifecycle</strong><p>Register a provider-neutral sandbox profile to evaluate readiness.</p></div></div>}
      {inventory && inventory.profiles.length > 0 && <div className="table-wrap inventory-device-table-wrap"><table className="inventory-device-table itsm-profile-table"><thead><tr><th>Profile</th><th>Provider</th><th>Readiness</th><th>Lifecycle</th><th>Updated</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{inventory.profiles.map((profile) => <tr key={profile.profile_id} className={selected?.profile_id === profile.profile_id ? "selected" : undefined} onClick={() => setSelectedId(profile.profile_id)}><td><div className="inventory-device-identity"><Link2 size={17} /><span><strong>{profile.display_name}</strong><code>{profile.profile_key}</code></span></div></td><td>{PROVIDERS[profile.provider_family]}</td><td><span className={`itsm-readiness-state ${profile.readiness.state}`}>{profile.readiness.state === "ready_for_sandbox" ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}{profile.readiness.state === "ready_for_sandbox" ? "Sandbox ready" : "Blocked"}</span></td><td><span className={`inventory-device-lifecycle ${profile.lifecycle}`}>{profile.lifecycle === "active" ? <CheckCircle2 size={14} /> : <Archive size={14} />}{profile.lifecycle}</span></td><td>{formatTimestamp(profile.updated_at)}</td><td>{profile.lifecycle === "active" && <button className="inventory-device-row-action" type="button" disabled={!governedSessionAvailable} title="Retire profile" aria-label={`Retire ${profile.display_name}`} onClick={(event) => { event.stopPropagation(); retireMutation.reset(); setRetiring(profile); }}><Archive size={16} /></button>}</td></tr>)}</tbody></table></div>}

      {selected && <div className="itsm-readiness-detail"><div className="itsm-readiness-summary"><div><span>Endpoint origin</span><strong>{selected.endpoint_origin}</strong></div><div><span>Accountable owner</span><strong>{selected.owner_id}</strong></div><div><span>Credential binding</span><strong><FileKey2 size={15} /> Configured reference</strong></div><div><span>Mapping contract</span><strong>Version {selected.mapping_version}</strong></div></div><div className="itsm-readiness-checks" aria-label="ITSM readiness checks">{selected.readiness.checks.map((check) => <div key={check.check_id} className={check.state}><span>{check.state === "satisfied" ? <CheckCircle2 size={16} /> : <XCircle size={16} />}{CHECK_LABELS[check.check_id] ?? check.check_id}</span><small>{check.state === "satisfied" ? "Satisfied" : check.reason_code.split(".").at(-1)?.replaceAll("_", " ")}</small></div>)}</div><div className="itsm-mapping-table"><div className="itsm-detail-heading"><div><p className="eyebrow">ALLOWLISTED FIELD CONTRACT</p><h3>Mapping version {selected.mapping_version}</h3></div><span>{selected.field_mappings.length} fields</span></div><table><thead><tr><th>Atlas source</th><th>Provider field</th><th>Semantics</th></tr></thead><tbody>{selected.field_mappings.map((mapping) => <tr key={mapping.source_field}><td><code>{mapping.source_field}</code></td><td><code>{mapping.provider_field}</code></td><td>{mapping.write_semantics === "append_only" ? "Append only" : "Reference only"}</td></tr>)}</tbody></table></div><div className="inventory-device-boundary"><ShieldCheck size={15} /><span>Readiness does not authorize dispatch, ticket mutation, workflow approval, or infrastructure execution.</span></div></div>}

      {selected && <div className="itsm-conformance-panel"><div className="itsm-detail-heading"><div><p className="eyebrow">SANDBOX CONFORMANCE</p><h3>Bounded adapter diagnostic</h3></div><button type="button" disabled={!governedSessionAvailable || selected.lifecycle !== "active" || conformanceMutation.isPending} title="Run fixed sandbox diagnostic" onClick={() => { conformanceMutation.reset(); setAssessing(selected); }}><FlaskConical size={15} /> Assess sandbox</button></div>{conformanceQuery.isLoading && <div className="inventory-device-status"><Clock3 size={16} /> Loading latest assessment</div>}{!conformanceQuery.isLoading && !conformanceQuery.data && <div className="inventory-device-empty compact"><FlaskConical size={18} /><div><strong>No conformance assessment</strong><p>The profile has no short-lived adapter diagnostic evidence.</p></div></div>}{conformanceQuery.data && <div className="itsm-conformance-evidence"><div><span>Outcome</span><strong className={conformanceQuery.data.state === "conformant" ? "conformant" : "blocked"}>{conformanceQuery.data.state === "conformant" ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}{conformanceQuery.data.state.replaceAll("_", " ")}</strong></div><div><span>Adapter</span><code>{conformanceQuery.data.adapter_id}</code></div><div><span>Profile binding</span><strong>Version {conformanceQuery.data.profile_version} / mapping {conformanceQuery.data.mapping_version}</strong></div><div><span>Valid until</span><strong>{formatTimestamp(conformanceQuery.data.valid_until)}</strong></div></div>}<div className="inventory-device-boundary"><ShieldCheck size={15} /><span>Conformance is diagnostic evidence only. Production readiness, dispatch, external mutation, workflow approval, and execution remain unavailable.</span></div></div>}

      {selected && <div className="itsm-conformance-panel itsm-onboarding-panel"><div className="itsm-detail-heading"><div><p className="eyebrow">SANDBOX ADAPTER ONBOARDING</p><h3>Deployment readiness dossier</h3></div>{onboardingQuery.data && <span className={`itsm-readiness-state ${onboardingQuery.data.state === "ready" ? "ready_for_sandbox" : "blocked"}`}>{onboardingQuery.data.state === "ready" ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}{onboardingQuery.data.state === "ready" ? "Onboarding ready" : "Fail closed"}</span>}</div>{onboardingQuery.isLoading && <div className="inventory-device-status"><Clock3 size={16} /> Evaluating authoritative deployment evidence</div>}{onboardingQuery.data && <><div className="itsm-conformance-evidence"><div><span>Policy</span><code>{onboardingQuery.data.policy_id} / v{onboardingQuery.data.policy_version}</code></div><div><span>Policy issuer</span><code>{onboardingQuery.data.policy_issuer}</code></div><div><span>Policy expires</span><strong>{formatTimestamp(onboardingQuery.data.policy_expires_at)}</strong></div><div><span>Policy digest</span><code>{onboardingQuery.data.policy_digest.slice(0, 20)}...</code></div><div><span>Profile binding</span><strong>Version {onboardingQuery.data.profile_version} / mapping {onboardingQuery.data.mapping_version}</strong></div><div><span>Adapter</span><code>{onboardingQuery.data.adapter_id ?? "Not evidenced"}</code></div><div><span>Evidence valid until</span><strong>{onboardingQuery.data.evidence_valid_until ? formatTimestamp(onboardingQuery.data.evidence_valid_until) : "Not available"}</strong></div></div><div className="itsm-onboarding-requirements" aria-label="ITSM sandbox onboarding requirements">{onboardingQuery.data.requirements.map((requirement) => <div key={requirement.requirement_id} className={requirement.state}><span>{requirement.state === "satisfied" ? <CheckCircle2 size={16} /> : <XCircle size={16} />}{ONBOARDING_LABELS[requirement.requirement_id] ?? requirement.requirement_id}</span><small>{requirement.state === "satisfied" ? "Satisfied" : requirement.reason_code.split(".").at(-1)?.replaceAll("_", " ")}</small></div>)}</div></>}<div className="inventory-device-boundary"><ShieldCheck size={15} /><span>This dossier is read-only evidence. It cannot configure an adapter, contact a provider, dispatch a record, approve a workflow, or execute infrastructure changes.</span></div></div>}

      {creating && <CreateProfileDialog pending={createMutation.isPending} onCancel={() => setCreating(false)} onSubmit={(input) => createMutation.mutate(input)} />}
      {retiring && <RetireProfileDialog profile={retiring} pending={retireMutation.isPending} onCancel={() => setRetiring(null)} onSubmit={(reason) => retireMutation.mutate({ profile: retiring, reason })} />}
      {assessing && <SandboxConformanceDialog profile={assessing} pending={conformanceMutation.isPending} onCancel={() => setAssessing(null)} onSubmit={() => conformanceMutation.mutate(assessing)} />}
    </section>
  );
}
