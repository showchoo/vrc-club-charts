#!/usr/bin/env python3
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

W, H = 1200, 630
BG = (9, 17, 21)
CYAN = (63, 217, 255)
CYAN_DARK = (16, 92, 112)
WHITE = (244, 251, 253)
MUTED = (150, 176, 186)
DARK = (5, 17, 22)

FONT = {
"A":["01110","10001","10001","11111","10001","10001","10001"],
"B":["11110","10001","10001","11110","10001","10001","11110"],
"C":["01111","10000","10000","10000","10000","10000","01111"],
"D":["11110","10001","10001","10001","10001","10001","11110"],
"E":["11111","10000","10000","11110","10000","10000","11111"],
"F":["11111","10000","10000","11110","10000","10000","10000"],
"G":["01111","10000","10000","10111","10001","10001","01111"],
"H":["10001","10001","10001","11111","10001","10001","10001"],
"I":["11111","00100","00100","00100","00100","00100","11111"],
"J":["00111","00010","00010","00010","00010","10010","01100"],
"K":["10001","10010","10100","11000","10100","10010","10001"],
"L":["10000","10000","10000","10000","10000","10000","11111"],
"M":["10001","11011","10101","10101","10001","10001","10001"],
"N":["10001","11001","10101","10011","10001","10001","10001"],
"O":["01110","10001","10001","10001","10001","10001","01110"],
"P":["11110","10001","10001","11110","10000","10000","10000"],
"Q":["01110","10001","10001","10001","10101","10010","01101"],
"R":["11110","10001","10001","11110","10100","10010","10001"],
"S":["01111","10000","10000","01110","00001","00001","11110"],
"T":["11111","00100","00100","00100","00100","00100","00100"],
"U":["10001","10001","10001","10001","10001","10001","01110"],
"V":["10001","10001","10001","10001","10001","01010","00100"],
"W":["10001","10001","10001","10101","10101","10101","01010"],
"X":["10001","10001","01010","00100","01010","10001","10001"],
"Y":["10001","10001","01010","00100","00100","00100","00100"],
"Z":["11111","00001","00010","00100","01000","10000","11111"],
"0":["01110","10001","10011","10101","11001","10001","01110"],
"1":["00100","01100","00100","00100","00100","00100","01110"],
"2":["01110","10001","00001","00010","00100","01000","11111"],
"3":["11110","00001","00001","01110","00001","00001","11110"],
"4":["00010","00110","01010","10010","11111","00010","00010"],
"5":["11111","10000","10000","11110","00001","00001","11110"],
"6":["01110","10000","10000","11110","10001","10001","01110"],
"7":["11111","00001","00010","00100","01000","01000","01000"],
"8":["01110","10001","10001","01110","10001","10001","01110"],
"9":["01110","10001","10001","01111","00001","00001","01110"],
"/":["00001","00010","00010","00100","01000","01000","10000"],
"-":["00000","00000","00000","11111","00000","00000","00000"],
".":["00000","00000","00000","00000","00000","00110","00110"],
":":["00000","00110","00110","00000","00110","00110","00000"],
}


def setpx(buf, x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i:i+3] = bytes(color)


def rect(buf, x0, y0, x1, y1, color):
    x0, x1 = max(0, x0), min(W, x1)
    y0, y1 = max(0, y0), min(H, y1)
    row = bytes(color) * max(0, x1 - x0)
    for y in range(y0, y1):
        i = (y * W + x0) * 3
        buf[i:i + len(row)] = row


def polygon(buf, points, color):
    min_y = max(0, min(y for _, y in points))
    max_y = min(H - 1, max(y for _, y in points))
    n = len(points)
    for y in range(min_y, max_y + 1):
        xs = []
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            if y1 == y2:
                continue
            if min(y1, y2) <= y < max(y1, y2):
                x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                xs.append(x)
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            rect(buf, int(a), y, int(b) + 1, y + 1, color)


def text(buf, x, y, value, scale, color, spacing=1):
    cursor = x
    for ch in value.upper():
        if ch == " ":
            cursor += 4 * scale
            continue
        glyph = FONT.get(ch)
        if glyph is None:
            cursor += 6 * scale
            continue
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    rect(buf, cursor + gx*scale, y + gy*scale,
                         cursor + (gx+1)*scale, y + (gy+1)*scale, color)
        cursor += (5 + spacing) * scale


def png_bytes(rgb: bytearray) -> bytes:
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw.extend(rgb[y*stride:(y+1)*stride])
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def main():
    if len(sys.argv) != 2:
        print("usage: build_og_image.py OUTPUT_DIR", file=sys.stderr)
        return 2
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)

    buf = bytearray(bytes(BG) * W * H)
    rect(buf, 0, 0, 430, H, (11, 31, 38))
    rect(buf, 0, 0, 285, H, (12, 43, 52))

    polygon(buf, [(790,40),(1150,100),(1190,550),(735,610),(690,160)], CYAN)
    polygon(buf, [(1015,90),(1150,100),(1190,550),(1035,568),(970,150)], DARK)
    polygon(buf, [(755,70),(770,72),(716,592),(702,594)], WHITE)

    text(buf, 58, 48, "VRCHAT CRAFTSMANSHIP RANKING", 3, CYAN)
    text(buf, 50, 120, "VRC", 14, WHITE)
    text(buf, 50, 230, "CLUB", 14, WHITE)
    text(buf, 50, 340, "CHARTS", 14, CYAN)
    text(buf, 58, 494, "REVIEWER-BASED / 100 WORLDS", 5, WHITE)
    text(buf, 58, 554, "PUBLIC BETA", 3, MUTED)

    (out / "og-image.png").write_bytes(png_bytes(buf))
    print("Generated", out / "og-image.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
