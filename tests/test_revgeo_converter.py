"""Focused tests for tools/revgeo_converter.py (DC2 Shed -> private DC1 Georama part).

Real-data cases need IXION_DC2_DATA (the DC2 data root) and IXION_DC2_CATALOG (its port_data/catalog.json)
and skip without them; the rest run on synthetic input only. Nothing here writes retail bytes anywhere but a
temporary directory that the test removes.
"""
import json
import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import revgeo_converter as rc  # noqa: E402
from tools.monster_converter import mdt_header, read_mds  # noqa: E402
from tools.room_converter import parse_collision_mds  # noqa: E402

ConvertError = rc.ConvertError  # tools/revgeo_converter imports room_converter as a top-level module

DC2 = os.environ.get("IXION_DC2_DATA")
CATALOG = os.environ.get("IXION_DC2_CATALOG")
HAVE_DATA = bool(DC2 and CATALOG and Path(DC2).is_dir() and Path(CATALOG).is_file())

BOX = [[[0, 0, 0], [10, 0, 0], [10, 20, 0]], [[0, 0, 0], [10, 20, 0], [0, 20, 0]],
       [[0, 0, 5], [10, 20, 5], [10, 0, 5]], [[0, 0, 5], [0, 20, 5], [10, 20, 5]]]


class CollisionEmitterTests(unittest.TestCase):
    def test_dc1_collision_reads_back_through_the_dc1_reader_with_retails_layout(self):
        data, info = rc.dc1_collision_mds(BOX, "ixrg_test_col")
        self.assertEqual(info["triangles"], 4)
        self.assertEqual(info["vertices"], 8)
        self.assertEqual(data[:4], b"MDS\0")
        self.assertEqual(struct.unpack_from("<3i", data, 4), (1, 1, 16))
        # the room converter's reader is the DC1 collision reader (MDT_COLLISION set at mesh_ofs, 20-byte polys)
        tris = parse_collision_mds(data, (0, 0, 0), 0)
        self.assertEqual(len(tris), 4)
        self.assertEqual(sorted(tuple(tuple(round(c, 3) for c in v) for v in t) for t in tris),
                         sorted(tuple(tuple(float(c) for c in v) for v in t) for t in BOX))
        mdt = 16 + rc.MDS_RECORD
        self.assertEqual(data[mdt:mdt + 4], b"MDT\0")
        head = struct.unpack_from("<16i", data, mdt)
        self.assertEqual(head[1], 64)                      # header size
        self.assertEqual(head[2], len(data) - mdt)         # whole resource
        self.assertEqual(head[3], 8)                       # vertices
        self.assertEqual(head[4], 64)                      # vertex_ofs
        mesh_ofs, info_ofs = head[10], head[14]
        self.assertEqual(mesh_ofs, 64 + 8 * 16)
        self.assertEqual(struct.unpack_from("<6i", data, mdt + mesh_ofs), (rc.COLLISION_TAG, 16, 4, 0, 3, 4))
        self.assertEqual(info_ofs % 16, 0)
        self.assertEqual(head[2] - info_ofs, 32)           # two 16-byte attribute records, as retail's
        for k in range(4):
            poly = struct.unpack_from("<5i", data, mdt + mesh_ofs + 24 + k * 20)
            self.assertTrue(all(0 <= i < 8 for i in poly[:3]))
            self.assertEqual(poly[3], 0)                    # attribute record 0
        record = data[mdt + info_ofs:mdt + info_ofs + 16]
        self.assertEqual(struct.unpack_from("<4h", record), (0, 0, 0, 0))   # ground kind, foot sound, area, ignore mask
        normals = head[6]
        for k in range(head[5]):
            n = struct.unpack_from("<3f", data, mdt + normals + k * 16)
            self.assertAlmostEqual(math.sqrt(sum(c * c for c in n)), 1.0, places=5)

    def test_collision_refuses_nothing_and_too_much(self):
        with self.assertRaises(ConvertError):
            rc.dc1_collision_mds([], "x")
        with self.assertRaises(ConvertError):
            rc.dc1_collision_mds(BOX * 300, "x")


class ArchiveTests(unittest.TestCase):
    def test_definition_matches_retails_part_header_for_a_footprint(self):
        blob = rc.part_definition(2, 3, 0x80, 0)
        (size, data_size, width, height, kind) = struct.unpack_from("<5i", blob, 0)
        self.assertEqual((size, width, height, kind), (0x78, 2, 3, 0))
        self.assertEqual(data_size, len(blob))
        self.assertEqual(struct.unpack_from("<I", blob, 0x3C)[0], 0x78)            # cell map offset
        self.assertEqual(blob[0x78:0x78 + 6], b"\x80" * 6)
        self.assertEqual(struct.unpack_from("<6i", blob, 0x40), (-1,) * 6)         # no elements
        self.assertEqual(struct.unpack_from("<6I", blob, 0x58), (0,) * 6)
        func_off, func_count = struct.unpack_from("<Ii", blob, 0x70)
        self.assertEqual(func_count, 0)
        self.assertEqual(func_off, data_size)

    def test_archive_offsets_and_scene_directory_resolve_like_searchpts(self):
        definition = rc.part_definition(1, 1, 0x80, 0)
        lod0 = b"MDS\0" + b"\x11" * 28
        collision = b"MDS\0" + b"\x22" * 60
        archive = rc.eparts_archive("ixrg_t", definition, lod0, collision)
        scene = rc.scene_of("ixrg_t", archive)
        self.assertEqual(scene[:4], b"SCN\0")
        count = struct.unpack_from("<I", scene, 4)[0]
        self.assertEqual(count, 1)
        self.assertEqual(scene[16:32].split(b"\0")[0], b"ixrg_t")
        base = struct.unpack_from("<i", scene, 32)[0]
        self.assertEqual(base % 16, 0)
        entry = scene[base:]
        self.assertEqual(entry[:4], b"PTS\0")
        info, = struct.unpack_from("<i", entry, 4)
        self.assertEqual(info, 0xE0)
        self.assertEqual(entry[info:info + len(definition)], definition)
        lod_off, = struct.unpack_from("<i", entry, 0x48)
        lod_size, = struct.unpack_from("<i", entry, 0x58)
        self.assertEqual(entry[lod_off:lod_off + lod_size], lod0)
        col_off, col_size = struct.unpack_from("<2i", entry, 0x78)
        self.assertEqual(entry[col_off:col_off + col_size], collision)
        self.assertEqual(lod_off % 16 + col_off % 16, 0)
        for absent in (0x4C, 0x50, 0x54, 0x5C, 0x60, 0x64, 0x90, 0x94, 0xA8, 0xAC, 0xC0, 0xC4, 0xD8, 0xDC):
            self.assertEqual(struct.unpack_from("<i", entry, absent)[0], 0, hex(absent))


class PictureTests(unittest.TestCase):
    def test_gs_alpha_is_half_range_and_png_reader_is_bounded(self):
        self.assertEqual(rc.gs_rgba(bytes([1, 2, 3, 255, 4, 5, 6, 0, 7, 8, 9, 128])),
                         bytes([1, 2, 3, 128, 4, 5, 6, 0, 7, 8, 9, 64]))
        from tools.room_converter import png_rgba as write_png
        pixels = bytes([10, 20, 30, 255, 40, 50, 60, 128, 70, 80, 90, 0, 100, 110, 120, 255])
        rgba, w, h = rc.png_rgba(write_png(2, 2, pixels))
        self.assertEqual((w, h, rgba), (2, 2, pixels))
        with self.assertRaises(ConvertError):
            rc.png_rgba(b"not a png")
        with self.assertRaises(ConvertError):
            rc.png_rgba(write_png(2, 2, pixels)[:-5])

    def test_catalog_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory(prefix="ixion-revgeo-") as tmp:
            root = Path(tmp)
            (root / "ok.png").write_bytes(b"x")
            self.assertEqual(rc.safe_catalog_file(root, "ok.png"), (root / "ok.png").resolve())
            for bad in ("../ok.png", "a/../../ok.png", "C:/x.png", "a\\b.png"):
                with self.assertRaises(ConvertError):
                    rc.safe_catalog_file(root, bad)

    def test_icon_is_an_84_cell_in_a_128_sheet_with_the_name_in_pixels(self):
        # a quad lit from above, drawn with no picture available: opaque where it is, clear elsewhere
        mds = self._single_quad_visual()
        icon = rc.render_icon(mds, {}, "SHED")
        self.assertEqual(len(icon), 128 * 128 * 4)
        alpha = [icon[i] for i in range(3, len(icon), 4)]
        self.assertTrue(any(a == 255 for a in alpha))
        outside = [icon[(y * 128 + x) * 4 + 3] for y in range(128) for x in range(84, 128)]
        self.assertEqual(set(outside), {0})
        label = [(x, y) for y in range(0, 14) for x in range(84) if icon[(y * 128 + x) * 4:(y * 128 + x) * 4 + 3] == bytes((255, 236, 150))]
        self.assertGreater(len(label), 40)

    @staticmethod
    def _single_quad_visual() -> bytes:
        verts = [(-10, 0, -10), (10, 0, -10), (10, 0, 10), (-10, 0, 10)]
        vertices = b"".join(struct.pack("<4f", *v, 1) for v in verts)
        normals = struct.pack("<4f", 0, 1, 0, 0)
        uvs = b"".join(struct.pack("<4f", u, v, 0, 0) for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)))
        faces = struct.pack("<4i", 0, 16, 1, 0) + struct.pack("<3I", 3, 6, 0)
        for tri in ((0, 1, 2), (0, 2, 3)):
            for i in tri:
                faces += struct.pack("<3i", i, 0, i)
        faces += b"\0" * ((-len(faces)) % 16)
        material = struct.pack("<13f", 1, 1, 1, 1, .5, .5, .5, 1, 0, 0, 0, 0, 0)[:48] + struct.pack("<i", 0) + b"none".ljust(44, b"\0")
        vo, no = 64, 64 + len(vertices)
        uo = no + len(normals)
        fo = uo + len(uvs)
        mo = fo + len(faces)
        size = mo + len(material)
        header = b"MDT\0" + struct.pack("<15i", 64, size, 4, vo, 1, no, 0, -1, len(faces), fo, 4, uo, 1, mo, 0)
        mdt = header + vertices + normals + uvs + faces + material
        matrix = (1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.)
        record = struct.pack("<2i", 0, 112) + b"quad".ljust(32, b"\0") + struct.pack("<2i16f", 128, -1, *matrix)
        return b"MDS\0" + struct.pack("<3i", 1, 1, 16) + record + mdt


@unittest.skipUnless(HAVE_DATA, "needs IXION_DC2_DATA and IXION_DC2_CATALOG")
class ShedConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ixion-revgeo-shed-")
        cls.out = Path(cls.tmp.name) / "pack"
        cls.manifest = rc.convert(Path(DC2), Path(CATALOG), cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_output_is_new_only_and_listed_in_the_manifest(self):
        with self.assertRaisesRegex(ConvertError, "refusing to overwrite"):
            rc.convert(Path(DC2), Path(CATALOG), self.out)
        names = {p.name for p in self.out.iterdir()}
        self.assertEqual(names, {"revgeo.json", "revgeo.scn", "ixrg_a0101.rgba", "ixrg_a0102.rgba",
                                 "ixrg_icon.rgba", "ixrg_icon.png"})
        manifest = json.loads((self.out / "revgeo.json").read_text())
        self.assertEqual((manifest["format"], manifest["version"], manifest["town"], manifest["plot"]),
                         ("ixion-revgeo-dc1", 1, 0, 17))
        for texture in manifest["textures"]:
            data = (self.out / texture["file"]).read_bytes()
            self.assertEqual(len(data), texture["width"] * texture["height"] * 4)
            self.assertTrue(texture["name"].startswith("ixrg_") and len(texture["name"]) <= 31)
            self.assertEqual(rc.sha256(data), texture["sha256"])
            self.assertLessEqual(max(data[3::4]), 128)      # GS alpha

    def test_scale_is_the_reciprocal_of_dc1_to_dc2(self):
        self.assertAlmostEqual(self.manifest["scale"], 1 / 1.5584790683, places=9)
        bounds = self.manifest["provenance"]["visual_bounds_dc1"]
        # the DC2 Shed measures about 90 x 99.6 x 90 DC2 units
        self.assertAlmostEqual(bounds[0][1] - bounds[0][0], 89.6 / 1.5584790683, delta=2.0)
        self.assertAlmostEqual(bounds[1][1], 99.6 / 1.5584790683, delta=2.0)
        self.assertAlmostEqual(bounds[0][0] + bounds[0][1], 0.0, delta=2.0)     # recentred on the placement volume

    def test_visual_is_a_dc1_scene_the_dc1_renderer_can_read(self):
        scene = (self.out / "revgeo.scn").read_bytes()
        base = struct.unpack_from("<i", scene, 32)[0]
        archive = scene[base:]
        lod_off, lod_size = struct.unpack_from("<i", archive, 0x48)[0], struct.unpack_from("<i", archive, 0x58)[0]
        visual = archive[lod_off:lod_off + lod_size]
        objects = read_mds(visual, "visual")
        self.assertEqual(len(objects), 9)
        textures = set()
        triangles = 0
        for obj in objects:
            if not obj.mesh:
                continue
            h = mdt_header(visual, obj.mesh)
            faces = obj.mesh + h["faces_ofs"]
            groups = struct.unpack_from("<i", visual, faces + 8)[0]
            cur = faces + 16
            stride = 4 if h["colour_ofs"] > 0 and h["colour_num"] > 0 else 3
            for _ in range(groups):
                prim, count, material = struct.unpack_from("<3I", visual, cur)
                self.assertIn(prim, (3, 4), "DC1's renderer reads the primitive as 3 or 4 and the colour column from the header")
                self.assertLess(material, h["material_num"])
                for k in range(count):
                    v, n, t = struct.unpack_from("<3i", visual, cur + 12 + k * stride * 4)
                    self.assertTrue(0 <= v < h["vertex_num"] and 0 <= n < h["normal_num"] and 0 <= t < h["uv_num"])
                cur += 12 + count * stride * 4
                triangles += count // 3 if prim == 3 else count - 2
            for m in range(h["material_num"]):
                at = obj.mesh + h["material_ofs"] + m * 96 + 52
                textures.add(visual[at:at + 44].split(b"\0")[0].decode())
        self.assertEqual(textures, {"ixrg_a0101", "ixrg_a0102"})       # the DC2 blob-shadow card kage02 is dropped
        self.assertEqual(triangles, self.manifest["provenance"]["visual"]["triangles"])
        self.assertEqual(self.manifest["provenance"]["visual"]["dropped"], ["2nuki--a01zp1n1z0"])

    def test_collision_is_the_wall_piece_at_dc1_scale_inside_the_footprint_height(self):
        scene = (self.out / "revgeo.scn").read_bytes()
        base = struct.unpack_from("<i", scene, 32)[0]
        archive = scene[base:]
        off, size = struct.unpack_from("<2i", archive, 0x78)
        tris = parse_collision_mds(archive[off:off + size], (0, 0, 0), 0)
        self.assertEqual(len(tris), 24)
        xs = [v[0] for t in tris for v in t]
        ys = [v[1] for t in tris for v in t]
        self.assertAlmostEqual(max(xs) - min(xs), 61.4, delta=0.6)
        self.assertAlmostEqual(max(ys), 140.3 / 1.5584790683, delta=0.6)
        self.assertEqual(self.manifest["part"]["cells"], [1, 1])


if __name__ == "__main__":
    unittest.main()
