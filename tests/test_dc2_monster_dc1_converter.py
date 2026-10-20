"""Synthetic control-flow fixtures; no retail assets needed."""
import struct
import unittest
from tools.dc2_monster_dc1_converter import validate_script, ConvertError

def script(op=23,mode=0,deep=False):
    b=bytearray(256)
    b[:4]=b'SB2\0'
    struct.pack_into('<6i',b,4,64,96,32,4,0,3)
    for i,no in enumerate((100,200,500,1000)):struct.pack_into('<2i',b,32+i*8,no,64)
    struct.pack_into('<4i',b,64,0,0,1,0)
    struct.pack_into('<3i',b,96,op,0,mode)
    struct.pack_into('<3i',b,108,3,1,0)
    struct.pack_into('<3i',b,120,15,0,0)
    if deep:
        struct.pack_into('<3i',b,96,19,0,64)
        struct.pack_into('<4i',b,160,80,0,1,0)
        struct.pack_into('<3i',b,176,1,0,0x40)
        struct.pack_into('<3i',b,188,3,1,0)
        struct.pack_into('<3i',b,200,15,0,0)
    return bytes(b)

class ScriptValidation(unittest.TestCase):
    def test_earlier_duplicate_with_globals_cannot_hide_behind_safe_program(self):
        b=bytearray(script())
        # First 200 contains a global load; DC1 selects it, while dict() kept the last.
        struct.pack_into('<i',b,12,208)
        struct.pack_into('<i',b,16,5)
        for i,row in enumerate(((100,64),(200,160),(200,64),(500,64),(1000,64))):
            struct.pack_into('<2i',b,208+8*i,*row)
        struct.pack_into('<4i',b,160,80,0,1,0)
        struct.pack_into('<3i',b,176,1,0,0x40)
        struct.pack_into('<3i',b,188,15,0,0)
        with self.assertRaisesRegex(ConvertError,'duplicate program number 200'):
            validate_script(bytes(b))
    def test_no_globals_referenced_despite_nonzero_reserved_slots(self):
        result=validate_script(script())
        self.assertFalse(result['globals_referenced'])
        self.assertEqual(result['programs'],[100,200,500,1000])
        self.assertEqual(result['reachable_instructions'],3)
    def test_global_load_and_address_rejected(self):
        for op in (1,2):
            for mode in (0x40,0x200):
                with self.subTest(op=op,mode=mode),self.assertRaises(ConvertError):validate_script(script(op,mode))
    def test_global_in_reachable_helper_rejected(self):
        with self.assertRaises(ConvertError):validate_script(script(deep=True))
    def test_branch_outside_file_and_unknown_opcode_rejected(self):
        with self.assertRaises(ConvertError):validate_script(script(0))
        b=bytearray(script());struct.pack_into('<3i',b,96,16,4096,0)
        with self.assertRaises(ConvertError):validate_script(bytes(b))
    def test_missing_program_and_function_stack_rejected(self):
        b=bytearray(script());struct.pack_into('<i',b,32,101)
        with self.assertRaises(ConvertError):validate_script(bytes(b))
        b=bytearray(script());struct.pack_into('<i',b,72,129)
        with self.assertRaises(ConvertError):validate_script(bytes(b))

if __name__=='__main__':unittest.main()
