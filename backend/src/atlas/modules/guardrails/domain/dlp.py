"""ATLAS-047 SS19: data-loss prevention.

Covers destination allowlisting, external-URL leakage detection in generated text, and a
volume-based anomaly tracker -- the byte-volume counterpart to `input_guardrails.InputRateLimiter`
(request-count). "Audit restricted export and large-volume access" is a caller responsibility this
module does not perform itself: it reports what should be audited (a blocked destination, an
anomalous volume), the actual audit write belongs wherever `policy_engine.application.audit`-style
wiring already lives for this pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DlpDestinationAllowlist:
    allowed_destinations: frozenset[str]

    def is_allowed(self, destination: str) -> bool:
        return destination in self.allowed_destinations


_URL_PATTERN = re.compile(r"https?://[^\s)\]}'\"]+")


def detect_external_urls(text: str, *, allowlist: DlpDestinationAllowlist) -> tuple[str, ...]:
    """SS19: "prevent model-generated external URLs, callbacks, or network requests from
    bypassing tools." Any URL in generated text that is not on the destination allowlist is
    flagged -- the model cannot smuggle a live network destination out through prose."""
    found = _URL_PATTERN.findall(text)
    return tuple(url for url in found if not allowlist.is_allowed(url))


@dataclass(frozen=True, slots=True)
class VolumeLimits:
    max_bytes_per_window: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.max_bytes_per_window < 1:
            raise ValueError("max_bytes_per_window must be positive")
        if self.window_seconds < 1:
            raise ValueError("window_seconds must be positive")


class VolumeAnomalyDetector:
    """SS19: "apply rate and volume anomaly detection." A fixed-window, same-process byte-volume
    tracker -- the DLP counterpart to `InputRateLimiter`'s request-count tracking."""

    def __init__(self) -> None:
        self._windows: dict[str, tuple[datetime, int]] = {}

    def record_and_check(
        self, *, key: str, size_bytes: int, limits: VolumeLimits, now: datetime
    ) -> bool:
        """Records the access and returns True if the running total for this window is still
        within `limits.max_bytes_per_window`; returns False once it is exceeded. Unlike
        `InputRateLimiter`, the access is always recorded even when it pushes the total over the
        limit -- SS19 is about *detecting* an anomaly in what already happened, not gatekeeping
        a request before it occurs."""
        window_start, total = self._windows.get(key, (now, 0))
        if (now - window_start).total_seconds() >= limits.window_seconds:
            window_start, total = now, 0
        new_total = total + size_bytes
        self._windows[key] = (window_start, new_total)
        return new_total <= limits.max_bytes_per_window
