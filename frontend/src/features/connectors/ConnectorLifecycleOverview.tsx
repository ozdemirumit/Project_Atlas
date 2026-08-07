import { CheckCircle2, CircleDashed, Database, ShieldCheck } from "lucide-react";

type LifecycleStage = {
  name: string;
  detail: string;
  state: "available" | "current" | "future";
  capabilities: readonly {
    name: string;
    state?: "available" | "pending";
  }[];
};

const lifecycleStages: readonly LifecycleStage[] = [
  {
    name: "Source and design",
    detail: "Analysis, design, generation, review",
    state: "available",
    capabilities: [
      { name: "OpenAPI intake" },
      { name: "Candidate generation" },
      { name: "Human review" },
    ],
  },
  {
    name: "Package assurance",
    detail: "Content, dependency, malware, license",
    state: "available",
    capabilities: [
      { name: "Content checks" },
      { name: "Dependency scan" },
      { name: "Malware scan" },
      { name: "License scan" },
    ],
  },
  {
    name: "Approval and registry",
    detail: "Attestation, signing, approval, publication",
    state: "available",
    capabilities: [
      { name: "Attestation" },
      { name: "Package signing" },
      { name: "Approval" },
      { name: "Registry publication" },
    ],
  },
  {
    name: "Installation and instance",
    detail: "Acquisition, installation, instance binding",
    state: "available",
    capabilities: [
      { name: "Package acquisition" },
      { name: "Installation" },
      { name: "Instance binding" },
    ],
  },
  {
    name: "Target and credentials",
    detail: "Configuration, assignment, validation",
    state: "available",
    capabilities: [
      { name: "Target configuration" },
      { name: "Credential assignment" },
      { name: "Validation" },
    ],
  },
  {
    name: "Runtime trust",
    detail: "Capability, workload, brokerage, activation",
    state: "available",
    capabilities: [
      { name: "Capability grant" },
      { name: "Workload identity" },
      { name: "Credential brokerage" },
      { name: "Activation" },
    ],
  },
  {
    name: "Bounded operations",
    detail: "Session, authorization, single-use read",
    state: "available",
    capabilities: [
      { name: "Session lease" },
      { name: "Step-up authorization" },
      { name: "Read-only invocation" },
    ],
  },
  {
    name: "Evidence preservation",
    detail: "Governed immutable ingestion",
    state: "available",
    capabilities: [
      { name: "Evidence capture" },
      { name: "Integrity validation" },
      { name: "Immutable storage" },
    ],
  },
  {
    name: "Knowledge publication",
    detail: "Curation, indexing, retrieval",
    state: "current",
    capabilities: [
      { name: "Draft curation" },
      { name: "Review request" },
      { name: "Reviewer assignment" },
      { name: "Inspection lease" },
      { name: "Content presentation" },
      { name: "Review findings" },
      { name: "Finding presentation" },
      { name: "Review decisions" },
      { name: "Correction resubmission" },
      { name: "Indexing", state: "pending" },
      { name: "Retrieval", state: "pending" },
    ],
  },
];

export function ConnectorLifecycleOverview() {
  return (
    <section className="connector-lifecycle" aria-labelledby="connector-lifecycle-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PLATFORM COVERAGE</p>
          <h2 id="connector-lifecycle-title">Connector lifecycle</h2>
        </div>
        <span className="state-badge neutral">
          <ShieldCheck size={14} /> governed boundaries
        </span>
      </div>
      <div className="connector-lifecycle-summary" aria-label="Delivery status">
        <div>
          <strong>8</strong>
          <span>Available stages</span>
        </div>
        <div>
          <strong>1</strong>
          <span>In progress</span>
        </div>
        <div>
          <strong>Correction resubmission</strong>
          <span>Latest available capability</span>
        </div>
      </div>
      <div className="connector-lifecycle-list">
        {lifecycleStages.map((stage, index) => (
          <div className="connector-lifecycle-row" data-state={stage.state} key={stage.name}>
            <span className="connector-lifecycle-index">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{stage.name}</strong>
              <span>{stage.detail}</span>
              <div className="connector-capability-list" aria-label={`${stage.name} capabilities`}>
                {stage.capabilities.map((capability) => (
                  <span
                    className="connector-capability"
                    data-state={capability.state ?? "available"}
                    key={capability.name}
                  >
                    {capability.name}
                  </span>
                ))}
              </div>
            </div>
            <span className="connector-lifecycle-state">
              {stage.state === "available" ? (
                <CheckCircle2 size={16} />
              ) : stage.state === "current" ? (
                <Database size={16} />
              ) : (
                <CircleDashed size={16} />
              )}
              {stage.state === "available"
                ? "Available"
                : stage.state === "current"
                  ? "In progress"
                  : "Not enabled"}
            </span>
          </div>
        ))}
      </div>
      <p className="connector-lifecycle-boundary">
        Availability is platform capability coverage, not authority for a connector instance.
      </p>
    </section>
  );
}
