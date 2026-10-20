from __future__ import annotations

import hashlib
import json
import os
import contextlib
import io
import math
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import room_converter as rc


def make_pack(entries: list[tuple[str, bytes]]) -> bytes:
    result=bytearray()
    for name,payload in entries:
        step=((80+len(payload)+15)//16)*16
        result.extend(name.encode("ascii").ljust(64,b"\0"))
        result.extend(struct.pack("<iii",80,len(payload),step))
        result.extend(b"\0"*4)  # Retail pack entries reserve the fourth word in their 80-byte header.
        result.extend(payload)
        result.extend(b"\0"*(step-80-len(payload)))
    result.extend(b"\0"*80)
    return bytes(result)


def make_mds() -> bytes:
    data=bytearray(16+112)
    data[:16]=b"MDS\0"+struct.pack("<III",1,1,16)
    data[16:24]=b"\0"*8
    data[24:32]=b"root\0".ljust(8,b"\0")
    struct.pack_into("<ii",data,56,0,-1)
    # Native libvu0 layout stores the four basis/translation vectors; translation is vector 3.
    struct.pack_into("<16f",data,64,1,0,0,0, 0,1,0,0, 0,0,1,0, 3,4,5,1)
    return bytes(data)


def make_mds_graph(matrices: list[tuple[float,...]], parents: list[int]) -> bytes:
    data=bytearray(16+112*len(matrices))
    data[:16]=b"MDS\0"+struct.pack("<III",1,len(matrices),16)
    for i,(matrix,parent) in enumerate(zip(matrices,parents)):
        at=16+i*112
        data[at+8:at+40]=f"node{i}".encode("ascii").ljust(32,b"\0")
        struct.pack_into("<ii",data,at+40,0,parent)
        struct.pack_into("<16f",data,at+48,*matrix)
    return bytes(data)


def native_apply(matrix: tuple[float,...], vector: tuple[float,...]) -> tuple[float,...]:
    """Independent oracle matching libvu0's four-column-vector Apply implementation."""
    return tuple(sum(matrix[col*4+row]*vector[col] for col in range(4)) for row in range(4))


def native_multiply(a: tuple[float,...], b: tuple[float,...]) -> tuple[float,...]:
    """Independent oracle: transform each stored column of b by a, as libvu0 Multiply does."""
    return tuple(value for col in range(4) for value in native_apply(a,b[col*4:col*4+4]))


class PackTests(unittest.TestCase):
    def test_walks_relative_members_and_casefolds(self):
        pack=rc.parse_pack(make_pack([("room.mds",b"MDS\0"),("empty.img",b"")]))
        self.assertEqual(pack["room.mds"].data,b"MDS\0")
        self.assertEqual(pack["empty.img"].data,b"")

    def test_rejects_truncation_bad_stride_and_unsafe_name(self):
        with self.assertRaisesRegex(rc.ConvertError,"truncated"):
            rc.parse_pack(b"short")
        bad=bytearray(make_pack([("room.mds",b"x")]))
        struct.pack_into("<i",bad,72,81)
        with self.assertRaisesRegex(rc.ConvertError,"stride"):
            rc.parse_pack(bytes(bad))
        with self.assertRaisesRegex(rc.ConvertError,"unsafe"):
            rc.parse_pack(make_pack([("../room.mds",b"x")]))

    def test_rejects_unsupported_texture_container_and_mds_version(self):
        with self.assertRaisesRegex(rc.ConvertError,"IMG signature"):
            rc.decode_img(b"NOPE"+b"\0"*12)
        broken=bytearray(make_mds())
        struct.pack_into("<I",broken,4,2)
        with self.assertRaisesRegex(rc.ConvertError,"unsupported MDS header"):
            rc.parse_mds(bytes(broken))

    def test_rejects_pack_missing_end_record(self):
        with self.assertRaises(rc.ConvertError):
            rc.parse_pack(make_pack([("room.mds",b"x")])[:-80])

    def test_rejects_casefold_duplicates_in_both_orders(self):
        for entries in ((('room.mds',b'first'),('ROOM.MDS',b'second')),
                        (('ROOM.MDS',b'first'),('room.mds',b'second'))):
            with self.subTest(entries=entries), self.assertRaisesRegex(rc.ConvertError,"duplicate"):
                rc.parse_pack(make_pack(list(entries)))

    def test_enforces_limit_on_physical_member_count(self):
        entries=[(f"member-{i:04d}.bin",b"") for i in range(rc.MAX_MEMBERS+1)]
        with self.assertRaisesRegex(rc.ConvertError,"member-count limit"):
            rc.parse_pack(make_pack(entries))


class GeometryTests(unittest.TestCase):
    def test_source_matrix_translation_is_applied_once(self):
        objects=rc.parse_mds(make_mds())
        matrices=rc.world_matrices(objects,(10,20,30))
        self.assertEqual(rc.transform_point(matrices[0],(1,2,3)),(14,26,38))

    def test_native_fourth_vector_and_noncommuting_parent_child_oracle(self):
        c=0.0; s=1.0
        parent=(c,0,-s,0, 0,1,0,0, s,0,c,0, 10,2,3,1)
        child=(1,0,0,0, 0,c,-s,0, 0,s,c,0, 2,4,1,1)
        parsed=rc.parse_mds(make_mds_graph([parent,child],[-1,0]))
        actual=rc.world_matrices(parsed,(0,0,0))
        native_world=native_multiply(parent,child)
        native_origin=native_apply(native_world,(0,0,0,1))
        self.assertEqual(tuple(round(x,6) for x in rc.transform_point(actual[1],(0,0,0))),
                         tuple(round(x,6) for x in native_origin[:3]))
        self.assertEqual(tuple(round(x,6) for x in native_origin[:3]),(11.0,6.0,1.0))
        native_point=native_apply(native_world,(3,5,7,1))
        self.assertEqual(tuple(round(x,6) for x in rc.transform_point(actual[1],(3,5,7))),
                         tuple(round(x,6) for x in native_point[:3]))

        # DC1 turn k is SetRotation(0, -90*k deg, 0): local' = RotMatrixY(angle)*local, then
        # translation += position (frame.cpp:489-514). The oracle builds libvu0 RotMatrixY's stored
        # columns (c,0,-s), (0,1,0), (s,0,c) itself.
        for k in (1,2,-1):
            angle=math.radians(-90.0*k); c,s=math.cos(angle),math.sin(angle)
            native_rot=(c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1)
            native_placed=list(native_multiply(native_rot,parent))
            native_placed[12]+=7.0
            turned=rc.world_matrices(parsed,(7,0,0),y_turn=k)
            for point in ((0,0,0),(3,5,7)):
                expected=native_apply(tuple(native_placed),(*point,1))[:3]
                self.assertEqual(tuple(round(x,5) for x in rc.transform_point(turned[0],point)),
                                 tuple(round(x,5) for x in expected),(k,point))

    def test_normal_uses_inverse_transpose_for_nonuniform_scale(self):
        # A = Rz(90) * diag(2,1,0.5); tangent and transformed normal stay perpendicular.
        matrix=(0,-1,0,0, 2,0,0,0, 0,0,0.5,0, 0,0,0,1)
        tangent=rc.transform_point(matrix,(1,0,0))
        normal=rc.transform_normal(matrix,(0,1,0))
        self.assertAlmostEqual(sum(tangent[i]*normal[i] for i in range(3)),0.0,places=6)
        self.assertAlmostEqual(sum(v*v for v in normal),1.0,places=6)

    def test_real_donor_origins_and_vertices_match_native_apply_multiply(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA for independent native matrix qualification")
        source=Path(data_root)/"dun"/"mpd_pack"/"d01inter.mpd"
        member=rc.parse_pack(source.read_bytes())["d01i01_0.mds"].data
        objects=rc.parse_mds(member)

        # Independent oracle: these loops mirror frame.cpp's native matrix contract, not the
        # converter's row-major matrix helpers. libvu0 Apply transforms a column vector from
        # four stored columns; Multiply applies the parent matrix to each local column.
        native_world=[]; native_raw=[]
        for i in range(len(objects)):
            at=16+i*112
            raw=struct.unpack_from("<16f",member,at+48)
            parent=struct.unpack_from("<i",member,at+44)[0]
            native_raw.append(raw)
            native_world.append(raw if parent<0 else native_multiply(native_world[parent],raw))
        converted=rc.world_matrices(objects,(0.0,0.0,0.0))
        by_name={obj["name"]:i for i,obj in enumerate(objects)}
        expected_local={
            "event00":(0.0,0.0,240.00009155273438),
            "obj865__s":(112.00030517578125,103.00004577636719,-43.00008773803711),
            "obj864__s":(31.999988555908203,103.0,-196.00003051757825),
        }
        for name,raw_translation in expected_local.items():
            i=by_name[name]
            self.assertEqual(tuple(round(v,5) for v in native_raw[i][12:15]),
                             tuple(round(v,5) for v in raw_translation))
            native_origin=native_apply(native_world[i],(0.0,0.0,0.0,1.0))[:3]
            converter_origin=rc.transform_point(converted[i],(0.0,0.0,0.0))
            self.assertEqual(tuple(round(v,5) for v in converter_origin),
                             tuple(round(v,5) for v in native_origin))
            self.assertGreater(sum(abs(v) for v in converter_origin),1.0)

        compared_vertices=0
        for name in ("obj865__s","obj864__s"):
            i=by_name[name]; obj=objects[i]
            self.assertTrue(obj["mesh"])
            count,offset=struct.unpack_from("<ii",member,obj["mesh"]+12)
            self.assertGreater(count,0)
            for vertex in range(min(count,3)):
                point=struct.unpack_from("<3f",member,obj["mesh"]+offset+vertex*16)
                native_point=native_apply(native_world[i],(*point,1.0))[:3]
                converter_point=rc.transform_point(converted[i],point)
                self.assertEqual(tuple(round(v,5) for v in converter_point),
                                 tuple(round(v,5) for v in native_point))
                compared_vertices+=1
        self.assertEqual(compared_vertices,6)

    @staticmethod
    def actor_y_bounds(mds: bytes) -> tuple[float,float]:
        objects=rc.parse_mds(mds); matrices=rc.world_matrices(objects,(0,0,0)); ys=[]
        for i,obj in enumerate(objects):
            if not obj["mesh"]: continue
            count,offset=struct.unpack_from("<ii",mds,obj["mesh"]+12)
            for j in range(count):
                point=struct.unpack_from("<3f",mds,obj["mesh"]+offset+j*16)
                ys.append(rc.transform_point(matrices[i],point)[1])
        if not ys: raise rc.ConvertError("actor model has no mesh vertices")
        return min(ys),max(ys)

    def test_rejects_bad_mds_and_cycles(self):
        with self.assertRaisesRegex(rc.ConvertError,"signature"):
            rc.parse_mds(b"MDS")
        data=bytearray(make_mds()+make_mds()[16:])
        struct.pack_into("<I",data,8,2)
        struct.pack_into("<i",data,60,1)
        struct.pack_into("<i",data,16+112+44,0)
        with self.assertRaisesRegex(rc.ConvertError,"cyclic|forward parent"):
            rc.parse_mds(bytes(data))

    def test_rejects_non_affine_and_singular_native_matrices(self):
        non_affine=bytearray(make_mds()); struct.pack_into("<f",non_affine,64+3*4,0.25)
        with self.assertRaisesRegex(rc.ConvertError,"non-affine"):
            rc.parse_mds(bytes(non_affine))
        singular=bytearray(make_mds()); struct.pack_into("<f",singular,64,0.0)
        with self.assertRaisesRegex(rc.ConvertError,"singular"):
            rc.parse_mds(bytes(singular))

    def test_rejects_parent_below_minus_one_forward_parent_and_cycle(self):
        invalid=bytearray(make_mds()); struct.pack_into("<i",invalid,60,-2)
        with self.assertRaisesRegex(rc.ConvertError,"parent"):
            rc.parse_mds(bytes(invalid))
        forward=bytearray(make_mds()+make_mds()[16:]); struct.pack_into("<I",forward,8,2)
        struct.pack_into("<i",forward,60,1)
        with self.assertRaisesRegex(rc.ConvertError,"forward parent"):
            rc.parse_mds(bytes(forward))
        cycle=bytearray(make_mds()+make_mds()[16:]); struct.pack_into("<I",cycle,8,2)
        struct.pack_into("<i",cycle,60,1); struct.pack_into("<i",cycle,16+112+44,0)
        with self.assertRaisesRegex(rc.ConvertError,"forward parent|cyclic"):
            rc.parse_mds(bytes(cycle))

    def test_rejects_real_member_with_truncated_mdt_resource(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA to run real MDT extent regression")
        source=Path(data_root)/"dun"/"mpd_pack"/"d01inter.mpd"
        members=rc.parse_pack(source.read_bytes())
        member=members["d01i01_0.mds"].data
        textures=rc.decode_img(members["d01i01.img"].data)
        mesh=next(obj["mesh"] for obj in rc.parse_mds(member) if obj["mesh"])
        truncated=bytearray(member); struct.pack_into("<I",truncated,mesh+8,64)
        with self.assertRaisesRegex(rc.ConvertError,"MDT resource"):
            rc.parse_visual_mds(bytes(truncated),(0,0,0),0,{})

    def test_rejects_real_mdt_offsets_that_escape_each_section(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA to run real section-boundary regressions")
        source=Path(data_root)/"dun"/"mpd_pack"/"d01inter.mpd"
        member=rc.parse_pack(source.read_bytes())["d01i01_0.mds"].data
        mesh=next(obj["mesh"] for obj in rc.parse_mds(member) if obj["mesh"])
        size=struct.unpack_from("<I",member,mesh+8)[0]
        for header_offset,label in ((16,"vertex"),(24,"normal"),(40,"face"),(48,"UV"),(56,"material")):
            bad=bytearray(member); struct.pack_into("<i",bad,mesh+header_offset,size-4)
            with self.subTest(section=label), self.assertRaises(rc.ConvertError):
                rc.parse_visual_mds(bytes(bad),(0,0,0),0,{})

    def test_rejects_cross_resource_face_primitive_indices(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA to run real primitive-section regression")
        source=Path(data_root)/"dun"/"mpd_pack"/"d01inter.mpd"
        members=rc.parse_pack(source.read_bytes())
        member=members["d01i01_0.mds"].data
        textures=rc.decode_img(members["d01i01.img"].data)
        mesh=next(obj["mesh"] for obj in rc.parse_mds(member) if obj["mesh"])
        face_size=struct.unpack_from("<i",member,mesh+36)[0]
        self.assertGreater(face_size,16)
        for truncated_size,pattern in ((16,"primitive header"),(28,"primitive indices")):
            bad=bytearray(member); struct.pack_into("<i",bad,mesh+36,truncated_size)
            with self.subTest(face_size=truncated_size), self.assertRaisesRegex(rc.ConvertError,pattern):
                rc.parse_visual_mds(bytes(bad),(0,0,0),0,textures)

    def test_rejects_nonzero_real_per_index_color_sections(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA to run real color-subset regression")
        source=Path(data_root)/"dun"/"mpd_pack"/"d01inter.mpd"
        members=rc.parse_pack(source.read_bytes())
        member=members["d01i01_0.mds"].data
        mesh=next(obj["mesh"] for obj in rc.parse_mds(member) if obj["mesh"])
        self.assertEqual(struct.unpack_from("<i",member,mesh+28)[0],0)
        # A colour section changes every strip entry to {v,n,uv,colour}; grafting one onto
        # three-word strips must fail rather than misread indices.
        bad=bytearray(member); struct.pack_into("<i",bad,mesh+28,1); struct.pack_into("<i",bad,mesh+32,64)
        with self.assertRaises(rc.ConvertError):
            rc.parse_visual_mds(bytes(bad),(0,0,0),0,rc.decode_img(members["d01i01.img"].data))
        count_only=bytearray(member); struct.pack_into("<i",count_only,mesh+28,1)
        with self.assertRaisesRegex(rc.ConvertError,"invalid per-index color section"):
            rc.parse_visual_mds(bytes(count_only),(0,0,0),0,rc.decode_img(members["d01i01.img"].data))

    def test_rejects_collision_mdt_extent_and_offsets(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA to run real collision-MDT regressions")
        source=Path(data_root)/"dun"/"mpd_pack"/"d01inter.mpd"
        member=rc.parse_pack(source.read_bytes())["d01i01_a.mds"].data
        objects=rc.parse_mds(member); mesh=next(obj["mesh"] for obj in objects if obj["mesh"])
        shortened=bytearray(member); struct.pack_into("<I",shortened,mesh+8,64)
        with self.assertRaisesRegex(rc.ConvertError,"MDT resource"):
            rc.parse_collision_mds(bytes(shortened),(0,0,0),0)
        size=struct.unpack_from("<I",member,mesh+8)[0]
        for offset_field,label in ((16,"vertex"),(40,"index")):
            bad=bytearray(member); struct.pack_into("<i",bad,mesh+offset_field,size-4)
            with self.subTest(section=label), self.assertRaises(rc.ConvertError):
                rc.parse_collision_mds(bytes(bad),(0,0,0),0)

    def test_real_donor_pack_cfg_meshes_and_consumer_schema(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        output=os.environ.get("IXION_ROOM_PACK")
        if not data_root or not output:
            self.skipTest("set IXION_DC1_DATA and IXION_ROOM_PACK to run retail-data qualification")
        root=Path(data_root); out=Path(output)
        source=root/"dun"/"mpd_pack"/"d01inter.mpd"
        cfg=root/"dun"/"d01inter.cfg"
        pack=rc.parse_pack(source.read_bytes())
        self.assertEqual(len(pack),26)
        placement,direction,collision_turn=rc.parse_cfg_placement(cfg.read_bytes(),"d01i01_0.mds","d01i01_a.mds")
        self.assertEqual(placement,(0.0,0.0,0.0))
        self.assertEqual((direction,collision_turn),(0,0))
        textures=rc.decode_img(pack["d01i01.img"].data)
        visuals,visual_count=rc.parse_visual_mds(pack["d01i01_0.mds"].data,placement,0,textures)
        collisions=rc.parse_collision_mds(pack["d01i01_a.mds"].data,placement,0)
        self.assertGreater(visual_count,1000)
        self.assertGreater(len(collisions),1000)
        def on_zero_floor(x: float, z: float) -> bool:
            for tri in collisions:
                (x1,y1,z1),(x2,y2,z2),(x3,y3,z3)=tri
                den=(z2-z3)*(x1-x3)+(x3-x2)*(z1-z3)
                if abs(den)<1e-8: continue
                a=((z2-z3)*(x-x3)+(x3-x2)*(z-z3))/den
                b=((z3-z1)*(x-x3)+(x1-x3)*(z-z3))/den
                c=1-a-b
                if min(a,b,c)>=-1e-5 and abs(a*y1+b*y2+c*y3)<0.05: return True
            return False
        self.assertTrue(all(on_zero_floor(x,0) for x in (0,40,80)))
        room=rc.validate_pack(out)
        self.assertEqual(room["donor"],{"game":"dc1","room":"d01inter","sources":room["donor"]["sources"]})
        self.assertEqual(sum(len(v["vertices"])//3 for v in room["visuals"]),visual_count)
        self.assertEqual(len(room["collision"]),len(collisions))
        self.assertEqual(len(room["textures"]),20)
        self.assertEqual({t["name"] for t in room["textures"]},set(textures))

    def test_real_toon_and_max_dimensions_justify_room_scale(self):
        c1=os.environ.get("IXION_DC1_DATA"); c2=os.environ.get("IXION_DC2_DATA")
        if not c1 or not c2:
            self.skipTest("set IXION_DC1_DATA and IXION_DC2_DATA for actor-scale qualification")
        toan=rc.parse_pack((Path(c1)/"dun"/"mainchara"/"c01d.chr").read_bytes())
        max_pack=rc.parse_pack((Path(c2)/"mainchr"/"c01fuku1.chr").read_bytes())
        toan_bounds=[self.actor_y_bounds(toan[k].data) for k in ("c01d.mds","c01s.mds")]
        toan_height=max(y[1] for y in toan_bounds)-min(y[0] for y in toan_bounds)
        max_bounds=self.actor_y_bounds(max_pack["c01f.mds"].data)
        max_height=max_bounds[1]-max_bounds[0]
        ratio=max_height/toan_height
        self.assertGreater(toan_height,10)
        self.assertGreater(max_height,toan_height)
        self.assertGreater(ratio,1.5)
        self.assertLess(ratio,1.6)

    def test_real_pack_markers_have_floor_contact_and_max_body_clearance(self):
        pack_root=os.environ.get("IXION_ROOM_PACK")
        data_root=os.environ.get("IXION_DC2_DATA")
        if not pack_root or not data_root: self.skipTest("set IXION_ROOM_PACK and IXION_DC2_DATA for real marker/path qualification")
        room=rc.validate_pack(Path(pack_root))
        spawn=room["spawn"]; enemy=room["enemy_spawn"]; exit_at=room["exit"]
        self.assertEqual(tuple(round(v,3) for v in spawn),(0.0,0.0,0.0))
        self.assertEqual(tuple(round(v,3) for v in enemy),(93.509,0.0,0.0))
        self.assertEqual(tuple(round(v,3) for v in exit_at),(249.357,0.0,0.0))
        tris=room["collision"]

        def vertical_surfaces(x: float,z: float) -> list[tuple[float,float]]:
            hits=[]
            for tri in tris:
                (x1,y1,z1),(x2,y2,z2),(x3,y3,z3)=tri
                den=(z2-z3)*(x1-x3)+(x3-x2)*(z1-z3)
                if abs(den)<1e-8: continue
                a=((z2-z3)*(x-x3)+(x3-x2)*(z-z3))/den
                b=((z3-z1)*(x-x3)+(x1-x3)*(z-z3))/den
                c=1-a-b
                if min(a,b,c)<-1e-6: continue
                ny=(z2-z1)*(x3-x1)-(x2-x1)*(z3-z1)
                nx=(y2-y1)*(z3-z1)-(z2-z1)*(y3-y1)
                nz=(x2-x1)*(y3-y1)-(y2-y1)*(x3-x1)
                length=math.sqrt(nx*nx+ny*ny+nz*nz)
                if length and abs(ny)/length>=0.65:
                    hits.append((a*y1+b*y2+c*y3,abs(ny)/length))
            return hits

        # The route is sampled in consumer/output units using actual converted retail collision.
        # The floor support check is independent barycentric geometry, not converter counters.
        route_x=[]
        cursor=spawn[0]
        while cursor<exit_at[0]:
            route_x.append(cursor); cursor+=5.0
        route_x.append(exit_at[0])
        for x in route_x:
            floors=[(y,n) for y,n in vertical_surfaces(x,0.0) if abs(y)<0.1 and n>=0.65]
            self.assertTrue(floors,("missing y=0 floor support",x))

        # Native Max body dimensions come from its actual info.cfg; actionchara.cpp expands
        # body_width to a 4+2*width movement radius. The measured model bounds are even broader.
        max_pack=rc.parse_pack((Path(data_root)/"mainchr"/"c01fuku1.chr").read_bytes())
        info=max_pack["info.cfg"].data.decode("cp932",errors="replace")
        body=re.search(r"(?im)^\s*BODY_SIZE\s+([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)",info)
        self.assertIsNotNone(body)
        body_height,body_width,body_depth=(float(v) for v in body.groups())
        native_move_radius=4.0+2.0*body_width
        self.assertEqual((body_height,body_width,body_depth),(16.0,4.0,0.0))
        self.assertEqual(native_move_radius,12.0)
        # Max's actual mesh AABB is x +/-15.522, z +/-4.449, y 3.211..29.356.
        # Use its circumscribed horizontal radius and a 30-unit vertical envelope, both larger
        # than native movement radius/height, then check the swept body against walls/overhangs.
        radius=max(native_move_radius,15.523)
        xlo=min(spawn[0],exit_at[0])-radius; xhi=max(spawn[0],exit_at[0])+radius
        zlo=-radius; zhi=radius; ylo=1.0; yhi=max(body_height,30.0)
        potential_walls=[]
        for index,tri in enumerate(tris):
            xs=[p[0] for p in tri]; ys=[p[1] for p in tri]; zs=[p[2] for p in tri]
            if max(xs)<xlo or min(xs)>xhi or max(zs)<zlo or min(zs)>zhi or max(ys)<ylo or min(ys)>yhi:
                continue
            a,b,c=tri
            nx=(b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1])
            ny=(b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2])
            nz=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            length=math.sqrt(nx*nx+ny*ny+nz*nz)
            if length and (abs(ny)/length<0.65 or min(ys)>1.0): potential_walls.append(index)
        self.assertEqual(potential_walls,[])
        for marker in (spawn,enemy,exit_at):
            self.assertTrue(any(abs(y-marker[1])<0.1 for y,_ in vertical_surfaces(marker[0],marker[2])),marker)


R3_D01INTER_SHA256="3517c689958910dfeca62d866e66515287be293b501f2e872743e12748674fc8"
R3_SCALE=1.5584790682688
ROOMS_DIR=Path(__file__).resolve().parents[1]/"tools"/"rooms"
# ROOMCONV-R4 room.json digests; the arena sidecar must leave them untouched.
R4_ROOM_SHA256={"d01boss":"41b18b63f810b4867ef4f62871523741de44a0e59c9e09daabea316f93b439c7",
                "d01inter2":"6f37a047b637e605ff2d1befd9242bb92a7a0e7e78b8bd14b461f915accfad9e"}


def floor_ys(tris: list, x: float, z: float) -> list[float]:
    """Independent barycentric probe: heights of near-horizontal triangles under (x, z)."""
    out=[]
    for (x1,y1,z1),(x2,y2,z2),(x3,y3,z3) in tris:
        den=(z2-z3)*(x1-x3)+(x3-x2)*(z1-z3)
        if abs(den)<1e-8: continue
        a=((z2-z3)*(x-x3)+(x3-x2)*(z-z3))/den
        b=((z3-z1)*(x-x3)+(x1-x3)*(z-z3))/den
        c=1-a-b
        if min(a,b,c)<-1e-6: continue
        ny=(z2-z1)*(x3-x1)-(x2-x1)*(z3-z1)
        nx=(y2-y1)*(z3-z1)-(z2-z1)*(y3-y1)
        nz=(x2-x1)*(y3-y1)-(y2-y1)*(x3-x1)
        length=math.sqrt(nx*nx+ny*ny+nz*nz)
        if length and abs(ny)/length>=0.65: out.append(a*y1+b*y2+c*y3)
    return out


class TurnSemanticsTests(unittest.TestCase):
    def test_dc1_turn_keeps_minus_three_quirk(self):
        # dungeonparts.cpp:2119-2124: if (turn > 3) turn -= 3; if (turn == 3) turn = -1.
        self.assertEqual([rc.dc1_turn(k) for k in range(7)],[0,1,2,-1,1,2,-1])

    def test_quarter_turn_maps_east_to_south_like_corner_chain_table(self):
        # Cells sit at (160*col, 0, 160*row): east = +x, south = +z. Corner direction 0 opens
        # E+S (mask 5) and direction 1 opens W+S (mask 3) (dungeonmap.cpp:84-99, 1463-1476).
        parsed=rc.parse_mds(make_mds_graph([(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)],[-1]))
        m=rc.world_matrices(parsed,(0,0,0),y_turn=1)[0]
        self.assertEqual(tuple(round(v,6) for v in rc.transform_point(m,(1,0,0))),(0.0,0.0,1.0))
        self.assertEqual(tuple(round(v,6) for v in rc.transform_point(m,(0,0,1))),(-1.0,0.0,0.0))

    def test_rejects_placing_multi_root_mds(self):
        ident=(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)
        parsed=rc.parse_mds(make_mds_graph([ident,ident],[-1,-1]))
        rc.world_matrices(parsed,(0,0,0),0)
        with self.assertRaisesRegex(rc.ConvertError,"more than one root"):
            rc.world_matrices(parsed,(0,0,0),1)

    def test_cfg_parser_reads_frame_turn_not_minimap_direction(self):
        cfg=(b'SET_PATH "dun/x/"\nGRD_IMG "a.img",1\nDEF_PATS\n PT_BASE "p_0.mds" ,8 ,1,0,-3.2, 2 // c\n'
             b' PT_COLS "p_a.mds" ,1\n PT_MARKER "m1",20,500,OFF,ON,OFF,ON\nDEF_ENDS\n'
             b'DEF_PATS\n PT_BASE "q_0.mds" ,0 ,0,0,0, 0\n PT_BASE "q_1.mds" ,0 ,0,0,0, 3\nDEF_ENDS\n')
        room=rc.parse_room_cfg(cfg)
        self.assertEqual(room.ground_images,("a.img",))
        part=room.parts[0]
        self.assertEqual((part.frames[0].direction_offset,part.frames[0].turn),(8,2))
        self.assertEqual(part.frames[0].offset,(10.0,0.0,-32.0))
        self.assertEqual(rc.part_collision_turn(part),rc.dc1_turn(3))
        self.assertEqual(part.markers[0].name,"m1")
        self.assertIsNone(room.parts[1].collision)
        self.assertEqual([rc.frame_visual_turn(f) for f in room.parts[1].frames],[0,-1])
        for bad in (b'SET_PATH "dun/x/"\nPT_BASE "p.mds",0,0,0,0,0\n',
                    b'SET_PATH "dun/x/"\nDEF_PATS\n PT_COLS "p_a.mds",0\nDEF_ENDS\n',
                    b'SET_PATH "dun/x/"\nDEF_PATS\n PT_BASE "p.mds",0,0,0,0,0\n PT_COLS "a.mds",0\n PT_COLS "b.mds",0\nDEF_ENDS\n'):
            with self.subTest(bad=bad), self.assertRaises(rc.ConvertError):
                rc.parse_room_cfg(bad)


class FixedRoomRealDataTests(unittest.TestCase):
    def setUp(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA for fixed-room qualification")
        self.dun=Path(data_root)/"dun"

    def members(self, name: str) -> dict:
        return rc.parse_pack((self.dun/"mpd_pack"/f"{name}.mpd").read_bytes())

    def test_kit_corner_collision_opens_toward_chain_table_sides(self):
        # Random-floor collision turn is cell direction + PT_COLS turn (dungeonparts.cpp:2162-2163).
        # Corner directions 0..3 open E+S, W+S, W+N, E+N (masks 5,3,10,12; north = -z).
        room=rc.parse_room_cfg((self.dun/"d01main_a.cfg").read_bytes())
        corner=room.parts[1]
        self.assertEqual(corner.frames[0].name,"d01g02_0.mds")
        self.assertEqual(corner.frames[0].direction_offset,4)  # minimap tile index, not a turn
        self.assertEqual(corner.collision,("d01g02_a.mds",0))
        data=self.members("d01main_a")["d01g02_a.mds"].data
        arms={"E":(60,0),"W":(-60,0),"S":(0,60),"N":(0,-60)}
        expected={0:{"E","S"},1:{"W","S"},2:{"W","N"},3:{"E","N"}}
        for direction,sides in expected.items():
            tris=rc.parse_collision_mds(data,(0,0,0),rc.dc1_turn(direction+corner.collision[1]))
            got={side for side,(x,z) in arms.items() if any(abs(y)<1.0 for y in floor_ys(tris,x,z))}
            self.assertEqual(got,sides,direction)

    def test_d01inter2_entrance_stair_turn_two_attaches_to_room(self):
        room=rc.parse_room_cfg((self.dun/"d01inter2.cfg").read_bytes())
        members=self.members("d01inter2")
        self.assertEqual(room.ground_images,("d01i02.img",))
        stair=room.parts[1]
        self.assertEqual((stair.frames[0].name,stair.frames[0].offset,stair.frames[0].turn),("d01o01_0.mds",(0.0,0.0,320.0),2))
        hall=rc.parse_collision_mds(members["d01i01_a.mds"].data,room.parts[0].frames[0].offset,rc.part_collision_turn(room.parts[0]))
        hall_max_z=max(p[2] for t in hall for p in t)
        turned=rc.parse_collision_mds(members["d01o01_a.mds"].data,stair.frames[0].offset,rc.part_collision_turn(stair))
        unturned=rc.parse_collision_mds(members["d01o01_a.mds"].data,stair.frames[0].offset,0)
        # Turned by frame_turn 2 the stair spans back to the hall's door edge; read unturned (the old
        # field-2 reading) it floats 80 units away.
        self.assertLess(min(p[2] for t in turned for p in t),hall_max_z+1.0)
        self.assertGreater(min(p[2] for t in unturned for p in t),hall_max_z+40.0)

    def test_d01inter_r3_pack_is_byte_identical(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"d01inter"
            rc.convert(self.dun/"mpd_pack"/"d01inter.mpd",self.dun/"d01inter.cfg",out,"d01inter","d01i01_0.mds","d01i01_a.mds",
                       (0.0,0.0,0.0),(93.508744096,0.0,0.0),(249.356651,0.0,0.0),R3_SCALE)
            self.assertEqual(hashlib.sha256((out/"room.json").read_bytes()).hexdigest(),R3_D01INTER_SHA256)

    def test_g08_per_index_colours_modulate_diffuse(self):
        members=self.members("d01boss")
        data=members["d01g08_0.mds"].data
        textures=rc.decode_img(members["d01b01.img"].data)
        visuals,count=rc.parse_visual_mds(data,(0,0,0),0,textures)
        self.assertEqual(count,112)
        # Independent read of the first strip entry {v,n,uv,colour} of the first mesh.
        obj=next(o for o in rc.parse_mds(data) if o["mesh"]); mesh=obj["mesh"]
        colour_count,colour_ofs=struct.unpack_from("<ii",data,mesh+28)
        face_ofs=struct.unpack_from("<i",data,mesh+40)[0]; info_ofs=struct.unpack_from("<i",data,mesh+56)[0]
        self.assertGreater(colour_ofs,0)
        _,_,material=struct.unpack_from("<IIi",data,mesh+face_ofs+16)
        ci=struct.unpack_from("<i",data,mesh+face_ofs+28+12)[0]
        vc=struct.unpack_from("<4f",data,mesh+colour_ofs+16*ci)
        diffuse=struct.unpack_from("<4f",data,mesh+info_ofs+96*material)
        expected=[max(0.0,min(1.0,d*min(255,max(0,int(v*128+0.5)))/128)) for d,v in zip(diffuse,vc)]
        self.assertEqual([round(x,6) for x in visuals[0]["vertices"][0]["color"]],[round(x,6) for x in expected])
        bad=bytearray(data); struct.pack_into("<i",bad,mesh+28,0)
        with self.assertRaisesRegex(rc.ConvertError,"color section"):
            rc.parse_visual_mds(bytes(bad),(0,0,0),0,textures)

    def convert_room(self, name: str, temp: str) -> tuple[dict, dict]:
        markers=json.loads((ROOMS_DIR/f"{name}.markers.json").read_text(encoding="utf-8"))
        out=Path(temp)/name
        result=rc.convert(self.dun/"mpd_pack"/f"{name}.mpd",self.dun/f"{name}.cfg",out,name,"","",
                          (0,0,0),(0,0,0),(0,0,0),R3_SCALE,all_parts=True,markers=markers)
        return result,rc.validate_pack(out)

    def assert_markers_grounded(self, room: dict) -> None:
        for key in ("spawn","enemy_spawn","exit"):
            m=room[key]
            self.assertTrue(any(abs(y-m[1])<0.01 for y in floor_ys(room["collision"],m[0],m[2])),(key,m))

    def test_d01inter2_all_parts_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            result,room=self.convert_room("d01inter2",temp)
        self.assertEqual([(p["frames"],p["visual_turns"],p["collision_turn"]) for p in result["parts"]],
                         [(["d01i01_0.mds"],[0],0),(["d01o01_0.mds"],[2],2),(["d01o02_0.mds"],[0],0)])
        self.assertEqual(len(room["textures"]),12)
        self.assertEqual(len(room["collision"]),sum(p["collision_triangles"] for p in result["parts"]))
        # Authored in front of the entrance door and the closed gate (see the marker file notes).
        self.assertEqual([round(v,3) for v in result["markers_donor"]["spawn"]["ground"]],[0.0,0.0,295.0])
        self.assertEqual([round(v,3) for v in result["markers_donor"]["exit"]["ground"]],[0.0,0.0,-300.0])
        self.assertEqual(result["markers_donor"]["straight_route_support"][0],result["markers_donor"]["straight_route_support"][1])
        self.assert_markers_grounded(room)

    def test_d01boss_all_seven_parts_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            result,room=self.convert_room("d01boss",temp)
        parts=result["parts"]
        self.assertEqual([p["frames"][0] for p in parts],
                         ["d01g01_0.mds","d01g02_0.mds","d01g04_0.mds","d01g05_0.mds","d01g06_0.mds","d01g07_0.mds","d01g08_0.mds"])
        # Only g01 and g05 carry PT_COLS; the rest are visual-only (no collision model in DC1).
        self.assertEqual([p["collision"] is not None for p in parts],[True,False,False,True,False,False,False])
        self.assertTrue(all(p["visual_triangles"]>0 for p in parts))
        self.assertEqual(result["markers_donor"]["spawn"]["source"],"frame:event01_2")
        self.assertEqual([round(v,2) for v in result["markers_donor"]["spawn"]["donor"]],[0.0,1.0,-370.0])
        self.assertEqual([round(v,2) for v in result["markers_donor"]["exit"]["ground"]],[0.0,0.0,-620.0])
        self.assert_markers_grounded(room)

    def test_marker_without_ground_or_unique_frame_fails(self):
        members=self.members("d01inter2")
        room=rc.parse_room_cfg((self.dun/"d01inter2.cfg").read_bytes())
        collision=[]
        for part in room.parts:
            collision+=rc.parse_collision_mds(members[part.collision[0].casefold()].data,part.frames[0].offset,rc.part_collision_turn(part))
        ok={"spawn":{"donor":[0,0,0]},"enemy_spawn":{"donor":[0,0,0]},"exit":{"donor":[0,0,0]}}
        rc.resolve_markers(ok,list(room.parts),members,collision)
        # Frame markers resolve through the placed, turned PT_COLS model (itemdata.cpp:1254).
        frames=rc.resolve_markers({"spawn":{"frame":"in_2","part":"d01o01_0.mds"},"enemy_spawn":{"frame":"event02"},
                                   "exit":{"frame":"out_2","part":"d01o02_0.mds"}},list(room.parts),members,collision)
        self.assertEqual([[round(v,3) for v in frames[k]["donor"]] for k in ("spawn","enemy_spawn","exit")],
                         [[0.0,0.0,320.0],[0.0,0.0,220.0],[0.0,-2.0,-333.0]])
        for bad,pattern in (({**ok,"exit":{"donor":[0,0,5000]}},"no supported ground"),
                            ({**ok,"exit":{"frame":"no_such_frame"}},"matches 0"),
                            ({**ok,"exit":{}},"needs frame or donor")):
            with self.subTest(pattern=pattern), self.assertRaisesRegex(rc.ConvertError,pattern):
                rc.resolve_markers(bad,list(room.parts),members,collision)

    def test_r4_room_packs_are_byte_identical(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            for name,digest in R4_ROOM_SHA256.items():
                self.convert_room(name,temp)
                self.assertEqual(hashlib.sha256((Path(temp)/name/"room.json").read_bytes()).hexdigest(),digest,name)

    def test_d01boss_arena_sidecar(self):
        with tempfile.TemporaryDirectory() as temp:
            _,room=self.convert_room("d01boss",temp); pack=Path(temp)/"d01boss"
            doc,files=rc.build_arena(pack,self.dun/"mpd_pack"/"d01boss.mpd",self.dun/"d01boss.cfg")
            scale=room["units"]["scale"]
            tiles=doc["field_tiles"]["tiles"]
            # Twelve CDranMapField slots; mot<N>_a collision carries ground_kind N, the value a shot
            # hit decrements state[N-1] by (shot_utils.cpp:79-86).
            self.assertEqual([(t["slot"],t["ground_kind"],t["model"],t["collision_model"]) for t in tiles],
                             [(i,i+1,f"mot{i+1:02d}.chr",f"mot{i+1:02d}_a.mds") for i in range(12)])
            self.assertEqual([len(t["collision"]) for t in tiles],[40,45,43,40,52,45,37,37,37,45,40,48])
            for t in tiles:
                self.assertEqual((t["motion"]["frames"],t["motion"]["speed"],t["motion"]["done_at"]),([1,60],0.6,59.0))
                col=[p for tri in t["collision"] for p in tri]
                vis=[]
                for o in t["objects"]:
                    first=o["track"]["t"][0]+o["track"]["q"][0]; rest=o["rest"]["t"]+o["rest"]["q"]
                    self.assertLess(max(abs(a-b) for a,b in zip(first,rest)),1e-5)  # key 1 = MDS pose (float32 noise)
                    self.assertTrue(all(a[-1]==0.0 and a[0]==1.0 for a in o["track"]["alpha"].values()))      # fades out
                    r=rc.quat_matrix(o["rest"]["q"])
                    vis+=[[sum(r[i*4+j]*v["position"][j] for j in range(3))+o["rest"]["t"][i] for i in range(3)] for g in o["groups"] for v in g["vertices"]]
                for axis in (0,2):  # intact slabs cover exactly their collision footprint
                    self.assertAlmostEqual(min(p[axis] for p in vis),min(p[axis] for p in col),places=3)
                    self.assertAlmostEqual(max(p[axis] for p in vis),max(p[axis] for p in col),places=3)
            # Independent read of mot01.mot: obj286 (object 1) translation and rotation at frame 60.
            chr_pack=rc.parse_pack(self.members("d01boss")["mot01.chr"].data); mot=chr_pack["mot01.mot"].data
            pos=0; seen={}
            while True:
                frame,_,kind,_,count,more=struct.unpack_from("<iiiIII",mot,pos)
                if frame==1 and kind in (0,2): seen[kind]=struct.unpack_from("<4f",mot,pos+32+(count-1)*32+16)
                pos+=32+count*32
                if not more: break
            o=next(o for o in tiles[0]["objects"] if o["index"]==1)
            self.assertEqual([round(v,3) for v in o["track"]["t"][-1]],[round(v*scale,3) for v in seen[2][:3]])
            q=(-seen[0][0],seen[0][1],seen[0][2],seen[0][3]); q=q if q[0]>=0 else tuple(-v for v in q)
            self.assertEqual([round(v,4) for v in o["track"]["q"][-1]],[round(v,4) for v in q])
            # PT_FIRE: part offset + 10 x raw; each lands on a vertex of the room's torch geometry.
            self.assertEqual([[round(v,2) for v in f["donor"]] for f in doc["fires"]["emitters"]],
                             [[247.43,347.97,344.28],[345.64,347.8,276.37],[48.75,27.97,-372.63],[-49.55,27.8,-370.97],
                              [-28.43,28.4,-632.89],[30.06,28.4,-632.89]])
            verts=[v["position"] for g in room["visuals"] for v in g["vertices"]]
            for f in doc["fires"]["emitters"]:
                self.assertLess(min(math.dist(f["position"],v) for v in verts),1.0,f["id"])
            # Markers keep every PT_MARKER field; event01_2 is the switched-off auto-start for event 500.
            self.assertEqual([(m["name"],m["script"],m["item_use"],m["auto_start"],m["switch_on"],m["ext_mem"],[round(v,2) for v in m["donor"]])
                              for m in doc["markers"]],
                             [("event01_2",500,0,1,0,1,[0.0,1.0,-370.0]),("bosskey_2",400,1,0,1,0,[0.0,10.0,-399.0])])
            self.assertEqual([(c["model"],c["turn"],[(o["name"],len(o["triangles"])) for o in c["objects"]]) for c in doc["camera_collision"]],
                             [("d01g01_v.mds",0,[("d01g01_aa1",188)]),("d01g05_v.mds",0,[("obj785",130),("boss_door_v",8)])])
            # The straight spawn->enemy->exit line: void beside the walkway without the tiles, none with them.
            self.assertEqual(doc["floor_support"]["room_only"],[210,302])
            self.assertEqual(doc["floor_support"]["with_tiles"],[302,302])
            rc.write_arena(pack,doc,files)
            self.assertEqual(rc.validate_arena(pack)["room"],"d01boss")
            with self.assertRaisesRegex(rc.ConvertError,"already exists"): rc.write_arena(pack,doc,files)
            bad=json.loads((pack/"arena.json").read_text(encoding="utf-8")); bad["room_json_sha256"]="0"*64
            (pack/"arena.json").write_text(json.dumps(bad),encoding="utf-8")
            with self.assertRaisesRegex(rc.ConvertError,"different room.json"): rc.validate_arena(pack)


class ConsumerContractTests(unittest.TestCase):
    def write_pack(self, root: Path, material: int=0, position=(0.0,0.0,0.0)) -> None:
        texture_dir=root/"textures"; texture_dir.mkdir(parents=True,exist_ok=True)
        (texture_dir/"surface.png").write_bytes(rc.png_rgba(1,1,b"\xff\xff\xff\xff"))
        doc={"format":"ixion-room","version":1,"donor":{"game":"dc1","room":"fixture","sources":[{"path":"fixture.mpd","sha256":"0"*64}]},
             "units":{"scale":1.0},"spawn":[0,0,0],"enemy_spawn":[1,0,0],"exit":[2,0,0],
              "bounds":{"min":[-1,-1,-1],"max":[3,1,3]},"textures":[{"name":"surface","file":"textures/surface.png"}],
             "visuals":[{"material":material,"vertices":[{"position":list(position),"normal":[0,1,0],"uv":[0,0],"color":[1,1,1,1]} for _ in range(3)]}],
             "collision":[[[0,0,0],[1,0,0],[0,0,1]]]}
        (root/"room.json").write_text(json.dumps(doc),encoding="utf-8")

    def test_accepts_contract_triangle_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); self.write_pack(root)
            self.assertEqual(rc.validate_pack(root)["format"],"ixion-room")

    def test_rejects_bad_material_nonfinite_and_path_escape(self):
        for change,pattern in ((lambda d:d["visuals"][0].update(material=3),"material"),
                               (lambda d:d["visuals"][0]["vertices"][0]["position"].__setitem__(0,float("nan")),"position"),
                               (lambda d:d["textures"][0].update(file="../escape.png"),"unsafe")):
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); self.write_pack(root)
                d=json.loads((root/"room.json").read_text()); change(d)
                (root/"room.json").write_text(json.dumps(d),encoding="utf-8")
                with self.assertRaisesRegex(rc.ConvertError,pattern): rc.validate_pack(root)

    def test_rejects_truncated_png_header(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); self.write_pack(root)
            (root/"textures"/"surface.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            with self.assertRaisesRegex(rc.ConvertError,"PNG"):
                rc.validate_pack(root)

    def test_rejects_truncated_png_chunk(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); self.write_pack(root)
            (root/"textures"/"surface.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0\x10IHDR")
            with self.assertRaisesRegex(rc.ConvertError,"PNG"):
                rc.validate_pack(root)

    def test_rejects_malformed_json_roots_members_and_elements(self):
        mutations=(
            (lambda d: [],"root"),
            (lambda d: d.update(donor=[]),"donor"),
            (lambda d: d.update(units=[]),"units"),
            (lambda d: d.update(bounds=[]),"bounds"),
            (lambda d: d.update(textures=[[]]),"texture"),
            (lambda d: d.update(visuals=[[]]),"visual"),
            (lambda d: d["visuals"][0].update(vertices=[[]]*3),"visual vertex"),
            (lambda d: d["donor"].update(sources=[[]]),"donor source"),
        )
        for mutate,pattern in mutations:
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); self.write_pack(root); doc=json.loads((root/"room.json").read_text())
                changed=mutate(doc)
                if changed is not None: doc=changed
                (root/"room.json").write_text(json.dumps(doc),encoding="utf-8")
                with self.assertRaisesRegex(rc.ConvertError,pattern): rc.validate_pack(root)

    def test_validator_cli_returns_defined_error_for_malformed_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for malformed in ([],{"format":"ixion-room","version":1,"donor":[]}):
                (root/"room.json").write_text(json.dumps(malformed),encoding="utf-8")
                stderr=io.StringIO()
                with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as result:
                    rc.main(["validate",str(root)])
                self.assertEqual(result.exception.code,2)
                self.assertIn("room-converter:",stderr.getvalue())

    def test_rejects_native_incompatible_bounds_geometry_markers_and_degenerate_collision(self):
        cases=(
            (lambda d:d["bounds"].update(max=d["bounds"]["min"]),"bounds"),
            (lambda d:d.update(exit=[4,0,0]),"exit marker"),
            (lambda d:d["visuals"][0]["vertices"][0].update(position=[4,0,0]),"visual vertex"),
            (lambda d:d.update(collision=[[[0,0,0],[1,0,0],[2,0,0]]]),"degenerate"),
            (lambda d:d.update(collision=[[[0,0,0],[1,0,0],[0,0,4]]]),"collision vertex"),
        )
        for mutate,pattern in cases:
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); self.write_pack(root); d=json.loads((root/"room.json").read_text()); mutate(d)
                (root/"room.json").write_text(json.dumps(d),encoding="utf-8")
                with self.assertRaisesRegex(rc.ConvertError,pattern): rc.validate_pack(root)

    def test_rejects_values_that_collapse_under_native_float32(self):
        # Reviewer trigger (SOL final F5): both x bounds round to float32 1.0,
        # so the native consumer has no positive x extent and must reject.
        def collapsed_bounds(d):
            d["bounds"].update(min=[1.000000001,-1,-1],max=[1.000000002,1,3])
            for key in ("spawn","enemy_spawn","exit"): d[key]=[1.0000000015,0,0]
            d["visuals"][0]["vertices"]=[{"position":[1.0000000015,0,0],"normal":[1,0,0],"uv":[0,0],"color":[1,1,1,1]} for _ in range(3)]
            d["collision"]=[[[1.0000000015,0,0],[1.0000000015,1,0],[1.0000000015,0,1]]]
        def collapsed_triangle(d):
            d["bounds"].update(min=[999999,-1,-1],max=[1000001,1,1])
            for key in ("spawn","enemy_spawn","exit"): d[key]=[1000000,0,0]
            d["visuals"][0]["vertices"]=[{"position":[1000000,0,0],"normal":[0,1,0],"uv":[0,0],"color":[1,1,1,1]} for _ in range(3)]
            d["collision"]=[[[1000000,0,0],[1000000.01,0,0],[1000000,0,0.01]]]
        for mutate,pattern in ((collapsed_bounds,"bounds"),(collapsed_triangle,"degenerate")):
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); self.write_pack(root); d=json.loads((root/"room.json").read_text()); mutate(d)
                (root/"room.json").write_text(json.dumps(d),encoding="utf-8")
                with self.assertRaisesRegex(rc.ConvertError,pattern): rc.validate_pack(root)

    def test_rejects_native_numeric_limits_and_boolean_numbers(self):
        cases=(
            (lambda d:d["units"].update(scale=1001),"unit scale"),
            (lambda d:d.update(spawn=[True,0,0]),"spawn"),
            (lambda d:d.update(spawn=[10_000_001,0,0]),"spawn"),
            (lambda d:d.update(spawn=[10**1000,0,0]),"spawn"),
        )
        for mutate,pattern in cases:
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); self.write_pack(root); d=json.loads((root/"room.json").read_text()); mutate(d)
                (root/"room.json").write_text(json.dumps(d),encoding="utf-8")
                with self.assertRaisesRegex(rc.ConvertError,pattern): rc.validate_pack(root)


def make_stb(programs: list[list[tuple[int,int,int]]], strings: list[str]) -> bytes:
    """Minimal STB: 0x18 header, id table at 0x40, 16-byte funcdata, code at code_base, strings after
    the code (PUSHCONST type 3 operands are code_base-relative)."""
    id_off=0x40; fd_off=id_off+8*len(programs); code_base=fd_off+16*len(programs)
    code=bytearray(); starts=[]
    for ops in programs:
        starts.append(len(code))
        for op in ops: code.extend(struct.pack("<3I",*op))
    string_at={}
    for s in strings:
        string_at[s]=len(code); code.extend(s.encode("latin-1")+b"\0")
    blob=bytearray(code_base)
    struct.pack_into("<6I",blob,0,int.from_bytes(b"STB\0","little"),0,code_base,id_off,len(programs),0)
    for k,start in enumerate(starts):
        struct.pack_into("<2I",blob,id_off+8*k,100+k,fd_off+16*k)
        struct.pack_into("<4I",blob,fd_off+16*k,start,0,0,0)
    blob.extend(code)
    return bytes(blob),string_at


def i_(v): return (0x03,1,v & 0xFFFFFFFF)
def f_(v): return (0x03,2,struct.unpack("<I",struct.pack("<f",v))[0])
def ext(n): return (0x15,n,0)


class PropsTests(unittest.TestCase):
    def program(self, at: dict) -> list:
        # SET_DUNGEON_MAP('other',1); SET_IBOX(1,0,1,7); SET_DUNGEON_MAP('room',0);
        # SET_ATRA(4,0,5,2); SET_IBOX(-(9),0,-(8),195); SET_DUNGEON_MAP('later',2); SET_IBOX(0,0,0,9); RET
        s=lambda name:(0x03,3,at[name])
        neg=(0x0B,0,0)
        return [i_(1051),s("other"),i_(1),ext(3),
                i_(1059),f_(1),f_(0),f_(1),i_(7),ext(5),
                i_(1051),s("room"),i_(0),ext(3),
                i_(1058),f_(4),f_(0),f_(5),i_(2),ext(5),
                i_(1059),f_(9),neg,f_(0),f_(8),neg,i_(195),ext(5),
                i_(1051),s("later"),i_(2),ext(3),
                i_(1059),f_(0),f_(0),f_(0),i_(9),ext(5),(0x0F,0,0)]

    def stb(self) -> bytes:
        names=["other","room","later"]
        # String offsets depend on code length, which is fixed: lay out once with dummy offsets.
        _,at=make_stb([self.program({n:0 for n in names})],names)
        blob,_=make_stb([self.program(at)],names)
        return blob

    def test_decoder_folds_negation_and_reads_string_operands(self):
        calls=rc.decode_stb_ext_calls(self.stb())
        self.assertEqual([c.number for c in calls],[1051,1059,1051,1058,1059,1051,1059])
        self.assertEqual(calls[0].args[0],("s","other"))
        self.assertEqual(calls[4].args,(("f",-9.0),("f",0.0),("f",-8.0),("i",195)))

    def test_placements_belong_to_the_room_segment_only(self):
        got=rc.room_placements_from_stb(rc.decode_stb_ext_calls(self.stb()),"ROOM")
        self.assertEqual([(p["op"],p["position"],p["value"]) for p in got],
                         [("SET_ATRA",[4.0,0.0,5.0],2),("SET_IBOX",[-9.0,0.0,-8.0],195)])

    def test_rejects_bad_signature_and_out_of_range_program(self):
        blob=bytearray(self.stb())
        with self.assertRaisesRegex(rc.ConvertError,"signature"): rc.decode_stb_ext_calls(b"XXXX"+bytes(blob[4:]))
        struct.pack_into("<I",blob,0x40+4,len(blob)+64)
        with self.assertRaisesRegex(rc.ConvertError,"funcdata"): rc.decode_stb_ext_calls(bytes(blob))

    def write_room(self, root: Path, name: str, collision: list) -> None:
        texture_dir=root/"textures"; texture_dir.mkdir(parents=True,exist_ok=True)
        (texture_dir/"s.png").write_bytes(rc.png_rgba(1,1,b"\xff\xff\xff\xff"))
        doc={"format":"ixion-room","version":1,"donor":{"game":"dc1","room":name,"sources":[{"path":"x.mpd","sha256":"0"*64}]},
             "units":{"scale":2.0},"spawn":[0,0,0],"enemy_spawn":[1,0,0],"exit":[2,0,0],
             "bounds":{"min":[-40,-5,-40],"max":[40,5,40]},"textures":[{"name":"s","file":"textures/s.png"}],
             "visuals":[{"material":0,"vertices":[{"position":[0,0,0],"normal":[0,1,0],"uv":[0,0],"color":[1,1,1,1]}]*3}],
             "collision":collision}
        (root/"room.json").write_text(json.dumps(doc),encoding="utf-8")

    def test_build_props_scales_grounds_and_refuses_unsupported_points(self):
        floor=[[[-40,1,-40],[40,1,-40],[-40,1,40]],[[40,1,-40],[40,1,40],[-40,1,40]]]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"pack"; self.write_room(root,"room",floor)
            stb=Path(temp)/"event.stb"; stb.write_bytes(self.stb())
            doc=rc.build_props(root,stb)
            box=next(p for p in doc["props"] if p["kind"]=="treasure_box")
            # donor (-9,0,-8) x scale 2, dropped onto the floor at y=1 (within the +2 donor-unit rise).
            self.assertEqual([round(v,6) for v in box["position"]],[-18.0,1.0,-16.0])
            self.assertEqual(box["contents"],{"dc1_item":195,"role":"gate_key","count":1})
            self.assertEqual(doc["format"],"ixion-room-props")
            rc.write_props(root,doc)
            with self.assertRaisesRegex(rc.ConvertError,"already exists"): rc.write_props(root,doc)
            # A floor only under +x: the -x chest has no supported ground.
            half=[[[0,1,-40],[40,1,-40],[0,1,40]],[[40,1,-40],[40,1,40],[0,1,40]]]
            other=Path(temp)/"half"; self.write_room(other,"room",half)
            with self.assertRaisesRegex(rc.ConvertError,"no supported ground"): rc.build_props(other,stb)

    def test_real_d01inter_chest_and_atla_from_event_stb(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA for the real event.stb")
        blob=(Path(data_root)/"dun"/"script"/"d01"/"event.stb").read_bytes()
        got=rc.room_placements_from_stb(rc.decode_stb_ext_calls(blob),"d01inter")
        # event.stb program 100: SET_ATRA(157,0,130,5) at +0x4e0, SET_IBOX(-93,0,-318,195) at +0x54c.
        self.assertEqual([(p["op"],p["program"],p["offset"],p["position"],p["value"]) for p in got],
                         [("SET_ATRA",100,0x4e0,[157.0,0.0,130.0],5),("SET_IBOX",100,0x54c,[-93.0,0.0,-318.0],195)])
        self.assertEqual(rc.room_placements_from_stb(rc.decode_stb_ext_calls(blob),"d01inter2"),[])
        deferred=rc.cfg_deferred_objects((Path(data_root)/"dun"/"d01inter.cfg").read_bytes())
        self.assertEqual(sum(d["kind"]=="torch" for d in deferred),10)
        self.assertEqual([d["frame"] for d in deferred if d["kind"]=="gate_marker"],["out_2","gatekey_2"])



def make_mot(drivers: list[tuple[int,int,int,list[tuple[int,tuple[float,float,float,float]]]]]) -> bytes:
    """Mot_File_List chain: 32-byte header (frame, target, type, unk, key_count, more) + 32-byte keys
    (frame, 12 unused bytes, value[4])."""
    out=bytearray()
    for i,(frame,target,kind,keys) in enumerate(drivers):
        out.extend(struct.pack("<iiiIII8x",frame,target,kind,32,len(keys),int(i+1<len(drivers))))
        for kf,value in keys: out.extend(struct.pack("<I12x4f",kf,*value))
    return bytes(out)


def dc1_quat_to_mat_native(q: tuple[float,...]) -> tuple[float,...]:
    """Independent transcription of frame.cpp QuatToMat into libvu0's column-major [col][row] layout."""
    x2,y2,z2=q[1]+q[1],q[2]+q[2],q[3]+q[3]
    xx,xy,xz=q[1]*x2,q[1]*y2,q[1]*z2; yy,yz,zz=q[2]*y2,q[2]*z2,q[3]*z2; wx,wy,wz=q[0]*x2,q[0]*y2,q[0]*z2
    m=[[0.0]*4 for _ in range(4)]
    m[0][0]=1-(yy+zz); m[1][0]=xy-wz; m[2][0]=xz+wy
    m[0][1]=xy+wz; m[1][1]=1-(xx+zz); m[2][1]=yz-wx
    m[0][2]=xz-wy; m[1][2]=yz+wx; m[2][2]=1-(xx+yy); m[3][3]=1.0
    return tuple(m[c][r] for c in range(4) for r in range(4))


class ArenaTests(unittest.TestCase):
    CFG=b"""SET_PATH "dun/d99/floor_boss/"
FIRE_IMG "fire.img"
GRD_IMG "r.img",1
DRANS_PARTS "mot01.chr"
DRANS_PARTS "mot02.chr"
DRANS_COLS "mot01_a.mds"
DRANS_COLS "mot02_a.mds"
DEF_PATS
 PT_BASE "a_0.mds" ,0 ,0,0,-64, 0
 PT_COLS "a_a.mds" ,0
  PT_MARKER "ev_2", 20,500,OFF,ON,OFF,ON  // boss start
 PT_CAM "a_v.mds" ,1
 PT_FIRE 1, 2, 3
 PT_FIRE 1, 2, 3
 PT_FIRE 1, 2, 3
 PT_FIRE 1, 2, 3
 PT_FIRE 1, 2, 3
 PT_FIRE 1, 2, 3
 PT_FIRE 9, 9, 9
DEF_ENDS
DEF_PATS
 PT_BASE "b_0.mds" ,0 ,0,0,0, 0
  PT_FIRE -1.5, .5, 2
DEF_ENDS
"""

    def test_cfg_pairs_field_slots_and_reads_full_marker_records(self):
        arena=rc.parse_arena_cfg(self.CFG)
        # DRANS_PARTS/DRANS_COLS fill CDranMapField slots in file order (dranmapfield.cpp:13-57).
        self.assertEqual([m for m,_ in arena.field_models],["mot01.chr","mot02.chr"])
        self.assertEqual([c for c,_ in arena.field_collisions],["mot01_a.mds","mot02_a.mds"])
        self.assertEqual(arena.fire_img,("fire.img",2))
        a,b=arena.parts
        self.assertEqual(a.markers,(rc.ArenaMarker("ev_2",20.0,500,0,1,0,1,11),))
        self.assertEqual(a.cameras,(("a_v.mds",1,12),))
        # Six fires per part; the seventh is dropped as itemdata.cpp:1404 drops it.
        self.assertEqual(len(a.fires),6); self.assertEqual(a.dropped_fires,(19,))
        self.assertEqual(b.fires,(((-1.5,0.5,2.0),23),))
        self.assertEqual(len(rc.parse_room_cfg(self.CFG).parts),2)
        too_many=self.CFG.replace(b'DRANS_PARTS "mot02.chr"\n',b'DRANS_PARTS "m.chr"\n'*12)
        with self.assertRaisesRegex(rc.ConvertError,"twelve"): rc.parse_arena_cfg(too_many)
        with self.assertRaisesRegex(rc.ConvertError,"outside DEF_PATS"): rc.parse_arena_cfg(b'PT_CAM "x.mds",0\n')

    def test_quaternion_keys_follow_dc1_quat_to_mat(self):
        for raw in ((0.9731,-0.1891,-0.0251,-0.1292),(0.2,0.5,-0.7,0.4583),(1.0,0.0,0.0,0.0)):
            n=math.sqrt(sum(v*v for v in raw)); raw=tuple(v/n for v in raw)
            # MotionProc negates element 0 before QuatToMat (gameutil.cpp:228-235).
            native=dc1_quat_to_mat_native((-raw[0],raw[1],raw[2],raw[3]))
            standard=tuple(native[c*4+r] for r in range(4) for c in range(4))
            got=rc.quat_matrix(rc.dc1_quaternion(raw))
            self.assertTrue(all(abs(x-y)<1e-6 for x,y in zip(got,standard)),raw)
            back=rc.matrix_quat(got); self.assertTrue(all(abs(x-y)<1e-6 for x,y in zip(rc.quat_matrix(back),standard)))

    def test_motion_pose_lerps_slerps_fades_and_composes_parents(self):
        ident=(1,0,0,0, 0,1,0,0, 0,0,1,0)
        root=ident+(10,0,0,1)        # native layout: translation is stored vector 3
        child=ident+(1,2,3,1)
        objects=rc.parse_mds(make_mds_graph([root,child],[-1,0]))
        h=math.sqrt(0.5)
        mot=make_mot([(1,0,rc.MOT_ROTATION,[(1,(-1.0,0,0,0)),(3,(-h,0,h,0))]),
                      (1,0,rc.MOT_TRANSLATION,[(1,(1,2,3,0)),(3,(1,-8,3,0))]),
                      (1,1,rc.MOT_MATERIAL_ALPHA,[(1,(0,0,0,0)),(2,(0.5,0,0,0)),(3,(1,0,0,0))])])
        drivers=rc.parse_dc1_motion(mot,len(objects))
        self.assertEqual([(d.frame,d.kind,len(d.keys)) for d in drivers],[(1,0,2),(1,2,2),(1,40,3)])
        w1,a1=rc.pose_motion(objects,drivers,1.0)
        self.assertEqual([round(w1[1][k],6) for k in (3,7,11)],[11.0,2.0,3.0])   # parent translation composed
        self.assertEqual(a1,{(1,1):1.0})
        w2,a2=rc.pose_motion(objects,drivers,2.0)
        self.assertEqual([round(w2[1][k],6) for k in (3,7,11)],[11.0,-3.0,3.0])  # lerp half way
        self.assertAlmostEqual(a2[(1,1)],0.5)                                     # alpha = 1 - value
        # Half of a 90-degree turn about y: 45 degrees (effective quats (1,0,0,0) -> (h,0,h,0)).
        c=math.cos(math.radians(45)); s=math.sin(math.radians(45))
        self.assertTrue(all(abs(w2[1][i]-e)<1e-6 for i,e in zip((0,2,8,10),(c,s,-s,c))))
        w3,a3=rc.pose_motion(objects,drivers,3.0)
        self.assertEqual(a3[(1,1)],0.0)
        w9,_=rc.pose_motion(objects,drivers,9.0)                                  # past the last key: holds
        self.assertEqual([round(w9[1][k],6) for k in (3,7,11)],[11.0,-8.0,3.0])
        with self.assertRaisesRegex(rc.ConvertError,"drives object"): rc.parse_dc1_motion(make_mot([(5,0,0,[(1,(1,0,0,0))])]),2)
        with self.assertRaisesRegex(rc.ConvertError,"escape"): rc.parse_dc1_motion(mot[:-8],2)
        with self.assertRaisesRegex(rc.ConvertError,"not ascending"):
            rc.parse_dc1_motion(make_mot([(1,0,2,[(3,(0,0,0,0)),(1,(0,0,0,0))])]),2)

    def test_fire_placement_matches_the_part_turn(self):
        # DrawFireFreeStyle: part offset + 10 x raw, turned by 90*(4-frame_turn) (dungeonmap.cpp:885-911).
        self.assertEqual(rc.fire_donor_position((0.0,0.0,-640.0),0,(1.0,2.0,3.0)),(10.0,20.0,-610.0))
        raw=(1.0,0.5,0.25)
        for turn in range(4):
            placed=rc.world_matrices([{"parent":-1,"matrix":rc._IDENTITY}],(5.0,0.0,7.0),rc.dc1_turn(turn))[0]
            want=rc.transform_point(placed,tuple(10*v for v in raw))
            got=rc.fire_donor_position((5.0,0.0,7.0),turn,raw)
            self.assertTrue(all(abs(x-y)<1e-9 for x,y in zip(got,want)),turn)
        # Retail quirk: the fire code sees turn 4 as no turn, while dc1_turn(4) is a quarter turn.
        self.assertEqual(rc.fire_donor_position((0.0,0.0,0.0),4,(1.0,0.0,0.0)),(10.0,0.0,0.0))

    def test_rgba32_img_entry_decodes_linearly_with_doubled_alpha(self):
        pixels=bytes((10,20,30,64, 40,50,60,128, 70,80,90,0, 1,2,3,100))
        tim=bytearray(16+48); tim[:4]=b"TIM2"
        struct.pack_into("<I",tim,16+8,len(pixels)); struct.pack_into("<HH",tim,16+12,48,0)
        tim[16+17]=1; tim[16+18]=0; tim[16+19]=3; struct.pack_into("<HH",tim,36,2,2)
        img=bytearray(16+48); img[:4]=b"IM2\0"; struct.pack_into("<I",img,4,1)
        img[16:16+5]=b"glow\0"; struct.pack_into("<I",img,16+32,len(img))
        img=bytes(img)+bytes(tim)+pixels
        got=rc.decode_img_rgba(img,rgba32=True)["glow"]
        self.assertEqual(got,(bytes((10,20,30,128, 40,50,60,255, 70,80,90,0, 1,2,3,200)),2,2))
        with self.assertRaisesRegex(rc.ConvertError,"unsupported texture layout"): rc.decode_img(img)


def make_floor_dump(cells: dict[tuple[int,int],tuple[int,int,int]], stair_down: tuple[int,int], stair_up: tuple[int,int]) -> dict:
    """A randfloor_dump object from {(col,row): (parts_no, direction, content)}."""
    dump={"format":rc.FLOOR_FORMAT,"version":1,"dungeon":0,"floor":1,"cur_floor":0,"map_seed":1,"srand_argument":1,
          "grid":{"width":20,"height":20,"playable":16,"cell_size":160},"gate_key_no":195,"room_num":0,"rooms":[],
          "chests":[],"atla":[],"trap_circles":[],
          "parts_no":[-1]*400,"direction":[0]*400,"content":[0]*400,"room_links":[0]*400,
          "stair_down":{"col":stair_down[0],"row":stair_down[1],"direction":0,"count":1},
          "stair_up":{"col":stair_up[0],"row":stair_up[1],"direction":2,"count":1},"ura_entrance":None}
    for (col,row),(part,direction,content) in cells.items():
        i=row*20+col; dump["parts_no"][i]=part; dump["direction"][i]=direction; dump["content"][i]=content
    return dump


def stair_corridor_dump() -> dict:
    """The smallest floor setStair can build: a corridor cell with the stair in above and the stair out below."""
    return make_floor_dump({(1,1):(rc.PART_STAIR_DOWN,0,rc.BUILD_STAIR_DOWN),(1,2):(2,0,rc.BUILD_CORRIDOR),
                            (1,3):(rc.PART_STAIR_UP,2,rc.BUILD_STAIR_UP)},(1,1),(1,3))


class FloorDumpTests(unittest.TestCase):
    def test_accepts_a_wellformed_dump_and_rejects_malformed_ones(self):
        rc.load_floor_dump(stair_corridor_dump())
        def mutate(f):
            d=stair_corridor_dump(); f(d); return d
        cases=(mutate(lambda d:d.update(format="other")),
               mutate(lambda d:d.update(version=2)),
               mutate(lambda d:d["grid"].update(cell_size=100)),
               mutate(lambda d:d["parts_no"].pop()),
               mutate(lambda d:d["direction"].__setitem__(5,4)),
               mutate(lambda d:d["parts_no"].__setitem__(5,True)),
               mutate(lambda d:d["stair_down"].update(col=2)),     # cell (2,1) holds no stair
               mutate(lambda d:d.pop("map_seed")),
               mutate(lambda d:d.pop("stair_up")))
        for i,bad in enumerate(cases):
            with self.subTest(case=i), self.assertRaises(rc.ConvertError):
                rc.load_floor_dump(bad)

    def test_placements_keep_the_playable_area_and_check_the_kit_size(self):
        d=stair_corridor_dump()
        d["parts_no"][5*20+19]=rc.PART_URA_ROAD; d["parts_no"][17*20+3]=0   # back-floor road, off-grid cell
        rc.load_floor_dump(d)
        got=rc.floor_placements(d,60)
        self.assertEqual([(c["col"],c["row"]) for c in got],[(1,1),(1,2),(1,3)])
        self.assertEqual(len(rc.floor_placements(d,60,include_under_road=True)),5)
        with self.assertRaisesRegex(rc.ConvertError,"kit has 2"):
            rc.floor_placements(d,2)

    def test_grid_path_follows_corridors_and_needs_doors_into_rooms(self):
        d=stair_corridor_dump()
        self.assertEqual(rc.floor_grid_path(d,(1,1),(1,3)),[(1,1),(1,2),(1,3)])
        # A bare room cell beside the corridor is walled off from it; a door cell joins them.
        d=make_floor_dump({(1,1):(30,0,rc.BUILD_STAIR_DOWN),(1,2):(0,0,rc.BUILD_CORRIDOR),(2,2):(17,0,rc.BUILD_ROOM),
                           (3,2):(17,0,rc.BUILD_ROOM),(1,3):(31,2,rc.BUILD_STAIR_UP)},(1,1),(1,3))
        self.assertEqual(rc.floor_grid_path(d,(1,1),(3,2)) is None,True)
        d["content"][2*20+2]=rc.BUILD_ROOM|rc.BUILD_DOOR
        self.assertEqual(rc.floor_grid_path(d,(1,1),(3,2)),[(1,1),(1,2),(2,2),(3,2)])
        # A dividing wall blocks, a dividing door does not.
        d["content"][2*20+2]=rc.BUILD_DIVIDING_WALL; self.assertIsNone(rc.floor_grid_path(d,(1,1),(3,2)))
        d["content"][2*20+2]=rc.BUILD_DIVIDING_DOOR|rc.BUILD_ROOM|rc.BUILD_DOOR
        self.assertIsNotNone(rc.floor_grid_path(d,(1,1),(3,2)))

    def test_ascii_marks_stairs_and_path(self):
        d=stair_corridor_dump()
        text=rc.floor_ascii(d,rc.floor_grid_path(d,(1,1),(1,3)))
        self.assertEqual(text.splitlines()[1:4],[" S"," *"," X"])



def monster_entry(slot: int, model: str, no: int, x: float, z: float, key: int=0, lift: float=0.0) -> dict:
    return {"slot":slot,"monster_no":no,"model":model,"x":x,"y":lift,"z":z,"lift":lift,"drops_items":1,"attempts":1,"holds_gate_key":key}


def with_monsters(dump: dict, entries: list[dict]) -> dict:
    holder=next((e["slot"] for e in entries if e["holds_gate_key"]),None)
    dump["monsters"]={"source":"CMonstorUnit::ArrangementPos(&MainDungeonMap, 15, -1, 0)","available":True,"requested":15,
                      "model_nos":sorted({e["monster_no"] for e in entries}),"list":entries,"placed":len(entries)}
    dump["gate_key"]={"item_no":195,"holder_slot":holder,"rule":"SetKey"}
    return dump


class FloorMonsterDataTests(unittest.TestCase):
    def test_dump_without_monsters_is_still_accepted_and_malformed_blocks_are_not(self):
        rc.load_floor_dump(stair_corridor_dump())
        good=with_monsters(stair_corridor_dump(),[monster_entry(0,"e03a",1,160,320,key=1),monster_entry(1,"e60a",52,160,400,lift=21.0)])
        rc.load_floor_dump(good)
        def bad(f):
            d=with_monsters(stair_corridor_dump(),[monster_entry(0,"e03a",1,160,320,key=1),monster_entry(1,"e60a",52,160,400)]); f(d); return d
        cases=(bad(lambda d:d["monsters"].pop("list")),
               bad(lambda d:d["monsters"]["list"].append(monster_entry(0,"e06a",3,10,10))),          # repeated slot
               bad(lambda d:d["monsters"]["list"].append(monster_entry(16,"e06a",3,10,10))),         # slot out of range
               bad(lambda d:d["monsters"]["list"].append(monster_entry(2,"e06a",3,9999,10))),        # outside the grid
               bad(lambda d:d["monsters"]["list"][0].update(x=float("nan"))),
               bad(lambda d:d["monsters"]["list"][0].update(model=7)),
               bad(lambda d:d["monsters"]["list"][1].update(holds_gate_key=1)),                     # two holders
               bad(lambda d:d["gate_key"].update(holder_slot=1)),                                   # holder mismatch
               bad(lambda d:d.update(monsters=[])))
        for i,c in enumerate(cases):
            with self.subTest(case=i), self.assertRaises(rc.ConvertError):
                rc.load_floor_dump(c)

    def test_chest_mapping_names_its_relation_and_stays_inside_dc2_items(self):
        self.assertEqual(rc.chest_mapping(233)["dc2_item"],305)
        self.assertEqual(rc.chest_mapping(233)["relation"],"equivalent")
        self.assertEqual(rc.chest_mapping(147)["relation"],"stand-in")
        self.assertEqual(rc.chest_mapping(195)["relation"],"built-in")
        fallback=rc.chest_mapping(300)
        self.assertEqual(fallback["dc2_item"],268); self.assertTrue(fallback["relation"].startswith("stand-in (fallback"))
        for dc1,(dc2,relation,_,_) in rc.CHEST_ITEMS.items():
            self.assertTrue(1<=dc2<=rc.DC2_ITEM_MAX,dc1); self.assertIn(relation,("equivalent","stand-in","built-in"))

    def test_chest_item_numbers_exist_in_the_dc2_item_table_with_the_claimed_names(self):
        data=os.environ.get("IXION_DC2_DATA")
        if not data: self.skipTest("set IXION_DC2_DATA")
        cfg=Path(data)/"menu"/"cfg7"
        names={int(m.group(1)):m.group(2) for m in re.finditer(r'MES_SYS (\d+),"([^"]*)";',(cfg/"comdatmes1.cfg").read_text(encoding="latin-1"))}
        rows={}
        for m in re.finditer(r'COM (\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),"[^"]*",(\d+);',(cfg/"comdat.cfg").read_text(encoding="latin-1")):
            rows[int(m.group(1))]=int(m.group(9))
        for dc1,(dc2,_,_,dc2_name) in rc.CHEST_ITEMS.items():
            with self.subTest(dc1=dc1):
                self.assertIn(dc2,rows); self.assertEqual(names.get(rows[dc2]),dc2_name)
        self.assertIn(rc.CHEST_FALLBACK[0],rows); self.assertEqual(names.get(rows[rc.CHEST_FALLBACK[0]]),rc.CHEST_FALLBACK[3])

    def test_gate_key_data_carries_dc1s_holder_and_no_runtime_decision(self):
        d=with_monsters(stair_corridor_dump(),[monster_entry(0,"e03a",1,160,320),monster_entry(1,"e60a",52,160,400,key=1,lift=21.0)])
        sidecar_like=rc.floor_monsters(d,rc.GroundIndex([[[0,0,0],[2000,0,0],[0,0,2000]],[[2000,0,0],[2000,0,2000],[0,0,2000]]]),1.5)
        key=rc.floor_gate_key(d,sidecar_like)
        self.assertEqual((key["item_no"],key["holder_slot"],key["holder"]["model"]),(195,1,"e60a"))
        self.assertFalse(key["holder_roster_donor"]); self.assertIn("runtime policy required",key["runtime_use"])
        self.assertEqual(sidecar_like["roster"]["donor_list"],"e03a")
        self.assertEqual(sidecar_like["roster"]["unsupported_models"],["e60a"])
        self.assertEqual(sidecar_like["list"][0]["output"][0],160*1.5)

    def test_props_carry_chests_and_monsters_and_defer_ungrounded_ones(self):
        index=rc.GroundIndex([[[0,0,0],[200,0,0],[0,0,200]],[[200,0,0],[200,0,200],[0,0,200]]])
        d=with_monsters(stair_corridor_dump(),[monster_entry(0,"e03a",1,60,60,key=1),monster_entry(1,"e06a",3,900,900)])
        mons=rc.floor_monsters(d,index,2.0)
        chests=[{"x":50.0,"y":0.0,"z":60.0,"item_no":233,"kind":1,"trap_no":0,"output":[100.0,0.0,120.0],"grounded":True,"dc2":rc.chest_mapping(233)},
                {"x":900.0,"y":0.0,"z":900.0,"item_no":147,"kind":0,"trap_no":3,"output":[1800.0,0.0,1800.0],"grounded":False,"dc2":rc.chest_mapping(147)}]
        props=rc.floor_props("room-x","ab"*32,2.0,[],chests,mons)
        self.assertEqual([p["kind"] for p in props["props"]],["treasure_box","monster_spawn"])
        # Spawn priority: nearest the entrance first, then DC1 slot order.
        near=with_monsters(stair_corridor_dump(),[monster_entry(0,"e03a",1,150,150),monster_entry(1,"e06a",3,60,60),monster_entry(2,"e03a",1,60,60)])
        order=rc.floor_props("room-x","ab"*32,2.0,[],[],rc.floor_monsters(near,index,2.0),(0.0,0.0,0.0))["props"]
        self.assertEqual([p["donor"]["slot"] for p in order],[1,2,0])
        box=props["props"][0]
        self.assertEqual((box["contents"]["dc1_item"],box["contents"]["dc2_item"],box["contents"]["mapping"]),(233,305,"equivalent"))
        self.assertEqual(box["position"],[100.0,0.0,120.0])
        spawn=props["props"][1]
        self.assertEqual((spawn["donor"]["model"],spawn["donor"]["slot"],spawn["position"]),("e03a",0,[120.0,0.0,120.0]))
        self.assertEqual(sorted(x["kind"] for x in props["deferred"]),["monster_spawn","treasure_box"])
        self.assertEqual(props["native_boxes"],"park")


class FloorWalkTests(unittest.TestCase):
    def strip(self, x0: float, x1: float, y: float=0.0):
        """Two up-facing triangles covering x0..x1, z -10..10 at height y."""
        return [[[x0,y,-10],[x1,y,-10],[x1,y,10]],[[x0,y,-10],[x1,y,10],[x0,y,10]]]

    def test_walk_reports_a_gap_in_the_floor_as_void(self):
        solid=rc.GroundIndex(self.strip(0,100))
        r=rc.walk_support(solid,[(1,0,0),(99,0,0)],4.0,6.0,12.0)
        self.assertEqual((r["void"],r["first_void"]),(0,None))
        gap=rc.GroundIndex(self.strip(0,40)+self.strip(60,100))
        r=rc.walk_support(gap,[(1,0,0),(99,0,0)],4.0,6.0,12.0)
        self.assertGreater(r["void"],0); self.assertTrue(38<=r["first_void"][0]<=46)
        self.assertEqual(r["longest_void_run"],r["void"])

    def test_walk_follows_steps_within_rise_and_drop_but_not_a_cliff(self):
        index=rc.GroundIndex(self.strip(0,50,0)+self.strip(50,100,5)+self.strip(100,150,40))
        r=rc.walk_support(index,[(1,0,0),(149,0,0)],4.0,6.0,12.0)
        self.assertGreater(r["void"],0)   # the 35 unit jump at x=100 is a cliff, not a step
        self.assertTrue(98<=r["first_void"][0]<=104)

    def test_walls_are_found_by_segment_crossing(self):
        wall=[[[50,0,-10],[50,30,-10],[50,30,10]],[[50,0,-10],[50,30,10],[50,0,10]]]
        walls=rc.WallIndex(wall+self.strip(0,100))     # the floor strip is walkable and is ignored
        self.assertGreaterEqual(walls.crosses((0,5,0),(100,5,0)),1)
        self.assertEqual(walls.crosses((0,5,0),(40,5,0)),0)
        self.assertEqual(walls.crosses((0,45,0),(100,45,0)),0)    # over the top
        track=[(x,0.0,0.0) for x in range(0,101,4)]
        self.assertGreaterEqual(rc.wall_crossings(walls,track)["wall_crossings"],1)
        self.assertEqual(rc.wall_crossings(walls,track[:10])["wall_crossings"],0)


class FloorRealKitTests(unittest.TestCase):
    SCALE=1.5584790682688

    def setUp(self):
        data_root=os.environ.get("IXION_DC1_DATA")
        if not data_root: self.skipTest("set IXION_DC1_DATA for random-floor kit qualification")
        self.dun=Path(data_root)/"dun"
        self.pack=self.dun/"mpd_pack"/"d01main_a.mpd"; self.cfg=self.dun/"d01main_a.cfg"

    def convert(self, dump: dict, temp: str, name: str="out") -> tuple[dict,Path]:
        dump_path=Path(temp)/f"{name}.dump.json"; dump_path.write_text(json.dumps(dump),encoding="utf-8")
        out=Path(temp)/name
        return rc.convert_floor(self.pack,self.cfg,dump_path,out,self.SCALE),out

    def test_three_cell_floor_places_kit_at_cell_offsets_and_walks_clean(self):
        with tempfile.TemporaryDirectory() as temp:
            result,out=self.convert(stair_corridor_dump(),temp)
            self.assertEqual(result["cells"],3); self.assertEqual(result["parts_used"],[2,30,31])
            self.assertEqual((result["walk"]["void"],result["walk"]["wall_crossings"]),(0,0))
            self.assertEqual(rc.validate_pack(out)["format"],"ixion-room")
            doc=json.loads((out/"room.json").read_text(encoding="utf-8"))
            s=self.SCALE
            # Spawn: in front of the entrance stair's gate wall, on the cell column x=160, between the stair
            # cell (row 1, z=160) and the corridor cell (row 2, z=320). Exit mirrors it below the corridor.
            self.assertAlmostEqual(doc["spawn"][0],160*s,delta=0.01)
            self.assertAlmostEqual(doc["spawn"][2],(160+40)*s,delta=0.01)
            self.assertAlmostEqual(doc["exit"][2],(480-40)*s,delta=0.01)
            self.assertLess(abs(doc["spawn"][1]),1.0)
            # Geometry is placed per cell: collision lies inside the three cells' footprint (+-80 about
            # each centre, stair parts reach a few units past it), nothing sits at the origin cell.
            xs=[p[0]/s for t in doc["collision"] for p in t]; zs=[p[2]/s for t in doc["collision"] for p in t]
            self.assertTrue(min(xs)>=160-90 and max(xs)<=160+90)
            self.assertTrue(160-10<=min(zs) and max(zs)<=480+90)
            side=json.loads((out/"floor.json").read_text(encoding="utf-8"))
            self.assertEqual((side["entrance"]["col"],side["entrance"]["row"]),(1,1))
            self.assertEqual((side["exit"]["col"],side["exit"]["row"]),(1,3))
            self.assertEqual(side["path_cells"],[[1,1],[1,2],[1,3]])

    def test_floor_pack_writes_props_and_sidecar_monsters(self):
        entries=[monster_entry(0,"e03a",1,160,330,key=1),monster_entry(1,"e06a",3,160,400),monster_entry(2,"e60a",52,160,470,lift=21.0),
                 monster_entry(3,"e03a",1,2300,2300)]                                   # the last one has no ground
        d=with_monsters(stair_corridor_dump(),entries)
        d["chests"]=[{"x":160.0,"y":0.0,"z":340.0,"item_no":233,"kind":1,"trap_no":0},{"x":2200.0,"y":0.0,"z":2200.0,"item_no":234,"kind":1,"trap_no":0}]
        with tempfile.TemporaryDirectory() as temp:
            result,out=self.convert(d,temp)
            side=json.loads((out/"floor.json").read_text(encoding="utf-8"))
            props=json.loads((out/"props.json").read_text(encoding="utf-8"))
            room_bytes=(out/"room.json").read_bytes()
            self.assertEqual(props["room_json_sha256"],hashlib.sha256(room_bytes).hexdigest())
            self.assertEqual(props["room"],json.loads(room_bytes)["donor"]["room"])
            self.assertEqual(side["monsters"]["placed"],4); self.assertEqual(side["monsters"]["roster"]["donor_list"],"e03a,e06a")
            self.assertEqual([m["grounded"] for m in side["monsters"]["list"]],[True,True,True,False])
            self.assertEqual(side["gate_key"]["holder_slot"],0); self.assertEqual(side["gate_key"]["holder"]["model"],"e03a")
            kinds=[p["kind"] for p in props["props"]]
            self.assertEqual(kinds.count("monster_spawn"),3); self.assertEqual(kinds.count("treasure_box"),1)
            chest=next(p for p in props["props"] if p["kind"]=="treasure_box")
            self.assertEqual(chest["contents"]["dc2_item"],305)
            self.assertAlmostEqual(chest["position"][0],160*self.SCALE,delta=0.01)
            self.assertEqual(result["props"],4); self.assertEqual(result["donor_list"],"e03a,e06a")
            self.assertEqual(len(props["deferred"]),2)           # the ungrounded monster and chest
            # Every prop stays inside the pack's own bounds, as the DC2 adapter requires.
            doc=json.loads(room_bytes)
            for p in props["props"]:
                for a in range(3): self.assertTrue(doc["bounds"]["min"][a]<=p["position"][a]<=doc["bounds"]["max"][a],p["id"])
            self.assertEqual(rc.validate_pack(out)["format"],"ixion-room")

    def test_centre_marker_is_behind_the_stair_gate_wall(self):
        # Negative control for the wall check: the old marker on the stair cell centre must cross a wall.
        with tempfile.TemporaryDirectory() as temp:
            result,out=self.convert(stair_corridor_dump(),temp)
            doc=json.loads((out/"room.json").read_text(encoding="utf-8")); s=self.SCALE
            tris=[[[c/s for c in p] for p in t] for t in doc["collision"]]
            walls=rc.WallIndex(tris); index=rc.GroundIndex(tris)
            centre=(160.0,floor_h(index,160.0,160.0),160.0); front=(160.0,floor_h(index,160.0,200.0),200.0)
            self.assertGreaterEqual(walls.crosses((centre[0],centre[1]+8,centre[2]),(front[0],front[1]+8,front[2])),1)

    def test_rotated_stair_parts_follow_cell_direction(self):
        # direction 2 (what setStair gives the stair out) must differ from direction 0 on the same kit part.
        with tempfile.TemporaryDirectory() as temp:
            a,pa=self.convert(stair_corridor_dump(),temp,"a")
            d=stair_corridor_dump(); d["direction"][3*20+1]=0
            b,pb=self.convert(d,temp,"b")
            ca=json.loads((pa/"room.json").read_text(encoding="utf-8"))["collision"]
            cb=json.loads((pb/"room.json").read_text(encoding="utf-8"))["collision"]
            self.assertNotEqual(ca,cb)
            self.assertEqual(len(ca),len(cb))

    def test_real_seed_dump_converts_deterministically_with_clean_walk(self):
        dump_path=os.environ.get("IXION_RANDFLOOR_DUMP")
        if not dump_path: self.skipTest("set IXION_RANDFLOOR_DUMP to a randfloor_dump JSON")
        with tempfile.TemporaryDirectory() as temp:
            outs=[]
            for name in ("one","two"):
                r=rc.convert_floor(self.pack,self.cfg,Path(dump_path),Path(temp)/name,self.SCALE); outs.append(Path(temp)/name)
            self.assertEqual((r["walk"]["void"],r["walk"]["wall_crossings"]),(0,0))
            self.assertEqual((outs[0]/"room.json").read_bytes(),(outs[1]/"room.json").read_bytes())
            self.assertEqual((outs[0]/"floor.json").read_bytes(),(outs[1]/"floor.json").read_bytes())
            self.assertLess(r["room_json_bytes"],rc.MAX_ROOM_JSON)
            b=r["bounds"]; self.assertLess(b["max"][0]-b["min"][0],14*320); self.assertLess(b["max"][2]-b["min"][2],14*320)


def floor_h(index: "rc.GroundIndex", x: float, z: float) -> float:
    return rc.floor_height(index.heights(x,z))


if __name__=="__main__": unittest.main()
