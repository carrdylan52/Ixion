"""Initialize a host-owned ledger, consumed high-water and DC1 cursor in a fresh,
disposable run folder. Never reset, never bind an existing save root."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

MARKER = "ixion-disposable-run.json"
LEDGER_VERSION = 2  # v1 fallback attribution is ambiguous; never migrate it.
MARKER_VERSION = 2  # Bind format eligibility independently of the ledger header.


@contextlib.contextmanager
def lock(path):
    stream = open(str(path) + ".lock", "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        stream.close()


def create(path, text):
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(text.encode())
            stream.flush()
            os.fsync(stream.fileno())
        # rename is exclusive on Windows; link is exclusive on POSIX.
        if os.name == "nt":
            os.rename(temporary, path)
        else:
            os.link(temporary, path)
            os.unlink(temporary)
            directory = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)  # Only the temporary file created by this call.


def line(value):
    return json.dumps(value, separators=(",", ":")) + "\n"


def fnv1a64(data):
    value = 0xCBF29CE484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def ledger_text(identity, cursor):
    # The trailer seals every byte before it (include/ixion_delivery.hpp).
    header = line({"version": LEDGER_VERSION, "ledger": identity, "cursor": str(cursor)})
    return header + line({"end": 0, "fnv1a64": fnv1a64(header.encode())})


def consumed_path(ledger):
    return Path(str(ledger) + ".consumed.jsonl")


def consumed_text(identity):
    # No consumed records or identities yet; canonical empty SHA-256 commitments.
    empty = hashlib.sha256(b"").hexdigest()
    body = line({"version": 2, "ledger": identity, "seq": 0,
                 "prefix_sha256": empty, "events_sha256": empty})
    return body + line({"end": 0, "fnv1a64": fnv1a64(body.encode())})


def initialize(ledger, save):
    ledger = ledger.resolve()
    save = save.resolve()
    run = ledger.parent
    if save == run or run not in save.parents:
        raise ValueError("the DC1 save root must be a new folder inside the ledger's run folder")
    if run.exists() and any(run.iterdir()):
        raise ValueError(f"run folder {run} is not empty; delivery needs a fresh disposable run folder")
    run.mkdir(parents=True, exist_ok=True)
    save.mkdir(parents=True, exist_ok=True)
    cursor = save / "ixion-delivery.cursor.json"
    consumed = consumed_path(ledger)
    marker = run / MARKER
    with lock(ledger), lock(cursor):
        if ledger.exists() or cursor.exists() or consumed.exists() or marker.exists():
            raise ValueError("ledger, cursor, consumed high-water or marker already exists; initialization never resets delivery state")
        identity = uuid.uuid4().hex
        # Both progress files before marker: partial initialization can only refuse.
        create(cursor, line({"version": 1, "ledger": identity, "seq": 0}))
        create(consumed, consumed_text(identity))
        create(ledger, ledger_text(identity, cursor))
        create(marker, line({"version": MARKER_VERSION, "ledger_format": LEDGER_VERSION, "ledger": identity}))
    print(f"ixion ledger initialized id={identity} ledger={ledger} cursor={cursor} marker={marker}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--dc1-save", required=True, type=Path)
    args = parser.parse_args()
    try:
        initialize(args.ledger, args.dc1_save)
    except (OSError, ValueError) as error:
        parser.exit(1, f"ixion ledger: {error}\n")
