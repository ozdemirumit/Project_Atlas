from __future__ import annotations

from datetime import datetime

from atlas.modules.rca.application.ports import RcaAssembler
from atlas.modules.rca.domain.models import RcaCase, RcaCreateRequest


class ChainedRcaAssembler:
    """Tries each configured, single-vendor assembler in order and returns the first that
    recognizes the requested target_id. Each underlying assembler already raises KeyError when it
    cannot resolve request.target_id to one of its own real, configured devices (the established
    "target unavailable" signal RcaService.create() converts to a domain error) -- this chain just
    keeps trying the next vendor on that same signal, and re-raises the last KeyError if none
    recognize the target. Vendors are tried in a fixed order, so a target_id that happens to collide
    across two vendors' identity hashes (astronomically unlikely, given each is a sha256-derived
    20-character hash of a real vendor-specific device id) would resolve to whichever is listed
    first -- no such collision is expected in practice.
    """

    def __init__(self, *, assemblers: tuple[RcaAssembler, ...]) -> None:
        if not assemblers:
            raise ValueError("a chained RCA assembler requires at least one assembler")
        self._assemblers = assemblers

    async def build(
        self,
        request: RcaCreateRequest,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> RcaCase:
        last_error: KeyError | None = None
        for assembler in self._assemblers:
            try:
                return await assembler.build(
                    request,
                    requested_by=requested_by,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    site_id=site_id,
                    created_at=created_at,
                    version=version,
                    prior_version_id=prior_version_id,
                )
            except KeyError as error:
                last_error = error
        assert last_error is not None
        raise last_error
