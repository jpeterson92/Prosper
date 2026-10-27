"""Bounded exact original-source storage, including hostile compressed streams."""

import hashlib
import zlib

import pytest

from prosper import source_blob
from prosper.storage import PersistenceError


@pytest.mark.parametrize(
    "raw", [b"a", bytes(range(256)) * 7, b"fictional,12.5000,,unknown\r\n" * 100]
)
def test_one_complete_source_roundtrips_exact_bytes(raw: bytes) -> None:
    size, encoded = source_blob.pack(raw)
    assert size == len(raw)
    assert encoded == zlib.compress(raw)
    assert source_blob.unpack(hashlib.sha256(raw).hexdigest(), size, encoded) == raw


@pytest.mark.parametrize(
    "fault",
    [
        "empty",
        "raw",
        "truncated",
        "trailing",
        "concatenated",
        "damaged",
        "checksum",
        "small-size",
        "large-size",
        "empty-source",
        "nonbytes",
        "size-bool",
    ],
)
def test_invalid_source_never_returns_partial_or_substitute_bytes(fault: str) -> None:
    raw = b"fictional source with explicit unknowns\n" * 7
    digest = hashlib.sha256(raw).hexdigest()
    size, encoded = source_blob.pack(raw)
    if fault == "empty":
        encoded = b""
    elif fault == "raw":
        encoded = raw
    elif fault == "truncated":
        encoded = encoded[:-1]
    elif fault == "trailing":
        encoded += b"trailing bytes"
    elif fault == "concatenated":
        encoded += zlib.compress(b"second stream")
    elif fault == "damaged":
        encoded = encoded[:-1] + bytes([encoded[-1] ^ 255])
    elif fault == "checksum":
        digest = "0" * 64
    elif fault == "small-size":
        size -= 1
    elif fault == "large-size":
        size += 1
    elif fault == "empty-source":
        size, encoded = 1, zlib.compress(b"")
    elif fault == "nonbytes":
        encoded = bytearray(encoded)  # type: ignore[assignment]
    elif fault == "size-bool":
        size = True
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        source_blob.unpack(digest, size, encoded)


def test_decoded_and_encoded_limits_refuse_without_expanding_unbounded_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_blob, "MAX_SOURCE_BYTES", 64)
    raw = b"F" * 64
    digest = hashlib.sha256(raw).hexdigest()
    assert source_blob.unpack(digest, *source_blob.pack(raw)) == raw
    for bad in (b"", b"F" * 65):
        with pytest.raises(PersistenceError, match="source_checksum_or_size_invalid"):
            source_blob.pack(bad)
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        source_blob.unpack(digest, 65, zlib.compress(raw))
    # A small declared size must bound expansion before a large stream finishes.
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        source_blob.unpack(digest, 64, zlib.compress(b"F" * 100000))
    monkeypatch.setattr(source_blob, "MAX_STORED_BYTES", 1)
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        source_blob.unpack(digest, 64, zlib.compress(raw))
    with pytest.raises(PersistenceError, match="source_checksum_or_size_invalid"):
        source_blob.pack(raw)
