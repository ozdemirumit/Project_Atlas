from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.guardrails.domain.dlp import (
    DlpDestinationAllowlist,
    VolumeAnomalyDetector,
    VolumeLimits,
    detect_external_urls,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def test_allowlisted_destination_is_allowed() -> None:
    allowlist = DlpDestinationAllowlist(
        allowed_destinations=frozenset({"https://approved.example"})
    )
    assert allowlist.is_allowed("https://approved.example") is True


def test_unlisted_destination_is_not_allowed() -> None:
    allowlist = DlpDestinationAllowlist(allowed_destinations=frozenset())
    assert allowlist.is_allowed("https://unapproved.example") is False


def test_no_urls_in_ordinary_text_detects_nothing() -> None:
    allowlist = DlpDestinationAllowlist(allowed_destinations=frozenset())
    assert (
        detect_external_urls("The controller reports a healthy status.", allowlist=allowlist) == ()
    )


def test_an_allowlisted_url_is_not_flagged() -> None:
    allowlist = DlpDestinationAllowlist(
        allowed_destinations=frozenset({"https://approved.example/path"})
    )
    text = "See https://approved.example/path for details."
    assert detect_external_urls(text, allowlist=allowlist) == ()


def test_a_non_allowlisted_url_is_flagged() -> None:
    allowlist = DlpDestinationAllowlist(allowed_destinations=frozenset())
    text = "Send the data to https://attacker.example/collect for review."
    detected = detect_external_urls(text, allowlist=allowlist)
    assert detected == ("https://attacker.example/collect",)


def test_multiple_urls_are_each_evaluated_independently() -> None:
    allowlist = DlpDestinationAllowlist(
        allowed_destinations=frozenset({"https://approved.example"})
    )
    text = "Approved: https://approved.example Unapproved: https://unapproved.example"
    detected = detect_external_urls(text, allowlist=allowlist)
    assert detected == ("https://unapproved.example",)


def test_volume_detector_stays_within_limit() -> None:
    detector = VolumeAnomalyDetector()
    limits = VolumeLimits(max_bytes_per_window=1000, window_seconds=60)
    assert detector.record_and_check(key="actor.example", size_bytes=500, limits=limits, now=NOW)
    assert detector.record_and_check(key="actor.example", size_bytes=400, limits=limits, now=NOW)


def test_volume_detector_flags_an_anomaly_once_the_window_total_is_exceeded() -> None:
    detector = VolumeAnomalyDetector()
    limits = VolumeLimits(max_bytes_per_window=1000, window_seconds=60)
    assert detector.record_and_check(key="actor.example", size_bytes=800, limits=limits, now=NOW)
    assert not detector.record_and_check(
        key="actor.example", size_bytes=800, limits=limits, now=NOW
    )


def test_volume_detector_still_records_an_access_that_exceeds_the_limit() -> None:
    detector = VolumeAnomalyDetector()
    limits = VolumeLimits(max_bytes_per_window=100, window_seconds=60)
    assert not detector.record_and_check(
        key="actor.example", size_bytes=200, limits=limits, now=NOW
    )
    # The oversized access was recorded (not silently dropped) -- a second small access still
    # reports over-limit because the running total already includes the first one.
    assert not detector.record_and_check(key="actor.example", size_bytes=1, limits=limits, now=NOW)


def test_volume_detector_resets_after_the_window_elapses() -> None:
    detector = VolumeAnomalyDetector()
    limits = VolumeLimits(max_bytes_per_window=100, window_seconds=60)
    assert detector.record_and_check(key="actor.example", size_bytes=100, limits=limits, now=NOW)
    later = NOW + timedelta(seconds=61)
    assert detector.record_and_check(key="actor.example", size_bytes=100, limits=limits, now=later)


def test_volume_detector_tracks_separate_keys_independently() -> None:
    detector = VolumeAnomalyDetector()
    limits = VolumeLimits(max_bytes_per_window=100, window_seconds=60)
    assert detector.record_and_check(key="actor.a", size_bytes=100, limits=limits, now=NOW)
    assert detector.record_and_check(key="actor.b", size_bytes=100, limits=limits, now=NOW)


def test_volume_limits_reject_non_positive_values() -> None:
    with pytest.raises(ValueError, match="max_bytes_per_window"):
        VolumeLimits(max_bytes_per_window=0, window_seconds=60)
    with pytest.raises(ValueError, match="window_seconds"):
        VolumeLimits(max_bytes_per_window=100, window_seconds=0)
