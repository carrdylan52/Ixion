"""Decode DC1 .mes message files (gedit/e01/e01talk_N.mes and friends) into plain English.

Format (from Chronicle ps2/src/clsmes.cpp ClsMes::GetTextLineDataTop, port/src/localize.cpp ReadRetail):
  s16 count
  s16 unused
  count pairs of s16: (message id, offset in shorts from base)
  base = 1 + count (in shorts from the start of the file)
  text: s16 codes ending with -0xFF (MES_CODE_END)

The code table mirrors Chronicle port/src/gametext.cpp (GameTextChar, ControlName, kGrid, kExtras). Code only: the
decoded text is retail-derived and stays in private packs. Adapted from the wave 5 text lane's scratch decoder.
"""
import struct

KGRID = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'=\"!?#&+-*/%()@|<>{}[]:,.$0123456789"
KGRID_FIRST = -0x2DF
EXTRAS = {
    -0x287: "oe", -0x286: "!", -0x285: "?", -0x284: "A", -0x283: "C", -0x282: "E", -0x281: "E", -0x280: "O",
    -0x27F: "U", -0x27E: "ss", -0x27D: "a", -0x27C: "a", -0x27B: "a", -0x27A: "a", -0x279: "c", -0x278: "e",
    -0x277: "e", -0x276: "e", -0x275: "e", -0x274: "i", -0x273: "i", -0x272: "i", -0x271: "i", -0x270: "n",
    -0x26F: "o", -0x26E: "o", -0x26D: "o", -0x26C: "o", -0x26B: "u", -0x26A: "u", -0x269: "u", -0x268: "u",
}
NAMED = {-0xFD: "page", -0x400: "/color", -0x3FF: "white", -0x3FE: "yellow", -0x3FD: "cyan", -0x3FC: "green",
         -0x3FB: "dark", -0x3FA: "gold", -0x3F9: "grey", -0x301: "highlight", -0x401: "value"}
# name1..name6 are the player and villager names (-0x506..-0x501); insert1.. are inserted fragments.
FAMILY_NAME = (-0x506, -0x501)
MES_END = -0xFF
MES_NEWLINE = -0x100
MES_SPACE = -0xFE
MES_PAGE = -0xFD


def game_char(code: int) -> str:
    if code == MES_SPACE:
        return " "
    if code == MES_NEWLINE:
        return "\n"
    if KGRID_FIRST <= code < KGRID_FIRST + len(KGRID):
        return KGRID[code - KGRID_FIRST]
    return EXTRAS.get(code, "")


def read_mes(data: bytes) -> dict[int, list[int]]:
    n = len(data) // 2
    words = struct.unpack("<%dh" % n, data[:n * 2])
    count = words[0]
    base = 1 + count
    table: dict[int, list[int]] = {}
    for i in range(count):
        mid, off = words[2 + i * 2], words[3 + i * 2]
        at = base + off
        codes = []
        while at < n and words[at] != MES_END:
            codes.append(words[at])
            at += 1
        if at < n:
            table[mid] = codes
    return table


def to_pages(codes: list[int], name1: str = "Max") -> list[str]:
    """Pages of plain text. {name1} (the player's name, code -0x506) becomes ``name1``; other controls are dropped."""
    pages: list[str] = []
    out: list[str] = []
    for code in codes:
        if code == MES_PAGE:
            pages.append("".join(out))
            out = []
            continue
        ch = game_char(code)
        if ch:
            out.append(ch)
        elif code == FAMILY_NAME[0]:
            out.append(name1)
    pages.append("".join(out))
    cleaned = []
    for page in pages:
        lines = [ln.strip() for ln in page.split("\n")]
        text = "\n".join(ln for ln in lines if ln)
        if text:
            cleaned.append(text)
    return cleaned
