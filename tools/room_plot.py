#!/usr/bin/env python3
"""Top-down collision plot of an ixion-room v1 pack (render-free sanity check, no dependencies).

Walkable triangles (|normal.y| >= 0.65) are shaded by height (dark = low, bright = high); steep
triangles (walls) are red. Markers: spawn green, enemy_spawn magenta, exit cyan. +x is right and
+z is down, so the image reads like DC1's grid (row = +z).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import room_converter as rc


def plot(room: dict, size: int = 768) -> bytes:
    tris = room["collision"]
    lo = room["bounds"]["min"]; hi = room["bounds"]["max"]
    span = max(hi[0] - lo[0], hi[2] - lo[2]) or 1.0
    k = (size - 16) / span
    w = int((hi[0] - lo[0]) * k) + 16; h = int((hi[2] - lo[2]) * k) + 16
    px = bytearray(b"\x18\x18\x18\xff" * (w * h))
    depth = [-math.inf] * (w * h)
    walk_y = [p[1] for t in tris for p in t]
    ylo, yhi = min(walk_y), max(walk_y)

    def to_px(x: float, z: float) -> tuple[float, float]:
        return (x - lo[0]) * k + 8, (z - lo[2]) * k + 8

    walls = []
    for t in tris:
        a, b, c = t
        nx = (b[1]-a[1])*(c[2]-a[2]) - (b[2]-a[2])*(c[1]-a[1])
        ny = (b[2]-a[2])*(c[0]-a[0]) - (b[0]-a[0])*(c[2]-a[2])
        nz = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if not length: continue
        if abs(ny) / length < 0.65:
            walls.append(t); continue
        pts = [to_px(p[0], p[2]) for p in t]
        ys = [p[1] for p in t]
        x0 = max(0, int(min(p[0] for p in pts))); x1 = min(w - 1, int(max(p[0] for p in pts)) + 1)
        y0 = max(0, int(min(p[1] for p in pts))); y1 = min(h - 1, int(max(p[1] for p in pts)) + 1)
        (ax, az), (bx, bz), (cx, cz) = pts
        den = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        if abs(den) < 1e-9: continue
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                u = ((bz - cz) * (xx - cx) + (cx - bx) * (yy - cz)) / den
                v = ((cz - az) * (xx - cx) + (ax - cx) * (yy - cz)) / den
                s = 1 - u - v
                if min(u, v, s) < -0.02: continue
                y = u * ys[0] + v * ys[1] + s * ys[2]
                i = yy * w + xx
                if y <= depth[i]: continue
                depth[i] = y
                g = int(60 + 190 * (y - ylo) / ((yhi - ylo) or 1.0))
                px[i*4:i*4+4] = bytes((g, g, min(255, g + 20), 255))

    def dot(x: float, z: float, rgb: tuple[int, int, int], r: int) -> None:
        cx, cz = to_px(x, z)
        for yy in range(int(cz) - r, int(cz) + r + 1):
            for xx in range(int(cx) - r, int(cx) + r + 1):
                if 0 <= xx < w and 0 <= yy < h and (xx - cx) ** 2 + (yy - cz) ** 2 <= r * r:
                    px[(yy*w+xx)*4:(yy*w+xx)*4+4] = bytes((*rgb, 255))

    for t in walls:
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]
            steps = max(1, int(math.dist((a[0], a[2]), (b[0], b[2])) * k))
            for s in range(steps + 1):
                f = s / steps
                xx, yy = to_px(a[0] + (b[0]-a[0]) * f, a[2] + (b[2]-a[2]) * f)
                if 0 <= int(xx) < w and 0 <= int(yy) < h:
                    i4 = (int(yy) * w + int(xx)) * 4
                    px[i4:i4+4] = b"\xc0\x30\x30\xff"
    for key, rgb in (("spawn", (40, 230, 60)), ("enemy_spawn", (230, 40, 230)), ("exit", (40, 220, 230))):
        dot(room[key][0], room[key][2], rgb, 6)
    dot(0.0, 0.0, (255, 200, 0), 2)  # donor origin
    return rc.png_rgba(w, h, bytes(px))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pack", type=Path); ap.add_argument("png", type=Path)
    args = ap.parse_args()
    room = rc.validate_pack(args.pack)
    args.png.write_bytes(plot(room))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
