from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


class FieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pointer: str
    message: str
    code: str


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    code: str
    detail: str
    correlation_id: str
    retryable: bool = False
    errors: list[FieldError] = Field(default_factory=list)


class AtlasError(Exception):
    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.retryable = retryable


def problem_response(problem: ProblemDetails, *, no_store: bool = False) -> JSONResponse:
    headers = {"X-Correlation-ID": problem.correlation_id}
    if no_store:
        headers["Cache-Control"] = "no-store"
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
        headers=headers,
    )


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "cor_unavailable"))


def _requires_no_store(request: Request) -> bool:
    return request.url.path.startswith(
        (
            "/api/v1/audit-export",
            "/api/v1/workflows/physical-transport-target-context-capsule-handoffs",
            "/api/v1/workflows/physical-transport-target-context-capsule-opening-authorization-leases",
            "/api/v1/workflows/physical-transport-target-context-capsule-openings",
            "/api/v1/workflows/protected-resident-context-access-authorizations",
            "/api/v1/workflows/protected-resident-context-access-consumptions",
        )
    )


def _validation_errors(exc: RequestValidationError) -> list[FieldError]:
    errors: list[FieldError] = []
    for error in exc.errors():
        location = "/".join(str(part) for part in error["loc"])
        errors.append(
            FieldError(
                pointer=f"/{location}",
                message=str(error["msg"]),
                code=str(error["type"]),
            )
        )
    return errors


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AtlasError)
    async def atlas_error_handler(request: Request, exc: AtlasError) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                type=f"https://atlas.invalid/problems/{exc.code}",
                title=exc.title,
                status=exc.status,
                code=exc.code,
                detail=exc.detail,
                correlation_id=_correlation_id(request),
                retryable=exc.retryable,
            ),
            no_store=_requires_no_store(request),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return problem_response(
            ProblemDetails(
                type="https://atlas.invalid/problems/validation-failed",
                title="Request validation failed",
                status=422,
                code="validation_failed",
                detail="One or more request fields are invalid.",
                correlation_id=_correlation_id(request),
                errors=_validation_errors(exc),
            ),
            no_store=_requires_no_store(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request.app.state.settings.logger.exception(
            "unhandled_request_error",
            extra={"correlation_id": _correlation_id(request)},
        )
        return problem_response(
            ProblemDetails(
                type="https://atlas.invalid/problems/internal-error",
                title="Internal server error",
                status=500,
                code="internal_error",
                detail="The request could not be completed.",
                correlation_id=_correlation_id(request),
                retryable=False,
            ),
            no_store=_requires_no_store(request),
        )
