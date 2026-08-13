from __future__ import annotations

import asyncio

from atlas.modules.reports.domain.models import TechnicalReport


class InMemoryTechnicalReportRepository:
    durable = False

    def __init__(self) -> None:
        self._reports: dict[str, TechnicalReport] = {}
        self._requests: dict[str, str] = {}
        self._latest: dict[str, str] = {}
        self._lineages: dict[tuple[str, int], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, report_id: str) -> TechnicalReport | None:
        async with self._lock:
            return self._reports.get(report_id)

    async def get_by_request_fingerprint(
        self, *, request_fingerprint: str
    ) -> TechnicalReport | None:
        async with self._lock:
            report_id = self._requests.get(request_fingerprint)
            return self._reports.get(report_id) if report_id else None

    async def get_latest(self, *, lineage_fingerprint: str) -> TechnicalReport | None:
        async with self._lock:
            report_id = self._latest.get(lineage_fingerprint)
            return self._reports.get(report_id) if report_id else None

    async def add(
        self,
        report: TechnicalReport,
        *,
        request_fingerprint: str,
        lineage_fingerprint: str,
    ) -> bool:
        async with self._lock:
            lineage_version = (lineage_fingerprint, report.version)
            if (
                report.report_id in self._reports
                or request_fingerprint in self._requests
                or lineage_version in self._lineages
            ):
                return False
            self._reports[report.report_id] = report
            self._requests[request_fingerprint] = report.report_id
            self._lineages[lineage_version] = report.report_id
            self._latest[lineage_fingerprint] = report.report_id
            return True

    async def close(self) -> None:
        return None
