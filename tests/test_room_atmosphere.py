from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import room_atmosphere as ra


def dc1_pack(entries: list[tuple[bytes, bytes]]) -> bytes:
    out = bytearray()
    for name, payload in entries:
        step = ((80 + len(payload) + 15) // 16) * 16
        out += name.ljust(64, b"\0") + struct.pack("<iiii", 80, len(payload), step, 0) + payload
        out += b"\0" * (step - 80 - len(payload))
    return bytes(out + b"\0" * 80)


TXT = b"d01a_a.hd\nd01c_a.sq\nd01a_a.sq\n\x81\x9b.sq\n"
TABLE = b"filename vol\nd01a_a.sq\t80\nd01c_a.sq\t94\n"
CFG = (b"\tAMBIENT\t\t0\t,0\t,0\n\tLIGHT_C\t\t1,\t0.6,\t1,\t120,\t110,\t100,\t2\n"
       b"\tFOG\t\t200\t,800\t,0\t,0\t,0\t,128\t,255\n\tBG_COL\t\t0\t,0\t,0\n")


class BgmPackTest(unittest.TestCase):
    def source(self) -> bytes:
        return dc1_pack([(b"d01a_a.hd", b"HD"), (b"d01a_a.bd", b"BD"), (b"d01c_a.sq", b"SQC"),
                         (b"d01a_a.sq", b"SQA"), (b"\x81\x9b.sq", b""), (b"bgm100.txt", TXT),
                         (b"bgm100.cfg", b"REVERBE 4,40\n")])

    def test_repacks_in_list_order_with_synthesised_cfg_and_vol(self) -> None:
        pack, info = ra.build_bgm_pack(self.source(), TABLE, "d01inter")
        members = ra.read_pack(pack)
        self.assertEqual([n for n, _ in members],
                         ["d01a_a.hd", "d01a_a.bd", "d01c_a.sq", "d01a_a.sq", "bgm100.vol", "bgm100.cfg"])
        self.assertEqual([s["name"] for s in info["sequences"]], ["d01c_a.sq", "d01a_a.sq"])
        self.assertEqual(info["reverb"], [4, 40])
        vol = dict(members)["bgm100.vol"].decode()
        self.assertIn("REVERB\t4\t40", vol)
        self.assertIn("0\t47", vol)  # 94 / 2.015748
        self.assertIn("1\t40", vol)  # 80 / 2.015748
        cfg = dict(members)["bgm100.cfg"]
        self.assertIn(b"0\td01c_a\td01c_a\t0\td01c_a.sq\t*\t*\t\x81\x9b\r", cfg)
        self.assertTrue(cfg.endswith(b"END\r"))

    def test_missing_volume_is_an_error(self) -> None:
        with self.assertRaises(ra.AtmosError):
            ra.build_bgm_pack(self.source(), b"filename vol\nd01a_a.sq\t80\n", "d01inter")

    def test_non_ascii_member_with_data_is_rejected(self) -> None:
        with self.assertRaises(ra.AtmosError):
            ra.read_pack(dc1_pack([(b"\x81\x9b.sq", b"x")]))


class CfgTest(unittest.TestCase):
    def test_fog_light_ambient_bg_and_scale(self) -> None:
        result = ra.parse_room_cfg(CFG, 1.5)
        self.assertEqual(result["fog"]["near"], 300.0)
        self.assertEqual(result["fog"]["far"], 1200.0)
        self.assertEqual(result["fog"]["far_value"], 128.0)
        self.assertEqual(result["fog"]["near_value"], 255.0)
        self.assertEqual(result["lights"][0]["slot"], 2)
        self.assertAlmostEqual(sum(c * c for c in result["lights"][0]["direction"]), 1.0)
        self.assertEqual(result["lights"][0]["color"], [120.0, 110.0, 100.0])
        self.assertEqual(result["ambient"], [0.0, 0.0, 0.0])

    def test_fog_arity_is_checked(self) -> None:
        with self.assertRaises(ra.AtmosError):
            ra.parse_room_cfg(b"FOG 200,800,0,0,0,128\n", 1.0)


if __name__ == "__main__":
    unittest.main()
