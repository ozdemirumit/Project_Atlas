from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.domain.models import ConnectorHealth, ConnectorInstance
from atlas.modules.connectors.vendors.commvault.domain import (
    CommvaultBrowseResult,
    CommvaultClientListResult,
    CommvaultClientRecord,
    CommvaultJob,
    CommvaultJobListResult,
    CommvaultRecoveryPoint,
    CommvaultStoragePolicy,
    CommvaultStoragePolicyListResult,
    CommvaultSubclient,
    CommvaultSubclientListResult,
    job_status_from_value,
)
from atlas.modules.connectors.vendors.commvault.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.commvault.ports import (
    CommvaultTransport,
    CommvaultTransportError,
)

_JOB_PATH_TEMPLATE = (
    "/webservice/Job?jobFilter=backup&jobCategory=All&completedJobLookupTime={lookup_seconds}"
)
_CLIENT_PATH = "/webservice/Client"
_STORAGE_POLICY_PATH = "/webservice/V2/StoragePolicy"
_STORAGE_POLICY_DETAIL_PATH_TEMPLATE = "/webservice/V2/StoragePolicy/{policy_id}?propertyLevel=10"
_SUBCLIENT_PATH_TEMPLATE = "/webservice/Subclient?clientId={client_id}"
_SUBCLIENT_BROWSE_PATH_TEMPLATE = "/webservice/Subclient/{subclient_id}/Browse?path=%5C"
_SAFE_NUMERIC_ID = re.compile(r"^[0-9]{1,10}$")


class CommvaultConnectorError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool = False) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class CommvaultClient:
    """Reads one exact, pre-bound Commvault CommServe's recent backup job status, registered
    client inventory, and storage policy inventory. There is no allowlist of many targets: the
    transport is bound to one CommServe management endpoint, and this client's job is only to
    parse and bound that one CommServe's responses safely."""

    def __init__(
        self,
        *,
        transport: CommvaultTransport,
        clock: Callable[[], datetime] | None = None,
        completed_job_lookup_seconds: int = 86_400,
        maximum_jobs: int = 1024,
        maximum_clients: int = 4096,
        maximum_policies: int = 1024,
        maximum_subclients: int = 1024,
        maximum_recovery_points: int = 1024,
        maximum_response_bytes: int = 1_048_576,
    ) -> None:
        if (
            maximum_jobs < 1
            or maximum_clients < 1
            or maximum_policies < 1
            or maximum_subclients < 1
            or maximum_recovery_points < 1
            or maximum_response_bytes < 1
            or completed_job_lookup_seconds < 1
        ):
            raise ValueError("connector collection limits must be positive")
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._completed_job_lookup_seconds = completed_job_lookup_seconds
        self._maximum_jobs = maximum_jobs
        self._maximum_clients = maximum_clients
        self._maximum_policies = maximum_policies
        self._maximum_subclients = maximum_subclients
        self._maximum_recovery_points = maximum_recovery_points
        self._maximum_response_bytes = maximum_response_bytes
        self._job_path = _JOB_PATH_TEMPLATE.format(lookup_seconds=completed_job_lookup_seconds)

    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        if instance.package_id != PACKAGE_ID:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.INCOMPATIBLE,
                checked_at=self._clock(),
                code="connector_instance_package_mismatch",
            )
        try:
            payload = await self._get(self._job_path)
        except CommvaultConnectorError as exc:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.UNAVAILABLE,
                checked_at=self._clock(),
                code=exc.code,
            )
        compatible = isinstance(payload.get("jobs"), list)
        return ConnectorSelfTestResult(
            health=ConnectorHealth.HEALTHY if compatible else ConnectorHealth.INCOMPATIBLE,
            checked_at=self._clock(),
            code="commvault_api_compatible" if compatible else "product_mismatch",
        )

    async def read_job_status(self) -> CommvaultJobListResult:
        payload = await self._get(self._job_path)
        raw_jobs = payload.get("jobs")
        if not isinstance(raw_jobs, list):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The job list response is malformed."
            )
        if len(raw_jobs) > self._maximum_jobs:
            raise CommvaultConnectorError(
                "vendor_response_limit_exceeded", "The job list response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("Job", payload),)
        jobs = tuple(self._parse_job(item) for item in raw_jobs)
        return CommvaultJobListResult(
            jobs=jobs, observed_at=observed_at, evidence_references=evidence
        )

    @staticmethod
    def _parse_job(value: object) -> CommvaultJob:
        if not isinstance(value, Mapping):
            raise CommvaultConnectorError("malformed_vendor_response", "A job item is malformed.")
        summary = value.get("jobSummary")
        if not isinstance(summary, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A job item is missing its summary."
            )
        job_id = summary.get("jobId")
        status = summary.get("status")
        job_type = summary.get("jobType")
        percent_complete = summary.get("percentComplete")
        subclient_name = summary.get("subclientName")
        client_name = summary.get("destClientName")
        if client_name is None:
            subclient = summary.get("subclient")
            if isinstance(subclient, Mapping):
                client_name = subclient.get("clientName")
        if (
            not isinstance(job_id, int)
            or isinstance(job_id, bool)
            or not isinstance(job_type, str)
            or not isinstance(percent_complete, int)
            or isinstance(percent_complete, bool)
            or not isinstance(subclient_name, str)
            or not isinstance(client_name, str)
        ):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A job item has invalid fields."
            )
        try:
            return CommvaultJob(
                job_id=job_id,
                client_name=client_name,
                subclient_name=subclient_name,
                job_type=job_type,
                status=job_status_from_value(status),
                percent_complete=percent_complete,
            )
        except ValueError as exc:
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A job item failed validation."
            ) from exc

    async def read_client_inventory(self) -> CommvaultClientListResult:
        payload = await self._get(_CLIENT_PATH)
        raw_clients = payload.get("clientProperties")
        if not isinstance(raw_clients, list):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The client list response is malformed."
            )
        if len(raw_clients) > self._maximum_clients:
            raise CommvaultConnectorError(
                "vendor_response_limit_exceeded", "The client list response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("Client", payload),)
        clients = tuple(self._parse_client(item) for item in raw_clients)
        return CommvaultClientListResult(
            clients=clients, observed_at=observed_at, evidence_references=evidence
        )

    async def read_storage_policies(self) -> CommvaultStoragePolicyListResult:
        payload = await self._get(_STORAGE_POLICY_PATH)
        raw_policies = payload.get("policies")
        if not isinstance(raw_policies, list):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The storage policy response is malformed."
            )
        if len(raw_policies) > self._maximum_policies:
            raise CommvaultConnectorError(
                "vendor_response_limit_exceeded", "The storage policy response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("V2/StoragePolicy", payload),)
        policies = tuple(self._parse_storage_policy(item) for item in raw_policies)
        return CommvaultStoragePolicyListResult(
            policies=policies, observed_at=observed_at, evidence_references=evidence
        )

    @staticmethod
    def _parse_client(value: object) -> CommvaultClientRecord:
        if not isinstance(value, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A client item is malformed."
            )
        client = value.get("client")
        if not isinstance(client, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A client item is missing its identity."
            )
        client_entity = client.get("clientEntity")
        if not isinstance(client_entity, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A client item is missing its identity."
            )
        client_id = client_entity.get("clientId")
        client_name = client_entity.get("clientName")
        host_name = client_entity.get("hostName")
        if (
            not isinstance(client_id, int)
            or isinstance(client_id, bool)
            or not isinstance(client_name, str)
            or not isinstance(host_name, str)
        ):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A client item has invalid fields."
            )

        # Not confirmed present on this list endpoint's documented response (only the
        # single-client `GET Client/{clientId}` endpoint's table carries them) -- parsed
        # defensively rather than required, see CommvaultClientRecord's docstring.
        os_info = client.get("osInfo")
        os_type = os_info.get("Type") if isinstance(os_info, Mapping) else None
        if not isinstance(os_type, str):
            os_type = None
        client_props = value.get("clientProps")
        is_deleted = (
            client_props.get("IsDeletedClient") if isinstance(client_props, Mapping) else None
        )
        if not isinstance(is_deleted, bool):
            is_deleted = None
        try:
            return CommvaultClientRecord(
                client_id=str(client_id),
                client_name=client_name,
                host_name=host_name,
                os_type=os_type,
                is_deleted=is_deleted,
            )
        except ValueError as exc:
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A client item failed validation."
            ) from exc

    @staticmethod
    def _parse_storage_policy(value: object) -> CommvaultStoragePolicy:
        if not isinstance(value, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A storage policy item is malformed."
            )
        storage_policy = value.get("storagePolicy")
        if not isinstance(storage_policy, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A storage policy item is missing its identity."
            )
        policy_id = storage_policy.get("storagePolicyId")
        policy_name = storage_policy.get("storagePolicyName")
        number_of_streams = value.get("numberOfStreams")
        if (
            not isinstance(policy_id, int)
            or isinstance(policy_id, bool)
            or not isinstance(policy_name, str)
            or not isinstance(number_of_streams, int)
            or isinstance(number_of_streams, bool)
        ):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A storage policy item has invalid fields."
            )
        # `numberOfCopies` is not confirmed present on this list endpoint's documented response
        # (its literal example response carries only `numberOfStreams` alongside the nested
        # `storagePolicy` identity) -- read via the bounded per-policy Details call instead, see
        # `read_storage_policy_copy_count()`.
        try:
            return CommvaultStoragePolicy(
                policy_id=str(policy_id),
                policy_name=policy_name,
                number_of_copies=None,
                number_of_streams=number_of_streams,
            )
        except ValueError as exc:
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A storage policy item failed validation."
            ) from exc

    async def read_storage_policy_copy_count(self, policy_id: str) -> int:
        """Reads one storage policy's confirmed real `numberOfCopies` via the Details endpoint
        (`GET V2/StoragePolicy/{id}?propertyLevel=10`), whose literal example response carries
        `numberOfCopies` directly on the `policies` element -- unlike the plain list endpoint.
        Bounded to one policy per call; the caller is responsible for bounding how many policies
        it enriches this way."""

        if not _SAFE_NUMERIC_ID.match(policy_id):
            raise CommvaultConnectorError(
                "invalid_target_identifier", "The storage policy id is not safe to interpolate."
            )
        path = _STORAGE_POLICY_DETAIL_PATH_TEMPLATE.format(policy_id=policy_id)
        payload = await self._get(path)
        policies = payload.get("policies")
        if isinstance(policies, list):
            policies = policies[0] if policies else None
        if not isinstance(policies, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The storage policy details response is malformed."
            )
        number_of_copies = policies.get("numberOfCopies")
        if not isinstance(number_of_copies, int) or isinstance(number_of_copies, bool):
            raise CommvaultConnectorError(
                "malformed_vendor_response",
                "The storage policy details response is missing numberOfCopies.",
            )
        return number_of_copies

    async def read_subclients(self, client_id: str) -> CommvaultSubclientListResult:
        """Reads one client's subclients via `GET webservice/Subclient?clientId={id}` -- the
        confirmed prerequisite for browsing that client's backed-up data (subclients are the
        confirmed real target of the Browse operation, not clients directly)."""

        if not _SAFE_NUMERIC_ID.match(client_id):
            raise CommvaultConnectorError(
                "invalid_target_identifier", "The client id is not safe to interpolate."
            )
        path = _SUBCLIENT_PATH_TEMPLATE.format(client_id=client_id)
        payload = await self._get(path)
        raw_subclients = payload.get("subClientProperties")
        if not isinstance(raw_subclients, list):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The subclient list response is malformed."
            )
        if len(raw_subclients) > self._maximum_subclients:
            raise CommvaultConnectorError(
                "vendor_response_limit_exceeded", "The subclient list response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence(f"Subclient?clientId={client_id}", payload),)
        subclients = tuple(self._parse_subclient(item) for item in raw_subclients)
        return CommvaultSubclientListResult(
            subclients=subclients, observed_at=observed_at, evidence_references=evidence
        )

    @staticmethod
    def _parse_subclient(value: object) -> CommvaultSubclient:
        if not isinstance(value, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A subclient item is malformed."
            )
        entity = value.get("subClientEntity")
        if not isinstance(entity, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A subclient item is missing its identity."
            )
        subclient_id = entity.get("subclientId")
        subclient_name = entity.get("subclientName")
        client_id = entity.get("clientId")
        app_name = entity.get("appName")
        if (
            not isinstance(subclient_id, int)
            or isinstance(subclient_id, bool)
            or not isinstance(subclient_name, str)
            or not isinstance(client_id, int)
            or isinstance(client_id, bool)
            or not isinstance(app_name, str)
        ):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A subclient item has invalid fields."
            )
        try:
            return CommvaultSubclient(
                subclient_id=str(subclient_id),
                subclient_name=subclient_name,
                client_id=str(client_id),
                app_name=app_name,
            )
        except ValueError as exc:
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A subclient item failed validation."
            ) from exc

    async def read_subclient_browse(self, subclient_id: str) -> CommvaultBrowseResult:
        """Reads one subclient's root-level backed-up items via
        `GET webservice/Subclient/{id}/Browse?path=%5C` (`%5C` is the confirmed root path). The
        real response is deeply nested and the official reference's own literal example shows two
        genuine collapsing ambiguities: `browseResponses` may hold one entry with a `dataResultSet`
        of actual items alongside a second, sibling entry carrying only an `aggrResultSet` count
        (no items) -- and `dataResultSet` itself may be a single object or a list depending on
        item count. Both are handled defensively rather than assumed."""

        if not _SAFE_NUMERIC_ID.match(subclient_id):
            raise CommvaultConnectorError(
                "invalid_target_identifier", "The subclient id is not safe to interpolate."
            )
        path = _SUBCLIENT_BROWSE_PATH_TEMPLATE.format(subclient_id=subclient_id)
        payload = await self._get(path)
        responses = payload.get("browseResponses")
        if isinstance(responses, Mapping):
            responses = [responses]
        if not isinstance(responses, list):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The browse response is malformed."
            )
        raw_items: list[object] = []
        for response in responses:
            if not isinstance(response, Mapping):
                continue
            result = response.get("browseResult")
            if not isinstance(result, Mapping):
                continue
            data_result_set = result.get("dataResultSet")
            if isinstance(data_result_set, Mapping):
                raw_items.append(data_result_set)
            elif isinstance(data_result_set, list):
                raw_items.extend(data_result_set)
        if len(raw_items) > self._maximum_recovery_points:
            raise CommvaultConnectorError(
                "vendor_response_limit_exceeded", "The browse response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence(f"Subclient/{subclient_id}/Browse", payload),)
        items = tuple(self._parse_recovery_point(item) for item in raw_items)
        return CommvaultBrowseResult(
            subclient_id=subclient_id,
            items=items,
            observed_at=observed_at,
            evidence_references=evidence,
        )

    @staticmethod
    def _parse_recovery_point(value: object) -> CommvaultRecoveryPoint:
        if not isinstance(value, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A recovery point item is malformed."
            )
        name = value.get("name")
        path = value.get("path")
        if not isinstance(name, str) or not isinstance(path, str):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A recovery point item has invalid fields."
            )
        size = value.get("size")
        if not isinstance(size, int) or isinstance(size, bool):
            size = None
        modification_time = value.get("modificationTime")
        if not isinstance(modification_time, int) or isinstance(modification_time, bool):
            modification_time = None
        advanced_data = value.get("advancedData")
        backup_job_id: int | None = None
        backup_time: int | None = None
        archive_file_id: int | None = None
        if isinstance(advanced_data, Mapping):
            raw_backup_job_id = advanced_data.get("backupJobId")
            if isinstance(raw_backup_job_id, int) and not isinstance(raw_backup_job_id, bool):
                backup_job_id = raw_backup_job_id
            raw_backup_time = advanced_data.get("backupTime")
            if isinstance(raw_backup_time, int) and not isinstance(raw_backup_time, bool):
                backup_time = raw_backup_time
            raw_archive_file_id = advanced_data.get("archiveFileId")
            if isinstance(raw_archive_file_id, int) and not isinstance(raw_archive_file_id, bool):
                archive_file_id = raw_archive_file_id
        try:
            return CommvaultRecoveryPoint(
                name=name,
                path=path,
                size=size,
                modification_time=modification_time,
                backup_job_id=backup_job_id,
                backup_time=backup_time,
                archive_file_id=archive_file_id,
            )
        except ValueError as exc:
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A recovery point item failed validation."
            ) from exc

    async def _get(self, path: str) -> Mapping[str, object]:
        try:
            payload = await self._transport.get(path)
        except CommvaultTransportError as exc:
            raise CommvaultConnectorError(exc.code, exc.detail, retryable=exc.retryable) from exc
        return self._bounded(payload)

    def _bounded(self, payload: object) -> Mapping[str, object]:
        if not isinstance(payload, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The vendor response must be a JSON object."
            )
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        if len(encoded) > self._maximum_response_bytes:
            raise CommvaultConnectorError(
                "vendor_response_limit_exceeded", "The vendor response exceeds its byte limit."
            )
        return payload

    @staticmethod
    def _evidence(kind: str, payload: Mapping[str, object]) -> str:
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise CommvaultConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        digest = hashlib.sha256(encoded).hexdigest()
        return f"commvault://{kind}#sha256:{digest}"
