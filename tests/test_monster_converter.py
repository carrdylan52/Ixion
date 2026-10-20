from __future__ import annotations

import json
import contextlib
import io
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import monster_converter as mc
from room_converter import ConvertError


def mdt(material_names=("tex01",), prims=((4, [(0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3)]),),
        colour_ofs=0, unk_3c=0, name_field=44) -> bytes:
    """Synthetic visual MDT in the shared DC1/DC2 0x40 layout: 4 verts/normals/uvs, FACES, materials."""
    verts = b"".join(struct.pack("<4f", x, 0, 0, 1) for x in range(4))
    faces = bytearray(struct.pack("<iiii", 0, 16, len(prims), 0))
    for ftype, idx in prims:
        faces += struct.pack("<III", ftype, len(idx), 0)
        for tup in idx:
            faces += struct.pack(f"<{len(tup)}i", *tup)
    faces = bytes(faces)
    vofs = 0x40
    nofs = vofs + len(verts)
    fofs = nofs + len(verts)
    uofs = fofs + ((len(faces) + 15) // 16) * 16
    mofs = uofs + len(verts)
    mats = b""
    for name in material_names:
        rec = struct.pack("<13f", *([1.0] * 7 + [0.0] * 5 + [50.0])) + name.encode("ascii").ljust(name_field, b"\0")
        mats += rec[:96].ljust(96, b"\0")
    size = mofs + len(mats)
    head = b"MDT\0" + struct.pack("<15i", 0x40, size, 4, vofs, 4, nofs, 0, colour_ofs, len(faces), fofs, 4, uofs,
                                  len(material_names), mofs, unk_3c)
    body = bytearray(size)
    body[:0x40] = head
    body[vofs:vofs + 64] = verts
    body[nofs:nofs + 64] = verts
    body[fofs:fofs + len(faces)] = faces
    body[uofs:uofs + 64] = verts
    body[mofs:mofs + len(mats)] = mats
    return bytes(body)


def mds(objects: list[tuple[str, int, bytes | None]]) -> bytes:
    table = 16 + 112 * len(objects)
    blobs, offsets, cur = [], [], table
    for _n, _p, body in objects:
        if body is None:
            offsets.append(0)
            continue
        cur = (cur + 15) // 16 * 16
        offsets.append(cur)
        blobs.append((cur, body))
        cur += len(body)
    out = bytearray(cur)
    out[:16] = b"MDS\0" + struct.pack("<III", 1, len(objects), 16)
    for i, (name, parent, _b) in enumerate(objects):
        at = 16 + i * 112
        struct.pack_into("<ii", out, at, i, 112)
        out[at + 8:at + 40] = name.encode("ascii").ljust(32, b"\0")
        struct.pack_into("<ii", out, at + 40, offsets[i], parent)
        struct.pack_into("<16f", out, at + 48, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    for off, body in blobs:
        out[off:off + len(body)] = body
    return bytes(out)


def mot(object_index=1, frames=(0, 30)) -> bytes:
    out = struct.pack("<iiiIII8x", object_index, 0, 0, 32, len(frames), 0)
    for f in frames:
        out += struct.pack("<I12x4f", f, 1, 0, 0, 0)
    return out


def img(names=("tex01",)) -> bytes:
    # Header-only IMG: the validator reads entry names; decoding is covered by the real-data test.
    out = bytearray(b"IMG\0" + struct.pack("<III", len(names), 0, 0))
    for n in names:
        out += n.encode("ascii").ljust(32, b"\0") + struct.pack("<4I", 0, 0, 0, 0)
    return bytes(out)


def dc2_cfg(model="x_m", frames=("bcol00",), keys=(("立ち", 0, 10, 0.2),), extra="") -> bytes:
    lines = ["v2;", f'IMG 0, "{model}01.img";', "IMG_END;", f'MODEL "{model}.mds";', "POLY_NUM 2, 0;",
             "SCALE 1.00, 1.00, 1.00;"]
    lines.append("OBJECT_NAME2 0, " + ", ".join(f'"{f}", 3.00' for f in frames) + ";")
    lines += [f'MOTION 0, "{model}.mot", "", "";', "KEY_START;"]
    lines += [f'KEY "{n}", {s}, {e}, {st:.2f};' for n, s, e, st in keys]
    lines += ["KEY_END;", "MOTION_END;", extra]
    return "\r\n".join(lines).encode("cp932")


def dc2_pack(model="x_m", mds_bytes=None, cfg=None, img_bytes=None) -> bytes:
    mds_bytes = mds_bytes or mds([("root", -1, None), ("body", 0, mdt()), ("bcol00", 1, None)])
    return mc.build_pack([(f"{model}.mds", mds_bytes), (f"{model}.mot", mot()),
                          (f"{model}01.img", img_bytes if img_bytes is not None else img()),
                          (f"{model}.cfg", cfg or dc2_cfg(model))])


class SyntheticTests(unittest.TestCase):
    def test_valid_synthetic_pack(self):
        report = mc.validate_chr(dc2_pack(), "x_m")
        self.assertEqual(report["triangles"], 2)
        self.assertEqual(report["textures"], ["tex01"])

    def test_triangle_list_count(self):
        body = mdt(prims=((3, [(0, 0, 0), (1, 1, 1), (2, 2, 2)]),))
        pack = dc2_pack(mds_bytes=mds([("root", -1, None), ("body", 0, body), ("bcol00", 1, None)]))
        self.assertEqual(mc.validate_chr(pack, "x_m")["triangles"], 1)

    def test_index_out_of_range(self):
        body = mdt(prims=((4, [(0, 0, 0), (1, 1, 1), (2, 2, 2), (9, 3, 3)]),))
        pack = dc2_pack(mds_bytes=mds([("root", -1, None), ("body", 0, body), ("bcol00", 1, None)]))
        with self.assertRaisesRegex(ConvertError, "out of range"):
            mc.validate_chr(pack, "x_m")

    def test_face_section_bounds(self):
        body = bytearray(mdt())
        struct.pack_into("<i", body, 36, 100000)  # faces_size escapes the MDT
        pack = dc2_pack(mds_bytes=mds([("root", -1, None), ("body", 0, bytes(body)), ("bcol00", 1, None)]))
        with self.assertRaisesRegex(ConvertError, "face section escapes"):
            mc.validate_chr(pack, "x_m")

    def test_unknown_face_flags(self):
        body = mdt(prims=((0x404, [(0, 0, 0), (1, 1, 1), (2, 2, 2)]),))
        pack = dc2_pack(mds_bytes=mds([("root", -1, None), ("body", 0, body), ("bcol00", 1, None)]))
        with self.assertRaisesRegex(ConvertError, "unknown type bits"):
            mc.validate_chr(pack, "x_m")

    def test_dc1_colour_ofs_rejected_in_output_fixed_by_rewrite(self):
        body = mdt(colour_ofs=-1, unk_3c=0x35343434)
        src = mds([("root", -1, None), ("body", 0, body), ("bcol0", 1, None)])
        with self.assertRaisesRegex(ConvertError, "colour_ofs"):
            mc.validate_chr(dc2_pack(mds_bytes=src), "x_m")
        out, stats = mc.rewrite_mds(src, mc.default_rename_frame, {"tex01": "ix_tex01"}, "src")
        self.assertEqual(stats["colour_ofs_fixed"], 1)
        self.assertEqual(stats["unk_3c_zeroed"], 1)
        self.assertEqual(stats["renamed"], {"bcol0": "bcol00"})
        objs = mc.read_mds(out, "out")
        info = mc.validate_mdt(out, objs[1].mesh, "out")
        self.assertEqual(info.materials, ["ix_tex01"])

    def test_overflowing_texture_name_rejected(self):
        src = mds([("root", -1, None), ("body", 0, mdt(material_names=("t" * 20,)))])
        with self.assertRaisesRegex(ConvertError, "exceeds 29 chars"):
            mc.rewrite_mds(src, lambda n: n, {"t" * 20: "ix_" + "t" * 27}, "src")

    def test_material_name_without_nul_rejected(self):
        body = mdt(material_names=("a" * 40,))
        pack = dc2_pack(mds_bytes=mds([("root", -1, None), ("body", 0, body), ("bcol00", 1, None)]))
        with self.assertRaisesRegex(ConvertError, "no NUL"):
            mc.validate_chr(pack, "x_m")

    def test_overflowing_frame_name_rejected(self):
        src = mds([("root", -1, None), ("bcol0", 0, None)])
        with self.assertRaisesRegex(ConvertError, "exceeds char"):
            mc.rewrite_mds(src, lambda n: n + "x" * 40, {}, "src")

    def test_missing_frame_rejected(self):
        pack = dc2_pack(cfg=dc2_cfg(frames=("dcol00",)))
        with self.assertRaisesRegex(ConvertError, "frame 'dcol00' is not in"):
            mc.validate_chr(pack, "x_m")

    def test_missing_brain_motion_rejected(self):
        contract = mc.BrainContract("brain", ["立ち", "攻撃１"], ["攻撃１"], {0: 1}, [])
        with self.assertRaisesRegex(ConvertError, "攻撃１"):
            mc.validate_chr(dc2_pack(), "x_m", contract)

    def test_damage_group_count(self):
        contract = mc.BrainContract("brain", ["立ち"], [], {0: 1, 3: 2}, [])
        cfg = dc2_cfg(extra='OBJECT_NAME2 3, "bcol00", 5.00;')
        with self.assertRaisesRegex(ConvertError, "damage group 3 has 1"):
            mc.validate_chr(dc2_pack(cfg=cfg), "x_m", contract)

    def test_key_beyond_motion_rejected(self):
        pack = dc2_pack(cfg=dc2_cfg(keys=(("立ち", 0, 99, 0.2),)))
        with self.assertRaisesRegex(ConvertError, "invalid for motion length 30"):
            mc.validate_chr(pack, "x_m")

    def test_key_name_overflow(self):
        pack = dc2_pack(cfg=dc2_cfg(keys=(("立" * 18, 0, 10, 0.2),)))
        with self.assertRaisesRegex(ConvertError, "name\\[0x24\\]"):
            mc.validate_chr(pack, "x_m")

    def test_texture_not_provided(self):
        with self.assertRaisesRegex(ConvertError, "not provided"):
            mc.validate_chr(dc2_pack(img_bytes=img(("other",))), "x_m")

    def test_stripped_img_needs_catalog(self):
        with self.assertRaisesRegex(ConvertError, "no payload and no catalog"):
            mc.validate_chr(dc2_pack(img_bytes=b""), "x_m")
        catalog = {"dungeon/monster/x_m.chr/x_m01.img": {"entries": [{"type": "texture", "name": "tex01", "variants": []}]}}
        mc.validate_chr(dc2_pack(img_bytes=b""), "x_m", catalog=catalog)

    def test_unknown_cfg_command_rejected(self):
        pack = dc2_pack(cfg=dc2_cfg(extra="SHADOW_VERTEX_ANIME 0;"))
        with self.assertRaisesRegex(ConvertError, "SHADOW_VERTEX_ANIME"):
            mc.validate_chr(pack, "x_m")

    def test_model_name_limit(self):
        with self.assertRaisesRegex(ConvertError, "model\\[16\\]"):
            mc.validate_chr(dc2_pack(), "x" * 16)

    def test_mot_object_bounds(self):
        with self.assertRaisesRegex(ConvertError, "drives object 7"):
            mc.walk_mot(mot(object_index=7), 3, "m")

    def test_mds_forward_parent_rejected(self):
        bad = bytearray(mds([("root", -1, None), ("a", 0, None)]))
        struct.pack_into("<i", bad, 16 + 44, 1)
        with self.assertRaisesRegex(ConvertError, "earlier object"):
            mc.read_mds(bytes(bad), "m")

    def test_rename_rule(self):
        self.assertEqual(mc.default_rename_frame("dcol0"), "dcol00")
        self.assertEqual(mc.default_rename_frame("mcol4"), "mcol04")
        self.assertEqual(mc.default_rename_frame("dcol"), "dcol")
        self.assertEqual(mc.default_rename_frame("lockon"), "lockon")
        self.assertEqual(mc.default_rename_frame("bcol00"), "bcol00")

    def test_dc1_cfg_comment_names(self):
        text = '//x\r\nMODEL "a.mds"\r\nMOTION 0, "a.mot", "", ""\r\nKEY_START 0\r\nKEY\t10,\t20,\t0.2,\t//立ち\t0\r\nMOTION_END\r\n'
        cfg = mc.parse_chr_cfg(text, dc1_comment_names=True)
        self.assertEqual(cfg.keys[0], [("立ち", 10, 20, 0.2)])

    def test_dc1_cfg_stray_annotation_line_is_skipped_not_fatal(self):
        text = 'MODEL "a.mds"\r\nKEY_START 0\r\ne104a  オパー（植物あつかい？）\r\nKEY\t10,\t20,\t0.13,\t//立ち\r\nMOTION_END\r\n'
        with self.assertRaises(ConvertError):
            mc.parse_chr_cfg(text)  # DC2 output/brain cfgs stay strict
        cfg = mc.parse_chr_cfg(text, dc1_comment_names=True)
        self.assertEqual(cfg.skipped, ["e104a  オパー（植物あつかい？）"])
        self.assertEqual(cfg.keys[0], [("立ち", 10, 20, 0.13)])

    def test_neutral_groups(self):
        groups = mc.neutral_groups(["root", "bcol2", "bcol0", "dcol1", "dcol0", "mcol10", "mcol2", "lockon", "dcol"])
        self.assertEqual(groups[0], [0, [["lockon", mc.NEUTRAL_RADIUS]]])
        self.assertEqual(groups[1], [1, [["root", None]]])
        self.assertEqual([n for n, _r in dict((g, p) for g, p in groups)[3]], ["dcol0", "dcol1"])
        self.assertEqual([n for n, _r in dict((g, p) for g, p in groups)[4]], ["mcol2", "mcol10"])

    def test_profile_aliases_resolve_and_refuse_bad_rows(self):
        keys = [("立ち", 10, 20, 0.13), ("歩き", 30, 50, 0.2)]
        rows = mc.resolve_profile_aliases({"frame_style": "two_digit",
                                           "aliases": [{"name": "歩き", "slot": 1}, {"name": "走り", "slot": 1, "step": 0.4}]}, keys)
        self.assertEqual([(r["name"], r["start"], r["end"], r["step"]) for r in rows],
                         [("歩き", 30, 50, 0.2), ("走り", 30, 50, 0.4)])
        for bad in ({"aliases": [{"name": "dc1_01", "slot": 1}]},           # shadows a slot name
                    {"aliases": [{"name": "a", "slot": 0}, {"name": "a", "slot": 1}]},  # duplicate
                    {"aliases": [{"name": "a", "slot": 2}]},                # missing DC1 slot
                    {"aliases": [{"name": "あ" * 18, "slot": 0}]},          # over name[0x24] in cp932
                    {"groups": []}):                                        # not a profile field
            with self.assertRaises(ConvertError, msg=bad):
                mc.resolve_profile_aliases(bad, keys)

    def test_profile_aliases_follow_dc1_slots_in_cfg(self):
        text = mc.author_cfg("m", [], "m.mds", None, "m.mot", None, (1, 1, 1), 1.0, (0, 0), [[1, [["root", None]]]], [],
                             [("立ち", 10, 20, 0.13)], None, [{"name": "立ち", "start": 10, "end": 20, "step": 0.13}])
        cfg = mc.parse_chr_cfg(text)
        self.assertEqual([k[0] for k in cfg.keys[0]], ["dc1_00", "立ち"])



def wgt(blocks) -> bytes:
    """Synthetic .wgt: [(frame, bone, [(vertex, weight), ...]), ...] as VertexWeightBlock/Entry records."""
    out = bytearray()
    for i, (frame, bone, entries) in enumerate(blocks):
        more = 1 if i + 1 < len(blocks) else 0
        out += struct.pack("<IiIIIIII", frame, bone, 20, 32, len(entries), more, 0, 0)
        for vid, w in entries:
            out += struct.pack("<IIIIfIII", vid, 0, 0, 0, w, 0, 0, 0)
    return bytes(out)


class SkinValidatorTests(unittest.TestCase):
    def setUp(self):
        objects = [("root", -1, None)] + [(f"jnt{i}", 0, None) for i in range(40)] + [("skin", 0, mdt())]
        self.data = mds(objects)
        self.objs = mc.read_mds(self.data, "t")
        self.skin = len(objects) - 1

    def test_counts_only_nonempty_blocks(self):
        # 40 empty headers plus 3 active bones: DC2 skips count==0 blocks before claiming a bone slot.
        blocks = [(self.skin, b + 1, []) for b in range(40)]
        blocks += [(self.skin, 1, [(0, 100.0), (1, 60.0)]), (self.skin, 2, [(1, 40.0), (2, 100.0)]), (self.skin, 3, [(3, 100.0)])]
        rep = mc.validate_wgt(wgt(blocks), self.objs, self.data, ["skin"], "t")
        self.assertEqual(rep["blocks"], 43)
        self.assertEqual(rep["frames"]["skin"]["bone_count"], 3)
        self.assertEqual(rep["frames"]["skin"]["max_influences"], 2)

    def test_bone_cap(self):
        blocks = [(self.skin, b + 1, [(b % 4, 1.0)]) for b in range(33)]
        with self.assertRaisesRegex(ConvertError, "Bone Num Over"):
            mc.validate_wgt(wgt(blocks), self.objs, self.data, None, "t")

    def test_influence_cap(self):
        blocks = [(self.skin, b + 1, [(0, 20.0)]) for b in range(5)]
        with self.assertRaisesRegex(ConvertError, "5 influences"):
            mc.validate_wgt(wgt(blocks), self.objs, self.data, None, "t")

    def test_vertex_out_of_range(self):
        with self.assertRaisesRegex(ConvertError, "vertex 4 >="):
            mc.validate_wgt(wgt([(self.skin, 1, [(4, 100.0)])]), self.objs, self.data, None, "t")

    def test_bone_out_of_range_and_bad_type(self):
        with self.assertRaisesRegex(ConvertError, "bone 99"):
            mc.validate_wgt(wgt([(self.skin, 99, [(0, 100.0)])]), self.objs, self.data, None, "t")
        bad = bytearray(wgt([(self.skin, 1, [(0, 100.0)])]))
        struct.pack_into("<I", bad, 8, 12)
        with self.assertRaisesRegex(ConvertError, "type 12"):
            mc.validate_wgt(bytes(bad), self.objs, self.data, None, "t")

    def test_trailing_bytes_and_unmeshed_target(self):
        with self.assertRaisesRegex(ConvertError, "after the last weight block"):
            mc.validate_wgt(wgt([(self.skin, 1, [(0, 100.0)])]) + b"\0" * 32, self.objs, self.data, None, "t")
        with self.assertRaisesRegex(ConvertError, "unmeshed frame"):
            mc.validate_wgt(wgt([(1, 2, [(0, 100.0)])]), self.objs, self.data, None, "t")

    def test_deform_frame_needs_weights(self):
        with self.assertRaisesRegex(ConvertError, "no non-empty weight block"):
            mc.validate_wgt(wgt([(self.skin, 1, [])]), self.objs, self.data, ["skin"], "t")
        with self.assertRaisesRegex(ConvertError, "not in the model"):
            mc.validate_wgt(wgt([(self.skin, 1, [(0, 100.0)])]), self.objs, self.data, ["skin9"], "t")

    def test_toan_alias_table_is_consistent(self):
        keys = mc.toan_keys(mc.TOAN_C01D, [("x", 10 * i, 10 * i + 5, 0.5) for i in range(41)])
        names = [k["name"] for k in keys]
        self.assertEqual(names[:41], [f"dc1_{i:02d}" for i in range(41)])
        for literal in mc.DC2_PLAYER_MOTION_LITERALS:
            self.assertIn(literal, names)
        with self.assertRaisesRegex(ConvertError, "missing DC1 slot"):
            mc.toan_keys(mc.TOAN_C01D, [("x", 0, 5, 0.5)] * 10)


def _bbp(rows) -> bytes:
    return b"".join(struct.pack("<16f", *r) for r in rows)


IDENT = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)


class BodyProfileTests(unittest.TestCase):
    def profile(self, **over):
        doc = {"frame_renames": {"weapon": ["ef00", "why"]}, "groups": [[1, [["keri_L", None]]]],
               "body_size": [16.0, 4.0, 0.0], "outline": [["", 2.0]], "seam_sockets": ["ef00", "keri_L"],
               "aliases": [["立ち", 0, "idle"], ["吹っ飛び", [1, 2, 0.3], "authored"]],
               "synth_frames": [{"name": "keri_L", "parent": "foot", "model_offset": [0, -1, 0]}]}
        doc.update(over)
        return doc

    def test_shipped_profiles_load(self):
        for name in ("toan-c01d", "goro-c06b", "ungaga-c10b"):
            prof = mc.load_body_profile(mc.PROFILES_DIR / f"{name}.json")
            self.assertEqual(prof["name"], name)
            self.assertEqual(len(prof["aliases"]), 46)
            self.assertEqual(prof["weapon_hit_frame"], "dcol1")
        self.assertEqual(mc.TOAN_C01D["synth_frames"], [])

    def test_loader_refuses_bad_profiles(self):
        self.assertEqual(mc.load_body_profile(self.profile())["weapon_hit_frame"], "dcol1")
        for over, msg in (({"sockets": []}, "unknown body profile fields"),
                          ({"synth_frames": [{"name": "keri_L", "parent": "foot"}]}, "exactly one"),
                          ({"synth_frames": [{"name": "keri_L", "parent": "f", "model_offset": [0, 0, 0],
                                              "local_translation": [0, 0, 0]}]}, "exactly one"),
                          ({"synth_frames": [{"name": "ef00", "parent": "f", "model_offset": [0, 0, 0]}]}, "twice"),
                          ({"synth_frames": [{"name": "keri L", "parent": "f", "model_offset": [0, 0, 0]}]}, "ASCII"),
                          ({"synth_frames": [{"name": "k", "parent": "f", "model_offset": [0, "x", 0]}]}, "finite"),
                          ({"aliases": [["立ち", "0", "x"]]}, "alias row"),
                          ({"version": 2}, "format/version")):
            with self.assertRaisesRegex(ConvertError, msg):
                mc.load_body_profile(self.profile(**over))
        doc = self.profile()
        del doc["seam_sockets"]
        with self.assertRaisesRegex(ConvertError, "lacks"):
            mc.load_body_profile(doc)

    def test_append_null_frame_moves_meshes_and_grows_bbp(self):
        data = mds([("root", -1, None), ("body", 0, mdt()), ("leg", 0, None), ("foot", 2, None), ("skin", 0, mdt())])
        # leg is rotated +90 degrees about Z (local X -> model Y) and raised; foot sits 2 along the leg's X.
        rot_z = (0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 3, 0, 1)
        foot = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 0, 0, 1)
        bbp = _bbp([IDENT, IDENT, rot_z, foot, IDENT])
        out, out_bbp, info = mc.append_null_frames(data, bbp, [{"name": "keri_L", "parent": "foot",
                                                                "model_offset": [0, -5, 0]}], "t")
        objs, new = mc.read_mds(data, "a"), mc.read_mds(out, "b")
        self.assertEqual(len(new), 6)
        self.assertEqual((new[5].name, new[5].parent, new[5].mesh), ("keri_L", 3, 0))
        for o in objs:
            self.assertEqual(new[o.index].name, o.name)
            if o.mesh:
                self.assertEqual(new[o.index].mesh, o.mesh + 112)
                size = mc.mdt_header(data, o.mesh)["unk_08"]
                self.assertEqual(out[o.mesh + 112:o.mesh + 112 + size], data[o.mesh:o.mesh + size])
                mc.validate_mdt(out, new[o.index].mesh, "moved")
        self.assertEqual(len(out), len(data) + 112)
        self.assertEqual(out_bbp[:len(bbp)], bbp)
        self.assertEqual(len(out_bbp), 6 * 64)
        # foot's model position is (0, 5, 0); 5 down in model space is -5 along the leg's local X.
        self.assertEqual(info[0]["bind_parent_model"], [0.0, 5.0, 0.0])
        self.assertEqual(info[0]["bind_model"], [0.0, 0.0, 0.0])
        self.assertEqual(info[0]["local_translation"], [-5.0, 0.0, 0.0])
        row = struct.unpack_from("<16f", out_bbp, 5 * 64)
        self.assertEqual(row, struct.unpack_from("<16f", out, 16 + 5 * 112 + 48))
        self.assertEqual(row[12:15], (-5.0, 0.0, 0.0))
        with self.assertRaisesRegex(ConvertError, "already exists"):
            mc.append_null_frames(data, bbp, [{"name": "foot", "parent": "leg", "local_translation": [0, 0, 0]}], "t")
        with self.assertRaisesRegex(ConvertError, "occurs 0 times"):
            mc.append_null_frames(data, bbp, [{"name": "k", "parent": "toe", "local_translation": [0, 0, 0]}], "t")
        with self.assertRaisesRegex(ConvertError, "rows for"):
            mc.append_null_frames(data, bbp[:-64], [], "t")
        self.assertEqual(mc.append_null_frames(data, bbp, [], "t")[:2], (data, bbp))

    def test_xiao_profile_fields(self):
        prof = mc.load_body_profile(mc.PROFILES_DIR / "xiao-c04b.json")
        self.assertEqual((prof["name"], len(prof["aliases"])), ("xiao-c04b", 46))
        self.assertIsNone(prof["weapon_hit_frame"])
        self.assertEqual((prof["deform_frames"], prof["weapon_points"]), (["skin"], ["eff30"]))
        self.assertEqual([s["model_target"][1] for s in prof["synth_frames"]], [0.0, 0.0])
        for over, msg in (({"weapon_hit_frame": 5}, "frame name or null"),
                          ({"weapon_hit_frame": ""}, "frame name or null"),
                          ({"deform_frames": []}, "non-empty list"),
                          ({"weapon_points": ["eff30", "eff30"]}, "distinct"),
                          ({"synth_frames": [{"name": "k", "parent": "f", "model_target": [0, 0, 0],
                                              "model_offset": [0, 0, 0]}]}, "exactly one")):
            with self.assertRaisesRegex(ConvertError, msg):
                mc.load_body_profile(self.profile(**over))

    def test_zero_root_row_becomes_identity_and_model_target_solves_through_it(self):
        # dummyRoot's .bbp row is all zero (Xiao's c04b); leg is rotated +90 degrees about Z and raised 3.
        data = mds([("root", -1, None), ("leg", 0, None), ("foot", 1, None), ("skin", 1, mdt()), ("prop", 0, mdt())])
        rot_z = (0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 3, 0, 1)
        foot = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 0, 0, 1)
        zero = (0,) * 16
        bbp = _bbp([zero, rot_z, foot, IDENT, zero])
        objs = mc.read_mds(data, "t")
        fixed_bbp, fixed = mc.identity_zero_bind_ancestors(objs, bbp, [3, 2])
        self.assertEqual(fixed, ["root"])
        self.assertEqual(struct.unpack_from("<16f", fixed_bbp, 0), IDENT)
        self.assertEqual(fixed_bbp[64:], bbp[64:])  # the zero leaf (prop) is no ancestor: untouched
        # Without the fix the chain is all zero and the solve is singular; with it the target lands exactly.
        with self.assertRaisesRegex(ConvertError, "singular"):
            mc.append_null_frames(data, bbp, [{"name": "keri_L", "parent": "foot", "model_target": [1, 0, 0]}], "t")
        _out, _b, info = mc.append_null_frames(data, fixed_bbp, [{"name": "keri_L", "parent": "foot",
                                                                  "model_target": [1, 0, 0]}], "t")
        self.assertEqual(info[0]["bind_parent_model"], [0.0, 5.0, 0.0])
        self.assertEqual(info[0]["bind_model"], [1.0, 0.0, 0.0])
        self.assertEqual(info[0]["local_translation"], [-5.0, -1.0, 0.0])
        same, none = mc.identity_zero_bind_ancestors(objs, fixed_bbp, [3])
        self.assertEqual((same, none), (fixed_bbp, []))

    def test_dc1_slots_past_the_motion_become_placeholders(self):
        dc1 = [("0立ち", 10, 20, 0.1), ("29走り", 690, 710, 0.65), ("13撃ち", 251, 255, 0.7)]
        keys = mc.toan_keys(self.profile(aliases=[["発砲", 2, "fire"]]), dc1, 568)
        self.assertEqual([(k["start"], k["end"], k["step"]) for k in keys], [(10, 20, 0.1), (1, 1, 1.0), (251, 255, 0.7),
                                                                          (251, 255, 0.7)])
        self.assertIn("placeholder", keys[1]["source"])
        self.assertEqual(mc.toan_keys(self.profile(aliases=[]), dc1)[1]["end"], 710)  # no length: unchanged
        with self.assertRaisesRegex(ConvertError, "past the motion"):
            mc.toan_keys(self.profile(aliases=[["走り", 1, "x"]]), dc1, 568)

    def test_dc1_int_vertex_anime_refused(self):
        cfg = dc2_cfg().decode("cp932").replace('MODEL "x_m.mds";', 'VERTEX_ANIME 1;\r\nMODEL "x_m.mds";')
        with self.assertRaisesRegex(ConvertError, "DC1 int form"):
            mc.validate_chr(dc2_pack(cfg=cfg.encode("cp932")), "x_m")


DC1 = os.environ.get("IXION_DC1_DATA")
DC2 = os.environ.get("IXION_DC2_DATA")


class CharacterTextureDecodeTests(unittest.TestCase):
    def test_chr_img_pixels_are_linear(self):
        w = h = 16
        pixels = bytes((x * 7 + y) & 0xFF for y in range(h) for x in range(w))
        palette = b"".join(bytes((i, 255 - i, 0, 0x40)) for i in range(256))
        pic = struct.pack("<IIIHHBBBBHH", 48 + len(pixels) + 1024, 1024, len(pixels), 48, 256, 0, 1, 3, 5, w, h)
        pic = pic.ljust(48, b"\0")
        tim2 = b"TIM2" + struct.pack("<HH", 3, 1) + b"\0" * 8 + pic + pixels + palette
        img = b"IMG\0" + struct.pack("<I", 1) + b"\0" * 8 + b"t01".ljust(32, b"\0") + struct.pack("<I", 64) + b"\0" * 12 + tim2
        import zlib
        png, pw, ph = mc.decode_chr_img(img)["t01"]
        self.assertEqual((pw, ph), (w, h))
        idat = png[png.index(b"IDAT") + 4:png.index(b"IEND") - 8]
        rows = zlib.decompress(idat)
        for y in (0, 5, 15):
            row = rows[y * (w * 4 + 1) + 1:(y + 1) * (w * 4 + 1)]
            for x in (0, 3, 15):
                index = pixels[y * w + x]
                slot = (index & ~0x18) | ((index & 0x08) << 1) | ((index & 0x10) >> 1)  # CSM1 order
                self.assertEqual(row[x * 4], slot)
        # The same bytes in an IM2 container go through the PSMT8 unswizzle (e104a/c15a layout).
        png2, _w, _h = mc.decode_chr_img(b"IM2\0" + img[4:])["t01"]
        self.assertNotEqual(png2, png)


@unittest.skipUnless(DC1 and DC2, "set IXION_DC1_DATA and IXION_DC2_DATA for real-data tests")
class RealDataTests(unittest.TestCase):
    def setUp(self):
        self.dc1_pack = Path(DC1) / "dun" / "monstor" / "e03a.chr"
        self.brain = Path(DC2) / "dungeon" / "monster" / "e202a.chr"  # IXION_DC2_DATA is the data/ root, as in test_room_converter
        self.brain_stb = Path(DC2) / "dungeon" / "monster" / "e202a.stb"
        self.catalog = Path(DC2).parent / "port_data" / "catalog.json"

    def test_native_e202a_round_trip(self):
        contract, _ = mc.brain_contract(self.brain.read_bytes(), "e202a", self.brain_stb.read_bytes())
        doc = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog = {s["source"].lower(): s for s in doc["sources"] if "/e202a.chr/" in s["source"]}
        report = mc.validate_chr(self.brain.read_bytes(), "e202a", contract, catalog, self.catalog.parent)
        self.assertEqual(report["poly_num"], [report["triangles"], report["shadow_triangles"]])
        self.assertIn("攻撃１", contract.stb_motion_names)

    def test_illza_death_key_clamps_with_warning_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "illza"
            warning = io.StringIO()
            with contextlib.redirect_stderr(warning):
                prov = mc.convert(Path(DC1) / "dun/monstor/e22a.chr", None, None, out)
            self.assertEqual(prov["dc1_slots"][11][1:], [215, 230, 0.25])
            self.assertEqual(prov["motion_key_clamps"], [
                {"slot": 11, "start": 215, "original_end": 235, "end": 230, "step": 0.25}])
            self.assertEqual(warning.getvalue().count("clamped KEY 11"), 1)
            pack = (out / prov["output_chr"]).read_bytes()
            cfg = mc.parse_pack(pack)["ix_e22a.cfg"].data.decode("cp932")
            self.assertIn('KEY "dc1_11", 215, 230, 0.25', cfg)
            cat_root = out / "port_data"
            catalog = {s["source"].lower(): s for s in json.loads((cat_root / "catalog.json").read_text())["sources"]}
            mc.validate_chr(pack, "ix_e22a", None, catalog, cat_root)

    def test_convert_e03a(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "e03a-dc2"
            prov = mc.convert(self.dc1_pack, self.brain, self.brain_stb, out)
            pack = (out / prov["output_chr"]).read_bytes()
            doc = json.loads((out / "port_data" / "catalog.json").read_text(encoding="utf-8"))
            catalog = {s["source"].lower(): s for s in doc["sources"]}
            contract, _ = mc.brain_contract(self.brain.read_bytes(), "e202a", self.brain_stb.read_bytes())
            report = mc.validate_chr(pack, "ix_e03a", contract, catalog, out / "port_data")
            self.assertEqual(report["meshed"], 22)
            src = mc.parse_pack(self.dc1_pack.read_bytes())
            dst = mc.parse_pack(pack)
            self.assertEqual(dst["ix_e03a.mot"].data, src["e03a.mot"].data)  # rotation keys copied unchanged
            a, b = src["e03a.mds"].data, dst["ix_e03a.mds"].data
            self.assertEqual(len(a), len(b))
            # Only names, two MDT header words and material name fields may differ.
            objs = mc.read_mds(b, "out")
            allowed = set()
            for o in objs:
                allowed.update(range(16 + o.index * 112 + 8, 16 + o.index * 112 + 40))
                if o.mesh:
                    h = mc.mdt_header(b, o.mesh)
                    allowed.update(range(o.mesh + 32, o.mesh + 36))
                    allowed.update(range(o.mesh + 60, o.mesh + 64))
                    for m in range(h["material_num"]):
                        at = o.mesh + h["material_ofs"] + m * 96
                        allowed.update(range(at + 52, at + 96))
            diffs = [i for i in range(len(a)) if a[i] != b[i]]
            self.assertTrue(diffs)
            self.assertFalse([i for i in diffs if i not in allowed])


@unittest.skipUnless(DC1, "set IXION_DC1_DATA for the e104a (Opar) real-data test")
class OparRealDataTests(unittest.TestCase):
    def test_convert_e104a_brainless(self):
        src_path = Path(DC1) / "dun" / "monstor" / "e104a.chr"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "e104a-dc2"
            prov = mc.convert(src_path, None, None, out)
            pack = (out / prov["output_chr"]).read_bytes()
            doc = json.loads((out / "port_data" / "catalog.json").read_text(encoding="utf-8"))
            catalog = {s["source"].lower(): s for s in doc["sources"]}
            report = mc.validate_chr(pack, "ix_e104a", None, catalog, out / "port_data")
            self.assertEqual((report["frames"], report["meshed"]), (38, 12))
            self.assertEqual(report["poly_num"], [report["triangles"], report["shadow_triangles"]])
            self.assertEqual(report["textures"], ["ix_e104a01", "ix_e104a02"])
            self.assertEqual(report["key_names"], [f"dc1_{i:02d}" for i in range(19)])
            self.assertEqual(report["warnings"], [])
            self.assertEqual(prov["dc1_cfg_skipped_statements"], ["e104a  オパー（植物あつかい？）"])
            self.assertEqual(prov["motion_table"], [])
            self.assertEqual(prov["dc1_slots"][13][0], "攻撃1（エラからネバネバ液）")
            src = mc.parse_pack(src_path.read_bytes())
            dst = mc.parse_pack(pack)
            self.assertEqual(dst["ix_e104a.mot"].data, src["e104a.mot"].data)
            self.assertEqual(report["motion_files"]["ix_e104a.mot"]["types"].get(1), 1)  # one scale channel
            # Brainless: DC1 frame names are kept verbatim.
            names = [o.name for o in mc.read_mds(dst["ix_e104a.mds"].data, "out")]
            self.assertEqual(names, [o.name for o in mc.read_mds(src["e104a.mds"].data, "src")])
            self.assertIn("dcol1", names)


    @unittest.skipUnless(DC2, "set IXION_DC2_DATA for the Himarra form contract")
    def test_convert_e104a_as_himarra_form_profile(self):
        src_path = Path(DC1) / "dun" / "monstor" / "e104a.chr"
        profile_path = Path(__file__).resolve().parents[1] / "tools" / "profiles" / "e104a-as-himarra.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "e104a-monica"
            prov = mc.convert(src_path, None, None, out, profile=profile)
            pack = (out / prov["output_chr"]).read_bytes()
            doc = json.loads((out / "port_data" / "catalog.json").read_text(encoding="utf-8"))
            catalog = {s["source"].lower(): s for s in doc["sources"]}
            # The native form's cfg KEY names, group counts and f216a's by-name frames are the contract.
            contract, _ = mc.brain_contract((Path(DC2) / "dungeon" / "monster" / "e216a.chr").read_bytes(), "e216a",
                                            (Path(DC2) / "dungeon" / "act_script" / "f216a.stb").read_bytes())
            self.assertEqual(contract.stb_frame_names, ["bcol00", "dcol00", "dcol01"])
            report = mc.validate_chr(pack, "ix_e104a", contract, catalog, out / "port_data")
            self.assertEqual(report["warnings"], [])
            self.assertEqual(report["key_names"][:19], [f"dc1_{i:02d}" for i in range(19)])
            self.assertEqual(len(report["key_names"]), 19 + len(profile["aliases"]))
            names = [o.name for o in mc.read_mds(mc.parse_pack(pack)["ix_e104a.mds"].data, "out")]
            self.assertIn("dcol01", names)
            self.assertNotIn("dcol1", names)
            self.assertEqual(prov["options"]["scale"], profile["scale"])
            cfg = mc.parse_chr_cfg(mc.parse_pack(pack)["ix_e104a.cfg"].data.decode("cp932"))
            self.assertEqual(cfg.body_size, tuple(v * profile["scale"] for v in (56.0, 50.0, 60.0)))
            rows = {r["name"]: r for r in prov["profile_aliases"]}
            self.assertEqual((rows["攻撃１in"]["start"], rows["攻撃１in"]["end"]), (110, 120))
            self.assertEqual((rows["攻撃２"]["start"], rows["攻撃２"]["end"]), (130, 150))
            # Motion names DC2's built-in player move asks for (actionchara.cpp SetMotion literals).
            for literal in (b"\x97\xA7\x82\xBF", b"\x83o\x83g\x83\x8B\x97\xA7\x82\xBF", b"\x95\xE0\x82\xAB",
                            b"\x91\x96\x82\xE8", b"\x97\x8E\x89\xBA\x92\x86",
                            b"\x83o\x83g\x83\x8B\x95\xE0\x82\xAB\x81i\x91O\x81j",
                            b"\x83o\x83g\x83\x8B\x95\xE0\x82\xAB\x81i\x8C\xE3\x81j",
                            b"\x83o\x83g\x83\x8B\x95\xE0\x82\xAB\x81i\x89E\x81j",
                            b"\x83o\x83g\x83\x8B\x95\xE0\x82\xAB\x81i\x8D\xB6\x81j"):
                self.assertIn(literal.decode("cp932"), report["key_names"])


@unittest.skipUnless(DC1 and DC2, "set IXION_DC1_DATA and IXION_DC2_DATA for the Toan body real-data test")
class ToanBodyRealDataTests(unittest.TestCase):
    def test_native_player_bases_pass_skin_validation(self):
        for name in ("c01_base2", "c02_base2"):
            pack = (Path(DC2) / "mainchr" / f"{name}.chr").read_bytes()
            rep = mc.validate_chr(pack, name, cfg_name="info.cfg", pack_dir="mainchr", require_textures=False)
            self.assertIn("skin1", rep["skin"]["frames"])
            self.assertEqual(rep["warnings"], [])

    def test_convert_toan_c01d_and_dagger(self):
        d1, d2 = Path(DC1), Path(DC2)
        src_path = d1 / "dun" / "mainchara" / "c01d.chr"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "toan"
            prov = mc.convert_player_body(src_path, out, d1 / "dun" / "mainchara" / "c01w.pac", "c01w01.chr",
                                          d2 / "mainchr" / "c01_base2.chr", d2 / "mainchr" / "c01.stb")
            body = mc.parse_pack((out / prov["outputs"]["ix_c01d"]["path"]).read_bytes())
            src = mc.parse_pack(src_path.read_bytes())
            for a, b in (("c01d.mot", "ix_c01d.mot"), ("c01d.bbp", "ix_c01d.bbp"), ("c01d.wgt", "ix_c01d.wgt"),
                         ("c01s.bbp", "ix_c01s.bbp"), ("c01s.wgt", "ix_c01s.wgt")):
                self.assertEqual(body[b].data, src[a].data, b)
            rep = prov["validation"]["ix_c01d"]
            self.assertEqual((rep["frames"], rep["meshed"]), (77, 17))
            self.assertEqual(rep["poly_num"], [rep["triangles"], rep["shadow_triangles"]])
            skin = rep["skin"]["frames"]["skin"]
            self.assertEqual((skin["frame"], skin["bone_count"], skin["max_influences"], skin["headers"]), (76, 18, 3, 54))
            dc1 = prov["dc1_slots"]
            self.assertEqual(len(dc1), 41)
            self.assertEqual([k["name"] for k in prov["keys"][:41]], [f"dc1_{i:02d}" for i in range(41)])
            self.assertEqual([(k["start"], k["end"]) for k in prov["keys"][36:41]], [(s, e) for _n, s, e, _st in dc1[36:41]])
            self.assertEqual(prov["keys"][41]["name"], "立ち")
            names = [o.name for o in mc.read_mds(body["ix_c01d.mds"].data, "out")]
            self.assertEqual(names[70], "ef00")
            self.assertEqual([o.name for o in mc.read_mds(body["ix_c01s.mds"].data, "s")][70], "ef00")
            self.assertEqual(rep["player"]["max_path_frames_missing"], ["dcol00", "dcol01", "gun", "nage"])
            self.assertEqual(rep["warnings"], [])
            dagger = prov["validation"]["ix_c01w01"]
            self.assertEqual(prov["weapon"]["frames"], ["c01w01__m", "dcol3", "dcol2", "dcol1", "dcol0"])
            self.assertEqual(dagger["textures"], ["ix_c01w01"])
            cfg = body["ix_c01d.cfg"].data.decode("cp932")
            self.assertLess(cfg.index("VERTEX_ANIME"), cfg.index("MODEL"))
            self.assertNotIn("CLOTH", cfg)
            self.assertNotRegex(cfg, r"(?m)^TEX_ANIME")
            self.assertEqual(prov["synth_frames"], [])
            self.assertEqual(prov["vertex_anime"]["dc1"], [1])

    def convert_profile(self, tmp, profile, stem, weapon_pac):
        d1, d2 = Path(DC1), Path(DC2)
        src_path = d1 / "dun" / "mainchara" / f"{stem}.chr"
        prof = mc.load_body_profile(mc.PROFILES_DIR / profile)
        prov = mc.convert_player_body(src_path, Path(tmp) / stem, d1 / "dun" / "mainchara" / weapon_pac,
                                      prof["source"]["weapon_member"], d2 / "mainchr" / "c01_base2.chr",
                                      d2 / "mainchr" / "c01.stb", mapping=mc.PROFILES_DIR / profile)
        body = mc.parse_pack((Path(tmp) / stem / prov["outputs"][f"ix_{stem}"]["path"]).read_bytes())
        return prov, body, mc.parse_pack(src_path.read_bytes()), prof

    def check_synth_body(self, prov, body, src, model, shadow, src_frames):
        rep = prov["validation"][prov["output_model"]]
        self.assertEqual(rep["warnings"], [])
        synth = prov["synth_frames"]
        self.assertEqual(rep["frames"], src_frames + len(synth))
        # .mot and .wgt untouched; .bbp is the DC1 table plus one row per synthesised frame.
        for name in (f"{model}.mot", f"{model}.wgt", f"{shadow}.bbp", f"{shadow}.wgt"):
            self.assertEqual(body[f"ix_{name}"].data, src[name].data, name)
        src_bbp, out_bbp = src[f"{model}.bbp"].data, body[f"ix_{model}.bbp"].data
        self.assertEqual(out_bbp[:len(src_bbp)], src_bbp)
        self.assertEqual(len(out_bbp), len(src_bbp) + 64 * len(synth))
        src_objs = mc.read_mds(src[f"{model}.mds"].data, "src")
        out_objs = mc.read_mds(body[f"ix_{model}.mds"].data, "out")
        for o in src_objs:
            if o.mesh:
                self.assertEqual(out_objs[o.index].mesh, o.mesh + 112 * len(synth))
        for k, s in enumerate(synth):
            self.assertEqual((out_objs[src_frames + k].name, out_objs[src_frames + k].index), (s["name"], s["index"]))
        self.assertEqual(len(mc.read_mds(body[f"ix_{shadow}.mds"].data, "s")), len(mc.read_mds(src[f"{shadow}.mds"].data, "s")))
        cfg = body[f"{prov['output_model']}.cfg"].data.decode("cp932")
        self.assertIn('VERTEX_ANIME "skin";', cfg)
        self.assertEqual(prov["vertex_anime"]["dc1"], [1])  # DC1 base.cfg says VERTEX_ANIME 1
        return rep, {s["name"]: s for s in synth}

    def test_convert_goro_c06b_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            prov, body, src, prof = self.convert_profile(tmp, "goro-c06b.json", "c06b", "c06w.pac")
            rep, synth = self.check_synth_body(prov, body, src, "c06a", "c06s", 60)
            self.assertEqual(synth["keri_L"]["index"], 60)
            self.assertEqual(synth["keri_L"]["parent"], "eff24")
            self.assertAlmostEqual(synth["keri_L"]["bind_model"][1], 0.0, places=3)
            self.assertEqual(rep["skin"]["frames"]["skin"]["bone_count"], 20)
            self.assertEqual(len(rep["key_names"]), 37 + 46)
            names = [o.name for o in mc.read_mds(body["ix_c06a.mds"].data, "out")]
            self.assertEqual((names[29], names[40], names[2]), ("ef00", "gun_hand", "hip"))
            self.assertEqual(prov["weapon"]["frames"], ["c06w01", "dcol3", "dcol2", "dcol1", "dcol0"])

    def test_convert_ungaga_c10b_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            prov, body, src, prof = self.convert_profile(tmp, "ungaga-c10b.json", "c10b", "c10w.pac")
            rep, synth = self.check_synth_body(prov, body, src, "c10a", "c10s", 67)
            self.assertEqual([s for s in synth], ["keri_L", "keri_R", "bcol00", "bcol01"])
            self.assertAlmostEqual(synth["keri_L"]["bind_model"][1], 0.0, places=3)
            self.assertAlmostEqual(synth["keri_R"]["bind_model"][1], 0.0, places=3)
            self.assertEqual(rep["player"]["max_path_frames_present"], ["ef00", "gun_hand", "hat", "bcol00", "bcol01", "keri_R"])
            self.assertEqual(rep["skin"]["frames"]["skin"]["max_influences"], 2)
            self.assertEqual(len(rep["key_names"]), 40 + 46)
            dc1 = prov["dc1_slots"]
            self.assertEqual([(s, e) for _n, s, e, _st in dc1[37:40]], [(670, 678), (678, 694), (695, 714)])

    def test_convert_xiao_c04b_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            prov, body, src, prof = self.convert_profile(tmp, "xiao-c04b.json", "c04b", "c04w.pac")
            rep = prov["validation"]["ix_c04b"]
            self.assertEqual(rep["warnings"], [])
            self.assertEqual(rep["frames"], 79 + 2)
            for name in ("c04b.mot", "c04b.wgt", "c04s.bbp", "c04s.wgt"):
                self.assertEqual(body[f"ix_{name}"].data, src[name].data, name)
            # .bbp: dummyRoot's zero row becomes identity, the other 78 rows are DC1's, plus keri_L and keri_R.
            src_bbp, out_bbp = src["c04b.bbp"].data, body["ix_c04b.bbp"].data
            self.assertEqual(src_bbp[:64], b"\0" * 64)
            self.assertEqual(struct.unpack_from("<16f", out_bbp, 0), IDENT)
            self.assertEqual(out_bbp[64:len(src_bbp)], src_bbp[64:])
            self.assertEqual(len(out_bbp), len(src_bbp) + 2 * 64)
            self.assertEqual(prov["bbp_zero_rows_identity"]["frames"], ["dummyRoot"])
            synth = {s["name"]: s for s in prov["synth_frames"]}
            self.assertEqual([(s["index"], s["parent"]) for s in synth.values()], [(79, "eff4"), (80, "eff26")])
            for s in synth.values():
                self.assertAlmostEqual(s["bind_model"][1], 0.0, places=3)
                self.assertAlmostEqual(s["bind_parent_model"][1], 0.4, places=3)
            cfg = body["ix_c04b.cfg"].data.decode("cp932")
            self.assertIn('VERTEX_ANIME "skin";', cfg)
            self.assertEqual(prov["vertex_anime"]["alloc_dbuff_dropped"], ["o"])
            self.assertEqual(rep["skin"]["frames"]["skin"]["bone_count"], 19)
            names = [o.name for o in mc.read_mds(body["ix_c04b.mds"].data, "out")]
            self.assertEqual((names[19], names[49], names[8], names[5]), ("ef00", "gun_hand", "bcol00", "bcol01"))
            keys = {k["name"]: k for k in prov["keys"]}
            self.assertEqual([(keys[n]["start"], keys[n]["end"]) for n in ("dc1_11", "dc1_12", "dc1_13")],
                             [(240, 251), (250, 250), (251, 255)])
            self.assertEqual([(keys[n]["start"], keys[n]["end"]) for n in ("dc1_29", "dc1_30")], [(1, 1), (1, 1)])
            self.assertEqual(len(rep["key_names"]), 36 + 46)
            self.assertEqual(prov["weapon"]["frames"], ["pati2", "chn30", "jnt30_1", "eff30", "null24", "c04w01"])
            self.assertIsNone(prov["weapon"]["hit_frame"])
            self.assertEqual(prov["weapon"]["points"], ["eff30"])


class SkinnedMonsterSyntheticTests(unittest.TestCase):
    def test_model_space_bbp_chains_down_the_tree_and_resets_the_skin_owner(self):
        # root -> leg (rotated +90 degrees about Z, raised 3) -> foot (2 along the leg's X); skin hangs off leg.
        data = mds([("root", -1, None), ("leg", 0, None), ("foot", 1, None), ("skin", 1, mdt())])
        rot_z = (0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 3, 0, 1)
        foot = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 0, 0, 1)
        skin_own = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 7, 7, 7, 1)  # must drop out, as in DC1
        objs = mc.read_mds(data, "t")
        out, info = mc.model_space_bbp(objs, _bbp([IDENT, rot_z, foot, skin_own]), [3], "t")
        rows = [struct.unpack_from("<16f", out, i * 64) for i in range(4)]
        self.assertEqual(rows[0], IDENT)
        self.assertEqual(rows[1], rot_z)                      # parent is the identity root: unchanged
        self.assertEqual(rows[2][12:15], (0.0, 5.0, 0.0))     # foot: leg raised 3 plus 2 along local X -> model Y
        self.assertEqual(rows[3], rows[1])                    # skin owner takes its parent's chained row
        self.assertEqual(info["skin_owner_reset_to_parent"], [{"skin": "skin", "index": 3, "parent": "leg"}])
        with self.assertRaisesRegex(ConvertError, "rows for"):
            mc.model_space_bbp(objs, _bbp([IDENT]), [3], "t")

    def test_author_cfg_rigid_defaults_are_unchanged_and_skin_adds_vertex_anime_before_model(self):
        args = ("n", ["i.img"], "m.mds", None, "m.mot", None, (1.0, 2.0, 3.0), 1.0, (1, 0),
                [[1, [["root", None]]]], [], [("a", 0, 1, 0.1)], None)
        rigid = mc.author_cfg(*args)
        self.assertIn('MOTION 0, "m.mot", "", "";', rigid)
        self.assertNotIn("VERTEX_ANIME", rigid)
        skin = mc.author_cfg(*args, None, ["obj7"], "m.bbp", "m.wgt")
        self.assertLess(skin.index("VERTEX_ANIME"), skin.index("MODEL"))
        self.assertIn('MOTION 0, "m.mot", "m.bbp", "m.wgt";', skin)
        self.assertEqual(skin.replace('VERTEX_ANIME "obj7";\r\n', "").replace('"m.bbp", "m.wgt"', '"", ""'), rigid)


def chain_mdt(n_vertices: int) -> bytes:
    """MDT whose list primitive has triangles (i, i+1, i+2): neighbouring triangles share two corners."""
    tris = [(i, i + 1, i + 2) for i in range(n_vertices - 2)]
    return mdt_n(n_vertices, ((3, [(v, v, v) for t in tris for v in t]),))


def mdt_n(n: int, prims) -> bytes:
    verts = b"".join(struct.pack("<4f", float(x), float(x % 7), 0, 1) for x in range(n))
    faces = bytearray(struct.pack("<iiii", 0, 16, len(prims), 0))
    for ftype, idx in prims:
        faces += struct.pack("<III", ftype, len(idx), 0)
        for tup in idx:
            faces += struct.pack(f"<{len(tup)}i", *tup)
    faces = bytes(faces) + b"\0" * (-len(faces) % 16)
    vofs = 0x40
    fofs = vofs + len(verts)
    nofs = fofs + len(faces)
    uofs = nofs + len(verts)
    mofs = uofs + len(verts)
    mat = (struct.pack("<13f", *([1.0] * 7 + [0.0] * 5 + [50.0])) + b"tex01".ljust(44, b"\0"))[:96].ljust(96, b"\0")
    size = mofs + len(mat)
    head = b"MDT\0" + struct.pack("<15i", 0x40, size, n, vofs, n, nofs, 0, 0, len(faces), fofs, n, uofs, 1, mofs, 0)
    return head + verts + faces + verts + verts + mat


class SkinSplitSyntheticTests(unittest.TestCase):
    """DRAN-R1: a skin frame over 32 bones or 800 vertices becomes sibling visuals."""

    def build(self, n_vertices=42, bones=40):
        objects = [("root", -1, None)] + [(f"jnt{i}", 0, None) for i in range(bones)] + [("skin", 0, chain_mdt(n_vertices))]
        data = mds(objects)
        skin = len(objects) - 1
        # vertex v: 100 on joint v % bones (one block per joint, in joint order)
        blocks = [(skin, 1 + b, [(v, 100.0) for v in range(n_vertices) if v % bones == b]) for b in range(bones)]
        bbp = b"".join(struct.pack("<16f", 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, i, 0, 0, 1) for i in range(len(objects)))
        return data, bbp, wgt(blocks), skin

    def test_split_conserves_triangles_and_weights_and_meets_both_caps(self):
        data, bbp, w, skin = self.build()
        with self.assertRaisesRegex(ConvertError, "Bone Num Over"):
            mc.validate_wgt(w, mc.read_mds(data, "t"), data, ["skin"], "t")
        out, out_bbp, out_wgt, info = mc.split_skin_frame(data, bbp, w, "skin", "t")
        objs = mc.read_mds(out, "t")
        names = [v["name"] for v in info["visuals"]]
        self.assertEqual(names, ["skin", "skin_b"])
        self.assertEqual(len(objs), skin + 2)
        self.assertEqual((objs[-1].name, objs[-1].parent), ("skin_b", 0))
        self.assertEqual(len(out_bbp), len(objs) * 64)
        self.assertEqual(out_bbp[-64:], bbp[skin * 64:(skin + 1) * 64])
        rep = mc.validate_wgt(out_wgt, objs, out, names, "t")
        self.assertTrue(all(f["bone_count"] <= 32 for f in rep["frames"].values()))
        self.assertEqual(sum(v["triangles"] for v in info["visuals"]), 40)
        self.assertEqual(sum(v["vertices"] for v in info["visuals"]) - 42, info["duplicated_vertices"])
        self.assertGreater(info["duplicated_vertices"], 0)  # the boundary corners are carried by both visuals
        for o in objs:
            if o.mesh:
                mc.validate_mdt(out, o.mesh, o.name)

    def test_vertex_cap_alone_splits(self):
        data, bbp, w, _skin = self.build(n_vertices=30, bones=4)
        out, _b, out_wgt, info = mc.split_skin_frame(data, bbp, w, "skin", "t", vertex_cap=10)
        self.assertTrue(all(v["vertices"] <= 10 for v in info["visuals"]))
        self.assertEqual(sum(v["triangles"] for v in info["visuals"]), 28)
        mc.validate_wgt(out_wgt, mc.read_mds(out, "t"), out, [v["name"] for v in info["visuals"]], "t")

    def test_one_strip_over_the_cap_is_refused(self):
        objects = [("root", -1, None)] + [(f"jnt{i}", 0, None) for i in range(40)]
        objects.append(("skin", 0, mdt_n(42, ((4, [(v, v, v) for v in range(42)]),))))
        data = mds(objects)
        blocks = [(41, 1 + b, [(v, 100.0) for v in range(42) if v % 40 == b]) for b in range(40)]
        bbp = b"\0" * 64 * len(objects)
        with self.assertRaisesRegex(ConvertError, "one face unit needs 40 bones"):
            mc.split_skin_frame(data, bbp, wgt(blocks), "skin", "t")


# Pinned outputs of the rigid path (checked at de252cc before the skinned branch, and again after it).
RIGID_PACK_SHA256 = {"e104a": "8c5cd70e55159b92281b70225a44ddc1f94f0db5b1f40ef4cd2088e98a796ef1",
                     "e42a": "b825206c0514b35958b53cf95dc41a7f741351751e63fc005a4777a6f51ce44d"}
# King Mimic at 9cc3b6d (SKINNED-R1); DRAN-R1's split must leave an in-cap skinned donor unchanged.
E34A_PACK_SHA256 = "95d39c13b8172d63c12345f8989bc1da8d020cdf4d0755fb4be20254a0c9a57d"


@unittest.skipUnless(DC1, "set IXION_DC1_DATA for the King Mimic (e34a) real-data tests")
class KingMimicRealDataTests(unittest.TestCase):
    SRC = Path(DC1) / "dun" / "monstor" / "e34a.chr" if DC1 else None

    def convert_mimic(self, tmp: str, src_path: Path | None = None):
        out = Path(tmp) / "e34a-dc2"
        prov = mc.convert(src_path or self.SRC, None, None, out)
        pack = (out / prov["output_chr"]).read_bytes()
        doc = json.loads((out / "port_data" / "catalog.json").read_text(encoding="utf-8"))
        return prov, pack, {s["source"].lower(): s for s in doc["sources"]}, out

    def mutated(self, tmp: str, edit) -> Path:
        members = mc.pack_members_ordered(self.SRC.read_bytes())
        path = Path(tmp) / "mut" / "e34a.chr"
        path.parent.mkdir()
        path.write_bytes(mc.build_pack(edit(members)))
        return path

    def test_convert_e34a_skinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            prov, pack, catalog, out = self.convert_mimic(tmp)
            report = mc.validate_chr(pack, "ix_e34a", None, catalog, out / "port_data")
            self.assertEqual(report["warnings"], [])
            self.assertEqual((report["frames"], report["meshed"]), (53, 29))
            self.assertEqual(report["poly_num"], [report["triangles"], report["shadow_triangles"]])
            skin = report["skin"]["frames"]["obj7"]
            self.assertEqual((skin["bone_count"], skin["vertices_weighted"], skin["max_influences"]), (4, 58, 2))
            self.assertEqual(report["key_names"], [f"dc1_{i:02d}" for i in range(23)])
            src, dst = mc.parse_pack(self.SRC.read_bytes()), mc.parse_pack(pack)
            self.assertEqual(dst["ix_e34a.mot"].data, src["e34a.mot"].data)
            self.assertEqual(dst["ix_e34a.wgt"].data, src["e34a.wgt"].data)
            self.assertEqual(len(dst["ix_e34a.bbp"].data), 53 * 64)
            cfg = dst["ix_e34a.cfg"].data.decode("cp932")
            self.assertIn('VERTEX_ANIME "obj7";', cfg)
            self.assertLess(cfg.index("VERTEX_ANIME"), cfg.index("MODEL"))
            self.assertIn('MOTION 0, "ix_e34a.mot", "ix_e34a.bbp", "ix_e34a.wgt";', cfg)
            self.assertNotIn("SHADOW_MOTION", cfg)
            self.assertEqual(prov["skin"]["vertex_anime"], {"dc1": [1], "dc2": ["obj7"]})
            self.assertEqual(prov["skin"]["bbp"]["skin_owner_reset_to_parent"],
                             [{"skin": "obj7", "index": 2, "parent": "null60"}])
            # Every skin bone hangs off the identity root, so the model-space table equals DC1's to float noise.
            for i in range(53):
                a = struct.unpack_from("<16f", src["e34a.bbp"].data, i * 64)
                b = struct.unpack_from("<16f", dst["ix_e34a.bbp"].data, i * 64)
                if i in (1, 2, 4, 5, 6) or any(a):
                    self.assertTrue(all(abs(x - y) < 1e-6 for x, y in zip(a, b)), i)

    def test_skinned_refusals(self):
        def drop_wgt(members):
            return [m for m in members if m[0].lower() != "e34a.wgt"]

        def edit_cfg(old, new):
            def go(members):
                return [(n, d.decode("cp932").replace(old, new).encode("cp932") if n == "info.cfg" else d)
                        for n, d in members]
            return go
        cases = ((drop_wgt, "lacks"),
                 (edit_cfg('ALLOC_DBUFF "obj7"', ""), "no ALLOC_DBUFF"),
                 (edit_cfg('"e34a.bbp", "e34a.wgt"', '"e34a.bbp", ""'), "both a .bbp and a .wgt"),
                 (edit_cfg('"e34a.bbp", "e34a.wgt"', '"e34a.bbp", "x.wgt"'), "not <model>.wgt"),
                 (edit_cfg('SHADOW_MOTION "e34s.mot", "", ""', 'SHADOW_MOTION "e34s.mot", "e34a.bbp", "e34a.wgt"'),
                  "skinned shadow"))
        for edit, msg in cases:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ConvertError, msg):
                    self.convert_mimic(tmp, self.mutated(tmp, edit))

    def test_rigid_packs_are_byte_identical_to_before_the_skinned_branch(self):
        for model, want in RIGID_PACK_SHA256.items():
            with tempfile.TemporaryDirectory() as tmp:
                prov = mc.convert(Path(DC1) / "dun" / "monstor" / f"{model}.chr", None, None, Path(tmp) / model)
                self.assertEqual(prov["output_chr_sha256"], want, model)
                self.assertNotIn("skin", prov)

    def test_mimic_pack_is_byte_identical_after_the_skin_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            prov, _pack, _catalog, _out = self.convert_mimic(tmp)
            self.assertEqual(prov["output_chr_sha256"], E34A_PACK_SHA256)
            self.assertNotIn("split", prov["skin"])
            self.assertNotIn("shadow", prov["dropped_skin"])


@unittest.skipUnless(DC1, "set IXION_DC1_DATA for the Dran (c12a) real-data test")
class DranRealDataTests(unittest.TestCase):
    def test_convert_c12a_splits_obj1_and_drops_the_missing_shadow(self):
        src_path = Path(DC1) / "dun" / "monstor" / "c12a.chr"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c12a-dc2"
            prov = mc.convert(src_path, None, None, out)
            pack = (out / prov["output_chr"]).read_bytes()
            doc = json.loads((out / "port_data" / "catalog.json").read_text(encoding="utf-8"))
            report = mc.validate_chr(pack, "ix_c12a", None, {s["source"].lower(): s for s in doc["sources"]},
                                     out / "port_data")
        self.assertEqual(report["warnings"], [])
        split = prov["skin"]["split"][0]
        self.assertEqual((split["source"]["vertices"], split["source"]["triangles"], split["source"]["bones"]),
                         (1669, 3274, 35))
        visuals = [v["name"] for v in split["visuals"]]
        self.assertEqual(visuals, ["obj1", "obj1_b", "obj1_c"])
        self.assertEqual(sum(v["triangles"] for v in split["visuals"]), 3274)
        frames = report["skin"]["frames"]
        for name in visuals:
            self.assertLessEqual(frames[name]["bone_count"], 32)
            self.assertLessEqual(frames[name]["vertices_weighted"], 800)
        self.assertEqual(report["triangles"], 3274 + 126)  # obj1 visuals plus the rigid tongue (bero)
        self.assertEqual(report["poly_num"], [3400, 0])
        self.assertEqual(prov["skin"]["vertex_anime"]["dc2"], visuals)
        src, dst = mc.parse_pack(src_path.read_bytes()), mc.parse_pack(pack)
        self.assertEqual(dst["ix_c12a.mot"].data, src["c12a.mot"].data)
        self.assertEqual(prov["copied_unchanged"], ["c12a.mot"])
        cfg = dst["ix_c12a.cfg"].data.decode("cp932")
        self.assertIn('VERTEX_ANIME "obj1", "obj1_b", "obj1_c";', cfg)
        self.assertNotIn("SHADOW", cfg)
        self.assertEqual(prov["dropped_skin"]["shadow"]["shadow_model"], "c12s.mds")
        # every visual's model-space base is its parent's chained row, so all three share obj1's row
        bbp = dst["ix_c12a.bbp"].data
        self.assertEqual(len(bbp), 43 * 64)
        self.assertEqual(bbp[41 * 64:42 * 64], bbp[2 * 64:3 * 64])
        self.assertEqual(bbp[42 * 64:43 * 64], bbp[2 * 64:3 * 64])


if __name__ == "__main__":
    unittest.main()
