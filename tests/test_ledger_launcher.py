import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.ledger import MARKER, consumed_path, create, fnv1a64, initialize


def quiet_init(ledger, save):
    with contextlib.redirect_stdout(io.StringIO()):
        initialize(ledger, save)


class LedgerLauncher(unittest.TestCase):
    def test_init_binds_one_recipient_and_cannot_reset(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("IXION_LEDGER_TEST_ROOT")) as temporary:
            root = Path(temporary) / "run"
            ledger, save = root / "ledger.jsonl", root / "save"
            quiet_init(ledger, save)
            cursor = save / "ixion-delivery.cursor.json"
            lines = ledger.read_text().splitlines(keepends=True)
            header, trailer = json.loads(lines[0]), json.loads(lines[1])
            value = json.loads(cursor.read_text())
            marker = json.loads((root / MARKER).read_text())
            self.assertEqual(len(lines), 2)
            self.assertEqual(header["version"], 2)
            self.assertEqual(header["ledger"], value["ledger"])
            self.assertEqual(marker, {"version": 2, "ledger_format": 2, "ledger": header["ledger"]})
            self.assertEqual(header["cursor"], str(cursor.resolve()))
            self.assertEqual(trailer, {"end": 0, "fnv1a64": fnv1a64(lines[0].encode())})
            self.assertEqual(value["seq"], 0)
            ack = consumed_path(ledger)
            ack_lines = ack.read_text().splitlines(keepends=True)
            self.assertEqual(len(ack_lines), 2)
            self.assertEqual(json.loads(ack_lines[0]), {
                "version": 2, "ledger": value["ledger"], "seq": 0,
                "prefix_sha256": hashlib.sha256(b"").hexdigest(),
                "events_sha256": hashlib.sha256(b"").hexdigest()})
            self.assertEqual(json.loads(ack_lines[1]), {"end": 0, "fnv1a64": fnv1a64(ack_lines[0].encode())})
            before = ledger.read_bytes(), cursor.read_bytes(), ack.read_bytes(), (root / MARKER).read_bytes()
            with self.assertRaises(ValueError):
                initialize(ledger, save)
            self.assertEqual(before, (ledger.read_bytes(), cursor.read_bytes(), ack.read_bytes(), (root / MARKER).read_bytes()))

    def test_interrupted_initialization_never_authorizes_or_resets_progress(self):
        for fail_at in range(1, 5):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory(dir=os.environ.get("IXION_LEDGER_TEST_ROOT")) as temporary:
                root = Path(temporary) / "run"
                ledger, save = root / "ledger.jsonl", root / "save"
                writes = []

                def interrupted(path, text):
                    writes.append(path)
                    if len(writes) == fail_at:
                        raise OSError("simulated initialization crash")
                    create(path, text)

                with patch("tools.ledger.create", side_effect=interrupted), self.assertRaises(OSError):
                    quiet_init(ledger, save)
                self.assertFalse((root / MARKER).exists())
                snapshots = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
                with self.assertRaises(ValueError):
                    quiet_init(ledger, save)
                self.assertEqual(snapshots, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_legacy_fallback_and_consumed_cursor_are_never_migrated(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("IXION_LEDGER_TEST_ROOT")) as temporary:
            root = Path(temporary)
            save = root / "save"
            save.mkdir()
            ledger, cursor = root / "ledger.jsonl", save / "ixion-delivery.cursor.json"
            identity = "0123456789abcdef0123456789abcdef"
            header = json.dumps({"version": 1, "ledger": identity, "cursor": str(cursor)}) + "\n"
            record = ('{"seq":1,"source_game":"dc2","source_event":"kill:' + identity +
                      ':d01inter:0:1:e0:dc1-e104a","item":145,"created":123}\n')
            body = header + record
            ledger.write_text(body + json.dumps({"end": 1, "fnv1a64": fnv1a64(body.encode())}) + "\n")
            cursor.write_text(json.dumps({"version": 1, "ledger": identity, "seq": 1}) + "\n")
            marker = root / MARKER
            marker.write_text(json.dumps({"version": 1, "ledger": identity}) + "\n")
            before = ledger.read_bytes(), cursor.read_bytes(), marker.read_bytes()
            with self.assertRaisesRegex(ValueError, "fresh disposable run folder"):
                initialize(ledger, save)
            self.assertEqual(before, (ledger.read_bytes(), cursor.read_bytes(), marker.read_bytes()))

    def test_fnv1a64_matches_the_protocol_vectors(self):
        self.assertEqual(fnv1a64(b""), "cbf29ce484222325")
        self.assertEqual(fnv1a64(b"a"), "af63dc4c8601ec8c")

    def test_orphan_cursor_refuses_initialization(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("IXION_LEDGER_TEST_ROOT")) as temporary:
            root = Path(temporary)
            save = root / "save"
            save.mkdir()
            cursor = save / "ixion-delivery.cursor.json"
            cursor.write_text("existing cursor")
            with self.assertRaises(ValueError):
                initialize(root / "ledger.jsonl", save)
            self.assertEqual(cursor.read_text(), "existing cursor")
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_existing_campaign_save_root_is_refused(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("IXION_LEDGER_TEST_ROOT")) as temporary:
            root = Path(temporary)
            campaign = root / "campaign-saves"
            (campaign / "saves" / "1").mkdir(parents=True)
            (campaign / "saves" / "1" / "save.dat").write_bytes(b"campaign")
            run = root / "run"
            # A save root outside the run folder, and a non-empty run folder.
            with self.assertRaises(ValueError):
                initialize(run / "ledger.jsonl", campaign)
            with self.assertRaises(ValueError):
                initialize(root / "ledger.jsonl", campaign)
            self.assertFalse((campaign / "ixion-delivery.cursor.json").exists())
            self.assertFalse((run / MARKER).exists())
            self.assertFalse((root / MARKER).exists())


if __name__ == "__main__":
    unittest.main()
