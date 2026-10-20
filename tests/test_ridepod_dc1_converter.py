import hashlib
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.ridepod_dc1_converter import (ConvertError, SCALE, png_rgba, gs_rgba,
    safe_file, rigid_mds, convert, validate_skin)
from tools.room_converter import parse_pack
from tools.monster_converter import read_mds, mdt_header, walk_mot


def chunk(tag, data):
    return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))


def png(scanlines, w=2, h=2, color=6):
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,color,0,0,0))+
        chunk(b'IDAT',zlib.compress(scanlines))+chunk(b'IEND',b''))


class TextureTests(unittest.TestCase):
    def test_all_five_png_filters_recover_same_rgba(self):
        rows = (bytes([10,30,60,128,4,12,18,255]),bytes([20,40,65,0,7,15,21,255]))
        for kind in range(5):
            encoded = bytearray()
            previous = bytes(8)
            for row in rows:
                encoded.append(kind)
                for i,value in enumerate(row):
                    a = row[i-4] if i >= 4 else 0
                    b = previous[i]
                    c = previous[i-4] if i >= 4 else 0
                    pred = 0
                    if kind == 1: pred=a
                    elif kind == 2: pred=b
                    elif kind == 3: pred=(a+b)//2
                    elif kind == 4:
                        p=a+b-c
                        distances=(abs(p-a),abs(p-b),abs(p-c))
                        pred=(a,b,c)[distances.index(min(distances))]
                    encoded.append((value-pred)&255)
                previous=row
            rgba,w,h=png_rgba(png(bytes(encoded)))
            self.assertEqual((rgba,w,h),(b''.join(rows),2,2))

    def test_gs_alpha_conversion_preserves_rgb(self):
        self.assertEqual(gs_rgba(bytes([10,20,30,255,1,2,3,128,5,6,7,0])),
            bytes([10,20,30,128,1,2,3,64,5,6,7,0]))

    def test_png_crc_truncation_formats_and_expansion_refused(self):
        good=png(b'\0'+bytes(8)+b'\0'+bytes(8))
        bad=bytearray(good); bad[20]^=1
        for data in (bytes(bad),good[:-7],png(bytes(18),color=2),png(bytes(100)),png(bytes(18),w=3000)):
            with self.subTest(size=len(data)), self.assertRaises(ConvertError): png_rgba(data)

    def test_catalog_path_cannot_escape(self):
        root=Path.cwd()
        for name in ('../outside.png','/outside.png','C:/outside.png','a\\b.png'):
            with self.assertRaises(ConvertError): safe_file(root,name)

    def test_inverse_room_scale(self):
        self.assertAlmostEqual(SCALE*1.5584790683,1)
        self.assertAlmostEqual(4*25*SCALE,64.1651222875,places=8)


@unittest.skipUnless(os.environ.get('IXION_DC2_DATA') and os.environ.get('IXION_RIDEPOD_TEST_ROOT'),
    'requires private DC2 data and private output root')
class RealRidepodTests(unittest.TestCase):
    def test_native_geometry_motions_assembly_and_texture_conversion(self):
        root=Path(os.environ['IXION_DC2_DATA'])
        with tempfile.TemporaryDirectory(dir=os.environ['IXION_RIDEPOD_TEST_ROOT'],prefix='ridepod-test-') as tmp:
            output=Path(tmp)/'pack'
            manifest=convert(root,root.parent/'port_data/catalog.json',output)
            self.assertEqual(len(manifest['textures']),5)
            self.assertEqual(manifest['assembly']['leg_joint'],'body1')
            self.assertEqual(manifest['assembly']['body_joint'],'spine')
            self.assertEqual(manifest['weapons']['arm']['attack'],60)
            self.assertEqual(manifest['weapons']['gun']['attack'],138)
            for part,name in (('leg01','leg01'),('body01','body01'),('arm01','arm01'),('arm04','arm04')):
                native=parse_pack((root/f'dungeon/robo/{part}.chr').read_bytes())
                result=parse_pack((output/f'{name}.chr').read_bytes())
                source=native[f'{part}.mds'].data
                actual=result[f'{name}.mds'].data
                objects=read_mds(source,part)
                self.assertEqual(len(read_mds(actual,name)),len(objects))
                expected=bytearray(source)
                for obj in objects:
                    if not obj.mesh: continue
                    header=mdt_header(source,obj.mesh)
                    for i in range(header['material_num']):
                        at=obj.mesh+header['material_ofs']+96*i+52
                        old=source[at:at+32].split(b'\0')[0]
                        expected[at:at+44]=(b'ixrp_'+old).ljust(44,b'\0')
                    if name=='body01' and obj.name.startswith('light--'):
                        struct.pack_into('<i',expected,16+112*obj.index+40,0)
                self.assertEqual(actual,bytes(expected))
                if name!='body01':
                    self.assertEqual(result[f'{name}.mot'].data,native[f'{part}.mot'].data)
                    self.assertGreater(walk_mot(result[f'{name}.mot'].data,len(objects),name)['channels'],0)
                    self.assertIn(b'KEY_START 0',result['info.cfg'].data)
                if name=='arm01':
                    for suffix in ('bbp','wgt'):
                        self.assertEqual(result[f'arm01.{suffix}'].data,native[f'arm01.{suffix}'].data)
            for tex in manifest['textures']:
                rgba,w,h=png_rgba((root.parent/'port_data'/tex['source_png']).read_bytes())
                raw=(output/tex['file']).read_bytes()
                self.assertEqual(raw,gs_rgba(rgba))
                self.assertEqual(hashlib.sha256(raw).hexdigest(),tex['sha256'])
                self.assertEqual(len(raw),w*h*4)
            with self.assertRaises(ConvertError): convert(root,root.parent/'port_data/catalog.json',output)

    def test_skin_validation_refuses_truncation_frames_and_bind_extent(self):
        root=Path(os.environ['IXION_DC2_DATA'])
        native=parse_pack((root/'dungeon/robo/arm01.chr').read_bytes())
        mds,bbp,wgt=(native[f'arm01.{s}'].data for s in ('mds','bbp','wgt'))
        self.assertGreater(validate_skin(mds,bbp,wgt)['weights'],0)
        for bones,weights in ((bbp[:-1],wgt),(bbp,wgt[:-1]),(bbp,bytes([255])*32+wgt[32:])):
            with self.assertRaises(ConvertError):validate_skin(mds,bones,weights)

    def test_refuses_mdt_unsupported_face_layout_and_missing_texture(self):
        root=Path(os.environ['IXION_DC2_DATA'])
        source=parse_pack((root/'dungeon/robo/leg01.chr').read_bytes())['leg01.mds'].data
        with self.assertRaises(ConvertError): rigid_mds(source,'leg',{})
        mesh=next(o.mesh for o in read_mds(source,'leg') if o.mesh)
        header=mdt_header(source,mesh)
        bad=bytearray(source)
        struct.pack_into('<I',bad,mesh+header['faces_ofs']+16,0x103)
        with self.assertRaises(ConvertError): rigid_mds(bytes(bad),'leg',{'r01a04':'ixrp_r01a04'})

if __name__=='__main__': unittest.main()
