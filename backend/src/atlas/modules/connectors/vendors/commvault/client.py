from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.domain.models import ConnectorHealth, ConnectorInstance
from atlas.modules.connectors.vendors.commvault.domain import (
    CommvaultClientListResult,
    CommvaultClientRecord,
    CommvaultJob,
    CommvaultJobListResult,
    CommvaultStoragePolicy,
    CommvaultStoragePolicyListResult,
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
        maximum_response_bytes: int = 1_048_576,
    ) -> None:
        if (
            maximum_jobs < 1
            or maximum_clients < 1
            or maximum_policies < 1
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
        client_props = value.get("clientProps")
        client = value.get("client")
        if not isinstance(client_props, Mapping) or not isinstance(client, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A client item is missing its properties."
            )
        client_entity = client.get("clientEntity")
        os_info = client.get("osInfo")
        if not isinstance(client_entity, Mapping) or not isinstance(os_info, Mapping):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A client item is missing its identity or OS info."
            )
        client_id = client_entity.get("clientId")
        client_name = client_entity.get("clientName")
        host_name = client_entity.get("hostName")
        os_type = os_info.get("Type")
        is_deleted = client_props.get("IsDeletedClient")
        if (
            not isinstance(client_id, int)
            or isinstance(client_id, bool)
            or not isinstance(client_name, str)
            or not isinstance(host_name, str)
            or not isinstance(os_type, str)
            or not isinstance(is_deleted, bool)
        ):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A client item has invalid fields."
            )
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
        number_of_copies = value.get("numberOfCopies")
        number_of_streams = value.get("numberOfStreams")
        if (
            not isinstance(policy_id, int)
            or isinstance(policy_id, bool)
            or not isinstance(policy_name, str)
            or not isinstance(number_of_copies, int)
            or isinstance(number_of_copies, bool)
            or not isinstance(number_of_streams, int)
            or isinstance(number_of_streams, bool)
        ):
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A storage policy item has invalid fields."
            )
        try:
            return CommvaultStoragePolicy(
                policy_id=str(policy_id),
                policy_name=policy_name,
                number_of_copies=number_of_copies,
                number_of_streams=number_of_streams,
            )
        except ValueError as exc:
            raise CommvaultConnectorError(
                "malformed_vendor_response", "A storage policy item failed validation."
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
