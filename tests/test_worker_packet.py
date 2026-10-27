"""Current binary worker boundary retains exact inputs and refuses ambiguity."""

import base64
import json
from pathlib import Path

import pytest

from prosper import worker_packet
from prosper.candidate_workflow import FrozenCandidate
from prosper.modeled_inputs import ModeledResult
from prosper.worker_packet import MAGIC, decode_input, encode_input
from tests.test_candidate_workflow import command, seed, service


def test_packet_exact_round_trip_malformed_payloads_and_both_size_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = service(tmp_path / "source")
    seed(workspace)
    run = workspace.store.run("inputs")
    frozen = FrozenCandidate(
        command=command(),
        modeled=workspace.store.modeled_inputs(run.inputs["modeled_inputs"]),
        coverage=ModeledResult.model_validate_json(json.dumps(run.outputs)),
        snapshot=workspace.store.snapshot(run.snapshot_id),
        retained_snapshots=(),
        required_sources=(),
    )
    raw = encode_input(frozen)
    assert decode_input(raw) == frozen
    assert frozen.modeled.alignment is not None
    payload = base64.b64decode(frozen.modeled.alignment.rows.data)
    assert raw.endswith(payload)
    assert len(raw) < len(frozen.model_dump_json().encode())
    for invalid in (
        b"",
        raw[:-1],
        raw + b"trailing",
        raw.replace(MAGIC, b"x" * len(MAGIC), 1),
        MAGIC + (len(raw) + 1).to_bytes(4, "big") + raw,
    ):
        with pytest.raises(ValueError):
            decode_input(invalid)
    prefix = len(MAGIC) + 4
    size = int.from_bytes(raw[len(MAGIC) : prefix], "big")
    header = raw[prefix : prefix + size]
    # Duplicate metadata fields and a second embedded payload refuse.
    for invalid_header in (
        b'{"modeled":null,' + header[1:],
        header.replace(b'"rows":{', b'"rows":{"data":"",', 1),
    ):
        with pytest.raises(ValueError):
            decode_input(MAGIC + len(invalid_header).to_bytes(4, "big") + invalid_header + payload)
    monkeypatch.setattr(worker_packet, "MAX_MESSAGE", len(raw) - 1)
    with pytest.raises(ValueError, match="worker_input_size_limit"):
        encode_input(frozen)
    with pytest.raises(ValueError, match="worker_input_size_limit"):
        decode_input(raw)
