from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from atlas.core.capabilities import CapabilityClass
from atlas.modules.mcp_builder.domain.models import (
    BuilderAuthenticationScheme,
    BuilderCapabilityCandidate,
    BuilderFinding,
    BuilderFindingSeverity,
)

MAX_SOURCE_BYTES = 524_288
MAX_PATHS = 200
MAX_OPERATIONS = 500
MAX_PARAMETERS = 2_000
MAX_SCHEMAS = 500
MAX_NESTING = 32
HTTP_METHODS = ("get", "head", "options", "trace", "post", "put", "patch", "delete")
SAFE_METHODS = frozenset({"get", "head"})
RISK_TOKENS = frozenset(
    {
        "all",
        "batch",
        "bulk",
        "collect",
        "execute",
        "failover",
        "reboot",
        "refresh",
        "rescan",
        "restart",
        "run",
        "start",
        "sync",
        "trigger",
    }
)
SECRET_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "client_secret",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
    }
)
SAFE_SECRET_MARKERS = frozenset(
    {"", "example", "placeholder", "redacted", "replace-me", "sample", "test", "your-value"}
)


class BuilderSourceError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class OpenApiAnalysis:
    canonical_source_json: str
    source_digest: str
    source_size_bytes: int
    openapi_version: str
    api_title: str
    api_version: str
    declared_servers: tuple[str, ...]
    authentication_schemes: tuple[BuilderAuthenticationScheme, ...]
    capability_candidates: tuple[BuilderCapabilityCandidate, ...]
    findings: tuple[BuilderFinding, ...]


class OpenApiSourceAnalyzer:
    def analyze(self, source_document: str) -> OpenApiAnalysis:
        source_size = len(source_document.encode("utf-8"))
        if not 1 <= source_size <= MAX_SOURCE_BYTES:
            raise BuilderSourceError("builder_source_size_invalid")
        try:
            document = json.loads(source_document, object_pairs_hook=self._unique_object)
        except BuilderSourceError:
            raise
        except (json.JSONDecodeError, UnicodeError) as error:
            raise BuilderSourceError("builder_source_json_invalid") from error
        if not isinstance(document, dict):
            raise BuilderSourceError("builder_source_root_invalid")
        self._validate_structure_budget(document)
        self._reject_embedded_secrets(document)
        canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = sha256(canonical.encode("ascii")).hexdigest()
        openapi_version = document.get("openapi")
        if not isinstance(openapi_version, str) or not re.fullmatch(
            r"3\.(?:0|1)\.\d+(?:-[0-9A-Za-z.-]+)?", openapi_version
        ):
            raise BuilderSourceError("builder_openapi_version_unsupported")
        info = document.get("info")
        if not isinstance(info, dict):
            raise BuilderSourceError("builder_openapi_info_missing")
        api_title = self._bounded_text(info.get("title"), "builder_openapi_title_invalid", 160)
        api_version = self._bounded_text(
            info.get("version"), "builder_openapi_api_version_invalid", 80
        )
        paths = document.get("paths")
        if not isinstance(paths, dict) or not paths:
            raise BuilderSourceError("builder_openapi_paths_missing")
        if len(paths) > MAX_PATHS:
            raise BuilderSourceError("builder_openapi_path_budget_exceeded")

        findings: list[BuilderFinding] = []
        self._inspect_references(document, document, findings, location="")
        if isinstance(document.get("webhooks"), dict) and document["webhooks"]:
            findings.append(
                self._finding(
                    "builder_webhooks_blocked",
                    "/webhooks",
                    "OpenAPI webhooks require a later reviewed Builder slice.",
                )
            )
        servers = self._servers(document.get("servers"), findings)
        schemes, scheme_map = self._authentication_schemes(document, findings)
        source_blocking_codes = tuple(
            dict.fromkeys(finding.code for finding in findings if finding.blocking)
        )
        candidates = self._capabilities(
            document=document,
            paths=paths,
            source_digest=digest,
            scheme_map=scheme_map,
            source_blocking_codes=source_blocking_codes,
            findings=findings,
        )
        return OpenApiAnalysis(
            canonical_source_json=canonical,
            source_digest=digest,
            source_size_bytes=source_size,
            openapi_version=openapi_version,
            api_title=api_title,
            api_version=api_version,
            declared_servers=servers,
            authentication_schemes=schemes,
            capability_candidates=candidates,
            findings=tuple(findings),
        )

    @staticmethod
    def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BuilderSourceError("builder_source_duplicate_key")
            result[key] = value
        return result

    @staticmethod
    def _bounded_text(value: object, code: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise BuilderSourceError(code)
        return value.strip()

    def _validate_structure_budget(self, document: dict[str, Any]) -> None:
        parameters = 0

        def walk(value: object, depth: int) -> None:
            nonlocal parameters
            if depth > MAX_NESTING:
                raise BuilderSourceError("builder_source_nesting_budget_exceeded")
            if isinstance(value, dict):
                parameters += int(
                    "parameters" in value and isinstance(value["parameters"], list)
                ) * len(value.get("parameters", []))
                for child in value.values():
                    walk(child, depth + 1)
            elif isinstance(value, list):
                for child in value:
                    walk(child, depth + 1)

        walk(document, 0)
        if parameters > MAX_PARAMETERS:
            raise BuilderSourceError("builder_openapi_parameter_budget_exceeded")
        components = document.get("components")
        schemas = components.get("schemas") if isinstance(components, dict) else None
        if isinstance(schemas, dict) and len(schemas) > MAX_SCHEMAS:
            raise BuilderSourceError("builder_openapi_schema_budget_exceeded")

    def _reject_embedded_secrets(self, document: dict[str, Any]) -> None:
        def walk(value: object, path: tuple[str, ...]) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
                    if normalized in SECRET_KEYS and self._looks_like_secret(child):
                        raise BuilderSourceError("builder_source_secret_detected")
                    if key in {"$ref", "url"} and isinstance(child, str):
                        self._reject_url_secret(child)
                    walk(child, (*path, key))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, (*path, str(index)))

        walk(document, ())

    def _reject_url_secret(self, value: str) -> None:
        parsed = urlsplit(value)
        if parsed.username is not None or parsed.password is not None:
            raise BuilderSourceError("builder_source_secret_detected")
        for key, candidate in parse_qsl(parsed.query, keep_blank_values=True):
            normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            if normalized in SECRET_KEYS and self._looks_like_secret(candidate):
                raise BuilderSourceError("builder_source_secret_detected")

    @staticmethod
    def _looks_like_secret(value: object) -> bool:
        if not isinstance(value, str):
            return False
        normalized = value.strip().lower()
        if normalized in SAFE_SECRET_MARKERS or normalized.startswith(("${", "{{", "<")):
            return False
        return len(normalized) >= 8

    def _inspect_references(
        self,
        value: object,
        root: dict[str, Any],
        findings: list[BuilderFinding],
        *,
        location: str,
    ) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_location = f"{location}/{self._pointer(key)}"
                if key == "$ref" and isinstance(child, str):
                    if not child.startswith("#/"):
                        findings.append(
                            self._finding(
                                "builder_external_reference_blocked",
                                child_location,
                                "External OpenAPI references are disabled in this Builder slice.",
                            )
                        )
                    elif not self._resolve_pointer(root, child):
                        findings.append(
                            self._finding(
                                "builder_local_reference_unresolved",
                                child_location,
                                "The local OpenAPI reference does not resolve.",
                            )
                        )
                self._inspect_references(child, root, findings, location=child_location)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._inspect_references(child, root, findings, location=f"{location}/{index}")

    @staticmethod
    def _resolve_pointer(root: dict[str, Any], reference: str) -> bool:
        current: object = root
        for part in reference[2:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and key.isdigit() and int(key) < len(current):
                current = current[int(key)]
            else:
                return False
        return True

    def _servers(self, value: object, findings: list[BuilderFinding]) -> tuple[str, ...]:
        if value is None:
            findings.append(
                self._finding(
                    "builder_server_evidence_missing",
                    "/servers",
                    "No API server boundary is declared.",
                )
            )
            return ()
        if not isinstance(value, list) or not 1 <= len(value) <= 20:
            raise BuilderSourceError("builder_openapi_servers_invalid")
        servers: list[str] = []
        for index, item in enumerate(value):
            location = f"/servers/{index}/url"
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                findings.append(
                    self._finding(
                        "builder_server_url_invalid", location, "Server URL evidence is malformed."
                    )
                )
                continue
            url = item["url"].strip()
            if len(url) > 500:
                raise BuilderSourceError("builder_openapi_server_url_too_long")
            parsed = urlsplit(url)
            if "{" in url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                findings.append(
                    self._finding(
                        "builder_server_url_unresolved",
                        location,
                        "Server variables or non-HTTP destinations require human clarification.",
                    )
                )
            servers.append(url)
        return tuple(servers)

    def _authentication_schemes(
        self, document: dict[str, Any], findings: list[BuilderFinding]
    ) -> tuple[tuple[BuilderAuthenticationScheme, ...], dict[str, str]]:
        components = document.get("components")
        raw_schemes = components.get("securitySchemes") if isinstance(components, dict) else None
        if not isinstance(raw_schemes, dict) or not raw_schemes:
            findings.append(
                self._finding(
                    "builder_authentication_evidence_missing",
                    "/components/securitySchemes",
                    "No authentication scheme is declared.",
                )
            )
            return (), {}
        schemes: list[BuilderAuthenticationScheme] = []
        mapping: dict[str, str] = {}
        for name in sorted(raw_schemes):
            raw = raw_schemes[name]
            location = f"/components/securitySchemes/{self._pointer(name)}"
            if not isinstance(raw, dict):
                findings.append(
                    self._finding(
                        "builder_authentication_scheme_invalid",
                        location,
                        "Authentication scheme evidence is malformed.",
                    )
                )
                continue
            scheme_id = f"builder-auth.{sha256(name.encode('utf-8')).hexdigest()[:24]}"
            mapping[name] = scheme_id
            scheme_type = str(raw.get("type", "unknown"))[:64]
            scheme = raw.get("scheme") if isinstance(raw.get("scheme"), str) else None
            parameter_location = raw.get("in") if isinstance(raw.get("in"), str) else None
            bearer = raw.get("bearerFormat") if isinstance(raw.get("bearerFormat"), str) else None
            supported = self._supported_authentication(raw)
            finding_codes: tuple[str, ...] = ()
            if not supported:
                code = "builder_authentication_requires_clarification"
                finding_codes = (code,)
                findings.append(
                    self._finding(
                        code,
                        location,
                        "Authentication cannot be confirmed for unattended least-privilege use.",
                    )
                )
            schemes.append(
                BuilderAuthenticationScheme(
                    scheme_id=scheme_id,
                    scheme_type=scheme_type,
                    scheme=scheme,
                    location=parameter_location,
                    bearer_format=bearer,
                    requires_secret_reference=scheme_type
                    in {"apiKey", "http", "oauth2", "mutualTLS"},
                    supported_for_unattended_use=supported,
                    finding_codes=finding_codes,
                )
            )
        return tuple(schemes), mapping

    @staticmethod
    def _supported_authentication(raw: dict[str, Any]) -> bool:
        scheme_type = raw.get("type")
        if scheme_type == "apiKey" and raw.get("in") in {"header", "query"}:
            return True
        if scheme_type == "http" and str(raw.get("scheme", "")).lower() in {"basic", "bearer"}:
            return True
        if scheme_type == "mutualTLS":
            return True
        if scheme_type == "oauth2":
            flows = raw.get("flows")
            return isinstance(flows, dict) and isinstance(flows.get("clientCredentials"), dict)
        return False

    def _capabilities(
        self,
        *,
        document: dict[str, Any],
        paths: dict[str, Any],
        source_digest: str,
        scheme_map: dict[str, str],
        source_blocking_codes: tuple[str, ...],
        findings: list[BuilderFinding],
    ) -> tuple[BuilderCapabilityCandidate, ...]:
        candidates: list[BuilderCapabilityCandidate] = []
        operation_count = 0
        global_security = document.get("security")
        for path in sorted(paths):
            path_item = paths[path]
            if not isinstance(path, str) or not path.startswith("/") or len(path) > 512:
                raise BuilderSourceError("builder_openapi_path_invalid")
            if not isinstance(path_item, dict):
                raise BuilderSourceError("builder_openapi_path_item_invalid")
            path_parameters = path_item.get("parameters")
            path_parameter_count = len(path_parameters) if isinstance(path_parameters, list) else 0
            for method in HTTP_METHODS:
                raw = path_item.get(method)
                if raw is None:
                    continue
                operation_count += 1
                if operation_count > MAX_OPERATIONS:
                    raise BuilderSourceError("builder_openapi_operation_budget_exceeded")
                if not isinstance(raw, dict):
                    raise BuilderSourceError("builder_openapi_operation_invalid")
                candidate, operation_findings = self._capability(
                    method=method,
                    path=path,
                    raw=raw,
                    path_parameter_count=path_parameter_count,
                    global_security=global_security,
                    scheme_map=scheme_map,
                    source_digest=source_digest,
                    source_blocking_codes=source_blocking_codes,
                )
                findings.extend(operation_findings)
                candidates.append(candidate)
        return tuple(candidates)

    def _capability(
        self,
        *,
        method: str,
        path: str,
        raw: dict[str, Any],
        path_parameter_count: int,
        global_security: object,
        scheme_map: dict[str, str],
        source_digest: str,
        source_blocking_codes: tuple[str, ...],
    ) -> tuple[BuilderCapabilityCandidate, tuple[BuilderFinding, ...]]:
        location = f"/paths/{self._pointer(path)}/{method}"
        operation_id = raw.get("operationId") if isinstance(raw.get("operationId"), str) else None
        summary_source = (
            raw.get("summary") or raw.get("description") or operation_id or f"{method} {path}"
        )
        summary = re.sub(r"\s+", " ", str(summary_source)).strip()[:500]
        local_codes: list[str] = []
        confidence: list[str] = [f"http_method:{method}"]
        side_effects = ["read"] if method in SAFE_METHODS else ["write_or_unknown"]

        if operation_id is None or not operation_id.strip():
            local_codes.append("builder_operation_id_missing")
        if method not in SAFE_METHODS:
            local_codes.append("builder_write_method_blocked")
        declared_effect = raw.get("x-atlas-side-effects")
        if method in SAFE_METHODS:
            if declared_effect not in {"none", "read"}:
                local_codes.append("builder_side_effect_evidence_missing")
            else:
                confidence.append(f"declared_side_effect:{declared_effect}")
        risk_text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", f"{path} {operation_id or ''} {summary}")
        tokens = set(token for token in re.split(r"[^a-z0-9]+", risk_text.lower()) if token)
        risky = sorted(tokens & RISK_TOKENS)
        if risky:
            local_codes.append("builder_read_style_action_ambiguous")
            confidence.append(f"risk_tokens:{','.join(risky)}")
        if raw.get("requestBody") is not None and method in SAFE_METHODS:
            local_codes.append("builder_read_request_body_ambiguous")
        if raw.get("callbacks"):
            local_codes.append("builder_callbacks_blocked")
        responses = raw.get("responses")
        response_codes = (
            tuple(sorted(str(code) for code in responses)) if isinstance(responses, dict) else ()
        )
        if not response_codes or not any(code.startswith("2") for code in response_codes):
            local_codes.append("builder_success_response_missing")

        operation_parameters = raw.get("parameters")
        operation_parameter_count = (
            len(operation_parameters) if isinstance(operation_parameters, list) else 0
        )
        parameter_count = path_parameter_count + operation_parameter_count
        security = raw.get("security", global_security)
        security_ids, security_codes = self._operation_security(security, scheme_map)
        local_codes.extend(security_codes)

        local_findings: list[BuilderFinding] = []
        for code in dict.fromkeys(local_codes):
            local_findings.append(self._finding(code, location, self._finding_message(code)))
        unique_codes = tuple(dict.fromkeys((*source_blocking_codes, *local_codes)))
        blocked = bool(unique_codes)
        proposed_class = CapabilityClass.C5_DESTRUCTIVE if blocked else CapabilityClass.C1_READ_ONLY
        if not blocked:
            confidence.append("bounded_read_only_candidate")
        candidate_hash = sha256(f"{method}:{path}".encode()).hexdigest()[:24]
        citation_path = self._pointer(path)
        candidate = BuilderCapabilityCandidate(
            candidate_id=f"builder-capability.{candidate_hash}",
            operation_id=operation_id.strip() if operation_id else None,
            method=method,
            path=path,
            summary=summary,
            citation=f"openapi://{source_digest}/paths/{citation_path}/{method}",
            proposed_capability_class=proposed_class,
            side_effects=tuple(side_effects),
            security_scheme_ids=security_ids,
            parameter_count=parameter_count,
            response_codes=response_codes,
            request_body_present=raw.get("requestBody") is not None,
            confidence_basis=tuple(confidence),
            clarification_codes=unique_codes,
            generation_blocked=blocked,
        )
        return candidate, tuple(local_findings)

    @staticmethod
    def _operation_security(
        value: object, scheme_map: dict[str, str]
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if not isinstance(value, list) or not value:
            return (), ("builder_operation_authentication_missing",)
        ids: set[str] = set()
        codes: list[str] = []
        for requirement in value:
            if not isinstance(requirement, dict) or not requirement:
                codes.append("builder_operation_authentication_missing")
                continue
            for original_id in requirement:
                scheme_id = scheme_map.get(original_id)
                if scheme_id is None:
                    codes.append("builder_operation_authentication_unknown")
                else:
                    ids.add(scheme_id)
        return tuple(sorted(ids)), tuple(dict.fromkeys(codes))

    @staticmethod
    def _pointer(value: str) -> str:
        return value.replace("~", "~0").replace("/", "~1")

    @staticmethod
    def _finding(
        code: str, location: str, message: str, *, blocking: bool = True
    ) -> BuilderFinding:
        return BuilderFinding(
            code=code,
            severity=BuilderFindingSeverity.ERROR if blocking else BuilderFindingSeverity.WARNING,
            location=location or "/",
            message=message,
            blocking=blocking,
        )

    @staticmethod
    def _finding_message(code: str) -> str:
        messages = {
            "builder_operation_id_missing": (
                "Operation ID is required for stable capability mapping."
            ),
            "builder_write_method_blocked": (
                "Write or control methods are outside this Builder slice."
            ),
            "builder_side_effect_evidence_missing": (
                "Explicit read-only side-effect evidence is missing."
            ),
            "builder_read_style_action_ambiguous": (
                "Read-style operation text indicates a possible action or broad scope."
            ),
            "builder_read_request_body_ambiguous": (
                "A read operation with a request body requires review."
            ),
            "builder_callbacks_blocked": "Callbacks are outside this Builder slice.",
            "builder_success_response_missing": (
                "No explicit successful response evidence is declared."
            ),
            "builder_operation_authentication_missing": (
                "Operation authentication evidence is missing or anonymous."
            ),
            "builder_operation_authentication_unknown": (
                "Operation references an unknown authentication scheme."
            ),
        }
        return messages[code]
