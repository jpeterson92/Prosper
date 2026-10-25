"""Cooperative fail-fast history writer lock; no stale-lock deletion or leases.

The OS releases the byte lock on process exit. The persistent lock file is never
removed/replaced. Hostile concurrent path replacement and power loss are outside
the existing local evidence boundary. Reads of immutable evidence need no lock.
"""

import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import BinaryIO

from prosper.evidence import EvidenceError, RuntimeBoundary

REGISTRY_NAMESPACE = "required-history-v1"
LOCK_NAME = "history-writer-v1.lock"
_PAYLOAD = b"prosper-history-writer-v1\n"


def _acquire(stream: BinaryIO) -> None:
    stream.seek(0)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release(stream: BinaryIO) -> None:
    stream.seek(0)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def history_writer(runtime: RuntimeBoundary, *, create: bool = False) -> Iterator[None]:
    """One lock for publication, registry changes and retention proof.

    Creation is only for pre-registry history writers or explicit first registry
    initialization. Missing coordination in an adopted runtime never reinitializes.
    Busy callers receive a stable refusal and may explicitly retry later.
    """
    path = runtime.path(LOCK_NAME)
    try:
        if create and not runtime.path(REGISTRY_NAMESPACE).exists():
            try:
                with path.open("xb") as stream:
                    stream.write(_PAYLOAD)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass
        if not path.exists():
            raise EvidenceError("history_coordination_missing")
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise EvidenceError("untrusted_history_coordination")
        with path.open("r+b") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                raise EvidenceError("untrusted_history_coordination")
            try:
                _acquire(stream)
            except OSError:
                raise EvidenceError("history_runtime_busy") from None
            try:
                if stream.read(len(_PAYLOAD) + 1) != _PAYLOAD:
                    raise EvidenceError("invalid_history_coordination")
                yield
            finally:
                _release(stream)
    except OSError:
        raise EvidenceError("history_coordination_io_failed") from None
