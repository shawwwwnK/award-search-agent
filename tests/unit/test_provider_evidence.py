from pathlib import Path

import pytest

from award_agent.providers.evidence import (
    evidence_sha256,
    read_verified_evidence,
    sanitize_provider_payload,
    write_immutable_evidence,
)


def test_sanitized_evidence_is_immutable_and_replay_verified(tmp_path: Path) -> None:
    original = {
        "data": [{"ID": "a", "JMileageCost": "0", "JRemainingSeats": None}],
        "booking_links": [{"link": "https://example.test/?token=private"}],
        "Authorization": "private",
    }
    path, digest = write_immutable_evidence(tmp_path, original)
    assert read_verified_evidence(path, digest) == {
        "data": [{"ID": "a", "JMileageCost": "0", "JRemainingSeats": None}]
    }
    assert b"private" not in path.read_bytes()
    assert write_immutable_evidence(tmp_path, original) == (path, digest)
    assert evidence_sha256(original) == digest

    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="digest mismatch"):
        read_verified_evidence(path, digest)
    with pytest.raises(ValueError, match="collision or mutation"):
        write_immutable_evidence(tmp_path, original)


def test_secret_value_is_redacted_even_under_benign_key() -> None:
    sanitized = sanitize_provider_payload(
        {"message": "provider echoed sensitive-credential here"},
        secret_values=("sensitive-credential",),
    )
    assert sanitized == {"message": "provider echoed [REDACTED] here"}
