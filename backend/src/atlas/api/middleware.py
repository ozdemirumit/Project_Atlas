from __future__ import annotations

import re
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from atlas.api.errors import ProblemDetails, problem_response

CORRELATION_HEADER = "X-Correlation-ID"
CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def new_correlation_id() -> str:
    return f"cor_{uuid4().hex}"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        generated_id = new_correlation_id()
        incoming_id = request.headers.get(CORRELATION_HEADER)
        request.state.correlation_id = generated_id

        if incoming_id is not None and not CORRELATION_PATTERN.fullmatch(incoming_id):
            return problem_response(
                ProblemDetails(
                    type="https://atlas.invalid/problems/invalid-correlation-id",
                    title="Invalid correlation identifier",
                    status=400,
                    code="invalid_correlation_id",
                    detail="X-Correlation-ID has an invalid format.",
                    correlation_id=generated_id,
                )
            )

        correlation_id = incoming_id or generated_id
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response


class ApiCredentialNoStoreMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if getattr(request.state, "authenticated_api_credential_id", None) is not None:
            response.headers["Cache-Control"] = "no-store"
        return response
