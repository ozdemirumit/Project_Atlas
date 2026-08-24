import { afterEach, describe, expect, it, vi } from "vitest";

import { credentialAssignment as assignment } from "../features/connectors/testCredentialAssignmentFixture";
import { targetConfigurationBinding as binding } from "../features/connectors/testTargetBindingFixture";
import {
  createConnectorCredentialAssignment,
  getConnectorCredentialAssignmentOptions,
  getConnectorCredentialAssignments,
} from "./credentialAssignments";

const inventoryItem = {
  assignment_id: assignment.assignment_id,
  source_target_binding_id: assignment.source_target_binding_id,
  connector_id: assignment.connector_id,
  release_version: assignment.release_version,
  instance_id: assignment.instance_id,
  display_name: assignment.display_name,
  credential_profile_id: assignment.credential_profile_id,
  credential_profile_digest: assignment.credential_profile_digest,
  credential_class: assignment.credential_class,
  authentication_method: assignment.authentication_method,
  vendor_role: assignment.vendor_role,
  privilege_class: assignment.privilege_class,
  rotation_state: assignment.rotation_state,
  revocation_state: assignment.revocation_state,
  next_rotation_at: assignment.next_rotation_at,
  credential_policy_id: assignment.credential_policy_id,
  credential_policy_digest: assignment.credential_policy_digest,
  credential_policy_version: assignment.credential_policy_version,
  instance_state: assignment.instance_state,
  assigned_by: assignment.assigned_by,
  purpose: assignment.purpose,
  assigned_at: assignment.assigned_at,
  credential_references_assigned: true,
  eligible_for_configuration_validation: true,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
} as const;

const option = {
  source_target_binding_id: binding.binding_id,
  credential_profile_id: assignment.credential_profile_id,
  credential_profile_digest: assignment.credential_profile_digest,
  credential_class: assignment.credential_class,
  authentication_method: assignment.authentication_method,
  vendor_role: assignment.vendor_role,
  privilege_class: assignment.privilege_class,
  rotation_state: assignment.rotation_state,
  revocation_state: assignment.revocation_state,
  next_rotation_at: assignment.next_rotation_at,
  credential_profile_expires_at: "2030-01-01T00:00:00Z",
  credential_policy_id: assignment.credential_policy_id,
  credential_policy_digest: assignment.credential_policy_digest,
  credential_policy_version: assignment.credential_policy_version,
  credential_policy_expires_at: "2030-01-01T00:00:00Z",
  required_assurance_level: "SINGLE_FACTOR",
  resulting_instance_state: "disabled_credentials_assigned",
  resulting_credential_references_assigned: true,
  eligible_for_configuration_validation: true,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("credential assignment API client", () => {
  it("reloads assignments within the requested target-binding scope", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ data: [inventoryItem] }), { status: 200 }));

    const assignments = await getConnectorCredentialAssignments({
      sourceTargetBindingId: binding.binding_id,
    });

    expect(assignments).toHaveLength(1);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl =
      request instanceof Request ? request.url : request instanceof URL ? request.href : request;
    expect(requestUrl).toContain(
      `source_target_binding_id=${encodeURIComponent(binding.binding_id)}`,
    );
  });

  it("rejects options that expose hidden secret internals", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ data: [{ ...option, secret_reference_id: "secret-reference.test" }] }),
        { status: 200 },
      ),
    );

    await expect(getConnectorCredentialAssignmentOptions(binding.binding_id)).rejects.toThrow(
      "unsafe evidence",
    );
  });

  it("rejects assignment inventory that crosses the requested target scope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          data: [{ ...inventoryItem, source_target_binding_id: "target-binding.outside-scope" }],
        }),
        { status: 200 },
      ),
    );

    await expect(
      getConnectorCredentialAssignments({ sourceTargetBindingId: binding.binding_id }),
    ).rejects.toThrow("crossed the requested target scope");
  });

  it.each([401, 403, 404, 409])("preserves create response status %s", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status }));

    await expect(
      createConnectorCredentialAssignment({
        binding,
        credentialProfileId: option.credential_profile_id,
        credentialProfileDigest: option.credential_profile_digest,
        policyId: option.credential_policy_id,
        policyDigest: option.credential_policy_digest,
        purpose: "Assign governed credential metadata without runtime authority.",
      }),
    ).rejects.toEqual(expect.objectContaining({ name: "ApiRequestError", status }));
  });
});
