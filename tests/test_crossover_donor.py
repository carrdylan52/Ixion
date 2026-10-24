"""Source-only donor preflight tests using temporary Git fixtures, no retail data."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import check_crossover_donor as checker


class DonorPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ixion donor tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "donor with spaces"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Donor Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.names = ("ps2/src/dng_effect.cpp", "ps2/src/actionchara.cpp", "port/src/mg_math.cpp")
        self.data = (b"// header\nfloat helper_one() {\n return 1;\n}\n",
                     b"// header\nfloat helper_two() {\n return 2;\n}\n",
                     b"// header\nfloat math() { return 3; }\n")
        entries = []
        copied = []
        for name, data in zip(self.names, self.data):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            snippet = b"".join(data.splitlines(keepends=True)[1:]).rstrip(b"\r\n")
            entries.append({"path": name, "start": 2, "end": len(data.splitlines()),
                            "blob": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest(),
                            "sha256": hashlib.sha256(snippet).hexdigest()})
            copied.append(snippet)
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic donor")
        self.commit = self.git("rev-parse", "HEAD").strip()
        self.manifest = {"donor_commit": self.commit, "snippets": entries[:2], "math": entries[2]}
        self.helpers = Path(self.temp.name) / "C1 helpers" / "helpers.json"
        self.helpers.parent.mkdir()
        self.save_manifest()
        self.helpers.with_name("helpers.inc").write_bytes(b"\n\n".join(copied[:2]) + b"\n")

    def git(self, *args):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT="0")
        return subprocess.check_output(["git", "-C", str(self.root), *args], env=env,
                                       stderr=subprocess.PIPE, text=True)

    def save_manifest(self):
        self.helpers.write_text(json.dumps(self.manifest), encoding="utf-8")

    def check(self):
        return checker.check_donor(self.root, self.helpers)

    def snapshot(self):
        return {str(p.relative_to(self.temp.name)): p.read_bytes()
                for p in Path(self.temp.name).rglob("*") if p.is_file()}

    def test_clean_detached_checkout_and_path_with_spaces(self):
        self.git("checkout", "--detach", "-q", self.commit)
        result = self.check()
        self.assertEqual(result["donor_commit"], self.commit)
        self.assertEqual(result["required_files"], list(self.names))
        self.assertEqual(result["cmake_argument"], f"-DIXION_DC2_SOURCE_DIR:PATH={self.root}")

    def test_clean_branch_checkout(self):
        self.assertEqual(self.check()["donor_commit"], self.commit)

    def test_missing_donor_directory(self):
        with self.assertRaisesRegex(checker.DonorError, "directory does not exist"):
            checker.check_donor(self.root / "missing", self.helpers)

    def test_non_git_directory(self):
        other = Path(self.temp.name) / "not a repository"
        other.mkdir()
        with self.assertRaisesRegex(checker.DonorError, "git rev-parse failed"):
            checker.check_donor(other, self.helpers)

    def test_donor_must_be_repository_root(self):
        with self.assertRaisesRegex(checker.DonorError, "checkout root"):
            checker.check_donor(self.root / "ps2", self.helpers)

    def test_wrong_revision_even_when_source_bytes_match(self):
        self.git("commit", "--allow-empty", "-qm", "different revision")
        with self.assertRaisesRegex(checker.DonorError, "wrong donor revision"):
            self.check()

    def test_missing_required_source(self):
        (self.root / self.names[0]).unlink()
        with self.assertRaisesRegex(checker.DonorError, "missing or symlinked"):
            self.check()

    def test_modified_source_and_math_are_rejected(self):
        for name, data in zip(self.names, self.data):
            with self.subTest(name=name):
                path = self.root / name
                path.write_bytes(data + b"// drift\n")
                with self.assertRaisesRegex(checker.DonorError, "modified donor source"):
                    self.check()
                path.write_bytes(data)

    def test_staged_edit_cannot_hide_behind_restored_file(self):
        path = self.root / self.names[0]
        path.write_bytes(b"staged drift\n")
        self.git("add", self.names[0])
        path.write_bytes(self.data[0])
        with self.assertRaisesRegex(checker.DonorError, "modified donor index"):
            self.check()

    def test_wrong_manifest_blob(self):
        self.manifest["math"]["blob"] = "0" * 40
        self.save_manifest()
        with self.assertRaisesRegex(checker.DonorError, "recorded donor blob"):
            self.check()

    def test_wrong_snippet_hash(self):
        self.manifest["snippets"][0]["sha256"] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(checker.DonorError, "donor snippet differs"):
            self.check()

    def test_crlf_snippets_fail_existing_gate_compatibility(self):
        (self.root / self.names[0]).write_bytes(self.data[0].replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(checker.DonorError, "line endings"):
            self.check()

    def test_copied_helpers_must_match(self):
        self.helpers.with_name("helpers.inc").write_bytes(b"changed\n")
        with self.assertRaisesRegex(checker.DonorError, "copied helpers differ"):
            self.check()

    def test_missing_helpers_manifest_or_copy(self):
        self.helpers.unlink()
        with self.assertRaisesRegex(checker.DonorError, "cannot read helpers manifest"):
            self.check()
        self.save_manifest()
        self.helpers.with_name("helpers.inc").unlink()
        with self.assertRaisesRegex(checker.DonorError, "cannot read copied helpers"):
            self.check()

    def test_malformed_manifest_fails_closed(self):
        original = copy.deepcopy(self.manifest)
        cases = [None, {}, {**original, "donor_commit": "HEAD"},
                 {**original, "snippets": []}, {**original, "math": None}]
        for invalid in cases:
            with self.subTest(invalid=invalid):
                self.manifest = invalid
                self.save_manifest()
                with self.assertRaises(checker.DonorError):
                    self.check()

    def test_unsafe_manifest_paths_and_duplicate_paths(self):
        original = self.manifest["math"]["path"]
        for invalid in ("../outside.cpp", "/absolute.cpp", "C:/source.cpp", "ps2//x.cpp",
                        "ps2/./x.cpp", "ps2\\x.cpp", ".git/config", self.names[0]):
            with self.subTest(path=invalid):
                self.manifest["math"]["path"] = invalid
                self.save_manifest()
                with self.assertRaises(checker.DonorError):
                    self.check()
        self.manifest["math"]["path"] = original

    def test_invalid_source_range(self):
        self.manifest["math"]["end"] = 100
        self.save_manifest()
        with self.assertRaisesRegex(checker.DonorError, "range exceeds"):
            self.check()
        self.manifest["math"]["start"] = True
        self.save_manifest()
        with self.assertRaisesRegex(checker.DonorError, "invalid source range"):
            self.check()

    def test_symlink_source_is_rejected(self):
        path = self.root / self.names[0]
        target = Path(self.temp.name) / "outside.cpp"
        target.write_bytes(self.data[0])
        path.unlink()
        try:
            path.symlink_to(target)
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaisesRegex(checker.DonorError, "symlinked donor source"):
            self.check()

    def test_unrelated_files_are_not_provenance_inputs(self):
        (self.root / "unrelated-note.txt").write_text("untracked, not compiled")
        self.assertEqual(self.check()["donor_commit"], self.commit)

    def test_reads_only_and_no_network_or_mutations_on_success_and_failure(self):
        real_run = subprocess.run
        calls = []
        def checked_run(command, **kwargs):
            self.assertEqual(command[:5], ["git", "-c", "core.fsmonitor=false", "-C", str(self.root)])
            self.assertIn(command[5], ("rev-parse", "ls-tree", "ls-files"))
            env = kwargs["env"]
            for name in ("GIT_OPTIONAL_LOCKS", "GIT_TERMINAL_PROMPT"):
                self.assertEqual(env[name], "0")
            self.assertEqual(env["GIT_NO_LAZY_FETCH"], "1")
            self.assertEqual(env["GIT_NO_REPLACE_OBJECTS"], "1")
            self.assertEqual(env["GIT_ALLOW_PROTOCOL"], "")
            self.assertNotIn("GIT_DIR", env)
            calls.append(command)
            return real_run(command, **kwargs)
        for drift in (False, True):
            if drift:
                (self.root / self.names[2]).write_bytes(b"drift")
            before = self.snapshot()
            with mock.patch.object(checker.subprocess, "run", side_effect=checked_run), \
                    mock.patch.dict(os.environ, {"GIT_DIR": "/invalid/caller/override"}):
                if drift:
                    with self.assertRaises(checker.DonorError):
                        self.check()
                else:
                    self.check()
            self.assertEqual(before, self.snapshot())
        self.assertTrue(calls)

    def test_cli_requires_explicit_donor(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            checker.main([])
        self.assertEqual(raised.exception.code, 2)

    def test_cli_json_carries_single_cmake_argument_and_fails_closed(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ["--donor", str(self.root), "--helpers", str(self.helpers)]
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(checker.main(args), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["cmake_argument"], f"-DIXION_DC2_SOURCE_DIR:PATH={self.root}")
        (self.root / self.names[0]).unlink()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(checker.main(args), 1)
        self.assertIn("FAIL donor preflight", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
