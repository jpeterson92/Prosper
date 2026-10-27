"""One bounded current worker packet: JSON metadata plus raw history payload.

The history table remains independently bounded and validated. Sending its
compressed bytes directly avoids base64 overhead across the binary process pipe.
"""

import base64
import json

from prosper.candidate_workflow import FrozenCandidate

MAX_MESSAGE = 16 * 1024 * 1024
MAGIC = b"prosper-worker-v1\x00"


def encode_input(frozen: FrozenCandidate) -> bytes:
    document = frozen.model_dump(mode="json")
    alignment = document["modeled"]["alignment"]
    payload = b""
    if alignment is not None:
        payload = base64.b64decode(alignment["rows"].pop("data"), validate=True)
    header = json.dumps(document, separators=(",", ":"), allow_nan=False).encode()
    raw = MAGIC + len(header).to_bytes(4, "big") + header + payload
    if len(raw) > MAX_MESSAGE:
        raise ValueError("worker_input_size_limit")
    return raw


def decode_input(raw: bytes) -> FrozenCandidate:
    if len(raw) > MAX_MESSAGE:
        raise ValueError("worker_input_size_limit")
    prefix = len(MAGIC) + 4
    if not raw.startswith(MAGIC) or len(raw) < prefix:
        raise ValueError("worker_input_packet_invalid")
    size = int.from_bytes(raw[len(MAGIC) : prefix], "big")
    if not 0 < size <= len(raw) - prefix:
        raise ValueError("worker_input_packet_invalid")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value = dict(pairs)
        if len(value) != len(pairs):
            raise ValueError("worker_input_duplicate_key")
        return value

    try:
        document = json.loads(raw[prefix : prefix + size], object_pairs_hook=unique)
        alignment = document["modeled"]["alignment"]
        payload = raw[prefix + size :]
        if alignment is None:
            if payload:
                raise ValueError("worker_input_packet_invalid")
        else:
            if "data" in alignment["rows"]:
                raise ValueError("worker_input_packet_invalid")
            alignment["rows"]["data"] = base64.b64encode(payload).decode()
        return FrozenCandidate.model_validate_json(json.dumps(document, allow_nan=False))
    except (KeyError, TypeError, RecursionError) as error:
        raise ValueError("worker_input_packet_invalid") from error
