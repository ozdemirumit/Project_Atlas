export type GraphEvidence = {
  reference: string;
  source: string;
  source_version: string;
  observed_at: string;
  freshness: "fresh" | "aging" | "stale" | "unknown" | "expired";
  trust_basis: string;
  classification: string;
};

export type GraphEntity = {
  entity_id: string;
  entity_type:
    | "storage_system"
    | "volume"
    | "datastore"
    | "virtual_machine"
    | "technical_service"
    | "business_service";
  display_name: string;
  domain_id: string;
  observed_at: string;
  freshness: string;
  confidence_basis: string;
  evidence_references: string[];
  classification: string;
  vendor: string | null;
  product: string | null;
  model: string | null;
  lifecycle_state: string;
};

export type GraphRelationship = {
  relationship_id: string;
  relationship_type: "backed_by" | "uses" | "runs_on" | "depends_on";
  source_entity_id: string;
  target_entity_id: string;
  assertion_method: string;
  observed_at: string;
  freshness: string;
  confidence_basis: string;
  evidence_references: string[];
  classification: string;
};

export type ImpactPath = {
  scope: "direct" | "possible" | "unknown";
  entity_ids: string[];
  relationship_ids: string[];
  evidence_references: string[];
};

export type StorageImpact = {
  snapshot_id: string;
  snapshot_generated_at: string;
  start_entity_id: string;
  max_depth: number;
  freshness: string;
  completeness: string;
  entities: GraphEntity[];
  relationships: GraphRelationship[];
  paths: ImpactPath[];
  evidence: GraphEvidence[];
  direct_entity_ids: string[];
  possible_entity_ids: string[];
  technical_service_ids: string[];
  business_service_ids: string[];
  unknowns: string[];
  known_gaps: string[];
  outage_confirmed: boolean;
  digital_twin_maturity: string;
  data_profile: string;
  safety_notice: string;
};

type StorageImpactResponse = {
  data: StorageImpact;
  meta: {
    correlation_id: string;
    generated_at: string;
  };
};

export async function getStorageImpact(
  entityId: string,
): Promise<StorageImpactResponse> {
  const response = await fetch(
    `/api/v1/graph/storage-impact/${encodeURIComponent(entityId)}?max_depth=5`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`Storage impact request failed with ${response.status}`);
  }
  return (await response.json()) as StorageImpactResponse;
}
