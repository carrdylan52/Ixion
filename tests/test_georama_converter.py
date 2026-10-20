import json
import os
import struct
import tempfile
import unittest
from pathlib import Path

from tools.georama_converter import (collision_mds, drop_objects, load_profile, prepare, scene_part,
                                     select_img, ConvertError)
from tools.monster_converter import read_mds, mdt_header, validate_mdt


class GeoramaConverterTests(unittest.TestCase):
    def test_collision_emits_vertex_only_lists_and_native_area_materials(self):
        data, report = collision_mds([[[0, 0, 0], [0, 0, 100], [100, 0, 100]]])
        obj = read_mds(data, "fixture")[0]
        header = mdt_header(data, obj.mesh)
        self.assertEqual(report["areas"], {"2": 1, "1": 2, "3": 2, "5": 8})
        self.assertEqual(header["vertex_num"], 39)
        cur = obj.mesh + header["faces_ofs"] + 16
        for i, area in enumerate((2, 1, 3, 5)):
            kind, count, material = struct.unpack_from("<3i", data, cur)
            self.assertEqual(kind, 0x213)
            self.assertEqual(material, i)
            ids = struct.unpack_from(f"<{count}i", data, cur + 12)
            self.assertTrue(all(0 <= n < header["vertex_num"] for n in ids))
            diffuse = struct.unpack_from("<4f", data, obj.mesh + header["material_ofs"] + i * 96)
            self.assertEqual(int(diffuse[2] * .7 + .01), area)
            cur += 12 + count * 4

    def test_scene_and_collision_reject_truncation_and_empty_input(self):
        with self.assertRaises(ConvertError):
            scene_part(b"SCN\0" + struct.pack("<I", 30) + b"\0" * 8, "e01t01", 0x48, 0x58)
        with self.assertRaises(ConvertError):
            collision_mds([])
        with self.assertRaises(ConvertError):
            select_img(b"\0" * 100, {"e01t02"})

    def test_existing_output_is_never_modified(self):
        with tempfile.TemporaryDirectory(prefix="ixion-georama-") as tmp:
            root = Path(tmp)
            sentinel = root / "owned-by-someone-else"
            sentinel.write_bytes(b"keep")
            with self.assertRaisesRegex(ConvertError, "already exists"):
                prepare(root / "absent-dc1", root / "absent-dc2", root)
            self.assertEqual(sentinel.read_bytes(), b"keep")

    @unittest.skipUnless(os.environ.get("IXION_DC1_DATA") and os.environ.get("IXION_DC2_DATA"), "private data")
    def test_real_tree_and_language_scripts_without_touching_native_inputs(self):
        dc1 = Path(os.environ["IXION_DC1_DATA"])
        dc2 = Path(os.environ["IXION_DC2_DATA"]).parent
        # A small native input fixture avoids copying unrelated retail assets in a unit test.
        with tempfile.TemporaryDirectory(prefix="ixion-georama-") as tmp:
            fixture = Path(tmp) / "native"
            paths = ["map/map0.cfg", "map/map1.cfg"]
            paths += ["map/g/g01/" + n for n in ("g01.map", "g01.mpk", "g01.ipk", "g010.gpi", "g011.gpi")]
            original = {}
            for rel in paths:
                original[rel] = (dc2 / "data" / rel).read_bytes()
                dest = fixture / "data" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(original[rel])
            (fixture / "port_data").mkdir()
            (fixture / "port_data/catalog.json").write_text('{"schema_version":1,"sources":[]}')
            out = Path(tmp) / "out"
            prepare(dc1, fixture, out)
            for rel, expected in original.items():
                self.assertEqual((fixture / "data" / rel).read_bytes(), expected)
            for lang in (0, 1):
                table = (out / f"data/map/map{lang}.cfg").read_bytes()
                self.assertIn(b'MAP_NAME "gix"', table.splitlines()[6])
                gpi = (out / f"data/map/g/gix/gix{lang}.gpi").read_bytes()
                self.assertIn(b'PARTS_NAME "ix_e01t01"', gpi)
                self.assertIn(b'ID 50;', gpi)
            catalog = json.loads((out / "port_data/catalog.json").read_text())
            textures = catalog["sources"][0]["entries"]
            self.assertEqual({e["name"] for e in textures}, {"ix_e01t20", "ix_e01t25"})
            for texture in textures:
                self.assertTrue((out / "port_data" / texture["variants"][0]["levels"][0]).is_file())
            provenance = json.loads((out / "georama-provenance.json").read_text())
            self.assertEqual(provenance["parts"][0]["collision"]["source_triangles"], 32)
            self.assertEqual(provenance["scale"], 1)
            self.assertEqual(provenance["parts"][0]["polyn_cost"][0], 180)
            world = (out / "world_collision.mds").read_bytes()
            mesh = read_mds(world, "world collision")[0].mesh
            header = mdt_header(world, mesh)
            self.assertEqual(header["material_num"], 1)
            self.assertEqual(header["vertex_num"], 32 * 3)
            script = (out / "data/map/g/gix/gix.map").read_bytes()
            self.assertIn(b'PIECE "ix_e01t01-w.mds",1;', script)

    def test_profile_rejects_native_ids_duplicates_and_bad_names(self):
        for parts in ([{"id": 4, "scene": "e01h02", "name": "Macho House"}],
                      [{"id": 51, "scene": "e01h02", "name": "A"}, {"id": 52, "scene": "e01h02", "name": "B"}],
                      [{"id": 51, "scene": "e01h02", "name": "A"}, {"id": 51, "scene": "e01h03", "name": "B"}],
                      [{"id": 51, "scene": "../x", "name": "A"}],
                      [{"id": 51, "scene": "e01h02", "name": "Name with quote\""}],
                      []):
            with tempfile.TemporaryDirectory(prefix="ixion-georama-") as tmp:
                path = Path(tmp) / "profile.json"
                path.write_text(json.dumps({"parts": parts}))
                with self.assertRaises(ConvertError):
                    load_profile(path)
        shipped = load_profile(Path(__file__).resolve().parents[1] / "tools/profiles/georama-norune-houses.json")
        self.assertEqual([p["id"] for p in shipped["parts"]], [50, 51, 52, 54, 55])

    def test_drop_objects_detaches_meshes_but_keeps_frames_and_refuses_dropping_all(self):
        def mds(names):
            body = b"MDS\0" + struct.pack("<3i", 1, len(names), 16)
            for i, name in enumerate(names):
                body += struct.pack("<2i", i, 112) + name.encode().ljust(32, b"\0")
                body += struct.pack("<2i16f", 4096, -1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
            return body + b"\0" * 8192
        data = mds(["body", "glow__CFN"])
        out, dropped = drop_objects(data, "__CF")
        self.assertEqual(dropped, ["glow__CFN"])
        self.assertEqual(struct.unpack_from("<i", out, 16 + 112 + 40)[0], 0)
        self.assertEqual(out[16 + 112 + 8:16 + 112 + 18], b"glow__CFN\0")  # frame stays
        self.assertEqual(struct.unpack_from("<i", out, 16 + 40)[0], 4096)
        self.assertEqual(drop_objects(data, None), (data, []))
        with self.assertRaises(ConvertError):
            drop_objects(data, ".")

    @unittest.skipUnless(os.environ.get("IXION_DC1_DATA") and os.environ.get("IXION_DC2_DATA"), "private data")
    def test_real_houses_convert_and_the_fixed_building_is_refused_with_its_reason(self):
        dc1 = Path(os.environ["IXION_DC1_DATA"])
        dc2 = Path(os.environ["IXION_DC2_DATA"]).parent
        profile = load_profile(Path(__file__).resolve().parents[1] / "tools/profiles/georama-norune-houses.json")
        with tempfile.TemporaryDirectory(prefix="ixion-georama-") as tmp:
            fixture = Path(tmp) / "native"
            paths = ["map/map0.cfg", "map/map1.cfg"]
            paths += ["map/g/g01/" + n for n in ("g01.map", "g01.mpk", "g01.ipk", "g010.gpi", "g011.gpi")]
            for rel in paths:
                dest = fixture / "data" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((dc2 / "data" / rel).read_bytes())
            (fixture / "port_data").mkdir()
            (fixture / "port_data/catalog.json").write_text('{"schema_version":1,"sources":[]}')
            out = Path(tmp) / "out"
            provenance = prepare(dc1, fixture, out, profile)
            self.assertEqual([p["scene"] for p in provenance["parts"]], ["e01t01", "e01h02", "e01h03", "e01h10"])
            self.assertEqual(len(provenance["refusals"]), 1)
            self.assertEqual(provenance["refusals"][0]["scene"], "e01h06")
            self.assertIn("index 657 out of range", provenance["refusals"][0]["reason"])
            house = provenance["parts"][1]
            self.assertEqual(house["collision"]["source_triangles"], 234)
            self.assertEqual(sorted(house["dropped_objects"]), ["Kwin2__CFN", "effect__CFAPPZN", "light2__CFN", "win2__CFN"])
            gpi = (out / "data/map/g/gix/gix1.gpi").read_bytes()
            for part_id in (50, 51, 52, 54):
                self.assertIn(f"ID {part_id};".encode(), gpi)
            self.assertNotIn(b"ID 55;", gpi)
            script = (out / "data/map/g/gix/gix.map").read_bytes()
            for scene in ("e01t01", "e01h02", "e01h03", "e01h10"):
                self.assertIn(f'PCP "ix_{scene}.pcp";'.encode(), script)
                self.assertIn(f'PIECE "ix_{scene}-w.mds",1;'.encode(), script)
            catalog = json.loads((out / "port_data/catalog.json").read_text())
            names = {e["name"] for e in catalog["sources"][-1]["entries"]}
            self.assertTrue({"ix_e01t03", "ix_e01t09", "ix_e01t10", "ix_e01t11", "ix_e01t12", "ix_e01t20", "ix_e01t25"} <= names)
            for entry in catalog["sources"][-1]["entries"]:
                self.assertTrue((out / "port_data" / entry["variants"][0]["levels"][0]).is_file())

    def test_a_part_refused_without_optional_aborts_the_run(self):
        with tempfile.TemporaryDirectory(prefix="ixion-georama-") as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(json.dumps({"parts": [{"id": 55, "scene": "e01h06", "name": "Fixed"}]}))
            profile = load_profile(path)
            self.assertFalse(profile["parts"][0].get("optional"))
            if not (os.environ.get("IXION_DC1_DATA") and os.environ.get("IXION_DC2_DATA")):
                self.skipTest("private data")
            with self.assertRaisesRegex(ConvertError, "refused"):
                prepare(Path(os.environ["IXION_DC1_DATA"]), Path(os.environ["IXION_DC2_DATA"]).parent,
                        Path(tmp) / "out", profile)
            self.assertFalse((Path(tmp) / "out").exists())


if __name__ == "__main__":
    unittest.main()
