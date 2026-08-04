from __future__ import annotations

from datetime import UTC, datetime

from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    BootstrapWorkloadIdentitySpec,
    TrustAnchorPurpose,
    TrustAnchorSpec,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

SYNTHETIC_LAB_ROOT_PEM = """-----BEGIN CERTIFICATE-----
MIIDgTCCAmmgAwIBAgIUUjl8YFLEsrswLhdDt7N2qm1ITa4wDQYJKoZIhvcNAQEL
BQAwSDEhMB8GA1UEAwwYQXRsYXMgU3ludGhldGljIExhYiBSb290MRYwFAYDVQQK
DA1Qcm9qZWN0IEF0bGFzMQswCQYDVQQGEwJUUjAeFw0yNjA4MDQxNjMxMzJaFw0z
NjA4MDExNjMxMzJaMEgxITAfBgNVBAMMGEF0bGFzIFN5bnRoZXRpYyBMYWIgUm9v
dDEWMBQGA1UECgwNUHJvamVjdCBBdGxhczELMAkGA1UEBhMCVFIwggEiMA0GCSqG
SIb3DQEBAQUAA4IBDwAwggEKAoIBAQDV46jrwfUqRjoaodzYcRrDap6+ATXg4Ozz
x20IezTbtc1j/BXyUDoyFJ2Nd/R2GTUpDpLSx0ktXTQXl35gB8/NECXx+V2ejZGj
BqcLt+yrZRAkdyYYMv6QEiL5K1vwA+TFWwl8Rl17OpVFL3OhZe+f0tRUkNp2uaN2
nWLxXAiWMwT0xEVactrSDIt1Ug4jOPmbipyD/kwW8GROYKZDT0EL3BiZWxxEfXJS
7RXeDjniFO9aQkP1JVYHex/GDEJzuvABg4/ZOekNVkBCrdTbjZMQtmdQ0dkKGLRi
DEW9opY+L5McIaXV5A9Eprgnym8IS4kh+l7AJvVaeBOC5P5bTXyrAgMBAAGjYzBh
MB0GA1UdDgQWBBSosnV0aVoHWtxCZn6KInHTulurmTAfBgNVHSMEGDAWgBSosnV0
aVoHWtxCZn6KInHTulurmTAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIB
BjANBgkqhkiG9w0BAQsFAAOCAQEAsHGly8pb902QpRCdaGefQ/rrAL7bm1Rij2bX
+a7nxxhiYB0tZwSeBIhz182vVKjRN/epcRvqDgm/sgj+P2Z4+9/zfckR96IyKW+D
00DPa7O4vrGaIe7fUv29hDx8e3zbXlCp1vjTPWq4AFdvSNuCk2m5nvhnJlyjiivJ
ye5dGDv7kMy0m+EGP2VD1WP3fyEup3MCvLDNrSfEP6zYnru3sFe527fM59AlHoB+
/Diw/4p4CMZNHMtJgWWjB4m5wiyt9jWo8PQ/cXH4mit1/joa3AOPA12tQA32LMUj
O3JHHDWyCRHLSlXFt5lBRu5xmw/VUzNdFXeVUV8vYkiYKqnO4Q==
-----END CERTIFICATE-----
"""


class SyntheticBootstrapTrustSource:
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[tuple[TrustAnchorSpec, ...], tuple[BootstrapWorkloadIdentitySpec, ...]]:
        if profile not in {DeploymentProfile.DEVELOPER, DeploymentProfile.LINUX_LAB}:
            raise ValueError("synthetic trust is restricted to non-production profiles")
        return (
            (
                TrustAnchorSpec(
                    anchor_id="trust-anchor.atlas-synthetic-lab-root",
                    source_id="trust-source.synthetic-lab",
                    purpose=TrustAnchorPurpose.INTERNAL_SERVICE,
                    subject_summary="CN=Atlas Synthetic Lab Root, O=Project Atlas, C=TR",
                    sha256="540024e6ea19c2d7818b8781b4268ca0119d71cb534dcdc9819e7b32ec36b703",
                    not_before=datetime(2026, 8, 4, 16, 31, 32, tzinfo=UTC),
                    not_after=datetime(2036, 8, 1, 16, 31, 32, tzinfo=UTC),
                    non_production_only=True,
                    certificate_pem=SYNTHETIC_LAB_ROOT_PEM,
                ),
            ),
            (
                BootstrapWorkloadIdentitySpec(
                    identity_id="workload.atlas-api.primary",
                    service_id="service.atlas-api",
                    instance_id="instance.primary",
                    owner_subject_id="subject.platform.security",
                    purpose="Authenticate the primary Atlas API workload to internal services.",
                    environment_id=environment_id,
                    audiences=("audience.atlas-internal",),
                    secret_reference_ids=("secret.workload.atlas-api",),
                ),
            ),
        )
