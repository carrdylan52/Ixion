from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import dc1_mes
import georama_villagers as gv
import monster_converter as mc
from room_converter import ConvertError

DC1 = os.environ.get("IXION_DC1_DATA")

PLACE = (b"//header\r\nNPC_PLACE_NUM 3;\r\nNPC_PLACE  0 , -1 ;\r\n\tPLACE_POS 1,2,3,0;\r\nNPC_PLACE_END;\r\n"
         b"NPC_PLACE  2 , 10 ;\r\n\tPLACE_POS 1,2,3,0;\r\nNPC_PLACE_END;\r\n")
NPC = (b"PROG_INFO  1 , 0 , 0 , 0 ,\"x\";\r\nNPC  1 ;\r\n\tPROGRESS  1 , 0 ,\"x\";\r\n\t\tNOON_PLACE  0 ;\r\n\tPROGRESS_END;\r\nNPC_END;\r\n"
       b"NPC_INFO_NUM  3 ;\r\nNPC_INFO  1 ,\"a\",0,\"\",\"\",-1 ,-1 ;\r\nNPC_INFO  413 ,\"b\",-1,\"\",\"\",-1 ,-1 ;\r\n"
       b"NPC_INFO  1012 ,\"c\",-1,\"\",\"\",-1 ,-1 ;\r\n")


def villager(vlgr=420, place=3):
    return {"name": "Macho", "vlgr_id": vlgr, "place_id": place, "dc1_chr": "gedit/e01/chara/p01a.chr",
            "spot": {"pos": [70.5, 10.0, -12.3], "yaw": 1.5708}}


class OverlayRows(unittest.TestCase):
    def test_place_rows_extend_the_table_and_name_map_5(self):
        out = gv.patch_place_cfg(PLACE, [villager()])
        self.assertIn(b"NPC_PLACE_NUM 4;", out)
        self.assertIn(b"NPC_PLACE  3 , 5 ;\r\n\tPLACE_POS 70.5,10.0,-12.3,1.57;", out)

    def test_place_id_must_extend_contiguously(self):
        with self.assertRaises(ConvertError):
            gv.patch_place_cfg(PLACE, [villager(place=7)])

    def test_npc_info_rows_stay_sorted_and_counts_bump(self):
        out = gv.patch_npc_cfg(NPC, [villager()], {420: "ix_p01a"})
        self.assertIn(b"NPC_INFO_NUM  4 ;", out)
        ids = [int(line.split()[1]) for line in out.splitlines() if line.startswith(b"NPC_INFO ") and not line.startswith(b"NPC_INFO_NUM")]
        self.assertEqual(ids, [1, 413, 420, 1012])
        self.assertIn(b"NPC  420 ;", out)
        self.assertIn(b"NOON_PLACE  3 ;", out)
        self.assertLess(out.index(b"NPC  420 ;"), out.index(b"NPC_INFO_NUM"))

    def test_taken_or_out_of_range_villager_ids_are_refused(self):
        for bad in (1, 413, 512):
            with self.assertRaises(ConvertError):
                gv.patch_npc_cfg(NPC, [villager(vlgr=bad)], {bad: "ix_p01a"})


class Dc1Text(unittest.TestCase):
    def test_pages_names_and_unknown_controls(self):
        grid = dc1_mes.KGRID_FIRST
        codes = [grid + dc1_mes.KGRID.index("H"), grid + dc1_mes.KGRID.index("i"), dc1_mes.MES_NEWLINE, -0x506,
                 dc1_mes.MES_PAGE, grid + dc1_mes.KGRID.index("O"), -0x3FF]
        self.assertEqual(dc1_mes.to_pages(codes), ["Hi\nMax", "O"])

    def test_read_mes_table(self):
        words = [1, 0, 7, 2, -0x2DF, -0xFF]
        data = struct.pack("<%dh" % len(words), *words)
        self.assertEqual(dc1_mes.read_mes(data), {7: [-0x2DF]})

class Routes(unittest.TestCase):
    SPOT = {"pos": [70.5, 10.0, -12.3], "yaw": 1.5708}

    def test_route_is_deterministic_loops_home_and_stays_in_the_front_yard(self):
        route = gv.sample_route(420, self.SPOT)
        self.assertEqual(route, gv.sample_route(420, self.SPOT))
        moves = [n for n in route if n[0] == "move"]
        self.assertGreaterEqual(len(moves), 2)
        self.assertEqual(route[-1][0], "wait")
        self.assertEqual(moves[-1][1:4], (70.5, 10.0, -12.3))  # back on the spot, so DC2's route restart is seamless
        for _, x, y, z, _yaw in moves:
            self.assertEqual(y, 10.0)
            self.assertGreaterEqual(x, 70.5 - 0.1)  # spot yaw 1.57 faces +x: never behind the spot
            self.assertLessEqual(x, 70.5 + gv.ROUTE_FRONT + 0.1)
            self.assertLessEqual(abs(z - -12.3), gv.ROUTE_SIDE + 0.1)

    def test_every_profile_house_gets_a_moving_route(self):
        for seed, spot in ((420, {"pos": [70.5, 10.0, -12.3], "yaw": 1.5708}), (421, {"pos": [-56.0, 10.0, 13.2], "yaw": -0.7854}),
                           (422, {"pos": [16.5, 10.0, 30.3], "yaw": 0.0})):
            self.assertTrue(any(n[0] == "move" for n in gv.sample_route(seed, spot)))

    def test_route_rows_follow_the_native_place_syntax(self):
        v = villager()
        v["route"] = [("move", 1.0, 2.0, 3.0, 0.5), ("wait", 60), ("move", 70.5, 10.0, -12.3, 1.0)]
        out = gv.place_rows([v]).decode("ascii")
        self.assertIn('MOVE_MOTION "walk";\r\n\tMOVE_TO 1.0,2.0,3.0,0.50;\r\n\tWAIT "cnt",60,"stand";\r\n\tMOVE_TO 70.5,10.0,-12.3,1.00;\r\nNPC_PLACE_END;', out)


@unittest.skipUnless(DC1 and (Path(DC1) / "gedit/e01/chara/p01a.chr").is_file(), "needs IXION_DC1_DATA")
class RealVillager(unittest.TestCase):
    def test_convert_p01a_as_townsperson(self):
        with tempfile.TemporaryDirectory() as tmp:
            prov = mc.convert_villager(Path(DC1) / "gedit/e01/chara/p01a.chr", Path(tmp) / "out", display_name="Macho")
            self.assertEqual(prov["output_model"], "ix_p01a")
            report = prov["validation"]
            self.assertEqual(report["skin"]["frames"]["obj2"]["bone_count"], 18)
            self.assertIn("info.cfg", report["members"])
            self.assertEqual(report["shadow_triangles"], 0)
            self.assertEqual(report["key_names"][:4], ["立ち", "歩き", "走り", "会話"])
            self.assertEqual(prov["options"]["scale"], 1.0)
            self.assertTrue((Path(tmp) / "out/data/chara/ix_p01a.chr").is_file())
            self.assertEqual(prov["dropped"]["shadow"][0], "p01s.mds")

    def test_house_spots_follow_the_villager_index(self):
        scene = (Path(DC1) / "gedit/e01/scene.scn").read_bytes()
        self.assertIn("func_hito03", gv.house_frames(scene, "e01h02"))  # Macho is villager 3
        self.assertIn("func_hito10", gv.house_frames(scene, "e01h03"))  # Laura is villager 10
        self.assertIn("func_hito06", gv.house_frames(scene, "e01h10"))  # Paige is villager 6

    def test_profile_loads(self):
        doc = gv.load_profile(Path(mc.__file__).resolve().parent / "profiles/georama-norune-villagers.json")
        self.assertEqual([v["vlgr_id"] for v in doc["villagers"]], [420, 421, 422])
        self.assertEqual(doc["villagers"][1]["mes_ids"], [220, 221, 222, 223, 226])  # villager lines: offsets 0, 1, 2, 3, 6


if __name__ == "__main__":
    unittest.main()
