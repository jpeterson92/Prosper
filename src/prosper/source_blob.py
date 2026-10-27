"""One bounded current source encoding; identity always hashes original bytes."""

import hashlib
import zlib

from prosper.storage import PersistenceError

MAX_SOURCE_BYTES = 16 * 1024 * 1024
# Permit compression framing/overhead without enlarging decoded-source authority.
MAX_STORED_BYTES = MAX_SOURCE_BYTES + 64 * 1024


def pack(raw: bytes) -> tuple[int, bytes]:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        raise PersistenceError("source_checksum_or_size_invalid")
    encoded = zlib.compress(raw)
    if len(encoded) > MAX_STORED_BYTES:
        raise PersistenceError("source_checksum_or_size_invalid")
    return len(raw), encoded


def unpack(digest: str, original_size: int, encoded: bytes) -> bytes:
    """Check exact size, complete single stream and checksum before using bytes."""
    if (
        type(original_size) is not int
        or not 0 < original_size <= MAX_SOURCE_BYTES
        or not isinstance(encoded, bytes)
        or not 0 < len(encoded) <= MAX_STORED_BYTES
    ):
        raise PersistenceError("source_unavailable_or_corrupt")
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(encoded, original_size + 1)
        if (
            len(raw) != original_size
            or not decoder.eof
            or decoder.unused_data
            or decoder.unconsumed_tail
            or hashlib.sha256(raw).hexdigest() != digest
        ):
            raise PersistenceError("source_unavailable_or_corrupt")
        return raw
    except zlib.error:
        raise PersistenceError("source_unavailable_or_corrupt") from None
