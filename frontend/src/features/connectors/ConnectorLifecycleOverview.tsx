import { CheckCircle2, CircleDashed, Database, ShieldCheck } from "lucide-react";

type LifecycleStage = {
  name: string;
  detail: string;
  state: "available" | "current" | "future";
};

const lifecycleStages: readonly LifecycleStage[] = [
  { name: "Source and design", detail: "Analysis, design, generation, review", state: "available" },
  { name: "Package assurance", detail: "Content, dependency, malware, license", state: "available" },
  { name: "Approval and registry", detail: "Attestation, signing, approval, publication", state: "available" },
  { name: "Installation and instance", detail: "Acquisition, installation, instance binding", state: "available" },
  { name: "Target and credentials", detail: "Configuration, assignment, validation", state: "available" },
  { name: "Runtime trust", detail: "Capability, workload, brokerage, activation", state: "available" },
  { name: "Bounded operations", detail: "Session, authorization, single-use read", state: "available" },
  { name: "Evidence preservation", detail: "Governed immutable ingestion", state: "available" },
  { name: "Knowledge publication", detail: "Curation, indexing, retrieval", state: "future" },
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
      <div className="connector-lifecycle-list">
        {lifecycleStages.map((stage, index) => (
          <div className="connector-lifecycle-row" data-state={stage.state} key={stage.name}>
            <span className="connector-lifecycle-index">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{stage.name}</strong>
              <span>{stage.detail}</span>
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
