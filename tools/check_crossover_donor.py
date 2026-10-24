"""Read-only preflight for C1's separate, pinned ChronicleTwo source donor.

This supplements, never replaces, port/ixdc2/check_symbols.py. It does not
fetch, checkout, repair, build, or modify either repository.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


class DonorError(ValueError):
    """The requested donor cannot be qualified from local source bytes."""


def git_read(root, *args):
    # Ignore caller repository overrides; never refresh the index, invoke a
    # filesystem-monitor hook, or lazily fetch a missing partial-clone object.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1",
               GIT_ALLOW_PROTOCOL="")
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
            env=env, capture_output=True, check=False)
    except OSError as exc:
        raise DonorError(f"cannot read donor Git metadata: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise DonorError(f"git {args[0]} failed: {detail}")
    return result.stdout


def require_hash(value, length, label):
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{length}}}", value):
        raise DonorError(f"{label} must be a full lowercase {length}-digit hash")
    return value


def manifest_entries(manifest):
    if not isinstance(manifest, dict):
        raise DonorError("helpers manifest must be an object")
    require_hash(manifest.get("donor_commit"), 40, "donor_commit")
    snippets = manifest.get("snippets")
    math = manifest.get("math")
    if not isinstance(snippets, list) or not snippets or not isinstance(math, dict):
        raise DonorError("helpers manifest needs nonempty snippets and a math entry")
    seen = set()
    for entry in [*snippets, math]:
        if not isinstance(entry, dict):
            raise DonorError("each manifest entry must be an object")
        path = entry.get("path")
        if (not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", path)
                or PurePosixPath(path).is_absolute()
                or str(PurePosixPath(path)) != path
                or any(part in ("..", ".git") for part in PurePosixPath(path).parts)):
            raise DonorError("manifest source paths must be canonical repository-relative paths")
        if path in seen:
            raise DonorError(f"duplicate manifest path: {path}")
        seen.add(path)
        require_hash(entry.get("blob"), 40, f"blob for {path}")
        start, end = entry.get("start"), entry.get("end")
        if type(start) is not int or type(end) is not int or not 1 <= start <= end:
            raise DonorError(f"invalid source range: {path}")
    for entry in snippets:
        require_hash(entry.get("sha256"), 64, f"snippet hash for {entry['path']}")
    return snippets, math


def check_donor(donor, helpers):
    """Return verified configuration; only Git reads and local file reads occur."""
    root = Path(donor).expanduser().resolve()
    if not root.is_dir():
        raise DonorError(f"donor directory does not exist: {root}")
    helpers = Path(helpers)
    try:
        manifest = json.loads(helpers.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise DonorError(f"cannot read helpers manifest: {exc}") from exc
    snippets, math = manifest_entries(manifest)
    top = Path(os.fsdecode(git_read(root, "rev-parse", "--show-toplevel").rstrip(b"\r\n"))).resolve()
    if top != root:
        raise DonorError("--donor must name the donor checkout root, not a subdirectory")
    head = git_read(root, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if head != manifest["donor_commit"]:
        raise DonorError(f"wrong donor revision: expected {manifest['donor_commit']}, found {head}")

    copied = []
    for entry in [*snippets, math]:
        name = entry["path"]
        path = root / name
        if path.resolve() != path or not path.is_file():
            raise DonorError(f"missing or symlinked donor source: {name}")
        # Check HEAD and the index too, so staged edits cannot hide behind
        # restored worktree bytes. No status/diff filters or external tools run.
        tree = git_read(root, "ls-tree", "-z", "HEAD", "--", name)
        expected = f"100644 blob {entry['blob']}\t{name}\0".encode()
        if tree != expected:
            raise DonorError(f"recorded donor blob/mode mismatch: {name}")
        index = git_read(root, "ls-files", "--stage", "-z", "--", name)
        expected_index = f"100644 {entry['blob']} 0\t{name}\0".encode()
        if index != expected_index:
            raise DonorError(f"modified donor index: {name}")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise DonorError(f"cannot read donor source {name}: {exc}") from exc
        normalized = data.replace(b"\r\n", b"\n")
        blob = hashlib.sha1(f"blob {len(normalized)}\0".encode() + normalized).hexdigest()
        if blob != entry["blob"]:
            raise DonorError(f"modified donor source: {name}")
        lines = data.splitlines(keepends=True)
        if entry["end"] > len(lines):
            raise DonorError(f"source range exceeds donor file: {name}")
        if entry is not math:
            snippet = b"".join(lines[entry["start"] - 1:entry["end"]]).rstrip(b"\r\n")
            if hashlib.sha256(snippet).hexdigest() != entry["sha256"]:
                raise DonorError(f"donor snippet differs from existing gate (including line endings): {name}")
            copied.append(snippet)
    try:
        actual = helpers.with_name("helpers.inc").read_bytes()
    except OSError as exc:
        raise DonorError(f"cannot read copied helpers: {exc}") from exc
    if actual != b"\n\n".join(copied) + b"\n":
        raise DonorError("copied helpers differ from donor; do not regenerate or repin automatically")
    return {"donor": str(root), "donor_commit": head,
            "required_files": [entry["path"] for entry in [*snippets, math]],
            "cmake_argument": f"-DIXION_DC2_SOURCE_DIR:PATH={root}"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor", required=True, help="explicit, separate donor Git checkout root")
    parser.add_argument("--helpers", type=Path, default=Path(__file__).resolve().parents[1]
                        / "games/chronicle/port/ixdc2/helpers.json",
                        help="C1's unchanged helpers.json (helpers.inc must be beside it)")
    args = parser.parse_args(argv)
    try:
        result = check_donor(args.donor, args.helpers)
    except (DonorError, OSError, UnicodeError) as exc:
        print(f"FAIL donor preflight: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
